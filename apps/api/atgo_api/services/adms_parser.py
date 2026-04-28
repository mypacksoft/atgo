"""Parse ZKTeco ADMS payloads.

ZKTeco devices push tab-separated text in the body. Format varies slightly by
firmware. We handle the common cases.

ATTLOG row:
    PIN \t YYYY-MM-DD HH:MM:SS \t verify \t state \t workcode \t reserved1 \t reserved2

OPERLOG: a sequence of records separated by newlines, each starting with a
type prefix (USER, FP, FACE, ATTPHOTO, OPLOG, ...). We *deliberately drop*
biometric rows so we never store templates.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AttLogRecord:
    pin: str
    punched_at_local: datetime  # device-local naive time
    verify_type: int | None
    punch_state: int | None
    work_code: str | None

    def to_utc(self, tz_name: str | None) -> datetime:
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
        local = self.punched_at_local.replace(tzinfo=tz)
        return local.astimezone(timezone.utc)

    def idempotency_key(self, serial_number: str) -> str:
        # Stable across retries: identical (sn, pin, time, state) collapses to 1 row
        raw = f"{serial_number}|{self.pin}|{self.punched_at_local.isoformat()}|{self.punch_state}"
        return hashlib.sha256(raw.encode()).hexdigest()


_BIOMETRIC_PREFIXES = ("FP", "FACE", "BIODATA", "USERPIC", "ATTPHOTO", "FINGERTMP")


def is_biometric_line(line: str) -> bool:
    head = line.strip().split(None, 1)[0] if line.strip() else ""
    return head.upper() in _BIOMETRIC_PREFIXES


def filter_biometric(payload: str) -> tuple[str, int]:
    """Return (cleaned_payload, dropped_byte_count)."""
    out: list[str] = []
    dropped = 0
    for line in payload.splitlines():
        if is_biometric_line(line):
            dropped += len(line)
            continue
        out.append(line)
    return "\n".join(out), dropped


def parse_attlog(body: str) -> Iterable[AttLogRecord]:
    """Yield AttLogRecord per non-empty line."""
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        pin = cols[0].strip()
        if not pin:
            continue
        ts_str = cols[1].strip()
        ts = _parse_zk_timestamp(ts_str)
        if ts is None:
            continue
        verify = _safe_int(cols[2]) if len(cols) > 2 else None
        state = _safe_int(cols[3]) if len(cols) > 3 else None
        wcode = cols[4].strip() if len(cols) > 4 and cols[4].strip() else None
        yield AttLogRecord(pin=pin, punched_at_local=ts, verify_type=verify,
                           punch_state=state, work_code=wcode)


def _parse_zk_timestamp(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _safe_int(s: str) -> int | None:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return None


def render_initial_config(serial: str, server_ver: str = "2.4") -> str:
    """Response body for GET /iclock/cdata?SN=...&options=all (initial pull)."""
    return (
        f"GET OPTION FROM: {serial}\n"
        f"ATTLOGStamp=NONE\n"
        f"OPERLOGStamp=NONE\n"
        f"ATTPHOTOStamp=NONE\n"
        f"ErrorDelay=30\n"
        f"Delay=10\n"
        f"TransTimes=00:00;14:05\n"
        f"TransInterval=1\n"
        f"TransFlag=TransData AttLog OpLog\n"
        f"TimeZone=0\n"
        f"Realtime=1\n"
        f"Encrypt=None\n"
        f"ServerVer={server_ver}\n"
    )
