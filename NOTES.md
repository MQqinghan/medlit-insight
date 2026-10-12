# NOTES.md — AI 协作实录

> 本文件是开发过程的真实记录，作为"如何借助 AI 快速解决实际问题、如何发现并修正 AI 错误"的现场证据。
> 开发模式：**AI 助手（小清）承担全部代码生成与调研，本人负责需求拆解、口径决策、结果验证**。

## 一、开发前的四个关键技术判断（AI 预判 + 人工核实）

以下四点是开工前逐一核实过的，每一条都直接影响架构：

| # | AI 的"想当然" | 核实结果 | 处置 |
| --- | --- | --- | --- |
| 1 | 前端直连 eutils 就行 | NCBI 官方明确**不支持 CORS**（OA-PASS 项目 issue 中 NCBI 的正式答复） | 必须有后端代理 → 直接定了 FastAPI 方案，纯静态网页方案出局 |
| 2 | EFetch 用 `retmode=json` 拿结构化数据 | **EFetch 全文记录只支持 XML**，`retmode=json` 返回的是 MEDLINE 平文本 | 用 XML + ElementTree 解析 |
| 3 | PubMed 数据里什么都有 | **影响因子、分区 PubMed 根本不提供** | 本地静态期刊库（ISSN 优先匹配）+ "暂无数据"兜底 + 页面标注数据版本；对比过爬 LetPub：脆弱且有 ToS 风险，演示场景不划算 |
| 4 | 限速随便调 | 官方口径：无 key 3 req/s、有 key 10 req/s；efetch 超约 200 UID 要分批 | 信号量（并发 8）+ 令牌间隔（无 key 0.4s / 有 key 0.12s）+ 指数退避重试，双保险防 429 封 IP |

## 二、开发中真实抓到并修掉的 bug（冒烟测试驱动）

项目带 `scripts/smoke_test.py`（进程内起服务 → 打请求 → 断言 → 退出，22 项断言）。
以下问题都是被它抓出来的，不是"看起来没问题"：

1. **`UnboundLocalError: cannot access local variable 'years'`**
   AI 初版在 SSE worker 闭包里写 `years = min(max(int(years or ...)))`——右侧引用的 `years`
   因本函数内有赋值而成为局部变量，读取时尚未绑定。Python 经典作用域坑。
   修法：局部变量改名 `years_n`，不复写外层参数名。
   *教训：闭包/嵌套函数里给外层参数同名赋值，是 AI 生成代码的高发错误，编译期不报，运行期才炸。*

2. **python-docx 的 `Document` 对象直接塞进 `Response`**
   `AttributeError: 'Document' object has no attribute 'encode'`——python-docx 的 Document
   不是字节流，必须先 `doc.save(BytesIO())` 再 `getvalue()`。
   *教训：AI 对"返回文件"的库经常混淆"对象"与"序列化后的字节"，导出类接口必须真下载一次验证。*

3. **冒烟测试第二次跑"假 FAIL"**
   缓存生效后 SSE 只发一个 `done`（cache_hit），测试却按完整流水线断言。
   这是**测试脚本没考虑幂等路径**，不是代码错——按纪律先判断失败性质再改，给链路请求加 `force=1`，
   缓存命中单独作为一条断言（实测 0.97s 返回）。
   *教训：缓存/幂等分支要让断言覆盖"合法跳过"，不能一律当失败。*

4. **解析层的三个暗坑（写 parser 前预判，单测覆盖）**
   - 标题含内嵌 XML 标签（斜体物种名、下标），`.text` 会静默丢掉首个子标签后的全部内容 → 必须 `itertext()` 拼接；
   - 约 15% 文献没有 Abstract（letter/comment）→ 判空，词云与综述不受影响；
   - 作者有 `CollectiveName`（课题组署名）→ 不能假定都有 LastName；
   - `PubDate` 三种形态（Year+Month / MedlineDate"2023 Jan-Feb" / 仅 epub ArticleDate）→ 逐级回退取年份。

5. **打印 CSS 选择器作用域错误（PDF 导出会得到空白页）**
   AI 初版写 `body > *:not(#print-report){display:none}` 想"只打印报告区"，
   但 `#print-report` 在 `#app` 内部，`#app` 作为 body 的直接子节点被整体隐藏，打印区陪葬。
   修法：改为 `#app > *:not(#print-report)`。
   *教训：AI 写"只显示某区域"的 CSS 时不检查 DOM 嵌套层级；打印/导出这类"看一眼就能发现"的
   路径，必须真机走一次，不能只 review 代码。*

