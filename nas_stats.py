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
import pytz
import threading
import sys
import subprocess
import json

import psutil
import os

import board
import adafruit_si7021
import adafruit_bme280
from barbudor_ina3221.full import *

logger = logging.getLogger(__name__)


MAX_CACHE_TIME_SECONDS = 10

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
        self.tempHumSensor1 = None
        self.tempHumSensor2 = None
        self.voltCurrentSensor = None

        self.stats_cache = None
        self.stats_cache_timestamp = 0
        self.filesystemDict_cache = {}
        self.deviceSupportsSmart = {}

    def startup(self):
        logger.info('NasStats Startup...')

        now = time.time()
        stats = { 
            'timestampEpoc': now,
            'timestamp': datetime.datetime.fromtimestamp(now,pytz.timezone("America/Denver")).strftime('%Y-%m-%d %H:%M:%S.%f%z'),
            'state': 'starting'
        }
        self.nasMon.pubsub.setDeviceBirthMsg( stats )


        i2c_bus = board.I2C()
        # The si7021 has a i2c address of 0x40
        # We try to init the sensor multiple times because sometimes we get the following error on init:
        #   adafruit_si7021.py", line 100: RuntimeError("bad USER1 register (%x!=%x)" % (value, _USER1_VAL))
        for x in range(30):
            try:
                self.tempHumSensor1 = adafruit_si7021.SI7021(i2c_bus)
                break
            except RuntimeError as e:
                #e = sys.exc_info()
                logger.error("Try %d Unexpected error type: %s Msg: %s", x, type(e), e)
                time.sleep(2)
            
        self.tempHumSensor2 = adafruit_bme280.Adafruit_BME280_I2C(i2c_bus, address=0x76)

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
        #data = self.getStats()

        now = time.time()
        stats = { 
            'timestampEpoc': now,
            'timestamp': datetime.datetime.fromtimestamp(now,pytz.timezone("America/Denver")).strftime('%Y-%m-%d %H:%M:%S.%f%z'),
            'state': 'shutdown'
        }
        self.nasMon.pubsub.publishCurrentState( stats )

    def startStatsThread(self):

        if self.stats_thread is None:
            logger.info('stats thread start request')
            self.stats_thread = threading.Thread(target=self.statsThread, name='statsUpdate')
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
          
            data = self.getStats()
            self.nasMon.pubsub.publishCurrentState( data )

            self.stats_thread_stop.wait(30)
            #time.sleep(5)
        logger.info('stats thread EXITING')



    # Only one thread can call at a time
    @synchronized_method
    def getStats(self):

        logger.info('in getStats')
        now = time.time()

        if self.stats_cache is not None and ((now - self.stats_cache_timestamp) < MAX_CACHE_TIME_SECONDS):
            logger.debug('in getStats returning value from cache')
            return self.stats_cache 

        if self.tempHumSensor1 is None:
            return {}

       
        beginTime = now

        cpuPercent = psutil.cpu_percent()
        cpuFreq = psutil.cpu_freq().current
        cpuTemperature = round(self.celsius2fahrenheit(psutil.sensors_temperatures()['cpu_thermal'][0].current), 1)
        memoryUsedPercent = psutil.virtual_memory().percent

        osStartTime = psutil.boot_time()
        osUptime = now - osStartTime

        p = psutil.Process(os.getpid())
        appStartTime = p.create_time()
        appUptime = now - appStartTime

        # TOOD: Look at example to get more stats:  https://gist.github.com/nathants/8e3b26e769abf86ece8d

        # Another example to build JSON from disk stats:
        #   https://python.hotexamples.com/site/file?hash=0x6f656f01be305c953664bc327ab3befbaa9cd4b3ac919f77dcb27692d33b3ddf&fullName=SchoolZillaDevOpsHomework-master/server.py&project=xoho/SchoolZillaDevOpsHomework



        enclosure_tempCelsius1 = self.tempHumSensor1.temperature
        enclosure_humidity1 = round(self.tempHumSensor1.relative_humidity,1)

        enclosure_tempCelsius2 = self.tempHumSensor2.temperature
        enclosure_humidity2 = round(self.tempHumSensor2.relative_humidity,1)
        enclosure_pressure = self.tempHumSensor2.pressure

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

        #filesystemInfo = self.runFilesystemInfoScript()
        filesystemInfo = self.getFilesystemInfo()

        endTime = time.time()
        collectStatsDuration = endTime-beginTime


        logger.info("Time to get stats: %0.3fms",  collectStatsDuration)
        stats = { 
            'timestampEpoc': now,
            'timestamp': datetime.datetime.fromtimestamp(now,pytz.timezone("America/Denver")).strftime('%Y-%m-%d %H:%M:%S.%f%z'),
            'collectStatsDuration': round(collectStatsDuration, 3),

            'os': {
                "cpuPercent": cpuPercent,
                "cpuFreq": cpuFreq,
                "cpuTemperature": cpuTemperature,
                "memoryUsedPercent": memoryUsedPercent,
                "bootTimestampEpoc": osStartTime,
                "uptime": round(osUptime,3),
                "uptimeFmt": str(datetime.timedelta(seconds=round(osUptime))),
                "monUptime": round(appUptime,3),
                "monUptimeFmt": str(datetime.timedelta(seconds=round(appUptime))),
            },

            'enclosure': {
                'temperature1': round(self.celsius2fahrenheit(enclosure_tempCelsius1), 1),
                'humidity1': enclosure_humidity1,
                'temperature2': round(self.celsius2fahrenheit(enclosure_tempCelsius2), 1),
                'humidity2': enclosure_humidity2,
                'pressure': round(enclosure_pressure, 2)
            },

            'power': {
                'rpi_psu_voltage':rpi_psu_voltage,
                'rpi_current': rpi_current,
                'rpi_bus_voltage': rpi_bus_voltage,

                'drive1_psu_voltage':drive1_psu_voltage,
                'drive1_current': drive1_current,
                'drive1_bus_voltage': drive1_bus_voltage,

                'drive2_psu_voltage':drive2_psu_voltage,
                'drive2_current': drive2_current,
                'drive2_bus_voltage': drive2_bus_voltage,

                'watts': round((rpi_current * rpi_bus_voltage) + (drive1_current * drive1_bus_voltage) + (drive2_current * drive2_bus_voltage), 1),
                
            },

            'filesystem': filesystemInfo

        }

        self.stats_cache = stats
        self.stats_cache_timestamp = now

        return stats


    def celsius2fahrenheit(self, celsius):
        return (celsius * 1.8) + 32


    def runFilesystemInfoScript(self):

        cmd = "./filesystem_info.sh"
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        
        if p.returncode != 0:
            logger.error("runFilesystemInfoScript returncode: %d", p.returncode)
        
        cmdOutput = p.stdout.strip()
        jsonResult = json.loads(cmdOutput)

        # Convert numbers from string to int JSON value and calculate spaceusedpercent to get multiple decimal places of accuracy  
        for filesystem in jsonResult:
            filesystem['spacetotal'] = int(filesystem['spacetotal'])
            filesystem['spaceused'] = int(filesystem['spaceused'])
            filesystem['spaceavail'] = int(filesystem['spaceavail'])
            filesystem['spaceusedpercent'] = (filesystem['spaceused'] / filesystem['spacetotal']) * 100

        return jsonResult




    def getFilesystemInfo(self):

        diskIoCounters = psutil.disk_io_counters(perdisk=True)
        filesystems = getMountedFilesystems()
        # for filesystem in filesystems:
        #     io = diskIoCounters[filesystem['kname']]
        #     filesystem['read_bytes'] = io.read_bytes
        #     filesystem['write_bytes'] = io.write_bytes
            
        #     usage = psutil.disk_usage(filesystem['mountpoint'])
        #     filesystem['spacetotal'] = usage.total
        #     filesystem['spaceused'] = usage.used
        #     filesystem['spaceavail'] = usage.free
        #     filesystem['spaceusedpercent'] = round( ((usage.used / usage.total) * 100), 3)

        filesystemDict = {}
        for filesystem in filesystems:
            label = filesystem['label']
            filesystemDict[label] = filesystem

            io = diskIoCounters[filesystem['kname']]
            filesystem['read_bytes'] = io.read_bytes
            filesystem['write_bytes'] = io.write_bytes
            
            usage = psutil.disk_usage(filesystem['mountpoint'])
            filesystem['spacetotal'] = usage.total
            filesystem['spaceused'] = usage.used
            filesystem['spaceavail'] = usage.free
            filesystem['spaceusedpercent'] = round( ((usage.used / usage.total) * 100), 3)
            
            filesystem_cache = self.filesystemDict_cache.get(label)
            activity_read = False
            activity_write = False
            if filesystem_cache is not None:
                readDiff = io.read_bytes - filesystem_cache['read_bytes']
                writeDiff = io.write_bytes - filesystem_cache['write_bytes']
                # TODO: This is an issue as it depends on the call
                # e.g., if its consistant at every 30 seconds then it would be a reliable
                # We cache this upon every call -- Need to think about it
                #filesystem_cache['read_bytes_diff'] = readDiff
                #filesystem_cache['write_bytes_diff'] = writeDiff

                # timeDiff = (now - filesystem_cache_timestamp)
                # filesystem_cache['read_bytes_per_sec'] = readDiff / (now - timeDiff
                # filesystem_cache['write_bytes_per_sec'] = writeDiff / (now - timeDiff

                activity_read = readDiff > 0 
                activity_write = writeDiff > 0
        
            filesystem['activity_read'] = activity_read
            filesystem['activity_write'] = activity_write
            if activity_read or activity_write:
                # Since there has been activity lately the drive is already spun-up so we can get the drive temperature
                deviceName = "/dev/{}".format(filesystem['pkname'])
                smartCapable = self.deviceSupportsSmart.get(deviceName)
                if smartCapable is None:
                    # Check if device is SMART capable and cache the answer
                    smartCapable = isSMARTCapable(deviceName)
                    self.deviceSupportsSmart[deviceName] = smartCapable
                if smartCapable:
                    tempCurrent,tempMax,tempMin = runSmartCmdForTemperature(deviceName)
                    filesystem['temperature_current'] = tempCurrent
                    filesystem['temperature_max'] = tempMax
                    filesystem['temperature_min'] = tempMin


        #print(filesystemDict)
        self.filesystemDict_cache = filesystemDict
        return filesystemDict

