# Embedding 与向量检索（`embedding-retrieval`）

[English](README.md) · 简体中文

课号按课程表顺序计算，只在网页上显示；文件里提到其他课一律写课程 ID。## 本课要解决的问题

上一课 `keyword-retrieval` 的 BM25 只认字面：查询问“滞纳金”，资料只写“逾期费用”，就漏检。本课把每个片段交给 Embedding 模型变成向量，用余弦相似度按意思检索，再和 BM25 在同一查询集上逐条比较命中与漏检。向量要调用模型才能得到，所以本课还讲清楚：索引怎样保存、记下哪些来历，什么情况下旧索引不能再用。

本课只发 Embedding 请求，不调用聊天模型，也不生成回答。

**状态：**`available`，带一个已知限制。本课需要配置了 Embedding 接口的服务商。2026-10-21 没有配置这样的服务商（Anthropic 没有 Embedding 接口），平台在创建时拒绝了本课的所有运行，所以本课**没有用真实模型运行过**，只有离线测试覆盖（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：`Embedder` 按 `context.embedding_batch_limit` 分批调用 `context.embed`；`open_index` 读取或重建索引；`stale_reasons` 逐项说明旧索引为什么不能用；`compare` 让两种检索回答同一查询集 |
| `vector_index.py` | 暴力向量索引（RAG 核心模块，签名不变）：`cosine`、`VectorIndex.search/save/load/is_stale`、`index_path` |
| `locales/zh_CN.py`、`locales/en.py` | 报告标签、检查项、回答等运行时文本，每种运行语言一份 |
| `fixtures.py`、`test_vectors.json` | 离线测试向量：按概念词表构造，只服务自动化测试 |
| `test_lesson.py` | 行为测试：分批、保存与复用、过期检测、对照结果、错误路径、两种运行语言 |
| `content.json`、`content.en.json` | 教学内容与英文译文层 |

共用模块：语料与分块在 `lessons/lesson_document_loading/`，BM25 与查询集在 `lessons/lesson_keyword_retrieval/`。

## 练习

| 练习 | 做什么 | 第一次运行的 Embedding 请求 |
| --- | --- | --- |
| 建索引并检索 | 为默认片段建索引（已有且没过期就复用），用“晚还书要交多少滞纳金？”做向量检索；可以按文档过滤 | 4 批片段 + 1 次查询 = 5；索引复用时只有 1 |
| 向量检索与关键词基线对照 | 14 条查询同时交给向量检索和 BM25，各取前 5，用同一份人工标注判定 | 4 + 2 = 6；索引复用时 2 |
| 换维度：旧索引不能用 | 256 维改成 512 维：检查旧索引被判过期、维度不同没法比较、按新维度建索引并保存到另一个文件 | 4 + 1 + 4 = 9 |
| 资料改了：旧索引不能用 | 模拟 2025 年版开放时间下线：检查旧索引被判过期、误用时会找回已下线的片段、为新资料建索引（只在内存里，不覆盖正式索引） | 4 + 1 + 4 = 9 |

Embedding 请求计入 `lesson.json` 的调用上限（`max_rounds` 为 12）。中文默认 38 个片段、英文 36 个，每批最多 10 条。

## 索引保存在哪里、什么时候过期

- 真实运行写到 `.runtime/rag-index/<语言>/<模型>-<维度>.json`（不提交）。离线测试模式不碰这个目录，每次运行用一个临时文件夹。
- 索引记下 Embedding 模型、维度、资料版本（`corpus_version`，全部文档内容摘要的摘要）和片段列表。模型、维度、资料版本任一不同，或片段列表不同，就判定过期并重建，原因写进索引报告。
- 三道防线：文件名带维度；`is_stale` 检查来历；查询向量与索引维度不同时 `search` 直接报错。
- 服务商忽略 `dimensions` 参数、返回了别的长度时，运行器停下报错，不把长度不一的向量混进索引。
- 编码的文字是 `embedding_text`：片段原文去掉 `{#anchor}` 小节标记。BM25 的分词也去掉它，两路读到同样的文字；代价是编码的文字和片段原文不再逐字一致。`hybrid-retrieval` 直接用片段原文算向量，两课的索引各存各的，不能互相复用。`corpus_version` 只摘要文档内容，改了 `embedding_text` 的处理方式不会让旧索引被判过期，要自己重建。
- 所选服务商没有配置 Embedding 模型时，平台在开始前拒绝运行（错误码 `embedding_model_missing`），并引导到模型设置。

## 实验看什么

- **建索引并检索**：第 1 批请求的 `data.body.input` 和 `dimensions`；响应里的向量；索引报告里的模型、维度、资料版本和状态（新建或复用）；检索结果表的余弦相似度。
- **向量检索与关键词基线对照**：两项检查（同一查询集、同一批片段）；两种检索的命中率与完整覆盖率；逐条对照表；资料里没有答案的查询，向量检索仍返回 5 个片段。
- **索引过期检测**：过期原因逐项写出旧值和新值；换维度时旧索引拒绝比较；资料改动时旧索引的结果里出现 `hours-2025` 的片段，新索引没有。

## 运行

离线测试（不需要密钥，向量来自夹具）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_embedding_retrieval.test_lesson -v
```

真实运行需要配置带 Embedding 模型的服务商（百炼默认 `text-embedding-v4`，其他服务商见模型设置）。可以在网页运行，或：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py embedding-retrieval build-and-search --url http://127.0.0.1:8765
```

## 离线测试向量说明

`fixtures.py` 按 `test_vectors.json` 的概念词表构造向量：每个概念一维，按词出现的次数计数，另加一维所有文本共有的常数；同义词（滞纳金/逾期费用、late fee/overdue charge）共用一维，房间号、证件代号这类编号没有维度。所以离线对照里同义改写只有向量检索命中、`q02`（R-305）只有 BM25 命中，这是按设计复现的分工，不代表任何真实模型的结果。报告的“向量来源”一项会写明是测试向量。用量数字也是脚本写的。

## 参考与借鉴

- 《深入理解 AI Agent》（bojieli/ai-agent-book，Apache-2.0）第三章“稠密嵌入”与 `chapter3/dense-embedding/`：余弦相似度的手算方式、精确检索与 ANN 的取舍、recall@k 口径的说明。
- Claude Cookbooks（MIT）`capabilities/contextual-embeddings/guide.ipynb`：分批编码、把向量存盘避免重复付费、Pass@k 评估与上下文前缀的思路。
- Hugging Face Agents Course（Apache-2.0）`unit2/llama-index/components.mdx`：查询必须用建索引时的同一个 Embedding 模型。
- Microsoft AI Agents for Beginners（MIT）`05-agentic-rag`：检索结果要能评估、可追溯。

只做了改写借鉴，没有复制代码或逐句翻译；分批、过期判断、实验与测试向量由本项目编写。
