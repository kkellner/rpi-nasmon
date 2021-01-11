#!/usr/bin/python3
# Publish to MQTT stats on the Raspberry Pi running NAS (Open Media Vault)
#
# This includes I2C sensors:
#   - SI7021 - temperature, humitity
#   - INA3221 - Volage and Current of Pi and each USB drive.
# 


import time
import logging, logging.handlers 
import signal
import sys
import os
import threading

#import RPi.GPIO as GPIO
#import board


from pubsub import Pubsub
from nas_stats import NasStats
from http_request import HttpServer


logger = logging.getLogger(__name__)


class NasMon:
    """Handle NAS stats publish via MQTT"""

    def __init__(self):
        self.pubsub = None
        self.server = None
        self.nasStats = None

        # Docs: https://docs.python.org/3/library/logging.html
        # Docs on config: https://docs.python.org/3/library/logging.config.html
        FORMAT = '%(asctime)-15s %(threadName)-10s %(levelname)6s %(message)s'
        logging.basicConfig(level=logging.NOTSET, format=FORMAT)
  
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)


    def __setup_logger(self, logger_name, log_file, level=logging.INFO):
        l = logging.getLogger(logger_name)
        FORMAT = '%(asctime)-15s %(message)s'
        formatter = logging.Formatter(FORMAT)
        # Docs: https://docs.python.org/3/library/logging.handlers.html#logging.handlers.RotatingFileHandler
        fileHandler = logging.handlers.RotatingFileHandler(log_file, mode='a',
                                                           maxBytes=1000000, backupCount=2)
        fileHandler.setFormatter(formatter)
        l.setLevel(level)
        l.addHandler(fileHandler)
        l.propagate = False
  
    def signal_handler(self, signal, frame):
        logger.info('Shutdown...')

        self.shutdown()
        sys.tracebacklimit = 0
        sys.exit(0)

    def startup(self):
        logger.info('Startup...')

        self.nasStats = NasStats(self)
        self.pubsub = Pubsub(self)
        self.nasStats.startup()

        self.server = HttpServer(self)
        # the following is a blocking call
        self.server.run()

    def shutdown(self):
        if self.server is not None:
            self.server.shutdown()
        if self.nasStats is not None:
            self.nasStats.shutdown()
        if self.pubsub is not None:
            self.pubsub.shutdown()


def main():
    """
    The main function
    :return:
    """
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")

    # f = open("/proc/net/wireless", "rt")
    # data = f.read()
    # link = int(data[177:179])
    # level = int(data[182:185])
    # noise = int(data[187:192])
    # print("Link:{} Level:{} Noise:{}".format(link, level, noise))

    nasMon = NasMon()
    nasMon.startup()


if __name__ == '__main__':
    main()