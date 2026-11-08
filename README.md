# Wi-Fi VoiceLink

Use a Wi-Fi device as a Mac microphone and speaker, with a button that invokes
an app shortcut. The project is independent of a specific board or chat app.
The first tested device is NOTE4C with ZecTrix firmware 1.12.0. The first tested
app is Codex Voice.

The two BlackHole routes make the audio available to Core Audio apps. Choose
the routes in the app when it offers device selection, or set the macOS sound
defaults. The button sends the keyboard chord configured at install time.
An app needs its own working shortcut for the action you want. Codex
start/stop has been verified with Option–Shift–V. ChatGPT Voice outside Codex
and other apps still need end-to-end testing.

## macOS background package

Use macOS 13 or later, Python 3.10 or later, and Homebrew. The archive
includes the original signed Karabiner VirtualHIDDevice 8.0.0 installer.
The setup command installs it if needed and installs missing BlackHole
2ch and 16ch drivers through Homebrew. Leave an existing manual bridge
and Karabiner daemon stopped during setup.

Extract `wifi-voicelink-macos.zip`. From Terminal in the extracted directory,
run this as your Mac user. Reuse the existing key for an already paired
NOTE4C.

```sh
./install.sh "$HOME/.note4c-wifi.key"
```

Enter your Mac administrator password in Terminal when prompted. If macOS
asks for driver approval, enable Karabiner under System Settings → General →
Login Items & Extensions → Driver Extensions. If the installer exits while
waiting for approval, enable it and run the same command again. If BlackHole is installed but either audio route is missing, the installer
asks you to restart the Mac. Restart before rerunning the same command with
your existing pairing key.

The installer checks both audio routes and waits for the bridge and virtual
keyboard to start. It rolls back an incomplete VoiceLink app and its jobs.
Driver installations are retained for a retry. The bridge runs under your
login account, with separate system jobs for Karabiner and the button. No
Terminal windows are needed after installation. The VoiceLink app and
helper are locally signed for development.

For Codex, set BlackHole 2ch as input and BlackHole 16ch as output in
macOS Sound settings, or select the devices in the app if available. In
Codex Settings → Voice, open the Voice chat hotkey recorder and hold the
NOTE4C front button to register Option–Shift–V from the virtual keyboard.
Then test a short timer press and two long presses to start and end Voice. To choose a different chord at
installation, pass the USB HID modifier mask and key usage in decimal.
The default is mask `6` and usage `25` for Option–Shift–V.

```sh
./install.sh /path/to/pairing.key 6 25
```

The login agent uses 5× nominal reply gain with peak limiting. To see its
connection status, open the log. To remove the app and launch jobs, run the
uninstaller from the extracted directory. It retains the drivers and the
original pairing file.

```sh
tail -f "$HOME/Library/Logs/Wi-Fi VoiceLink/bridge.log"
./uninstall.sh
```

## Build the local package

Clone the Karabiner VirtualHIDDevice source at tag `v8.0.0`, including its
vendored headers, and download the original signed installer from the
[v8.0.0 release](https://github.com/pqrs-org/Karabiner-DriverKit-VirtualHIDDevice/releases/tag/v8.0.0).
Then run:

```sh
./macos/package.sh /path/to/Karabiner-DriverKit-VirtualHIDDevice \
  /path/to/Karabiner-DriverKit-VirtualHIDDevice-8.0.0.pkg
```

The result is `dist/wifi-voicelink-macos.zip` for the architecture used to
build it. The [NOTE4C adapter](adapters/note4c/README.md) explains how to pair
that board. Other devices can implement the [wire protocol](docs/protocol.md).

## Process boundaries

The bridge handles networking and audio as the logged-in user. The
privileged helper accepts one fixed command over a Unix socket, checks the
peer's user ID, and sends only the chord set in its root-owned launch job.
The Wi-Fi device cannot provide arbitrary keyboard events. Audio is
unencrypted on the local network. Use a trusted LAN.
