#!/usr/bin/env python
"""
Manages connection to mysql database, with useful methods to save data to tables
in database.
"""
import os
import socket
import sys
import traceback
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import MetaData
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import insert

SOCKET_NAME = socket.gethostname()
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
MODULE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class DBInfo:
    """
    Central class for Mysql DB Cursor and static data
    """
    _connection_data: dict = None
    _target_alias: str = None
    _engine = None

    def __init__(self):
        pass

    @classmethod
    def dbinfo_from_configfile(cls, config_filename: str, target_alias: str, db: str = None, table: str = None):
        """
        instantiate DBInfo from configuration file
        :param config_filename: filename with (potentially multiple) database tables
        :param target_alias: identifies particular set of database connection data in config file
        :param db: database name
        :param table: table name
        :return:
        """
        db_info = DBInfo()
        db_info._connection_data = db_info.load_connection_data(config_filename, target_alias)
        if db:
            db_info.get_connection_data()['db'] = db
        if table:
            db_info.get_connection_data()['table-name'] = table
        db_info.connect_to_db(db_info.get_connection_data())
        return db_info

    @classmethod
    def dbinfo_from_dict(cls, db_connect_data: dict):
        db_info = DBInfo()
        db_info._connection_data = db_connect_data
        db_info.connect_to_db(db_connect_data)
        return db_info

    def connect_to_db(self, db_connect_data: dict, db: str = None):
        """
        connect to database and test connection
        :param db_connect_data: dictionary of connection information
        :param db: name of database, if not already specified above
        :return: None
        """
        if not db_connect_data.get('hostname'):
            raise ValueError("Error on connection attempt: hostname not specified")
        if SOCKET_NAME == db_connect_data['hostname']:
            db_connect_data['hostname'] = 'localhost'
        if db:
            db_connect_data['db'] = db
        if db_connect_data.get('db') is None:
            raise ValueError("Database not specified for {0}".format(db_connect_data['hostname']))
        connect_str = 'mysql+pymysql://{0}:{1}@{2}:{3}/{4}'. \
            format(db_connect_data['user'], db_connect_data['passwd'], db_connect_data['hostname'],
                   db_connect_data['port'], db_connect_data['db'])
        self._engine = create_engine(connect_str)
        try:
            with self.get_engine().connect() as connection:
                results = self.get_table_list_from_engine()
                if results is None:
                    raise ValueError("invalid data connection: {0}".format(db_connect_data['hostname']))
                if len(results) == 0:
                    print("Warning: no tables in {0}: {1}".format(db_connect_data['hostname'], db_connect_data['db']))
        except Exception as ex:
            print("Exception on connection attempt to database {0}: {1}".format(self._connection_data['db'], ex))
            raise ex

    def get_table_list_from_engine(self):
        """
        queries list of all tables in database
        :return: list of table names
        """
        with self.get_engine().connect() as connection:
            results = connection.execute("SELECT TABLE_NAME FROM information_schema.TABLES"
                                         " WHERE TABLE_TYPE = 'BASE TABLE' "
                                         "AND TABLE_SCHEMA = '{0}';".format(self._connection_data['db']))
        return [result[0] for result in results]

    @staticmethod
    def load_connection_data(config_filename: str, target_alias: str):
        """
        loads configuration from yaml file
        :param config_filename: filename to parse
        :param target_alias: name which identifies set of connection data
        :return: None
        """
        if Path(MODULE_DIRECTORY).exists() and Path(MODULE_DIRECTORY, config_filename).exists():
            try:
                with open(Path(MODULE_DIRECTORY, config_filename), 'r') as f:
                    return yaml.safe_load(f)['connection-data'][target_alias]
            except Exception as ex:
                raise ValueError('Could not parse config, exception {0}'.format(str(ex)))
        else:
            raise ValueError("Path to config file {0} does not exist"
                             .format(Path(MODULE_DIRECTORY, config_filename)))

    def get_table_cols(self, table_name: str):
        """
        returns all column names in a table
        :param table_name: name of table
        :return: set of column names
        """
        db_engine = self._engine
        meta = MetaData()
        meta.reflect(bind=db_engine)
        if table_name not in meta.tables.keys():
            raise ValueError("table {0} does not exist".format(table_name))
        return set([column.name for column in meta.tables[table_name].columns])

    def insert_dict_to_table(self, table_name: str, insert_dict: dict, dup_key_update: list = None):
        """
        inserts dictionary of data as table row
        :param table_name: name of table
        :param insert_dict: data to insert
        :param dup_key_update: whether to 'upsert' data if row is duplicate
        :return: None
        """
        valid_cols = self.get_table_cols(table_name)
        insert_cols = set(insert_dict.keys())
        if not insert_cols.issubset(valid_cols):
            raise ValueError("invalid columns: {0}"
                             .format(", ".join([str(x) for x in list(insert_cols - valid_cols)])))
        if dup_key_update:
            if not set(dup_key_update).issubset(insert_cols):
                raise ValueError("duplicate keys not subset of insert keys")
        meta = MetaData()
        meta.reflect(bind=self.get_engine())
        insert_stmt = insert(meta.tables[table_name]).values(insert_dict)
        if dup_key_update:
            dup_key_update_dict = dict([(k, insert_dict[k]) for k in dup_key_update])
            insert_stmt = insert_stmt.on_duplicate_key_update(**dup_key_update_dict)
        with self.get_engine().connect() as con:
            result_proxy = con.execute(insert_stmt)
        if len(result_proxy.last_inserted_params()) == 0:
            print("database insert unsuccessful")

    def insert_df_to_table(self, table_name: str, df: pd.DataFrame, if_exists: str):
        """
        insert pandas dataframe to table
        :param table_name: name of table
        :param df: dataframe
        :param if_exists: action if table exists
        :return: None
        """
        valid_calls = {'fail', 'replace', 'append'}
        if if_exists not in valid_calls:
            raise ValueError("incorrect entry to 'if_exists'")
        valid_cols = self.get_table_cols(table_name)
        insert_cols = set(df.columns)
        if not insert_cols.issubset(valid_cols):
            raise ValueError("invalid columns: {0}"
                             .format(", ".join([str(x) for x in list(insert_cols - valid_cols)])))
        df.to_sql(name=table_name, con=self._engine, if_exists=if_exists)

    def read_sql_to_df(self, sqlstr: str):
        """
        read sqlstring to pandas dataframe
        :param sqlstr: query string
        :return: dataframe associated with query
        """
        with self._engine.connect() as connection:
            return pd.read_sql(sql=sqlstr, con=connection)

    def get_db_name(self):
        return self._connection_data['db']

    def get_connection_data(self):
        return self._connection_data

    def get_engine(self):
        return self._engine

    def close(self):
        self._engine.dispose()


