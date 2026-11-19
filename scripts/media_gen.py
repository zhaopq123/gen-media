#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen-media 命令入口：出图、出视频、查任务、取产物、配置。

产物路径或任务号打印在 stdout 最后一行，其余过程信息走 stderr。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import medgen_config as cfg
import medgen_extract as extract
import medgen_net as net

IMAGE_RATIOS = ("1:1", "3:4", "4:3", "16:9", "9:16", "2:3", "3:2", "21:9")
VIDEO_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
DONE_WORDS = {"completed", "succeeded", "success", "done", "finished"}
FAIL_WORDS = {"failed", "fail", "error", "cancelled", "canceled", "rejected"}

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_NO_ID = 3
EXIT_QUEUE_FULL = 4
EXIT_HTTP = 5
EXIT_NO_ARTIFACT = 6
EXIT_TASK_FAILED = 7
EXIT_TIMEOUT = 8
EXIT_LOCAL_FILE = 9


def log(message: str = "") -> None:
    print(message, file=sys.stderr, flush=True)


def emit(path: str) -> None:
    print(path, flush=True)


def die(code: int, message: str) -> None:
    log(message)
    raise SystemExit(code)


def to_media_ref(value: str) -> str:
    """网址和 data URI 原样用；本地文件转 data URI。"""
    text = (value or "").strip()
    if text.startswith(("http://", "https://", "data:")):
        return text
    path = os.path.abspath(os.path.expanduser(text))
    if not os.path.isfile(path):
        die(EXIT_LOCAL_FILE, f"找不到文件，也不是网址：{text}")
    suffix = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(suffix, suffix)
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    log(f"[本地文件转 Base64] {os.path.basename(path)}")
    return f"data:image/{mime};base64,{encoded}"


def split_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def context(args, want_video: bool = False):
    """取配置、服务与密钥。缺项时给出能照做的指引。"""
    data = cfg.load()
    try:
        conf = cfg.find(data, getattr(args, "provider", None))
    except KeyError as exc:
        die(EXIT_CONFIG, "\n".join([
            str(exc),
            f"配置文件：{cfg.config_path()}",
            "初始化：python media_gen.py config init",
        ]))

    key = cfg.resolve_key(conf, getattr(args, "api_key", None))
    missing = cfg.missing_fields(conf, want_video=want_video)
    if not key and "密钥" not in missing:
        missing.append("密钥")
    if missing:
        die(EXIT_CONFIG, "\n".join([
            f"服务 [{conf['name']}] 还差：{'、'.join(missing)}",
            f"配置文件：{cfg.config_path()}",
            "两种填法：",
            "  1) 直接打开上面的文件填（密钥不进对话记录）",
            f"  2) 让助手代写：python media_gen.py config set --api-key <密钥>",
        ]))
    return data, conf, key


# ---------------------------------------------------------------- 生图
def cmd_image(args) -> int:
    data, conf, key = context(args)
    style = cfg.detect_style(conf, getattr(args, "style", None))
    size = args.size or "1K"
    refs = [to_media_ref(item) for item in split_list(args.image)]

    body: dict = {"model": conf["image_model"], "prompt": args.prompt, "size": size}
    if style == cfg.STYLE_NESTED:
        if args.ratio:
            body["ratio"] = args.ratio
        inner: dict = {}
        if args.b64:
            body["return_base64"] = True
        else:
            inner["response_format"] = "url"
        if refs:
            inner["image"] = refs
            if args.b64:
                inner["response_format"] = "b64_json"
        if inner:
            body["extra_body"] = inner
    else:
        if refs:
            body["image"] = refs if len(refs) > 1 else refs[0]
        if args.b64:
            body["response_format"] = "b64_json"

    url = conf["image_url"]
    log(f"[提交] {conf['name']} 出图 · {conf['image_model']} · size={size}" + (f" ratio={args.ratio}" if args.ratio else ""))
    log(f"[端点] POST {url}")

    started = time.time()
    try:
        status, _, payload = net.request(url, method="POST", body=body,
                                        api_key=key, timeout=args.timeout)
    except net.NetError as exc:
        die(EXIT_HTTP, f"[失败] {exc}")

    if args.dump:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        log("[响应原文] " + cfg.scrub(text[:4000], key))

    if status != 200:
        die(EXIT_HTTP, f"[失败] HTTP {status}：{cfg.scrub(net.err_text(payload), key)}")

    if isinstance(payload, bytes):
        out = args.out or os.path.join(os.getcwd(), f"gen_media_{int(time.time())}.png")
        out = os.path.abspath(os.path.expanduser(out))
        parent = os.path.dirname(out)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out, "wb") as handle:
            handle.write(payload)
        log(f"[完成] {time.time() - started:.1f}s，服务端直接回了二进制")
        emit(out)
        return EXIT_OK

    picks = split_list(args.extract) or cfg.DEFAULT_IMAGE_PICK
    artifacts = extract.pick_artifacts(payload, picks, want_b64=args.b64)
    if not artifacts:
        die(EXIT_NO_ARTIFACT, "\n".join([
            "[异常] 请求成功，但响应里找不到图片地址。",
            "加 --dump 看服务端原文，再按实际字段用 --extract 指定，例如 --extract data[].url",
        ]))

    log(f"[完成] {time.time() - started:.1f}s，共 {len(artifacts)} 个产物")
    saved = []
    stamp = int(time.time())
    for index, item in enumerate(artifacts, 1):
        if args.out:
            if len(artifacts) == 1:
                path = args.out
            else:
                root, suffix = os.path.splitext(args.out)
                path = f"{root}_{index}{suffix or '.png'}"
        else:
            path = os.path.join(os.getcwd(), f"gen_media_{stamp}_{index}.png")
        path = os.path.abspath(os.path.expanduser(path))
        if item["kind"] == "url":
            try:
                net.download(item["value"], path)
            except net.NetError as exc:
                die(EXIT_HTTP, f"[失败] {exc}")
        else:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(extract.decode_b64(item["value"]))
        saved.append(path)
        log(f"[已保存] {path}")

    for path in saved:
        emit(path)
    return EXIT_OK


