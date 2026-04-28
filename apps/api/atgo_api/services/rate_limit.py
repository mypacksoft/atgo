"""Token-bucket rate limiter on Redis.

Used by middleware + ADMS guard to throttle per-IP and per-device.
Quietly degrades to allow-all if Redis is unavailable so the API never
goes down due to ratelimiter loss.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import redis.asyncio as redis_async

from ..config import get_settings

settings = get_settings()

_pool: redis_async.Redis | None = None
# After N consecutive failures we stop trying for a while — otherwise every
# request eats the 5s DNS / connect timeout when Redis is just plain down.
_consecutive_failures = 0
_redis_disabled_until = 0.0
_FAILURE_THRESHOLD = 3
_DISABLE_SECONDS = 60
_REDIS_DISABLED_SCHEMES = {"redis://disabled", "redis://off", "disabled", "off", ""}


def get_redis() -> redis_async.Redis | None:
    global _pool
    # Explicit opt-out for local dev where Redis isn't running.
    if settings.REDIS_URL.lower().rstrip("/") in _REDIS_DISABLED_SCHEMES:
        return None
    if _pool is None:
        _pool = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,   # fail fast, never block requests
            socket_timeout=0.5,
            retry_on_timeout=False,
            health_check_interval=30,
        )
    return _pool


def _circuit_open() -> bool:
    return time.monotonic() < _redis_disabled_until


def _record_failure() -> None:
    global _consecutive_failures, _redis_disabled_until
    _consecutive_failures += 1
    if _consecutive_failures >= _FAILURE_THRESHOLD:
        _redis_disabled_until = time.monotonic() + _DISABLE_SECONDS


def _record_success() -> None:
    global _consecutive_failures
    _consecutive_failures = 0


# Lua: atomic token-bucket. Returns 1 if request allowed, 0 if throttled,
# along with current tokens.
_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- tokens per second
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now
end

-- refill
local delta = math.max(0, now - ts)
tokens = math.min(capacity, tokens + delta * refill_rate)

local allowed = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
end
redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 60)
return {allowed, tokens}
"""


@dataclass
class RateLimitConfig:
    capacity: int
    refill_per_sec: float


# Built-in profiles
PROFILES = {
    # ADMS endpoints — devices push frequently. Per-SN bucket.
    "adms_per_device":   RateLimitConfig(capacity=120, refill_per_sec=2.0),
    # Per source IP for unknown devices.
    "adms_unknown_ip":   RateLimitConfig(capacity=10,  refill_per_sec=0.1),
    # Portal API — per IP, generous.
    "api_per_ip":        RateLimitConfig(capacity=300, refill_per_sec=5.0),
    # Auth endpoints — stricter.
    "auth_per_ip":       RateLimitConfig(capacity=20,  refill_per_sec=0.2),
    # Webhooks: per provider.
    "webhook_per_ip":    RateLimitConfig(capacity=60,  refill_per_sec=1.0),
}


async def take(profile: str, key: str, cost: int = 1) -> tuple[bool, float]:
    """Returns (allowed, tokens_remaining)."""
    cfg = PROFILES.get(profile)
    if not cfg:
        return True, 0.0
    if _circuit_open():
        return True, 0.0
    r = get_redis()
    if r is None:
        return True, 0.0
    try:
        out = await r.eval(_BUCKET_LUA, 1, f"rl:{profile}:{key}",
                           cfg.capacity, cfg.refill_per_sec,
                           int(time.time()), cost)
        _record_success()
        return bool(int(out[0])), float(out[1])
    except Exception:
        _record_failure()
        return True, 0.0


async def is_blocked_ip(ip: str) -> bool:
    """Cheap check via Redis cache; falls back to DB miss."""
    if _circuit_open():
        return False
    r = get_redis()
    if r is None:
        return False
    try:
        result = await r.sismember("blocked_ips", ip)
        _record_success()
        return result
    except Exception:
        _record_failure()
        return False
