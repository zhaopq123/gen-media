#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动前只读体检：不写文件、不打印凭据。

输出四种状态之一：ready / partial / needs_setup / unavailable
退出码：0 ready 或 partial，2 needs_setup，3 unavailable
"""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import medgen_config as cfg

MIN_PYTHON = (3, 8)
EXIT_READY = 0
EXIT_SETUP = 2
EXIT_UNAVAILABLE = 3


def python_ok() -> tuple[bool, str]:
    version = sys.version_info
    ok = (version.major, version.minor) >= MIN_PYTHON
    return ok, f"{version.major}.{version.minor}.{version.micro}"


def network_ok(url: str) -> tuple[bool, str]:
    """只做 DNS/TCP 可达性判断，不发请求、不消耗额度。"""
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        if not host:
            return False, "地址里解析不出主机名"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=5):
            return True, f"{host}:{port} 可达"
    except OSError as exc:
        return False, f"连不上：{exc}"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    report = {"status": "ready", "passed": [], "missing": [], "optional": [], "failed": []}

    ok, version = python_ok()
    if ok:
        report["passed"].append(f"Python {version}")
    else:
        report["failed"].append(f"Python {version} 低于 3.8")

    path = cfg.config_path()
    data = cfg.load()
    rows = cfg.overview(data)
    ready_rows = [row for row in rows if row["ready"]]

    if os.path.isfile(path):
        report["passed"].append(f"配置文件 {path}")
    else:
        report["missing"].append(f"配置文件不存在（先跑 config init）：{path}")

    if ready_rows:
        for row in ready_rows:
            report["passed"].append(f"服务 {row['name']} 已填完整，密钥 {row['key']}")
        target = next((row for row in ready_rows if row["current"]), ready_rows[0])
        ok_net, detail = network_ok(str(target["image_url"] or ""))
        if ok_net:
            report["passed"].append(f"网络 {detail}")
        else:
            report["failed"].append(f"网络 {detail}")
    elif rows:
        for row in rows:
            report["missing"].append(f"服务 {row['name']} 还差：{'、'.join(row['missing'])}")
    else:
        report["missing"].append("还没有填过任何服务")

    if len(ready_rows) > 1:
        names = "、".join(row["name"] for row in ready_rows)
        report["optional"].append(f"有多个可用服务（{names}），生成前先问用户用哪个")

    if report["failed"]:
        report["status"] = "unavailable"
        code = EXIT_UNAVAILABLE
    elif report["missing"]:
        report["status"] = "needs_setup"
        code = EXIT_SETUP
    elif report["optional"]:
        report["status"] = "partial"
        code = EXIT_READY
    else:
        code = EXIT_READY

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
