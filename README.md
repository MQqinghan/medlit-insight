# 文献罗盘 · PubMed 文献洞察（medlit-insight）

> 长沿科技 AI 全栈开发工程师笔试作品。输入一个研究方向，30 秒看清这个领域：
> 总量统计、年度趋势、期刊与分区格局、热点词云、近5年影响力 Top100、约500字中文分点综述。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 关键词检索 | PubMed E-utilities 真实检索，支持中英文关键词 |
| 领域统计 | 命中总量、近N年数量与占比、纳入分析样本量、中位 IF、1区占比、期刊指标匹配率 |
| 可视化 | 研究热点词云（MeSH 词频 + 标题实词）、年度发文趋势（逐年精确计数）、高产期刊 Top10、中科院分区分布 |
| 影响力榜单 | 近5年按影响因子降序 Top100，含期刊/年份/IF/分区 |
| AI 中文综述 | 基于入选文献摘要生成约500字分点综述；LLM 不可用时自动走统计模板兜底 |
| 导出 | Markdown / Word（.docx）/ PDF（浏览器打印） |
| 演示保障 | SSE 实时进度、磁盘缓存（同关键词秒出）、断网/LLM 故障均有兜底路径 |

## 快速开始

### 方式一：PyCharm 一键运行（推荐）

1. PyCharm 打开项目根目录，创建 venv（Python 3.10+），终端执行 `pip install -r requirements.txt`
2. 复制 `config.local.example.py` 为 `config.local.py`，填入 PubMed API Key 与 LLM Key（均可留空，留空时综述走模板兜底）
3. 直接 Run `run.py`，浏览器打开 <http://127.0.0.1:8000>

### 方式二：命令行

```bash
pip install -r requirements.txt
cp config.local.example.py config.local.py   # 然后编辑填入密钥
python run.py
```

### 冒烟测试（可选）

```bash
python scripts/smoke_test.py
```

进程内起服务 → 打请求 → 断言 → 退出，不依赖服务常驻；真实调用 PubMed，约 1-2 分钟。

## 目录结构

```
medlit-insight/
├── run.py                    # PyCharm 一键启动入口（传 app 对象 + NO_PROXY 注入）
├── config.local.example.py   # 密钥模板（复制为 config.local.py）
├── requirements.txt
├── app/
│   ├── main.py               # FastAPI 入口：SSE 流式分析 + 导出接口
│   ├── pubmed.py             # E-utilities 异步客户端（限速 + 分批 + 重试退避）
│   ├── parser.py             # EFetch XML 解析（标题/摘要/MeSH/日期/ISSN）
│   ├── journals.py           # 期刊指标库匹配（ISSN 优先）
│   ├── analysis.py           # 统计 / 词云 / TopN 排名
│   ├── llm.py                # LLM 综述（prompt 工程 + 校验 + 模板兜底）
│   ├── export.py             # Markdown / Word 导出
│   ├── cache.py              # 磁盘缓存
│   └── static/               # 前端（Vue3 global build + ECharts，全部本地化，零 CDN）
│       ├── index.html
│       ├── css/style.css
│       ├── js/app.js
│       └── vendor/           # vue.global.prod.js / echarts.min.js / echarts-wordcloud.min.js
├── data/
│   ├── build_journals.py     # 期刊库生成脚本（加期刊只改这里）
│   └── journals.json         # 183 个常见医学期刊静态指标库
└── scripts/
    └── smoke_test.py         # 端到端冒烟测试
```

## 数据口径与免责声明（重要）

1. **PubMed 不提供影响因子与分区数据**。本项目使用本地静态示例库（`data/journals.json`，版本 v2026.10，
   IF 为约 2024 JCR 公开口径的近似整理值，分区为中科院大类 + JCR Q 双口径），
   仅用于演示完整数据流；**生产环境应替换为权威数据源**（中科院分区官方 / LetPub / 期刊官网）。
   数据源已隔离在 `JournalDB.lookup()`，换源不改业务代码。未命中库的期刊显示"暂无数据"。
2. **Top100 为样本内排名**：对"近N年前 N 篇（按相关度）"的样本按 IF 降序取前 100，
   页面与导出物中均已标注样本量与匹配率；年度趋势图为逐年精确计数，不受采样偏差影响。
3. **综述由 LLM 基于检索摘要生成**，prompt 已限定材料边界并做输出校验，仅供参考，不构成医学建议。

## 已知限制与路线图

- [ ] 被引数据（elink `pubmed_pubmed_citedin`）作为影响力辅助列——需更多 API 调用，v2 再做
- [ ] Top100 标题中文批量翻译（LLM）——演示效果好，按需开启
- [ ] 期刊库扩充至 500+，或接入实时数据源
- [ ] 研究方向聚类（MeSH 共现 / 向量聚类）
- [ ] Electron 套壳交付桌面端（后端 API-first，可直接复用）

## 技术栈

Python 3.10+ · FastAPI · httpx（异步并发 + 限速）· Vue3（global build，无构建步骤）· ECharts + wordcloud ·
SSE 流式进度 · python-docx · PubMed E-utilities · LLM（OpenAI 兼容协议）
