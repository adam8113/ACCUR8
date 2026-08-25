# WeeWX driver for weather stations built on the CCL "WeatherRouter" SoC.
# Sold as ACCUR8 DWS5100 and under other white-label names.
#
# The station serves current readings as JSON at
#   http://<station-ip>/client?command=record
# with no authentication. This driver polls that URL and turns each
# response into a WeeWX loop packet.
#
# weewx.conf:
#
#   [Station]
#       station_type = WeatherRouter
#
#   [WeatherRouter]
#       driver = user.weatherrouter
#       url = http://192.0.2.10/client?command=record
#       poll_interval = 60
#
# Install: copy this file to the WeeWX user directory (bin/user/ on WeeWX 4,
# /etc/weewx/bin/user/ on a WeeWX 5 package install), add the config above,
# restart weewx.

import logging
import time

import requests

import weewx
import weewx.drivers

DRIVER_NAME = 'WeatherRouter'
DRIVER_VERSION = '1.1'

log = logging.getLogger(__name__)


def loader(config_dict, engine):
    return WeatherRouterDriver(**config_dict[DRIVER_NAME])


# Readings are emitted in METRICWX: degC, m/s, mm, mbar (1 hPa == 1 mbar).
# The station lets the owner change display units, and the unit string comes
# back with every value, so convert from whatever it reports.

def _to_c(value, unit):
    return (value - 32.0) * 5.0 / 9.0 if 'F' in unit else value


def _to_mps(value, unit):
    unit = unit.lower()
    if unit == 'km/h':
        return value / 3.6
    if unit == 'mph':
        return value * 0.44704
    if unit in ('knots', 'knot', 'kt', 'kts'):
        return value * 0.514444
    return value


def _to_mbar(value, unit):
    unit = unit.lower()
    if unit == 'inhg':
        return value * 33.8639
    if unit == 'mmhg':
        return value * 1.33322
    return value


def _to_mm(value, unit):
    return value * 25.4 if unit.lower().startswith('in') else value


class WeatherRouterDriver(weewx.drivers.AbstractDevice):

    def __init__(self, **stn_dict):
        self.url = stn_dict.get('url')
        if not self.url:
            raise ValueError("[%s] needs a 'url' setting" % DRIVER_NAME)
        self.poll_interval = float(stn_dict.get('poll_interval', 60))
        self.timeout = float(stn_dict.get('timeout', 10))
        self.last_rain_total = None
        log.info("%s %s polling %s every %ss",
                 DRIVER_NAME, DRIVER_VERSION, self.url, self.poll_interval)

    @property
    def hardware_name(self):
        return DRIVER_NAME

    def genLoopPackets(self):
        while True:
            try:
                response = requests.get(self.url, timeout=self.timeout)
                response.raise_for_status()
                yield self._parse(response.json())
            except Exception as e:
                log.error("fetch or parse failed: %s", e)
            time.sleep(self.poll_interval)

    @staticmethod
    def _groups(data):
        """Return {group title: {reading name: (value, unit)}}."""
        groups = {}
        for sensor in data.get('sensor', []):
            readings = {}
            for item in sensor.get('list', []):
                if len(item) < 2:
                    continue
                try:
                    value = float(item[1])
                except (TypeError, ValueError):
                    continue
                unit = item[2] if len(item) > 2 else ''
                readings[item[0]] = (value, unit)
            groups[sensor.get('title', '')] = readings
        return groups

    def _parse(self, data):
        g = self._groups(data)
        packet = {'dateTime': int(time.time()), 'usUnits': weewx.METRICWX}

        def put(field, group, name, convert):
            reading = g.get(group, {}).get(name)
            if reading is not None:
                packet[field] = convert(*reading)

        put('inTemp', 'Indoor', 'Temperature', _to_c)
        put('inHumidity', 'Indoor', 'Humidity', lambda v, u: v)
        put('outTemp', 'Outdoor', 'Temperature', _to_c)
        put('outHumidity', 'Outdoor', 'Humidity', lambda v, u: v)
        put('pressure', 'Pressure', 'Absolute', _to_mbar)
        put('barometer', 'Pressure', 'Relative', _to_mbar)
        put('windSpeed', 'Wind Speed', 'Wind', _to_mps)
        put('windGust', 'Wind Speed', 'Gust', _to_mps)
        put('windDir', 'Wind Speed', 'Direction', lambda v, u: v)
        put('rainRate', 'Rainfall', 'Rate', _to_mm)

        # WeeWX wants rain as the amount since the previous packet. The station
        # only gives running totals, so diff the lifetime total. A total that
        # goes backwards means the counter was reset on the console.
        total = g.get('Rainfall', {}).get('Total')
        if total is not None:
            total_mm = _to_mm(*total)
            if self.last_rain_total is not None:
                delta = total_mm - self.last_rain_total
                packet['rain'] = delta if delta >= 0 else 0.0
            self.last_rain_total = total_mm

        battery = data.get('battery', {}).get('list', [])
        if battery:
            packet['outTempBatteryStatus'] = 0.0 if any(
                'ok' in str(line).lower() for line in battery) else 1.0

        log.debug("packet: %s", packet)
        return packet


if __name__ == '__main__':
    # Standalone check: python3 weatherrouter.py http://<station-ip>/client?command=record
    import sys
    import weeutil.logger
    import weeutil.weeutil

    weewx.debug = 1
    weeutil.logger.setup('weatherrouter')
    url = sys.argv[1] if len(sys.argv) > 1 else 'http://192.0.2.10/client?command=record'
    driver = WeatherRouterDriver(url=url, poll_interval=10)
    for pkt in driver.genLoopPackets():
        print(weeutil.weeutil.timestamp_to_string(pkt['dateTime']), pkt)
