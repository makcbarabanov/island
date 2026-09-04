"""
Отправка / чтение Telegram Bot API. На РФ VPS — через TELEGRAM_PROXY_URL (HTTP или SOCKS5).

sendMessage: curl (короткий вызов).
getUpdates: urllib (+ PySocks для SOCKS) — токен не светится в `ps`.
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
from urllib.parse import urlparse


def telegram_proxy_url() -> str | None:
    for key in ("TELEGRAM_PROXY_URL", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return None


def _build_opener(proxy: str | None):
    if not proxy:
        return urllib.request.build_opener()
    parsed = urlparse(proxy)
    scheme = (parsed.scheme or "").lower()
    if scheme.startswith("socks"):
        try:
            import socks
            from sockshandler import SocksiPyHandler
        except ImportError as e:
            raise urllib.error.URLError(
                "Для SOCKS-прокси нужен пакет PySocks (pip install PySocks)"
            ) from e
        host = parsed.hostname or "127.0.0.1"
        port = int(parsed.port or 1080)
        rdns = scheme in ("socks5h", "socks4a")
        return urllib.request.build_opener(
            SocksiPyHandler(socks.SOCKS5, host, port, rdns=rdns)
        )
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )


def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    proxy_url: str | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proxy = proxy_url if proxy_url is not None else telegram_proxy_url()
    # reply_markup требует JSON — urllib path надёжнее curl urlencode
    if reply_markup is not None:
        return telegram_api_call(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "true",
                "reply_markup": reply_markup,
            },
            proxy_url=proxy,
            timeout=45,
        )
    if shutil.which("curl"):
        return _send_curl(token, chat_id, text, proxy)
    return _send_urllib(token, chat_id, text, proxy)


def answer_callback_query(
    token: str,
    callback_query_id: str,
    *,
    text: str | None = None,
    show_alert: bool = False,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "callback_query_id": callback_query_id,
        "show_alert": "true" if show_alert else "false",
    }
    if text:
        params["text"] = text
    return telegram_api_call(
        token, "answerCallbackQuery", params, proxy_url=proxy_url, timeout=30
    )


def edit_telegram_message(
    token: str,
    chat_id: str | int,
    message_id: int,
    text: str,
    *,
    proxy_url: str | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "text": text,
        "disable_web_page_preview": "true",
    }
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    return telegram_api_call(
        token,
        "editMessageText",
        params,
        proxy_url=proxy_url,
        timeout=45,
    )


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

    try:
        opener = _build_opener(proxy)
        with opener.open("https://api.telegram.org/", timeout=20) as resp:
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
    opener = _build_opener(proxy)
    with opener.open(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def telegram_api_call(
    token: str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    proxy_url: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Bot API через urllib (токен не в argv процесса)."""
    proxy = proxy_url if proxy_url is not None else telegram_proxy_url()
    params = dict(params or {})
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = urllib.parse.urlencode(
        {
            k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
            for k, v in params.items()
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    opener = _build_opener(proxy)
    with opener.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("ok"):
        raise urllib.error.URLError(f"Telegram API {method}: {data}")
    return data


def get_telegram_updates(
    token: str,
    *,
    offset: int | None = None,
    timeout: int = 25,
    limit: int = 100,
    allowed_updates: list[str] | None = None,
    proxy_url: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "timeout": int(timeout),
        "limit": max(1, min(int(limit), 100)),
    }
    if offset is not None:
        params["offset"] = int(offset)
    if allowed_updates is not None:
        params["allowed_updates"] = list(allowed_updates)
    data = telegram_api_call(
        token,
        "getUpdates",
        params,
        proxy_url=proxy_url,
        timeout=max(int(timeout) + 20, 45),
    )
    return list(data.get("result") or [])
