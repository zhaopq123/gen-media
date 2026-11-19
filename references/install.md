# 安装与迁移

## 1 单一真相源

技能本体只维护一份，放在你自己的技能库目录。下文的 `$SKILL_SRC` 指这个目录的绝对路径；下文 `~` 指用户主目录。

各客户端不各存一份内容，只放指向它的目录链接。改一次，六端同时生效。

配置不在技能目录里，位于 `~/.media-gen/config.json`。所以无论用链接还是复制，配置都是同一份，填一次就行。

## 2 六个客户端的技能目录

目录名必须是 `gen-media`，和技能名完全一致，否则多数客户端会拒绝加载。

| 客户端 | 个人级目录 |
|---|---|
| Claude Code | `~/.claude/skills/gen-media` |
| Codex | `~/.agents/skills/gen-media` |
| Qoder | `~/.qoder/skills/gen-media` |
| Trae | `~/.trae/skills/gen-media` |
| Cursor | `~/.cursor/skills/gen-media` |
| WorkBuddy | `~/.workbuddy/skills/gen-media` |

目录不存在时先建父目录的 `skills`，例如 `~/.qoder/skills`。

## 3 两种部署方式

### 目录链接（推荐）

Windows 上在命令提示符里执行：

```bat
mklink /J "%USERPROFILE%\.claude\skills\gen-media" "$SKILL_SRC"
```

要点：

- `mklink` 是 cmd 内建命令。在 Git Bash 里要写成 `cmd //c mklink /J ...`，双斜杠防止路径被改写。
- `/J` 是目录交接点，**不需要管理员权限**，但**只能在同一磁盘分区内**。源和目标都在 C 盘时可用；跨盘会失败，只能改用复制。
- 路径里有空格或中文时必须加双引号。

macOS 和 Linux：

```bash
ln -s "$SKILL_SRC" ~/.claude/skills/gen-media
```

### 复制（备选）

只在目标客户端不认目录链接、或者要打包发给别人时用。

```bash
cp -r "$SKILL_SRC" ~/.qoder/skills/gen-media
```

代价是多份会各自漂移。检测方法：

```bash
diff -r "$SKILL_SRC" ~/.qoder/skills/gen-media
```

没有输出就是一致。

## 4 装完验四件事

1. 配置能读：`python "$SKILL_SRC/scripts/media_gen.py" config show`，应该打印出配置路径和服务列表。
2. 客户端能认：在目标客户端新开一个会话，问「你能生成图片吗」，技能名应该出现在可调用列表里。没出现就是目录名与技能名不一致，或者客户端需要重启。
3. 真出一张小图：`python "$SKILL_SRC/scripts/media_gen.py" image "一张测试图" --size 1K -o test.png`，最后一行应该是可打开的绝对路径。
4. 视频链路通（不必等出片）：`python "$SKILL_SRC/scripts/media_gen.py" video "测试" --submit-only`，能打印任务号就说明提交链路没问题。

## 5 让别人少踩坑：加一条强制规则

技能自己会尽量抢在客户端内置生成工具之前被选中，但那是靠描述判断，不是硬拦截。要更硬的约束，让对方把下面这段加到他项目根目录的 `AGENTS.md`（或客户端对应的规则文件）。

现成文本在技能目录的 `assets/rules-snippet.md`，直接复制粘贴即可。

各客户端的规则文件位置：

| 客户端 | 规则文件 |
|---|---|
| WorkBuddy | 项目根 `AGENTS.md` |
| Qoder | 项目根 `AGENTS.md` |
| Trae | `.trae/rules/project_rules.md` |
| Cursor | `.cursor/rules/` 下的 `.mdc` 文件 |
| Codex | 项目根 `AGENTS.md` |
| Claude Code | 项目根 `CLAUDE.md` |

## 6 迁移与维护

| 场景 | 做法 |
|---|---|
| 换电脑 | 搬技能目录加搬 `~/.media-gen/config.json` 这一个文件；或者在新机器跑 `config init` 重填密钥 |
| 换密钥 | `config set --api-key <新密钥>`，再 `config test` 确认 |
| 换服务 | `config use 名字` |
| 升级技能 | 链接方式直接更新源目录；复制方式重新复制并重新 `diff -r` |
| 卸载 | 删链接或目录，再决定要不要删 `~/.media-gen`（那里有密钥） |
| 打包给别人 | 只打包技能目录，**不要**带上配置文件。配置在用户主目录，天然不会被带出去 |

## 7 已知不可用的组合

- 目标服务不是 OpenAI 兼容协议（GraphQL、签名鉴权、两步上传换文件 ID、WebSocket 推进度）——配什么都接不上，换服务。
- 同步阻塞式接口，请求会挂几分钟才返回——脚本按「提交 + 轮询」设计，这类会撞超时。换服务。
- 状态字段是数字码（`task_status: 3`）——只认文字状态，数字码不支持。
