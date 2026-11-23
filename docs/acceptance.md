# 首版验收 · 2026-11-23

环境为 Linux x86_64、Python 3.12.14、FFmpeg/ffprobe 7.1.5、librosa 0.11.0。图像、视频及配乐均由 scripts/generate_fixture.py 本地生成。输入包含 10 张图片、5 段 6 秒视频与一首 24 秒立体声 WAV。原曲按 120 BPM 合成。

| 检查 | 结果 |
| --- | --- |
| CLI 完整作业 | job_id 为 8ee428ccdd424378ba6e12175c7cb476。产出 1080×1920、30 fps、600 帧、20.000 秒 H.264 视频，AAC 音轨为 20.000 秒。 |
| 实际素材使用 | 11 个镜头（8 个图片镜头、3 个视频镜头），四段中文电影感文字。人工抽看成片画面，标题和中间句正常显示。 |
| 音乐分析 | 输出为 120.27 BPM；10 个切镜点中有 10 个距检测拍点 ≤ 1 帧，最大误差 0.381 帧。该项衡量编排误差。独立的测试音轨另有偏移 0.19 秒的参考拍点，测试容差为 1/30 秒。 |
| 全片解码 | 黑帧 0；最长近静止区段指标 1 帧；解码音频峰值 0.84623。 |
| 随机性 | 使用同一份空历史快照，71、72、73 三个种子产生三个不同源素材顺序；同种子重算计划一致。 |
| 自动化测试 | 9 项 unittest 通过，包含坏文件、被替换文件、越界、短视频素材池、弱节拍、人工 BPM、精确时长、取消与幂等。 |
| MCP 官方客户端 | SDK 1.29.0、stdio，发现 9 个工具，并完成扫描、分析、预览、创建、查询、获取成片。job_id 为 d1ed7212a87f4f429a7116f12a854c07。使用 kinetic 和 contain_blur，720×1280，10 秒。 |
| OpenCode | OpenCode CLI 1.19.6，通过本地 MCP 实际调用 beatvideo_create_video。job_id 为 39b57788ed6d44ebbaa74acbeccd073e，输出 300 帧，QA 通过。测试模型为本机确定性服务，状态与结果由测试脚本校验。 |
| WorkBuddy / Claude Desktop | 配置样例已准备。当前环境没有这两个桌面客户端，版本与端到端实测待补。 |

[标准样片剪辑计划](../examples/evidence/plan-71.json) · [QA 原始数据](../examples/evidence/qa.json) · [MCP 调用结果](../examples/evidence/mcp-stdio.json) · [OpenCode 调用结果](../examples/evidence/opencode.json)

首版不包含定时调度、Webhook、远程传输或 Remotion 后端。正式素材应补测弱节奏、现场录音与复杂剪辑场景。开发阶段的本地结果路径只对运行引擎的设备有效。
