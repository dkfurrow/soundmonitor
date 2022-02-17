#!/usr/bin/env python
"""
Generic class to handle all logging activity, define handlers
"""

import logging
import logging.handlers
import os
import smtplib
import sys
import time
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
import yaml
from pandas.tseries.offsets import Hour

from sqlalchemy import Column, Integer, String, DateTime, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.mysql import LONGTEXT

from dbinfo import DBInfo

IS_WINDOWS = os.name != 'posix'
TIMESTAMP_FORMAT_ALT = '%m/%d/%Y %H:%M:%S'
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
MODULE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class DBHandler(logging.Handler):
    """
    Handler for mysql database
    """
    log_config: dict = None  # dictionary for logging configuration
    db_info: DBInfo = None  # database connection information
    table_name: str = None  # logging table name

    def __init__(self, log_config: dict):
        super(DBHandler, self).__init__()
        self.log_config = log_config
        self.db_info = DBInfo.dbinfo_from_configfile(log_config['db-configfile'], log_config['db-target-alias'])
        if self.db_info.get_connection_data().get('table-name'):
            self.table_name = self.db_info.get_connection_data()['table-name']
        else:
            raise ValueError("configfile {0} must contain table name".format(log_config['db-configfile']))
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        """
        creates table for logging data if it does not already exist in database
        :return: None
        """
        engine = self.db_info.get_engine()
        insp = inspect(engine)
        if not insp.has_table(self.table_name):
            print("from logmanager--table {0} does not exist--creating table {0}".format(self.table_name))
            base = declarative_base()

            # noinspection PyUnusedLocal
            class LogInfo(base):
                __tablename__ = self.table_name
                id = Column(Integer, primary_key=True)  # auto, starts at zero
                timestamp = Column(DateTime(), nullable=False)
                logger_name = Column(String(15), nullable=False)
                level = Column(String(15), nullable=False)
                message = Column(LONGTEXT, nullable=True)

                def __str__(self):
                    return "{0} | {1} | {2} | {3}".format(self.timestamp.strftime(TIMESTAMP_FORMAT),
                                                          self.logger_name, self.level, self.message)

            base.metadata.create_all(bind=engine, tables=None, checkfirst=True)

    def close(self):
        self.db_info.close()

    def emit(self, record):
        """
        emit logging record
        :param record: logging element
        :return: None
        """
        log_dict = {'timestamp': time.strptime(record.asctime, TIMESTAMP_FORMAT_ALT),
                    'logger_name': record.name, 'level': record.levelname, 'message': record.msg}
        self.db_info.insert_dict_to_table(table_name=self.table_name, insert_dict=log_dict)


class MessageHandler:
    """
    Main logging manager
    """
    logger = None  # base logger
    logger_name: str = None  # name of logger, also determines filename for file-logging
    db_handler: DBHandler = None  # database hanlder if any
    log_config: dict = None  # dictionary of logging definitions
    is_debug: bool = False  # causes filehandler and consolehandler to set to lowest logging level

    def __init__(self, config_filename: str, is_debug: bool):
        self.is_debug = is_debug
        self.load_log_config(config_filename)
        self.logger_name = self.log_config['logger-name']
        self.logger = logging.getLogger(self.logger_name)
        self.db_handler = DBHandler(self.log_config['dbhandler-data']) \
            if self.log_config['dbhandler-data']['include'] else None
        if not len(self.logger.handlers):
            self.logger.setLevel(logging.DEBUG if self.is_debug else logging.INFO)
            # create formatter
            formatter = logging.Formatter(fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                                          datefmt=TIMESTAMP_FORMAT_ALT)
            # get console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.DEBUG if self.is_debug else logging.INFO)
            self.logger.addHandler(console_handler)
            # get file handler
            if self.log_config['filehandler-data']['include']:
                log_full_path = self.log_config['filehandler-data']['log-Location'] \
                                + os.path.sep + "{0}.log".format(self.logger_name)
                file_handler = logging.handlers.TimedRotatingFileHandler(filename=log_full_path, when='MIDNIGHT',
                                                                         interval=1, backupCount=30)
                file_handler.setFormatter(formatter)
                file_handler.setLevel(self.log_config['filehandler-data']['level']
                                      if not self.is_debug else logging.DEBUG)
                self.logger.addHandler(file_handler)

            if self.log_config['gmailhandler-data']['include']:
                email_handler = GenericEmailHandler(self.log_config)
                email_handler.setFormatter(formatter)
                email_handler.setLevel(self.log_config['gmailhandler-data']['level'])
                self.logger.addHandler(email_handler)

            if self.log_config['dbhandler-data']['include']:
                self.db_handler.setFormatter(formatter)
                self.db_handler.setLevel(self.log_config['dbhandler-data']['level'])
                self.logger.addHandler(self.db_handler)

    def load_log_config(self, config_filename: str):
        """
        load logging configuraiton from yaml file
        :param config_filename: filename
        :return: None
        """
        if Path(MODULE_DIRECTORY).exists() and Path(MODULE_DIRECTORY, config_filename).exists():
            try:
                with open(Path(MODULE_DIRECTORY, config_filename), 'r') as f:
                    self.log_config = yaml.safe_load(f)['logger-info']
            except Exception as ex:
                raise ValueError('Could not parse config, exception {0}'.format(str(ex)))
        else:
            raise ValueError("Path to config file {0} does not exist"
                             .format(Path(MODULE_DIRECTORY, config_filename)))

    def get_log_config(self):
        return self.log_config

    def log(self, msg, lvl=logging.INFO):
        self.logger.log(lvl, msg)

    def close(self):
        if self.db_handler:
            self.db_handler.close()

    # @staticmethod
    # def show_log():
    #     if IS_WINDOWS:
    #         file_path = os.path.join(LOG_LOCATION, logger_name)
    #         commands = ["C:\\Program Files (x86)\\Notepad++\\notepad++.exe", file_path]
    #         _ = Popen(commands)


