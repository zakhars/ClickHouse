from datetime import datetime, timezone, timedelta

DB = {
   'host': 'clickhouse-marketdata',
   'port': 8123,
   'username': 'mduser',
   'password': 'mdpassword',
   'database': 'marketdata'
}

REGENERATE_DATA = True
NUM_QUOTES = 1_000_000
NUM_TRADES = 10_000
INSERT_CHUNK_SIZE = 100_000 # tried from 1 to 1M - optimal size is around 100k - as fast as 1M, but looks safer
VERBOSE_STATS = False

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

NS_IN_SEC = 1000_000_000
BASE_TS_LOCAL  = int(datetime(2026, 4, 25, 8, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3))).timestamp()) * NS_IN_SEC
BASE_TS_EXCH   = int(datetime(2026, 4, 25, 8, 0, 0, 0, tzinfo=timezone(timedelta(hours= 5))).timestamp()) * NS_IN_SEC

CHECK_QUERY_PLAN = 'EXPLAIN indexes = 1'

JOIN_SETTINGS = {
   'none'              : {},
   'auto'              : {'join_algorithm': 'auto'},
   'hash'              : {'join_algorithm': 'hash'},
   'parallel_hash'     : {'join_algorithm': 'parallel_hash'},
   'full_sorting_merge': {'join_algorithm': 'full_sorting_merge'}
}

DATES = "between '2026-04-27 00:00:00' AND '2026-04-27 23:59:59.999'"
SYMBOLS = "='F.ENQM27'"
SOURCES = "='CME'"

FILTER = {
   'none'                : '',
   'where_date_trade'    : f"WHERE t.local_ts {DATES}",
   'where_date_quote'    : f"WHERE q.local_ts {DATES}",
   'where_date_symbol'   : f"WHERE t.local_ts {DATES} and t.symbol {SYMBOLS}",
   'where_src'           : f"WHERE t.src {SOURCES}",
   'prewhere_date_trade' : f"PREWHERE t.local_ts {DATES}",
   'prewhere_date_quote' : f"PREWHERE q.local_ts {DATES}",
   'prewhere_date_symbol': f"PREWHERE t.local_ts {DATES} and t.symbol {SYMBOLS}",
   'prewhere_src'        : f"PREWHERE t.src {SOURCES}"
}

# Table definition order
#  CREATE TABLE
#  ...
#  ENGINE = MergeTree
#  PARTITION BY toYearWeek(local_ts)
#  ORDER BY (symbol, local_ts)
#  PRIMARY KEY (symbol, local_ts)
#  SETTINGS index_granularity = 8192;

ENGINE = {
   'merge_tree': 'ENGINE = MergeTree'
}

PARTITION_BY = {
   'none'      : '',
   'toYearWeek': 'PARTITION BY toYearWeek(local_ts)',
   'toYYYYMMDD': 'PARTITION BY toYYYYMMDD(local_ts)'
}

PRIMARY_KEY = {
   'none'       : '',
   'symbol_time': 'PRIMARY KEY (symbol, local_ts)'
}

ORDER_BY = {
   'none'       : '',
   'symbol_time': 'ORDER BY (symbol, local_ts)'
}

INDEX_GRANULARITY = {
   '1'   : 'SETTINGS index_granularity = 1',
   '128' : 'SETTINGS index_granularity = 128',
   '1024': 'SETTINGS index_granularity = 1024',
   '4096': 'SETTINGS index_granularity = 4096',
   '8192': 'SETTINGS index_granularity = 8192'
}
