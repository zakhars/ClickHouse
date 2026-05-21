import sys
import time
from pathlib import Path
import random
import clickhouse_connect
import traceback
from datetime import datetime

from utils import avg_time, trace, print_clickhouse_rowset, print_test_header, print_green, print_red, print_blue
import sql
import config
from config import NS_IN_SEC

@trace('Connecting to server')
def connect():
   client = clickhouse_connect.get_client(**config.DB)
   if client.query('SELECT currentDatabase()').result_rows[0][0] != config.DB['database']:
      raise Exception(f"Database {config.DB['database']} should be created during ClickHouse container startup")
   return client


@trace('Dropping all tables')
def reset_database(client):
   client.query(f'TRUNCATE DATABASE {config.DB['database']}')


@trace('Creating schema')
def init_schema(client, sc_scripts):
   for script in sc_scripts:
      client.command(script)


# Alternatively load scripts from given folder in case we can't modify SQL scripts
# Function assumes scripts should be applied in alphabetical order
@trace('Creating schema from files')
def init_schema_from_script_files(client, scripts_path):
   path = Path(scripts_path)
   sc_scripts = sorted([str(f.resolve()) for f in path.glob('*_sc_*')])
   for script_name in sc_scripts:
      script = Path(script_name).read_text(encoding='utf-8')
      client.command(script)

def print_script_code(prefix, code):
   print(f'\n{prefix} code:', flush=True)
   for script in code:
      print(script, flush=True)
      print('\n')

