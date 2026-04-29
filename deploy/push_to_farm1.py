"""Push ATGO source + Postgres portable + bootstrap script to farm1, then run.

Designed to be re-runnable. Skips re-uploading files that haven't changed
(by size+mtime).
"""
from __future__ import annotations

import argparse
import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import paramiko

HOST = "farm1.mypacksoft.com"
PORT = 29812
USER = "administrator"
REMOTE_ROOT = "E:\\atgo"
REMOTE_PKGS = f"{REMOTE_ROOT}\\pkgs"
REMOTE_REPO = f"{REMOTE_ROOT}\\repo"

LOCAL_REPO = Path(__file__).resolve().parents[1]
LOCAL_PG_PORTABLE = Path(r"C:\Users\phuoc\postgres-portable\pgsql")


def banner(s):
    print(f"\n\033[1;36m{'='*64}\n  {s}\n{'='*64}\033[0m", flush=True)


def make_archive(src: Path, dest: Path,
                  excludes: tuple[str, ...] = ()) -> None:
    print(f"  packing {src} -> {dest.name}")
    with tarfile.open(dest, "w:gz") as tar:
        def filt(ti: tarfile.TarInfo):
            for pat in excludes:
                if pat in ti.name:
                    return None
            return ti
        tar.add(str(src), arcname=src.name, filter=filt)
    print(f"  -> {dest.stat().st_size / 1024 / 1024:.1f} MB")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--password", required=True)
    p.add_argument("--admin-email", default="admin@atgo.io")
    p.add_argument("--admin-password", default=None,
                   help="defaults to a randomly generated 16-char password")
    p.add_argument("--skip-postgres", action="store_true",
                   help="don't re-upload Postgres portable (slow ~50MB)")
    p.add_argument("--skip-source",   action="store_true",
                   help="don't re-upload ATGO source")
    p.add_argument("--bootstrap-only", action="store_true",
                   help="don't upload anything, just run bootstrap.ps1")
    p.add_argument("--skip-phases", default="",
                   help="comma-separated phase numbers to skip in bootstrap")
    args = p.parse_args()

    if not args.admin_password:
        import secrets
        args.admin_password = secrets.token_urlsafe(12).replace("-", "_")[:16] + "!"

    banner(f"Connecting to {USER}@{HOST}:{PORT}")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, PORT, USER, args.password,
              timeout=30, look_for_keys=False, allow_agent=False)
    print("OK connected")

    sftp = c.open_sftp()

    def mkdir_p(remote: str):
        # Convert backslashes to forward slashes for SFTP
        path = remote.replace("\\", "/")
        parts = path.split("/")
        cur = ""
        for part in parts:
            if not part: continue
            cur = (cur + "/" + part) if cur else part
            try: sftp.stat(cur)
            except FileNotFoundError:
                try: sftp.mkdir(cur)
                except Exception: pass

    def put(local: Path, remote: str):
        # SFTP needs forward slashes
        remote_unix = remote.replace("\\", "/")
        sz = local.stat().st_size
        try:
            existing = sftp.stat(remote_unix)
            if existing.st_size == sz:
                print(f"  skip (same size): {remote}")
                return
        except FileNotFoundError:
            pass
        print(f"  upload {local.name} ({sz/1024/1024:.1f} MB) -> {remote}")
        sftp.put(str(local), remote_unix)

    def run(cmd: str, *, ps: bool = False, timeout: int = 600) -> int:
        if ps:
            import base64
            enc = base64.b64encode(cmd.encode("utf-16-le")).decode()
            full = f"powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand {enc}"
        else:
            full = cmd
        chan = c.get_transport().open_session()
        chan.set_combine_stderr(True)
        chan.exec_command(full)
        # stream output
        buf = b""
        start = time.time()
        while True:
            if chan.recv_ready():
                d = chan.recv(4096)
                buf += d
                # print line-buffered
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    print("   | " + line.decode(errors="replace").rstrip())
            if chan.exit_status_ready():
                break
            if time.time() - start > timeout:
                chan.close(); print("   ! timeout"); return 999
            time.sleep(0.1)
        if buf:
            print("   | " + buf.decode(errors="replace").rstrip())
        return chan.recv_exit_status()

    # ---- Phase: prepare folders ----
    banner("Phase 0 — folders")
    for p_ in (REMOTE_ROOT, REMOTE_PKGS, REMOTE_REPO):
        mkdir_p(p_)
    print("OK folders")

    # ---- Phase: upload Postgres portable ----
    if not args.bootstrap_only and not args.skip_postgres:
        banner("Phase 1 — Postgres portable")
        if not LOCAL_PG_PORTABLE.exists():
            print(f"  ! local Postgres portable not found at {LOCAL_PG_PORTABLE}")
        else:
            with tempfile.TemporaryDirectory() as td:
                tar = Path(td) / "pgsql.tgz"
                make_archive(LOCAL_PG_PORTABLE, tar)
                put(tar, f"{REMOTE_PKGS}\\pgsql.tgz")
            # extract on remote
            ps_cmd = (
                f'$ErrorActionPreference="Stop"; '
                f'$dst="{REMOTE_PKGS}\\pgsql"; '
                f'if (Test-Path $dst) {{ Write-Host "  pgsql already extracted" }} '
                f'else {{ '
                f'  Write-Host "  extracting pgsql.tgz..."; '
                f'  cd "{REMOTE_PKGS}"; tar -xzf pgsql.tgz; '
                f'  Write-Host "  done"; '
                f'}}'
            )
            run(ps_cmd, ps=True)

    # ---- Phase: upload source code ----
    if not args.bootstrap_only and not args.skip_source:
        banner("Phase 2 — ATGO source")
        with tempfile.TemporaryDirectory() as td:
            tar = Path(td) / "atgo-source.tgz"
            print("  packing source")
            with tarfile.open(tar, "w:gz") as t:
                excludes = {".venv","node_modules",".next","__pycache__",".pytest_cache",
                            ".pgdata",".env",".git",".publish","atgo-source.tgz",
                            "deploy/atgo_deploy_key", "deploy/atgo_deploy_key.pub"}
                for sub in ("apps","infra","scripts","deploy",".env.example",".gitignore",
                             "README.md","LICENSE","SECURITY.md","CONTRIBUTING.md"):
                    src = LOCAL_REPO / sub
                    if not src.exists(): continue
                    def filt(ti, ex=excludes):
                        if any(p in ti.name for p in ex): return None
                        return ti
                    t.add(str(src), arcname=sub, filter=filt)
            print(f"  -> {tar.stat().st_size/1024/1024:.1f} MB")
            put(tar, f"{REMOTE_PKGS}\\atgo-source.tgz")
        ps_cmd = (
            f'$ErrorActionPreference="Stop"; '
            f'cd "{REMOTE_REPO}"; '
            f'Write-Host "  extracting source"; '
            f'tar -xzf "{REMOTE_PKGS}\\atgo-source.tgz" -C "{REMOTE_REPO}"; '
            f'Write-Host "  done"; '
        )
        run(ps_cmd, ps=True)

    # ---- Phase: upload bootstrap.ps1 ----
    banner("Phase 3 — bootstrap script")
    put(LOCAL_REPO / "deploy" / "bootstrap_windows.ps1",
        f"{REMOTE_ROOT}\\bootstrap_windows.ps1")

    # ---- Phase: run bootstrap ----
    banner("Phase 4 — running bootstrap_windows.ps1 on farm1")
    skip_arg = ""
    if args.skip_phases:
        skip_arg = f"-SkipPhases @({args.skip_phases})"
    cmd = (
        f"& '{REMOTE_ROOT}\\bootstrap_windows.ps1' "
        f"-Root '{REMOTE_ROOT}' "
        f"-AdminEmail '{args.admin_email}' "
        f"-AdminPassword '{args.admin_password}' "
        f"{skip_arg}"
    )
    rc = run(cmd, ps=True, timeout=2400)

    sftp.close()
    c.close()

    if rc != 0:
        print(f"\nbootstrap returned rc={rc}")
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
