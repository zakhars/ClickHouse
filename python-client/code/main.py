import sys
import time
from pathlib import Path
import random
import clickhouse_connect
import traceback

from utils import avg_time, trace, print_clickhouse_rowset
import sql

CONFIG = {
    'host': 'clickhouse-marketdata',
    'port': 8123,
    'username': 'mduser',
    'password': 'mdpassword',
    'database': 'marketdata'
}

NUM_QUOTES = 100000
NUM_TRADES = 10000
CHUNK_SIZE = 1000
NS_IN_SEC  = 1000000000


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
   print("\n", flush=True)
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


def gen_quotes(quotes_total, chunk_size):
   time_ns = time.time_ns()
   rows_inserted = 0
   for n in range(0, quotes_total, chunk_size):
      quotes = []
      for m in range(n, n+chunk_size):
         rows_inserted += 1
         quotes.append(
            (random.randint(1, 100),  # bid_qty
             random.randint(1, 100),  # ask_qty
             random.randint(1, 1000), # bid_price
             random.randint(1, 1000), # ask_price
             time_ns,                 # local_ts
             time_ns,                 # exch_ts (same as local as it is not too important for this test)
             random.choice(['f.ep.z26', 'f.ep.h26']), # symbol
             'cme',                   # source
             time_ns))                # seqno (any increasing number is suitable)
      # next quote comes within random interval from 1 ns to 1 sec
      time_ns = time_ns + random.randint(1, NS_IN_SEC)
      yield quotes
   if rows_inserted != quotes_total:
      raise Exception(f'Wrong number of rows inserted into trades. Expected {quotes_total}, got {rows_inserted}')


def gen_trades(trades_total, chunk_size):
   time_ns = time.time_ns()
   rows_inserted = 0
   for n in range(0, trades_total, chunk_size):
      trades = []
      for m in range(n, n+chunk_size):
         rows_inserted += 1
         trades.append(
            (random.randint(1, 100),  # qty
             random.randint(0, 2),    # side
             random.randint(1, 1000), # price
             time_ns,                 # local_ts
             time_ns,                 # exch_ts
             random.choice(['f.ep.z26', 'f.ep.h26', 'f.ep.m27']), # symbol (some can be absent in quotes)
             'cme',                   # source
             time_ns))                # seqno
      # next trade comes within random interval from 1 ns to 100 sec
      # TODO: make sure trades and quotes are distributed across the same time window
      time_ns = time_ns + random.randint(1, NS_IN_SEC * 100)
      yield trades
   if rows_inserted != trades_total:
      raise Exception(f'Wrong number of rows inserted into trades. Expected {trades_total}, got {rows_inserted}')


@trace('Inserting data')
@avg_time(n_calls=1, verbose=True)
def init_data(client, chunk_size=1):
    for chunk in gen_quotes(NUM_QUOTES, chunk_size):
       client.insert(table='md_quotes', data=chunk, column_names=['bid_qty', 'ask_qty', 'bid_price', 'ask_price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])
    for chunk in gen_trades(NUM_TRADES, chunk_size):
       client.insert(table='md_trades', data=chunk, column_names=['qty', 'side', 'price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])


@trace('Checking data')
def check_data(client, verbose=False):
    if verbose:
       quotes = client.query("""
         select bid_qty, ask_qty, bid_price, ask_price, toString(local_ts) as local_ts, symbol from md_quotes order by local_ts asc limit 5 union all
         select bid_qty, ask_qty, bid_price, ask_price, toString(local_ts) as local_ts, symbol from md_quotes order by local_ts desc limit 5""")
       print('\nQuotes')
       print_clickhouse_rowset(quotes, 10)
       trades = client.query("""
         select qty, side, price, toString(local_ts) as local_ts, symbol from md_trades order by local_ts asc limit 5 union all
         select qty, side, price, toString(local_ts) as local_ts, symbol from md_trades order by local_ts desc limit 5""")
       print('\nTrades')
       print_clickhouse_rowset(trades, 10)

    quotes_row_count = client.query('SELECT COUNT(*) FROM md_quotes')
    trades_row_count = client.query('SELECT COUNT(*) FROM md_trades')
    if quotes_row_count.result_rows[0][0] != NUM_QUOTES or trades_row_count.result_rows[0][0] != NUM_TRADES:
       raise Exception('Wrong number of quotes or trades')


@trace('Joining')
@avg_time(n_calls=1)
def join_simple(client, rows_to_print=-1):
    joined = client.query(sql.q_simple_asof_join)
    print(f'\nNumber of rows returned by JOIN: {joined.row_count}. Top {rows_to_print} rows:' )
    print_clickhouse_rowset(joined, rows_to_print)


def main():
   client = None
   try:
      client = connect()
      #reset_database(client) # Drop tables to be able to re-create them each time with custom settings
      init_schema(client, [sql.sc_create_table_md_quotes, sql.sc_create_table_md_trades])
      truncate_data(client)
      init_data(client, chunk_size=CHUNK_SIZE)
      check_data(client, True)
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
