import sys
import time
import subprocess
import getpass
import requests
import random
import string

# ─── Prompt config ─────────────────────────────────────────────────────────────
def prompt_config():
    print("=" * 52)
    print("  Roblox Auto Rejoin — Python Executor")
    print("=" * 52)
    print()
    characters = string.ascii_uppercase + string.digits
    executor_id =  ''.join(random.choices(characters, k=5))
    while not executor_id:
        executor_id = input("🏷️  Executor ID      : (misal: android_andi) ").strip()
        if not executor_id:
            print("  ⚠️  Wajib diisi!")

    host = "https://prototipe.staryuu.my.id/"
    host = host.rstrip('/')
    if not host:
        host = "http://127.0.0.1:3000"

    secret = "Staryuu17"
    while not secret:
        secret = getpass.getpass("🔐 Executor Secret  : ")
        if not secret:
            print("  ⚠️  Wajib diisi!")

    interval_input = input("⏱️  Poll Interval    : detik (Enter = 3) ").strip()
    interval = float(interval_input) if interval_input else 3.0

    print()
    print(f"  ✅ Executor ID : {executor_id}")
    print(f"  ✅ Server      : {host}")
    print("=" * 52)
    print()

    return {
        "executor_id": executor_id,
        "base_url":    host,           # ← 1 URL saja, beda endpoint
        "secret":      secret,
        "interval":    interval,
    }

# ─── Globals ───────────────────────────────────────────────────────────────────
CONFIG = {}

def headers():
    return {
        "Content-Type":       "application/json",
        "x-executor-secret":  CONFIG["secret"],
    }

def url(path):
    # path contoh: /internal/commands
    return CONFIG["base_url"] + path

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
        print(f"[{CONFIG['executor_id']}] Kill {pkg} PID={pid}: {'OK' if ok else msg}")
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

# ─── API calls ke Node.js /internal/* ─────────────────────────────────────────
def register():
    try:
        r = requests.post(url("/internal/register"), headers=headers(),
            json={"executor_id": CONFIG["executor_id"]}, timeout=10)
        if r.status_code == 200:
            data  = r.json()
            users = data.get("users", [])
            claimed = data.get("claimed", False)
            if users:
                print(f"[{CONFIG['executor_id']}] ✅ User terdaftar: {', '.join(users)}")
            else:
                print(f"[{CONFIG['executor_id']}] ℹ️  Belum ada user — inject Lua script dulu")
            if not claimed:
                print(f"[{CONFIG['executor_id']}] ⚠️  Executor belum di-claim! Ketik /claim {CONFIG['executor_id']} di Discord")
        elif r.status_code == 401:
            print(f"[{CONFIG['executor_id']}] ❌ Secret salah!")
            sys.exit(1)
        else:
            print(f"[{CONFIG['executor_id']}] ⚠️  Register response: {r.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"[{CONFIG['executor_id']}] ⚠️  Tidak bisa konek ke {CONFIG['base_url']}, lanjut polling...")

def fetch_commands():
    try:
        r = requests.get(
            url("/internal/commands"),
            headers=headers(),
            params={"executor_id": CONFIG["executor_id"]},
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("commands", [])
        if r.status_code == 401:
            print(f"[{CONFIG['executor_id']}] ❌ Secret salah!")
    except requests.exceptions.ConnectionError:
        print(f"[{CONFIG['executor_id']}] ⚠️  Koneksi terputus, menunggu...")
    except Exception as e:
        print(f"[{CONFIG['executor_id']}] Error fetch: {e}")
    return []

def report_result(cmd_id, success, message):
    try:
        requests.post(url("/internal/result"), headers=headers(),
            json={"id": cmd_id, "success": success, "message": message}, timeout=10)
    except Exception as e:
        print(f"[{CONFIG['executor_id']}] Error report: {e}")

# ─── Command handlers ──────────────────────────────────────────────────────────
def handle_rejoin(cmd):
    username = cmd.get("username", "?")
    pkg      = cmd.get("packagename", "")
    game_id  = cmd.get("game_id", "")
    is_ps    = cmd.get("is_ps", False)
    ps_link  = cmd.get("ps_link", "")

    if not pkg:
        return False, "packagename kosong"

    print(f"[{CONFIG['executor_id']}] Rejoin {username} | pkg={pkg} | ps={is_ps}")
    ok, msg = launch_private_server(ps_link, pkg) if (is_ps and ps_link) else launch_game(game_id, pkg)
    status = "berhasil" if ok else "gagal"
    print(f"[{CONFIG['executor_id']}] {username}: {status}")
    return ok, f"{status}: {msg}"

def handle_scan_packages(cmd):
    pkgs = find_roblox_packages()
    msg  = ("Package: " + ", ".join(pkgs)) if pkgs else "Tidak ada package Roblox"
    print(f"[{CONFIG['executor_id']}] Scan: {msg}")
    return bool(pkgs), msg

HANDLERS = {
    "rejoin":        handle_rejoin,
    "scan_packages": handle_scan_packages,
}

def process_command(cmd):
    cmd_id   = cmd.get("id", "")
    cmd_type = cmd.get("type", "")
    username = cmd.get("username", "?")
    print(f"[{CONFIG['executor_id']}] ← {cmd_type} | user={username} | id={cmd_id[:8]}")
    handler = HANDLERS.get(cmd_type)
    if handler:
        success, message = handler(cmd)
    else:
        success, message = False, f"Unknown: {cmd_type}"
    report_result(cmd_id, success, message)

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    global CONFIG
    CONFIG = prompt_config()

    register()
    print(f"[{CONFIG['executor_id']}] Polling setiap {CONFIG['interval']}s...\n")

    while True:
        try:
            cmds = fetch_commands()
            if cmds:
                print(f"[{CONFIG['executor_id']}] {len(cmds)} command(s)")
                for i, cmd in enumerate(cmds):
                    process_command(cmd)
                    if i < len(cmds) - 1:
                        print(f"[{CONFIG['executor_id']}] Jeda 10 detik...")
                        time.sleep(10)
        except KeyboardInterrupt:
            print(f"\n[{CONFIG['executor_id']}] Dihentikan.")
            sys.exit(0)
        except Exception as e:
            print(f"[{CONFIG['executor_id']}] Error: {e}")
        time.sleep(CONFIG["interval"])

if __name__ == "__main__":
    main()
