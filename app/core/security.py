import base64
import hashlib
import hmac
import os
import secrets

PBKDF2_ALGO = "sha256"
PBKDF2_ITERATIONS = 240_000
SALT_BYTES = 16


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGO,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_{PBKDF2_ALGO}${PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        method, iters, salt_b64, digest_b64 = stored_hash.split("$", 3)
        algo = method.replace("pbkdf2_", "")
        iterations = int(iters)
        salt = _b64d(salt_b64)
        expected = _b64d(digest_b64)
    except Exception:
        return False

    computed = hashlib.pbkdf2_hmac(
        algo,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(computed, expected)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
