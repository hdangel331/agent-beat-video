# 开发基线与取舍 · 2026-11-23

| 上游 | 调研后用于本项目的决策 |
| --- | --- |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 参考它从任务创建到视频输出的分层设计。我们的输入是用户已有素材和音乐。 |
| [CutClaw](https://github.com/GVCLab/CutClaw) | 借鉴策划与质量检查分开的思路。独立实现，用 JSON 交换结果。 |
| [BeatSync-Engine](https://github.com/Merserk/BeatSync-Engine)、[cadence](https://github.com/DisaterPeace/cadence) | 拍点检测和切点选择各自独立。局部能量决定候选间隔，所有切点最终量化为帧。 |
| [librosa](https://github.com/librosa/librosa) | 使用其公开 Python API 计算起音强度、节拍和局部能量。 |
| [FFmpeg](https://github.com/FFmpeg/FFmpeg) | 用单独进程探测、裁剪、混流、编码和解码验收。 |
| [MoviePy](https://github.com/Zulko/moviepy) | 评估了 Python 合成接口。首版直接调用 FFmpeg 以精确控制帧数。 |
| [auto-editor](https://github.com/WyattBlue/auto-editor)、[autocut](https://github.com/mli/autocut) | 保留可以人工编辑并再次渲染的中间计划。 |
| [Essentia](https://github.com/MTG/essentia) | 扩展音频特征候选，目前没有引入。 |
| [Remotion](https://github.com/remotion-dev/remotion) | 可选后端。先评估 Chromium 部署和[许可条件](https://www.remotion.dev/pricing)，当前用本机 FFmpeg/libass。 |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | 可选安装，通过标准输入输出调用同一引擎。 |
| [WorkBuddy 开放平台](https://open.workbuddy.cn/docs/connector) | 本地连接器使用 connector-meta.json、mcp.json、图标。机器上预先安装 Python 包和 FFmpeg。 |

**阶段 0 交付**　原创测试集生成器、依赖记录和渲染器决策。没有移植以上编辑器的源码或字体、音频、图像素材。
