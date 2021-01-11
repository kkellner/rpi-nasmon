"""
Get various stats from RPi including i2c info

RPi Header pins (for I2C bus1)

1   3v
3  GPIO2 (SDL)
5  GPIO3 (SCL)
7  n/a
9  GND


si7021 - temperature & Humidity i2c sensor.
   ref: https://learn.adafruit.com/adafruit-si7021-temperature-plus-humidity-sensor/circuitpython-code
ina3221 - Voltage and Current sensor (3 channel)
    #1 - RPi power/current
    #2 - USB drive 1 (data1) power/current
    #3 - USB drive 2 (data2) power/current

Show i2c sensors addresses:
sudo i2cdetect -y 1
"""

import logging
import time
import datetime
import threading
import sys

import board
import adafruit_si7021
from barbudor_ina3221.full import *

logger = logging.getLogger(__name__)


# Ref: http://theorangeduck.com/page/synchronized-python
def synchronized_method(method):
    
    outer_lock = threading.Lock()
    lock_name = "__"+method.__name__+"_lock"+"__"
    
    def sync_method(self, *args, **kws):
        with outer_lock:
            if not hasattr(self, lock_name): setattr(self, lock_name, threading.Lock())
            lock = getattr(self, lock_name)
            with lock:
                return method(self, *args, **kws)  

    return sync_method


class NasStats:

    def __init__(self, _nasMon):
        self.nasMon = _nasMon
        self.stats_thread = None
        self.stats_thread_stop = threading.Event()
        self.tempHumSensor = None
        self.voltCurrentSensor = None

    def startup(self):
        logger.info('NasStats Startup...')

        i2c_bus = board.I2C()
        # The si7021 has a i2c address of 0x40
        # We try to init the sensor 6 times because sometimes we get the following error on init:
        #   adafruit_si7021.py", line 100: RuntimeError("bad USER1 register (%x!=%x)" % (value, _USER1_VAL))
        for x in range(6):
            try:
                self.tempHumSensor = adafruit_si7021.SI7021(board.I2C())
                break
            except RuntimeError as e:
                #e = sys.exc_info()
                logger.error("Try %d Unexpected error type: %s Msg: %s", x, type(e), e)
                time.sleep(1)
            

        # The INA3221 has a i2c address of 0x41 (changed from default)
        self.voltCurrentSensor = INA3221(i2c_bus, 0x41)
        # improve accuracy by slower conversion and higher averaging
        # each conversion now takes 128*0.008 = 1.024 sec
        # which means 2 seconds per channel
        self.voltCurrentSensor.update(reg=C_REG_CONFIG,
                    mask=C_AVERAGING_MASK |
                    C_VBUS_CONV_TIME_MASK |
                    C_SHUNT_CONV_TIME_MASK |
                    C_MODE_MASK,
                    value=C_AVERAGING_128_SAMPLES |
                    C_VBUS_CONV_TIME_8MS |
                    C_SHUNT_CONV_TIME_8MS |
                    C_MODE_SHUNT_AND_BUS_CONTINOUS)

        # enable all 3 channels. You can comment (#) a line to disable one
        self.voltCurrentSensor.enable_channel(1)
        self.voltCurrentSensor.enable_channel(2)
        self.voltCurrentSensor.enable_channel(3)

        self.startStatsThread()

    def shutdown(self):
        logger.info('Shutdown...')
        self.stopStatsThread()

    def startStatsThread(self):

        if self.stats_thread is None:
            logger.info('stats thread start request')
            self.stats_thread = threading.Thread(target=self.statsThread)
            self.stats_thread.daemon = True
            self.stats_thread_stop.clear()
            self.stats_thread.start()


    def stopStatsThread(self):

        if self.stats_thread is not None:
            logger.info('stats thread stop request')
            self.stats_thread_stop.set()
            self.stats_thread.join()
            self.stats_thread = None
            logger.info('stats thread stopped')

    def statsThread(self):
       
        while not self.stats_thread_stop.isSet():
            #now = time.time() * 1000
          
            logger.info('stats thread get-stats')

            data = self.getStats()
            self.nasMon.pubsub.publishCurrentState(data)

            self.stats_thread_stop.wait(30)
            #time.sleep(5)
        logger.info('stats thread EXITING')



    # Only one thread can call at a time
    @synchronized_method
    def getStats(self):

        # TODO: Optimize by caching the result and return the cache value if
        # its within the last 10 seconds.

        logger.info('in getStats ############')

        if self.tempHumSensor is None:
            return {}

        now = time.time()
        beginTime = now
        tempCelsius = self.tempHumSensor.temperature
        humidity = round(self.tempHumSensor.relative_humidity,1)

        #print('Temperature: %0.1f C (%0.1f F)  humidity: %0.1f %%' % (tempCelsius, celsius2fahrenheit(tempCelsius), humidity))
        while not self.voltCurrentSensor.is_ready:
            print(".",end='')
            time.sleep(0.1)
        print("")


        # WARNING: These method calls can take 2 seconds total to complete (because of sample size)
        channel = 1
        rpi_bus_voltage = round(self.voltCurrentSensor.bus_voltage(channel),2)
        rpi_shunt_voltage = round(self.voltCurrentSensor.shunt_voltage(channel),2)
        rpi_current = round(self.voltCurrentSensor.current(channel),3)
        rpi_psu_voltage = round(rpi_bus_voltage + rpi_shunt_voltage,2)

        channel = 2
        drive1_bus_voltage = round(self.voltCurrentSensor.bus_voltage(channel),2)
        drive1_shunt_voltage = round(self.voltCurrentSensor.shunt_voltage(channel),2)
        drive1_current = round(self.voltCurrentSensor.current(channel),3)
        drive1_psu_voltage = round(drive1_bus_voltage + drive1_shunt_voltage,2)

        channel = 3
        drive2_bus_voltage = round(self.voltCurrentSensor.bus_voltage(channel),2)
        drive2_shunt_voltage = round(self.voltCurrentSensor.shunt_voltage(channel),2)
        drive2_current = round(self.voltCurrentSensor.current(channel),3)
        drive2_psu_voltage = round(drive2_bus_voltage + drive2_shunt_voltage,2)

        endTime = time.time()
        collectStatsDuration = endTime-beginTime


        logger.info("Time to get stats: %0.3fms",  collectStatsDuration)
        stats = { 
            'timestampEpoc': now,
            'timestamp': datetime.datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'collectStatsDuration': round(collectStatsDuration, 3),
            'temperature': round(self.celsius2fahrenheit(tempCelsius), 1),
            'humidity': humidity,

            'rpi_psu_voltage':rpi_psu_voltage,
            'rpi_current': rpi_current,
            'rpi_bus_voltage': rpi_bus_voltage,

            'drive1_psu_voltage':drive1_psu_voltage,
            'drive1_current': drive1_current,
            'drive1_bus_voltage': drive1_bus_voltage,

            'drive2_psu_voltage':drive2_psu_voltage,
            'drive2_current': drive2_current,
            'drive2_bus_voltage': drive2_bus_voltage,

        }
        return stats


    def celsius2fahrenheit(self, celsius):
        return (celsius * 1.8) + 32


