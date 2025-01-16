# TL;DR
If you want to poll your **ACCUR8** or any **WeatherRouter**-based SoC PWS weather station **without** having it connected to the internet, just run:

    curl "http://<IP>/client?command=record"

It’ll return a JSON array of all the available sensors, something like:

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

You don’t need to configure **wunderground.com** or **weathercloud.net** (like the manual suggests), and you don’t need Docker or HomeAssistant just to pull the data.

---

# Introduction / Why
My wife got me an **ACCUR8 DWS5100 5-in-1 Weather Station (PWS)** for Christmas. Being an amateur security researcher, I set it up and then did a quick penetration test. The results were concerning enough that I ended up blocking its internet access. Unfortunately, the manual doesn’t list any direct way to poll the data.

A quick online search led me to a bunch of solutions involving configuring uploads to **wunderground.com** or **weathercloud.net**, which I didn’t want to do. So I reversed engineered the product and figured out how to collect the data directly.

---

# Explanation / How
Once the weather station is set up, the manual states there are two pages available:
1. One to configure the WiFi and upload settings.
2. Another to upgrade the firmware.

When viewing the configuration page’s source, I saw it uses two JavaScript files:
- `setting.js`
- `common.js`

`common.js` references a page called `record.html` with a “Live Data” tag. That page doesn’t exist, so I guessed there might be a `record.js` file. Indeed, `record.js` contained several calls, including:

    client?command=record
    client?command=rec_refresh

`record` pulls the entire set of current data values. I believe `rec_refresh` only shows changes, which might be more efficient. I haven’t looked too deeply into it yet, but it’s definitely worth exploring if you want to minimize data transfer or poll more frequently.

# Further Work 
It looks like there are a bunch of weater stations using the same SoC. I suspect you can pull data directly from all of them. Please let me know if it works for you. 
