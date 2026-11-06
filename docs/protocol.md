# VoiceLink wire protocol

A device and Mac share a 64-byte lowercase ASCII hex key established during
pairing. HMAC means HMAC-SHA256 with that ASCII key. Devices and the bridge
use IPv4 UDP and TCP port 42574 on the same local network.

1. The device broadcasts a fresh 16-byte nonce over UDP.
2. The Mac replies with the 32-byte HMAC of ASCII `M` followed by the nonce.
3. After verifying the reply, the device connects to the reply source on
   TCP port 42574 and sends the nonce followed by the HMAC of ASCII `B`
   and the nonce. The bridge matches the nonce against the recent UDP
   request from that IP and answers with ASCII `V` if accepted.
4. Each device packet begins with one byte, then 256 mono PCM samples in
   signed little-endian 16-bit format at 16 kHz. The first byte is zero
   for audio alone or one for audio plus a button event.
5. A button packet appends a 32-byte HMAC of ASCII `V` and the original
   nonce XORed with the zero-based packet counter encoded in 16
   little-endian bytes. The counter increments on every packet.
6. The bridge returns 256 samples in the same PCM format after each
   packet. Close and repeat discovery on connection failure.

The authentication covers discovery and button commands. PCM is
unencrypted. The current bridge serves one paired device at a time.
