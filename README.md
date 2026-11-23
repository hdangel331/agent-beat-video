# AgentBeatVideo

用自己的图片、视频、音乐和中文文案，生成一条 10–60 秒的竖屏音乐短片。可从命令行运行，也可以让支持本地 MCP 的 Agent 调用。

首个示例《山海有时》长 20 秒，含 11 个镜头，标题“山海有时”从首帧到末帧固定在画面下方居中。这份项目包含测试素材生成器；运行示例无需账号、API Key 或联网生成素材。

## Windows 快速开始

安装 Python 3.11 或更高版本、带 libx264 与 libass 的 FFmpeg，把 ffmpeg、ffprobe 加入 PATH。在解压后的项目目录用 PowerShell 运行：

```powershell
py scripts/setup.py
.\.venv\Scripts\python.exe scripts/generate_fixture.py work/demo
.\.venv\Scripts\agent-beat-video.exe --root work/demo make examples/task.json
```

中文字体已随项目提供，Windows、macOS 和 Linux 统一使用 Noto Sans SC Regular 2.004。若 py 无法运行，可使用 python 命令。

## Linux / macOS

Debian/Ubuntu 可通过 apt 安装 ffmpeg 和 python3-venv。macOS 可用 Homebrew 安装 ffmpeg。FFmpeg 安装包见[上游下载页](https://ffmpeg.org/download.html)。

```bash
python3 scripts/setup.py
.venv/bin/python scripts/generate_fixture.py work/demo
.venv/bin/agent-beat-video --root work/demo make examples/task.json
```

make 先扫描、再生成时间线，然后创建后台任务。命令行输出 job_id，结束时输出本机成片路径。首次分析会编译部分音频函数，后续按音乐内容哈希和分析器版本复用结果。安装依赖需要网络，本地渲染可以离线运行。

## 使用自己的素材

1. 准备一个工作目录，例如 work/mine。在 assets/ 中放入 JPG、PNG、WebP、MP4 或 MOV；在 music/ 中放入 WAV、MP3、M4A、FLAC、AAC 或 OGG。可通过 assets/ 子目录划分素材集。
2. 复制 examples/task.json，把 music_id 改成 music/ 内的相对路径，把 caption 改成整条视频要显示的文字。asset_pool 填相对于 assets/ 的子目录或点号。将 resolution 设为 720 可快速预览，默认 1080；fps 默认 30。
3. 用新工作目录与任务文件运行 make。结果在 output/UTC日期/job_id/，包含 video.mp4、plan.json、analysis.json、manifest.json、qa.json 和 render.log。

| 参数 | 可用设置 |
| --- | --- |
| random_seed / rotation_window_days | 随机种子，默认参考最近 7 天完成的任务；将窗口设为 0 可忽略历史。 |
| duration_s / music_offset_s | 目标时长、音乐起点（秒）；所选区间必须落在原音乐内。 |
| cut_density / variation_strength | low、medium、high；策略变化幅度 0–1。 |
| fit | contain_blur 保留完整画面并以模糊背景填充；cover_crop 居中裁满画面。 |
| caption | 全程显示的一段文字。固定在画面水平中心、高度约 74% 处，字形、字号和位置在镜头切换时保持一致；可换行。 |
| transition_style | mixed 按种子混合硬切、叠化、向左擦除、向右推移和圆形展开。需要单一风格时填 cut、fade、wipeleft、slideright 或 circleopen。 |
| manual_bpm | 可选，拍网格从音乐零点开始；自动置信度偏低时会显式报告均匀切镜。 |

旧任务的 text_blocks 会按原顺序合成同一块固定文字；填写 caption 时请移除 text_blocks。省略两者可输出纯画面。已保存的 1.0 时间线仍可按原字幕时序重放，字库统一使用随附的开源字体。

导出后，qa.json 的 fixed_caption_check 记录已检查帧数、文字边界与未通过的帧号。可运行 `.venv/bin/python scripts/check_caption.py <成片目录>` 再次检查固定文字。

## 检查、修改或重放剪辑

以下用已加入 PATH 的 agent-beat-video 表示虚拟环境中的同名可执行文件。

```bash
agent-beat-video --root work/demo scan
agent-beat-video --root work/demo analyze tide.wav
agent-beat-video --root work/demo plan examples/task.json
agent-beat-video --root work/demo create --plan-id <plan_id> --request-key draft-001
agent-beat-video --root work/demo status <job_id>
agent-beat-video --root work/demo result <job_id>
```

修改已导出 plan.json 中的素材、入点、字幕或切镜时刻后，可用 create --plan-file 指向编辑后的文件。镜头以输出帧为单位，从零连续覆盖总帧数。逐帧计划保留历史快照。要从任务配置重建相同计划，给 plan 或 make 增加 --history-from 已导出的plan.json，保持相同素材、音频分析版本、种子与配置。要精确重渲染，可直接使用原 plan.json。

每次新建任务会依次编码镜头、混流、整片解码验收。状态保存在 SQLite 中。相同 request_key 和 plan_id 会返回原作业。命令 cancel 在下一个阶段边界生效。用 retry 重试失败作业；若工作进程意外退出，下一次 status 轮询会恢复该任务。默认一台电脑同时编码一个任务。

## Agent 接入

- 腾讯 WorkBuddy 的连接器元信息、图标和本地启动配置位于 [integrations/workbuddy](integrations/workbuddy/README.md)。本次以官方 MCP SDK 实测工具发现、建单、查询和取片；WorkBuddy 桌面客户端仍待验证。
- OpenCode 的 v1、v2 配置与 Claude Desktop 配置在 integrations/。实际测试使用 OpenCode 1.19.6 和本机确定性测试模型。Claude Desktop 待实测。
- MCP 进程只读授权 assets/、music/ 输入，只返回本机结果路径。当前采用本地 stdio，远程下载和远程服务尚未开放。

## 验收与边界

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/smoke_mcp.py work/demo
```

算法读取起音、节拍与局部能量，在候选拍点中选镜头边界，过渡从切点开始，默认约 0.32 秒；短镜头自动缩短。整个时间线的帧数、拍点和音乐时长保持一致。照片使用轻微推拉，视频选择有效入点。验收检查实际解码帧数、编码、音轨、同步误差、黑帧、近似冻结和音频峰值。慢摇、无鼓点、复杂变速音乐仍需人工试听。参考 [实测记录](docs/acceptance.md)、[开发需求](docs/AgentBeatVideo_开源调研与开发需求_V1.1.md)、[第三方依赖](THIRD_PARTY.md)。

后续里程碑包括 WorkBuddy 桌面真机验收、定时补跑、Webhook 投递、跨日文案去重和跨日镜头序列去重。当前已对近期用过的素材降权。原始项目许可证待所有者确定。样例任务只能读取当前授权目录中的媒体；源码包随附原版 Noto Sans SC Regular 字体、版权声明及 SIL OFL 1.1 许可证。成片文案直接用该字库生成，缺字时会列出缺失字符。
