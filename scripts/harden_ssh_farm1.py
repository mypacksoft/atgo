"""Harden SSH on farm1.mypacksoft.com (Windows Server 2016).

Strategy (safety first — never lose remote access):
    Phase 1: open firewall for new port 29812
    Phase 2: write sshd_config that listens on BOTH 22 and 29812,
             with AllowUsers administrator + PermitRootLogin no
    Phase 3: restart sshd, verify new port works
    Phase 4: rewrite sshd_config to listen ONLY on 29812
    Phase 5: restart sshd, verify
    Phase 6: remove firewall rule for port 22 (optional, kept for safety)

If any step fails, roll back from .bak file.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import paramiko

HOST = "farm1.mypacksoft.com"
USER = "administrator"
OLD_PORT = 22
NEW_PORT = 29812
SSHD_CONFIG = r"C:\ProgramData\ssh\sshd_config"


# =============================================================
# Helpers
# =============================================================

def banner(s: str) -> None:
    print(f"\n\033[1;36m{'='*66}\n  {s}\n{'='*66}\033[0m")

def ok(s: str) -> None:
    print(f"  \033[1;32m+\033[0m {s}")

def err(s: str) -> None:
    print(f"  \033[1;31m!\033[0m {s}")


def connect(host: str, port: int, password: str, timeout: int = 15) -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        host, port=port, username=USER, password=password,
        timeout=timeout, banner_timeout=timeout,
        look_for_keys=False, allow_agent=False,
    )
    return c


def run(c: paramiko.SSHClient, cmd: str, *, shell: str = "cmd",
        ignore_err: bool = False, timeout: int = 30) -> tuple[int, str, str]:
    """Execute a command. shell='cmd' (default) or 'ps' for PowerShell."""
    if shell == "ps":
        # -EncodedCommand avoids quoting hell when cmd contains $ or quotes
        import base64
        encoded = base64.b64encode(cmd.encode("utf-16-le")).decode()
        full = f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {encoded}"
    else:
        full = cmd
    stdin, stdout, stderr = c.exec_command(full, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    e = stderr.read().decode(errors="replace")
    if rc != 0 and not ignore_err:
        err(f"command failed (rc={rc}): {cmd[:120]}")
        if out.strip(): err(f"  stdout: {out.strip()[:300]}")
        if e.strip():   err(f"  stderr: {e.strip()[:300]}")
    return rc, out, e


def write_remote(c: paramiko.SSHClient, path: str, content: bytes) -> None:
    """Atomically write a file on the remote via SFTP."""
    sftp = c.open_sftp()
    try:
        tmp = path + ".new"
        with sftp.open(tmp, "wb") as f:
            f.write(content)
        # Windows: replace requires removing the target first if it exists
        try: sftp.remove(path)
        except FileNotFoundError: pass
        sftp.rename(tmp, path)
    finally:
        sftp.close()


def read_remote(c: paramiko.SSHClient, path: str) -> str:
    sftp = c.open_sftp()
    try:
        with sftp.open(path, "rb") as f:
            return f.read().decode(errors="replace")
    finally:
        sftp.close()


# =============================================================
# Config builder
# =============================================================

ATGO_BLOCK_START = "# >>> ATGO managed (do not edit between markers) <<<"
ATGO_BLOCK_END = "# <<< ATGO managed end >>>"


def build_atgo_block(ports: list[int], allow_user: str = "administrator") -> str:
    port_lines = "\n".join(f"Port {p}" for p in ports)
    # On Windows AD-joined hosts, sshd resolves the username to the SAM form
    # `domain\user`. `AllowUsers administrator` then no longer matches.
    # Cover both bare and domain-qualified forms with a wildcard.
    allow_pattern = f"{allow_user} *\\{allow_user}"
    return (
        f"{ATGO_BLOCK_START}\n"
        f"# rendered {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{port_lines}\n"
        f"AllowUsers {allow_pattern}\n"
        f"DenyUsers Guest DefaultAccount krbtgt WDeployAdmin WDeployConfigWriter\n"
        f"PermitRootLogin no\n"
        f"# Keep password auth (original setup); switch to keys later\n"
        f"PasswordAuthentication yes\n"
        f"PubkeyAuthentication yes\n"
        f"PermitEmptyPasswords no\n"
        f"MaxAuthTries 4\n"
        f"LoginGraceTime 30\n"
        f"ClientAliveInterval 60\n"
        f"ClientAliveCountMax 3\n"
        f"{ATGO_BLOCK_END}\n"
    )


def merge_config(original: str, new_block: str) -> str:
    """Splice the ATGO block into sshd_config.

    Critical: must insert BEFORE any `Match` block — directives after `Match`
    are scoped to that block, and many (Port, ListenAddress, ...) are not
    allowed inside Match scopes.
    """
    import re

    # Strip prior managed block (anywhere)
    pattern = re.escape(ATGO_BLOCK_START) + r"[\s\S]*?" + re.escape(ATGO_BLOCK_END) + r"\r?\n?"
    cleaned = re.sub(pattern, "", original)

    # Comment-out conflicting top-level directives so duplicates don't conflict
    def comment_directive(text: str, directive: str) -> str:
        out = []
        # Track Match scope so we don't comment out things inside it
        in_match = False
        for line in text.splitlines():
            stripped = line.lstrip()
            low = stripped.lower()
            if low.startswith("match "):
                in_match = True
                out.append(line); continue
            if in_match:
                # Match blocks end at the next non-indented non-empty line
                # that isn't part of the match continuation
                if stripped and not line.startswith((" ", "\t")):
                    in_match = False
                else:
                    out.append(line); continue
            if (not stripped.startswith("#")) and low.startswith(directive.lower() + " "):
                out.append("# " + line + "  # disabled by ATGO harden_ssh")
            else:
                out.append(line)
        return "\n".join(out)

    for d in ("Port", "AllowUsers", "PermitRootLogin", "PasswordAuthentication",
              "PubkeyAuthentication", "PermitEmptyPasswords"):
        cleaned = comment_directive(cleaned, d)

    # Find the first `Match ...` line and insert our block right before it.
    lines = cleaned.splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if line.lstrip().lower().startswith("match "):
            insert_at = i
            break

    head = "\n".join(lines[:insert_at]).rstrip()
    tail = "\n".join(lines[insert_at:])
    out = head + "\n\n" + new_block.rstrip() + "\n"
    if tail.strip():
        out += "\n" + tail.rstrip() + "\n"
    return out


# =============================================================
# Phases
# =============================================================

def phase_open_firewall(c: paramiko.SSHClient, port: int, label: str) -> None:
    rc, out, _ = run(c,
        f"netsh advfirewall firewall show rule name=\"ATGO-SSH-{port}\"",
        ignore_err=True)
    if "No rules match" in out or rc != 0:
        rc, _, _ = run(c,
            f"netsh advfirewall firewall add rule "
            f"name=\"ATGO-SSH-{port}\" dir=in action=allow "
            f"protocol=TCP localport={port}", ignore_err=False)
        if rc == 0:
            ok(f"firewall opened port {port}/TCP ({label})")
    else:
        ok(f"firewall rule for {port} already exists")


def phase_close_firewall(c: paramiko.SSHClient, port: int) -> None:
    run(c, f"netsh advfirewall firewall delete rule name=\"ATGO-SSH-{port}\"",
        ignore_err=True)
    # Also delete any default OpenSSH rule on port 22
    run(c, "netsh advfirewall firewall delete rule name=\"OpenSSH-Server-In-TCP\"",
        ignore_err=True)
    ok(f"firewall closed port {port}/TCP")


def phase_write_config(c: paramiko.SSHClient, ports: list[int]) -> str:
    """Returns path to the .bak file written before the change."""
    original = read_remote(c, SSHD_CONFIG)

    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = f"{SSHD_CONFIG}.bak-{ts}"
    sftp = c.open_sftp()
    try:
        with sftp.open(bak, "wb") as f:
            f.write(original.encode())
    finally:
        sftp.close()
    ok(f"backed up to {bak}")

    new_content = merge_config(original, build_atgo_block(ports))
    write_remote(c, SSHD_CONFIG, new_content.encode())
    ok(f"wrote new sshd_config (Port = {','.join(map(str,ports))})")
    return bak


def phase_validate_config(c: paramiko.SSHClient) -> bool:
    # PowerShell call operator handles paths with spaces cleanly.
    rc, out, e = run(
        c,
        f'$exe = (Get-Command sshd -ErrorAction SilentlyContinue).Source; '
        f'if (-not $exe) {{ $exe = "C:\\Program Files\\OpenSSH\\sshd.exe" }}; '
        f'& $exe -t -f "{SSHD_CONFIG}"; exit $LASTEXITCODE',
        shell="ps", ignore_err=True,
    )
    if rc == 0:
        ok(f"sshd -t : config syntax OK")
        return True
    err(f"sshd -t failed (rc={rc}): {e or out or '<no output>'}")
    return False


def phase_restart_sshd(c: paramiko.SSHClient) -> bool:
    rc, _, _ = run(c, "Restart-Service sshd -Force; Start-Sleep -Seconds 3; "
                       "(Get-Service sshd).Status",
                    shell="ps", ignore_err=True)
    if rc != 0:
        err(f"Restart-Service sshd returned non-zero ({rc})")
        return False
    ok("sshd restarted")
    return True


def phase_rollback(c: paramiko.SSHClient, bak: str) -> None:
    err("ROLLING BACK sshd_config from " + bak)
    sftp = c.open_sftp()
    try:
        with sftp.open(bak, "rb") as f:
            data = f.read()
    finally:
        sftp.close()
    write_remote(c, SSHD_CONFIG, data)
    phase_restart_sshd(c)


def verify_new_port(host: str, port: int, password: str) -> bool:
    print(f"\n  verifying connection to {host}:{port}...")
    try:
        c2 = connect(host, port, password, timeout=20)
        rc, out, _ = run(c2, "whoami", ignore_err=True)
        c2.close()
        if rc == 0 and out.strip().lower().endswith("administrator"):
            ok(f"reconnected on port {port} as {out.strip()}")
            return True
        err(f"reconnected but unexpected user: {out!r}")
        return False
    except Exception as e:
        err(f"could not connect on port {port}: {e}")
        return False


# =============================================================
# Main
# =============================================================

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--password", required=True)
    p.add_argument("--dry-run", action="store_true",
                    help="connect + read config, do not modify")
    args = p.parse_args()

    banner(f"Phase 0 — connect to {HOST}:{OLD_PORT} as {USER}")
    try:
        c = connect(HOST, OLD_PORT, args.password)
    except Exception as e:
        err(f"initial connect failed: {e}")
        return 1
    ok("connected")

    # Read current state
    rc, current_users, _ = run(c, "net user", shell="cmd", ignore_err=True)
    print("  --- net user ---")
    print("  " + (current_users or "").replace("\n", "\n  "))

    if args.dry_run:
        original = read_remote(c, SSHD_CONFIG)
        print("\n  --- current sshd_config (first 60 lines) ---")
        for line in original.splitlines()[:60]:
            print("  | " + line)
        c.close()
        return 0

    bak = None
    try:
        banner(f"Phase 1 — open firewall for port {NEW_PORT}")
        phase_open_firewall(c, NEW_PORT, "new SSH")

        banner(f"Phase 2 — write sshd_config (BOTH {OLD_PORT} and {NEW_PORT})")
        bak = phase_write_config(c, [OLD_PORT, NEW_PORT])

        banner("Phase 2b — validate sshd config")
        if not phase_validate_config(c):
            phase_rollback(c, bak)
            return 2

        banner("Phase 3 — restart sshd (dual-port)")
        if not phase_restart_sshd(c):
            phase_rollback(c, bak)
            return 3

        time.sleep(2)
        banner(f"Phase 3b — verify NEW port {NEW_PORT} reachable")
        if not verify_new_port(HOST, NEW_PORT, args.password):
            phase_rollback(c, bak)
            return 4

        banner(f"Phase 4 — rewrite sshd_config (ONLY port {NEW_PORT})")
        bak2 = phase_write_config(c, [NEW_PORT])
        if not phase_validate_config(c):
            phase_rollback(c, bak2)
            return 5

        banner("Phase 5 — restart sshd (single port)")
        if not phase_restart_sshd(c):
            phase_rollback(c, bak2)
            return 6

        time.sleep(2)
        banner(f"Phase 5b — final verify on {NEW_PORT}")
        if not verify_new_port(HOST, NEW_PORT, args.password):
            phase_rollback(c, bak2)
            return 7

        banner(f"Phase 6 — close firewall port {OLD_PORT}")
        phase_close_firewall(c, OLD_PORT)

        banner("DONE")
        ok(f"SSH now restricted to {USER}@{HOST}:{NEW_PORT}")
        ok(f"backup files left on server: {bak}, {bak2}")
        ok(f"reconnect with: ssh -p {NEW_PORT} {USER}@{HOST}")
        return 0
    finally:
        try: c.close()
        except: pass


if __name__ == "__main__":
    sys.exit(main())
