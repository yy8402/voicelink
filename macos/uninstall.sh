#!/bin/bash
set -euo pipefail
uid="$(id -u)"
[[ "$uid" != 0 ]] || { echo "Run as your Mac user." >&2; exit 1; }
label=org.wifivoicelink
sudo -v
launchctl bootout "gui/$uid/$label.bridge" 2>/dev/null || true
for job in button karabiner; do
  sudo launchctl bootout "system/$label.$job" 2>/dev/null || true
  sudo rm -f "/Library/LaunchDaemons/$label.$job.plist"
done
sudo rm -f "/Library/PrivilegedHelperTools/$label.button"
rm -f "$HOME/Library/LaunchAgents/$label.bridge.plist"
rm -rf "$HOME/Applications/Wi-Fi VoiceLink.app" \
       "$HOME/Library/Application Support/Wi-Fi VoiceLink"
echo "Wi-Fi VoiceLink removed. Original pairing file, logs and system extension are retained."