# ---------------------------------------------------------------- 视频
def cmd_video(args) -> int:
    data, conf, key = context(args)
    style = cfg.detect_style(conf, getattr(args, "style", None))

    if args.mode == "keyframe":
        if not (args.first or args.last):
            die(EXIT_CONFIG, "首尾帧模式至少要给 --first 或 --last")
        if style != cfg.STYLE_NESTED:
            log("[提示] 当前服务不一定支持首尾帧，素材可能被忽略")
    if args.mode == "reference":
        images = split_list(args.images)
        audios = split_list(args.audios)
        if not images and not audios:
            die(EXIT_CONFIG, "参考模式至少要给 --images 或 --audios")
        if len(images) > 5:
            die(EXIT_CONFIG, f"参考图最多 5 张，当前 {len(images)} 张")
        if len(audios) > 3:
            die(EXIT_CONFIG, f"参考音频最多 3 段，当前 {len(audios)} 段")

    body: dict = {"model": conf["video_model"], "prompt": args.prompt}
    if style == cfg.STYLE_NESTED:
        body["mode"] = args.mode
        body["size"] = "720P"
        body["seconds"] = str(args.seconds)
        body["n"] = 1
        body["aspect_ratio"] = args.aspect
        if args.seed is not None:
            body["seed"] = args.seed
        if args.mode == "keyframe":
            if args.first:
                body["first_frame"] = to_media_ref(args.first)
            if args.last:
                body["last_frame"] = to_media_ref(args.last)
        elif args.mode == "reference":
            images = [to_media_ref(item) for item in split_list(args.images)]
            audios = split_list(args.audios)
            if images:
                body["images"] = images
            if audios:
                body["audios"] = audios
    else:
        # 通用形态只发最小集：模型、提示词、可选参考图。
        # 时长、分辨率各家要求不一样，hardcode 进去必然有一家报 400，交给服务端默认。
        if args.mode != "text":
            ref = args.first or (split_list(args.images)[0] if split_list(args.images) else None)
            if ref:
                body["image_url"] = to_media_ref(ref)
                log(f"[参考图] 已作为 image_url 提交")
            else:
                log(f"[提示] mode={args.mode} 没给素材，按纯文本提交")
        if args.seed is not None:
            body["seed"] = args.seed

    url = conf["video_url"]
    log(f"[提交] {conf['name']} 出视频 · {conf['video_model']} · {args.seconds}s · {args.aspect}")
    log(f"[端点] POST {url}")

    deadline = time.time() + min(args.timeout, 300)
    attempt = 0
    while True:
        attempt += 1
        try:
            status, _, payload = net.request(url, method="POST", body=body,
                                            api_key=key, timeout=min(args.timeout, 180), retry=False)
        except net.NetError as exc:
            die(EXIT_HTTP, f"[失败] {exc}")

        if args.dump:
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
            log("[响应原文] " + cfg.scrub(text[:4000], key))

        if status == 200 and not isinstance(payload, bytes):
            task_id = extract.pick_first(payload, cfg.DEFAULT_ID_PICK)
            if task_id:
                log(f"[提交成功] 任务号 {task_id}")
                return finish_submit(args, conf, key, style, task_id)
            die(EXIT_NO_ID, f"[异常] 提交成功但拿不到任务号：{cfg.scrub(net.err_text(payload), key)}")

        if net.is_queue_full(payload):
            if time.time() > deadline:
                die(EXIT_QUEUE_FULL, "[放弃] 上游队列持续满载，稍后再试")
            wait = min(8.0 * attempt, 60.0)
            log(f"[排队] 上游队列已满，{wait:.0f}s 后重试（第 {attempt} 次）")
            time.sleep(wait)
            continue

        die(EXIT_HTTP, f"[提交失败] HTTP {status}：{cfg.scrub(net.err_text(payload), key)}")


