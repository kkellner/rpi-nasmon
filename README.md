# rpi-nasmon - Raspberry Pi 4b NAS monitor

This python project is installed on a Raspberry Pi 4b running OpenMediaVault.
It queries i2c sensors to monitor:
- temperature
- humitity
- voltage supplyed to Pi via PoE
- current draw on Pi
- current draw of USB drive 1
- current draw of USB drive 2

It also queries the disk free information (via `df `command).

All this information is then published as JSON to MQTT every 30 seconds.  
This information is then consumed by Home Asssitant to record history and
provide alerting as needed (e.g., over temperature, low disk space)

# Python Prerequisites 

```

sudo apt-get install -y python3-pip
sudo apt-get install -y python-smbus
sudo apt-get install -y i2c-tools
sudo apt-get install -y python3-rpi.gpio
sudo pip3 install paho-mqtt
sudo pip3 install RPI.GPIO
sudo pip3 install adafruit-blinka
sudo pip3 install adafruit-circuitpython-si7021
sudo pip3 install barbudor-circuitpython-ina3221
```

## Enable i2c on Pi

```
sudo raspi-config nonint do_i2c 0
```
