"""
Secure Communication + Simulated Anti-Jamming.

1. Encryption is REAL: AES-GCM via the `cryptography` library.
2. Frequency hopping is SIMULATED decision logic -- real anti-jamming
   needs SDR/RF hardware this project doesn't have. Keep that
   distinction clear if asked about it directly.

Usage: python secure_comm.py
"""
import os
import random
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CHANNELS = [2412, 2417, 2422, 2427, 2432, 2437, 2442]
JAM_DETECTION_CHANCE = 0.15


class SecureLink:
    def __init__(self):
        self.key = AESGCM.generate_key(bit_length=256)
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: bytes):
        nonce = os.urandom(12)
        return nonce, self.aesgcm.encrypt(nonce, plaintext, associated_data=None)

    def decrypt(self, nonce: bytes, ciphertext: bytes) -> bytes:
        return self.aesgcm.decrypt(nonce, ciphertext, associated_data=None)


class FrequencyHopper:
    def __init__(self):
        self.current_channel = random.choice(CHANNELS)

    def check_and_hop(self) -> bool:
        if random.random() < JAM_DETECTION_CHANCE:
            old = self.current_channel
            self.current_channel = random.choice([c for c in CHANNELS if c != old])
            print(f"!! Interference detected on {old}MHz -- hopped to {self.current_channel}MHz")
            return True
        return False


if __name__ == "__main__":
    link = SecureLink()
    hopper = FrequencyHopper()
    for i in range(6):
        hopper.check_and_hop()
        message = f"telemetry packet #{i}".encode()
        nonce, ciphertext = link.encrypt(message)
        print(f"[ch={hopper.current_channel}MHz] sent {len(ciphertext)} encrypted bytes")
        decrypted = link.decrypt(nonce, ciphertext)
        assert decrypted == message
        time.sleep(0.3)
    print("-- All messages sent and verified over simulated secure link")
