#Custom WeeWX driver for Accur8 DWS5100 5-in-1 Weather Station
#Accur8 is the white-label brand name. the SoC chip is WeatherRouter and the manufacturer is CCL. There are a bunch of different versions of this PWS. They should all work. 
#This script polls the PWS every poll_interval seconds. It's been stable for a few days now but I will monitor and ensire compliance with WeeWX custom standards. 

#Weewx.conf required config:
#[CustomDriver]
#    driver = user.driver_custom
#    url = http://IP_ADDRESS/client?command=record
#    poll_interval = 60

import logging
import time
import requests
import json

import weewx.drivers

DRIVER_NAME = 'CustomDriver'
DRIVER_VERSION = '1.0'

log = logging.getLogger(__name__)

def loader(config_dict, engine):
    return CustomDriver(**config_dict[DRIVER_NAME])

class CustomDriver(weewx.drivers.AbstractDevice):
    """Custom WeeWX driver for fetching weather data from a JSON endpoint."""

    def __init__(self, **stn_dict):
        
        self.url = stn_dict.get('url')
        if not self.url:
            raise ValueError("Missing 'url' parameter in configuration.")
        
        self.poll_interval = float(stn_dict.get('poll_interval', 60))
        log.info(f"{DRIVER_NAME} initialized with URL: {self.url}, Poll Interval: {self.poll_interval}s")

    def genLoopPackets(self):
        """Generator yielding loop packets."""
        while True:
            try:
                response = requests.get(self.url, timeout=10)
                response.raise_for_status()
                data = response.json()
                yield self._parse_data(data)
            except Exception as e:
                log.error(f"Error fetching or parsing data: {e}")
            time.sleep(self.poll_interval)

    def _parse_data(self, data):
        """Parse JSON data into a WeeWX loop packet."""
        packet = {
            'dateTime': int(time.time()),
            'usUnits': weewx.US,
        }

       
        for sensor in data.get('sensor', []):
            if sensor['title'] == 'Indoor':
                packet['inTemp'] = float(sensor['list'][0][1])
                packet['inHumidity'] = float(sensor['list'][1][1])
            elif sensor['title'] == 'Outdoor':
                packet['outTemp'] = float(sensor['list'][0][1])
                packet['outHumidity'] = float(sensor['list'][1][1])

        
        for sensor in data.get('sensor', []):
             if sensor['title'] == 'Pressure':
                 raw_pressure_hpa = float(sensor['list'][1][1])
        # Convert hPa to inHg to stop random failure
                 packet['barometer'] = raw_pressure_hpa * 0.02953  # hPa to inHg
                 log.debug(f"Converted barometer: {raw_pressure_hpa} hPa to {packet['barometer']} inHg")


        
        for sensor in data.get('sensor', []):
            if sensor['title'] == 'Wind Speed':
                packet['windSpeed'] = float(sensor['list'][1][1])
                packet['windGust'] = float(sensor['list'][2][1])
                packet['windDir'] = float(sensor['list'][3][1])

        
        for sensor in data.get('sensor', []):
            if sensor['title'] == 'Rainfall':
                packet['rainRate'] = float(sensor['list'][0][1])
                packet['dayRain'] = float(sensor['list'][2][1])

        log.debug(f"Generated packet: {packet}")
        return packet

    @property
    def hardware_name(self):
        return DRIVER_NAME


if __name__ == "__main__":
    import weeutil.weeutil
    import weeutil.logger
    import weewx

    weewx.debug = 1
    weeutil.logger.setup('customdriver')

    driver = CustomDriver(url="http://<IP>/client?command=record", poll_interval=60)
    for packet in driver.genLoopPackets():
        print(weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet)
