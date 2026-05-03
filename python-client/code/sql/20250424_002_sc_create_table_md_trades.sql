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
