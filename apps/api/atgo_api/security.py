import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(*, user_id: int, tenant_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tid": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ===== device claim & API key utilities =====

_CLAIM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ambiguity-free


def generate_device_code(length: int = 4) -> str:
    """Marketing-friendly short code, e.g. 'A7K9'."""
    return "".join(secrets.choice(_CLAIM_ALPHABET) for _ in range(length))


def generate_claim_code() -> str:
    """Two groups for legibility: 'A7K9-3F2X'. ~10^12 entropy in 8 chars."""
    return f"{generate_device_code(4)}-{generate_device_code(4)}"


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hash). Show full_key once, store hash."""
    raw = secrets.token_urlsafe(32)
    full = f"atgo_live_{raw}"
    prefix = full[:14]  # 'atgo_live_xxxx'
    digest = hashlib.sha256(full.encode()).hexdigest()
    return full, prefix, digest


def hash_api_key(full: str) -> str:
    return hashlib.sha256(full.encode()).hexdigest()


def generate_device_secret() -> tuple[str, str]:
    """HMAC shared key for ZK device, returns (plain, hash)."""
    plain = secrets.token_urlsafe(24)
    digest = hashlib.sha256(plain.encode()).hexdigest()
    return plain, digest


def verify_hmac_signature(secret: str, message: bytes, signature_hex: str) -> bool:
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex)


def random_token(n: int = 24) -> str:
    return secrets.token_urlsafe(n)


def secure_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def normalize_slug(value: str) -> str:
    s = value.strip().lower()
    allowed = set(string.ascii_lowercase + string.digits + "-")
    return "".join(c for c in s if c in allowed)


def normalize_domain(value: str) -> str | None:
    """Normalize a domain. Reject URLs, paths, and obviously invalid values.

    Returns None when the input is unsalvageable.
    """
    if not value:
        return None
    s = value.strip().lower().rstrip(".")
    if "://" in s or "/" in s or "?" in s or "#" in s or " " in s:
        return None
    if "." not in s:
        return None
    if len(s) > 253:
        return None
    parts = s.split(".")
    if any(not p or len(p) > 63 for p in parts):
        return None
    if any(p.startswith("-") or p.endswith("-") for p in parts):
        return None
    return s
