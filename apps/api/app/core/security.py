import hashlib
import hmac

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_password_hash = PasswordHash((Argon2Hasher(),))

# Fixed key for length-safe secret comparison (not a credential).
_SECRET_COMPARE_KEY = b"gema.constant-time-secret-compare.v1"


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hash.verify(plain_password, password_hash)


def secrets_equal(provided: str | None, expected: str) -> bool:
    """Constant-time equality that never raises on length mismatch.

    ``hmac.compare_digest`` raises ``ValueError`` when lengths differ, which
    would surface as an unhandled 500 and leak that the candidate length differs.
    Both sides are HMAC'd to a fixed-length digest before comparison.
    """
    if provided is None or expected == "":
        return False
    left = hmac.new(
        _SECRET_COMPARE_KEY, provided.encode("utf-8"), hashlib.sha256
    ).digest()
    right = hmac.new(
        _SECRET_COMPARE_KEY, expected.encode("utf-8"), hashlib.sha256
    ).digest()
    return hmac.compare_digest(left, right)
