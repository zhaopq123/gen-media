# 配置

## 它在哪

`~/.media-gen/config.json`（Windows 上是 `%USERPROFILE%\.media-gen\config.json`）。

不在技能目录里：多端部署不会变成多份，打包分发不会把密钥带出去，升级技能不覆盖配置。

## 长什么样

```json
{
  // 默认用哪一条，写下面某个 name
  "current": "我的服务",
  // 可以放多条，每条一个服务；只用一个就填第一条
  "providers": [
    {
      // 随便起个名字，自己认得出就行
      "name": "我的服务",
      // 密钥，服务商给你的那一串
      "api_key": "",
      // 生图接口的完整地址，照文档原样复制
      "image_url": "",
      // 视频接口的完整地址，照文档原样复制
      "video_url": "",
      // 视频查询地址，里面的 {id} 会替换成任务号
      "query_url": "",
      // 生图模型名，去服务商的模型列表里抄
      "image_model": "",
      // 视频模型名，只出图可以先留空
      "video_model": "",
      // 请求风格，填 auto、nested 或 openai，不确定就 auto
      "style": "auto"
    }
  ]
}
```

八个值，每个都是你自己从服务商文档抄过来的**完整地址**。程序不做拼接、不做推测，填什么就请求什么。

只有 `{id}` 会被替换成任务号，这是唯一的自动处理。

## 最省事的填法

服务商文档里一般会写「调用地址」，整条复制进 `image_url` 就行。例如文档写：

```text
POST https://api.example.com/v1/images/generations
```

就把 `https://api.example.com/v1/images/generations` 整个粘进去，别拆成域名加路径。

视频通常有两个地址：创建任务的和查询任务的。查询地址里的任务号位置换成 `{id}`。

## 多家服务

`providers` 是可以放多条记录的数组。加一条就复制一段，改 `name` 和各个地址。

两家都填完整时，`config show` 会提示先问用哪一个。选定后 `config use 名字` 记住，临时换一家加 `--provider 名字`。

## 命令行改配置

```bash
python media_gen.py config init                        # 生成模板
python media_gen.py config show                        # 看现状（密钥打码）
python media_gen.py config set --image-url https://...  # 改单项
python media_gen.py config set --api-key sk-...         # 写密钥，不回显
python media_gen.py config add 另一家                   # 增加一条
python media_gen.py config use 另一家                   # 切换默认
python media_gen.py config test                        # 探活验证
```

## 请求风格

`style` 决定请求体怎么组织：

| 值 | 含义 |
|---|---|
| `auto` | 默认按通用扁平请求体拼（`openai`） |
| `nested` | 部分参数包一层 `extra_body`，时长为字符串，尺寸走 720P；适用于少数要求把参数套一层 `extra_body` 的接口 |
| `openai` | 扁平请求体，参数直接放最外层 |

不确定就留 `auto`。服务端报 400 提到字段形状时，改用 `nested` 再试。

## 接不上怎么调

三步：

1. `config show` 看差什么
2. `config test` 看返回：401/403 是密钥问题，404 是地址问题，402 是余额
3. 加 `--dump` 跑一次真实请求，stderr 会打出服务端原文（密钥已打码）。响应字段和预期不一样时，用 `--extract` 临时指定取值路径试：

```bash
python media_gen.py image "测试" --dump
python media_gen.py image "测试" --extract "output.images[]"
```

`--extract` 的语法只有两条规则：`a.b.c` 逐层取键，`a[].b` 对数组每一项继续取。没有数字下标，`[]` 取到的第一个就是第一项。

## 环境变量

| 变量 | 作用 |
|---|---|
| `MEDIA_GEN_CONFIG` | 指定另一份配置文件，多套配置并行时用 |
| `MEDIA_GEN_API_KEY` | 临时顶掉配置里的密钥 |
| `MEDIA_GEN_PROVIDER` | 临时顶掉默认服务 |

命令行参数优先于环境变量，环境变量优先于配置文件。

## 密钥安全

- 任何命令输出都只显示打码值
- 服务端如果在错误响应里回显密钥，输出前会被替换掉
- 密钥不进技能目录，不随打包外传
- 换密钥：改 `api_key` 后跑 `config test`，通了再去平台撤销旧的
