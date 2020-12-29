#!/usr/bin/python3

"""
HA API: https://developers.home-assistant.io/docs/api/rest/
"""
from requests import post
import yaml


ymlfile = open("config.yml", 'r')
cfg = yaml.safe_load(ymlfile)
haConfig = cfg['homeassistant']
haUrl = haConfig['url']
haAccessToken = haConfig['access_token']

entity_id = "input_number.ceiling_display_brightness"

url = "{}/api/states/{}".format(haUrl, entity_id)
headers = {
    "Authorization": "Bearer {}".format(haAccessToken),
    "content-type": "application/json",
}

json_state = '''
{
    "state": "90.0"
}
'''

response = post(url, headers=headers, data=json_state)
print(response.text)

