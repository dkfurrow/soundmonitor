#!/usr/bin/env python
"""Analyze gradebook data from processed file
"""
from datetime import datetime as dt
import pandas as pd
import numpy as np
import os
from pprint import pprint
import sqlalchemy as sa
from pathlib import Path
from pprint import pprint
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', 5000)
pd.set_option('display.width', 1000)
pd.options.display.float_format = '{:,.2f}'.format
import numpy as np

#%%
print(os.getcwd())
#%%
df = pd.read_parquet('./testdata.parquet')
#%%
run_description_dict = df.describe(percentiles=[0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]).to_dict()['decibel']
pprint(run_description_dict)
summary_dict = {}
summary_dict['timestamp'] = df.timestamp.max().ceil('min')
for k, v in run_description_dict.items():
    summary_dict["db_{0}".format(k)] = v
pprint(summary_dict)

#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
#%%
