__author__ = 'Dale Furrow'
import logging
import logging.handlers
import sys
import time
import smtplib
from subprocess import Popen
import os
import traceback

IS_WINDOWS = os.name != 'posix'
mail_host = ("smtp.gmail.com", 587) #mailhost, mailport tuple
from_address = 'dkfurrow@gmail.com'
text_address = '7134781585@tmomail.net'
email_addresses = ['dalefurrow@usa.net']
subject_line = 'Alarm Alert!'
credentials = ('dkfurrow@gmail.com', 'gdaxjuctokoapiva') # username, password
date_format = '%m/%d/%Y %H:%M:%S'
log_location = "D:\\DKF\\DEV\\Logs" if IS_WINDOWS else "/home/dale/pi1shared/logs"
log_filename = "airmonitor.log"


class MessageHandler:
    logger = None

    def __init__(self):
        self.logger = logging.getLogger()
        if not len(self.logger.handlers):
            self.logger.setLevel(logging.DEBUG)
            # get console handler
            console_handler = logging.StreamHandler(sys.stdout)
            # get file handler
            log_full_path = log_location + "/" + log_filename
            file_handler = logging.handlers.TimedRotatingFileHandler(filename=log_full_path, when='MIDNIGHT',
                                                                     interval=1, backupCount=30)
            # get email handler
            email_handler = GenericEmailHandler()
            # create formatter
            formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s',
                                          datefmt=date_format)
            # add formatter to handlers
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            # email_handler.setFormatter(formatter)
            # set levels on handlers
            console_handler.setLevel(logging.INFO)
            file_handler.setLevel(logging.INFO)
            # email_handler.setLevel(logging.WARNING)
            # sdd handlers to logger
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
            # self.logger.addHandler(email_handler)

    def log(self, msg, lvl=logging.INFO):
        self.logger.log(lvl, msg)

    @staticmethod
    def send_to_gmail(is_text, msg_subject, message_text, date_str=time.strftime(date_format)):
        try:
            to_address = email_addresses
            message_type = "Email"
            if is_text:
                to_address = text_address
                message_type = "Text"
            msg_subject += date_str
            message = """\From: %s\nTo: %s\nSubject: %s\n\n%s""" \
                      % (from_address, ", ".join(to_address), msg_subject, message_text)
            server = smtplib.SMTP("smtp.gmail.com", 587)  # or port 465 doesn't seem to work!
            server.ehlo()
            server.starttls()
            server.login(credentials[0], credentials[1])
            server.sendmail(from_address, to_address, message)
            server.close()
            logging.getLogger().info("Successfully sent: " + message_type)
        except Exception as ex:
            logging.getLogger().warning("ERROR FROM EMAIL SEND FUNCTION: " + ex)

    @staticmethod
    def show_log():
        if IS_WINDOWS:
            file_path = os.path.join(log_location, log_filename)
            commands = ["C:\\Program Files (x86)\\Notepad++\\notepad++.exe", file_path]
            p = Popen(commands)
            



class GenericEmailHandler(logging.StreamHandler):
    def emit(self, record):
        """
        Emit a record.
        Format the record and send it to the specified addressees.
        """
        try:
            date_str = time.strftime(date_format)
            msg = self.format(record)
            MessageHandler.send_to_gmail(True, "Alarm Error! - ", msg, date_str)
        except Exception as ex:
            logging.getLogger().warning("ERROR FROM EMAIL HANDLER: " + ex)
