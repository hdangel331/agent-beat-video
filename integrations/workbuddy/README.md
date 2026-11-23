# 腾讯 WorkBuddy 本地接入

先用项目 README 的命令在 WorkBuddy 所在的电脑渲染一次。选用带 Agent 依赖的安装方式。把 mcp.json 中的 Python 可执行文件与授权工作目录改为实际绝对路径；桌面应用的 PATH 也需要能找到 ffmpeg 和 ffprobe。Linux/macOS 虚拟环境的解释器在 .venv/bin/python。Windows 路径要保留 JSON 的双反斜杠。

打开 WorkBuddy 的「连接器 → 自定义连接器」，按已安装版本选择本地 stdio，复制 mcp.json 中的自定义配置或逐项填入 command 和 args。工具发现后，让它先调用 scan_assets 和 analyze_music，再提交 preview_edit_plan 的 task。用返回的 plan_id 调用 create_video，保留 job_id 并轮询 get_job_status。completed 后调用 get_video_result。

示例指令：“扫描已授权的素材目录，使用 tide.wav 剪一条 20 秒竖屏短片，标题写‘山海有时’，字效选 cinematic。先给我镜头数，然后渲染，返回 MP4 路径和逐帧检查结果。”文件路径只在服务运行的本机有效。

仓库内 scripts/smoke_mcp.py 可验证这套服务的标准输入输出链路。WorkBuddy 桌面验收需要记录软件版本、系统、实际配置、工具列表、job_id 和返回的视频；本次交付没有该桌面客户端的实测记录。远程传输与市场上架均为后续工作。

[腾讯自定义连接器](https://www.codebuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector) · [开放平台规范](https://open.workbuddy.cn/docs/connector)
