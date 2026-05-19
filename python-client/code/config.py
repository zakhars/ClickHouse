from datetime import datetime, timezone, timedelta

DB = {
   'host': 'clickhouse-marketdata',
   'port': 8123,
   'username': 'mduser',
   'password': 'mdpassword',
   'database': 'marketdata'
}

NUM_QUOTES = 10000000
NUM_TRADES = 100000
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

NS_IN_SEC = 1000000000
BASE_TS_LOCAL  = int(datetime(2026, 4, 25, 8, 0, 0, 0, tzinfo=timezone(timedelta(hours=-3))).timestamp()) * NS_IN_SEC
BASE_TS_EXCH   = int(datetime(2026, 4, 25, 8, 0, 0, 0, tzinfo=timezone(timedelta(hours= 5))).timestamp()) * NS_IN_SEC
