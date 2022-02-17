#!/usr/bin/python -u
# coding=utf-8
"""
Generic Data Manager implementation with concrete subclasses
Here we include subclasses to handle saving data to csv or to mysql database
"""
import logging
import os
import pandas as pd
from pathlib import Path
from dbinfo import DBInfo
from logmanager import MessageHandler
from datatablecreate import TABLE_PREFIX, TABLE_SUFFIXES, create_empty_database
from argparse import Namespace


class DataManager:
    """
    Superclass, implements basic init from meter_info dict and MessageHandler
    """
    _meter_info: dict = None
    _message_handler: MessageHandler = None

    def __init__(self, meter_info: dict, message_handler: MessageHandler):
        self._meter_info = meter_info
        self._message_handler = message_handler

    def save_reading(self, data: pd.DataFrame):
        raise NotImplementedError  # implement in subclasses

    def __str__(self):
        return str(self._meter_info)


class DBDataManager(DataManager):
    """
    implements DataManager for MySql Databases
    """
    _db_configfile: str = None  # file for database configs
    _target_alias: str = None  # target alias to seek in database config file
    _db_name: str = None  # name of database
    _datatable_name: str = None  # name of table for time series data

    def __init__(self, meter_info: dict, message_handler: MessageHandler):
        super(DBDataManager, self).__init__(meter_info, message_handler)
        if not {'db-configfile', 'db-target-alias'}.issubset(set(list(self._meter_info.keys()))):
            raise ValueError("config information must have specified db-configfile, db-target-alias")
        self._db_configfile = self._meter_info['db-configfile']
        self._target_alias = self._meter_info['db-target-alias']
        db_info: DBInfo = DBInfo.dbinfo_from_configfile(config_filename=self._db_configfile,
                                                        target_alias=self._target_alias,
                                                        db=self._meter_info.get('db-name'),
                                                        table=None)
        self._db_name = self._meter_info.get('db-name') if self._meter_info.get('db-name') is not None else \
            db_info.get_connection_data()['db']
        self._datatable_name = '{0}_{1}'.format(TABLE_PREFIX, TABLE_SUFFIXES['data'])
        if db_info.get_connection_data().get('table-name') is not None:
            message_handler.log("Disregarding entered config data table name: {0} in favor of {1}"
                                .format(db_info.get_connection_data()['table-name'], self._datatable_name),
                                logging.WARNING)
        db_info.close()
        self.create_tables_if_not_exist()
        self.initialize_meta_info()

    def create_tables_if_not_exist(self):
        """
        if meta, params, and data tables do not exist, create them
        :return: None
        """
        db_info: DBInfo = DBInfo.dbinfo_from_configfile(config_filename=self._db_configfile,
                                                        target_alias=self._target_alias,
                                                        db=self._db_name,
                                                        table=None)
        required_tables = ['{0}_{1}'.format(TABLE_PREFIX, table_suffix) for table_suffix in TABLE_SUFFIXES]
        db_tables = db_info.get_table_list_from_engine()
        if not set(required_tables).issubset(set(db_tables)):
            self._message_handler.log("datamanager: soundmeter data tables don't exist, creating data tables...")
            meter_info_ns = Namespace()
            meter_info_ns.config_file = self._db_configfile
            meter_info_ns.db_target_alias = self._target_alias
            create_empty_database(meter_info_ns)
        else:
            self._message_handler.log("datamanager: soundmeter data tables present, continuing...")

    def initialize_meta_info(self):
        """
        insert metadata to meta table in accordance with config file
        :return: None
        """
        self._message_handler.log("initializing metadata...")
        if 'meta-entry' not in list(self._meter_info.keys()):
            raise ValueError('meta-entry must be specified for data manager.')
        try:
            meta_entry: dict = self._meter_info['meta-entry']
            meta_entry['id'] = self._meter_info['meter-id']
            metatable_name = '{0}_{1}'.format(TABLE_PREFIX, TABLE_SUFFIXES['meta'])
            for k, v in meta_entry.items():
                if 'time' in k:
                    meta_entry[k] = pd.Timestamp(v)
            db_info: DBInfo = DBInfo.dbinfo_from_configfile(config_filename=self._db_configfile,
                                                            target_alias=self._target_alias,
                                                            db=self._db_name,
                                                            table=metatable_name)
            sql_str = "SELECT id FROM {0} WHERE {1} = {2}".format(metatable_name, 'id', meta_entry['id'])
            has_meta: bool = len(db_info.read_sql_to_df(sql_str)) != 0
            if not has_meta:
                self._message_handler.log("inserting metadata to table: \n {0}".format(str(meta_entry)))
                db_info.insert_dict_to_table(table_name=metatable_name, insert_dict=meta_entry)
            else:
                self._message_handler.log("metadata id already in table.")
            db_info.close()
        except Exception as _:
            raise ValueError('meta-entry improperly specified!')

    def save_reading(self, data: pd.DataFrame):
        """
        saves readings to database
        :param data: one minute of sound meter data
        :return:None
        """
        db_info: DBInfo = DBInfo.dbinfo_from_configfile(config_filename=self._db_configfile,
                                                        target_alias=self._target_alias,
                                                        db=self._db_name,
                                                        table=self._datatable_name)
        params_index = self.get_params_index(data.iloc[0, 4:], db_info)
        data_out: pd.DataFrame = data.iloc[:, :4].copy()
        data_out.insert(loc=0, column='params_id', value=params_index)
        db_info.insert_df_to_table(table_name=self._datatable_name, df=data_out, if_exists='append')
        db_info.close()

    def get_params_index(self, params: pd.Series, db_info: DBInfo):
        """
        tests to see if reading parameters are already represented in table,
        if they are, return index, if not insert row and return index
        :param params: observed meter parameters from querying meter
        :param db_info: database connection holder
        :return: integer id corresponding to parameter set
        """
        paramstable_name = '{0}_{1}'.format(TABLE_PREFIX, TABLE_SUFFIXES['params'])
        sql_str = "SELECT id FROM {0} WHERE ".format(paramstable_name)
        for k, v in params.iteritems():
            sql_str += "{0} = '{1}' AND ".format(k, v)
        sql_str = sql_str[:-5] + ';'
        select_df: pd.DataFrame = db_info.read_sql_to_df(sql_str)
        all_rows: pd.DataFrame = db_info.read_sql_to_df('SELECT * FROM {0};'.format(paramstable_name))
        if len(all_rows) == 0 or len(select_df) == 0:
            param_id = 0 if len(all_rows) == 0 else all_rows['id'].max() + 1
            insert_ind = pd.Index(data=[param_id], name='id')
            insert_df: pd.DataFrame = pd.DataFrame(index=insert_ind, data=[params.values], columns=params.index)
            db_info.insert_df_to_table(table_name=paramstable_name, df=insert_df, if_exists='append')
            params_str = ", ".join(["{0}: {1}".format(k, v) for k, v in params.iteritems()])
            self._message_handler.log("new spl meter parameter set, index: {0:d} \n {1}".format(param_id, params_str))
        else:
            param_id = select_df.loc[0, 'id']
        return param_id


