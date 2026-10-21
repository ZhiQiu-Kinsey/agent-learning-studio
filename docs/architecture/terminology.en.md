# Terms and code names: how to write, annotate and check them

**English** · [简体中文](terminology.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

**Scope note.** The checks described here run on the Chinese lesson text. Chinese terms that are the subject of a rule stay in Chinese, followed by an English explanation. English text uses the `en` name from `curriculum/glossary.json` for each concept, consistently. The "write 中文（English）on first use" convention and the Chinese wording table (section 3) apply to the Chinese text only; the English text writes the term once, in lowercase running text, and never gives both languages side by side.

In lesson text, the words a reader might stop at and ask "what is this?" fall into four classes. Each class looks different on the web page and asks something different of the author.
The rules are checked by `server/vocabulary.py`. A change cannot be merged until `validate_lessons` and `tests/test_lesson_vocabulary.py` pass.

## 1. The four classes

| Class | Examples | On the web page | What the author does |
| --- | --- | --- | --- |
| Course concept | 工具调用 (tool calling), 上下文预算 (context budget), 任务卡 (task card), ReAct | Underlined at its first occurrence on each page, with a hover card giving the definition. In the **introducing lesson** the underline is a solid gradient; in other lessons it is dotted (a review) | Add it to `curriculum/glossary.json`; set `first_lesson` to the earliest runnable lesson that uses it. In the introducing lesson, write it on first use as "中文（English）"; in other lessons write the Chinese only |
| Background word | 分词器 (tokenizer), 消融 (ablation), 基线 (baseline), 夹具 (fixture), 混淆矩阵 (confusion matrix) | Dashed underline; the hover card is labelled "background knowledge" | Add it to the glossary with `kind` set to `background` and no `first_lesson`. In the text write Chinese only; no lesson writes the English alongside |
| Code name | `evidence`, `stop`, `lesson.plan`, `assistant` | Code style; if the author wrote a note, it also gets a dotted underline and a hover | Write the name as is; the frontend recognizes it automatically from the sources registered for the lesson. When the text depends on the reader understanding what it means, add an entry to `code_notes` in `content.json` |
| Ordinary word | 重试 (retry), 修订 (revision), 提示词 (prompt), JSON, HTTP, 正则表达式 (regular expression) | No annotation | Do not add it |

**Inclusion criteria.** A word goes into the glossary if it meets any one of these:

- It has a specific meaning in agent / LLM engineering that differs from, or is narrower than, its everyday meaning, such as 上下文 (context), 终态 (terminal state), 召回 (recall).
- It appears in two or more lessons and readers need to review it.
- It is machine-learning, testing or experiment-method vocabulary that even programmers may not know.

Words that appear in only one lesson and are fully explained on the spot are not added — for example 探针问题 (probe question) in the lesson on context compaction and probe questions. Words every programmer knows are not added either.

**Make names specific.** Chinese has no word boundaries, so the matcher finds short names inside longer words, for example 验收 (acceptance) inside 验收器 (acceptor). Therefore:

- Do not use common single-word nouns or verbs as term names or aliases. 引用 (citation/quote) became 来源引用 (source citation), 产物 (artifact) became A2A 产物 (A2A artifact), and aliases such as 压缩 (compaction) and 验收 (acceptance) were removed.
- When a name really does occur inside a longer phrase with a different meaning, list that phrase in `not_in`. For example the `not_in` of 评估 (evaluation) lists 评估者 (evaluator), so 评估者 in the text is skipped as a whole.

## 2. Code names and code notes

From the Python sources registered for each lesson (`sources` in `lesson.json`), the backend extracts identifiers and short string literals. (For runtime text under `locales/` it takes only identifiers and dict keys; the string values are natural language and do not count as code names.) It then adds platform names:

- message roles;
- JSON literals;
- run event names and run terminal states.

Names that are already in the glossary are removed (terms take priority). All the rest go into `code_names` in the lesson detail (`server/code_names.py`). When the text mentions these names, the frontend renders them in code style; no backticks are needed.

`code_notes` is only for names whose meaning the text **depends on the reader understanding**:

- Each note is at most 60 characters. Say what it is and what role it plays in this lesson; do not repeat the text.
- The name must really appear in this lesson's source and in this lesson's text, or the check fails.
- If the name explains itself (`goal`, `add_numbers`), or is only mentioned in passing, write no note.

```json
"code_notes": [
  {"name": "evidence", "note": "任务卡字段：验收要看哪条工具证据、满足什么条件（工具成功且结果为 42）。"}
]
```

(The example note reads: "Task card field: which tool evidence acceptance looks at, and what condition it must meet (the tool succeeded and the result is 42).")

The text must not contain lowercase English words that are neither terms nor this lesson's code names, such as `tokenizer`, `live`, `regex`:

- If it is a term, add it to the glossary and write it in Chinese.
- If it is code outside this lesson, rewrite it as a Chinese explanation.
- If it is an exercise id (such as `flow-rule`), use the exercise's Chinese name shown in the UI instead.

## 3. Writing rules

- **Explain before use.** A paragraph introduces at most two new concepts. A new word in a concept card must either be in the glossary (so it has a hover card) or be explained in the card itself.
- **One name per thing.** Use the standard wording in the table below. When a new lesson brings a new synonym, add it to this table first.
- **English appears once, in the introducing lesson.** Pairing Chinese and English everywhere reads as wordy: write it once in the introducing lesson; other lessons rely on the hover card for review.

The table is a Chinese wording table: it lists the Chinese wording to use and the Chinese wordings that are retired. The third column gives the meaning in English, with the English name the glossary or UI uses where there is one.

| Standard wording | No longer used | Meaning / English equivalent |
| --- | --- | --- |
| 工具结果 (the event name is written `tool_result`) | 回执, 工具回执, tool 回执, 收据 (all: "receipt") | tool result |
| 验收器 (decides whether the task is done), 验证器 (generic: a program that checks against rules) | 校验器, 检查器 (when meaning a program) | acceptor / validator. The glossary `en` name for 验证器 is Validator |
| 协议检查 (`validate_tool_history` in `messages-context`) | 验证器, 校验器 | protocol check |
| 运行器 (each lesson's run code), 运行层 (the concept) | 运行程序, 课程程序 | runner / run layer (harness) |
| 运行器发起的调用 (the event field is `origin: course_program`; the UI shows "运行器调用工具") | 程序发起, 课程程序发起 | a call initiated by the runner (the lesson's run code), as opposed to one proposed by the model |
| 未报告 (a number the provider did not report: usage, cache hits and so on; English: not reported) | 未知, when it means this kind of number | not reported |
| 运行语言 (the language of a run, written as `locale` in `run_start`), 运行时文本 (the prompts and messages in `locales/`) | 运行时语言, 多语言提示词 | run language / runtime text |
| 白名单 (noun), 登记 (verb) | 允许列表, 登记表 | allowlist / register |
| 工具定义 (the whole definition), 工具描述 (the `description` field) | 工具说明, 接口说明 | tool definition / tool description |
| 调用提议 (introduced by `tool-proposals`) | 提议行动, 行动请求, 调用请求 | tool call proposal |
| 调用 id (`tool_call_id`) | 调用标识 | call id |
| 消息历史 | 会话历史, 对话记录 | message history |
| 轮数上限 | 轮次预算, 有限轮数 | round limit |
| 提示词, 系统提示词 | Prompt, system 提示 | prompt, system prompt |
| 轨迹 | 正文里的 trace (trace written in English in the text) | trace |
| 结构化错误 | 结构化观察, 结构化失败 | structured error |
| 业务规则 | 领域规则 | business rule |
| 终态 | 运行生命周期结束 | terminal state |
| 服务商 | 供应商 | provider |
| 后端 (this platform's server process) | 服务端 | backend |
| 离线测试模式 | 离线模式, 测试模式, offline | offline test mode |
| 真实运行 | live, 现场 | real run |
| 故障注入 | 离线注入 | fault injection |
| Token | token (lowercase) | token (in Chinese text the English word is capitalized) |
| 分词器 | tokenizer | tokenizer |
| 并行 | 并发 (use 并发 only when describing the execution mechanism) | parallel / concurrent |
| 模型调用数 (the counting basis) | 模型请求数, 请求次数, 调用次数 | number of model calls |
| 有上限的 (of a loop) | 有界 | bounded (with a stated limit) |
| 迭代上限 (`max_iters`; introduced by `reflection-revision`) | 评估循环上限 | iteration limit |
| 评估者 (the role), 评审 (the action, the event, the stop reason) | 评估循环, 评估通过, 评委 | evaluator / review |
| 评审模型 (introduced by `prompt-experiments`; written "评审模型（LLM-as-a-Judge）") | 评委, LLM 评审 | review model (LLM-as-a-Judge) |
| 推理模型 (a model that generates reasoning content first and then gives the answer; a background word, Chinese only; at first use a one-sentence Chinese explanation may be added in parentheses, no English) | 先推理的模型, 先推理再回答的模型, 思考模型 | reasoning model |
| 人工标注 | 标注, 或 gold, in the text | human annotation |
| 实验报告 (the report panel on the lab bench) | 证据板 | lab report |
| 编码 Agent (tools like Claude Code and Cursor; a background word, no English in parentheses) | 编程助手, 编码助手 | coding agent |
| 学习者备注 | 问题栏 | learner notes |
| 回归 (a case that passed no longer passes after a change; introduced by `evaluation-sets`) | 退化, when it means this | regression |
| 配对分析 (comparing two versions case by case on the same cases; introduced by `evaluation-sets`) | 配对比较, when it means this | paired analysis |
| 开发集, 留出集 (introduced by `evaluation-sets`) | 调参集, 测试集 (for the held-out cases) | development set, holdout set |
| 不可评估 (the verifier lacks what it needs to decide, such as an open-ended answer or a missing source result) | 无法评估, 未评估 | unassessable |
| 角色切换 (introduced in `multi-agent-patterns`: one agent swaps its system prompt while the message history stays shared) | 角色转换, 多角色转换 | role switching |
| 交接包 (introduced in `multi-agent-patterns`: everything handed to another agent) | 移交包, 交接内容 | handoff package |
| 漏检 (introduced by `keyword-retrieval`: none of a query's annotated sections reach the first `top_k`) | 漏召回, 未召回, 没检索到 (for this) | retrieval miss |
| 命中率 (the share of annotated queries that hit; the reference book writes recall@k) | 召回率 (for this number: 召回 is already the memory lessons' term) | hit rate |
| Embedding (the English word, for the result, the model and the request: Embedding, Embedding 模型, Embedding 请求; introduced by `embedding-retrieval`) | 嵌入, 嵌入向量, 向量化模型 | embedding, embedding model, embedding request |
| 向量索引 (introduced by `embedding-retrieval`: chunk vectors saved together with the model, dimensions and corpus version) | 向量库, 向量数据库 (for this lesson's index file) | vector index |
| 归并函数 (introduced by `langgraph-state`: decides how a node's update is merged into the old value) | 合并函数, 规约函数, reducer in Chinese text | reducer |
| 路由函数 (the function on a conditional edge that reads the state and returns where to go; `langgraph-state`) | 条件函数, 路由器 for this | router function |
| 状态差异 (the fields a node returns, recorded as `lesson.graph_update`; `langgraph-state`) | 状态增量, 状态补丁 | state diff (state update) |
| 委派方, 被委派方 (the two ends of an A2A delegation; introduced by `a2a-delegation`; 远端 is only an adjective, as in 远端任务, 远端失败) | 客户端 Agent, 服务端 Agent, 远端 Agent (for these two ends; 客户端 and 服务端 are kept for MCP) | delegating side, remote agent |

The boundary between 评审 (review) and 评估者 (evaluator):

- 评审 refers to actions, events and stop reasons (phrases like 评审意见 "review comments" and 评审通过 "review passed"). It also refers to the review model in `reflection-revision`.
- 评估者 is only a role name in `orchestrator-evaluator`, the counterpart of the generator.
- 评估 on its own is a course concept in the glossary, introduced by the `evaluation-sets` lesson (see `evaluation` in `curriculum/glossary.json`). Earlier lessons do not use it for anything else.

The boundary between "未报告" (not reported) and "未知" (unknown):

- A number the provider did not report in the response (usage, cache hits, reasoning tokens) is written 未报告 (English: not reported). The number may exist; it just was not given this time, and it must not be replaced by a local estimate or by 0.
- 未知 (English: unknown) is only for values the program truly cannot know.
- `validate_lessons` and `tests/test_lesson_vocabulary.py` use `UNREPORTED` in `server/vocabulary.py` to check the text of runnable lessons (all readable text in every scene) and the `code_notes` notes. It rejects two patterns:
  - 用量 (usage), Token, 命中 (hit), 命中数 (hit count) or 缓存命中 (cache hit), followed within at most 4 characters (no 。；，、 or line break in between) by 未知, for example "用量未知", "Token 数未知", "缓存命中数仍未知";
  - 未知 or 未知的 immediately followed by 用量, Token 数 or 命中数, for example "未知用量", "未知的用量", "未知命中数".
- The regular expression covers only these phrasings. Reworded sentences such as "记为未知" (recorded as unknown), and text in the course catalog, glossary and onboarding, are left to the author. The matching check for English is in section 5.

Names within a single lesson must also stay fixed. For example:

- `context-budget`: 截取窗口 (truncating to a window). `context-compaction`: 规则压缩 (rule-based compaction), 清理旧工具结果 (clearing old tool results), 摘要压缩 (summary compaction), 探针问题 (probe questions).
- `persistent-memory`: 召回 (recall); 命名空间 (namespace) is already a course concept, introduced by `persistent-memory`, and the field name is written `namespace`. `memory-lifecycle`: 范围 (scope, field `scope`), 乐观并发控制 (optimistic concurrency control), 过时写入 (stale writes).
- `todo-planning`: messages the run layer **inserts**.
- `plan-and-replan`: 失败后重新规划 (re-planning after a failure, the strategy) and 修订计划 (revising the plan, the action).
- `observability-cost`: 账本 (the ledger, one row per span written by `Tracer`), 指纹 (fingerprint, `fingerprint`), 重复执行 (repeated execution: the second and later executions with the same fingerprint; cache hits do not count), 工具缓存 (tool cache, within one run only), 端到端耗时 (end-to-end time, the report label; the term is 端到端延迟, end-to-end latency), 不适用 (not applicable: tool rows have no token usage and show "—", which differs from not reported).
- `langgraph-state`: 终态节点 (terminal nodes: answer, ask_user, fail), 业务预算 (the business budget, `max_repairs`, as opposed to the recursion limit), 修正 (repair: going back to plan after a failed check), 验证节点 (the verify node, `verify`).
- `agentic-rag`: 检索记录 (the search record the runner inserts each round, event `lesson.harness_injected`), 重复查询 (a repeated query: the same set of terms with no larger top_k, still counted), 停止原因 (the stop reason, `lesson.stop`), 最后一次请求 (the last request after a limit, with `tool_choice` none, which can only answer), 变差 (got worse: a question where the loop does worse than static RAG in the per-question comparison; the term 回归, regression, is introduced by `evaluation-sets`).
- `goal-loops`: 执行者 (the worker, `Worker` in code; the `status` it hands in is the completion claim), 验收器 (the validator `evaluate_goal`, the program that performs the goal evaluation), 完成条件 (the completion condition, `CRITERIA`: field, shape of the value and source; the form the acceptance criteria take in this lesson), 通知卡 (the notice card, the worker's product, not the task card), 结局 (the outcome: complete, abandoned or budget exhausted, event field `decision`), 停止原因 (the stop reason, `reason_code`), 轮数上限 (the round limit, `max_rounds`, not the iteration limit, which belongs to the revision loop). The abandon condition and budget exhausted already appear in earlier lessons and are registered as background terms.

## 4. Author workflow (for new and revised lessons)

1. Before writing, check the glossary and the standard wording table above.
2. After writing, run `.\.venv\Scripts\python.exe scripts/term_report.py --lesson <slug> --full` and look at three things:
   - which introduced, review and background terms the lesson has;
   - which code names carry a note;
   - what problems remain.
3. **Read the whole text and look for Chinese terms.** The machine can only check words that are already in the glossary; unlisted Chinese terms have to be found by a human:
   - Go paragraph by paragraph and ask: would a reader who has only studied the earlier lessons get stuck on this word?
   - For those that would, use the criteria in section 1 to decide whether to add the word to the glossary or explain it on the spot.
4. Run `validate_lessons` and `tests/test_lesson_vocabulary.py`. The number of problems must be zero.

## 5. Checks on English text

The rules above only look at the Chinese source text. English text has three checks of its own, implemented by `english_problems` in `server/vocabulary.py`; a change cannot be merged unless `validate_lessons` and `tests/test_english_text.py` pass. They cover:

- translation overlays: each lesson's `content.en.json` and `lesson.en.json`, and `catalog.en.json`, `glossary.en.json` and `onboarding.en.json` under `curriculum/` (every translation in `texts`, stale entries included);
- English runtime text: `lessons/*/locales/**/en.py`, `en.md` and `course/locales/en.py` (whole files);
- English UI strings: `frontend/src/i18n/locales/en/*.json`.

The three rules:

1. **No Chinese.** English text must not contain Chinese characters, Chinese punctuation or full-width characters. Anything that has to stay goes into `ENGLISH_CJK_ALLOWED`; each entry is a file, a text path, an exact substring and a reason, and the file and path may be `*`. Allowed substrings are removed first, and what remains must contain no Chinese. Entries that are no longer used are reported too and must be deleted (`validate_lessons` checks entries that name a file; `tests/test_english_text.py` checks the `*` entries). Current entries:
   - any file: `(深入理解 AI Agent)`, the Chinese title of the reference book, in parentheses after the English title, so readers can find the book;
   - `how-llm-works.tokens.paragraphs.1` in `curriculum/onboarding.en.json`: the tokenization example "函数式编程" and the three pieces it is cut into;
   - `section-4.paragraphs.2` in `lessons/lesson_reflection_revision/content.en.json`: `` `s-1０４２` ``, showing that the digit class of Python regular expressions also matches full-width digits.
2. **Numbers the provider did not report are "not reported".** The counterpart of `UNREPORTED` in section 3 (`EN_UNREPORTED`, case-insensitive) rejects two patterns:
   - usage, token count, cache hit, hit count, or prompt / completion / reasoning / cached / input / output tokens, followed — with only linking words such as is, was, shown, as or still in between and no punctuation — by an optional colon, parenthesis or quote and then unknown, for example "usage unknown", "cache hits: unknown", "prompt tokens (unknown)";
   - unknown immediately followed by one of those nouns, for example "unknown usage", "unknown token count".
   Plain "tokens" is not included ("unknown tokens" in a tokenizer means something else). In the course catalog only the entries of runnable lessons (`lesson.<slug>.*`) are checked; entries of planned lessons and the source notes are planning text and, as in Chinese, are not checked yet.
3. **No "Chinese original plus English gloss".** Before the runtimes became bilingual, English translations could only quote the Chinese original, written as `"未报告" ("not reported")`. An English run now sends English, so English text quotes the English runtime text directly (`"not reported"`). A quoted string containing Chinese followed by a parenthesis and a quote is always rejected; the allowlist does not exempt it.

The other English style rules (sentence case, glossary `en` names for terms, the fixed UI vocabulary) are in "English style" in [Localizing a lesson](localizing-lessons.en.md).
