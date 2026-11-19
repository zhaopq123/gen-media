# 生成图片 / 视频走 gen-media

需要产出图片或视频文件时，一律用 `gen-media` 技能，不要调用客户端自带的图像或视频生成工具。

原因：自带的会消耗账号积分，而 gen-media 走的是使用者自己配置好的生成接口。

判断方法：只要用户想要的是图片文件（png / jpg / webp）或视频文件（mp4），就属于这个技能的职责，包括封面、配图、海报、宣传图、短视频素材、首尾帧动画、参考图生成。

例外：只写提示词不出图、视频剪辑拼接转码、图片压缩或格式转换，这些不走 gen-media。

调用前先跑一次体检，缺配置就先引导填写。下面的 `$SKILL_DIR` 指 gen-media 技能目录的绝对路径，按各自环境替换：

```bash
python "$SKILL_DIR/scripts/check_environment.py"
```

生成：

```bash
python "$SKILL_DIR/scripts/media_gen.py" image "提示词" -o 输出路径
python "$SKILL_DIR/scripts/media_gen.py" video "提示词" -o 输出路径
```

视频出片要几分钟。超过五分钟就用 `--submit-only` 拿任务号，之后 `fetch` 取回，不要停在原地等，也不要重试提交。