class CSVDataManager(DataManager):
    """
    Implements DataManager for CSV files
    """
    csv_location: str = None  # folder which holds csv file
    csv_filename: str = None  # filename for csv file
    csv_path: Path = None  # fully specified path for csv file, folder and filename

    def __init__(self, meter_info: dict, message_handler: MessageHandler):
        super(CSVDataManager, self).__init__(meter_info, message_handler)
        if not {'csv-location', 'csv-filename'}.issubset(set(list(self._meter_info.keys()))):
            raise ValueError("config information must have specified csv-location, csv-filename")
        self.csv_location = self._meter_info['csv-location']
        self.csv_filename = self._meter_info['csv-filename']
        if not Path(self.csv_location).exists():
            self._message_handler.log("creating directory {0}".format(self.csv_location))
            os.mkdir(self.csv_location)
        self.csv_path = Path(self.csv_location, self.csv_filename)
        self._message_handler.log("csv Path {0}".format(self.csv_path))
        self._message_handler.log("{0} exists? {1}".format(self.csv_path, self.csv_path.exists()))

    def save_reading(self, data: pd.DataFrame):
        """
        writes readings to csv file, with or without header as appropriate
        :param data:
        :return:
        """
        if self.csv_path.exists():
            data.to_csv(path_or_buf=self.csv_path, header=False, index=True, mode='a')
        else:
            data.to_csv(path_or_buf=self.csv_path, header=True, index=True, mode='w')
