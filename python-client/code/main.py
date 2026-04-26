import clickhouse_connect
import datetime

client = clickhouse_connect.get_client(
    host='clickhouse-md-svr',
    username='default',
    password='password',
    database='marketdata'
)

result = client.query('SELECT 123')
print(f"Connection successful: {result.result_rows}")


client.command('''
CREATE TABLE IF NOT EXISTS default.md_trades
(
    `qty` UInt64 CODEC(DoubleDelta, LZ4),
    `side` Enum8('undef' = 0, 'buy' = 1, 'sell' = 2) CODEC(LZ4),
    `price` Float64 CODEC(Gorilla, LZ4),
    `local_ts` DateTime64(9, 'UTC') CODEC(LZ4),
    `exch_ts` DateTime64(9, 'UTC') CODEC(LZ4),
    `symbol` LowCardinality(String) CODEC(LZ4),
    `source` LowCardinality(String) CODEC(LZ4),
    `seqno` UInt64 CODEC(DoubleDelta, LZ4)
)
ENGINE = MergeTree
PARTITION BY toYearWeek(local_ts)
ORDER BY (symbol, local_ts)
SETTINGS index_granularity = 8192;
''')

client.command('''
CREATE TABLE IF NOT EXISTS default.md_quotes
(
    `bid_qty` UInt64 CODEC(DoubleDelta, LZ4),
    `ask_qty` UInt64 CODEC(DoubleDelta, LZ4),
    `bid_price` Float64 CODEC(Gorilla, LZ4),
    `ask_price` Float64 CODEC(Gorilla, LZ4),
    `local_ts` DateTime64(9, 'UTC') CODEC(LZ4),
    `exch_ts` DateTime64(9, 'UTC') CODEC(LZ4),
    `symbol` LowCardinality(String) CODEC(LZ4),
    `source` LowCardinality(String) CODEC(LZ4),
    `seqno` UInt64 CODEC(DoubleDelta, LZ4)
)
ENGINE = MergeTree
PARTITION BY toYearWeek(local_ts)
ORDER BY (symbol, local_ts)
SETTINGS index_granularity = 8192;
''')

print("Tables created successfully.")

trades = [
    [1, 1, 100.0, datetime.datetime(2026,1,1,10,10,10),  datetime.datetime(2026,1,1,15,10,10), 'f.ep.z26', 'src', 1],
    [1, 1, 100.0, datetime.datetime(2026,1,1,10,10,10),  datetime.datetime(2026,1,1,15,10,10), 'f.sp.z26', 'src', 2],
]
client.insert('default.md_trades', trades, column_names=['qty', 'side', 'price', 'local_ts', 'exch_ts', 'symbol', 'source', 'seqno'])
print("Data inserted successfully.")

result = client.query('SELECT * FROM default.md_trades')
print("SELECT results:")
for row in result.result_rows:
    print(row)
