# 第三方组件

| 直接依赖 | 核验来源 | 使用方式 |
| --- | --- | --- |
| librosa 0.11.0 | [ISC](https://github.com/librosa/librosa/blob/0.11.0/LICENSE.md) | 导入公开音频分析 API |
| NumPy 2.x | [BSD 系列与打包库声明](https://numpy.org/doc/stable/license.html) | 数值分析、测试音乐 |
| Pillow | [MIT-CMU / HPND](https://pillow.readthedocs.io/en/stable/about.html#license) | 生成样本及字体度量 |
| FontTools | [MIT](https://github.com/fonttools/fonttools/blob/main/LICENSE) | 校验字体字形，读取字体族 |
| Pydantic | [MIT](https://github.com/pydantic/pydantic/blob/main/LICENSE) | 任务参数和时间线校验 |
| filelock | [Unlicense](https://github.com/tox-dev/filelock/blob/main/LICENSE) | 作业互斥 |
| MCP Python SDK 1.29.0 | [MIT](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE) | 可选 stdio 服务和验收客户端 |
| FFmpeg / ffprobe | [上游许可说明](https://ffmpeg.org/legal.html) | 调用本机二进制，启用 libx264、libass 的构建。分发编译产物前须审查对应构建选项。 |
| Noto Sans CJK SC | [SIL OFL](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE) | 样片使用本机字体，没有随项目打包。 |

发布前按实际安装环境检查传递依赖及其 NOTICE。源码包不含第三方库、字体或 FFmpeg 可执行文件。示例音乐与插画由仓库内的原创程序生成。请为实际素材、音乐和字体取得所需使用权。
