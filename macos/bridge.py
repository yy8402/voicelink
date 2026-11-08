#!/usr/bin/env python3
"""Connect a VoiceLink device to macOS audio over Wi-Fi."""

import argparse
from contextlib import ExitStack
import array
from collections import deque
import hmac
from pathlib import Path
import select
import socket
import sys
import time

class BridgeError(Exception):
    pass


class MissingAudioDevice(BridgeError):
    pass


RATE = 16000
PORT = 42574


def receive(connection, size):
    data = bytearray()
    while len(data) < size:
        block = connection.recv(size - len(data))
        if not block:
            raise ConnectionError("device closed the audio connection")
        data.extend(block)
    return data


class PlaybackGain:
    """Limit peaks immediately and recover gain gradually between blocks."""

    def __init__(self, gain):
        self.gain = self.scale = gain

    def apply(self, data):
        samples = array.array("h", data)
        peak = max(map(abs, samples), default=0)
        limit = min(self.gain, 26000 / peak) if peak else self.gain
        start = min(self.scale, limit)
        self.scale = min(limit, start + (self.gain - start) * 0.08)
        step = (self.scale - start) / max(1, len(samples) - 1)
        return array.array("h", (int(sample * (start + i * step))
                                 for i, sample in enumerate(samples))).tobytes()


class AudioBuffer:
    def __init__(self, silence):
        self.blocks = deque(maxlen=12)
        self.silence = silence
        self.buffered = False

    def append(self, block):
        self.blocks.append(block)

    def take(self):
        if not self.buffered:
            self.buffered = len(self.blocks) >= 4
        if self.buffered:
            try:
                return self.blocks.popleft()
            except IndexError:
                self.buffered = False
        return self.silence


def audio_routes(inject_name, capture_name):
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise BridgeError("Install the live audio dependencies from macos/requirements.txt") from exc

    try:
        inject = sd.query_devices(inject_name, "output")
        capture = sd.query_devices(capture_name, "input")
    except ValueError as exc:
        raise MissingAudioDevice(f"Missing Core Audio device: {exc}") from exc
    if inject["index"] == capture["index"]:
        raise BridgeError("Use separate Core Audio devices for the microphone and speaker routes")

    return sd, inject, capture


def check_audio(inject_name, capture_name):
    sd, inject, capture = audio_routes(inject_name, capture_name)
    try:
        sd.check_output_settings(device=inject["index"], channels=2,
                                 dtype="int16", samplerate=RATE)
        sd.check_input_settings(device=capture["index"], channels=1,
                                dtype="int16", samplerate=RATE)
    except sd.PortAudioError as exc:
        raise BridgeError(f"Core Audio routes cannot run at {RATE} Hz: {exc}") from exc
    print(f"Core Audio routes ready: {inject['name']} and {capture['name']}.")


def live_audio(connection, inject_name, capture_name, speaker_gain, button_socket, key, nonce):
    sd, inject, capture = audio_routes(inject_name, capture_name)
    frames = 256
    mono_bytes = frames * 2
    silence = bytes(mono_bytes)
    microphone = AudioBuffer(bytes(frames * 4))
    speaker = AudioBuffer(silence)
    playback_gain = PlaybackGain(speaker_gain)

    def from_codex(data, count, _time, _status):
        if count == frames:
            speaker.append(bytes(data))

    def to_codex(data, count, _time, _status):
        data[:] = microphone.take() if count == frames else bytes(count * 4)

    try:
        with (
            sd.RawInputStream(device=capture["index"], samplerate=RATE, channels=1,
                              dtype="int16", blocksize=frames, callback=from_codex),
            sd.RawOutputStream(device=inject["index"], samplerate=RATE, channels=2,
                               dtype="int16", blocksize=frames, callback=to_codex),
        ):
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connection.sendall(b"V")
            print(f"Live bridge ready. Microphone route: {inject['name']}. "
                  f"Speaker route: {capture['name']}. Ctrl+C to stop.", file=sys.stderr, flush=True)
            frame = 0
            while True:
                packet = receive(connection, mono_bytes + 1)
                if packet[0] == 1:
                    event_nonce = bytes(a ^ b for a, b in zip(nonce, frame.to_bytes(16, "little")))
                    expected = hmac.digest(key, b"V" + event_nonce, "sha256")
                    if not hmac.compare_digest(receive(connection, len(expected)), expected):
                        raise ConnectionError("Invalid device button signature")
                    if button_socket:
                        try:
                            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as button:
                                button.settimeout(0.5)
                                button.connect(str(button_socket))
                                button.sendall(b"V")
                        except OSError as exc:
                            print(f"Voice button unavailable: {exc}", file=sys.stderr, flush=True)
                elif packet[0] != 0:
                    raise ConnectionError("Invalid device audio frame")
                frame += 1
                mono = array.array("h", packet[1:])
                stereo = array.array("h", [0]) * (frames * 2)
                stereo[::2] = stereo[1::2] = mono
                microphone.append(stereo.tobytes())
                connection.sendall(playback_gain.apply(speaker.take()))
    except sd.PortAudioError as exc:
        raise BridgeError(f"Could not open the Core Audio bridge: {exc}") from exc


