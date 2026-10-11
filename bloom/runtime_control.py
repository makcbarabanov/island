"""
Состояние управления Bloom (файл, без миграций БД).

Инвариант: пауза администрирования НЕ останавливает ingest / журнал.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
STATE_PATH = Path(__file__).resolve().parent / "runtime_state.json"
INGEST_UNIT = "bloom-telegram-ingest.service"

_DEFAULT: dict[str, Any] = {
    "admin_paused": False,
    "full_stopped": False,
    "updated_at": None,
    "updated_by": None,
}


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return dict(_DEFAULT)
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(_DEFAULT)
        out = dict(_DEFAULT)
        out.update(data)
        return out
    except Exception:
        return dict(_DEFAULT)


def save_state(state: dict[str, Any], *, by: str | None = None) -> dict[str, Any]:
    out = dict(_DEFAULT)
    out.update(state)
    out["updated_at"] = datetime.now(MSK).isoformat(timespec="seconds")
    if by:
        out["updated_by"] = by
    STATE_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def is_admin_paused() -> bool:
    st = load_state()
    return bool(st.get("admin_paused")) or bool(st.get("full_stopped"))


def is_full_stopped() -> bool:
    return bool(load_state().get("full_stopped"))


def set_admin_paused(paused: bool, *, by: str = "admin") -> dict[str, Any]:
    st = load_state()
    st["admin_paused"] = bool(paused)
    if not paused:
        # снятие паузы не снимает full_stopped — для full_stop отдельный путь
        pass
    return save_state(st, by=by)


def set_full_stopped(stopped: bool, *, by: str = "admin") -> dict[str, Any]:
    st = load_state()
    st["full_stopped"] = bool(stopped)
    if stopped:
        st["admin_paused"] = True
    return save_state(st, by=by)


def ingest_is_active() -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", INGEST_UNIT],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return (r.stdout or "").strip() == "active"
    except Exception:
        return False


def ingest_restart() -> tuple[bool, str]:
    """Перезапуск только ingest. Не меняет admin_paused."""
    try:
        r = subprocess.run(
            ["systemctl", "--user", "restart", INGEST_UNIT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip() or f"rc={r.returncode}"
            return False, err
        # дать подняться
        import time

        time.sleep(2)
        if ingest_is_active():
            return True, "active"
        return False, "restart ok, but not active"
    except Exception as e:
        return False, str(e)


def ingest_stop() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "stop", INGEST_UNIT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "").strip() or f"rc={r.returncode}"
        return True, "stopped"
    except Exception as e:
        return False, str(e)


def schedule_ingest_restart_after_reply() -> None:
    """
    Рестарт изнутри ingest-процесса: сначала ответ уйдёт, потом unit перезапустится.
    """
    cmd = (
        "sleep 2; "
        f"systemctl --user restart {INGEST_UNIT} "
        ">>/home/makc/Apps/island/logs/bloom_ingest.log 2>&1"
    )
    subprocess.Popen(
        ["bash", "-c", cmd],
        start_new_session=True,
        env=os.environ.copy(),
    )
