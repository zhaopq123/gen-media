#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""所有出网动作收口在这里：鉴权注入、错误解析、退避、探活、下载。"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "gen-media-skill/1.0"

# 503 队列满与 429 限流都按「等一下再来」处理，其余 5xx 只重试一次
RETRY_MAX = 2
BACKOFF_MIN = 1.0
BACKOFF_MAX = 30.0


class NetError(Exception):
    """带可读原因的网络失败。"""

    def __init__(self, message: str, status: int | None = None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def _apply_auth(url: str, headers: dict, auth: dict, api_key: str) -> str:
    """按配置把凭据放到 header 或 query。"""
    auth = auth or {}
    where = str(auth.get("in") or "header").lower()
    name = str(auth.get("name") or "Authorization")
    prefix = str(auth.get("prefix") or "")
    if not api_key:
        return url
    if where == "query":
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urllib.parse.urlencode({name: api_key})}"
    headers[name] = f"{prefix}{api_key}"
    return url


def request(url: str, *, method: str = "GET", body: dict | None = None,
            auth: dict | None = None, api_key: str = "",
            timeout: float = 120.0, retry: bool = True,
            accept_json: bool = True):
    """发一次请求。返回 (status, headers, payload)。

    payload 是解析后的 JSON；服务端回非 JSON 时返回原始字节，由调用方决定写盘。
    """
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    target = _apply_auth(url, headers, auth or {}, api_key)

    attempts = RETRY_MAX if retry else 1
    last_error: Exception | None = None
    wait = BACKOFF_MIN
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(target, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if accept_json and "json" in ctype.lower():
                    try:
                        return resp.status, dict(resp.headers), json.loads(raw.decode("utf-8", "replace"))
                    except ValueError:
                        return resp.status, dict(resp.headers), raw
                return resp.status, dict(resp.headers), raw
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            payload = None
            try:
                payload = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                payload = raw.decode("utf-8", "replace")
            status = exc.code
            reason = ""
            if isinstance(payload, dict):
                reason = str(payload.get("code") or "")
            transient = status == 429 or (status == 503 and "queue_full" in reason) or 500 <= status < 600
            if transient and attempt < attempts:
                time.sleep(wait + random.uniform(0, wait * 0.3))
                wait = min(wait * 2, BACKOFF_MAX)
                continue
            return status, dict(exc.headers or {}), payload
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(wait + random.uniform(0, wait * 0.3))
                wait = min(wait * 2, BACKOFF_MAX)
                continue
            raise NetError(f"连不上 {urllib.parse.urlparse(target).netloc}：{exc}") from exc
    raise NetError(f"请求失败：{last_error}")


def err_text(payload) -> str:
    """三种错误体都要认。

    {"error":{code,message,type}} / {"code":..,"message":..} / {"detail":"..."}
    """
    if isinstance(payload, dict):
        inner = payload.get("error")
        if isinstance(inner, dict) and inner.get("message"):
            return str(inner["message"])
        for field in ("detail", "message", "code"):
            value = payload.get(field)
            if value:
                return str(value)
        return json.dumps(payload, ensure_ascii=False)[:300]
    if isinstance(payload, bytes):
        return payload[:300].decode("utf-8", "replace")
    return str(payload)[:300]


def is_queue_full(payload) -> bool:
    return isinstance(payload, dict) and "queue_full" in str(payload.get("code") or "")


def download(url: str, out_path: str, timeout: float = 300.0) -> str:
    """流式下载到本地。不把 API key 带进下载请求，避免落进访问日志。"""
    out_path = os.path.abspath(os.path.expanduser(out_path))
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = out_path + ".part"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as handle:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                handle.write(chunk)
        os.replace(tmp, out_path)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise NetError(f"下载产物失败：{exc}") from exc
    return out_path


def probe(urls, auth: dict, api_key: str) -> dict:
    """只读探活：按顺序试候选地址，返回第一个能说明问题的结果。

    优先用模型列表这类只读端点；都不存在时再试生成端点。
    全程 GET，不提交任务，不产生计费。
    """
    if isinstance(urls, str):
        urls = [urls]
    last = {"ok": False, "status": None, "verdict": "unreachable", "detail": "没有可探测的地址"}
    for url in urls:
        try:
            status, _, payload = request(url, auth=auth, api_key=api_key, timeout=20.0, retry=False)
        except NetError as exc:
            last = {"ok": False, "status": None, "verdict": "unreachable", "detail": str(exc)}
            continue
        if status in (401, 403):
            return {"ok": False, "status": status, "verdict": "auth", "detail": err_text(payload)}
        if status == 402:
            return {"ok": False, "status": status, "verdict": "quota", "detail": err_text(payload)}
        if status == 404:
            last = {"ok": False, "status": status, "verdict": "path", "detail": err_text(payload)}
            continue
        return {"ok": True, "status": status, "verdict": "reachable", "detail": err_text(payload)}
    return last
