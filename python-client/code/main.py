import clickhouse_connect
import time
from pathlib import Path
import random

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

def init_data(client, batch_size=1):
    client.query('TRUNCATE TABLE default.md_trades')
    client.query('TRUNCATE TABLE default.md_quotes')

    trades = []
    cur_ns = time.time_ns() - 1000000
    i = 0
    for n in range(10000 // batch_size):
        for m in range(batch_size):
            trades.append((random.randint(1,100), random.randint(0,2), random.randint(1,1000), cur_ns+i,  cur_ns+i, random.choice(['f.ep.z26', 'f.ep.h26']), 'src', n * m))
            i += 1
    client.insert('default.md_trades', trades, column_names=['qty', 'side', 'price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])


    quotes = []
    i = 0
    for n in range(1000000 // batch_size):
        for m in range(batch_size):
            quotes.append((random.randint(1,100), random.randint(1,100), random.randint(1,1000), random.randint(1,1000), random.randint(1,1000), cur_ns + i,  cur_ns + i, random.choice(['f.ep.z26', 'f.ep.h26']), 'src', n * m))
            i += 1
    client.insert('default.md_quotes', quotes, column_names=['bid_qty', 'ask_qty', 'bid_price', 'ask_price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])


def check_data(client):
    trades_row_count = client.query('SELECT COUNT(*) FROM default.md_trades')
    quotes_row_count = client.query('SELECT COUNT(*) FROM default.md_quotes')
    return trades_row_count.result_rows[0][0] == 10000 and quotes_row_count.result_rows[0][0] == 1000000


if __name__ == '__main__':
    try:
        client = connect(
            host='clickhouse-md-svr',
            db='marketdata',
            usr='default',
            pwd='password')
        if client is not None: print(f"Connected successfully.")

        init_schema(client, './sql')
        print("Tables created successfully.")

        init_data(client=client, batch_size=100)
        print("Data inserted successfully.")

        if (check_data(client)): print("Data checked successfully.")

    except Exception as e:
        print(f'Exception occurred in main(): {e}')
