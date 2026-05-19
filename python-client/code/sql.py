sc_create_table_md_quotes = """
   CREATE TABLE IF NOT EXISTS md_quotes
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
   --PARTITION BY toYearWeek(local_ts)
   PARTITION BY toYYYYMMDD(local_ts)
   ORDER BY (symbol, local_ts)
   SETTINGS 
      index_granularity = 1024;
"""

sc_create_table_md_trades = """
   CREATE TABLE IF NOT EXISTS md_trades
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
   --PARTITION BY toYearWeek(local_ts)
   PARTITION BY toYYYYMMDD(local_ts)
   ORDER BY (symbol, local_ts)
   SETTINGS 
      index_granularity = 1024;
"""

sc_materized_view = """
   CREATE MATERIALIZED VIEW IF NOT EXISTS mv_trade_quote_asof_join
   ENGINE = MergeTree
   ORDER BY (symbol, trade_local_ts)
   SETTINGS index_granularity = 1024
   POPULATE  -- Fill immediately
   AS
   SELECT 
         t.symbol,
         t.side as trade_side,
         t.qty as trade_qty,
         t.local_ts as trade_local_ts,
         q.local_ts as quote_local_ts,
         round(t.price, 5) as trade_price,
         round(q.bid_price, 5) as bid_price,
         round(q.ask_price, 5) as ask_price,
         round(t.price - q.bid_price, 5) as spread_to_bid,
         round(q.ask_price - t.price, 5) as spread_to_ask
--         dateDiff('microsecond', q.local_ts, t.local_ts) AS quote_to_request_latency_us
   FROM md_trades AS t
   ASOF LEFT JOIN md_quotes AS q
       ON t.symbol = q.symbol 
       AND t.local_ts >= q.local_ts
"""

q_simple_asof_join = """
     --EXPLAIN indexes = 1
     SELECT 
         t.symbol,
         t.side as trade_side,
         t.qty as trade_qty,
         t.local_ts as trade_local_ts,
         q.local_ts as quote_local_ts,
         round(t.price, 5) as trade_price,
         round(q.bid_price, 5) as bid_price,
         round(q.ask_price, 5) as ask_price,
         round(t.price - q.bid_price, 5) as spread_to_bid,
         round(q.ask_price - t.price, 5) as spread_to_ask
--         dateDiff('microsecond', q.local_ts, t.local_ts) AS quote_to_request_latency_us
     FROM md_trades AS t
     ASOF LEFT JOIN md_quotes AS q
         ON t.symbol = q.symbol 
         AND t.local_ts >= q.local_ts
--     WHERE t.local_ts between '2026-04-27 00:00:00' AND '2026-04-27 23:59:59.999'   
     PREWHERE t.local_ts between '2026-04-27 00:00:00' AND '2026-04-27 23:59:59.999'
"""


q_select_from_mv = """
   SELECT * 
   FROM trade_quote_asof_mv
   WHERE t.local_ts between '2026-04-27 00:00:00' AND '2026-04-27 23:59:59.999' 
"""