def test_dbase_connect_from_file(configfilename: str, target_alias: str, db: str = None, table: str = None):
    db_info = DBInfo.dbinfo_from_configfile(configfilename, target_alias, db, table)
    print('Checking db connection to alias {0}...'.format(target_alias))
    with db_info.get_engine().connect() as con:
        results = con.execute("SELECT COUNT(TABLE_NAME) FROM information_schema.TABLES WHERE TABLE_TYPE = "
                              "'BASE TABLE' AND TABLE_SCHEMA = '{0}';".format(db_info.get_db_name()))
    print('successful connection to machine {0}, database {1} , {2:d} tables found'
          .format(target_alias, db_info.get_connection_data()['db'], list(results)[0][0]))
    return db_info


def test_dbase_connect_from_dict(connection_data: dict):
    db_info = DBInfo.dbinfo_from_dict(connection_data)
    print('Checking db connection to alias {0}...'.format(connection_data['hostname']))
    with db_info.get_engine().connect() as con:
        results = con.execute("SELECT COUNT(TABLE_NAME) FROM information_schema.TABLES WHERE TABLE_TYPE = "
                              "'BASE TABLE' AND TABLE_SCHEMA = '{0}';".format(db_info.get_db_name()))
    print('successful connection to machine {0}, database {1} , {2:d} tables found'
          .format(connection_data['hostname'], db_info.get_connection_data()['db'], list(results)[0][0]))
    return db_info


def main():
    try:
        connection_data = {'hostname': 'localhost', 'port': '3306', 'db': 'weather', 'user': 'dale', 'passwd': 'dale'}
        db_info = test_dbase_connect_from_dict(connection_data)
        db_info.get_table_list_from_engine()
        print(db_info.get_connection_data())
        db_info.close()
    except Exception as ex:
        print("Exception in user code:")
        print('-' * 60)
        print(str(ex))
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)


if __name__ == '__main__':
    main()
