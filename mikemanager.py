#!/usr/bin/python -u
# coding=utf-8
"""
Manage microphone with pyaudio
"""
import logging
import os
import sys
import threading
import time
import traceback
import wave
from collections import deque
from pathlib import Path
from subprocess import Popen, PIPE
import argparse
import glob
import yaml
import pandas as pd
from pandas.tseries.offsets import Minute
from pyaudio import PyAudio
from logmanager import MessageHandler

TIMESTAMP_FORMAT = '%m/%d/%Y %H:%M:%S.%f'
TIMESTAMP_FORMAT_SQL = '%Y-%m-%d %H:%M:%S'
WAV_FILE_TIMESTAMP = '%Y%m%d%H%M'
MODULE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
os.chdir(MODULE_DIRECTORY)
LOG_DIR = str(Path('./logs').absolute())
OUTPUT_QUEUE = deque([], 5)  # used to queue frames for saving to wav file
STOP_QUEUE = deque([], 1)  # used to issue stop command


class MikeManager:
    """
    Main class to manage microphone
    """
    _recorder_info: dict = None  # configuration information
    _msg_handler: MessageHandler = None  # logging interface
    py_audio: PyAudio = None  # PyAudio representation of microphone

    def __init__(self, recorder_info: dict, msg_handler: MessageHandler):
        self._recorder_info = recorder_info
        self._msg_handler = msg_handler
        self.initialize()

    def initialize(self):
        self.py_audio = PyAudio()

    def close(self):
        self.py_audio.terminate()

    def check_audio_connections(self):
        """
        print out all PyAudio connections
        :return:
        """
        self._msg_handler.log("printing audio devices out and exiting...")
        for device_ind in range(self.py_audio.get_device_count()):
            print("index: {0:d}, name:{1}"
                  .format(device_ind, self.py_audio.get_device_info_by_index(device_ind).get('name')))
        self.py_audio.terminate()

    def create_recording(self, end: pd.Timestamp):
        """
        create audio recording in accordiance with config file, append to queue
        :param end:
        :return:
        """
        now = pd.Timestamp.now()
        record_secs = (end - now).seconds
        record_frames_num = int((self._recorder_info['sample-rate'] / self._recorder_info['chunk']) * record_secs)
        self._msg_handler.log("recording until {0}, {1:d} seconds"
                              .format(end.strftime(TIMESTAMP_FORMAT_SQL), record_secs))
        stream = self.py_audio.open(format=self._recorder_info['format'], rate=self._recorder_info['sample-rate'],
                                    channels=self._recorder_info['channels'],
                                    input_device_index=self._recorder_info['device-index'],
                                    input=self._recorder_info['input'],
                                    frames_per_buffer=self._recorder_info['chunk'])
        self._msg_handler.log("recording {0:d} frames".format(record_frames_num))
        frames = []
        for ii in range(0, record_frames_num):
            data = stream.read(self._recorder_info['chunk'], exception_on_overflow=False)
            frames.append(data)
        if len(frames) != record_frames_num:
            self._msg_handler.log("Warning: {0:d) requested, {1:d} frames received"
                                  .format(len(frames), record_frames_num))
        if len(frames) == 0:
            self._msg_handler.log(msg="No Frames received, reinitializing...", lvl=logging.WARNING)
            self.close()
            self.initialize()
        self._msg_handler.log("finished recording {0:d} frames".format(len(frames)))
        # stop the stream, close it, and terminate the pyaudio instantiation
        stream.stop_stream()
        stream.close()
        self._msg_handler.log("stopped stream appending to queue..")
        OUTPUT_QUEUE.append((frames, end))