def video_status(conf: dict, key: str, style: str, task_id: str) -> dict:
    """查询地址完全来自配置，只把 {id} 换成任务号，不做任何拼接。"""
    query_url = str(conf.get("query_url") or "").strip()
    if not query_url:
        return {"status": "error", "detail": "配置里没填视频查询地址（query_url）"}
    url = query_url.replace("{id}", task_id)
    try:
        status, _, payload = net.request(url, api_key=key, timeout=30.0, retry=False)
    except net.NetError as exc:
        return {"status": "error", "detail": str(exc)}
    if status == 200 and isinstance(payload, dict):
        return payload
    return {"status": "error", "detail": net.err_text(payload), "http": status}


def finish_submit(args, conf: dict, key: str, style: str, task_id: str) -> int:
    if args.submit_only:
        emit(task_id)
        return EXIT_OK
    out = args.out or os.path.join(os.getcwd(), f"gen_media_{task_id[:8]}.mp4")
    return wait_video(args, conf, key, style, task_id, out)


def wait_video(args, conf: dict, key: str, style: str, task_id: str, out_path: str) -> int:
    pick = split_list(getattr(args, "extract", None)) or cfg.DEFAULT_VIDEO_PICK
    interval = float(getattr(args, "interval", 2.0) or 2.0)
    deadline = time.time() + float(getattr(args, "timeout", 900.0) or 900.0)

    last_line = ""
    while True:
        info = video_status(conf, key, style, task_id)
        state = extract.pick_first(info, cfg.DEFAULT_STATUS_PICK).lower()
        progress = extract.pick_first(info, cfg.DEFAULT_PROGRESS_PICK)
        line = f"{state or '未知'}{' ' + progress if progress else ''}"
        if line != last_line:
            log(f"[状态] {line}")
            last_line = line

        if state in DONE_WORDS:
            artifacts = extract.pick_artifacts(info, pick)
            if not artifacts:
                die(EXIT_NO_ARTIFACT, "[异常] 任务已完成但取不到视频地址，加 --dump 看字段")
            target = os.path.abspath(os.path.expanduser(out_path))
            item = artifacts[0]
            if item["kind"] == "url":
                try:
                    net.download(item["value"], target)
                except net.NetError as exc:
                    die(EXIT_HTTP, f"[失败] {exc}")
            else:
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(extract.decode_b64(item["value"]))
            log(f"[已保存] {target}")
            emit(target)
            return EXIT_OK

        if state in FAIL_WORDS:
            die(EXIT_TASK_FAILED, "[失败] " + cfg.scrub(json.dumps(info, ensure_ascii=False)[:400], key))

        if time.time() > deadline:
            log("[超时] 等太久了，任务还在上游。稍后这样取回：")
            log(f"  python media_gen.py fetch {task_id} -o <输出路径>")
            emit(task_id)
            return EXIT_TIMEOUT

        time.sleep(interval)


def cmd_query(args) -> int:
    data, conf, key = context(args)
    style = cfg.detect_style(conf, getattr(args, "style", None))
    info = video_status(conf, key, style, args.task_id)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return EXIT_OK if str(info.get("status", "")).lower() != "error" else EXIT_HTTP


def cmd_fetch(args) -> int:
    data, conf, key = context(args)
    style = cfg.detect_style(conf, getattr(args, "style", None))
    out = args.out or os.path.join(os.getcwd(), f"gen_media_{args.task_id[:8]}.mp4")
    return wait_video(args, conf, key, style, args.task_id, out)


