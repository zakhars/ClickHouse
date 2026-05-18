import sys
from pathlib import Path
import random
import clickhouse_connect
import traceback
from datetime import datetime, timezone, timedelta

from utils import avg_time, trace, print_clickhouse_rowset
import sql

CONFIG = {
   'host': 'clickhouse-marketdata',
   'port': 8123,
   'username': 'mduser',
   'password': 'mdpassword',
   'database': 'marketdata'
}

NUM_QUOTES = 1000000
NUM_TRADES = 10000
INSERT_CHUNK_SIZE = 100000 # tried from 1 to 1M - optimal size is around 100k - as fast as 1M, but looks safer
REGENERATE_DATA = False


BASE_DATA = {
   'CME':   [('F.EPZ26',      100),
             ('F.ENQH26',     200),
             ('F.ENQM27',     230),
             ('F.EPU27',      150)
             ],
   'NYMEX': [('C.BP6H27110',  10),
             ('P.EU6Z27150',  25),
             ('C.EU6Z261000', 15)
             ],
   'LME':   [('F.SDAS3H28',   20),
             ('F.SDAS9H27',   25),
             ('F.SDAS9H27',   10)]
}

BASE_TS_LOCAL  = int(datetime(2026, 4, 25, 8, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3))).timestamp()) * NS_IN_SEC
BASE_TS_EXCH   = int(datetime(2026, 4, 25, 8, 0, 0, 0, tzinfo=timezone(timedelta(hours= 5))).timestamp()) * NS_IN_SEC

NS_IN_SEC = 1000000000

@trace('Connecting to server')
def connect():
   client = clickhouse_connect.get_client(**CONFIG)
   if client.query('SELECT currentDatabase()').result_rows[0][0] != CONFIG['database']:
      raise Exception(f"Database {CONFIG['database']} should be created during ClickHouse container startup")
   return client


@trace('Dropping all tables')
def reset_database(client):
   client.query(f'TRUNCATE DATABASE {CONFIG['database']}')


@trace('Truncating data')
def truncate_data(client):
   tables = client.query(f"SHOW TABLES FROM {CONFIG['database']}").result_rows
   for table in tables:
      table_name = table[0]
      client.command(f'TRUNCATE TABLE {table_name}')


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


@trace('Inserting quotes')
@avg_time(n_calls=1, verbose=True)
def insert_quotes(client, chunk_size=1):
   if chunk_size > NUM_QUOTES: chunk_size = NUM_QUOTES
   sources = list(BASE_DATA.keys())
   local_ts = BASE_TS_LOCAL
   exch_ts  = BASE_TS_EXCH
   min_ts = local_ts # save earliest timestamp
   seqno = 1
   quotes = []
   for i in range(NUM_QUOTES):
      source = random.choice(sources)
      contract_idx = random.randint(0, len(BASE_DATA[source])-1) # pick arbitrary symbol/price
      symbol = BASE_DATA[source][contract_idx][0]
      bid_qty = random.randint(10, 1000)
      ask_qty = random.randint(10, 1000)

      base_price = BASE_DATA[source][contract_idx][1]
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

   if rows_inserted != NUM_QUOTES:
      raise Exception(f'Wrong number of rows inserted into md_quotes. Expected {NUM_QUOTES}, got {rows_inserted}')

   min_dt = datetime.fromtimestamp(min_ts   // NS_IN_SEC).strftime('%Y-%m-%d %H:%M:%S')
   max_dt = datetime.fromtimestamp(local_ts // NS_IN_SEC).strftime('%Y-%m-%d %H:%M:%S')
   print(f'\nQuotes time range is {min_dt} to {max_dt}')

   return quotes


@trace('Inserting trades')
@avg_time(n_calls=1, verbose=True)
def insert_trades(client, quotes, chunk_size=1):
   if chunk_size > NUM_TRADES: chunk_size = NUM_TRADES

   available_quotes = [i for i in range(len(quotes))]
   sides = [0, 1, 2]
   weights = [0.02, 0.44, 0.44] # undef is less frequent, than bid and ask
   seqno = 1
   trades = []
   for i in range(NUM_TRADES):
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

   if rows_inserted != NUM_TRADES:
      raise Exception(f'Wrong number of rows inserted into md_trades. Expected {NUM_QUOTES}, got {rows_inserted}')


@trace('Checking data')
def check_data(client, verbose=False):
   if verbose:
      quotes = client.query("""
         with ranked as (
         select bid_qty, ask_qty, round(bid_price, 5) as bid_price, round(ask_price, 5) as ask_price, toString(local_ts) as local_ts, toString(exch_ts) as exch_ts, symbol, source, seqno
         from md_quotes order by local_ts asc limit 5
         union all
         select bid_qty, ask_qty, round(bid_price, 5) as bid_price, round(ask_price, 5) as ask_price, toString(local_ts) as local_ts, toString(exch_ts) as exch_ts, symbol, source, seqno
         from md_quotes order by local_ts desc limit 5)
         select * from ranked order by local_ts
      """)
      print('\nQuotes')
      print_clickhouse_rowset(quotes, 10)
      trades = client.query("""
         with ranked as (
         select qty, side, round(price, 5) as price, toString(local_ts) as local_ts, toString(exch_ts) as exch_ts, symbol, source, seqno
         from md_trades order by local_ts asc limit 5
         union all
         select qty, side, round(price, 5) as price, toString(local_ts) as local_ts, toString(exch_ts) as exch_ts, symbol, source, seqno
         from md_trades order by local_ts desc limit 5)
         select * from ranked order by local_ts
      """)
      print('\nTrades')
      print_clickhouse_rowset(trades, 10)

   quotes_row_count = client.query('SELECT COUNT(*) FROM md_quotes')
   trades_row_count = client.query('SELECT COUNT(*) FROM md_trades')
   if quotes_row_count.result_rows[0][0] != NUM_QUOTES or trades_row_count.result_rows[0][0] != NUM_TRADES:
      raise Exception('Wrong number of quotes or trades')


@trace('Checking DB size')
def get_physical_size(client):
   dbname = CONFIG['database']
   sizes = client.query(
      f"SELECT table, sum(bytes_on_disk) AS size_on_disk FROM system.parts WHERE database='{dbname}' GROUP BY table")
   print_clickhouse_rowset(sizes)


@trace('Joining')
@avg_time(n_calls=10, verbose=True)
def join_simple(client, rows_to_print=-1):
   joined = client.query(sql.q_simple_asof_join)
   print(f'\nNumber of rows returned by JOIN: {joined.row_count}. Top {rows_to_print} rows:')
   print_clickhouse_rowset(joined, rows_to_print)


def main():
   client = None
   try:
      client = connect()
      if REGENERATE_DATA:
         reset_database(client) # Drop tables to be able to re-create them each time with custom settings
         init_schema(client, [sql.sc_create_table_md_quotes, sql.sc_create_table_md_trades])
         truncate_data(client)
         quotes = insert_quotes(client, chunk_size=INSERT_CHUNK_SIZE)
         insert_trades(client, quotes, chunk_size=INSERT_CHUNK_SIZE)
         check_data(client, True)
         get_physical_size(client)
      join_simple(client=client, rows_to_print=10)
   except Exception as e:
      print(f'\n\nException occurred in main(): {e}\n', flush=True)
      traceback.print_exc()
      return -1
   finally:
      if client: client.close()
   return 0


if __name__ == '__main__':
   sys.exit(main())