def isSMARTCapable(dev):
    cmd="smartctl -i {}".format(dev)
    exitcode, output = subprocess.getstatusoutput(cmd)
    return exitcode==0

def getMountedFilesystems():
    cmd ="lsblk --noheadings --output label,KNAME,path,MOUNTPOINT,PKNAME --json | jq '[ .blockdevices[] | select( .mountpoint!=null ) ]'"
    cmdOutput = subprocess.getoutput(cmd)
    jsonResult = json.loads(cmdOutput)
    return jsonResult

def runSmartCmdForTemperature(deviceName):

    #cmdOutput = subprocess.getoutput('smartctl -l devstat,0x05 {} --json'.format(deviceName))
    #jsonOutput = json.loads(cmdOutput)

    # This will output three lines: current, max, min
    cmd = """
    sudo smartctl -l devstat,0x05 {} --json | jq '.. | objects | select(.name=="Current Temperature", .name=="Highest Temperature", .name=="Lowest Temperature") | .value '
    """
    cmdOutput = subprocess.getoutput(cmd.format(deviceName))
    currentMaxMin = cmdOutput.split('\n')
    return currentMaxMin


if __name__ == '__main__':
    #out = runSmartCmdForTemperature('/dev/sdb')
    #print(out)
    nas = NasStats(None)
    # nas.getFilesystemInfo()
    # time.sleep(10)
    # x = nas.getFilesystemInfo()
    # print(x)
    # print(json.dumps(x))
    pkname = "sda"
    #x = nas.isSMARTCapable("/dev/sda")
    #print(x)
    currentTemp,maxTemp,minTemp = runSmartCmdForTemperature("/dev/{}".format(pkname))
    print("current:{} max:{} min:{}".format(currentTemp,maxTemp,minTemp))
