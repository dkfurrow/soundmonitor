#!/usr/bin/python -u
# coding=utf-8
# Manage Sound Meter
import sys

import usb.core
import usb.util
import random
import time
import signal
from LogManager import MessageHandler
import numpy as np
import pandas as pd
from collections import deque
import pandas as pd
from pandas.tseries.offsets import Minute
import os
import re
import itertools
from datetime import datetime
from pprint import pprint
VENDOR_ID = 0x64bd
PRODUCT_ID = 0x74e3
timestamp_format = '%m/%d/%Y %H:%M:%S.%f'


class SoundMeterReading:
    range_dict = {0: '30-130', 1: '30-80', 2: '50-100', 3: '60-110', 4: '80-130'}
    ts: pd.Timestamp = None
    int_buffer: list = None
    binaries: list = None
    decibal_reading: float = None
    is_slow: bool = None  # as opposed to fast
    is_max: bool = None  # as opposed to NotMax
    is_a: bool = None  # as opposed to c
    range: str = None  # element of fixed range setting

    def __init__(self, ts: datetime, int_buffer: list):
        self.ts = ts
        if len(int_buffer) != 8:
            raise ValueError("buffer must be of length 8")
        self.int_buffer = int_buffer
        self.parse_intbuffer()

    def parse_intbuffer(self):
        read_binaries = []
        try:
            for ele in self.int_buffer:
                binary = '{0:08b}'.format(ele)
                read_binaries.append(binary)
        except:
            raise ValueError("Could not interpret integer buffer elements from device")
        self.binaries = read_binaries
        self.decibal_reading = float((self.int_buffer[0] * 256. + self.int_buffer[1]) / 10.)
        settings_str = self.binaries[2][0:4]
        self.is_slow = True if settings_str[1] == '0' else False
        self.is_max = True if settings_str[2] == '1' else False
        self.is_a = True if settings_str[3] == '0' else False
        range_str = self.binaries[2][4:8]
        range_int = int(range_str, 2)
        if self.range_dict.get(range_int):
            self.range = self.range_dict[range_int]
        else:
            raise ValueError("Invalid Range in buffer output")
        if None in [self.decibal_reading, self.is_slow, self.is_max, self.is_a, self.range]:
            raise ValueError("Invalid reading parse, at least one element failed to parse")

    def to_dict(self):
        return {'timestamp': self.ts, 'decibel': self.decibal_reading, 'slow': self.is_slow,
                'lockmax': self.is_max, 'a': self.is_a, 'range': self.range}

    def get_timestamp(self):
        return self.ts

    def __str__(self):
        # Fast is current time reading, Slow within 1 second
        # max locks up the meximum reading , NotMax does not
        # A=> normal frequcny C=>low frequency,
        # SoundLevel is range measured
        # default: Fast, NotMax, A, 30-130
        return 'timestamp: {0}, decibel: {1:.1f}, TimeWeight: {2}, MaxValue: {3}, FrequencyWeight: {4},' \
               ' soundLevel: {5}'.format(self.ts.strftime(timestamp_format), self.decibal_reading,
                                         "Slow" if self.is_slow else "Fast","Max" if self.is_max else "NotMax",
                                         "A" if self.is_a else "C" ,self.range)


class MeterManager:
    dev: usb.core.Device = None
    eout: usb.core.Endpoint = None
    ein: usb.core.Endpoint = None
    state_request: bytearray = None
    sound_readings: deque = None
    interface = 0


    def __init__(self, message_handler: MessageHandler):
        self.sound_readings = deque([], 1000)
        self.connect_and_clear()


    def is_driver_active(self):
        is_active: bool = self.dev.is_kernel_driver_active(0)
        print("Kernal driver active: {0}".format(is_active))


    def connect_and_clear(self):
        self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.dev == None:
            print("no Sound Meter found!")
            sys.exit()
        if self.dev.is_kernel_driver_active(0):
            self.dev.detach_kernel_driver(0)
            usb.util.claim_interface(self.dev, 0)
        self.is_driver_active()
        self.eout = self.dev[0][(0, 0)][0]
        self.ein = self.dev[0][(0, 0)][1]
        self.state_request = bytearray([0xb3, random.randint(0, 255), random.randint(0, 255),
                                        random.randint(0, 255), 0, 0, 0, 0])
        _ = self.dev.read(self.ein.bEndpointAddress, self.ein.wMaxPacketSize)  # clear buffer,
        print("usb device connected and cleared")

    def generate_spl(self):
        spl_generate_time: pd.Timestamp = pd.Timestamp.now()
        timeout: time = time.time() + 5
        print("Requesting meter read at {0}".format(spl_generate_time.strftime(timestamp_format)))
        self.dev.write(self.eout.bEndpointAddress, self.state_request)
        buffer = []
        need_restart: bool = False
        while True:
            buffer += self.dev.read(self.ein.bEndpointAddress, self.ein.wMaxPacketSize)
            if len(buffer) >= 8:
                break
            if time.time() > timeout:
                print("error! buffer taking too long")
                need_restart = True
                break
        if not need_restart:
            sound_meter_reading: SoundMeterReading = SoundMeterReading(ts=spl_generate_time,
                                                                   int_buffer=buffer)
            print(sound_meter_reading)
            self.sound_readings.append(sound_meter_reading)   # right side of queue
        else:
            print("Resetting USB device")
            self.dev.reset()
            self.connect_and_clear()

    def summarize_readings(self):
        end_reading: pd.Timestamp = pd.Timestamp.now().floor('min')
        start_reading = end_reading - Minute(1)
        df: pd.DataFrame = pd.DataFrame.from_records([x.to_dict() for x in list(self.sound_readings)])
        df = df[df['timestamp'].between(start_reading, end_reading)]
        df.to_parquet('testdata.parquet', index=False)
        segment_stats_dict = df.describe(percentiles=[0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])\
        .to_dict()['decibel']
        summary_dict = {}
        summary_dict['timestamp'] = df.timestamp.max().ceil('min')
        for k, v in segment_stats_dict.items():
            summary_dict["db_{0}".format(k)] = v
        pprint(summary_dict)


    def close(self):
        usb.util.release_interface(self.dev, self.interface)
        # reattach the device to the OS kernel
        self.dev.attach_kernel_driver(self.interface)






if __name__ == "__main__":
    start_time = pd.Timestamp.now()
    end_time = start_time + Minute(2)
    print("start {0} end {1}".format(start_time.strftime(timestamp_format),
                                     end_time.strftime(timestamp_format)))
    meter_manager = MeterManager(message_handler=None)
    updated_time = pd.Timestamp.now()
    while updated_time < end_time:
        meter_manager.generate_spl()
        time.sleep(2.0)
        updated_time = pd.Timestamp.now()
    print("End time exceeded")
    meter_manager.summarize_readings()
    meter_manager.close()
    print("program ended")
