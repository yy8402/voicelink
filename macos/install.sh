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
[[ -x "$karabiner" ]] || fail "Install and enable Karabiner VirtualHIDDevice 8.0.0 first."
systemextensionsctl list | grep -F 'org.pqrs.Karabiner-DriverKit-VirtualHIDDevice' |
  grep -Fq '[activated enabled]' || fail "Enable the Karabiner system extension first."
[[ -x "$root/voice-button" && -d "$root/Wi-Fi VoiceLink.app" ]] || fail "Extract the complete release archive first."
[[ ! -e "$app" && ! -e "$support" && ! -e "$agent" && ! -e "$helper" &&
   ! -e "$daemon_dir/$label.karabiner.plist" && ! -e "$daemon_dir/$label.button.plist" ]] ||
   fail "A VoiceLink installation already exists. Uninstall it before reinstalling."
if pgrep -f '[K]arabiner-VirtualHIDDevice-Daemon' >/dev/null ||
   lsof -nP -iTCP:42574 -sTCP:LISTEN >/dev/null ||
   lsof -nP -iUDP:42574 >/dev/null; then
  fail "Stop the existing bridge and Karabiner daemon before installing."
fi
python3 - "$key" <<'PY'
import re, sys
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
started=true
mkdir -p "$HOME/Applications" "$HOME/Library/LaunchAgents" "$support" "$logs"
ditto "$root/Wi-Fi VoiceLink.app" "$app"
install -m 600 "$key" "$support/pairing.key"
python3 -m venv "$support/venv"
"$support/venv/bin/python" -m pip install -r "$app/Contents/Resources/requirements.txt"
sudo install -d -o root -g wheel -m 755 /Library/PrivilegedHelperTools
sudo install -o root -g wheel -m 755 "$root/voice-button" "$helper"
for job in karabiner button; do
  sudo install -o root -g wheel -m 644 "$stage/$label.$job.plist" "$daemon_dir/$label.$job.plist"
  sudo launchctl bootstrap system "$daemon_dir/$label.$job.plist"
done
install -m 644 "$stage/$label.bridge.plist" "$agent"
launchctl bootstrap "gui/$uid" "$agent"
echo "Wi-Fi VoiceLink installed. Bridge log: $logs/bridge.log"
