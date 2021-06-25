
from subprocess import Popen

from LogManager import MessageHandler
import logging
import re
import subprocess
import serial, time
from datetime import datetime, timedelta
import pytz
import traceback
import sys
from dbinfo import DBInfo
from metermanager import MeterManager
import threading


TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
MESSAGE_HANDLER = MessageHandler()
def show_usb_devices():
    device_re = re.compile("Bus\s+(?P<bus>\d+)\s+Device\s+(?P<device>\d+).+ID\s(?P<id>\w+:\w+)\s(?P<tag>.+)$", re.I)
    df = subprocess.check_output("lsusb").decode('utf-8')
    print(type(df))
    devices = []
    for i in df.split('\n'):
        if i:
            info = device_re.match(i)
            if info:
                dinfo = info.groupdict()
                dinfo['device'] = '/dev/bus/usb/%s/%s' % (dinfo.pop('bus'), dinfo.pop('device'))
                devices.append(dinfo)
    for device in devices:
        print(device)

def next_interval_dt(dt:datetime=datetime.now(), delta_mins:int=10):
    """
    calculates next interval time in whole minutes (e.g. 10)
    :param dt: reference datetime
    :param delta_mins: whole minute interval to return
    :return: next datetime based on interval
    """
    delta = timedelta(minutes=delta_mins)
    return dt + (datetime.min - dt) % delta

