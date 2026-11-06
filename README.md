# Wi-Fi VoiceLink

Use a Wi-Fi device as a Mac microphone and speaker, with a button that invokes
an app shortcut. The project is independent of a specific board or chat app.
The first tested device is NOTE4C with ZecTrix firmware 1.11.0. The first tested
app is Codex Voice.

The two BlackHole routes make the audio available to Core Audio apps. Choose
the routes in the app when it offers device selection, or set the macOS sound
defaults. The button sends the keyboard chord configured at install time.
An app needs its own working shortcut for the action you want. Codex
start/stop has been verified with Option–Shift–V. ChatGPT Voice outside Codex
and other apps still need end-to-end testing.

## macOS background package

Requirements are macOS 13 or later, Python 3.10 or later, BlackHole 2ch and
16ch, and the enabled Karabiner VirtualHIDDevice 8.0.0 extension. The install
script uses Homebrew or system-installed Python; the installer does not
bundle Python, BlackHole, or Karabiner.

Extract `wifi-voicelink-macos.zip`. Stop any manually running VoiceLink bridge
and Karabiner daemon, then run this from the extracted directory as your Mac
user. Use the existing pairing file if the device has already been paired.

```sh
./install.sh "$HOME/.note4c-wifi.key"
```

The installer requests administrator approval for the system services. It
starts the bridge under your login account and installs the two privileged
jobs for Karabiner and the button. At subsequent logins, no Terminal windows
are needed. The package is locally signed for development; it is not a
notarized release.

For Codex, select BlackHole 2ch as input and BlackHole 16ch as output, then
set the Voice hotkey to Option–Shift–V. To choose a different chord at
installation, pass the USB HID modifier mask and key usage in decimal.
The default is mask `6` and usage `25` for Option–Shift–V.

```sh
./install.sh /path/to/pairing.key 6 25
```

The login agent uses 5× nominal reply gain with peak limiting. To see its
connection status, open the log. To remove the app and launch jobs, run the
uninstaller from the extracted directory.

```sh
tail -f "$HOME/Library/Logs/Wi-Fi VoiceLink/bridge.log"
./uninstall.sh
```

## Build the local package

Clone the Karabiner VirtualHIDDevice source at tag `v8.0.0`, including its
vendored headers, then run:

```sh
./macos/package.sh /path/to/Karabiner-DriverKit-VirtualHIDDevice
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
