# 配置指南

这份讲三个依赖怎么准备、密钥怎么弄到手、填进去、验一下、以后怎么换和撤销。

## 0 依赖一览

| 依赖 ID | 类型 | 必需 | 作用 |
|---|---|---|---|
| `python-runtime` | 运行环境 | 是 | 跑所有脚本，只用标准库 |
| `generation-api` | 接口加密钥 | 是 | 实际出图出视频的上游服务 |
| `config-file` | 本地配置 | 否 | 存放服务与密钥，支持多家并存 |

### python-runtime

- 官方主页：https://www.python.org/
- 官方文档：https://docs.python.org/3/using/index.html
- 下载地址：https://www.python.org/downloads/
- 支持版本：3.8 及以上
- 配置步骤：先用 `python --version` 确认可用；低于 3.8 就从下载地址装新版，Windows 记得勾选加入 PATH；`python` 命令不存在时改用 `py -3`
- 验证方式：`python --version` 输出 3.8 以上
- 凭据：不涉及
- 安全：只用标准库，不安装任何第三方包

### config-file

配置文件位于 `~/.media-gen/config.json`，结构版本 `version: 1`。

- 生成：`config init`
- 查看：`config show`
- 加第二家：编辑文件，复制 `custom` 段改键名
- 切换默认：`config use <名字>`
- 删除即回到初始状态，需要重填密钥

## 1 任意 OpenAI 兼容服务

适用于各种第三方中转、自建网关、官方 OpenAI。

- 用途：出图、出视频
- 官方主页：以你所用服务的控制台为准
- 官方文档：以你所用服务的文档为准
- 密钥页面：各服务平台的控制台
- 权限与范围：通常只需要模型调用权限，不要给账号管理权限
- 配置步骤：
  1. 从服务方文档抄四样：生图接口完整地址、视频接口完整地址、视频查询地址、两个模型名
  2. 拿到 API 密钥
  3. `python media_gen.py config init`
  4. 打开配置文件，把这几样填进对应字段：`image_url`、`video_url`、`query_url`、`image_model`、`video_model`、`api_key`
  5. `config test --provider custom` 验证
- 凭据存储：`~/.media-gen/config.json` 的 `api_key` 字段；也可用环境变量 `MEDIA_GEN_API_KEY` 临时顶替
- 验证方式：`config test --provider custom`
- 轮换和撤销：服务方控制台删除旧密钥后 `config set`，再 `config test` 确认
- 核验日期：不适用，以服务方文档为准

## 2 OpenAI 官方（参考）

- 官方主页：https://openai.com
- 密钥页面：https://platform.openai.com/api-keys
- 登录后路径：登录 → API keys → Create new secret key
- 权限与范围：项目级密钥，只勾模型调用
- 配置步骤：`image_url` 填 `https://api.openai.com/v1/images/generations`，`video_url` 填 `https://api.openai.com/v1/videos`，再填两个模型名和密钥
- 核验日期：以实际访问时的页面结构为准

## 3 密钥安全

**不要让用户在对话里粘贴完整密钥。** 默认路径是让用户自己打开配置文件填，这样密钥不进对话记录、不进服务端日志。

用户坚持要代写时：

1. 用 `config set --api-key` 写入，不要用 echo 或打印回显。
2. 写入后只回一句「已写入，密钥不回显」。
3. 明确提醒一次：这条消息已经进了对话记录，介意的话去平台轮换一次。

其他规则：

- 任何输出都不显示完整密钥，`config show` 只给打码值。
- 服务端如果在错误响应里回显了密钥，输出前会被替换成打码值。
- 技能目录里不放任何密钥，打包分发时不会带出去。
- 怀疑泄露时：平台删旧密钥 → 新建 → `config set --api-key` → `config test` 确认。

## 4 常见故障对照

| 现象 | 判断 | 处理 |
|---|---|---|
| `config test` 返回 401/403 | 密钥不对或没权限 | 重新复制密钥，注意别带空格和引号 |
| `config test` 返回 404 | 地址不完整或重复 | 确认 `image_url` 是文档里那条完整地址，别自己拆开或重复拼版本段 |
| `config test` 返回 402 | 余额或配额不足 | 充值或换服务 |
| 连不上域名 | 网络或代理 | 确认能访问该域名，必要时设 `HTTPS_PROXY` |
| 生成时 429 | 限流 | 降低并发，隔一会儿再试 |
| 出图成功但找不到地址 | 响应字段不是预期形状 | `--dump` 看原文，按 config.md 第 7 节写 `pick` |
