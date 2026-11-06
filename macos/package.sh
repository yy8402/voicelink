#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
sdk="${1:?Pass the path to a Karabiner VirtualHIDDevice v8.0.0 source checkout}"
[[ "$(git -C "$sdk" rev-parse HEAD)" = ba649ef9cbbdc453cc384838496ef03eab3e3c87 ]] ||
  { echo "Expected the v8.0.0 Karabiner SDK." >&2; exit 1; }
mkdir -p "$root/dist"
stage="$(mktemp -d "$root/dist/.package.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
app="$stage/Wi-Fi VoiceLink.app"
mkdir -p "$app/Contents/"{MacOS,Resources}
cp "$root/macos/Info.plist" "$app/Contents/"
install -m 755 "$root/macos/VoiceLink" "$app/Contents/MacOS/"
cp "$root/macos/"{bridge.py,requirements.txt} "$app/Contents/Resources/"
clang++ -std=c++23 -O2 -Wall -Wextra -I "$sdk/include" -isystem "$sdk/vendor/vendor/include" \
  -framework IOKit -framework CoreFoundation "$root/macos/voice_button.cpp" -o "$stage/voice-button"
codesign --force --sign - --identifier org.wifivoicelink.button "$stage/voice-button"
codesign --force --sign - "$app"
cp "$root/macos/"{install.sh,uninstall.sh,jobs.py} "$stage/"
cp "$root/"{README.md,THIRD_PARTY_NOTICES.md} "$stage/"
/usr/bin/ditto -c -k "$stage" "$stage.zip"
mv "$stage.zip" "$root/dist/wifi-voicelink-macos.zip"
