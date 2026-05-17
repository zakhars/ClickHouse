import clickhouse_connect


class clickhouse_db_connection:
   def __init__(self, host, db, usr, pwd):
      self.hostname = host
      self.dbname = db
      self.user = usr
      self.password = pwd
      self.client = clickhouse_connect.get_client(host=host, username=usr, password=pwd, database=db)
      self.client.query('SELECT 1')

   def reset_database(self):
      tables = self.client.query(f"SHOW TABLES FROM {self.dbname}").result_rows
      for table in tables:
         table_name = table[0]
         self.client.command(f'DROP TABLE IF EXISTS {table_name}')

   def truncate_data(self):
      return self.client.query(f'TRUNCATE DATABASE {self.dbname}')

   def command(self, query):
      return self.client.command(query)

   def query(self, query):
      return self.client.query(query)
