#!/usr/bin/env python
"""Test of convergence meter nsrt-mk3-dev interfaced
to a linux machine. Below find test code to read meter,
show meter index for machine, and test the nsrt-mk3-dev
to see if it is consistent with documentation.
"""
import time
from pprint import pprint

# %%
import pandas as pd
from pandas.tseries.offsets import Second
from collections import OrderedDict
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', 500)
pd.set_option('display.width', 1000)
pd.options.display.float_format = '{:,.2f}'.format
# %%
# try to access on serial
# need to run sudo chmod 666 /dev/ttyACM0
# alternatively, apply method in notes_convergence.txt, modify /etc/udev/rules.d/50-usb-perms.rules
# other alternatives, add username running script to dialout sudo usermod -a -G dialout $USER
import serial
sTest = serial.Serial('/dev/ttyACM0')
print(sTest.name)
print("Serial connection is open: {0}".format(sTest.is_open))

# %%

from nsrt_mk3_dev import NsrtMk3Dev
# found via lsusb, see notes
device_name = '/dev/ttyACM0'
nsrt = NsrtMk3Dev(device_name)
model = nsrt.read_model()
serial_number  = nsrt.read_sn()
print("Serial Number {0}".format(serial_number))
#%%
serial_number  = nsrt.read_sn()
firmware_revision = nsrt.read_fw_rev()
date_of_birth = nsrt.read_dob()
date_of_calibration = nsrt.read_doc()
print(f'Sound level meter model: {model}\n'
      f'serial number: {serial_number}, firmware revision number: {firmware_revision}\n'
      f'manufactured on: {date_of_birth}, calibrated on: {date_of_calibration}')

leq_level = nsrt.read_leq()
weighting = nsrt.read_weighting()
weighted_level = nsrt.read_level()
print(f'current leq level: {leq_level:0.2f} dB, {weighting} value: {weighted_level:0.2f}')
# %%
print("Adjusting tau...")
print("tau is {0:.1f}".format(nsrt.read_tau()))
new_tau = 1.0
success = nsrt.write_tau(new_tau)
print("adjusting tau to {0:.1f}--success {1}".format(new_tau, success))
print("new tau is {0:.1f}".format(nsrt.read_tau()))
# %%
print("Adjusting weighting...")
print("weighting is {0}".format(nsrt.read_weighting().name))
new_wt = NsrtMk3Dev.Weighting.DB_A
success = nsrt.write_weighting(new_wt)
print("adjusting weighting to {0}--success {1}".format(new_wt.name, success))
print("new weighting is {0}".format(nsrt.read_weighting().name))
# %%
print("Adjusting frequency, can be either 48000 or 32000...")
print("frequency is {0}".format(nsrt.read_fs()))
new_f = 48000
success = nsrt.write_fs(new_f)
print("adjusting frequency to {0:d}--success {1}".format(new_f, success))
print("new freq is {0:d}".format(nsrt.read_fs()))
# %%
print("temperature in celsius is {0}".format(nsrt.read_temperature()))
# %%
# do a succession or reads...
time_start = pd.Timestamp.now().round('1s') + Second(5)
time_end = time_start + Second(20)
print("start at {0}, end at {1}".format(time_start, time_end))
while (time_now:= pd.Timestamp.now()) < time_end:
      lavg, leq, current_tau = nsrt.read_level(), nsrt.read_leq(), nsrt.read_tau()
      print("At: {0}, lavg: {1:.1f}. leq: {2:.1f}, current_tau: {3:.1f}".format(time_now, lavg, leq, current_tau))
      time.sleep(1)
#%%
# propertiese of com port
print("name of serial is {0}".format(nsrt.serial.name))
print("baud rate of connection is {0:d}.".format(nsrt.serial.baudrate))
print("byte size of connection is {0:d}.".format(nsrt.serial.bytesize))
print("Serial connection is closed: {0}".format(nsrt.serial.closed))
print("Serial connection is open: {0}".format(nsrt.serial.is_open))
#%%
# section closes nsrt port
# print("closing serial port...")
# nsrt.serial.close()
# print("Serial connection is open: {0}".format(nsrt.serial.is_open))
# nsrt = None
#%%
# use USBDeview from Nirsoft in windows to get port enumeration
# below is how to get port information
# the vendorid and product id that shows up in windows can be found
# by parsing the 'hwid' element
import os
if os.name == 'nt':  # sys.platform == 'win32':
    from serial.tools.list_ports_windows import comports
elif os.name == 'posix':
    from serial.tools.list_ports_posix import comports
#~ elif os.name == 'java':
else:
    raise ImportError("Sorry: no implementation for your platform ('{}') available".format(os.name))

infos = comports()
for info in infos:
      pprint(info.__dict__)
      hwid = dict(zip(['vendorId', 'productId'], info.usb_info().split()[1].split('=')[1].split(':')))
      print(hwid)


# %%
# this an example, meant to show the command to read lq
# input per docs is hex 80000011 of 0x80000011 as python reads it, which interprets to 2147483665
# struct converts between python values and C structs represented as Python bytes objects
# the command struct.pack yields bytes, appropriate to 'Longs' in this case
# for format '<LLL' , the '<' represents 'little-endian' format
# LLL indicates 3 items, hence 3 items following format
# so a 'Long' has standard size 4 bytes https://docs.python.org/3/library/struct.html
# so struct.pack in this case yields 4x3=12 bytes
import struct
command, address, count = 0x80000011, 0, 4  # read_leq
# command, address, count = 0x00000020, 0, 4 # write
bytes_convert = struct.pack('<LLL', command, address, count)
# equivalent to...
# list(struct.pack('<L', command) + struct.pack('<L', address) + struct.pack('<L', count)) == list(bytes_convert)
print("Here are the bytes")
print(bytes_convert)
print("where everything after 'x' is hexadecimal, so 'x11' = 16 +1 = 17")
print('length: {0:d} bytes'.format(len(bytes_convert)))
t = list(bytes_convert)
print('list function turns those 12 bytes into integers')
print(t)
print('so full command is 12 bytes as indicated in the api documentation')
# https://wiki.python.org/moin/BitwiseOperators
print('bitwise and functions as mask to figure out read length...')
print("is this a command to receive float data? {0}".format((command & 0x80000000) == 0x80000000))
# this is just a way to say command is a 'number of class 0x80000000'

# %%
sound_meter_reading: OrderedDict = OrderedDict([('timestamp', pd.Timestamp.now()),
                               ('lavg', nsrt.read_level()),
                               ('leq', nsrt.read_leq()),
                               ('temp_f', nsrt.read_temperature() * 9. / 5. + 32.),
                               ('tau', "{0:.2f}".format(nsrt.read_tau())),
                               ('wt', nsrt.read_weighting().name),
                               ('freq', "{0:d}".format(nsrt.read_fs())),
                               ('serial_number',nsrt.read_sn()),
                               ('firmware_revision',nsrt.read_fw_rev()),
                               ('date_of_birth',nsrt.read_dob()),
                               ('date_of_calibration',nsrt.read_doc())])

# %%
# %%
# %%
# %%
# %%
# %%
# %%
