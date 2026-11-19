#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置读写。

地址由使用者按服务商文档原样填写，程序不做任何拼接、不做猜测。
配置在用户主目录 ~/.media-gen/config.json，不进技能目录。
"""
from __future__ import annotations

import copy
import json
import os
import re
import stat

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".media-gen")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

ENV_CONFIG = "MEDIA_GEN_CONFIG"
ENV_KEY = "MEDIA_GEN_API_KEY"
ENV_PROVIDER = "MEDIA_GEN_PROVIDER"

STYLE_NESTED = "nested"
STYLE_OPENAI = "openai"
STYLES = ("auto", STYLE_NESTED, STYLE_OPENAI)

PROVIDER_TEMPLATE = {
    "name": "",
    "api_key": "",
    "image_url": "",
    "video_url": "",
    "query_url": "",
    "image_model": "",
    "video_model": "",
    "style": "auto",
}

REQUIRED_FIELDS = ("api_key", "image_url", "image_model")

FIELD_LABELS = {
    "api_key": "密钥",
    "image_url": "生图接口地址",
    "video_url": "视频接口地址",
    "query_url": "视频查询地址",
    "image_model": "生图模型名",
    "video_model": "视频模型名",
    "style": "请求风格",
}

_FIELD_COMMENTS = {
    "name": "随便起个名字，自己认得出就行",
    "api_key": "密钥，服务商给你的那一串",
    "image_url": "生图接口的完整地址，照文档原样复制",
    "video_url": "视频接口的完整地址，照文档原样复制",
    "query_url": "视频查询地址，里面的 {id} 会替换成任务号",
    "image_model": "生图模型名，去服务商的模型列表里抄",
    "video_model": "视频模型名，只出图可以先留空",
    "style": "请求风格，填 auto、nested 或 openai，不确定就 auto",
}

_FIELD_ORDER = ("name", "api_key", "image_url", "video_url", "query_url",
                "image_model", "video_model", "style")

DEFAULT_IMAGE_PICK = ["data[].url", "data[].b64_json", "data[0].url", "url", "output.url", "images[]"]
DEFAULT_VIDEO_PICK = [
    "url", "video_url", "output.url",
    "video_result[].url", "video_result[0].url",
    "data[].url", "data[0].url",
]
DEFAULT_ID_PICK = ["video_id", "task_id", "id"]
DEFAULT_STATUS_PICK = ["status", "task_status", "state"]
DEFAULT_PROGRESS_PICK = ["progress"]


def default_config() -> dict:
    """空壳，不带任何服务商信息。"""
    return {"current": "", "providers": []}


def config_path() -> str:
    override = (os.environ.get(ENV_CONFIG) or "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return CONFIG_FILE


def _auto_name(url: str) -> str:
    host = re.sub(r"^https?://", "", (url or "").strip()).split("/")[0]
    return host or "我的服务"


def _normalize_provider(raw) -> dict:
    item = copy.deepcopy(PROVIDER_TEMPLATE)
    if isinstance(raw, dict):
        for key in PROVIDER_TEMPLATE:
            value = raw.get(key)
            if isinstance(value, str):
                item[key] = value.strip()
    if item["style"] not in STYLES:
        item["style"] = "auto"
    if not item["name"]:
        item["name"] = _auto_name(item.get("image_url") or item.get("video_url") or "")
    return item


def load() -> dict:
    path = config_path()
    raw = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                raw = json.loads(_strip_comments(handle.read()))
        except (OSError, ValueError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    providers_raw = raw.get("providers")
    providers: list[dict] = []
    if isinstance(providers_raw, list):
        providers = [_normalize_provider(item) for item in providers_raw if isinstance(item, dict)]
    elif isinstance(providers_raw, dict):
        for name, item in providers_raw.items():
            if isinstance(item, dict):
                merged = dict(item)
                merged.setdefault("name", name)
                providers.append(_normalize_provider(merged))

    names = [item["name"] for item in providers]
    current = str(raw.get("current") or "").strip()
    if current not in names:
        current = names[0] if names else ""
    return {"current": current, "providers": providers}


def save(data: dict) -> str:
    path = config_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "current": str(data.get("current") or ""),
        "providers": [_normalize_provider(item) for item in (data.get("providers") or [])],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_render(payload))
    os.replace(tmp, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def find(data: dict, name: str | None = None) -> dict:
    providers = data.get("providers") or []
    if not providers:
        raise KeyError("还没有填过任何服务，先运行 config init")
    target = (name or os.environ.get(ENV_PROVIDER) or data.get("current") or "").strip()
    if not target:
        return providers[0]
    for item in providers:
        if item["name"] == target:
            return item
    names = "、".join(item["name"] for item in providers)
    raise KeyError(f"没有名为 {target} 的服务，现有：{names}")


def resolve_key(conf: dict, cli_key: str | None = None) -> str:
    if cli_key:
        return cli_key.strip()
    env = (os.environ.get(ENV_KEY) or "").strip()
    if env:
        return env
    return str(conf.get("api_key") or "").strip()


def missing_fields(conf: dict, want_video: bool = False) -> list[str]:
    fields = list(REQUIRED_FIELDS)
    if want_video:
        fields += ["video_url", "video_model"]
    return [FIELD_LABELS[field] for field in fields if not str(conf.get(field) or "").strip()]


def detect_style(conf: dict, override: str | None = None) -> str:
    """请求体形状。配置里明确指定优先，auto 时按地址判断。"""
    chosen = (override or conf.get("style") or "auto").strip().lower()
    if chosen in (STYLE_NESTED, STYLE_OPENAI):
        return chosen
    return STYLE_OPENAI


def mask_key(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "未填"
    if len(text) >= 16:
        return f"{text[:3]}…{text[-4:]}"
    if len(text) >= 6:
        return f"…{text[-2:]}"
    return "••••"


def scrub(text: str, key: str) -> str:
    if not key or not text:
        return text
    return text.replace(key, mask_key(key))


def overview(data: dict) -> list[dict]:
    rows = []
    for item in data.get("providers") or []:
        miss = missing_fields(item)
        rows.append({
            "name": item["name"],
            "current": item["name"] == data.get("current"),
            "ready": not miss,
            "key": mask_key(resolve_key(item)),
            "image_url": item.get("image_url") or "",
            "video_url": item.get("video_url") or "",
            "query_url": item.get("query_url") or "",
            "image_model": item.get("image_model") or "",
            "video_model": item.get("video_model") or "",
            "missing": miss,
        })
    return rows


def _strip_comments(text: str) -> str:
    """剥掉 // 与 /* */ 注释，但不碰字符串内部。URL 里的 // 不会被误伤。"""
    out = []
    index = 0
    length = len(text)
    in_string = False
    escaped = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length:
            nxt = text[index + 1]
            if nxt == "/":
                while index < length and text[index] != "\n":
                    index += 1
                continue
            if nxt == "*":
                index += 2
                while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                    index += 1
                index += 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _render(data: dict) -> str:
    """输出带注释的配置文本。第一条带完整说明，后面几条从简。"""
    providers = [_normalize_provider(item) for item in (data.get("providers") or [])]
    lines = ["{"]
    lines.append("  // 默认用哪一条，写下面某个 name")
    lines.append(f'  "current": {json.dumps(str(data.get("current") or ""), ensure_ascii=False)},')
    if not providers:
        lines.append("  // 可以放多条，每条一个服务。只用一个就先跑 config init")
        lines.append('  "providers": []')
        lines.append("}")
        return "\n".join(lines) + "\n"

    lines.append("  // 可以放多条，每条一个服务；只用一个就填第一条")
    lines.append('  "providers": [')
    for index, item in enumerate(providers):
        lines.append("    {")
        for field in _FIELD_ORDER:
            if index == 0:
                lines.append(f"      // {_FIELD_COMMENTS[field]}")
            value = json.dumps(item[field], ensure_ascii=False)
            lines.append(f'      "{field}": {value},')
        lines[-1] = lines[-1][:-1]
        tail = "," if index < len(providers) - 1 else ""
        lines.append(f"    }}{tail}")
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"
