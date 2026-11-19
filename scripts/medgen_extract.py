#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从各家不同形状的响应里取出图片/视频地址。

表达式语法刻意做小，只有两条规则：
  a.b.c     逐层取键
  a[].b     取到列表后对每一项继续取
不支持数字下标；需要「第一项」时用 [] 也一样，取到的第一个就是。
"""
from __future__ import annotations

import base64
import binascii
import re

URL_PREFIXES = ("http://", "https://", "data:")
B64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")

CANDIDATE_PATHS = [
    "data[].url",
    "data[].b64_json",
    "data[0].url",
    "data.0.url",
    "url",
    "video_url",
    "image_url",
    "output.url",
    "result.url",
    "data.url",
    "images[]",
    "data[].video_url",
]


def _walk(node, segments):
    """按分段下降，返回所有命中的叶子值（列表）。"""
    if not segments:
        if isinstance(node, list):
            out = []
            for item in node:
                out.extend(_walk(item, []))
            return out
        return [node]
    head, rest = segments[0], segments[1:]
    expand = head.endswith("[]")
    key = head[:-2] if expand else head
    if key:
        if not isinstance(node, dict) or key not in node:
            return []
        node = node[key]
    if expand:
        if not isinstance(node, list):
            return []
        out = []
        for item in node:
            out.extend(_walk(item, rest))
        return out
    return _walk(node, rest)


def resolve(expr: str, payload) -> list:
    """按表达式取值，取不到返回空列表。"""
    if not expr or not isinstance(expr, str):
        return []
    segments = [part for part in expr.strip().split(".") if part]
    if not segments:
        return []
    try:
        return _walk(payload, segments)
    except (TypeError, KeyError, IndexError):
        return []


def _is_remote(text: str) -> bool:
    return text.startswith(URL_PREFIXES)


def _looks_like_b64(text: str) -> bool:
    if len(text) < 200:
        return False
    sample = text.strip()
    return bool(B64_RE.match(sample))


def _normalize_data_uri(text: str) -> tuple[str, str] | None:
    """data:image/png;base64,xxxx → (mime, b64)。"""
    match = re.match(r"^data:([^;,]+);base64,(.*)$", text, re.S)
    if not match:
        return None
    return match.group(1), match.group(2)


def pick_artifacts(payload, paths: list[str], want_b64: bool = False) -> list[dict]:
    """按路径列表依次尝试，返回 [{kind, value}]；kind 为 url 或 b64。"""
    ordered = [p for p in (paths or []) if p] + CANDIDATE_PATHS
    seen_expressions = set()
    found: list[dict] = []
    seen_values = set()
    for expr in ordered:
        if expr in seen_expressions:
            continue
        seen_expressions.add(expr)
        declared_b64 = "b64" in expr.lower()
        for value in resolve(expr, payload):
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text or text in seen_values:
                continue
            if _is_remote(text):
                seen_values.add(text)
                found.append({"kind": "url", "value": text})
                continue
            if declared_b64 or _looks_like_b64(text):
                seen_values.add(text)
                found.append({"kind": "b64", "value": text})
        if found and not want_b64:
            break
        if found and want_b64 and any(item["kind"] == "b64" for item in found):
            break
    return found


def pick_first(payload, paths: list[str]) -> str:
    """取单个标量（id、状态、进度）。"""
    ordered = [p for p in (paths or []) if p]
    for expr in ordered:
        for value in resolve(expr, payload):
            if isinstance(value, bool):
                continue
            if isinstance(value, (str, int, float)) and str(value).strip():
                return str(value).strip()
    return ""


def decode_b64(text: str) -> bytes:
    """容忍换行与缺少 padding 的 base64。"""
    cleaned = "".join(text.split())
    padding = (-len(cleaned)) % 4
    if padding:
        cleaned += "=" * padding
    try:
        return base64.b64decode(cleaned)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"base64 解码失败：{exc}") from exc


def guess_extension(mime: str) -> str:
    table = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }
    return table.get((mime or "").lower(), "")
