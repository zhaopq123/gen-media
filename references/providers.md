# 常见服务怎么填

配置要填的是**完整接口地址**，不是域名。打开服务商文档，找到「调用地址」那一栏，整条复制过来，不要自己拆开。

这里给三份可以直接照抄的例子，把密钥和模型名换掉即可。

## OpenAI 官方

```json
{
  "name": "openai",
  "api_key": "sk-...",
  "image_url": "https://api.openai.com/v1/images/generations",
  "video_url": "https://api.openai.com/v1/videos",
  "query_url": "https://api.openai.com/v1/videos/{id}",
  "image_model": "gpt-image-1",
  "video_model": "sora-2",
  "style": "openai"
}
```

## 各类第三方中转

中转基本都保持 OpenAI 的接口形状，把域名换成中转商给的那个：

```json
{
  "name": "中转",
  "api_key": "sk-...",
  "image_url": "https://你的中转域名/v1/images/generations",
  "video_url": "https://你的中转域名/v1/videos",
  "query_url": "https://你的中转域名/v1/videos/{id}",
  "image_model": "gpt-image-1",
  "video_model": "sora-2",
  "style": "openai"
}
```

模型名按中转商给的清单填，不一定和官方一致。

## 智谱

```json
{
  "name": "智谱",
  "api_key": "...",
  "image_url": "https://open.bigmodel.cn/api/paas/v4/images/generations",
  "video_url": "https://open.bigmodel.cn/api/paas/v4/videos/generations",
  "query_url": "https://open.bigmodel.cn/api/paas/v4/async-result/{id}",
  "image_model": "cogview-3-flash",
  "video_model": "cogvideox-flash",
  "style": "openai"
}
```

它的视频是「提交拿任务号、再查结果」两段式，查询地址里那段路径和生成地址不一样，照抄上面这条即可。

## 自建网关

保持同样接口形状的，按中转那样填完整地址。如果改了响应结构，先用 `--dump` 看它到底返回什么，再用 `--extract` 指定取值路径。

## 填错了会怎样

| 现象 | 多半是 |
|---|---|
| `config test` 返回 401 或 403 | 密钥不对，或复制时多了空格 |
| `config test` 返回 404 | 地址不完整，或者版本段重复了 |
| `config test` 返回 402 | 余额或配额不足 |
| 提交返回 400 提到 model | 模型名不对，去控制台抄 |
| 提交返回 400 提到字段 | `style` 选错了，换个值再试 |
| 提交成功但取不到图 | 响应结构不同，`--dump` 看原文后用 `--extract` |
