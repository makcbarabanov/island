#!/usr/bin/env python3
"""
Ежедневный снимок здоровья VPS → sites/stat/data/server_health.json.

Метрики: диск, RAM, swap, load, docker, smoke island/stat.
История: последние N дней (по умолчанию 60), одна запись на дату (MSK).

Cron на проде (08:00 MSK = 05:00 UTC):
  0 5 * * * cd /home/makc/Apps/island && python3 scripts/build_server_health_snapshot.py >> logs/server_health.log 2>&1
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_project_root = Path(__file__).resolve().parent.parent
OUT_PATH = _project_root / "sites" / "stat" / "data" / "server_health.json"
TZ = ZoneInfo(os.getenv("SERVER_HEALTH_TZ", "Europe/Moscow"))
HISTORY_DAYS = int(os.getenv("SERVER_HEALTH_HISTORY_DAYS", "60"))
DISK_PATH = os.getenv("SERVER_HEALTH_DISK_PATH", "/")
SMOKE_ISLAND = os.getenv("SMOKE_ISLAND_URL", "https://islanddream.ru/")
SMOKE_STAT = os.getenv("SMOKE_STAT_URL", "https://islanddream.ru/stat/")


def _human_bytes(n: int) -> str:
    if n < 0:
        n = 0
    units = ["B", "Ki", "Mi", "Gi", "Ti"]
    size = float(n)
    for unit in units:
        if size < 1024.0 or unit == "Ti":
            if unit == "B":
                return f"{int(size)}B"
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}Ti"


def _read_disk() -> tuple[int, str]:
    try:
        usage = shutil.disk_usage(DISK_PATH)
        pct = round(usage.used / usage.total * 100) if usage.total else 0
        return pct, _human_bytes(usage.free)
    except OSError:
        return 0, "—"


def _read_mem() -> tuple[str, str, str, int]:
    """ram_used, ram_avail, swap_used, ram_used_pct."""
    try:
        mem: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    mem[parts[0].rstrip(":")] = int(parts[1]) * 1024
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", mem.get("MemFree", 0))
        used = max(total - avail, 0)
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        swap_used = max(swap_total - swap_free, 0)
        pct = round(used / total * 100) if total else 0
        return _human_bytes(used), _human_bytes(avail), _human_bytes(swap_used), pct
    except OSError:
        return "—", "—", "—", 0


def _read_load() -> list[float]:
    try:
        with open("/proc/loadavg", encoding="utf-8") as f:
            parts = f.read().split()
        return [round(float(parts[i]), 2) for i in range(min(3, len(parts)))]
    except (OSError, ValueError, IndexError):
        return [0.0, 0.0, 0.0]


def _run(cmd: list[str], timeout: int = 30) -> str:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _docker_containers() -> list[str]:
    out = _run(["docker", "ps", "--format", "{{.Names}}: {{.Status}}"])
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _docker_images_summary() -> str:
    count = _run(["docker", "images", "-q"])
    n = len([x for x in count.splitlines() if x.strip()]) if count else 0
    df = _run(["docker", "system", "df", "--format", "{{.Size}}"], timeout=60)
    total_size = "—"
    if df:
        sizes = [ln.strip() for ln in df.splitlines() if ln.strip()]
        if sizes:
            total_size = sizes[0]
    return f"{n} images" + (f", {total_size}" if total_size != "—" else "")


def _smoke(url: str) -> int:
    out = _run(
        [
            "curl",
            "-sk",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--max-time",
            "15",
            url,
        ],
        timeout=20,
    )
    try:
        return int(out) if out.isdigit() else 0
    except ValueError:
        return 0


def _host_label() -> str:
    env = (os.getenv("SERVER_HEALTH_HOST") or "").strip()
    if env:
        return env
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return socket.gethostname()


def _snapshot_row() -> dict:
    disk_pct, disk_avail = _read_disk()
    ram_used, ram_avail, swap_used, ram_pct = _read_mem()
    return {
        "disk_used_pct": disk_pct,
        "disk_avail": disk_avail,
        "ram_used": ram_used,
        "ram_avail": ram_avail,
        "ram_used_pct": ram_pct,
        "swap_used": swap_used,
        "load": _read_load(),
        "smoke": {
            "island": _smoke(SMOKE_ISLAND),
            "stat": _smoke(SMOKE_STAT),
        },
        "containers": _docker_containers(),
        "docker_images": _docker_images_summary(),
    }


def _load_existing() -> dict:
    if not OUT_PATH.exists():
        return {"history": []}
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"history": []}


def _merge_history(existing: dict, today: str, row: dict) -> list[dict]:
    history = list(existing.get("history") or [])
    history = [h for h in history if h.get("date") != today]
    entry = {"date": today, **row}
    history.append(entry)
    history.sort(key=lambda h: h.get("date") or "")
    if len(history) > HISTORY_DAYS:
        history = history[-HISTORY_DAYS:]
    return history


def _atomic_write(payload: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUT_PATH)


def build() -> dict:
    now = datetime.now(TZ)
    today = now.date().isoformat()
    row = _snapshot_row()
    existing = _load_existing()
    history = _merge_history(existing, today, row)
    payload = {
        "updated_at": now.isoformat(timespec="seconds"),
        "host": _host_label(),
        "latest": row,
        "history": history,
    }
    _atomic_write(payload)
    return payload


def main() -> int:
    if sys.platform != "linux":
        print("⚠ Снимок server_health рассчитан на Linux (VPS). Пропуск.", file=sys.stderr)
        return 1
    payload = build()
    print(
        f"OK {OUT_PATH} · disk {payload['latest']['disk_used_pct']}% · "
        f"smoke island={payload['latest']['smoke']['island']} stat={payload['latest']['smoke']['stat']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