class AirMonitor:
    _dbinfo: DBInfo = None
    _message_handler: MessageHandler = None
    _sensormanager: MeterManager = None
    _run_interval: int = None
    _seconds_to_run: int = None
    _next_run: datetime = None
    METER_NUM = 1
    STATION_ID = 0
    TIME_BETWEEN_MEASUREMENTS = 2 # time between measurements in seconds

    def __init__(self, run_interval: int, seconds_to_run: int, dbinfo: DBInfo, message_handler: MessageHandler):
        self._run_interval = run_interval
        self._seconds_to_run = seconds_to_run
        self._dbinfo = dbinfo
        self._message_handler = message_handler
        self.initialize_schedule()



    def initialize_schedule(self):
        self._message_handler.log("Initializing Air Monitor, every {0:d} minutes, run {1:d} seconds"
                            .format(self._run_interval, self._seconds_to_run))
        self._message_handler.log("Initializing Sensor Manager...")
        self._sensormanager = MeterManager(MESSAGE_HANDLER)
        self._sensormanager.open_serial_port()
        self._next_run = next_interval_dt(datetime.now(), self._run_interval) - timedelta(seconds=self._seconds_to_run)
        self._message_handler.log("First run is at: {0}".format(self._next_run.strftime(TIMESTAMP_FORMAT)))

    def run_sensor_schedule(self):
        while True:
            measurements = []
            seconds_until_run = (self._next_run - datetime.now()).seconds
            self._message_handler.log("sleeping {0:d} seconds...".format(seconds_until_run))
            time.sleep(seconds_until_run)
            for i in range(self._seconds_to_run // self.TIME_BETWEEN_MEASUREMENTS + 1) :
                self._sensormanager.cmd_query_data()
                values = self._sensormanager.cmd_query_data()
                measurement_time = datetime.now()
                self._message_handler.log(msg="Iteration: {0:d} at {1} PM 2.5: {2:.1f} μg/m^3  PM 10: {3:.1f} μg/m^3"
                      .format(i+1, measurement_time.strftime(TIMESTAMP_FORMAT) ,values[0], values[1]),lvl=logging.DEBUG)
                measurements.append(self.write_measurement_to_dict(measurement_time, values))
                time.sleep(self.TIME_BETWEEN_MEASUREMENTS)
            self._next_run = next_interval_dt(datetime.now(), self._run_interval) - \
                             timedelta(seconds=self._seconds_to_run)
            self._message_handler.log("Measurement concluded, next run: {0}"
                                .format(self._next_run.strftime(TIMESTAMP_FORMAT)))
            self._message_handler.log("Writing to database")
            for measurement in measurements:
                self._dbinfo.insert_dict_to_table('pm_data', measurement)
            self._message_handler.log("{0:d} measurements written to database for utc {1}"
                                .format(len(measurements),
                                        measurements[-1]['obs_group_ts_utc'].strftime(TIMESTAMP_FORMAT)))

    def write_measurement_to_dict(self, measurement_time, values):
        obs_group_ts_utc = (self._next_run + timedelta(seconds=self._seconds_to_run)).astimezone(pytz.utc)
        obs_ts_utc = (measurement_time).astimezone(pytz.utc)
        write_dict = dict([('station_id', self.STATION_ID), ('meter_id', self.METER_NUM),
                           ('obs_group_ts_utc', obs_group_ts_utc), ('obs_ts_utc', obs_ts_utc), ('pm10', values[1]),
                           ('pm25', values[0])])
        return write_dict


def run_monitor():
    # initial code is '/dev/ttyUSB0'
    # try '/dev/ttyUSB6'
    serial_id = '/dev/ttyUSB0'
    ser = serial.Serial(serial_id)
    # ser.port = serial_id
    # ser.baudrate = 9600
    print(ser.is_open)
    if not ser.is_open:
        MESSAGE_HANDLER.log(msg="Serial is not opening, attempting to open...", lvl=logging.INFO)
    else:
        MESSAGE_HANDLER.log(msg="Serial is open!", lvl=logging.INFO)

    data = []
    max_iters = 5
    init_iter = 1
    while init_iter <= max_iters:
        print("running {0:d} of {1:d}".format(init_iter, max_iters))
        data = []
        for index in range(0,10):
            datum = ser.read()
            data.append(datum)
        print([x.decode('utf-8', 'backslashreplace') for x in data]) # encodes to the terminal encoding
        pmtwofive = int.from_bytes(b''.join(data[2:4]), byteorder='little') / 10  # this is actually of type 'float'
        pmten = int.from_bytes(b''.join(data[4:6]), byteorder='little') / 10
        print("outputting message")
        MESSAGE_HANDLER.log(msg="PM2.5: {0} PM10: {1}".format(str(pmtwofive), str(pmten)), lvl=logging.INFO)
        print("sleeping 10 seconds")
        time.sleep(10)
        init_iter += 1

def runAirMonitor(message_handler: MessageHandler):
    message_handler.log("Starting Air Monitor...")
    db_info = DBInfo()
    run_interval = 10
    seconds_to_run = 30
    air_monitor = AirMonitor(run_interval, seconds_to_run, db_info, message_handler)
    MESSAGE_HANDLER.log("Running Air Monitor schedule")
    air_monitor.run_sensor_schedule()



def main():
    try:
        MESSAGE_HANDLER.log("Starting Air Monitor and Connection Checker Threads")
        air_monitor_thread = threading.Thread(target=runAirMonitor, args=(MESSAGE_HANDLER, ))
        MESSAGE_HANDLER.log("Starting Air Monitor...")
        air_monitor_thread.start()
        connection_checker_thread = threading.Thread(target=run_connection_checker, args=(MESSAGE_HANDLER,))
        MESSAGE_HANDLER.log("Starting Connection Checker...")
        connection_checker_thread.start()
        MESSAGE_HANDLER.log("All threads started...")





    except Exception as ex:
        print("Exception in user code:")
        print('-' * 60)
        print(str(ex))
        traceback.print_exc(file=sys.stdout)
        print('-' * 60)





if __name__ == '__main__':
    main()

"""
[4741700.922135] usb 1-3: USB disconnect, device number 6
[4741700.922705] ch341-uart ttyUSB0: ch341-uart converter now disconnected from ttyUSB0
[4741700.922795] ch341 1-3:1.0: device disconnected
[4741706.554456] usb 1-3: new full-speed USB device number 7 using xhci_hcd
[4741706.890495] usb 1-3: device descriptor read/64, error -71
[4741707.148484] usb 1-3: unable to read config index 0 descriptor/all
[4741707.148493] usb 1-3: can't read configurations, error -71
[4741707.690404] usb 1-3: new full-speed USB device number 8 using xhci_hcd
[4741707.840421] usb 1-3: New USB device found, idVendor=1a86, idProduct=7523, bcdDevice= 2.64
[4741707.840427] usb 1-3: New USB device strings: Mfr=0, Product=2, SerialNumber=0
[4741707.840430] usb 1-3: Product: USB Serial
[4741707.842362] ch341 1-3:1.0: ch341-uart converter detected
[4741707.844107] usb 1-3: ch341-uart converter now attached to ttyUSB0

"""

"""
/home/dale/Dropbox/DEV/Python/linux_server/airmonitor
wget -O /home/dale/Dropbox/DEV/Python/linux_server/airmonitor/aqi.py https://raw.githubusercontent.com/zefanja/aqi/master/python/aqi.py
"""
