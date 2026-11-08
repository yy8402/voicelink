#!/bin/bash
set -euo pipefail
umask 077
root="$(cd "$(dirname "$0")" && pwd)"
key="${1:?Usage: ./install.sh PAIRING_KEY [MODIFIER_MASK] [HID_KEY_USAGE]}"
mask="${2:-6}"
usage="${3:-25}"
uid="$(id -u)"
label=org.wifivoicelink
app="$HOME/Applications/Wi-Fi VoiceLink.app"
support="$HOME/Library/Application Support/Wi-Fi VoiceLink"
logs="$HOME/Library/Logs/Wi-Fi VoiceLink"
agent="$HOME/Library/LaunchAgents/$label.bridge.plist"
helper="/Library/PrivilegedHelperTools/$label.button"
daemon_dir=/Library/LaunchDaemons
karabiner='/Library/Application Support/org.pqrs/Karabiner-DriverKit-VirtualHIDDevice/Applications/Karabiner-VirtualHIDDevice-Daemon.app/Contents/MacOS/Karabiner-VirtualHIDDevice-Daemon'
fail() { echo "$*" >&2; exit 1; }
[[ "$uid" != 0 ]] || fail "Run the installer as your logged-in Mac user."
[[ -x "$root/voice-button" && -d "$root/Wi-Fi VoiceLink.app" ]] || fail "Extract the complete release archive first."
[[ ! -e "$app" && ! -e "$support" && ! -e "$agent" && ! -e "$helper" &&
   ! -e "$daemon_dir/$label.karabiner.plist" && ! -e "$daemon_dir/$label.button.plist" ]] ||
   fail "A VoiceLink installation already exists. Uninstall it before reinstalling."
if pgrep -f '[K]arabiner-VirtualHIDDevice-Daemon' >/dev/null ||
   lsof -nP -iTCP:42574 -sTCP:LISTEN >/dev/null ||
   lsof -nP -iUDP:42574 >/dev/null; then
  fail "Stop the existing bridge and Karabiner daemon before installing."
fi
launchctl print "gui/$uid" >/dev/null 2>&1 || fail "Run the installer in your logged-in macOS desktop session."
command -v brew >/dev/null || fail "Install Homebrew first so VoiceLink can install BlackHole."
python3 - "$key" <<'PY'
import re, sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10 or later is required")
from pathlib import Path
if not re.fullmatch(r"[a-f0-9]{64}", Path(sys.argv[1]).read_text().strip()):
    raise SystemExit("Invalid pairing key")
PY
stage="$(mktemp -d)"
started=false
cleanup() {
  local result=$?
  if [[ "$started" == true && "$result" != 0 ]]; then
    "$root/uninstall.sh" || true
  fi
  rm -rf "$stage"
}
trap cleanup EXIT
python3 "$root/jobs.py" "$stage" "$mask" "$usage"
plutil -lint "$stage/"*.plist
sudo -v
driver="$root/Karabiner-DriverKit-VirtualHIDDevice-8.0.0.pkg"
if [[ ! -x "$karabiner" ]]; then
  expected=0d412ea49613b70a981d816461dc3019b84a9659fde0a156939697283a61a7ac
  [[ -f "$driver" && "$(shasum -a 256 <"$driver" | cut -d ' ' -f 1)" = "$expected" ]] ||
    fail "Missing or invalid bundled Karabiner installer."
  sudo installer -pkg "$driver" -target /
fi
extension_enabled() {
  systemextensionsctl list | grep -F 'org.pqrs.Karabiner-DriverKit-VirtualHIDDevice' |
    grep -F '[activated enabled]' >/dev/null
}
if ! extension_enabled; then
  echo "Approve the Karabiner driver in System Settings → General → Login Items & Extensions → Driver Extensions if prompted."
  /Applications/.Karabiner-VirtualHIDDevice-Manager.app/Contents/MacOS/Karabiner-VirtualHIDDevice-Manager activate
  extension_enabled || fail "Enable the Karabiner driver, then rerun this installer."
fi
for channels in 2 16; do
  if [[ ! -d "/Library/Audio/Plug-Ins/HAL/BlackHole${channels}ch.driver" ]]; then
    brew install --cask "blackhole-${channels}ch"
  fi
done
started=true
mkdir -p "$HOME/Applications" "$HOME/Library/LaunchAgents" "$support" "$logs"
ditto "$root/Wi-Fi VoiceLink.app" "$app"
install -m 600 "$key" "$support/pairing.key"
python3 -m venv "$support/venv"
"$support/venv/bin/python" -m pip install -r "$app/Contents/Resources/requirements.txt"
if "$app/Contents/MacOS/VoiceLink" --check-audio; then
  :
else
  result=$?
  if [[ "$result" == 3 ]]; then
    fail "Restart your Mac now to load the BlackHole drivers, then rerun this installer with the same pairing key."
  fi
  fail "Core Audio route validation failed."
fi
sudo install -d -o root -g wheel -m 755 /Library/PrivilegedHelperTools
sudo install -o root -g wheel -m 755 "$root/voice-button" "$helper"
for job in karabiner button; do
  sudo install -o root -g wheel -m 644 "$stage/$label.$job.plist" "$daemon_dir/$label.$job.plist"
  sudo launchctl bootstrap system "$daemon_dir/$label.$job.plist"
done
install -m 644 "$stage/$label.bridge.plist" "$agent"
launchctl bootstrap "gui/$uid" "$agent"
for ((attempt=0; attempt<25; attempt++)); do
  if launchctl print "gui/$uid/$label.bridge" | grep -F 'state = running' >/dev/null &&
     launchctl print "system/$label.karabiner" | grep -F 'state = running' >/dev/null &&
     launchctl print "system/$label.button" | grep -F 'state = running' >/dev/null &&
     lsof -nP -iTCP:42574 -sTCP:LISTEN >/dev/null &&
     hidutil list | grep -F 'Karabiner DriverKit VirtualHIDKeyboard' >/dev/null; then
    echo "Wi-Fi VoiceLink installed and listening. Bridge log: $logs/bridge.log"
    exit 0
  fi
  sleep 1
done
tail -n 20 "$logs/bridge.log" >&2 || true
fail "VoiceLink did not become ready. The installer will remove the incomplete app and jobs."