# ---------------------------------------------------------------- 配置
def _print_show(data: dict) -> None:
    path = cfg.config_path()
    rows = cfg.overview(data)
    ready = [row for row in rows if row["ready"]]
    print(f"配置文件：{path}")
    print(f"文件存在：{'是' if os.path.isfile(path) else '否（还没跑过 config init）'}")
    print("")
    if not rows:
        print("还没有填过任何服务。运行 config init 生成模板。")
        return
    for row in rows:
        mark = "*" if row["current"] else " "
        state = "可用" if row["ready"] else "缺 " + "、".join(row["missing"])
        print(f" {mark} {row['name']}")
        print(f"     生图 {row['image_url'] or '（未填）'}")
        print(f"     视频 {row['video_url'] or '（未填）'}")
        print(f"     生图 {row['image_model'] or '（未填）'}   视频 {row['video_model'] or '（未填）'}")
        print(f"     密钥 {row['key']}   状态 {state}")
    print("")
    if not ready:
        print("还差：至少一个填完整的服务")
    elif len(ready) > 1:
        print(f"有 {len(ready)} 个可用服务，生成前先问用哪个；选定后 config use <名字> 记住")
    else:
        print("可以直接开始生成")


def cmd_config(args) -> int:
    action = args.action
    data = cfg.load()

    if action == "init":
        path = cfg.config_path()
        if os.path.isfile(path) and not args.force:
            log(f"配置已存在：{path}")
            log("要重建加 --force；只换密钥用 config set --api-key")
            return EXIT_CONFIG
        data = {
            "current": "我的服务",
            "providers": [{
                "name": "我的服务",
                "api_key": "",
                "image_url": "",
                "video_url": "",
                "query_url": "",
                "image_model": "",
                "video_model": "",
                "style": "auto",
            }],
        }
        written = cfg.save(data)
        log(f"[已生成] {written}")
        log("打开这个文件，填四个值：服务地址、密钥、生图模型名、视频模型名")
        log("填完运行 config test 验证")
        emit(written)
        return EXIT_OK

    if action == "add":
        name = (args.name or "").strip()
        if not name:
            die(EXIT_CONFIG, "加一条要起名字，例如 config add 我的另一家")
        if any(item["name"] == name for item in data.get("providers") or []):
            die(EXIT_CONFIG, f"已经有一条叫 {name} 了")
        data.setdefault("providers", []).append({
            "name": name, "api_key": "", "image_url": "", "video_url": "",
            "query_url": "", "image_model": "", "video_model": "", "style": "auto",
        })
        cfg.save(data)
        log(f"[已添加] {name}；打开配置文件把它填完整")
        return EXIT_OK

    if action == "show":
        _print_show(data)
        return EXIT_OK

    if action == "use":
        if not args.name:
            die(EXIT_CONFIG, "要指定用哪一条，例如 config use 我的服务")
        try:
            cfg.find(data, args.name)
        except KeyError as exc:
            die(EXIT_CONFIG, str(exc))
        data["current"] = args.name
        cfg.save(data)
        log(f"[已切换] 默认服务 → {args.name}")
        return EXIT_OK

    if action == "set":
        try:
            conf = cfg.find(data, args.provider)
        except KeyError as exc:
            die(EXIT_CONFIG, str(exc))
        changed = []
        mapping = {
            "api_key": "api_key", "image_url": "image_url", "video_url": "video_url",
            "query_url": "query_url",
            "image_model": "image_model", "video_model": "video_model", "name": "name",
        }
        for attr, field in mapping.items():
            value = getattr(args, attr, None)
            if value:
                conf[field] = value.strip()
                changed.append(field)
        if not changed:
            die(EXIT_CONFIG, "没有要改的项，用 --api-key / --base-url / --image-model / --video-model")
        cfg.save(data)
        shown = cfg.mask_key(conf.get("api_key") or "") if "api_key" in changed else ""
        log(f"[已更新] {conf['name']} 的 {'、'.join(changed)}" + (f"；密钥不回显（{shown}）" if shown else ""))
        return EXIT_OK

    if action == "test":
        try:
            conf = cfg.find(data, args.provider)
        except KeyError as exc:
            die(EXIT_CONFIG, str(exc))
        key = cfg.resolve_key(conf, args.api_key)
        missing = cfg.missing_fields(conf)
        if missing:
            die(EXIT_CONFIG, f"[{conf['name']}] 还差：{'、'.join(missing)}")
        result = net.probe([
            str(conf.get("image_url") or "").strip(),
        ], {}, key)
        verdicts = {
            "reachable": "通，地址和密钥都被接受了",
            "auth": "密钥不对或没有权限",
            "path": "地址能连上，但找不到可探测的端点，确认服务地址是否写全",
            "quota": "余额或配额不足",
            "unreachable": "连不上，检查网络和地址",
        }
        log(f"[{conf['name']}] {verdicts.get(result['verdict'], result['verdict'])}（HTTP {result['status']}）")
        if result.get("detail"):
            log("  服务端说：" + cfg.scrub(str(result["detail"]), key))
        return EXIT_OK if result["ok"] else EXIT_HTTP

    die(EXIT_CONFIG, f"不认识的配置动作：{action}")


