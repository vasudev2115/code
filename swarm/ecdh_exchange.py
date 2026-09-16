"""
ECDH Key Exchange -- upgrades secure_comm.py's shared-key AES-GCM to
per-session negotiated keys.

Previously, SecureLink generated one AES key and both "sides" (drone
and ground station) implicitly shared it -- fine for a demo, but not
how you'd do it for real: a shared key baked into both ends means
whoever extracts it from either device reads everything, forever.

ECDH (Elliptic Curve Diffie-Hellman) lets two parties each generate
their own private/public keypair, exchange only the PUBLIC keys, and
independently derive the SAME shared secret -- without ever
transmitting the secret itself. This is real, standard cryptography
(same primitive TLS uses), not a simulated stand-in.

Usage: python ecdh_exchange.py
"""

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os


class ECDHParty:
    """One side of the exchange -- the drone, or the ground station."""

    def __init__(self, name: str):
        self.name = name
        self.private_key = ec.generate_private_key(ec.SECP384R1())
        self.public_key = self.private_key.public_key()
        self.shared_key: bytes | None = None

    def public_bytes(self):
        """What actually gets transmitted -- the public key, never the private one."""
        from cryptography.hazmat.primitives import serialization
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint,
        )

    def derive_shared_key(self, peer_public_bytes: bytes):
        """Independently compute the same shared secret the peer will also derive."""
        peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP384R1(), peer_public_bytes
        )
        shared_secret = self.private_key.exchange(ec.ECDH(), peer_public_key)

        # HKDF turns the raw ECDH secret into a proper AES-256 key --
        # using the raw secret directly as a cipher key is bad practice
        # even though it's the right length; HKDF is the standard step.
        self.shared_key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None,
            info=b"aegisnet-secure-link",
        ).derive(shared_secret)
        return self.shared_key


def perform_exchange(party_a: ECDHParty, party_b: ECDHParty):
    """Simulates transmitting only public keys, each side deriving the same secret."""
    a_public = party_a.public_bytes()
    b_public = party_b.public_bytes()

    key_a = party_a.derive_shared_key(b_public)
    key_b = party_b.derive_shared_key(a_public)

    return key_a, key_b


def encrypt_with_derived_key(key: bytes, plaintext: bytes):
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    return nonce, aesgcm.encrypt(nonce, plaintext, associated_data=None)


def decrypt_with_derived_key(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)


def _self_test():
    drone = ECDHParty("drone")
    ground_station = ECDHParty("ground_station")

    key_drone, key_ground = perform_exchange(drone, ground_station)

    assert key_drone == key_ground, "BUG: ECDH derived different keys on each side"
    print(f"PASS: both sides independently derived the same {len(key_drone)*8}-bit key")

    message = b"telemetry: lat=26.812 lon=80.912 alt=42m"
    nonce, ciphertext = encrypt_with_derived_key(key_drone, message)
    decrypted = decrypt_with_derived_key(key_ground, nonce, ciphertext)

    assert decrypted == message, "BUG: ground station couldn't decrypt with its derived key"
    print(f"PASS: ground station decrypted using its independently-derived key: {decrypted.decode()}")

    # Sanity check: a third party without the private keys can't derive the same secret.
    eavesdropper = ECDHParty("eavesdropper")
    eavesdropper_key = eavesdropper.derive_shared_key(drone.public_bytes())
    assert eavesdropper_key != key_drone, "BUG: eavesdropper derived the real key -- ECDH is broken"
    print("PASS: an eavesdropper with only the public key cannot derive the same shared secret")


if __name__ == "__main__":
    _self_test()
