#!/usr/bin/env python
"""form tables for sound data
"""
# %%
import os

import pandas as pd
from pathlib import Path
from pprint import pprint
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', 500)
pd.set_option('display.width', 1000)
pd.options.display.float_format = '{:,.2f}'.format
#%%
from dbinfo import DBInfo
#%%
connection_data = {'hostname': 'localhost', 'port': '3306', 'db': 'weather', 'user': 'dale', 'passwd': 'dale'}
db_info = DBInfo.dbinfo_from_dict(connection_data)
db_info.get_table_list_from_engine()
print(db_info.get_connection_data())
#%%
TIMESTAMP_FORMAT_SQL = "%Y-%m-%d %H:%M:%S.%f"
df = pd.read_sql(con=db_info.get_engine(), sql="SELECT * FROM nsrt_data nd WHERE nd.timestamp > '2022-02-14 20:44:59';")
#%%
df = pd.read_sql(con=db_info.get_engine(), sql="SELECT * FROM nsrt_params;")
#%%
df = pd.read_sql(con=db_info.get_engine(), sql="SELECT * FROM nsrt_meta;")
#%%
df.loc[4, 'timestamp'].strftime(TIMESTAMP_FORMAT_SQL)
#%%
from pandas.tseries.offsets import Milli
print((pd.Timestamp.now().floor('ms') + Milli(float(0.5) * 1000.)- pd.Timestamp.now()).total_seconds())
#%%
sleep_time_next_measure = (pd.Timestamp.now().floor('ms') + Milli(int(0.5* 1000)) - pd.Timestamp.now()).total_seconds() + .001
print(sleep_time_next_measure)
#%%
print(pd.Timestamp.now())
print(pd.Timestamp.now().floor('250ms'))
#%%
df = pd.read_csv('./logs/nsrt.csv')
#%%
df.loc[df.index.max(), :].to_markdown()
#%%