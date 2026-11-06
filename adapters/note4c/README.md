# NOTE4C reference adapter

ZecTrix NOTE4C timer firmware 1.11.0 already implements the VoiceLink
protocol. Keep that firmware installed to retain the timer, stored runs,
and activity list. A short front-button press controls the timer. A long
press sends a signed Voice event while the audio bridge is connected.

For a board already paired with that firmware, pass its existing
`~/.note4c-wifi.key` to the Mac installer. For an unpaired board, connect
the USB data cable once and run:

```sh
python3 -m venv .venv
.venv/bin/pip install -r adapters/note4c/requirements.txt
.venv/bin/python adapters/note4c/pair.py --port /dev/cu.usbmodem1234561 --ssid "YOUR NETWORK"
```

Use the port shown by macOS. The pairing tool prompts for the Wi-Fi
password and writes the shared key to a private local file. Disconnect
USB after the board connects to the bridge.

The ESP-IDF transport source in this directory is the reference from
firmware 1.11.0. It relies on a board's `audio.h` implementation of
`audio::stream`, and on the host firmware to initialize NVS, expose
`wifi_pair` during provisioning, and call `wifi_audio::voice_button()`
on a hold. It does not contain the ZecTrix timer, activity storage, or
display logic.
