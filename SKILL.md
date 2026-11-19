---
name: gen-media
description: "生成可直接交付的图片与视频文件。用户说出一张图、画一个、做几张配图、来张封面或海报、做个视频、把这张图做成视频、用这两张做首尾帧、照这个角色生成一段时使用。支持文生图、图生图改图、多图合成、文生视频、首尾帧控制、参考图与参考音频生成。走用户自备的生成 API，首次使用需填写地址与密钥，之后可随时更换服务。不用于只写提示词不出图、视频剪辑拼接转码、图片压缩或格式转换。"
license: MIT
compatibility: "需要 Python 3.8 以上，只用标准库无需安装依赖。需要用户自备任一 OpenAI 兼容图像或视频生成服务的 base URL、模型名与 API 密钥。配置存放于用户主目录的 .media-gen/config.json，多个客户端共用同一份。"
version: 2.0.2
agent_created: true
---

# 出图与出视频

产出的是真实文件——png、jpg、webp 或 mp4，落在本地磁盘上，不是一个链接或一段提示词。

下文的 `$SKILL_DIR` 指本技能目录的绝对路径，按当前环境拼出来。命令在哪个目录执行都可以，脚本自己定位依赖。

## 什么时候用

用户想要一个看得见的结果时用：

- 要图：「生成一张」「画一个」「出几张配图」「做个封面」「来张海报」「这个产品出张宣传图」
- 要改图：「把这张改成夜景」「换成这个风格」「合到一起」「保留构图换个背景」
- 要视频：「做个视频」「生成一段」「把这张图做成视频」「用这两张做首尾帧」「照这个角色生成一段」
- 要动起来：「让这张照片动起来」「做个 5 秒的短片」

不用的场合：只写提示词不出图、视频剪辑拼接转码、图片压缩或格式转换、下载解析已有视频。这些直接做，别套这个技能。

## 开工前：先看配置

```bash
python "$SKILL_DIR/scripts/check_environment.py"
```

返回 `ready` 或 `partial` 就直接干活，不要念配置教程。

返回 `needs_setup` 时按下面走，**一次问完，不要挤牙膏**。需要用户给四样：

1. 生图接口的完整地址
2. 密钥
3. 生图模型名
4. 视频模型名
5. 要出视频的话，再要视频接口地址和视频查询地址

**不要替用户假设用哪家服务，也不要自己拼地址。** 本技能不带任何默认服务商。用户给什么地址就填什么地址，完整照抄，不要拆成域名加路径。用户说不清模型名时，让他去服务商控制台的模型列表里抄。

然后按情况选一条：

**A. 用户自己填（默认，密钥不进对话记录）**

```bash
python "$SKILL_DIR/scripts/media_gen.py" config init
```

把打印出的配置文件路径给用户，请他填四个值：服务地址、密钥、生图模型名、视频模型名。密钥由用户自己贴进文件，不经过对话。

**B. 用户在对话里直接把密钥给了你**

```bash
python "$SKILL_DIR/scripts/media_gen.py" config set --api-key "<用户给的密钥>"
```

写完只回一句「已写入，密钥不回显」，并**必须提醒一次**：这条消息已经进了对话记录，介意的话去平台轮换。

**C. 用户要加第二家服务**

```bash
python "$SKILL_DIR/scripts/media_gen.py" config add 另一家
```

再让他打开配置文件把那条填完整。两家都填好后，生成前先问用哪个。

配完验一次：

```bash
python "$SKILL_DIR/scripts/media_gen.py" config test
```

401/403 是密钥不对，404 是地址或路径不对，402 是余额不足，其余视为可用。哪项失败就带具体报错问那一项，不要重问全部。

**通过后立刻继续用户原来的任务**，不要让用户重述需求，也不要只回一句「配置完成」。

## 有多个 API 时怎么选

配置里可以并存多家服务。`config show` 会列出全部，并标出哪些可用：

```bash
python "$SKILL_DIR/scripts/media_gen.py" config show
```

出现「有 N 个可用服务」时：

1. 生成前先问用户这次用哪个，把名字和各自的模型列出来。
2. 用户没特别要求就用配置里的默认值（标了 `*` 那个），不要为这件事卡住。
3. 用户说了「以后都用某家」，跑 `config use <名字>` 记住，之后不再问。
4. 这次临时换一家，用 `--provider <名字>`，不改默认值。

只有一个可用时就别问，直接用。

## 怎么调用

出图：

```bash
python "$SKILL_DIR/scripts/media_gen.py" image "提示词" -o 输出路径
```

出视频：

```bash
python "$SKILL_DIR/scripts/media_gen.py" video "提示词" -o 输出路径
```

视频时间长，可以拆两段：

```bash
python "$SKILL_DIR/scripts/media_gen.py" video "提示词" --submit-only    # 只提交，打印任务号
python "$SKILL_DIR/scripts/media_gen.py" query <任务号>                   # 查一次状态
python "$SKILL_DIR/scripts/media_gen.py" fetch <任务号> -o 输出路径       # 等完成并取回
```

**stdout 最后一行恒为产物的绝对路径，超时时是任务号。** 过程日志全在 stderr。取最后一行就行，不要解析中间输出。

## 三条不要踩

