#!/usr/bin/env python
"""
create necessary mysql tables for sound meter data storage
"""
import argparse
import os
import sys
import traceback

from sqlalchemy import Column, ForeignKey, Integer, BigInteger, String, Float, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from dbinfo import DBInfo
from sqlalchemy.dialects.mysql import DATETIME
Base = declarative_base()

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
MODULE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
TABLE_PREFIX = 'nsrt'
TABLE_SUFFIXES = {'data': 'data', 'meta': 'meta', 'params': 'params'}
# https://www.pythoncentral.io/introductory-tutorial-python-sqlalchemy/
# http://docs.sqlalchemy.org/en/latest/orm/basic_relationships.html


class nsrt_data(Base):
    __tablename__ = '{0}_{1}'.format(TABLE_PREFIX, TABLE_SUFFIXES['data'])
    id = Column(BigInteger(), primary_key=True, autoincrement=True)  # auto, starts at zero
    timestamp = Column(DATETIME(fsp=6), nullable=False)
    lavg = Column(Float(), nullable=False)
    leq = Column(Float(), nullable=False)
    temp_f = Column(Float(), nullable=False)
    params_id = Column(Integer(), ForeignKey('nsrt_params.id'))
    nsrt_id = Column(Integer(), ForeignKey('nsrt_meta.id'))
    nsrt_meta = relationship("nsrt_meta")
    spl_params = relationship("spl_params")


class nsrt_params(Base):
    __tablename__ = '{0}_{1}'.format(TABLE_PREFIX, TABLE_SUFFIXES['params'])
    id = Column(Integer(), primary_key=True, autoincrement=False)
    tau = Column(String(5), nullable=False)
    wt = Column(String(4), nullable=False)
    freq = Column(String(5), nullable=False)
    serial_number = Column(String(25), nullable=False)
    firmware_revision = Column(String(10), nullable=False)
    date_of_birth = Column(String(20), nullable=False)
    date_of_calibration = Column(String(20), nullable=False)


class nsrt_meta(Base):
    __tablename__ = '{0}_{1}'.format(TABLE_PREFIX, TABLE_SUFFIXES['meta'])
    id = Column(Integer(), primary_key=True, autoincrement=False)
    station_name = Column(String(50), nullable=False)
    station_location = Column(String(50), nullable=False)
    station_height_m = Column(Integer(), nullable=False)
    modified_by = Column(String(50), nullable=False)
    modified_time = Column(DATETIME(), nullable=False)


def create_empty_database(run_args: argparse.Namespace):
    """
    creates empty data tables in the database specified by user
    :param run_args: run arguments from command line or converted'
    from dictionary by other code
    :return: None
    """
    db_info: DBInfo = DBInfo.dbinfo_from_configfile(run_args.config_file, run_args.db_target_alias)
    engine = db_info.get_engine()
    insp = inspect(engine)
    table_names = Base.metadata.tables.keys()
    create_table: bool = True
    for table_name in table_names:
        table_exists = insp.has_table(table_name)
        print("Does table {0} exist? {1}".format(table_name, table_exists))
        if table_exists:
            create_table = False
            break
    if create_table:
        print("creating tables...")
        Base.metadata.create_all(bind=engine, tables=None, checkfirst=True)
        print("tables created, closing database connection...")
        db_info.close()
    else:
        print("at least one table exists, please drop all tables and run again...")


def main():
    try:
        my_parser = argparse.ArgumentParser(prog='datatablecreate',
                                            description='Create data tables for storage of sound meter readings')
        my_parser.add_argument('--config_file', type=str, help='database config file')
        my_parser.add_argument('--db_target_alias', type=str, help='target alias to find in config file')
        args: argparse.Namespace = my_parser.parse_args()
        create_empty_database(args)

    except Exception as ex:
        print("Exception in user code:")
        print('-' * 60)
        print(str(ex))
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)


if __name__ == '__main__':
    main()
