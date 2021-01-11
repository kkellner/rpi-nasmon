#!/usr/bin/python3

"""
HA API: https://developers.home-assistant.io/docs/api/rest/



si7021 - temperature & Humidity i2c sensor.

RPi Header pins (for I2C bus1)

1   3v
3  GPIO2 (SDL)
5  GPIO3 (SCL)
7  n/a
9  GND

GPIO2 - SDL (bus 1)
GPIO3 - SCL (bus 1)

ref: https://learn.adafruit.com/adafruit-si7021-temperature-plus-humidity-sensor/circuitpython-code

Show i2c sensors:
sudo i2cdetect -y 1

Get drive temperature from SMART (but causes drive spin-up)
sudo smartctl -A /dev/sda


/home/kkellner/rpi-sensor-push-homeassistant/ha-update-info.py


"""
from requests import post
import yaml
import time
import board
import adafruit_si7021
import logging
import os, sys, signal

FORMAT = '%(asctime)-15s %(threadName)-10s %(levelname)6s %(message)s'
logging.basicConfig(level=logging.NOTSET, format=FORMAT)

logger = logging.getLogger(__name__)

def celsius2fahrenheit(celsius):
   return (celsius * 1.8) + 32


class HaUpdateInfo:

    def __init__(self):
        #initialize 
        logger.info("startup" )

    def update(self):


        ymlfile = open("config.yml", 'r')
        cfg = yaml.safe_load(ymlfile)
        haConfig = cfg['homeassistant']
        haUrl = haConfig['url']
        haAccessToken = haConfig['access_token']


        # Create library object using our Bus I2C port
        sensor = adafruit_si7021.SI7021(board.I2C())
        tempCelsius = sensor.temperature
        relativeHumidity = sensor.relative_humidity


        headers = {
            "Authorization": "Bearer {}".format(haAccessToken),
            "content-type": "application/json",
        }

        # Update enclosure tempeature
        entity_id = "input_number.bnas01_enclosure_temperature"
        url = "{}/api/states/{}".format(haUrl, entity_id)
        json_state = '{ "state": "%0.1f" }' % celsius2fahrenheit(tempCelsius)
        response = post(url, headers=headers, data=json_state)
        logger.info(response.text)

        # Update enclosure relative humidity
        entity_id = "input_number.bnas01_enclosure_humidity"
        url = "{}/api/states/{}".format(haUrl, entity_id)
        json_state = '{ "state": "%0.1f" }' % relativeHumidity
        response = post(url, headers=headers, data=json_state)
        logger.info(response.text)

        logger.info('Temperature: %0.1f C (%0.1f F)  humidity: %0.1f %%' % (tempCelsius, celsius2fahrenheit(tempCelsius), relativeHumidity))



def main():
    """
    The main function
    :return:
    """
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")

    display = HaUpdateInfo()
    display.update()

    print("Existing app...")
    sys.exit(0) 


if __name__ == '__main__':
    main()
