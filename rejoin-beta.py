#!/usr/bin/env python3
"""
executor.py — Python Executor untuk Roblox Auto Rejoin

Tidak ada .env — config diinput saat startup.
Polling ke Node.js Internal API, ambil perintah,
eksekusi shell command di Android, laporkan hasil.
"""

import os
import sys
import time
import subprocess
import getpass
import requests

# ─── Prompt config saat startup ────────────────────────────────────────────────

def prompt_config():
    print("=" * 50)
    print("  Roblox Auto Rejoin — Python Executor")
    print("=" * 50)
    print()

    host = input("🌐 Node.js Host    : (Enter = 127.0.0.1) ").strip() or "127.0.0.1"

    port_input = input("🔌 Node.js CMD Port: (Enter = 6970) ").strip()
    port = int(port_input) if port_input.isdigit() else 6970

    secret = ""
    while not secret:
        secret = getpass.getpass("🔐 Executor Secret  : ")
        if not secret:
            print("  ⚠️  Secret wajib diisi! Harus sama dengan yang diinput di Node.js.")

    interval_input = input("⏱️  Poll Interval    : detik (Enter = 3) ").strip()
    interval = float(interval_input) if interval_input else 3.0

    print()
    print(f"  ✅ Config OK — konek ke http://{host}:{port}")
    print("=" * 50)
    print()

    return {"host": host, "port": port, "secret": secret, "interval": interval}

# ─── Globals ───────────────────────────────────────────────────────────────────
CONFIG = {}

def headers():
    return {"Content-Type": "application/json", "x-executor-secret": CONFIG["secret"]}

def base_url():
    return f"http://{CONFIG['host']}:{CONFIG['port']}"

# ─── Shell helpers ──────────────────────────────────────────────────────────────

def run(cmd):
    try:
        result = subprocess.run(cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace").strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Timeout 30 detik"
    except Exception as e:
        return False, str(e)

def get_pid(pkg):
    ok, out = run(f"pidof {pkg}")
    return out.strip() if out.strip() else None

def kill_app(pkg):
    pid = get_pid(pkg)
    if pid:
        ok, msg = run(f"su -c 'kill {pid}'")
        print(f"[Executor] Kill {pkg} PID={pid}: {'OK' if ok else msg}")
        return ok
    return False

def launch_private_server(ps_link, pkg):
    kill_app(pkg)
    time.sleep(5)
    return run(f"am start -a android.intent.action.VIEW -d '{ps_link}' {pkg}")

def launch_game(game_id, pkg):
    return run(f"am start -a android.intent.action.VIEW -d 'roblox://placeID={game_id}' {pkg}")

def find_roblox_packages():
    ok, out = run("pm list packages")
    if not ok or not out:
        return []
    return [l.split(":")[-1].strip() for l in out.splitlines() if "roblox" in l.lower()]

# ─── API calls ─────────────────────────────────────────────────────────────────

def fetch_commands():
    try:
        r = requests.get(f"{base_url()}/commands", headers=headers(), timeout=5)
        if r.status_code == 200:
            return r.json().get("commands", [])
        if r.status_code == 401:
            print("[Executor] ❌ Secret salah!")
    except requests.exceptions.ConnectionError:
        print(f"[Executor] ⚠️  Tidak bisa konek ke {base_url()}, menunggu...")
    except Exception as e:
        print(f"[Executor] Error fetch: {e}")
    return []

def report_result(cmd_id, success, message):
    try:
        requests.post(f"{base_url()}/result", headers=headers(),
            json={"id": cmd_id, "success": success, "message": message}, timeout=5)
    except Exception as e:
        print(f"[Executor] Error report: {e}")

# ─── Handlers ──────────────────────────────────────────────────────────────────

def handle_rejoin(cmd):
    username = cmd.get("username", "?")
    pkg      = cmd.get("packagename", "")
    game_id  = cmd.get("game_id", "")
    is_ps    = cmd.get("is_ps", False)
    ps_link  = cmd.get("ps_link", "")

    if not pkg:
        return False, "packagename kosong"

    print(f"[Executor] Rejoin {username} pkg={pkg} ps={is_ps}")
    ok, msg = launch_private_server(ps_link, pkg) if (is_ps and ps_link) else launch_game(game_id, pkg)
    status = "berhasil" if ok else "gagal"
    print(f"[Executor] {username}: {status} — {msg}")
    return ok, f"{status}: {msg}"

def handle_scan_packages(cmd):
    pkgs = find_roblox_packages()
    msg = ("Package: " + ", ".join(pkgs)) if pkgs else "Tidak ada package Roblox"
    print(f"[Executor] Scan: {msg}")
    return bool(pkgs), msg

HANDLERS = {"rejoin": handle_rejoin, "scan_packages": handle_scan_packages}

def process_command(cmd):
    cmd_id   = cmd.get("id", "")
    cmd_type = cmd.get("type", "")
    username = cmd.get("username", "?")
    print(f"[Executor] ← {cmd_type} user={username} id={cmd_id[:8]}")
    handler = HANDLERS.get(cmd_type)
    if handler:
        success, message = handler(cmd)
    else:
        success, message = False, f"Unknown: {cmd_type}"
    report_result(cmd_id, success, message)

# ─── Main loop ─────────────────────────────────────────────────────────────────

def main():
    global CONFIG
    CONFIG = prompt_config()
    print(f"[Executor] Polling setiap {CONFIG['interval']}s...\n")

    while True:
        try:
            cmds = fetch_commands()
            if cmds:
                print(f"[Executor] {len(cmds)} command(s)")
                for cmd in cmds:
                    process_command(cmd)
        except KeyboardInterrupt:
            print("\n[Executor] Dihentikan.")
            sys.exit(0)
        except Exception as e:
            print(f"[Executor] Error: {e}")
        time.sleep(CONFIG["interval"])

if __name__ == "__main__":
    main()
