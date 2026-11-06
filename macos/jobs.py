"""Generate launchd jobs for a single Mac account."""
import argparse
import os
from pathlib import Path
import plistlib

LABEL = "org.wifivoicelink"
SOCKET = "/var/run/wifi-voicelink.sock"
DAEMON = ("/Library/Application Support/org.pqrs/Karabiner-DriverKit-VirtualHIDDevice/"
          "Applications/Karabiner-VirtualHIDDevice-Daemon.app/Contents/MacOS/"
          "Karabiner-VirtualHIDDevice-Daemon")
HELPER = "/Library/PrivilegedHelperTools/org.wifivoicelink.button"


def write_jobs(destination, home, uid, mask, usage):
    app = home / "Applications/Wi-Fi VoiceLink.app"
    support = home / "Library/Application Support/Wi-Fi VoiceLink"
    logs = home / "Library/Logs/Wi-Fi VoiceLink"
    jobs = {
        "karabiner": dict(ProgramArguments=[DAEMON], ProcessType="Interactive"),
        "button": dict(ProgramArguments=[HELPER, str(uid), str(mask), str(usage)],
                       ProcessType="Interactive", Sockets={"Button": {
                           "SockPathName": SOCKET, "SockPathMode": 0o666}}),
        "bridge": dict(ProgramArguments=[
            str(app / "Contents/MacOS/VoiceLink"), "--key-file",
            str(support / "pairing.key"), "--button-socket", SOCKET],
            StandardOutPath=str(logs / "bridge.log"),
            StandardErrorPath=str(logs / "bridge.log"),
            LimitLoadToSessionType="Aqua"),
    }
    for suffix, job in jobs.items():
        label = f"{LABEL}.{suffix}"
        job.update(Label=label, RunAtLoad=True, KeepAlive=True, ThrottleInterval=10,
                   AssociatedBundleIdentifiers=f"{LABEL}.bridge")
        (destination / f"{label}.plist").write_bytes(plistlib.dumps(job))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("modifier_mask", type=int, choices=range(256), metavar="MODIFIERS")
    parser.add_argument("key_usage", type=int, choices=range(4, 232), metavar="KEY")
    args = parser.parse_args()
    write_jobs(args.destination, Path.home(), os.getuid(), args.modifier_mask, args.key_usage)
