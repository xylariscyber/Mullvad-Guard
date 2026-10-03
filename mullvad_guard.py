#!/usr/bin/env python3
"""
Mullvad Guard - keeps your Mullvad account limited to N devices.

Runs in a loop while the Mullvad app is open. If the account has more devices
than allowed, the NEWEST devices are removed (the oldest ones are kept).

Setup:  pip install requests psutil
Config: edit the SETTINGS section below
Run:    python mullvad_guard.py          (loop mode)
        python mullvad_guard.py --once   (single check, then exit)
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
import requests

# =============================== SETTINGS ===============================
ACCOUNT_NUMBER = "YOUR_MULLVAD_ACCOUNT_NUMBER"   # your Mullvad account number
MAX_DEVICES = 2                    # number of devices allowed on the account
CHECK_INTERVAL = 30                # seconds between two checks
PROTECTED_NAMES = []               # device names to NEVER kick, e.g. ["happy-fox", "calm-owl"]
DRY_RUN = False                    # True = only log what would be removed, nothing is deleted
ONLY_WHEN_MULLVAD_RUNNING = True   # False = also check when the Mullvad app is closed
MULLVAD_PROCESSES = [              # Mullvad process names (lowercase)
    "mullvad vpn.exe", "mullvad-daemon.exe", "mullvad-daemon",
    "mullvad vpn", "mullvad-gui",
]
# ========================================================================

PLACEHOLDER = "YOUR_MULLVAD_ACCOUNT_NUMBER"
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "mullvad_guard.log"
API = "https://api.mullvad.net"

# ---------------------------------------------------------------- logging
# Console shows everything (INFO+). The log file only keeps warnings:
# "too many devices detected" and "device kicked".
log = logging.getLogger("mullvad-guard")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(_fmt)
log.addHandler(_console)

_file = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file.setLevel(logging.WARNING)
_file.setFormatter(_fmt)
log.addHandler(_file)

_token = {"value": None, "expiry": 0.0}


def account_number() -> str:
    return str(ACCOUNT_NUMBER).replace(" ", "")


def check_settings() -> None:
    if not account_number() or account_number() == PLACEHOLDER:
        sys.exit("Set your Mullvad account number in ACCOUNT_NUMBER (top of the script) first.")
    if int(MAX_DEVICES) < 1:
        sys.exit("MAX_DEVICES must be at least 1.")


# ---------------------------------------------------------------- helpers
def mullvad_running() -> bool:
    names = {n.lower() for n in MULLVAD_PROCESSES}
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() in names:
            return True
    return False


def get_token() -> str:
    if _token["value"] and time.time() < _token["expiry"] - 60:
        return _token["value"]
    r = requests.post(
        f"{API}/auth/v1/token",
        json={"account_number": account_number()},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    _token["value"] = data["access_token"]
    try:
        exp = datetime.fromisoformat(data["expiry"].replace("Z", "+00:00"))
        _token["expiry"] = exp.timestamp()
    except Exception:
        _token["expiry"] = time.time() + 3600
    return _token["value"]


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}"}


def list_devices() -> list:
    r = requests.get(f"{API}/accounts/v1/devices", headers=auth_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def delete_device(dev: dict) -> None:
    if DRY_RUN:
        log.warning("[DRY RUN] Device would be KICKED: %s", dev["name"])
        return
    r = requests.delete(
        f"{API}/accounts/v1/devices/{dev['id']}", headers=auth_headers(), timeout=15
    )
    r.raise_for_status()
    log.warning("Device KICKED: %s", dev["name"])


def check_once() -> None:
    devices = list_devices()
    log.info(
        "Check OK: %d/%d devices (%s)",
        len(devices), MAX_DEVICES, ", ".join(d["name"] for d in devices),
    )
    if len(devices) <= MAX_DEVICES:
        return

    # Oldest devices are trusted, newest ones are suspicious.
    devices.sort(key=lambda d: d.get("created", ""))
    protected = [d for d in devices if d["name"] in PROTECTED_NAMES]
    others = [d for d in devices if d["name"] not in PROTECTED_NAMES]

    slots_left = max(MAX_DEVICES - len(protected), 0)
    keep = protected + others[:slots_left]
    to_kick = [d for d in devices if d not in keep]

    log.warning(
        "%d devices detected (max %d) -> %d to remove",
        len(devices), MAX_DEVICES, len(to_kick),
    )
    for dev in to_kick:
        delete_device(dev)


# ---------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description="Mullvad device guard")
    parser.add_argument("--once", action="store_true",
                        help="run a single check and exit (ignores the Mullvad process check)")
    args = parser.parse_args()

    check_settings()

    if args.once:
        check_once()
        return

    log.info("Mullvad Guard started (max %s devices, check every %ss%s)",
             MAX_DEVICES, CHECK_INTERVAL, ", DRY RUN" if DRY_RUN else "")

    was_running = False
    while True:
        try:
            running = mullvad_running() or not ONLY_WHEN_MULLVAD_RUNNING
            if running and not was_running:
                log.info("Monitoring active.")
            elif not running and was_running:
                log.info("Mullvad closed, monitoring paused.")
            was_running = running

            if running:
                check_once()
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            log.error("API error (%s), will retry.", code)
            _token["value"] = None
            if code == 429:
                time.sleep(120)
        except Exception as e:
            log.error("Error: %s", e)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped (Ctrl+C).")