def serve(args):
    key = args.key_file.read_text().strip().encode("ascii")
    if len(key) != 64:
        raise BridgeError("Invalid pairing key file")
    challenges = {}
    with ExitStack() as resources:
        discovery = resources.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        discovery.bind(("", PORT))
        listener = resources.enter_context(socket.create_server(("", PORT)))
        print("Waiting for paired device over Wi-Fi.", file=sys.stderr, flush=True)
        while True:
            readable, _, _ = select.select([discovery, listener], [], [])
            now = time.monotonic()
            challenges = {peer: (nonce, expiry) for peer, (nonce, expiry) in challenges.items()
                          if expiry > now}
            if discovery in readable:
                nonce, peer = discovery.recvfrom(64)
                if len(nonce) == 16 and len(challenges) < 32:
                    challenges[peer[0]] = nonce, now + 5
                    discovery.sendto(hmac.digest(key, b"M" + nonce, "sha256"), peer)
            if listener in readable:
                connection, peer = listener.accept()
                with connection:
                    connection.settimeout(5)
                    try:
                        nonce, expiry = challenges.pop(peer[0], (None, 0))
                        if nonce is None or expiry < time.monotonic():
                            continue
                        expected = nonce + hmac.digest(key, b"B" + nonce, "sha256")
                        if not hmac.compare_digest(receive(connection, len(expected)), expected):
                            continue
                        live_audio(connection, args.mic_device, args.speaker_device,
                                   args.speaker_gain, args.button_socket, key, nonce)
                    except (ConnectionError, TimeoutError) as exc:
                        print(f"device disconnected ({exc}). Waiting for it to reconnect.",
                              file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, help="Local pairing key file")
    parser.add_argument("--mic-device", default="BlackHole 2ch", help="Core Audio route for the device microphone")
    parser.add_argument("--speaker-device", default="BlackHole 16ch", help="Core Audio route for device playback")
    parser.add_argument("--speaker-gain", type=float, choices=(1, 1.5, 2, 2.5, 3, 4, 5),
                        default=5, help="Live speaker gain multiplier (default: 5)")
    parser.add_argument("--button-socket", type=Path, help="Local shortcut service socket")
    parser.add_argument("--check-audio", action="store_true", help="Verify the selected Core Audio routes")
    args = parser.parse_args()
    try:
        if args.check_audio:
            check_audio(args.mic_device, args.speaker_device)
        elif args.key_file is None:
            parser.error("--key-file is required to start the bridge")
        else:
            serve(args)
    except KeyboardInterrupt:
        print("\nAudio bridge stopped.", file=sys.stderr)
    except MissingAudioDevice as exc:
        print(f"Wi-Fi audio failed: {exc}", file=sys.stderr)
        return 3
    except (OSError, BridgeError) as exc:
        print(f"Wi-Fi audio failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
