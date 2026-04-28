"""Simulate a ZKTeco device against the ADMS endpoint.

Usage:
    python scripts/simulate_zkteco.py --sn TEST123456 --pin 1001
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def post(url: str, body: str = "") -> tuple[int, str]:
    req = Request(
        url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    with urlopen(req, timeout=10) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def get(url: str) -> tuple[int, str]:
    with urlopen(url, timeout=10) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://adms.atgo.local",
                   help="ADMS base URL")
    p.add_argument("--sn", required=True, help="Device serial number")
    p.add_argument("--pin", default="1001", help="Employee PIN to punch")
    p.add_argument("--state", type=int, default=0, help="0=in, 1=out")
    args = p.parse_args()

    base = args.base.rstrip("/")

    print(f"[1/3] GET initial config (cdata?SN={args.sn})")
    status, body = get(f"{base}/iclock/cdata?{urlencode({'SN': args.sn, 'options': 'all'})}")
    print(f"  -> {status}: {body[:160]}")

    print(f"[2/3] POST attendance log (table=ATTLOG)")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = f"{args.pin}\t{now}\t1\t{args.state}\t0\t0\t0\n"
    status, response = post(
        f"{base}/iclock/cdata?{urlencode({'SN': args.sn, 'table': 'ATTLOG', 'Stamp': '0'})}",
        body,
    )
    print(f"  -> {status}: {response.strip()[:160]}")

    print(f"[3/3] GET pending command (getrequest)")
    status, response = get(f"{base}/iclock/getrequest?{urlencode({'SN': args.sn, 'INFO': '1'})}")
    print(f"  -> {status}: {response.strip()[:160]}")

    print("\nDone. Check the API:")
    print(f"  curl http://api.atgo.local/api/devices  (with auth)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
