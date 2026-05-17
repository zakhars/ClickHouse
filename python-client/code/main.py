import sys
import time
from pathlib import Path
import random
import clickhouse_connect

from utils import avg_time
import sql

CONFIG = {
    'host': 'clickhouse-marketdata',
    'port': 8123,
    'username': 'mduser',
    'password': 'mdpassword',
    'database': 'marketdata'
}

NUM_QOUTES = 1000
NUM_TRADES = 100
NS_IN_SEC  = 1000000000
NS_IN_MS   = 1000000

def connect():
   client = clickhouse_connect.get_client(**CONFIG)
   print(f"Connected to a database {client.query('SELECT currentDatabase()').result_rows[0][0]}", flush=True)
   return client

def reset_database(client):
   client.query(f'TRUNCATE DATABASE {CONFIG['database']}')

def truncate_data(client):
   tables = client.query(f"SHOW TABLES FROM {CONFIG['database']}").result_rows
   print("\n", flush=True)
   for table in tables:
      table_name = table[0]
      print(f"Truncating table {table_name}", flush=True)
      client.command(f'TRUNCATE TABLE {table_name}')

def init_schema(client, sc_scripts):
   for script in sc_scripts:
      client.command(script)

# Alternatively load scripts from given folder in case we can't modify SQL scripts
# Function assumes scripts should be applied in alphabetical order
def init_schema_from_script_files(client, scripts_path):
    path = Path(scripts_path)
    sc_scripts = sorted([str(f.resolve()) for f in path.glob('*_sc_*')])
    for script_name in sc_scripts:
        script = Path(script_name).read_text(encoding='utf-8')
        client.command(script)

def gen_quotes(quotes_total, chunk_size):
   time_ns = time.time_ns()
   for n in range(0, quotes_total, chunk_size):
      quotes = []
      for m in range(n, n+chunk_size):
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

def gen_trades(trades_total, chunk_size):
   time_ns = time.time_ns()
   for n in range(0, trades_total, chunk_size):
      trades = []
      for m in range(n, n+chunk_size):
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


@avg_time(n_calls=1, verbose=True)
def init_data(client, chunk_size=1):

    for chunk in gen_quotes(NUM_QOUTES, chunk_size):
       client.insert(table='md_quotes', data=chunk, column_names=['bid_qty', 'ask_qty', 'bid_price', 'ask_price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])

    for chunk in gen_trades(NUM_TRADES, chunk_size):
       client.insert(table='md_trades', data=chunk, column_names=['qty', 'side', 'price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])


def check_data(client, verbose=False):
    if verbose:
       quotes = client.query("""
         select bid_qty, ask_qty, bid_price, ask_price, toString(local_ts), symbol from md_quotes order by local_ts asc limit 5 union all
         select bid_qty, ask_qty, bid_price, ask_price, toString(local_ts), symbol from md_quotes order by local_ts desc limit 5""")
       print('\nQuotes', *quotes.result_rows, sep='\n')
       trades = client.query("""
         select qty, side, price, toString(local_ts), symbol from md_trades order by local_ts asc limit 5 union all
         select qty, side, price, toString(local_ts), symbol from md_trades order by local_ts desc limit 5""")
       print('\nTrades', *trades.result_rows, sep='\n')

    quotes_row_count = client.query('SELECT COUNT(*) FROM md_quotes')
    trades_row_count = client.query('SELECT COUNT(*) FROM md_trades')
    return quotes_row_count.result_rows[0][0] == NUM_QOUTES and trades_row_count.result_rows[0][0] == NUM_TRADES


@avg_time(n_calls=1)
def join_simple(client, rows_to_print=0):
    joined = client.query(sql.q_simple_asof_join)
    rows_total = joined.result_rows[0][0]
    print('\nNumber of rows returned by JOIN', rows_total)
    if rows_to_print: print(f'\nTop {rows_to_print} joined', *joined.result_rows[:rows_to_print], sep='\n')


def main():
   client = None
   try:
      print("\nConnecting to database... ", flush=True, end='')
      client = connect()
      print(f"Success", flush=True)

      # Drop tables to be able to re-create them each time with custom settings
      print("\nDropping all tables... ", flush=True, end='')
      reset_database(client)
      print("Success", flush=True)

      print("\nCreating tables... ", flush=True, end='')
      init_schema(client, [sql.sc_create_table_md_quotes, sql.sc_create_table_md_trades])
      #init_schema(client, './sql')
      print("Success", flush=True)

      print("\nTruncating data... ", flush=True, end='')
      truncate_data(client)
      print(f"Success", flush=True)

      for chunk_size in [10]:
         print(f"\nInserting data with batch size {chunk_size}... ", flush=True, end='')
         init_data(client, chunk_size=chunk_size)
         print("Success", flush=True)

         print("\nChecking data... ", flush=True, end='')
         success = check_data(client, True)
         print("Success" if success else "!!!Failure: unexpected rows count", flush=True)

      print("\nJoining... ", flush=True, end='')
      join_simple(client=client, rows_to_print=10)
      print("Success", flush=True)

   except Exception as e:
      print(f'\n\nException occurred in main(): {e}', flush=True)
   finally:
      if client: client.close()

if __name__ == '__main__':
   sys.exit(main())
