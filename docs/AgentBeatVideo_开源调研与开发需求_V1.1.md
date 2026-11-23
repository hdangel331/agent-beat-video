# AgentBeatVideo：面向多 Agent 的自动音乐卡点视频工具

**文档版本：V1.1（新增腾讯 WorkBuddy 兼容要求）**  
**调研日期：2026-11-23**  
**目标读者：ChatGPT Work、腾讯 WorkBuddy、OpenCode、Claude Desktop 及其他开发/调用 Agent**  
**项目建议名称：`agent-beat-video`**

> **项目目标**：用户提供一批图片/视频素材，指定音乐和每天的文案主题。Agent 自动产出不同组合、随音乐节奏切换镜头、具有精美中文文字动画的短视频，并按设定时间交付。工具应当以无界面、可调用的“视频生产引擎”为核心，不依赖某一个 Agent、模型供应商或聊天窗口持续在线。

---

## 1. GitHub 开源项目实地调研

评估原则：**成熟度和相关性是两条独立维度**。Star 高不意味着适合直接 fork；Star 低也不意味着不能学习具体算法。最终要综合评估功能、代码质量、活跃程度、许可证、可替换性、部署成本。

下列 Star 为查询时页面显示的近似值，之后会变化。

| 项目 | 约 Star | 已确认的主要能力 | 对我们的结论 | 已知许可证/注意 |
|---|---:|---|---|---|
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 145,100 | 脚本、素材、字幕、合成、CLI/API/Agent 工作流、任务状态 | **重点研究流水线、任务记录、失败恢复、投递**；不是直接拿它做音乐卡点 | MIT；其主题生成路径与“自有素材随机踩点”不同 |
| [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | 75,000 | React 程序化视频、字幕、转场、文字动画、模板、渲染 | **重点借鉴高级文字模板与动画**，作为可选高级渲染后端 | 专有/特殊许可证：个人及符合条件的小团队免费，其他用途须审查商业许可 |
| [Zulko/moviepy](https://github.com/Zulko/moviepy) | 15,200 | Python 拼接、裁剪、合成 | 适合原型和少量视频操作；大规模渲染优先 FFmpeg | MIT |
| [librosa/librosa](https://github.com/librosa/librosa) | 9,100 | BPM、onset、节拍、能量等音频分析 | **首选节奏分析引擎**，自行建立剪辑点算法 | ISC |
| [mli/autocut](https://github.com/mli/autocut) | 7,800 | 转录后按文字编辑视频 | 学习可编辑中间结果和中文支持，不作为卡点核心 | Apache-2.0 |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | 6,100 | 音量/运动信息驱动自动剪切、时间线导出 | 学习分析与执行解耦、剪辑中间格式；其主要功能不是音乐节奏剪辑 | Unlicense；独立 App 的资产许可可能不同 |
| [MTG/essentia](https://github.com/MTG/essentia) | 3,800 | 丰富的音乐特征分析 | 如 librosa 精度不够可评估，**不在首版硬依赖** | AGPL-3.0，需法律兼容性评估 |
| [GVCLab/CutClaw](https://github.com/GVCLab/CutClaw) | 1,000 | Agent 镜头策划、音画同步、成片质量检查 | **借鉴“分析 → 计划 → 渲染 → 检查”架构**，但不直接复制 | 仓库页面未明确显示许可证，复用代码前需查证 |
| [Merserk/BeatSync-Engine](https://github.com/Merserk/BeatSync-Engine) | 90 | 节拍/音乐能量/段落分析，按帧编排音乐剪辑 | **重点研究节奏切镜逻辑，独立实现我们的算法** | GPL-3.0；谨慎复用 |
| [DisaterPeace/cadence](https://github.com/DisaterPeace/cadence) | 0 | 基于强弱拍、音色、段落调整切镜密度 | 借鉴“不在每一拍切镜头”的设计思路 | AGPL-3.0；谨慎复用 |
| [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) | — | 解码、滤镜、拼接、音视频混流、编码 | **默认渲染执行引擎**；检查二进制编译选项的许可证 | LGPL/GPL 具体取决于构建选项 |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | — | Python MCP 服务/客户端 SDK | 首选 Agent 通用接口实现 | 按实际依赖锁定版本及许可证审查 |

**重要判断**：MoneyPrinterTurbo 和 CutClaw 值得学习“怎样组织一条视频生产流水线”，Remotion 值得学习“怎样把字幕做漂亮”，librosa 值得学习“怎样找音乐的节奏点”。我们的独创核心则是 **素材资产库 + 音乐结构驱动的可控随机剪辑 + 每日多样性 + 多 Agent 接口**。

### 1.1 不做的事

- 不直接 fork 某个大型项目后仅改名字。
- 不复制他人的界面、动画模板、代码或商业素材，而忽略许可证。
- 不把自动删静音等同于音乐踩点。
- 不为了追求“AI”而给每个素材调用昂贵视觉模型；先让本地低成本方案可用。
- 不把视频渲染绑死在单一 LLM/单一 MCP 客户端中。

---

## 2. 产品定位与核心场景

用户典型操作：

1. 把 100 张图片或 50 段视频素材存到本地素材文件夹；可以不断追加。
2. 放入一首或多首用户有权使用的音乐，指定当日音乐或让系统轮换。
3. 设置“每天 1 条、15–30 秒、9:16 竖屏、文案主题、文字风格、发送渠道”。
4. Agent 根据主题产生当日文案（或接受用户固定文案）；调用工具创建任务。
5. 工具识别节奏、随机挑素材、编排镜头、渲染字幕效果，生成 MP4。
6. 系统做基本质量检查，保存成片及生成清单，并发送文件或有权限的下载链接。
7. 第二天继续执行，优先避免最近使用过的素材组合、镜头顺序和文案。

**普通用户只关心素材、音乐、文案和成片；Agent 通过结构化接口完成其他操作。**

## 3. 必须实现的核心业务规则

### 3.1 素材管理

- 支持 JPG/PNG/WebP/MP4/MOV 等；通过 `ffprobe` 预检查格式、时长、尺寸、帧率和能否解码。
- 每个素材计算内容哈希和唯一 ID；记录横竖屏、时长、标签、最近使用次数、最近用过的日期、可用区间。
- 图片可自动添加轻微平移/缩放（Ken Burns 效果）；视频可随机截取有效片段，不应随意拉伸画面。
- 支持按素材集、标签、优先级、使用权重筛选；最近频繁使用的素材降低抽样权重。
- 素材不足时可在允许条件下重复使用，但不能随机报错或导出黑屏；应写入质量报告。
- 对竖屏裁剪提供 `contain_blur` / `cover_crop` 两种模式；默认安全裁剪，防止字幕盖住主体。高级主体识别为二期功能。
- 不上传用户原始素材到公共仓库。

### 3.2 音乐分析与踩点（最重要）

第一步分析音乐，输出统一结构：

- 时长、采样率、建议剪辑片段区间。
- BPM（含 half-time/double-time 候选）；拍点 `beats[]`、强起音 `onsets[]`。
- 局部能量曲线及低/中/高能量段落；如能可靠识别，再计算小节起点、段落边界、高潮或 drop 候选。
- 分析结果按音频文件哈希缓存，不要每天重复计算。

**关键设计：节拍网格 ≠ 切镜点列表。**

独立的 `CutPlanner` 根据音乐节拍、强弱变化、时长目标、片段可用长度生成 `cut_points[]`：

- 默认先在每 2/4/8 拍等候选间隔里选择，高潮/强起音处可提高切换密度；柔和段落适当延长镜头。
- 切镜点必须对齐输出帧网格；所有镜头总帧数应严格等于目标视频总帧数。
- 限制连续极短镜头，避免“闪灯式”剪辑；插入少量过渡而非每次都套特效。
- 可配置 `cut_density`（低/中/高）与 `variation_strength`（0~1）。
- 默认大部分直接硬切；其余少量淡化、推拉、轻闪等效果，概率可配置，避免镜头花哨。
- 音乐分析失败时可请求用户/Agent 指定 BPM 或采用安全均匀切法，并在报告中明确“未完成自动踩点”。
- 使用分层置信度：节拍置信度低时，减少强制踩点密度，不能假报节奏准确。

验证指标：对于判定为 **节拍同步切点** 的镜头，目标为至少 90% 在最近候选拍点 1 个输出帧的误差范围内（属于时间线工程误差，不代表节拍识别本身 90% 准确）；节拍识别准确性要靠带参考标注的音频单独测试。

### 3.3 随机但可控的素材编排

- 每个成片使用 `random_seed`，同一输入和 seed 应产生可复现的时间线。
- 在计划时进行加权抽样：考虑近期曝光率、画幅、时长适配度、连续同素材的惩罚、素材多样性。
- `rotation_window_days` 可配置，默认 7 天：尽量不重复近 7 天的镜头序列；不同音乐/长度下允许不同片段二次利用。
- 单条视频里的相邻片段不得完全相同；尽量避开同一视频的相邻原始时间段。
- 保存 `edit_plan.json`，以便 Agent 修改某些片段后重新渲染，而不是完全重做。
- 不要为“随机性”破坏节奏、出现黑帧或字幕撞脸。

### 3.4 每日文案与文字动画

文案可以由控制 Agent 提供，不要求视频引擎本身必须安装或绑定大模型 API。

文案来源：`user_provided`、`agent_generated` 或可选 `llm_provider` 适配器。任务定义须包含 `theme`、`tone`、`audience`、`language`、`forbidden_terms` 等字段。

文字类型：开场主题/中间情绪短句/关键字强调/结尾收束。

- 使用 3 套原创高质量中文字效模板：`clean_pop`（干净弹入）、`cinematic`（电影感）、`kinetic`（逐字节奏动效）。
- 动效含淡入、位移、缩放、字间距、描边、阴影、背景遮罩；按帧决定动画开始/结束时刻。
- 标题字数限制和自动换行；中文字体必须明确取得使用权，字体文件不得擅自提交或散发。
- 默认字幕位于安全区域；对强视觉背景加遮罩或描边，不可溢出屏幕。
- 部分文字可在强拍出现，但避免所有字同时闪烁。
- 文案重复检测：当天文案与最近 N 天文案做文本相似度判定；相似度过高要求 Agent 重写或启用候补文案。

### 3.5 渲染及音频

- 默认 MP4/H.264/AAC，1080×1920/30fps，支持 720×1280 快速预览。
- 视频长度可 10~60 秒配置；音乐只截用授权区段；完整保留主音乐节拍，默认不对原音乐做无意义变速。
- 音量归一化可选，入场/结尾平滑处理，避免音频爆音和结尾硬切。
- 默认 FFmpeg 执行渲染；字幕动效初版可采用 FFmpeg/图层合成；**Remotion 作为可切换的高级文字渲染适配器**，在验收许可与安装复杂度后启用。
- 长视频使用任务队列 + 临时文件 + 原子写入；任务取消后清理临时文件。

## 4. 面向多 Agent 的独立架构

```text
用户素材 / 自有音乐库 / 每日主题
           │
           ▼
控制 Agent（腾讯 WorkBuddy / OpenCode / Claude Desktop / 其他客户端）
           │  MCP / HTTP / CLI
           ▼
   AgentBeatVideo API 层
           │
           ├── AssetIndexer: 导入、校验、标签、哈希
           ├── AudioAnalyzer: BPM、拍点、能量、缓存
           ├── Copywriting: 校验/分段/去重（LLM 可由外部 Agent 承担）
           ├── CutPlanner: 节奏选点 + 随机素材编排
           ├── TextPlanner: 文字布局 + 动画时间点
           ├── Timeline: 与渲染器无关的 JSON 中间格式
           ├── Renderer: FFmpeg（默认） / Remotion（可选）
           ├── QualityGate: 时长、帧数、画幅、黑帧、音轨、字幕安全区
           ├── JobManager: 持久队列、状态、重试、可取消
           └── Delivery: 本地保存 / 邮件 / Webhook / 扩展交付端
           │
           ▼
   MP4 + EditPlan JSON + Manifest + QA Report
```

**多 Agent 兼容性**：本地 MCP 采用 `stdio`；远程 MCP 可支持 `Streamable HTTP` 并做鉴权。补充 CLI 和 REST API，使任何具备命令执行、HTTP 调用或 MCP 能力的 Agent 都有合适入口。各 Agent 的实际可调用能力需要在接入时验证；**不能假定所有聊天客户端都能直接操作用户电脑上的 MCP 服务**。

### 4.1 腾讯 WorkBuddy 作为正式兼容目标（必做）

**定义：**此处 WorkBuddy 指腾讯 WorkBuddy 桌面 AI 助手，并非泛指名称相近的其他软件。

根据腾讯官方文档，WorkBuddy 支持通过自定义 **MCP Connector** 接入第三方工具；开放平台还描述了 **MCP + Skill** 和 **CLI + Skill** 两类接入方案，MCP 连接方式包含 HTTP/SSE/stdio。我们的首选方案是 **复用统一 MCP 服务**，而不是再开发第二套视频剪辑引擎。

**接入优先级：**

1. **本地优先**：核心渲染器、素材文件、音乐和输出文件仍保存在用户明确授权的本机目录。准备 MCP `stdio` 启动命令和 WorkBuddy 的自定义连接器接入说明，先以真实安装版本验证；客户端环境存在差异时，不假定所有版本均可运行同一种本地连接方式。
2. **远程备选**：当 WorkBuddy 运行环境不能直接启动本机服务，或需要跨设备操作时，提供经鉴权的 `Streamable HTTP` MCP 地址；远程不能未经授权访问本机素材路径，需使用显式上传或受限共享机制。
3. **官方连接器包**：在 `integrations/workbuddy/` 下准备符合平台规范的 `connector-meta.json`、`mcp.json` 和可选 `skills/agent-beat-video/SKILL.md`；如使用 Token 模式，增加 `token-schema.json`。仅在实际需要面向平台发布时，再处理平台审核/上架，不把上架当作本地开发的前置条件。
4. **CLI 保底**：暴露与 MCP 一致的命令行能力。如 MCP 接入受版本或运行时限制，可评估官方 `CLI + Skill` Connector 方案，仍然调用同一套核心引擎。
5. **跨 Agent 功能一致**：WorkBuddy、OpenCode、Claude Desktop 发起同一个标准任务，应得到同样的剪辑计划、任务 ID/状态协议与视频输出格式；不能做出只能在某一个客户端运行的孤立功能。

**WorkBuddy 中文自然语言工作流示例：**

> “使用我授权的素材库，选取本周还没用过的片段，按照这首音乐生成 25 秒竖屏卡点视频。写一段今天的新文案，使用醒目的中文动态文字。渲染后检查视频和音轨，有问题先重试，再把成片保存到约定目录，并发送完成通知。”

**验收步骤（必须有实际运行记录）：**

- 在 WorkBuddy 的「连接器 / 自定义连接器」里连接 AgentBeatVideo，验证至少能发现 `scan_assets`、`preview_edit_plan`、`create_video`、`get_job_status`、`get_video_result`。
- 从 WorkBuddy 发起视频生成，拿到 `job_id`，轮询直到完成，并取得 MP4 文件路径或受权限保护的下载地址。
- 验证 WorkBuddy 与 OpenCode 使用的是**同一素材授权边界、同一个后端接口**；不得把绝对路径直接当成跨机器通用的文件下载链接。
- 记录已测试的 WorkBuddy 版本、系统、接入传输方式、完整配置样例和任何限制；未实测只能写“计划支持/待验证”，不得宣传为“已兼容”。
- 每日定时任务应由本机常驻服务或服务器调度，**不依赖 WorkBuddy 始终打开**。

官方参考：
- 腾讯 WorkBuddy 自定义连接器：https://www.codebuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector
- WorkBuddy 开放平台 Connector 规范：https://open.workbuddy.cn/docs/connector

**每日自动执行**：由常驻本机程序或服务器上的定时器执行，不依赖 ChatGPT / 桌面客户端每天保持打开。机器休眠、关机时不会执行任务；需提供错过任务补跑和失败重试策略。

## 5. MCP 工具规范（首版必须定义并实现）

建议优先实现下列工具，所有响应为结构化 JSON，错误具有固定错误码。

| 工具名 | 输入摘要 | 输出摘要 |
|---|---|---|
| `scan_assets` | `library_path`, `recursive` | `asset_count`, `added`, `warnings` |
| `list_assets` | `filters`, `page` | `assets[]`, `next_page` |
| `analyze_music` | `music_id` 或受限路径 | `bpm`, `beat_times`, `energy_sections`, `confidence` |
| `preview_edit_plan` | `music_id`, `asset_pool`, `duration_s`, `seed`, `cut_density`, `style` | `plan_id`, `cut_points`, `shot_count`, `warnings` |
| `create_video` | `plan_id` 或规范任务参数、`text_blocks[]`、输出规格 | `job_id`, `status=queued` |
| `get_job_status` | `job_id` | `status`, `stage`, `progress`, `error` |
| `get_video_result` | `job_id` | `output_path`/带权限 URI、`manifest_path`, `qa_report` |
| `cancel_job` | `job_id` | `cancelled` / `already_completed` |
| `list_render_history` | `date_range`, `page` | `jobs[]`, `asset_reuse_summary` |
| `configure_daily_schedule` | 时间、时区、素材集、音乐策略、文案来源、交付配置 | `schedule_id`, `next_run` |
| `run_daily_now` | `schedule_id`, `date` | `job_id`，含幂等策略 |

**工具设计约束**：

1. `create_video` 不可阻塞几分钟；必须先返回 `job_id`，之后通过轮询/事件查询结果。
2. 所有路径参数必须限定在显式授权目录中，防止任意文件读取、路径穿越、命令注入。
3. 不把整个视频文件直接塞入 MCP 文本响应，只给绝对路径（本地）或受权限保护的 URI（远程）。
4. MCP 服务输出的状态应基于数据库任务记录；进程重启后仍可查到。
5. 每日任务加幂等键 `schedule_id + local_date + variant_index`，防止重启造成重复生成/重复发送。
6. 发送或联网操作需要渠道凭证，存环境变量/密钥管理器；不得写入日志和 GitHub。

### 5.1 输入示例

```json
{
  "asset_pool": "daily_collection",
  "music_id": "bgm_001",
  "duration_s": 25,
  "aspect_ratio": "9:16",
  "fps": 30,
  "cut_density": "medium",
  "variation_strength": 0.6,
  "random_seed": 2026112301,
  "text_style": "kinetic",
  "text_blocks": [
    {"text": "今天也要闪闪发光", "role": "title"},
    {"text": "慢慢来，也会很快", "role": "middle"}
  ],
  "output_name": "daily_2026-11-23_a.mp4"
}
```

### 5.2 时间线中间格式（必须独立于具体渲染引擎）

```json
{
  "schema_version": "1.0",
  "seed": 2026112301,
  "fps": 30,
  "total_frames": 750,
  "music": {"asset_id": "bgm_001", "offset_frames": 0},
  "shots": [
    {"asset_id": "img_014", "start_frame": 0, "duration_frames": 90, "source_in_frames": 0, "transition": "cut"},
    {"asset_id": "vid_008", "start_frame": 90, "duration_frames": 60, "source_in_frames": 312, "transition": "cut"}
  ],
  "text_events": [
    {"text": "今天也要闪闪发光", "start_frame": 0, "duration_frames": 84, "template": "kinetic"}
  ]
}
```

上例仅展示结构，完整生成时 `shots` 时段必须连续覆盖 `total_frames`，所有素材 ID 必须可解析。

## 6. 数据、调度、交付与安全

数据表建议：`assets`、`music_analyses`、`render_plans`、`jobs`、`job_events`、`usage_history`、`schedules`、`delivery_attempts`。

本地用 SQLite + 事务保证一致性；先用单机持久任务队列，复杂队列（Redis/Celery）延后。产物位置 `output/YYYY-MM-DD/<job_id>/`，保存 `video.mp4`、`plan.json`、`manifest.json`、`qa.json`、`render.log`。

投递层初版先实现 `local_folder` + `webhook`，再按用户实际渠道实现邮件或企业微信等；个人微信通常没有任意自动发附件的官方通用 API，**不得声称已经能够直接发送个人微信**。超大视频可发送经过鉴权、带有效期的下载链接。

鉴权：默认仅本机使用；远程服务必须启用 token / OAuth、速率限制与文件权限。视频、音乐须来自用户有合法使用权的素材库；明确声明内容版权由使用者负责。

## 7. 开发仓库与可交付文件

```text
agent-beat-video/
├── README.md
├── pyproject.toml
├── config.example.yaml
├── .gitignore
├── LICENSE                 # 自有项目许可证待确认
├── THIRD_PARTY.md          # 依赖、来源、许可证记录
├── src/agent_beat_video/
│   ├── core/               # schema, models, configs
│   ├── assets/             # ingest, index, preprocess
│   ├── music/              # bpm, onsets, beat-grid, cache
│   ├── planner/            # selection, cuts, timeline
│   ├── typography/         # fonts, layout, templates
│   ├── renderers/          # ffmpeg, optional remotion
│   ├── quality/            # ffprobe, black frames, audio
│   ├── jobs/               # db, queue, worker, retries
│   ├── scheduling/         # timezone-aware daily jobs
│   ├── delivery/           # local, webhook, adapters
│   ├── mcp_server/         # stdio + optional HTTP
│   ├── api/                # optional REST
│   └── cli.py
├── templates/               # original text styles
├── examples/                # config, sample prompts, fixture generator
├── tests/                   # unit + integration + golden tests
├── docs/                    # architecture, MCP, deployment, licenses
├── scripts/                 # setup and smoke tests
└── output/                   # ignored from Git
```

必须有 `.gitignore` 忽略媒体素材、输出视频、token、数据库、临时文件及本地配置；准备 `Dockerfile` 或跨平台安装脚本，明确 `ffmpeg/ffprobe` 外部依赖的安装方式。

## 8. 推荐分阶段实施（每一阶段可独立验收）

### Phase 0 — 基线调研和许可证核验

1. 把本文件中参考仓库清单放入 `docs/research.md`。
2. 对准备直接引用的代码或依赖记录版本、许可证、兼容性；Remotion 先核对使用资格。
3. 使用生成的测试素材建立标准测试集，不上传用户私人素材。
4. 通过架构决策记录（ADR）明确 FFmpeg 首选渲染、Remotion 可选。

### Phase 1 — 最小真正可用的卡点工具

1. 导入 10 张图片、5 段短视频和 1 首测试音乐。
2. `librosa` 分析节奏；`CutPlanner` 输出逐帧时间线。
3. 用 FFmpeg 导出可播放的 20 秒 9:16 MP4，带至少一段中文标题及一种动画。
4. 使用 seed 生成至少 3 个不同方案；记录素材使用历史。
5. 运行 ffprobe/黑帧/音轨等最小质量检查。

### Phase 2 — Agent 接口

1. 开发 MCP stdio 服务，提供 `scan_assets`、`analyze_music`、`preview_edit_plan`、`create_video`、`get_job_status`、`get_video_result`。
2. 提供命令行等价能力与示例。
3. 给腾讯 WorkBuddy、OpenCode、Claude Desktop 等客户端分别提供配置示例、安装说明和真实调用测试；WorkBuddy 自定义 Connector 的 `stdio` / HTTP 接入方式优先验证。
4. 在 `integrations/workbuddy/` 准备 WorkBuddy 自定义 MCP Connector 包和中文使用说明，按官方要求说明授权与运行时条件；必要时设计 CLI + Skill 备选方案。
5. 接入异步任务管理；渲染失败可以重试，避免重复成品。

### Phase 3 — 每日生成与交付

1. 定时任务、自动选音乐、调用用户指定文案生成器或接收 Agent 文案。
2. 重复素材控制和文案去重。
3. 实现用户选择的交付渠道和重试通知。
4. 记录每日运行是否成功，支持补跑。

### Phase 4 — 精致字幕和成片优化

1. 3 套可切换的中文动态文字模板。
2. 音乐段落/高潮感知、转场概率配置、自动裁剪优化。
3. 可选 Remotion 高级渲染器；在许可符合条件且有价值时开启。
4. 输出预览与 QA 报告给 Agent，便于二次调整。

## 9. 验收测试（禁止只交付界面或空函数）

- **功能**：给一组真实图片、视频和音乐，输出能正常解码的 MP4，音乐存在、音画时长一致。
- **踩点**：输出 `analysis.json` 和 `plan.json`，记录原始拍点、实际切镜点和对齐误差。抽测节拍明显的音乐；人工评估柔和/复杂节拍音乐，不能只看数值。
- **随机性**：同一素材库用 3 个 seed 生成 3 条不同镜头序列；同 seed 同配置生成一致的计划。
- **画质**：不存在非预期黑帧、连续冻结画面、文字出界、中文乱码、音频削波。
- **任务**：创建后立即拿到 job ID；进程重启能恢复状态；重复请求不会无限重复生成；取消有效。
- **接入**：至少一次来自 OpenCode 或 Claude Desktop 的 `create_video` 调用成功；**必须额外通过腾讯 WorkBuddy 自定义 Connector 完成一次真实的创建、状态查询和结果获取流程**；CLI 等价调用成功。记录客户端版本及环境。
- **每日执行**：通过模拟跨日/重启时区测试，检查只生成预期数量并正确交付。
- **权限**：拒绝工作目录外路径、非法文件、缺失凭证和未经授权的远程访问。
- **开发**：测试通过；README 写明安装、示例、常见问题、许可证、真实的当前限制。

## 10. 可直接交给 ChatGPT Work 的执行指令

> 请根据仓库中的 `AgentBeatVideo_开源调研与开发需求_V1.1.md` 为我开发 AgentBeatVideo。先阅读调研表所列 GitHub 项目，重点确认成熟项目的架构、特定卡点项目的算法思路和所有将复用组件的许可证；不能直接照搬。请在我授权的 GitHub 新仓库 `agent-beat-video` 中实施，先做 Phase 0 和 Phase 1，交付一个真正能把图片/视频+音乐+中文文案剪成卡点 MP4 的命令行程序和测试。不要先做复杂 GUI。实现统一的逐帧时间线 JSON 以便后续 MCP、腾讯 WorkBuddy、Claude Desktop、OpenCode、定时任务共用。WorkBuddy 必须作为正式兼容目标：按官方文档实现自定义 MCP Connector 包，验证本地 stdio 或受鉴权的 HTTP 接入，记录真实客户端的端到端测试；不要仅因协议相同就宣称兼容。每完成一阶段要运行测试、提交代码、附示例产物与待办清单。没有确认的软件授权、素材文件或发送渠道时，保留适配接口并说明未完成，不要猜测或伪造已实现的功能。未获我许可，不要提交私有素材或密钥到 GitHub。

---

## 11. 参考来源（2026-11-23 已核对）

- https://github.com/harry0703/MoneyPrinterTurbo
- https://github.com/remotion-dev/remotion
- https://www.remotion.dev/pricing
- https://github.com/Zulko/moviepy
- https://github.com/librosa/librosa
- https://github.com/mli/autocut
- https://github.com/WyattBlue/auto-editor
- https://github.com/MTG/essentia
- https://github.com/GVCLab/CutClaw
- https://github.com/Merserk/BeatSync-Engine
- https://github.com/DisaterPeace/cadence
- https://github.com/FFmpeg/FFmpeg
- https://github.com/modelcontextprotocol/python-sdk
- https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture
- https://opencode.ai/docs/mcp-servers/
- https://www.codebuddy.ai/docs/zh/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector
- https://open.workbuddy.cn/docs/connector