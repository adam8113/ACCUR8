#!/usr/bin/env python3
"""Poll a WeatherRouter based station and print the readings as a table.

    python3 poll.py 192.0.2.10
    python3 poll.py 192.0.2.10 --interval 30
    python3 poll.py 192.0.2.10 --once --csv readings.csv
"""

import argparse
import csv
import os
import sys
import time

import requests
from tabulate import tabulate


def fetch(url):
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def rows(data):
    table = []
    for group in data.get('sensor', []):
        table.append([group.get('title', ''), '', ''])
        for item in group.get('list', []):
            unit = item[2] if len(item) > 2 else ''
            table.append(['  ' + item[0], item[1], unit])
    battery = data.get('battery')
    if battery:
        table.append([battery.get('title', 'Battery'), '', ''])
        for line in battery.get('list', []):
            table.append(['  ' + line, '', ''])
    return table


def flat(data):
    """Return {"Outdoor Temperature (°C)": "9.9", ...} for a CSV row."""
    row = {}
    for group in data.get('sensor', []):
        for item in group.get('list', []):
            unit = item[2] if len(item) > 2 else ''
            key = '%s %s' % (group.get('title', ''), item[0])
            if unit:
                key += ' (%s)' % unit
            row[key] = item[1]
    return row


def append_csv(path, data):
    row = {'time': time.strftime('%Y-%m-%d %H:%M:%S')}
    row.update(flat(data))
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('host', help='station IP address or hostname')
    parser.add_argument('--interval', type=int, default=10, help='seconds between polls (default 10)')
    parser.add_argument('--once', action='store_true', help='print one reading and exit')
    parser.add_argument('--csv', metavar='FILE', help='append each reading as a row to this CSV file')
    args = parser.parse_args()

    url = 'http://%s/client?command=record' % args.host
    while True:
        try:
            data = fetch(url)
            print('\n' + time.strftime('%Y-%m-%d %H:%M:%S'))
            print(tabulate(rows(data), headers=['Sensor', 'Value', 'Unit'], tablefmt='github'))
            if args.csv:
                append_csv(args.csv, data)
        except requests.RequestException as e:
            print('error: %s' % e, file=sys.stderr)
        if args.once:
            return
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return


if __name__ == '__main__':
    main()
