#!/usr/bin/env python3

# A sample python script which pulls the local data every 10 seconds and displays it in a table. 
# Don't forget to update IPADDRESS to yours below

import time
import requests
from tabulate import tabulate

STATION_URL = "http://IPADDRESS/client?command=record"
POLL_INTERVAL = 10  # interval in seconds

def main():
    while True:
        try:
            response = requests.get(STATION_URL, timeout=5)
            data = response.json()
            
            table = []
            
            if "sensor" in data:
                for sensor_group in data["sensor"]:
                    # Header
                    table.append([f"--- {sensor_group['title']} ---", "", ""])
                    
                    for item in sensor_group["list"]:
                        name = item[0]
                        value = item[1]
                        unit = item[2] if len(item) > 2 else ""
                        table.append([name, value, unit])

            # Battery
            if "battery" in data:
                battery_info = data["battery"]
                table.append([f"--- {battery_info.get('title', 'Battery')} ---", "", ""])
                for line in battery_info.get("list", []):
                    table.append([line, "", ""])

            # Time
            print("\n" + time.strftime("%Y-%m-%d %H:%M:%S"), "Live Data\n")

            print(tabulate(table, headers=["Sensor / Title", "Value", "Unit"], tablefmt="github"))

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nExiting on user interrupt.")
            break
        except Exception as e:
            print(f"\nError occurred: {e}\nRetrying in {POLL_INTERVAL} seconds...")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
