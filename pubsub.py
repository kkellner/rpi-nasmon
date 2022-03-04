# Handle MQTT publish / subscribe 

import time
import threading
import logging, logging.handlers
import paho.mqtt.client as mqtt
import json
import os
import sys

import yaml


logger = logging.getLogger(__name__)

#
# Node: [NAMESPACE]/node/[NODE_NAME]/status
#    yukon/node/rpibasaltX/status
#
# Device: [NAMESPACE]/device/[TYPE]/[LOCATION_NAME]/[NODE_NAME]/[DEVICE_NAME]/status
#    yukon/device/basalt/driveway/rpibasaltX/light/status
#
# To update all basalt lights in sync -- publish to this queue
# All Device sync: [NAMESPACE]/device/[TYPE]/[LOCATION_NAME]/ALL/[DEVICE_NAME]/status
#    yukon/device/basalt/driveway/ALL/light/status
#
# Pub test message from command-line:
#   mosquitto_pub -h rpicontroller1 -h mqtt.domain.com -u mqtt -P XXXXX -r -d -t "yukon/device/halloween-tombstone/front/ALL/light/status" -m '{ "lightState": "FLAME"}'
#   mosquitto_sub -h rpicontroller1 -h mqtt.domain.com -u mqtt -P XXXXX -d -t "yukon/device/halloween-tombstone/front/rpihalloween/light/status"
#
class Pubsub:

 
    def __init__(self, _nasMon):
        self.nasMon = _nasMon

        ymlfile = open("config.yml", 'r')
        cfg = yaml.safe_load(ymlfile)
        mqttConfig = cfg['mqtt']

        self.mqttBrokerHost = mqttConfig['host']
        self.mqttBrokerPort = mqttConfig['port']
        self.mqttBrokerUsername = mqttConfig['username']
        self.mqttBrokerPassword = mqttConfig['password']

        self.queueNamespace = mqttConfig['queue']['queueNamespace']
        self.locationName = mqttConfig['queue']['locationName']
        self.typeName = mqttConfig['queue']['typeName']
        self.deviceName = mqttConfig['queue']['deviceName']

        self._deviceBirthMsg = None

        # Node name example: yukon/node/rpibasalt1/status
        _nodeName = os.uname().nodename
        # Remove the domain part of the hostname if it exits
        self.nodeName = _nodeName.partition('.')[0]

        self.queueNodeStatus = self.queueNamespace + "/node/" + self.nodeName + "/status"

        # Device name example: yukon/device/basalt/driveway/basalt1/light/status
        self.queueDeviceStatus = self.queueNamespace + "/device/" + self.typeName + "/" + self.locationName + "/" + self.nodeName + "/" + self.deviceName + "/status"
        self.queueDeviceAllStatus = self.queueNamespace + "/device/" + self.typeName + "/" + self.locationName + "/ALL/" + self.deviceName + "/status"


        logger.info("Node name: %s Node MQTT: %s Device MQTT: %s", self.nodeName, self.queueNodeStatus, self.queueDeviceStatus )
        # Connect to MQTT broker
        self.client = mqtt.Client(client_id=self.nodeName)
        mqttLogger = logging.getLogger('mqtt')
        self.client.enable_logger(mqttLogger)
        self.client.reconnect_delay_set(1, 30)
        self.client.max_queued_messages_set(10)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        #deathPayload = "DISCONNECTED"
        deathPayload = "offline"  # Has to be 'offline' (to match node death) so Home Assistant will work
        self.client.will_set(self.queueNodeStatus, deathPayload, 0, True)

        #self.client.message_callback_add(self.queueDeviceAllStatus, self.on_message_light_status)
        self.client.on_message = self.on_message

        self.client.username_pw_set(self.mqttBrokerUsername, self.mqttBrokerPassword)
        self.client.connect_async(self.mqttBrokerHost,self.mqttBrokerPort,60)

        self.client.loop_start()

    ######################################################################
    # Allow other classes to set the device birth msg prior to connecting
    ######################################################################
    def setDeviceBirthMsg(self, msg):
        self._deviceBirthMsg = msg

    ######################################################################
    # Publish the BIRTH certificates
    ######################################################################
    def publishBirth(self):
        self.publishNodeBirth()
        self.publishDeviceBirth()

    ######################################################################
    # Publish the NODE BIRTH certificate
    ######################################################################
    def publishNodeBirth(self):
        logger.info("Publishing Node Birth")
        payload = "online"
        self.client.publish(self.queueNodeStatus, payload, 0, True)

    ######################################################################
    # Publish the DEVICE BIRTH certificate
    ######################################################################
    def publishDeviceBirth(self):
        if self._deviceBirthMsg is not None:
            logger.info("Publishing Device Birth")
            payload = json.dumps(self._deviceBirthMsg)
            self.client.publish(self.queueDeviceStatus, payload, 0, True)

    ######################################################################
    # Publish the NODE offline
    ######################################################################
    def publishNodeOffline(self):
        # logger.info("Publishing Device Death")
        # payload = "unknown"
        # self.client.publish(self.queueDeviceStatus, payload, 0, True)
        logger.info("Publishing Node Death")
        payload = "offline"
        self.client.publish(self.queueNodeStatus, payload, 0, True)
        
    def on_connect(self, client, userdata, flags, rc):
        logger.info("Connected with result code "+str(rc))
        self.publishBirth()
        self.client.subscribe(self.queueDeviceAllStatus, qos=2)

    def on_disconnect(self, client, userdata, rc):
        logger.warn("Disconnected with result code "+str(rc))


    ######################################################################
    # Subscribe: To all "other" messages, which we shouldn't have any
    ######################################################################
    def on_message(self, client, userdata, msg):
        topic=msg.topic
        logger.info("Got generic message from %s timestamp: %s", topic, msg.timestamp)


    ######################################################################
    # Subscribe: List for the ALL (sync) queue to change light state
    ######################################################################
    # def on_message_light_status(self, client, userdata, msg):
    #     try:
    #         topic=msg.topic
    #         logger.info("Got message from %s timestamp: %s", topic, msg.timestamp)
    #         m_decode=str(msg.payload.decode("utf-8","ignore"))
    #         #logger.info("data Received type %s",type(m_decode))
    #         logger.info("data Received: %s",m_decode)
    #         m_in=json.loads(m_decode) #decode json data
    #         lightStateName = m_in["lightState"]
    #         logger.info("payload light state = %s", lightStateName)

    #         if not lightStateName in LightState.__members__:
    #             logger.error("Unknown light state name: [%s]", lightStateName)
    #             return

    #         lightState = LightState[lightStateName]
    #         light = self.basalt.light
    #         light.setLightState(lightState)
    #     except: # catch *all* exceptions
    #         e = sys.exc_info()
    #         logger.error("Exception in on_message_light_status: %s", e)

    def shutdown(self):
        logger.info("Shutdown -- disconnect from MQTT broker")
        self.publishNodeOffline()
        self.client.loop_stop()
        self.client.disconnect()


    ######################################################################
    # publish the current state of nas
    ######################################################################
    def publishCurrentState(self, jsonState):
        # jsonStateExample = {
        #     "lightState": lightStateName,
        #     "time" : time.time()
        # }
        self.publishEventObject(self.queueDeviceStatus, jsonState, True)


    def publishEventObject(self, eventQueue, eventData, retain=False):
        data_out=json.dumps(eventData) # encode object to JSON
        return self.publishEventString(eventQueue, data_out, retain)

    def publishEventString(self, eventQueue, eventString, retain=False):
        logger.info("Publish to queue:[%s] data:[%s] retain:[%s]", eventQueue, eventString, retain)
        msg_info = self.client.publish(eventQueue, eventString, qos=0, retain=retain)
        #msg_info.wait_for_publish()
        return msg_info
