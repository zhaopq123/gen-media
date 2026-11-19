# gen-media

让 AI 助手生成真实的图片和视频文件（png / jpg / webp / mp4），而不是只给一段提示词或一个链接。

支持文生图、图生图改图、多图合成、文生视频、首尾帧控制、参考图与参考音频生成。走使用者自己配置的任意 OpenAI 兼容图像/视频接口，本仓库不绑定任何服务商，也不含任何密钥。

## 它能做什么

用户说出「生成一张」「改成夜景」「做个封面」「把这张图做成视频」「用这两张做首尾帧」时，AI 助手直接产出落盘的文件。

只写提示词不出图、视频剪辑转码、图片压缩格式转换这类事不走它。

## 安装

把整个目录放到技能库里，目录名保持 `gen-media`。各客户端的常见位置：

| 客户端 | 目录 |
|---|---|
| Claude Code | `~/.claude/skills/gen-media` |
| Codex | `~/.agents/skills/gen-media` |
| Qoder | `~/.qoder/skills/gen-media` |
| Trae | `~/.trae/skills/gen-media` |
| Cursor | `~/.cursor/skills/gen-media` |
| WorkBuddy | `~/.workbuddy/skills/gen-media` |

详细的多端部署、目录链接和迁移方式见 `references/install.md`。

## 配置

先初始化，再打开生成的配置文件填服务地址、密钥、模型名：

```bash
python scripts/check_environment.py
python scripts/media_gen.py config init
python scripts/media_gen.py config show
python scripts/media_gen.py config test
```

配置文件在用户主目录 `~/.media-gen/config.json`，不在本仓库内，密钥不会随仓库分发。支持多家服务并存、切换和打码查看。配置字段、`style` 请求风格、`--extract` 取值表达式见 `references/config.md`。常见服务商的填法见 `references/providers.md`，密钥申请与安全见 `references/setup-guide.md`。

## 用法

```bash
# 文生图
python scripts/media_gen.py image "深夜便利店，暖光，胶片质感" --size 2K --ratio 16:9 -o a.png

# 图生图：传 --image 即改图，本地文件自动转 Base64
python scripts/media_gen.py image "改成赛博朋克夜景，保留构图" --image 原图.png -o b.png

# 文生视频
python scripts/media_gen.py video "机械臂倒咖啡，特写，电影感" --seconds 5 --aspect 9:16 -o v.mp4

# 长视频：先提交拿任务号，再取回，避免等超时
python scripts/media_gen.py video "提示词" --submit-only
python scripts/media_gen.py query <任务号>
python scripts/media_gen.py fetch <任务号> -o v.mp4
```

`stdout` 最后一行恒为产物绝对路径（超时时为任务号），过程日志走 `stderr`。完整参数见 `SKILL.md`。

## 注意

- 出片通常要几分钟，等待时不要重复提交，会重复计费。
- 提交超时不代表任务没建成，拿任务号去 `query`，不要重提。
- 任何输出都不回显完整密钥。
- 只接 OpenAI 兼容的 HTTP JSON 接口；GraphQL、签名鉴权、两步上传换文件 ID、WebSocket 进度这类接不了。

## 强制走本技能（可选）

把 `assets/rules-snippet.md` 的内容加到项目根目录的 `AGENTS.md`（或客户端对应规则文件），让助手优先选它而不是客户端自带的生成工具。各客户端规则文件位置见 `references/install.md` 第 5 节。

## 许可

自由使用和修改。