**一、视频出片要几分钟。** 实测 4 秒的片子约 8 分钟。用户在等的时候不要反复查状态刷屏，也不要因为等不及就重新提交——那会重复扣费。等不下去就 `--submit-only` 拿任务号，回头 `fetch`。

**二、绝不重试提交。** 提交超时、客户端断开、没看到返回，都不代表任务没建成。重提交就是再扣一次钱。正确做法是拿到任务号去 `query`，拿不到任务号就问用户，别自己再来一次。

**三、密钥永不复述。** 任何回复、命令、日志里都不出现完整密钥。`config show` 已经是打码的，不要自己打开配置文件把内容贴给用户看。

## 常用组合

```bash
# 文生图，16:9 的 2K
python "$SKILL_DIR/scripts/media_gen.py" image "深夜便利店，暖光，胶片质感" --size 2K --ratio 16:9 -o a.png

# 图生图：传了 --image 就是改图，本地文件会自动转 Base64
python "$SKILL_DIR/scripts/media_gen.py" image "改成赛博朋克夜景，保留原始构图" --image 原图.png -o b.png

# 多图合成
python "$SKILL_DIR/scripts/media_gen.py" image "把这两个角色放进同一个战斗场景" --image "图1.png,图2.png" -o c.png

# 文生视频，竖屏 5 秒
python "$SKILL_DIR/scripts/media_gen.py" video "机械臂倒咖啡，特写，电影感" --seconds 5 --aspect 9:16 -o v.mp4

# 首尾帧
python "$SKILL_DIR/scripts/media_gen.py" video "人物从首帧走向窗边" --mode keyframe --first 首.png --last 尾.png -o v2.mp4

# 参考图生成；prompt 里用尖括号指代素材，放在引号内不会被 shell 当成重定向
python "$SKILL_DIR/scripts/media_gen.py" video "以 <Picture 1> 的角色为主角在花田奔跑" --mode reference --images 角色.png -o v3.mp4
```

## 参数速查

`image`：

| 参数 | 说明 |
|---|---|
| `--size` | `1K` / `2K` / `3K` / `4K`，或 `1024x768` 这种精确值 |
| `--ratio` | `1:1 3:4 4:3 16:9 9:16 2:3 3:2 21:9` |
| `--image` | 参考图，逗号分隔，支持网址、本地文件、data URI |
| `--b64` | 要 Base64 返回，不落远端链接 |
| `--extract` | 临时覆盖取值路径 |
| `--dump` | 把服务端原始响应打到 stderr |
| `--timeout` | 总等待秒数，默认 900 |

`video`：

| 参数 | 说明 |
|---|---|
| `--mode` | `text` / `keyframe` / `reference` |
| `--seconds` | 4–12 秒，默认 5 |
| `--aspect` | `21:9 16:9 4:3 1:1 3:4 9:16` |
| `--seed` | 随机种子，复现同一结果时用 |
| `--first` / `--last` | 首帧 / 尾帧，keyframe 模式用 |
| `--images` | 参考图，最多 5 张 |
| `--audios` | 参考音频网址，最多 3 段 |
| `--submit-only` | 只提交，打印任务号 |
| `--interval` | 轮询间隔秒数，默认 2 |

通用：`--provider <名字>` 临时换服务，`--api-key` 临时给密钥（不建议，会进命令历史）。

## 出错时怎么看

按退出码分流：

| 码 | 含义 | 怎么处理 |
|---|---|---|
| 0 | 成功 | 取 stdout 最后一行 |
| 2 | 配置或参数缺 | 按提示补，别改代码 |
| 3 | 上游成功但拿不到任务号 | `--dump` 看原始响应，调 `id_pick` |
| 4 | 队列持续满 | 上游高峰，隔几分钟再试 |
| 5 | HTTP 失败 | 看 stderr 的错误体 |
| 6 | 拿不到产物地址 | `--dump` 看字段，用 `--extract` 或写 `pick` |
| 7 | 任务失败 | 看 stderr 里上游给的原因 |
| 8 | 等超时 | stdout 给了任务号，稍后 `fetch` |
| 9 | 本地文件不存在 | 检查 `--image` 或 `--first` 的路径 |

拿不到产物时最快的排查方式：加 `--dump` 再跑一次，照着实际字段用 `--extract` 试，对了再写进配置。

## 需要更多细节

- 配置字段、取值表达式、换服务、接不上怎么调 → `@references/config.md`
- 常见服务商的填法与报错对照 → `@references/providers.md`
- 怎么装到各个客户端、怎么给别人用 → `@references/install.md`
- 密钥怎么弄、怎么验、怎么换、怎么撤销 → `@references/setup-guide.md`

## 能力边界

能接的：任何 OpenAI 兼容的图像 / 视频生成接口，包括各类第三方中转和自建网关。

接不了的：不是 HTTP JSON 协议的（GraphQL、签名鉴权、两步上传换文件 ID、WebSocket 推进度），以及同步阻塞几分钟才返回的接口。遇到这些直接说明并建议换服务，不要硬调。

不做的：视频剪辑、拼接、转码、加字幕、抽帧；图片压缩和格式转换；提示词模板库；批量队列和断点续跑。

产物落盘位置由 `-o` 决定，不给就落在当前工作目录。归档和整理是下游的事，本技能不移动也不删除已有文件。
