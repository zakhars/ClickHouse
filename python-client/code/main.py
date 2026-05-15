import sys
import clickhouse_connect
import time
from pathlib import Path
import random
from functools import wraps
import statistics

def avg_time(n_calls=10, verbose=True, return_stats=False):
   def decorator(func):
      @wraps(func)
      def wrapper(*args, **kwargs):
         times = []

         result = None
         for i in range(n_calls):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            times.append(end_time - start_time)

         avg_time = statistics.mean(times)
         min_time = min(times)
         max_time = max(times)
         std_dev = statistics.stdev(times) if len(times) > 1 else 0

         if verbose:
            print(f"\nStats for function '{func.__name__}':")
            print(f"   Calls: {n_calls}")
            print(f"   Avg: {avg_time:.6f} s ({avg_time * 1000:.3f} ms)")
            print(f"   Min: {min_time:.6f} s")
            print(f"   Max: {max_time:.6f} s")
            print(f"   Stddev: {std_dev:.6f} s")

         if return_stats:
            return result, {
               'avg': avg_time,
               'min': min_time,
               'max': max_time,
               'std': std_dev,
               'times': times
            }
         return result
      return wrapper
   return decorator


def connect(host, db, usr, pwd):
    client = clickhouse_connect.get_client(host=host, username=usr, password=pwd, database=db)
    client.query('SELECT 1')
    return client

def init_schema(client, scripts_path):
    path = Path(scripts_path)
    sc_scripts = sorted([str(f.resolve()) for f in path.glob('*_sc_*')])
    for script_name in sc_scripts:
        script = Path(script_name).read_text(encoding='utf-8')
        client.command(script)

@avg_time(n_calls=10, verbose=True)
def init_data(client, batch_size=1):
    client.query('TRUNCATE TABLE default.md_trades')
    client.query('TRUNCATE TABLE default.md_quotes')

    trades = []
    cur_ns = time.time_ns() - 1000000
    i = 0
    for n in range(10000 // batch_size):
        for m in range(batch_size):
            trades.append(
                (random.randint(1,100),
                 random.randint(0,2),
                 random.randint(1,1000),
                 cur_ns+i,
                 cur_ns+i,
                 random.choice(['f.ep.z26', 'f.ep.h26']),
                 'src',
                 n * m))
            i += 1000000
    client.insert('default.md_trades', trades, column_names=['qty', 'side', 'price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])


    quotes = []
    i = 0
    for n in range(1000000 // batch_size):
        for m in range(batch_size):
            quotes.append(
                (random.randint(1,100),
                 random.randint(1,100),
                 random.randint(1,1000),
                 random.randint(1,1000),
                 cur_ns + i,
                 cur_ns + i,
                 random.choice(['f.ep.z26', 'f.ep.h26']),
                 'src',
                 n * m))
            i += 1000000
    client.insert('default.md_quotes', quotes, column_names=['bid_qty', 'ask_qty', 'bid_price', 'ask_price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])


def check_data(client):
    trades_row_count = client.query('SELECT COUNT(*) FROM default.md_trades')
    quotes_row_count = client.query('SELECT COUNT(*) FROM default.md_quotes')
    trades = client.query('select qty, side, price, toString(local_ts), toString(exch_ts), symbol, source, seqno from default.md_trades order by local_ts  limit 10')
    print('\nTop 10 trades')
    for row in trades.result_rows:
        print(row)
    quotes = client.query('select bid_qty, ask_qty, bid_price, ask_price, toString(local_ts), toString(exch_ts), symbol, source, seqno from default.md_quotes order by local_ts desc limit 10')
    print('\nTop 10 quotes')
    for row in quotes.result_rows:
        print(row)
    return trades_row_count.result_rows[0][0] == 10000 and quotes_row_count.result_rows[0][0] == 1000000

@avg_time(n_calls=100, verbose=True)
def join_simple(client):
    query = """
         SELECT 
             t.symbol,
             t.local_ts,
             t.price as trade_price,
             t.qty,
             q.local_ts,
             q.bid_price,
             q.ask_price,
             (t.price - q.bid_price) as spread_to_bid,
             (q.ask_price - t.price) as spread_to_ask
         FROM default.md_trades AS t
         ASOF LEFT JOIN default.md_quotes AS q
             ON t.symbol = q.symbol 
             AND q.local_ts <= t.local_ts 
         WHERE t.symbol = 'f.ep.h26'
         ORDER BY t.local_ts
    """
    joined = client.query(query)
    # print('\nTop 100 joined')
    # for row in joined.result_rows:
    #     print(row)
    #print('\n')


def main():
   try:
      print("\nConnecting to database -> ", flush=True, end='')
      client = connect(host='clickhouse-md-svr', db='marketdata', usr='default', pwd='password')
      print(f"-> success" if client else "-> failure", flush=True)

      print("\nCreating tables -> ", flush=True, end='')
      init_schema(client, './sql')
      print("-> success", flush=True)

      print("\nInserting data -> ", flush=True, end='')
      init_data(client=client, batch_size=1000)
      print("-> success", flush=True)

      print("\nChecking data -> ", flush=True, end='')
      success = check_data(client)
      print("-> success" if success else "-> failure: unexpected rows count", flush=True)

      print("\nJoining -> ", flush=True, end='')
      join_simple(client=client)
      print("-> success", flush=True)

   except Exception as e:
      print(f'Exception occurred in main(): {e}', flush=True)


if __name__ == '__main__':
   sys.exit(main())