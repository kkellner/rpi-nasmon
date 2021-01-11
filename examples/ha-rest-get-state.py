#!/usr/bin/python3

"""
HA API: https://developers.home-assistant.io/docs/api/rest/
"""
from requests import get
import yaml


ymlfile = open("config.yml", 'r')
cfg = yaml.safe_load(ymlfile)
haConfig = cfg['homeassistant']
haUrl = haConfig['url']
haAccessToken = haConfig['access_token']

entity_id = "sensor.indoor_humidity"

url = "{}/api/states/{}".format(haUrl, entity_id)
headers = {
    "Authorization": "Bearer {}".format(haAccessToken),
    "content-type": "application/json",
}

response = get(url, headers=headers)
print(response.text)

