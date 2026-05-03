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
