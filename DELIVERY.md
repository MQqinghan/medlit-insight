# DELIVERY.md — 笔试提交清单与操作指引

## 一、提交材料清单（发给 HR）

| # | 材料 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | GitHub 仓库链接 | 待推送 | 代码 + README + NOTES（AI 协作实录） |
| 2 | 演示视频（3 分钟） | ✅ 已完成 | `video/medlit_demo.mp4`（1080p，AI 全自动制作，见第三节） |
| 3 | PubMed 数据来源截图 | 本人截取 | 位置见下方第二节 |
| 4 | demo 系统页面截图 | 本人截取 | 方法见下方第二节 |
| 5 | 邮件正文 | 模板见下方第四节 | 附上述材料链接/附件 |

## 二、截图指引

### 1. PubMed 数据来源截图（证明数据真实来自 PubMed）

- **截图 A（检索结果页）**：浏览器打开 <https://pubmed.ncbi.nlm.nih.gov/?term=diabetic+retinopathy>
  （⚠️ 必须用英文关键词——PubMed API 对中文查询不做术语映射，直搜中文结果为 0），
  截取完整结果页——画面里能看到**结果总数**（如 "53,177 results"）和文献列表，
  与 demo 首页"检索总量"数字互相印证。
- **截图 B（单篇文献详情页，可选加分项）**：点进榜单第一文献（Journal of Clinical Investigation，
  IF 15.9），展示其 PubMed 原文页面，证明 demo 中的标题/期刊/年份与 PubMed 一致。

### 2. demo 系统页面截图

- 先跑一次完整检索，等结果全部渲染出来（含词云、图表、Top100、综述）。
- **整页截图**：结果页按 `F12` 打开开发者工具 → `Ctrl+Shift+P` → 输入 `capture full size screenshot`
  → 回车，保存整页长图（含所有图表与表格）。
- **局部特写**（建议各截一张）：
  1. 顶部搜索区 + KPI 统计卡；
  2. 词云 + 年度趋势图；
  3. Top100 表格前几行；
  4. AI 中文综述报告卡（含"qwen3.7-flash 生成"徽标与导出按钮）。

## 三、演示视频（已由 AI 全自动制作完成）

成品：`video/medlit_demo.mp4`（1920x1080，3 分 04 秒，13.3 MB）

**制作方式本身就是"深度使用 AI 工具"的实证**，邮件和面试中可主动讲：

| 环节 | 工具 | 脚本 |
| --- | --- | --- |
| 分镜配音（中文，Cherry 音色） | 通义千问 qwen3-tts-flash | `scripts/make_voice.py` |
| 浏览器自动操作 + 录屏（1080p） | Playwright 驱动 Edge | `scripts/record_demo.py` |
| 剪辑（进度段 4 倍速）+ 音画对位合成 | ffmpeg（trim/adelay/tpad） | `scripts/compose_video.py` |

视频结构（对应 DELIVERY 原脚本，配音由 TTS 生成，片尾已诚实标注制作方式）：
片头定位 → 输入检索（真实进度流，4 倍速）→ KPI/趋势 → 词云/期刊格局 → Top100 与数据口径 →
AI 综述（qwen3.7-flash，含兜底说明）→ 导出演示 → 片尾（AI 协证据实）。

> 若需重制或改文案：改 `make_voice.py` 里的 SEGMENTS → 跑三个脚本即可（详见 NOTES.md 第六节）。

## 四、邮件正文模板

> 主题：长沿科技 AI 全栈开发工程师笔试作品 —— 文献罗盘（PubMed 文献洞察 demo）
>
> 您好：
>
> 附件/链接为笔试 demo「文献罗盘」的全部材料：
>
> 1. GitHub 仓库：<链接>（含 README、AI 协作实录 NOTES.md、端到端冒烟测试脚本）
> 2. 演示视频：见附件 `medlit_demo.mp4`（3 分钟，含完整链路与设计思路讲解；
>    视频由 Playwright 自动操作录制、通义千问 TTS 配音，全流程 AI 制作）
> 3. PubMed 数据来源截图：<附件>（与 demo 统计数字互相印证）
> 4. demo 页面截图：<附件>
>
> 本地运行方式：`pip install -r requirements.txt` 后 `python run.py`，
> 或 PyCharm 直接 Run `run.py`（README 有详细说明）。PubMed API Key 与 LLM Key
> 在 `config.local.example.py` 中有配置模板，不配置也能运行（LLM 综述自动走统计模板兜底）。
>
> 期待与团队交流，谢谢！
>
> MQHuangq

## 五、提交前自检（逐条打勾）

- [ ] `config.local.py` 已填入 Key 且**未被提交进 git**（`git status` 确认）
- [ ] README 中的运行方式在自己机器上完整走过一遍
- [ ] 演示视频里展示的关键词与截图一致
- [ ] NOTES.md 无密钥泄露
- [ ] 仓库为 Public（HR 能直接打开）