def check_queue_and_write(recorder_info: dict, msg_handler: MessageHandler):
    """
    check recording queue, write audio file to specified location
    :param recorder_info: configuration dictionary
    :param msg_handler: logger
    :return: None
    """
    msg_handler.log("Initializing writer thread...")
    delete_old = recorder_info['delete-old']
    if delete_old:
        msg_handler.log("deleting old files...")
    wav_output_filename_form = '{0}{1}.wav'
    while True:
        if OUTPUT_QUEUE:  # check output queue, write frames
            frames, end = OUTPUT_QUEUE.pop()
            filename = wav_output_filename_form\
                .format(end.strftime(WAV_FILE_TIMESTAMP), recorder_info['output-name'])
            save_folder_path = recorder_info['dest-dir']
            if not Path(recorder_info['dest-dir']).exists():
                save_folder_path = mount_destination(recorder_info, msg_handler)
            wav_output_filepath = str(Path(save_folder_path, filename).absolute())
            if len(frames) > 0:
                msg_handler.log("writer: saving {0} writing {1:d} frames"
                                .format(str(wav_output_filepath), len(frames)))
                with wave.open(wav_output_filepath, 'wb') as wavefile:
                    wavefile.setnchannels(recorder_info['channels'])
                    wavefile.setsampwidth(2)  # really audio.get_sample_size(FORM_1)
                    wavefile.setframerate(recorder_info['sample-rate'])
                    wavefile.writeframes(b''.join(frames))
                    # wavefile.close()
                msg_handler.log("writer: {0} save complete".format(str(filename)))
                if delete_old:  # if delete old specified, only keep last 10 sound files, delete rest
                    index_to_delete = 10
                    sound_files = list(reversed(sorted(glob.glob(str(
                        Path(save_folder_path, '*{0}.wav'.format(recorder_info['output-name'])))))))
                    if len(sound_files) > index_to_delete:
                        msg_handler.log("deleting: {0} and older, {1:d} files"
                                        .format(Path(sound_files[index_to_delete]).stem,
                                                len(sound_files[index_to_delete:])))
                        for sound_file in sound_files[index_to_delete:]:
                            os.remove(sound_file)
        else:
            if STOP_QUEUE:
                msg_handler.log("writer: stop queue detected by writer thread, breaking...")
                break
            time.sleep(1)


# noinspection PyTypeChecker
def check_audio_devices(recorder_info: dict, msg_handler: MessageHandler):
    mike_manager = MikeManager(recorder_info, msg_handler)
    mike_manager.check_audio_connections()
    mike_manager.close()


def run_mike(recorder_info: dict, msg_handler: MessageHandler):
    """
    manage microphone, recording sounds to queue
    :param recorder_info: config specifications
    :param msg_handler: logger
    :return: None
    """
    start_time = pd.Timestamp.now()
    msg_handler.log("start mike manager now {0}".format(start_time.strftime(TIMESTAMP_FORMAT)))
    start_time = pd.Timestamp.now().ceil('min') + Minute(1)
    run_mins = recorder_info['run-minutes']
    end_times = pd.date_range(start=start_time, periods=run_mins, freq='min').to_list()\
        if run_mins else [start_time]
    if run_mins:
        msg_handler.log("start recording: {0}, end {1}"
                        .format(start_time.strftime(TIMESTAMP_FORMAT), end_times[-1].strftime(TIMESTAMP_FORMAT)))
    else:
        msg_handler.log("running for indefinite period")
    if not run_mins:
        msg_handler.log("first end time: {0}".format(start_time.strftime(TIMESTAMP_FORMAT)))

    if run_mins:
        msg_handler.log(str(end_times))

    mike_manager = MikeManager(recorder_info, msg_handler)
    next_recording_time = end_times.pop(0)
    while True:
        if next_recording_time:
            mike_manager.create_recording(end=next_recording_time)
        else:
            msg_handler.log("Maximum reads exceeded, closing...")
            mike_manager.close()
            STOP_QUEUE.append("STOP")
            secs_to_sleep = 10
            msg_handler.log("Appended stop queue, Sleeping for {0:d} seconds".format(secs_to_sleep))
            time.sleep(secs_to_sleep)
            break
        if run_mins:
            if len(end_times) > 0:
                next_recording_time = end_times.pop(0)
                message_handler.log("popping next recording time {0}".format(str(next_recording_time)))
            else:
                message_handler.log("setting next recording time to None...")
                next_recording_time = None
        else:
            next_recording_time = next_recording_time + Minute(1)
    message_handler.log("recording program thread ended")  # if no break, shouldn't reach this


