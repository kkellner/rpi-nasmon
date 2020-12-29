#!/usr/bin/python3

"""
Initializes the sensor, gets and prints readings every two seconds.


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


"""
import time
import board
import adafruit_si7021

# Create library object using our Bus I2C port
sensor = adafruit_si7021.SI7021(board.I2C())
sensor.set_resolution(0)
#print sensor.get_resolution()

def celsius2fahrenheit(celsius):
   return (celsius * 1.8) + 32

while True:
    tempCelsius = sensor.temperature
    print('Temperature: %0.1f C (%0.1f F)  humidity: %0.1f %%' % (tempCelsius, celsius2fahrenheit(tempCelsius), sensor.relative_humidity))
    time.sleep(2)





