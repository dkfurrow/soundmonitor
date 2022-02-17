#!/usr/bin/python -u
# coding=utf-8
"""
Manage Convergence nsrt-mk3-dev Sound Level Meter, aggregates readings by minute
https://github.com/xanderhendriks/nsrt-mk3-dev

"""
import argparse
import importlib
import logging
import os
import sys
import time
import traceback
from collections import OrderedDict
from collections import deque
from pathlib import Path
from pprint import pprint

import pandas as pd
import yaml
from nsrt_mk3_dev import NsrtMk3Dev
from pandas.tseries.offsets import Minute, Second, Milli

from datamanager import DataManager
from logmanager import MessageHandler

MODULE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
os.chdir(MODULE_DIRECTORY)
TIMESTAMP_FORMAT = '%m/%d/%Y %H:%M:%S.%f'
TIMESTAMP_FORMAT_SQL = '%Y-%m-%d %H:%M:%S'
NSRT_WEIGHTINGS = dict([('DB_A', NsrtMk3Dev.Weighting.DB_A), ('DB_C', NsrtMk3Dev.Weighting.DB_C),
                        ('DB_Z', NsrtMk3Dev.Weighting.DB_Z)])
TIME_PADDING_SECONDS = 0.001  # time after mark to call meter for measurement (ensures meter queried 'after' mark
MIN_RUN_TIME_SECONDS = 5.0  # must run for this minimum time before recording


