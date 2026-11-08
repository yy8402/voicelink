#!/usr/bin/env python3
"""Pair a NOTE4C or change its Wi-Fi settings over USB."""

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import sys
import time

from serial import Serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--ssid", required=True)
    parser.add_argument("--key-file", type=Path, default=Path.home() / ".note4c-wifi.key")
    parser.add_argument("--reconfigure", action="store_true",
                        help="Change Wi-Fi without replacing the pairing key (firmware 1.12.0+)")
    args = parser.parse_args()
    request = dict(id=1, cmd="wifi_config" if args.reconfigure else "wifi_pair",
                   ssid=args.ssid, password=getpass("Wi-Fi password: "))
    if not args.reconfigure:
        request["key"] = load_key(args.key_file)
    return send_request(args.port, request)


def load_key(path):
    try:
        key = path.read_text().strip()
    except FileNotFoundError:
        key = secrets.token_hex(32)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(key + "\n")
    if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
        raise SystemExit("Invalid pairing key")
    return key


def send_request(port_name, request):
    with Serial(port=None, baudrate=115200, timeout=0.25, write_timeout=4) as port:
        port.dtr = port.rts = False
        port.port = port_name
        port.open()
        port.write((json.dumps(request) + "\n").encode())
        end = time.monotonic() + 5
        while time.monotonic() < end:
            line = port.readline()
            try:
                reply = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(reply, dict) and reply.get("id") == 1:
                if reply.get("ok"):
                    if request["cmd"] == "wifi_config":
                        print("Wi-Fi settings saved. Restart the NOTE4C to apply them.")
                    else:
                        print("Device paired.")
                    return 0
                print(reply.get("error", "Pairing failed"), file=sys.stderr)
                return 1
    print("Device did not acknowledge pairing.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
