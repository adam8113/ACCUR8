# Firmware teardown

I did a quick pen test on this station when I set it up, didn't like what I found, and blocked it off the internet. This is the longer look. I pulled apart the vendor's firmware download for the WiFi module to see what it actually does, because the manual only covers a fraction of it.

I only ever read from my own unit while working this out. I didn't flash anything and I didn't POST anything to the device. You can reproduce all of it from the firmware file and the pages the station already serves.

## The image

The WiFi module is an ESP8266. The console is a separate chip, and the two talk over a serial line, which I get to further down. The box says ACCUR8 but the firmware calls itself WeatherRouter, and the same SoC turns up under other brands, so a lot of this probably holds for stations that aren't a DWS5100 at all.

| Property | Value |
|---|---|
| Chip | ESP8266 (Xtensa LX106) |
| SDK | Espressif Non-OS SDK 2.0.0 |
| Firmware string | V1.2.5 |
| Image size | 414244 bytes |
| SHA-256 | 4428c264032ae35aa36433f4b75b9cb068d87104ec2f4c06a32519d9292f5255 |
| Transport | HTTP/1.0, cleartext |

If you want to load it into Ghidra or radare2, the segments sit like this: irom0 code and rodata at vaddr 0x40200000 plus the file offset (so file 0x8 is 0x40200008), IRAM at 0x40100000, and two DRAM blocks at 0x3ffe8000 and 0x3ffe87f0. Entry point is 0x40100004, flash 2MB, QIO, 40MHz, and the image checksum is valid. Ghidra wants the Xtensa LX106 processor module, or use radare2 with `-a xtensa`. The four upload URLs come out as clean strings and make good anchors for checking your load base is right.

## Every network endpoint

The module answers on port 80 and nothing else. Everything it serves lives under `/config?command=` or `/client?command=`, and the only things it calls out to are five fixed hosts.

| Endpoint | Direction | Purpose |
|---|---|---|
| `/config?command=setup` | serves | GET reads, POST writes WiFi, per server upload creds, NTP and timezone |
| `/config?command=unit` | serves | display unit selection |
| `/config?command=calibrate` | serves | sensor offsets and gains, rain counters (forwarded to the console) |
| `/config?command=firmware` | serves | GET version, POST is an OTA flash |
| `/config?command=debug` | serves | status dump, POST toggles a model check flag |
| `/config?command=register` | serves | pair or unpair a sensor transmitter |
| `/config?command=scan_ap` | serves | trigger a WiFi scan, return the AP list |
| `/config?command=connect_status` | serves | station status, IP, RSSI |
| `/config?command=close_apmode` | serves | drop the SoftAP setup network |
| `/client?command=record` | serves | live sensor JSON |
| `/client?command=rec_refresh` | serves | changed values only |
| `rtupdate.wunderground.com` | calls | Wunderground RapidFire upload |
| `api.ambientweather.net` | calls | Ambient Weather upload |
| `api.weathercloud.net` | calls | Weathercloud upload |
| `extrakold.tk` | calls | a fourth uploader the settings page hides |
| `time.windows.com` | calls | SNTP clock sync |

Nothing else phones home. No analytics, no update check. The only entry there I didn't expect was the fourth uploader.

## The hidden fourth uploader

The settings page shows three upload services. The firmware has four. The web UI builds its list from four entries and flags the first one so the page skips drawing it, so you never see it, but the upload code behind it is complete and works.

Turn it on and it sends a request like this over plain HTTP:

    GET /v10/set?ID=<account>&PASSWORD=<password>&ver=0.6&type=491&dateutc=...&
        absbaro=..&relbaro=..&outtemp=..&outhumi=..&wind=..&wdir=..&raintotal=..
    Host: extrakold.tk

The host `extrakold.tk` is hard coded. There's no field in the config to change it, the firmware picks the host by server index and resolves the name over DNS at upload time. It reads like the vendor's old cloud (extrakold looks like an earlier brand of theirs), and they've let the domain lapse. It comes back NXDOMAIN now.

Two things about that. This uploader is off by default and hidden, so a normal station sends nothing to it, and with the domain dead it wouldn't reach anything even if it were on. So this isn't data leaking in the wild. What it is, is a dead dependency baked into the firmware: there's no TLS and no certificate check, so if that name ever resolved again (a lapsed `.tk` can in principle be re-registered) any unit that happened to have the uploader enabled would post its readings and its upload password in the clear to whoever owned the name. It's a latent problem, not an active one.

There's an upside to the same design if it's your own station. Point `extrakold.tk` at a box on your own LAN in your local DNS, switch the hidden server on, and the station will push a full reading to you about once a minute with no cloud in the way. That's the one practical use I found for it.

## config command map

There's a single dispatcher that looks at the method, the path and the `command=` value, then jumps to a handler. Eleven commands in total, and no hidden factory or reset verb hiding among them, the UI names every one the firmware answers.

| Command | Method | Body or params | What it does |
|---|---|---|---|
| setup | GET POST | `{router, weather[], time}` | read or write WiFi, upload creds and enable flags, NTP and timezone |
| unit | GET POST | `[Unit, idx...]` | display unit selection |
| calibrate | GET POST | `{id<N>: value, ...}` | sensor offsets and gains, rain counters |
| firmware | GET POST | multipart .bin | version, or OTA flash |
| debug | GET POST | `{"Feature": bool}` | status dump, or toggle the model check flag |
| register | POST | `{"Register": "<id>"}` | pair or unpair a sensor transmitter |
| scan_ap | GET | none | WiFi scan, returns AP list |
| connect_status | GET | none | station status, IP, RSSI |
| close_apmode | POST | none | close SoftAP setup mode |
| record | GET | none | live sensor JSON |
| rec_refresh | GET | none | changed values only |