class MeterManager:
    """
    Main meter manager class
    """
    nsrt: NsrtMk3Dev = None  # nsrt meter representation from NsrtMk3Dev
    sound_readings: deque = None  # running fixed queue of sound readings
    _measurement_frequency: float = None  # how often to query meter (e.g. 1 sec, 0.5 sec)
    _meter_info: dict = None  # dictionary of meter configurations
    _data_manager: DataManager = None  # data manager for output
    _message_handler: MessageHandler = None  # hanlde logging
    _device_port: str = None  # device port as specified
    _weighting: NsrtMk3Dev.Weighting = None  # frequency weighting
    _tau: float = None  # time period for 'L' reading (e.g. 1 sec for 'slow' 0.125 sec for 'fast'
    _freq: int = None  # frequency setting
    _meter_id: int = None  # meter identification defined in config file for meta data

    def __init__(self):
        pass

    @classmethod
    def metermanager_from_configfile(cls, config_filename: str, message_handler: MessageHandler):
        meter_manager = MeterManager()
        meter_manager.load_meter_data(config_filename)
        meter_manager._message_handler = message_handler
        try:  # attempting to instantiate DataManager from string
            message_handler.log("Creating data manager: {0}".format(meter_manager.get_meter_info()['data-manager']))
            datamanager_module = importlib.import_module("datamanager")
            datamanager_class = getattr(datamanager_module, meter_manager.get_meter_info()['data-manager'])
            meter_manager._data_manager = datamanager_class(meter_manager.get_meter_info(), message_handler)
        except Exception as ex1:
            message_handler.log("Error--datamanager improperly specified\n{0}"
                                .format(traceback.format_exc()), lvl=logging.CRITICAL)
            raise ex1
        try:
            # 3 minutes of readings
            queue_length = int(1. / meter_manager.get_meter_info()['measurement-frequency'] * 60. * 3.)
            meter_manager.sound_readings = deque([], queue_length)
            meter_manager._measurement_frequency = meter_manager.get_meter_info()['measurement-frequency']
            meter_manager._device_port = meter_manager.get_meter_info()['device-port']
            meter_manager._weighting = NSRT_WEIGHTINGS[meter_manager.get_meter_info()['weighting']]
            meter_manager._tau = meter_manager.get_meter_info()['tau']
            meter_manager._freq = meter_manager.get_meter_info()['freq']
            meter_manager._meter_id = meter_manager.get_meter_info()['meter-id']
            meter_manager.nsrt = NsrtMk3Dev(meter_manager._device_port)
            meter_manager.connect_and_set()
        except Exception as ex1:
            message_handler.log("Error--meter manager improperly specified, check run parameters\n{0}"
                                .format(traceback.format_exc()), lvl=logging.CRITICAL)
            raise ex1
        return meter_manager

    def get_run_mins(self):
        return self._meter_info['run_mins']

    def get_meter_info(self):
        return self._meter_info

    def get_measurement_frequency(self):
        return self._measurement_frequency

    def connect_and_set(self):
        """
        connects to meter, sets various parameters
        :return:
        """
        self.nsrt = NsrtMk3Dev(port=self._device_port)
        if self.nsrt.serial is None:
            self._message_handler.log("no Sound Meter found!")
            sys.exit()
        success = self.nsrt.write_tau(self._tau)
        self._message_handler.log("adjusting meter tau to {0:.3f}--success {1}".format(self.nsrt.read_tau(), success))
        success = self.nsrt.write_weighting(self._weighting)
        self._message_handler.log("adjusting weighting to {0}--success {1}"
                                  .format(self.nsrt.read_weighting().name, success))
        success = self.nsrt.write_fs(self._freq)
        self._message_handler.log("adjusting frequency level of sound meter to {0:d}--success {1}"
                                  .format(self.nsrt.read_fs(), success))
        self._message_handler.log("usb device connected, measurement frequency (seconds): {0:.2f}"
                                  .format(self._measurement_frequency))

    def generate_spl(self):
        """
        query meter, load readings into dictionary, add to queue
        :return: None
        """
        sound_meter_reading = [('timestamp', pd.Timestamp.now()),
                               ('lavg', self.nsrt.read_level()),
                               ('leq', self.nsrt.read_leq()),
                               ('temp_f', self.nsrt.read_temperature() * 9. / 5. + 32.),
                               ('nsrt_id', self._meter_id),
                               ('tau', "{0:.2f}".format(self.nsrt.read_tau())),
                               ('wt', self.nsrt.read_weighting().name),
                               ('freq', "{0:d}".format(self.nsrt.read_fs())),
                               ('serial_number', self.nsrt.read_sn()),
                               ('firmware_revision', self.nsrt.read_fw_rev()),
                               ('date_of_birth', self.nsrt.read_dob()),
                               ('date_of_calibration', self.nsrt.read_doc())]
        # self.print_reading(sound_meter_reading)
        self.sound_readings.append(OrderedDict(sound_meter_reading))  # right side of queue

    def load_meter_data(self, this_config_filename):
        """
        load meter configuration specs from configfile
        :param this_config_filename: yaml file to query
        :return: None
        """
        if Path(MODULE_DIRECTORY).exists() and Path(MODULE_DIRECTORY, this_config_filename).exists():
            try:
                with open(Path(MODULE_DIRECTORY, this_config_filename), 'r') as f:
                    self._meter_info = yaml.safe_load(f)['soundmeter-info']
            except Exception as ex1:
                raise ValueError('Could not parse config, exception {0}'.format(str(ex1)))
        else:
            raise ValueError("Path to config file {0} does not exist"
                             .format(Path(MODULE_DIRECTORY, this_config_filename)))

    def write_readings_block(self):
        """
        write one minute of data per DataManager specification
        :return:
        """
        end_reading: pd.Timestamp = pd.Timestamp.now().floor('min')
        start_reading = end_reading - Minute(1)
        df: pd.DataFrame = pd.DataFrame.from_records(list(self.sound_readings))
        df = df[df['timestamp'].between(start_reading, end_reading)]
        df.set_index('timestamp', inplace=True)
        self._message_handler.log("writing minute ending {0} to database..."
                                  .format(df.index.to_list()[-1].ceil(freq='T')))
        self._data_manager.save_reading(data=df)

    # noinspection PyTypeChecker
    def close(self):
        """
        close serial port
        :return: None
        """
        print("closing serial port...")
        self.nsrt.serial.close()
        print("Serial connection is closed: {0}".format(not self.nsrt.serial.is_open))
        self.nsrt = None