6. **密钥进命令行 → 被沙箱脱敏 → 401 假象（差点误判"key 是坏的"）**
   验证 qwen key 时 curl 直接返回 `invalid_api_key`，换域名、换协议重试均 401，
   一度判定"key 无效"。改用 `scripts/check_llm.py` 从 `config.local.py` 读 key 再发请求——
   **同一把 key 立刻 200，还成功对话**。原因：命令行里出现密钥形态的字符串会被执行环境脱敏/拦截，
   到达服务器的 key 已被改动，401 是假象。
   *教训：排查"鉴权失败"先排除"钥匙在传输路上被改过"；密钥只从配置文件读、不进命令行，
   既避开沙箱策略，也是安全惯例。*

7. **拿到的 PubMed key 被 NCBI 拒绝，最终发现是"拿错了 key"**
   本人第一版发来的 key（36 位混大写）被 NCBI 拒（`not wellformed` → 转小写后 `status invalid`），
   逐一排除格式、截断、大小写后仍失败。本人截图复核，发现 NCBI API Key Management 页上
   **真正的 key 是另一串**（36 位全小写），换入后立即 200。
   *教训：鉴权类问题"钥匙-锁-门"三要素逐个确认（钥匙本身对不对、格式对不对、用对没有），
   不要只在代码侧穷举；让用户回源头页面截图复核，比任何猜测都快。*
   另：NCBI 现行 key 已是 36 位小写十六进制（不再是老文档说的 32 位 UUID），以账号页实际显示为准。

## 三、设计取舍记录（为什么这么做，而不是那么做）

| 决策 | 选择 | 放弃的方案及理由 |
| --- | --- | --- |
| 期刊指标数据 | 静态 JSON 库 + 页面标注版本 + 接口隔离 | 爬 LetPub/中科院：脆弱、有 ToS 风险、演示当天可能挂；静态库换源不改业务代码 |
| Top100 口径 | 近N年前 N 篇样本内排名，UI 诚实标注样本量与匹配率 | 拉全集"精确排名"：热门词近5年可能上万篇，抓取耗时不可控，演示场景性价比低 |
| 综述可靠性 | prompt 圈定材料边界 + 字数/结构校验 + 重试一次 + 统计模板兜底 | 只调 LLM：超时/幻觉/格式飘都会让演示白屏；兜底保证区块永不空白 |
| 前端技术 | Vue3 global build + ECharts 全部下载到本地 | CDN 引入：现场网络抽风就全挂；npm 构建：多一道工序多一个故障点 |
| 启动方式 | `run.py` 传 app 对象 + 注入 NO_PROXY + PyCharm 直接 Run | 字符串导入 `"app.main:app"`：工作目录一变就 ModuleNotFound |
| 限速实现 | 信号量 + 令牌间隔 + 指数退避 | 只加 sleep：并发抓取时退化成串行，2000 篇要几分钟 |

## 四、演示保障设计（现场不翻车）

- **三级兜底**：PubMed 超时/429 → 退避重试 + 磁盘缓存；LLM 失败 → 统计模板综述；彻底断网 → 预置缓存关键词照常演。
- **SSE 进度流**：检索 → 抓取（第 x/N 批）→ 分析 → 综述，每阶段实时推送，避免"卡死"错觉。
- **缓存**：同关键词 + 参数 7 天内直接命中（实测 0.3~1.0s），现场同一个词重复演示不尴尬。

## 五、Key 验证实录（2026-10-12 全部完成）

### LLM（qwen3.7-flash）

- `scripts/check_llm.py`：从 `config.local.py` 读 key，遍历 8 个候选端点，输出可用端点 + 模型清单 + 一次真实对话。
- 结果：`sk-ws-` 新格式 key 在 **千问AI平台**（`maas.qianwenaiapi.com/compatible-mode/v1`）与 **百炼北京**（`dashscope.aliyuncs.com/compatible-mode/v1`）**双双实测通过**，模型清单 175 个，`qwen3.7-flash` 在线（另有快照版 `qwen3.7-flash-2026-07-15`）。
- 当前配置用千问AI平台端点（sk-ws- key 的签发方），百炼端点作备用，注释都写在 config.local.py 里。

### PubMed

- `scripts/check_pubmed_key.py`：从配置读 key，实测 esearch。
- 最终 key（NCBI 账号页 API Key Management）验证 **HTTP 200**，`diabetic retinopathy` count=53150，10 req/s 全速生效。

### 双 key 满血回归（`scripts/smoke_test.py`，真实数据）

- **22/22 断言通过**，全程 52 秒（600 篇样本 = 3 批抓取 + 10 年趋势 + 真实 LLM 综述）。
- 综述通路首次走真实 LLM：`source=llm`，625 字，5 个小标题，统计数字全部锚定真实结果。
- 缓存命中 0.34s。
- 期间修正：冒烟测试的"无 key 走兜底"断言改为**感知 key 存在性的双路断言**（有 key 断言 `source=llm`，无 key 断言 `source=fallback`），并给 review 增加 `model` 字段——页面徽标、页脚声明、md/docx 导出声明均按实际来源动态展示（LLM 生成时标注模型名，兜底时明示"统计模板生成"）。