The one worth knowing about is `debug`. A GET gives you the model name, the last upload result and time for each service, the connection count, uptime, the clock sync countdown and a regional option block. The per service result is a quick way to see whether your uploads are actually landing.

## Calibration

The firmware carries the usual calibration knobs: a temperature and humidity offset per sensor, an absolute and relative pressure offset, a wind speed gain, a wind direction offset, a solar gain, a rainfall gain, and the six rain counters (hour, day, week, month, year, total).

Reading the image is one thing, but on my actual DWS5100 the calibrate command comes back empty. On this model the offsets and gains live on the console and you set them with the buttons, not over the network, so that wind direction offset exists in the firmware but you can't reach it over HTTP here. If your array is pointing the wrong way, the fix is to go and turn it, not to send a request. The rain counters are the exception. They show up as editable fields on the live data page (ids 43 to 48) and get written back through calibrate, with a rule that hour can't be greater than day, day can't be greater than month, and so on up to total.

## Console link

The WiFi module isn't the sensor. It reads the console over a serial line at 9600 baud (the code can auto detect from 4800 up to 115200). The frames are a sync byte, a length, an opcode, the data, and a checksum that's the payload summed with a constant. Register turns into an opcode 0x96 frame with the sensor id in it, and sensor values come back the other way, which is what you read as JSON from `/client?command=record`. There's no way to send an arbitrary opcode over the network, so from the LAN you can read every value and run the commands the web UI runs, but you can't inject a raw frame or fake a reading.

## Odds and ends

A few things that aren't in the manual or the settings page.

Port 80 also answers a third kind of request line beside GET and POST, a raw one that starts `CMD /TCP/1.0`, handled by its own task. After the request line the frame is the same shape as the console link above, with the checksum being the opcode plus the length plus the sum of the data. The dispatcher switches on the opcode and handles twelve of them, 0x0d to 0x18. Like the rest of the module it checks no password or key at all, and it answers in normal STA mode on the same port you already poll, so it looks like the phone app's live-data and control channel. What I could not settle from the image is which opcodes read and which write. The twelve handlers are pure binary with no strings to anchor them, so I can only guess (0x0f looks like a bulk sensor read, 0x14 like a setter) and neither is proven. The handlers build console-format frames but send them back over the socket, and I could not trace a path from this channel to the serial transmit function, so there is no confirmed way to push an arbitrary console command through it. Pinning the read and write split down properly needs dynamic work, capturing the vendor app against a unit or stepping opcodes one at a time on an isolated station. Until someone does that I would not send it anything, a bare connect to the open port is the only safe thing to do.

There are more static pages baked in than the menu shows. `debug.html` isn't linked anywhere but loads straight from the root and gives the same status block as the debug command. The page set depends on the build though. `calibrate.html` 404s on mine even though the firmware mentions it, so don't assume every page named in the image ships on your model.

The firmware handles solar radiation, a light reading and a solar gain, and a model with a light sensor returns them in the record JSON. A plain 5-in-1 doesn't have that sensor. Mine returns only Indoor, Outdoor, Pressure, Wind Speed and Rainfall, with no solar or light or UV anywhere, so that's a capability of the chip rather than something a 5-in-1 will give you. Check your own record output before you count on it.

The rest is minor. The boot path has strings for a factory self test image ("reboot to use test bin", "restart to use user bin"). There's a dormant SPI path to the console next to the serial one, unused. A build flag (`client = 'sai'`) picks the normal UI, an `'amb'` variant swaps the settings screen for an Ambient Weather registration page. And the SoftAP setup network is named WeatherHome- plus the last three bytes of the MAC.

## Security

None of the endpoints check anything. There's no password, no token, no session, and no auth related code or strings anywhere in the image. So anything the module can do, anyone who can reach it on the network can do too.

The two that matter. `POST /config?command=firmware` writes an uploaded image to flash, and the only check is that it looks like a valid image, which is an integrity check and not a signature, so anyone on the network can flash whatever they want onto it. And the setup POST rewrites the WiFi credentials and every upload account, hidden server included, since the hiding is only done in the browser. On top of that everything is cleartext HTTP, upload passwords and all, sitting in the query string of each upload.

There's no hard coded password or bypass parameter, so this isn't a planted backdoor, it's just that nothing is locked. It also isn't exploitable from outside on its own, the device exposes nothing to the internet unless you forward a port to it. But anyone already on your network owns it, and can reflash it, which is reason enough to keep it on a segment you trust and off the internet. That's where mine lives.

## How I did it

I used `esptool image-info` for the header and segments, `strings` for a first pass with the known upload URLs to fix the load base, and Ghidra with the Xtensa LX106 module (radare2 with `-a xtensa` also works) for the dispatcher, the upload builders and the frame code. The station's own `setting.js`, `common.js` and `record.js` cover the UI side and the server list. Then read only GETs to my own unit to check the behaviour matched.

The endpoint map, the hidden uploader, the missing auth and the empty calibrate response I confirmed against a running station. The lower level details, the serial checksum constant and the exact upload timing, come from the disassembly, and I've said so above where a claim rests on reading the image rather than testing it.