# ---------------------------------------------------------------- 参数
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media_gen",
        description="出图 / 出视频：对接任意 OpenAI 兼容的图像与视频生成服务",
    )
    parser.add_argument("--provider", help="临时指定哪一条服务，覆盖默认值")
    parser.add_argument("--api-key", help="临时指定密钥，优先于配置文件")
    parser.add_argument("--style", choices=["nested", "openai"], help="强制请求风格，默认自动判断")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(node):
        node.add_argument("--timeout", type=float, default=900.0, help="总等待秒数，默认 900")
        node.add_argument("--dump", action="store_true", help="把服务端原始响应打到 stderr")
        node.add_argument("--extract", help="临时覆盖取值路径，逗号分隔，如 data[].url")

    img = sub.add_parser("image", help="出图 / 图生图 / 多图合成")
    img.add_argument("prompt")
    img.add_argument("-o", "--out", help="输出路径；多张时自动加序号")
    img.add_argument("--size", help="尺寸，形如 1K/2K/3K/4K 或 1024x768")
    img.add_argument("--ratio", choices=IMAGE_RATIOS, help="画幅比例")
    img.add_argument("--image", help="参考图，逗号分隔，支持网址或本地文件；传了就是改图")
    img.add_argument("--b64", action="store_true", help="要 Base64 返回而不是网址")
    add_common(img)
    img.set_defaults(func=cmd_image)

    vid = sub.add_parser("video", help="出视频 / 首尾帧 / 参考图与音频")
    vid.add_argument("prompt")
    vid.add_argument("-o", "--out", help="输出 mp4 路径")
    vid.add_argument("--mode", default="text", choices=["text", "keyframe", "reference"])
    vid.add_argument("--seconds", default=5, type=int, help="时长 4-12 秒，默认 5")
    vid.add_argument("--aspect", default="16:9", choices=VIDEO_RATIOS, help="画幅，默认 16:9")
    vid.add_argument("--seed", type=int)
    vid.add_argument("--first", help="首帧，网址或本地文件")
    vid.add_argument("--last", help="尾帧，网址或本地文件")
    vid.add_argument("--images", help="参考图，逗号分隔，最多 5 张")
    vid.add_argument("--audios", help="参考音频网址，逗号分隔，最多 3 段")
    vid.add_argument("--submit-only", action="store_true", help="只提交，打印任务号")
    vid.add_argument("--interval", type=float, default=2.0, help="轮询间隔秒数")
    add_common(vid)
    vid.set_defaults(func=cmd_video)

    query = sub.add_parser("query", help="查一次任务状态")
    query.add_argument("task_id")
    query.set_defaults(func=cmd_query, dump=False, extract=None, timeout=60.0)

    fetch = sub.add_parser("fetch", help="等任务完成并取回产物")
    fetch.add_argument("task_id")
    fetch.add_argument("-o", "--out")
    fetch.add_argument("--interval", type=float, default=2.0)
    add_common(fetch)
    fetch.set_defaults(func=cmd_fetch)

    conf = sub.add_parser("config", help="查看和修改配置")
    conf.add_argument("action", choices=["init", "add", "show", "use", "set", "test"])
    conf.add_argument("name", nargs="?", help="config add / use 的名字")
    conf.add_argument("--force", action="store_true", help="init 时覆盖已有配置")
    conf.add_argument("--provider", help="set / test 针对哪一条")
    conf.add_argument("--api-key", dest="api_key")
    conf.add_argument("--image-url", dest="image_url")
    conf.add_argument("--video-url", dest="video_url")
    conf.add_argument("--query-url", dest="query_url")
    conf.add_argument("--image-model", dest="image_model")
    conf.add_argument("--video-model", dest="video_model")
    conf.set_defaults(func=cmd_config, dump=False, extract=None, timeout=60.0)

    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("已中断")
        return 130
    except net.NetError as exc:
        log(f"[失败] {exc}")
        return EXIT_HTTP


if __name__ == "__main__":
    raise SystemExit(main())