def load_config_data(this_config_filename):
    """
    load config data from filename
    :param this_config_filename: config file
    :return: config dictionary
    """
    if Path(MODULE_DIRECTORY).exists() and Path(MODULE_DIRECTORY, this_config_filename).exists():
        try:
            with open(Path(MODULE_DIRECTORY, this_config_filename), 'r') as f:
                return yaml.safe_load(f)['soundrecorder-info']
        except Exception as ex1:
            raise ValueError('Could not parse config, exception {0}'.format(str(ex1)))
    else:
        raise ValueError("Path to config file {0} does not exist"
                         .format(Path(MODULE_DIRECTORY, this_config_filename)))


def mount_destination(recorder_info: dict, msg_handler: MessageHandler):
    mount_cmd = ['sudo', 'mount', '-t', 'cifs', recorder_info['network-share'],
                 recorder_info['local-mount'], '-o',
                 'credentials={0},rw,iocharset=utf8,file_mode=0777,dir_mode=0777,nodfs'
                 .format(recorder_info['credentials-file'])]
    if not Path(recorder_info['dest-dir']).exists():
        msg_handler.log('mounting directory')
        # os.cmd(MOUNT_CMD)
        p1 = Popen(mount_cmd, stdout=PIPE)
        stdoutdata, stderrdata = p1.communicate()
        msg_handler.log(stdoutdata)
        msg_handler.log(stderrdata)
        time.sleep(5)
        if Path(recorder_info['dest-dir']).exists():
            return recorder_info['dest-dir']
        else:
            return LOG_DIR
    else:
        return recorder_info['dest-dir']


def run_sound_recorder(recorder_info: dict, run_message_handler: MessageHandler):
    """
    manage recording of sound to queue, reading of queue and writing soundfiles to
    disk as concurrent threads
    :param recorder_info: config dictionary
    :param run_message_handler: logger
    :return:
    """
    run_message_handler.log("Establishing destination directory...")
    dest_dir = mount_destination(recorder_info, run_message_handler)
    run_message_handler.log("Destination directory is {0}".format(dest_dir))
    run_message_handler.log("writing sound files to {0}".format(dest_dir))
    recorder_info['dest-dir'] = dest_dir
    # create threads and start
    write_thread: threading.Thread = threading.Thread(target=check_queue_and_write,
                                                      args=(recorder_info, run_message_handler,))
    record_thread: threading.Thread = threading.Thread(target=run_mike, args=(recorder_info, run_message_handler,))
    write_thread.daemon = True
    record_thread.daemon = True
    write_thread.start()
    record_thread.start()
    while True:
        if STOP_QUEUE and not OUTPUT_QUEUE:  # gracefully stop threads if stop point reached
            run_message_handler.log("Program stop signal received, stopping threads")
            join_timout = 30.
            write_thread.join(join_timout)
            record_thread.join(join_timout)
            if write_thread.is_alive():
                run_message_handler.log("Write Thread is ALIVE!")
            elif record_thread.is_alive():
                run_message_handler.log("Record Thread is ALIVE!")
            else:
                run_message_handler.log("All threads joined, closing logger and exiting")
            run_message_handler.close()
            sys.exit(0)
        else:
            time.sleep(1)


if __name__ == "__main__":
    try:
        desctxt: str = "Check PyAudio devices, Manage NSRT Microphone"
        my_parser = argparse.ArgumentParser(prog='soundrecorder', description=desctxt)
        my_parser.add_argument('action', help="enter either run or check")
        my_parser.add_argument('--config_file', type=str, help='config file to run')
        args = my_parser.parse_args()
        print(args)
        if args.config_file:
            config_data: dict = load_config_data(args.config_file)
        else:
            raise ValueError("No configuration file specified")
        message_handler = MessageHandler(config_filename=str(Path(MODULE_DIRECTORY, args.config_file)),
                                         is_debug=False)
        if args.action == 'check':
            message_handler.log("Checking audio devices only")
            check_audio_devices({}, message_handler)
        if args.action == 'run':
            message_handler.log("Running and recording audio...")
            run_sound_recorder(config_data, message_handler)

    except Exception as ex:
        # noinspection PyUnboundLocalVariable
        message_handler.log(msg="Critical Exception: {0}".format(str(ex)), lvl=logging.CRITICAL)
        message_handler.log(msg=traceback.format_exc(), lvl=logging.CRITICAL)
