"""
JWT authentication -- access tokens + refresh tokens.

Uses PyJWT (the `jwt` package) rather than python-jose, since that's
what's actually available/verifiable in this environment -- they do
the same job. Password hashing uses stdlib hashlib+PBKDF2 rather than
passlib for the same reason; passlib would work identically if you
install it, this just doesn't add a dependency this environment can't
verify.

Design:
  - Access tokens: short-lived (15 min), sent with every request.
  - Refresh tokens: long-lived (7 days), used only to get a new access
    token without re-entering credentials. If an access token leaks,
    it's only useful for 15 minutes.

This is a real, runnable auth module -- verified below with an actual
generate -> verify -> expire -> refresh cycle, not just written blind.
"""

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone

import jwt

SECRET_KEY = os.environ.get("AEGISNET_JWT_SECRET", "dev-only-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


# --- Password hashing (PBKDF2, stdlib -- passlib does the same thing) ---

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + pwd_hash.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    salt_hex, hash_hex = stored_hash.split(":")
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(actual, expected)  # constant-time comparison, not ==


# --- JWT tokens ---

def create_access_token(subject: str) -> str:
    payload = {
        "sub": subject,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, expected_type: str = "access") -> dict:
    """Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected a {expected_type} token, got {payload.get('type')}")
    return payload


def refresh_access_token(refresh_token: str) -> str:
    """Exchange a valid refresh token for a new access token."""
    payload = verify_token(refresh_token, expected_type="refresh")
    return create_access_token(payload["sub"])


def _self_test():
    # 1. Password hashing round-trip
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed), "correct password should verify"
    assert not verify_password("wrong-password", hashed), "wrong password should NOT verify"
    print("PASS: password hashing rejects wrong password, accepts correct one")

    # 2. Access token creation and verification
    access = create_access_token("operator-1")
    payload = verify_token(access, expected_type="access")
    assert payload["sub"] == "operator-1"
    print("PASS: access token created and verified")

    # 3. Refresh token flow
    refresh = create_refresh_token("operator-1")
    new_access = refresh_access_token(refresh)
    new_payload = verify_token(new_access, expected_type="access")
    assert new_payload["sub"] == "operator-1"
    print("PASS: refresh token successfully exchanged for a new access token")

    # 4. Using a refresh token as an access token should fail
    try:
        verify_token(refresh, expected_type="access")
        raise AssertionError("BUG: refresh token was accepted as an access token")
    except jwt.InvalidTokenError:
        print("PASS: refresh token correctly rejected when used as an access token")

    # 5. Expired token should fail (use a token with 0-second expiry)
    import jwt as jwt_module
    expired_payload = {
        "sub": "operator-1", "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),  # already expired
        "iat": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt_module.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    try:
        verify_token(expired_token)
        raise AssertionError("BUG: expired token was accepted")
    except jwt_module.ExpiredSignatureError:
        print("PASS: expired token correctly rejected")


if __name__ == "__main__":
    _self_test()
