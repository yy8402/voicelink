#!/usr/bin/env python3
"""Pair NOTE4C firmware 1.11.0 over its USB setup port."""

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
    args = parser.parse_args()
    try:
        key = args.key_file.read_text().strip()
    except FileNotFoundError:
        key = secrets.token_hex(32)
        fd = os.open(args.key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(key + "\n")
    if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
        parser.error("Invalid pairing key")
    request = dict(id=1, cmd="wifi_pair", ssid=args.ssid,
                   password=getpass("Wi-Fi password: "), key=key)
    with Serial(args.port, 115200, timeout=0.25, write_timeout=4) as port:
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
                    print("Device paired.")
                    return 0
                print(reply.get("error", "Pairing failed"), file=sys.stderr)
                return 1
    print("Device did not acknowledge pairing.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