class GenericEmailHandler(logging.StreamHandler):
    """
    email handler if used: specifically geared to gmail
    """
    log_config: dict = None
    email_log_path: str = None
    email_log_form = {'timestamp': pd.Timestamp.min, 'process_name': "process name",
                      'level': "message level", 'msg': 'message'}
    email_log: pd.DataFrame = None

    def __init__(self, log_config: dict):
        super(GenericEmailHandler, self).__init__()
        self.log_config = log_config
        self.email_log_path = str(Path(self.log_config['filehandler-data']['log-Location'], 'email_log.csv'))
        if not Path(self.email_log_path).exists():
            print("creating {0}".format(self.email_log_path))
            df: pd.DataFrame = pd.DataFrame.from_records([self.email_log_form])
            df.to_csv(path_or_buf=self.email_log_path, index=False)
        self.email_log = pd.read_csv(filepath_or_buffer=self.email_log_path, parse_dates=['timestamp'])

    def test_and_log_email(self, record):
        """
        logs email, based on record severity and threshold number of daily emails
        if over threshold, do not send
        :param record: logging record
        :return: whether send was successful
        """
        email_limit = self.log_config['gmailhandler-data']['email-limit-daily']
        record_time: pd.Timestamp = pd.Timestamp(record.asctime)
        time_limit = record_time - Hour(24)
        emails_sent = len(self.email_log[(self.email_log['timestamp'] > time_limit)
                                         & (self.email_log['process_name'] == record.name)])
        if emails_sent < email_limit:  # add to log, return true
            email_record_dict = self.email_log_form.copy()
            email_record_dict['timestamp'] = record_time
            email_record_dict['process_name'] = record.name
            email_record_dict['level'] = record.levelname
            email_record_dict['msg'] = record.msg
            email_record_df = pd.DataFrame.from_records([email_record_dict])
            email_record_df.to_csv(path_or_buf=self.email_log_path, mode='a', index=False, header=False)
            return True
        else:  # return false
            return False

    def send_to_gmail(self, record):
        """
        format and send emails
        :param record: logging record
        :return:
        """
        try:
            gmail_data: dict = self.log_config['gmailhandler-data']
            to_address = ", ".join(gmail_data['email-addresses'])
            message_type = "Email"
            msg_subject = "Process {0} - {1}".format(record.name, record.levelname)
            # Setup the MIME
            message = MIMEMultipart()
            message['From'] = gmail_data['from-address']
            message['To'] = to_address
            message['Subject'] = msg_subject
            message.attach(MIMEText(record.msg, 'plain'))
            server = smtplib.SMTP(gmail_data['mail-host'], gmail_data['mail-port'])  # or port 465 doesn't seem to work!
            server.ehlo()
            server.starttls()
            server.login(gmail_data['credentials']['username'], gmail_data['credentials']['password'])
            server.sendmail(gmail_data['from-address'], to_address, message.as_string())
            server.close()
            logging.getLogger(record.name).info("Successfully sent: " + message_type)
        except Exception as ex:
            logging.getLogger().warning("ERROR FROM EMAIL SEND FUNCTION: {0}".format(str(ex)))

    def emit(self, record):
        """
        Emit a record.
        Format the record and send it to the specified addressees.
        """
        try:
            if self.test_and_log_email(record):
                self.send_to_gmail(record)
            else:
                print("Daily email threshold exceeded! Not sending...")
        except Exception as ex:
            logging.getLogger().warning("ERROR FROM EMAIL HANDLER: {0}".format(str(ex)))


# noinspection PyBroadException
def main():
    try:
        log_config_loc = './ConfigSoundMonitor.yaml'
        message_handler = MessageHandler(config_filename=log_config_loc, is_debug=False)
        message_handler.log(lvl=logging.ERROR, msg="Logging test message {0}"
                            .format(datetime.now().strftime(TIMESTAMP_FORMAT)))
    except Exception as _:
        traceback.print_exc()
    finally:
        pass
        # message_handler.close()


if __name__ == '__main__':
    main()