@trace('Inserting quotes')
@avg_time(n_calls=1, verbose=config.VERBOSE_STATS)
def insert_quotes(client, chunk_size=1):
   if chunk_size > config.NUM_QUOTES: chunk_size = config.NUM_QUOTES
   sources = list(config.BASE_DATA.keys())
   local_ts = config.BASE_TS_LOCAL
   exch_ts  = config.BASE_TS_EXCH
   min_ts = local_ts # save earliest timestamp
   seqno = 1
   quotes = []
   for i in range(config.NUM_QUOTES):
      source = random.choice(sources)
      contract_idx = random.randint(0, len(config.BASE_DATA[source])-1) # pick arbitrary symbol/price
      symbol = config.BASE_DATA[source][contract_idx][0]
      bid_qty = random.randint(10, 1000)
      ask_qty = random.randint(10, 1000)

      base_price = config.BASE_DATA[source][contract_idx][1]
      price_deviation = random.uniform(-0.01, 0.01)
      middle_price = base_price * (1 + price_deviation)
      bid_ask_spread = middle_price * random.uniform(0.001, 0.010)
      bid_price = round(middle_price - bid_ask_spread, 5) # tick size 0.00001
      ask_price = round(middle_price + bid_ask_spread, 5)

      quotes.append((bid_qty, ask_qty, bid_price, ask_price, local_ts, exch_ts, symbol, source, seqno))

      # next quote comes within random interval from 1 ns to 1 sec
      next_quote_ts_shift = random.randint(1, NS_IN_SEC)
      local_ts += next_quote_ts_shift
      exch_ts  += next_quote_ts_shift
      seqno += 1  # any increasing number is suitable

   rows_inserted = 0
   begin = 0
   end = begin + chunk_size
   while begin < len(quotes):
      # insert chunk
      client.insert(table='md_quotes', data=quotes[begin:end],
         column_names=['bid_qty','ask_qty','bid_price','ask_price','local_ts','exch_ts','symbol','source','seqno'])

      rows_inserted += chunk_size
      begin += chunk_size
      end += chunk_size

   if rows_inserted != config.NUM_QUOTES:
      raise Exception(f'Wrong number of rows inserted into md_quotes. Expected {config.NUM_QUOTES}, got {rows_inserted}')

   min_dt = datetime.fromtimestamp(min_ts   // NS_IN_SEC).strftime('%Y-%m-%d %H:%M:%S')
   max_dt = datetime.fromtimestamp(local_ts // NS_IN_SEC).strftime('%Y-%m-%d %H:%M:%S')
   print(f'Inserted quotes time range is {min_dt} to {max_dt}')

   return quotes


@trace('Inserting trades')
@avg_time(n_calls=1, verbose=config.VERBOSE_STATS)
def insert_trades(client, quotes, chunk_size=1):
   if chunk_size > config.NUM_TRADES: chunk_size = config.NUM_TRADES

   available_quotes = [i for i in range(len(quotes))]
   sides = [0, 1, 2]
   weights = [0.02, 0.44, 0.44] # undef is less frequent, than bid and ask
   seqno = 1
   trades = []
   for i in range(config.NUM_TRADES):
      index = random.randrange(len(available_quotes))
      quote_idx = available_quotes[index]
      quote = quotes[quote_idx]
      symbol = quote[6]
      source = quote[6]
      bid_price = quote[2]
      ask_price = quote[3]
      quote_ts_local = quote[4]
      quote_ts_exch = quote[5]
      qty = random.randint(1, 1000)

      trade_shift_ts = random.randint(0, NS_IN_SEC // 10000) # trade is at the same time or up to 100 μs later than quote

      local_ts = quote_ts_local + trade_shift_ts
      exch_ts  = quote_ts_exch  + trade_shift_ts

      side = random.choices(sides, weights=weights, k=1)[0]

      if side == 1: # buy
         price = ask_price
      elif side == 2: # sell
         price = bid_price
      else:
         price = round((ask_price + bid_price) / 2, 5) # TODO: is this a correct idea?

      trades.append((qty, side, price, local_ts, exch_ts, symbol, source, seqno))

      seqno += 1
      del available_quotes[index] # do not reuse same quote twice for trade


   rows_inserted = 0
   begin = 0
   end = begin + chunk_size
   while begin < len(trades):
      # insert chunk
      client.insert(table='md_trades', data=trades[begin:end],
         column_names=['qty', 'side', 'price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])

      rows_inserted += chunk_size
      begin += chunk_size
      end += chunk_size

   if rows_inserted != config.NUM_TRADES:
      raise Exception(f'Wrong number of rows inserted into md_trades. Expected {config.NUM_QUOTES}, got {rows_inserted}')


@trace('Checking data')
def check_data(client, verbose=True):
   quotes_row_count = client.query(sql.q_select_quotes_count).result_rows[0][0]
   trades_row_count = client.query(sql.q_select_trades_count).result_rows[0][0]

   if verbose:
      print(f'Quotes inserted {quotes_row_count}. First and last rows:', flush=True)
      quotes = client.query(sql.q_select_from_quotes)
      print_clickhouse_rowset(quotes, 10)

      print(f'Trades inserted {trades_row_count}. First and last rows:', flush=True)
      trades = client.query(sql.q_select_from_trades)
      print_clickhouse_rowset(trades, 10)

      print_physical_size(client)

   if quotes_row_count != config.NUM_QUOTES:
      raise Exception(f'Wrong number of quotes. Expected {config.NUM_QUOTES}, got {quotes_row_count}')
   if trades_row_count != config.NUM_TRADES:
      raise Exception(f'Wrong number of trades. Expected {config.NUM_TRADES}, got {trades_row_count}')


@trace('Checking DB size')
def print_physical_size(client):
   dbname = config.DB['database']
   sizes = client.query(
      f"SELECT table, sum(bytes_on_disk) AS size_on_disk FROM system.parts WHERE database='{dbname}' GROUP BY table")
   print_clickhouse_rowset(sizes, num_rows=100)


@trace('Dropping MV')
def drop_mv(client, sc_script):
   client.command(sc_script)


@trace('Creating MV')
def create_mv(client, sc_script):
   client.command(sc_script)


def join_check_and_warmup(client, settings='', filter=''):
   joined = client.query(sql.q_asof_join + '\n' + filter, settings=settings)
   print(f'JOIN returned {len(joined.result_rows)} rows', flush=True)


@avg_time(n_calls=10, verbose=config.VERBOSE_STATS)
def join_asof(client, settings='', filter='', rows_to_print=-1):
   joined = client.query(sql.q_asof_join + '\n' + filter, settings=settings)
   print_clickhouse_rowset(joined, rows_to_print)

@trace('Selecting from MV')
@avg_time(n_calls=10, verbose=config.VERBOSE_STATS)
def select_from_mv(client, rows_to_print=-1):
   selected = client.query(sql.q_select_from_mv)
   print_clickhouse_rowset(selected, rows_to_print)

def generate_dataset(client, engine, partition, orderby, primarykey, settings):
   reset_database(client)  # Drop tables to be able to re-create them with custom settings

   table_creation_settings = '\n'.join([engine, partition, orderby, primarykey, settings])

   patched_sc_scripts = [
      sql.sc_create_table_md_quotes + table_creation_settings,
      sql.sc_create_table_md_trades + table_creation_settings,
   ]

   print_script_code('Table creation scripts', patched_sc_scripts)

   init_schema(client, patched_sc_scripts)
   quotes = insert_quotes(client, config.INSERT_CHUNK_SIZE)
   insert_trades(client, quotes, config.INSERT_CHUNK_SIZE)

   print("Completing partitioning after inserting data", flush=True)
   client.command(sql.q_complete_partitioning_quotes)
   client.command(sql.q_complete_partitioning_trades)
   print('Waiting additional time after data partitioning', flush=True)
   time.sleep(10)

def generate_mv(client):
   drop_mv(client, sql.sc_drop_mv)
   create_mv(client, sql.sc_create_mv)


def main():
   client = None
   try:
      client = connect()

      # Default settings
      engine = config.ENGINE['merge_tree']
      partition = config.PARTITION_BY['none']
      orderby = config.ORDER_BY['symbol_time']
      primarykey = config.PRIMARY_KEY['none']
      settings = config.INDEX_GRANULARITY['8192']
      filter = config.FILTER['none']

      print(f'========== Benchmarks start ==========', flush=True)

      print_test_header(1, 'Compare ENGINE without partitions')
      # We may want to skip initial dataset generation
      if config.REGENERATE_DATA: generate_dataset(client, engine, partition, orderby, primarykey, settings)
      generate_mv(client)
      check_data(client, verbose=True)
      print_script_code('ASOF JOIN', [sql.q_asof_join])
      join_check_and_warmup(client, '', filter)
      for join_settings in config.JOIN_SETTINGS:
         print_blue(f'\nJoin settings: {join_settings}')
         print(f'Executing:', flush=True)
         join_asof(client=client, settings=join_settings, filter=filter, rows_to_print=-1)
      select_from_mv(client, rows_to_print=-1)

      print_test_header(2, 'Compare ENGINE with partitioning by DAY')
      partition = config.PARTITION_BY['toYYYYMMDD']
      generate_dataset(client, engine, partition, orderby, primarykey, settings)
      generate_mv(client)
      check_data(client, verbose=True)
      print_script_code('ASOF JOIN', [sql.q_asof_join])
      join_check_and_warmup(client, '', filter)
      for join_settings in config.JOIN_SETTINGS:
         print_blue(f'\nJoin settings: {join_settings}')
         print(f'Executing:', flush=True)
         join_asof(client=client, settings=join_settings, filter=filter, rows_to_print=-1)
      select_from_mv(client, rows_to_print=-1)

      print(f'========== Benchmarks stop ==========', flush=True)

   except Exception as e:
      print_red(f'\n\nException occurred in main(): {e}\n')
      traceback.print_exc()
      return -1
   finally:
      if client: client.close()
   return 0


if __name__ == '__main__':
   sys.exit(main())
