"""Promote a user to super-admin, or create a new super-admin if email is new.

Usage:
    python -m scripts.bootstrap_admin admin@atgo.io  --password=Sup3rSecret!  [--name="ATGO Admin"]
    python -m scripts.bootstrap_admin owner@acme.com   # promote existing user

Idempotent: safe to run multiple times.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from atgo_api.db import SessionLocal
from atgo_api.security import hash_password


async def upsert_super_admin(email: str, password: str | None, name: str | None) -> None:
    async with SessionLocal() as s:
        existing = await s.execute(
            text("SELECT id, is_super_admin FROM users WHERE email = :e"), {"e": email}
        )
        row = existing.mappings().first()

        if row:
            if row["is_super_admin"]:
                print(f"User {email} (id={row['id']}) is already super-admin. Nothing to do.")
                return
            await s.execute(
                text("UPDATE users SET is_super_admin = TRUE WHERE id = :id"),
                {"id": row["id"]},
            )
            await s.commit()
            print(f"Promoted {email} (id={row['id']}) to super-admin.")
            return

        if not password:
            print(f"User {email} not found and no --password given.", file=sys.stderr)
            sys.exit(2)

        ins = await s.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name, is_super_admin, is_active) "
                "VALUES (:e, :p, :n, TRUE, TRUE) RETURNING id"
            ),
            {"e": email, "p": hash_password(password), "n": name or "ATGO Admin"},
        )
        await s.commit()
        print(f"Created super-admin {email} (id={ins.scalar()}).")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("email")
    p.add_argument("--password", default=None)
    p.add_argument("--name", default=None)
    args = p.parse_args()
    asyncio.run(upsert_super_admin(args.email, args.password, args.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
