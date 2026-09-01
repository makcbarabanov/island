"""
Отправка в Telegram Bot API. На РФ VPS — через TELEGRAM_PROXY_URL (HTTP или SOCKS5).

Использует curl (если есть) — стабильнее с прокси; иначе urllib + ProxyHandler.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def telegram_proxy_url() -> str | None:
    for key in ("TELEGRAM_PROXY_URL", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return None


def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    proxy = proxy_url if proxy_url is not None else telegram_proxy_url()
    if shutil.which("curl"):
        return _send_curl(token, chat_id, text, proxy)
    return _send_urllib(token, chat_id, text, proxy)


def probe_telegram_api(*, proxy_url: str | None = None) -> tuple[bool, str]:
    proxy = proxy_url if proxy_url is not None else telegram_proxy_url()
    if shutil.which("curl"):
        cmd = ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20"]
        if proxy:
            cmd.extend(["-x", proxy])
        cmd.append("https://api.telegram.org/")
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
            ok = out.isdigit() and int(out) < 500
            return ok, f"curl HTTP {out} proxy={proxy or 'нет'}"
        except subprocess.CalledProcessError as e:
            return False, f"curl failed: {e.output} proxy={proxy or 'нет'}"

    url = "https://api.telegram.org/"
    try:
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        opener = urllib.request.build_opener(*handlers)
        with opener.open(url, timeout=20) as resp:
            return True, f"urllib HTTP {resp.status} proxy={proxy or 'нет'}"
    except Exception as e:
        return False, f"{e} proxy={proxy or 'нет'}"


def _send_curl(token: str, chat_id: str, text: str, proxy: str | None) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    cmd = [
        "curl", "-sS", "-f", "--max-time", "45",
        "-X", "POST", url,
        "--data-urlencode", f"chat_id={chat_id}",
        "--data-urlencode", f"text={text}",
        "-d", "disable_web_page_preview=true",
    ]
    if proxy:
        cmd.extend(["-x", proxy])
    try:
        raw = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise urllib.error.URLError(f"curl Telegram: {e.output}") from e
    data = json.loads(raw)
    if not data.get("ok"):
        raise urllib.error.URLError(f"Telegram API: {data}")
    return data


def _send_urllib(token: str, chat_id: str, text: str, proxy: str | None) -> dict[str, Any]:
    url = "https://api.telegram.org/bot" + urllib.parse.quote(token) + "/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    with opener.open(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))
