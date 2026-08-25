# TL;DR
If you want to poll your **ACCUR8** or any **WeatherRouter**-based SoC PWS weather station **without** having it connected to the internet, just run:

    curl "http://<IP>/client?command=record"

It'll return a JSON array of all the available sensors, something like:

    {
      "sensor":[
        {
          "title":"Indoor",
          "list":[["Temperature","20.3","°C"],["Humidity","43","%"]]
        },
        {
          "title":"Outdoor",
          "list":[["Temperature","9.9","°C"],["Humidity","38","%"]]
        },
        {
          "title":"Pressure",
          "list":[["Absolute","985.6","hpa"],["Relative","1012.0","hpa"]]
        },
        {
          "title":"Wind Speed",
          "list":[
            ["Max Daily Gust","3.3","m/s"],
            ["Wind","0.9","m/s"],
            ["Gust","1.0","m/s"],
            ["Direction","216","°"],
            ["Wind Average 2 Minute","0.8","m/s"],
            ["Direction Average 2 Minute","243","°"],
            ["Wind Average 10 Minute","0.4","m/s"],
            ["Direction Average 10 Minute","271","°"]
          ]
        },
        {
          "title":"Rainfall",
          "list":[
            ["Rate","0.0","mm/hr"],
            ["Hour","0.0","mm","43"],
            ["Day","0.0","mm","44"],
            ["Week","3.0","mm","45"],
            ["Month","3.0","mm","46"],
            ["Year","3.0","mm","47"],
            ["Total","3.0","mm","48"]
          ],
          "range":"Range: 0mm to 9999.9mm. "
        }
      ],
      "battery":{
        "title":"Battery",
        "list":["All battery are ok"]
      }
    }

You don't need to configure **wunderground.com** or **weathercloud.net** (like the manual suggests), and you don't need Docker or HomeAssistant just to pull the data.

The units are whatever you've set on the console, so if you've switched it to °F or mph that's what you'll get back.

# Introduction / Why
My wife got me an **ACCUR8 DWS5100 5-in-1 Weather Station (PWS)** for Christmas. Being an amateur security researcher, I set it up and then did a quick penetration test. The results were concerning enough that I ended up blocking its internet access. Unfortunately, the manual doesn't list any direct way to poll the data.

A quick online search led me to a bunch of solutions involving configuring uploads to **wunderground.com** or **weathercloud.net**, which I didn't want to do. So I reverse engineered the product and figured out how to collect the data directly.

# Explanation / How
Once the weather station is set up, the manual states there are two pages available:
1. One to configure the WiFi and upload settings.
2. Another to upgrade the firmware.

When viewing the configuration page's source, I saw it uses two JavaScript files:
- `setting.js`
- `common.js`

`common.js` references a page called `record.html` with a "Live Data" tag. That page doesn't exist, so I guessed there might be a `record.js` file. Indeed, `record.js` contained several calls, including:

    client?command=record
    client?command=rec_refresh

`record` pulls the entire set of current data values. I believe `rec_refresh` only shows changes, which might be more efficient. I haven't looked too deeply into it yet, but it's definitely worth exploring if you want to minimise data transfer or poll more frequently.

# What's in this repo

## WeeWX driver
`weewx/weatherrouter.py` polls the station and feeds it into WeeWX. Copy it into your WeeWX user directory (`bin/user/` on WeeWX 4, `/etc/weewx/bin/user/` if you installed WeeWX 5 from a package) and add this to `weewx.conf`:

    [Station]
        station_type = WeatherRouter

    [WeatherRouter]
        driver = user.weatherrouter
        url = http://<IP>/client?command=record
        poll_interval = 60

Then restart weewx. It reads the unit off each value and converts, so it doesn't matter what units the console is set to. Rain is worked out as the difference in the station's running total between polls, which is what WeeWX wants. You can test it on its own with `python3 weatherrouter.py http://<IP>/client?command=record`.

## Python script
`examples/poll.py` pulls the data every 10 seconds and shows it in a table.

    pip install -r requirements.txt
    python3 examples/poll.py <IP>

Add `--once` to grab a single reading, and `--csv weather.csv` to append it to a CSV you can open in Excel. Stick that in cron and you've got a daily log:

    0 9 * * * /usr/bin/python3 /home/you/ACCUR8/examples/poll.py <IP> --once --csv /home/you/weather.csv

## Home Assistant
If you'd rather have it in HA, a `rest` sensor is enough:

    rest:
      - resource: http://<IP>/client?command=record
        scan_interval: 60
        sensor:
          - name: "Weather station outdoor temperature"
            unit_of_measurement: "°C"
            device_class: temperature
            value_template: "{{ value_json.sensor[1].list[0][1] }}"
          - name: "Weather station outdoor humidity"
            unit_of_measurement: "%"
            device_class: humidity
            value_template: "{{ value_json.sensor[1].list[1][1] }}"
          - name: "Weather station relative pressure"
            unit_of_measurement: "hPa"
            device_class: pressure
            value_template: "{{ value_json.sensor[2].list[1][1] }}"

The index positions match the JSON at the top.

# Further Work
It looks like there are a bunch of weather stations using the same SoC (the chip is CCL's WeatherRouter, ACCUR8 is just the brand on the box). I suspect you can pull data directly from all of them. Please let me know if it works for you, ideally with the model and firmware version, and I'll list it here.

| Station | Firmware |
|---|---|
| ACCUR8 DWS5100 5-in-1 | WeatherRouter V1.2.x |

Licence is MIT.