def run_meter(config_filename: str):
    """
    run meter in accordance with config gile
    :param config_filename: config file
    :return: None
    """
    run_message_handler = MessageHandler(config_filename=config_filename, is_debug=False)
    run_message_handler.log("start time meter manager now {0}".format(pd.Timestamp.now().strftime(TIMESTAMP_FORMAT)))
    meter_manager: MeterManager = MeterManager.metermanager_from_configfile(config_filename, run_message_handler)
    measurement_freq_ms = int(meter_manager.get_measurement_frequency() * 1000.)
    # establish time to start querying meter, time to end if any
    if (pd.Timestamp.now().ceil('min') - pd.Timestamp.now()).total_seconds() > MIN_RUN_TIME_SECONDS:
        start_time = pd.Timestamp.now().ceil('min')
    else:  # add one minute
        start_time = pd.Timestamp.now().ceil('min') + Minute(1)
    mins_to_run = meter_manager.get_run_mins()
    end_time = start_time + Minute(mins_to_run) + Second(1) if mins_to_run else None
    if end_time:
        run_message_handler.log('stopping at {0}'.format(end_time))
    else:
        run_message_handler.log("running for indefinite period")
    if mins_to_run is not None:
        run_message_handler.log("start data saving: {0}, end {1}"
                                .format(start_time.strftime(TIMESTAMP_FORMAT), end_time.strftime(TIMESTAMP_FORMAT)))
    else:
        run_message_handler.log("start data saving: {0}".format(start_time.strftime(TIMESTAMP_FORMAT)))
    next_summary_time = start_time + Minute(1)
    sleep_until = ((pd.Timestamp.now().ceil('s') + Second(1)) - pd.Timestamp.now()).total_seconds() + \
                  TIME_PADDING_SECONDS
    run_message_handler.log("start pinging soundmeter: {0}"
                            .format((pd.Timestamp.now() + Milli(int(sleep_until * 1000.)))
                                    .strftime("%Y-%m-%d %H:%M:%S.%f")))
    time.sleep(sleep_until)
    while True:   # now, run meter for specified period
        try:
            meter_manager.generate_spl()
            time.sleep((pd.Timestamp.now().floor('{0:d}ms'.format(measurement_freq_ms)) + Milli(measurement_freq_ms)
                        - pd.Timestamp.now()).total_seconds() + TIME_PADDING_SECONDS)
            updated_time = pd.Timestamp.now()
            if end_time is not None and updated_time > end_time:
                run_message_handler.log("Maximum time exceeded, closing...")
                meter_manager.close()
                break
            if updated_time > next_summary_time:  # time to write minute of reading data
                meter_manager.write_readings_block()
                next_summary_time += Minute(1)
        except Exception as ex1:
            run_message_handler.log("Error during running of meter manager\n{0}"
                                    .format(traceback.format_exc()), lvl=logging.CRITICAL)
            raise ex1
    run_message_handler.log("program ended")


def print_serial_info():
    """
    prints serial info to find meter as configured by host machine
    :return: None
    """
    print("checking serial ports...")
    if os.name == 'nt':  # sys.platform == 'win32':
        from serial.tools.list_ports_windows import comports
    elif os.name == 'posix':
        from serial.tools.list_ports_posix import comports
    # ~ elif os.name == 'java':
    else:
        raise ImportError("Sorry: no implementation for your platform ('{}') available".format(os.name))
    infos = comports()
    for info in infos:
        pprint(info.__dict__)
        hwid = dict(zip(['vendorId', 'productId'], info.usb_info().split()[1].split('=')[1].split(':')))
        print(hwid)
    print("exiting...")


if __name__ == "__main__":
    my_parser = argparse.ArgumentParser(prog='soundmonitor', description='Run NSRT sound meter, save results')
    my_parser.add_argument('--config_file', type=str, help='config file to run')
    my_parser.add_argument('--check_serial', action='store_true')  # no argument needed
    args = my_parser.parse_args()
    if args.check_serial:
        print_serial_info()
        sys.exit(0)
    try:
        # data_manager: DataManager = CSVDataManager(csv_location='./logs', csv_name='test.csv')
        if args.config_file:
            run_meter(args.config_file)
    except Exception as ex:
        print(ex)
        print(traceback.format_exc())
