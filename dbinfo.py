#!/usr/bin/env python
"""
"""
import sys
import traceback
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import insert
from sqlalchemy import MetaData
from sqlalchemy import text
import logging
from LogManager import MessageHandler
import pandas as pd
import socket
from pprint import pprint
import sys

CONNECTION_INFO = {
    'dale-ThinkPad-E560': {'hostname': 'localhost', 'port': '3306', 'db': 'weather', 'user': 'dale', 'passwd': 'dale'},
    'DalePi1': {'hostname': 'localhost', 'port': '3306', 'db': 'weather', 'user': 'dale', 'passwd': 'pi1shared'}}
CONNECTION_DATA = CONNECTION_INFO[socket.gethostname()]
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'

MESSAGE_HANDLER = MessageHandler()


class DBInfo:
    """
    Central class for Mysql DB Cursor and static data
    """
    _engine = None


    def __init__(self):
        connect_str = 'mysql+pymysql://{0}:{1}@{2}:{3}/{4}'. \
            format(CONNECTION_DATA['user'], CONNECTION_DATA['passwd'], CONNECTION_DATA['hostname'],
                   CONNECTION_DATA['port'], CONNECTION_DATA['db'])
        self._engine = create_engine(connect_str)
        MESSAGE_HANDLER.log(msg="database connected", lvl=logging.INFO)
        with self.get_engine().connect() as connection:
            results = connection.execute('SELECT COUNT(*) FROM weather.pm_data;')
            for result in results:
                print("rows in pm_data: {0}".format(str(result[0])))

    def insert_dict_to_table(self, table_name: str, insert_dict: dict, dup_key_update: list=None):
        db_engine = self._engine
        meta = MetaData()
        meta.reflect(bind=db_engine)
        if table_name not in meta.tables.keys():
            raise ValueError("table {0} does not exist".format(table_name))
        valid_cols = set([column.name for column in meta.tables[table_name].columns])
        insert_cols = set(insert_dict.keys())
        if not insert_cols.issubset(valid_cols):
            raise ValueError ("invalid columns: {0}"
                              .format(", ".join([str(x) for x in list(insert_cols - valid_cols)])))
        if dup_key_update:
            if not set(dup_key_update).issubset(insert_cols):
                raise ValueError("duplicate keys not subset of insert keys")
        insert_stmt = insert(meta.tables[table_name]).values(insert_dict)
        if dup_key_update:
            insert_stmt = insert_stmt.on_duplicate_key_update(**dup_key_update)
        with db_engine.connect() as con:
            result_proxy = con.execute(insert_stmt)
        if len(result_proxy.last_inserted_params())  == 0:
            MESSAGE_HANDLER.log(msg="database insert unsuccessful", lvl=logging.WARN)

    def insert_df_to_table(self, table_name: str, df: pd.DataFrame, if_exists: str):
        valid_calls = set(['fail', 'replace', 'append'])
        if if_exists not in valid_calls:
            raise ValueError("incorrect entry to 'if_exists'")
        db_engine = self._engine
        meta = MetaData()
        meta.reflect(bind=db_engine)
        if table_name not in meta.tables.keys():
            raise ValueError("table {0} does not exist".format(table_name))
        valid_cols = set([column.name for column in meta.tables[table_name].columns])
        insert_cols = set(df.columns)
        if not insert_cols.issubset(valid_cols):
            raise ValueError("invalid columns: {0}"
                             .format(", ".join([str(x) for x in list(insert_cols - valid_cols)])))
        df.to_sql(name=table_name, con=self._engine, if_exists=if_exists)




    def get_engine(self):
        return self._engine

    def close(self):
        self._engine.dispose()



def main():
    try:
        db_info = DBInfo()
        # station_dict = db_info.get_station_dictionary()
        # pprint(station_dict)
        # days = db_info.get_previous_regular_metar_ts(datetime.now(), 'KMCJ')
        # pprint(days)
        db_info.close()
    except Exception as ex:
        print("Exception in user code:")
        print('-' * 60)
        print(str(ex))
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)


if __name__ == '__main__':
    main()
