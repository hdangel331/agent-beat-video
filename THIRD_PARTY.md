# 第三方组件

| 直接依赖 | 核验来源 | 使用方式 |
| --- | --- | --- |
| librosa 0.11.0 | [ISC](https://github.com/librosa/librosa/blob/0.11.0/LICENSE.md) | 导入公开音频分析 API |
| NumPy 2.x | [BSD 系列与打包库声明](https://numpy.org/doc/stable/license.html) | 数值分析、测试音乐 |
| Pillow | [MIT-CMU / HPND](https://pillow.readthedocs.io/en/stable/about.html#license) | 生成样本及字体度量 |
| FontTools | [MIT](https://github.com/fonttools/fonttools/blob/main/LICENSE) | 校验字体字形，读取字体族 |
| Pydantic | [MIT](https://github.com/pydantic/pydantic/blob/main/LICENSE) | 任务参数和时间线校验 |
| filelock | [MIT](https://github.com/tox-dev/filelock/blob/main/LICENSE) | 作业互斥 |
| MCP Python SDK 1.29.0 | [MIT](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE) | 可选 stdio 服务和验收客户端 |
| FFmpeg / ffprobe | [上游许可说明](https://ffmpeg.org/legal.html) | 调用本机二进制，启用 libx264、libass 的构建。分发编译产物前须审查对应构建选项。 |
| Noto Sans SC Regular 2.004，© 2014–2021 Adobe | [SIL OFL 1.1](src/agent_beat_video/fonts/OFL.txt) · [字体来源、版本与校验值](src/agent_beat_video/fonts/NOTICE.txt) | 随项目分发上游原版字体；用于固定标题及旧时间线重放。OFL 允许将字形用于商用视频标题。[官方解释](https://openfontlicense.org/ofl-faq/) |

发布前按实际安装环境检查传递依赖及其 NOTICE。源码包不含第三方 Python 库或 FFmpeg 可执行文件。示例音乐与插画由仓库内的原创程序生成。请为实际素材、音乐和字体取得所需使用权。
