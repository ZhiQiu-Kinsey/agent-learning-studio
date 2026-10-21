# 事件信封 v2 与运行存储

[English](event-envelope-v2.en.md) · **简体中文**

确认日期：2026-10-01。对应[重构方案](redesign-plan.md)第一阶段子任务 3，约束来自[课程调研](curriculum-research.md) 6.1、6.3、6.5 与决策 4、5。

## 1. 运行是服务端资源

| 接口 | 作用 | 主要错误码 |
| --- | --- | --- |
| `POST /api/runs` | 请求体与原 `/api/run` 相同（`lesson_id`、`mode`、`question`、`exercise_id`、`inputs`）；校验通过后在后台启动，返回 `202 {run_id}` | `409 run_busy`（执行互斥） |
| `GET /api/runs/{id}/events?from_seq=N` | SSE：先回放存储中 `seq ≥ N` 的事件，再接续实时事件，收到 `done` 后结束；也接受 `Last-Event-ID` 头 | `404 run_not_found` |
| `GET /api/runs?limit=` | 运行列表（新到旧），只含元数据 | |
| `GET /api/runs/{id}` | 单次运行元数据，含 `event_count`、`last_seq` | `404 run_not_found` |
| `DELETE /api/runs` | 一键清除全部记录 | `409 run_active` |
| `POST /api/runs/{id}/cancel` | 停止指定运行的后续步骤；可选请求体 `{reason: user_stop\|page_closed}`，没有时记为 `api` | `409 run_not_active`、`404`、`422` |
| `POST /api/runs/{id}/approvals` | 提交人的审批决定：`{approval_id, decision: approve\|reject, payload_digest, note?, edited_payload?}`，见第 7.2 节 | `409 no_pending_approval`、`409 approval_digest_mismatch`、`409 approval_run_finished`、`422 approval_edit_not_allowed`、`404 run_not_found` |
| `POST /api/runs/{id}/resume` | 从这次运行的一个检查点启动新运行：`{checkpoint_id}`，返回 `202 {run_id, resumed_from}`，见第 7.3 节 | `404 checkpoint_not_found`、`409 run_still_active`、`409 checkpoint_stale`、`409 run_busy` |

错误响应为 `{"detail": "中文说明", "code": "稳定错误码"}`；`detail` 与旧接口一致，前端照常显示。

旧的 `POST /api/run` 已删除：前端、Python 测试、浏览器测试和 `scripts/verify_providers_live.py` 全部迁移到新接口，保留两条执行路径只会让“断线即取消”和“断线可续读”两种语义并存。

### 停止与断线

- 读取事件的连接断开**不会**取消运行，重连后按 `from_seq` 续读。运行结束前断开的连接数记在 `done.data.client_disconnects`（没有断开时没有这个字段）。网页的“断开事件连接（运行继续）”只关闭事件流，“重新连接”从最后一条事件接着读。
- 前端点击“停止运行”时调用 `cancel`（`reason: user_stop`），并继续读事件直到服务端记下 `done`，屏幕上显示的终态就是后端的终态；页面关闭（`pagehide`，`keepalive` 请求）时调用 `cancel`（`reason: page_closed`），沿用原来“关闭页面即停止后续步骤”的行为。停止的运行在 `done.data.cancel_reason` 写明原因。已经发出的非流式模型请求仍受 60 秒网络超时约束；流式请求在下一个分块之前就停止接收。
- 运行结束时先把 `done` 与运行状态写入存储、释放执行互斥，再对读者公开 `done`；客户端收到 `done` 时即可开始下一次运行。

### 续读如何做到不重不漏

`seq` 在单次运行内从 1 连续递增，存储以 `(run_id, seq)` 为主键。运行中只向读者公开已经提交的事件（`published` 水位）；读者断线后带 `from_seq = 最后收到的 seq + 1` 重连，服务端从存储回放，前端再丢弃 `seq ≤ 已收到` 的事件。连续重试 5 次都没有新事件才报告失败。

## 2. 信封字段

保留 v1 的 `schema_version`、`type`、`round`、`timestamp`、`data`，`schema_version` 改为 `2`，并新增：

| 字段 | 说明 |
| --- | --- |
| `run_id` | 32 位十六进制运行编号 |
| `seq` | 单次运行内从 1 单调递增 |
| `span_id` / `parent_span_id` / `span_kind` | 事件所属的 span 及其父级；`span_kind` 取 `run`、`agent`、`step`、`llm`、`tool`、`approval` |
| `actor` / `role` | 默认 `"agent"` / `null`；为多 Agent 与规划者、评审者等角色预留 |
| `provenance` | `real_run`、`recorded_run`、`offline_recompute`、`illustration`；本平台运行一律写 `real_run` |
| `representation` | 只在 `request` / `response` / `response_delta` 上有值，其余事件为 `null` |
| `sdk` | 只在 `representation = sdk_standardized` 时有值：`{name, version}` |

信封字段全部由服务端填写，课程代码只能发出 `type/round/data`，无法自行声明来源或表示层级。

### representation 如何确定

| 运行路径 | `representation` | `sdk` |
| --- | --- | --- |
| 百炼原生 HTTP（`course/api_client.send_bailian`，请求体即 urllib 发送的 JSON） | `http_body` | `null` |
| LiteLLM 多服务商（`course/providers.SDKCompletion`，输入是 SDK 参数，输出是 `model_dump()`） | `sdk_standardized` | `{"name": "litellm", "version": 已安装版本}` |
| 百炼 Embedding（`course/api_client.send_bailian_embeddings`，同一 Workspace 的 `/embeddings`） | `http_body` | `null` |
| LiteLLM Embedding（`course/providers.SDKEmbedding`，`litellm.embedding` 的 `model_dump()`） | `sdk_standardized` | `{"name": "litellm", "version": 已安装版本}` |
| 确定性测试适配器（仅自动化测试） | `sdk_standardized` | `{"name": "deterministic-test-adapter", "version": null}` |
| 不调用模型的本地课程 | `null` | `null` |

Embedding 请求与聊天请求走同一次运行的同一条连接，所以表示层级相同，不单独标注。

### Embedding 请求

课程用 `context.embed(texts, round_number=1, *, branch=None, dimensions=None)` 发 Embedding 请求。它仍是一对 `request` / `response` 事件，打开和关闭一个 `llm` span，`data` 多一个 `endpoint: "embeddings"`；没有 `endpoint` 的请求是聊天补全：

```json
{"type": "request", "data": {"endpoint": "embeddings", "representation": "http_body",
  "body": {"model": "text-embedding-v4", "input": ["片段一", "片段二"], "dimensions": 256}}}
{"type": "response", "data": {"endpoint": "embeddings", "representation": "http_body", "duration_ms": 412,
  "body": {"data": [{"index": 0, "embedding": [0.012, "…"]}, {"index": 1, "embedding": ["…"]}],
           "model": "text-embedding-v4", "usage": {"prompt_tokens": 9, "total_tokens": 9}}}}
```

- `body` 如实记录：请求体是发出的 JSON（没传 `dimensions` 就没有这个字段，不替服务商填默认值），响应体是服务商返回的完整 JSON 或 SDK 的 `model_dump()`。向量完整写进运行存储与录制，不截断；界面只在显示时截断并注明。
- 带 `branch` 时与并行聊天请求一样按 `branch` 配对。
- Embedding 请求计入 `max_model_calls`（课程 `runtime.max_rounds`），与聊天请求共用一份预算。
- 每次请求最多 `context.embedding_batch_limit` 条输入（百炼兼容接口 10），课程代码自己分批；超过上限、空列表或空字符串都是编程错误（`ValueError`），不发事件。响应的向量条数与输入不一致时，先记下响应再停止。
- 本练习要用 Embedding 时（`lesson.json` 声明了 `testing.embedding_factory`，或练习写了 `requires_embedding: true`），`run_start.data.embedding_model` 记录这次运行的 Embedding 模型。

红线：SDK 标准化数据绝不标成 `http_body` 或 `wire`；`EnvelopeBuilder` 拒绝没有 SDK 信息的 `sdk_standardized`，也拒绝给非 SDK 数据附 SDK 信息。目前没有任何路径产生 `wire` 或 `parsed`。`data.representation`（v1 字段）照旧保留。

## 3. span 规则

常量表只在 `server/envelope.py` 的 `SPAN_EVENTS` 声明一份；`scripts/export_trace_contract.py` 生成前端镜像 `frontend/src/generated/trace-contract.ts`，`tests/test_runs.py` 检查两者一致。修改常量表后运行：

```powershell
.\.venv\Scripts\python.exe scripts/export_trace_contract.py
```

| 事件 | 阶段 | span |
| --- | --- | --- |
| `run_start` → `done` | 开始 / 结束 | `run` 根 span，`parent_span_id = null` |
| `request` → `response` | 开始 / 结束；并行分支按 `data.branch` 配对 | `llm` |
| `tool_call` → `tool_result` | 开始 / 结束，按 `id` ↔ `tool_call_id` 配对 | `tool` |
| `response_delta` | 进行中（`progress`）：挂在同一 `branch` 的未关闭 `llm` span 上，不关闭它 | `llm` |
| `approval_requested` → `approval_resolved` | 开始 / 结束，按 `approval_id` 配对 | `approval` |
| `checkpoint`、`answer`、`error`、`lesson.*` 及其他未声明类型 | 瞬时 | 挂在当前 span |

- **step**：没有独立事件。同一 `round` 的事件属于同一个 step span，`round` 变化即开始新 step，父级是 run。`agent` 层预留给多 Agent 课程，当前单 Agent 运行不生成。
- `llm`/`tool` span 的父级是当前 step；事件没有 `round` 时父级是 run。
- 服务商对当前模型拒绝的请求参数（目前是 Anthropic 5 系列模型的 `temperature`）不会发出：`request.data.body` 是实际发出的请求，被省略的参数和课程原本写的值记在 `request.data.omitted_params`（`{values, reason: "unsupported_by_model"}`）；没有省略时没有这个字段。适配层仍不丢参数（`drop_params=False`），省略由 `RunContext` 在记录前完成。
- `response` 带 `branch` 时关闭同一 `branch` 的 `llm` span，不带时关闭最近一个未关闭的 `llm` span（课程用 `context.complete(..., branch=...)` 发起并行请求）；`tool_result` 关闭 `id` 相同的 `tool` span。找不到可关闭的 span 时按瞬时事件处理，不凭空配对。
- 瞬时事件挂在最内层未关闭的 `llm`/`tool` span；没有时，有 `round` 挂在该轮 step，无 `round` 挂在 run。
- 新 step 开始或运行结束时，仍未关闭的 `llm`/`tool` span 保持未关闭，表示“没有结果”（例如被停止），不补造结束事件。
- 开始/结束事件的 `span_id` 就是它打开/关闭的 span；瞬时事件的 `span_id` 是所在 span。span id 形如 `run-1`、`step-2`、`llm-3`、`tool-1`，只在单次运行内唯一。

## 4. 运行存储

- 文件：`.runtime/runs.sqlite3`（已在 `.gitignore`），首次创建运行时才打开；WAL 模式、`synchronous=FULL`、`secure_delete=ON`。
- 表：`runs`（`run_id`、`lesson_id`、`exercise_id`、`mode`、`model`、`provider_id`、`representation`、`provenance`、`schema_version`、`status`、`created_at`、`finished_at`、`locale`）与 `events`（`run_id`、`seq`、`type`、`event`），`(run_id, seq)` 为主键。`locale` 是运行语言；加入它之前建的库在打开时补上这一列，旧运行都是中文运行，记为 `zh-CN`。
- append-only：每个事件写入后立即提交；`events` 上的触发器拒绝 `UPDATE`。`done` 与运行状态在同一事务提交。唯一的删除路径是一键清除，清除后截断 WAL。
- 只存储已脱敏的事件：`scrub()` 先作用于 `data`，再序列化写库；信封字段由平台生成，不含用户输入。存储中的事件文本就是 SSE 发送的文本。
- 状态：`running`、`paused`（停在审批点等人决定）、`completed`、`error`、`cancelled`；服务启动时把遗留的 `running` / `paused` 标为 `interrupted`，这类运行没有 `done`，读取到末尾即结束。
- 恢复相关的列：`thread_id`（第一次运行等于自己的 `run_id`，恢复出来的运行沿用来源运行的）、`resumed_from_run`、`resumed_from_checkpoint`。旧库打开时补上这几列。检查点不另建表：它就是 `checkpoint` 事件，恢复时按 `(run_id, checkpoint_id)` 从事件表读取。
- 自动化测试通过 `tests/run_support.py` 把存储换到临时目录，从不写入真实 `.runtime/`。

## 5. 兼容策略

- 事件类型 `run_start/request/response/tool_call/tool_result/answer/error/done` 与 `lesson.*` 名称、`data` 内容均不变。
- `request` / `response` 可以带 `data.endpoint: "embeddings"`（见第 2 节“Embedding 请求”）；没有这个字段的旧记录都是聊天请求。`run_start.data.embedding_model` 只在练习使用 Embedding 时出现。
- `error.data` 可以带稳定的 `code`（和可选的 `params`），前端按 code 翻译并给出配置指引；目前只有 `embedding_model_missing`（所选服务商没有 Embedding 模型，`params.setting` 写该改哪个设置）。`message` 仍按运行语言记录原文。
- `run_start.data.locale` 记录运行语言（`zh-CN`、`en`）；界面请求的语言本课不支持、回落到源语言时，另记 `requested_locale`。没有 `locale` 的旧运行都是中文运行。运行语言决定事件里所有文字的语言，回放按记录原样显示，界面语言不同时只加标注，不翻译。
- 前端 `Trace` 类型同时接受 v1 与 v2，v2 字段按可选读取；`isTraceV2()` 判断是否可以推导 span。v1 记录只能按数组顺序读取。
- 下载的运行记录增加 `run_id`，事件为 v2；目前没有导入功能，将来导入时 v1 记录按上述规则读取。
- 随课录制（`recorded_run`）见第 6 节；流式分块、审批与检查点事件见第 7 节，旧记录里没有这些事件；哈希链在后续子任务实现。
- `done.data` 可以带 `cancel_reason`（停止的运行）与 `client_disconnects`；旧记录没有这两个字段。

## 6. 随课录制（`recorded_run`）

对应[重构方案](redesign-plan.md)第一阶段子任务 4 与[课程调研](curriculum-research.md)决策 5。实现：`server/recordings.py`；脚本：`scripts/export_recording.py`、`scripts/validate_recordings.py`（已接入 `scripts/validate_lessons.py`）。

### 6.1 文件与格式

一份录制是一个 JSON 文件：`lessons/<课程目录>/recordings/<name>.json`，`name` 为 kebab-case（小写字母、数字、连字符，≤ 64 字符）。文件恰好包含两个键：

```text
{ "metadata": { ... }, "events": [ 信封 v2 事件 ... ] }
```

| 元数据字段 | 说明 |
| --- | --- |
| `schema_version` | 录制格式版本，当前为 `2`（事件自身的信封版本仍是 `2`）；版本 2 起元数据带 `locale` |
| `lesson` | 课程 slug，必须与所在课程目录的 `lesson.json` 一致 |
| `exercise_id` | 练习 id，必须存在于当前课程 |
| `run_id` | 来源运行编号，与事件中的 `run_id` 相同 |
| `status` | `completed` 或 `error`（运行存储中“失败”记为 `error`），与 `done.data.status` 一致 |
| `model`、`provider_id`、`provider_label` | 取自运行记录与 `run_start` 事件，必须与 `run_start.data` 一致 |
| `representation` | `http_body` 或 `sdk_standardized` |
| `sdk` | `http_body` 时为 `null`；`sdk_standardized` 时必须是 `{name, version}`，两者都是非空字符串 |
| `recorded_at` | 这次真实运行的开始时间（运行记录的 `created_at`，ISO 8601，UTC） |
| `platform_version` | 导出时的平台版本，取法见下 |
| `source_hash` | 课程源码哈希，规则见 6.2 |
| `integrity_hash` | 事件完整性哈希，规则见 6.2 |
| `event_count` | 事件条数 |
| `locale` | 运行语言，取自运行记录，必须与 `run_start.data.locale` 一致，且是本课 `runtime.locales` 之一 |

**platform_version 取法**：`pyproject.toml` 的 `project.version` 加 git 提交，形如 `0.1.0+g<12 位提交>`；已跟踪文件有未提交改动时追加 `.dirty`（`git status --porcelain --untracked-files=no` 非空）。没有 git 时只写 pyproject 版本，读不到版本时写 `unknown`。它只用于追溯，不参与校验；与源码是否一致以 `source_hash` 为准。

### 6.2 哈希规则

两个哈希都写成 `sha256:<64 位小写十六进制>`。

- **integrity_hash**：对 `events` 数组做规范化 JSON 后求 sha256。规范化 = `json.dumps(events, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` 的 UTF-8 字节。键排序、无多余空白、非 ASCII 字符原样保留；不允许 NaN/Infinity。
- **source_hash**：参与的文件依次为：
  1. `lessons/<课程目录>/lesson.json`；
  2. `lesson.json` 的 `sources` 列出的全部文件，去重后按相对路径（POSIX 分隔符）字典序排序。

  对每个文件，先把字节中的 CRLF 统一为 LF，再求 sha256，得到一行 `<hex>  <相对路径>\n`（与 `sha256sum` 输出格式相同）。按上述顺序把各行拼接起来，对拼接结果的 UTF-8 字节求 sha256。`content.json` 等教学文字不参与哈希：它们不影响运行结果。

### 6.3 导出

```powershell
.\.venv\Scripts\python.exe scripts/export_recording.py --run <run_id> --name <name> [--replace]
```

脚本以只读方式打开 `.runtime/runs.sqlite3`，不经过 `RunStore`，因此不会把正在进行的运行标为中断。以下情况拒绝导出：

- `mode` 不是 `live`，例如离线确定性测试运行；
- 状态不是 `completed` / `error`，包括 `cancelled`、`interrupted` 和仍在进行的 `running`；
- 运行或任一事件的来源不是 `real_run`；
- 运行没有模型请求或响应（`representation` 为空），例如本地 Python 课程，此时无法证明运行来自真实模型；
- 课程源码（6.2 中的文件）的修改时间晚于这次运行的开始时间：此时录制无法对应运行当时的源码，需要重新运行；
- 同名录制已存在且没有加 `--replace`。

事件只改一处：顶层 `provenance` 由 `real_run` 改为 `recorded_run`。其余字段与顺序一字不改，不编辑、不裁剪、不拼接。`sdk` 取自事件中第一条模型请求或响应的 `sdk`。写文件前做两项检查，任何一项不通过都不写文件：

1. **安全检查**：报告全部可疑位置（JSON 路径），但不回显可疑值。
2. **完整校验**：与 6.4 相同，保证导出的文件一定能通过校验。

**安全检查范围**（元数据与事件中的所有字符串和字段名都检查）：

- 与当前已配置的任一 API Key 相同的字符串。只比对长度 ≥ 8 的密钥。脚本只能看到环境变量和本地配置中的密钥；网页中临时填写的密钥在写入存储时已经被 `scrub()` 替换。
- 常见密钥格式：`sk-` 前缀、`AIza`、`ghp_` 等 GitHub 令牌、`xox?-`、`AKIA`、`Bearer <令牌>`。`[REDACTED]` 不算。
- 认证字段：字段名为 `authorization`、`proxy-authorization`、`api_key`、`apikey`、`x-api-key`、`api_secret`、`secret_key`、`access_token` 或 `client_secret`，且值非空。比较时忽略大小写、`-` 和 `_`。
- 本机私有路径：盘符加 `Users` 或 `Documents and Settings` 的 Windows 路径、`/Users/<名>`、`/home/<名>`，以及本机用户主目录和项目所在目录的绝对路径（两种分隔符，不区分大小写）。

### 6.4 校验

`scripts/validate_recordings.py` 和 `scripts/validate_lessons.py` 都会扫描 `lessons/*/recordings/` 下的全部文件。任何一项失败时，脚本以退出码 1 结束，并给出文件和位置。

1. 文件名必须是 kebab-case 的 `.json`，所在目录必须有课程实现声明。
2. 安全检查同 6.3。
3. 元数据字段齐全且类型正确，`lesson` 与所在课程一致，`event_count` 与事件数一致。
4. `integrity_hash` 与重新计算的结果一致。
5. 表示层级与服务商一致：
   - 百炼原生 HTTP（`bailian`）只能是 `http_body`，且 `sdk = null`；
   - 其他服务商经 LiteLLM，必须是 `sdk_standardized`，并附 SDK 名称和版本；
   - `testing`、`local` 和确定性测试适配器一律拒绝。

   因此 SDK 数据无论怎样改标都不能成为 `http_body`。
6. **信封 v2 重放**：用 `EnvelopeBuilder(run_id, provenance="recorded_run", representation, sdk)` 按事件的 `type/data/round/timestamp` 逐条重新生成信封，结果必须与录制完全相等。这一条同时检查以下各项，span 规则不另写一份：
   - `seq` 从 1 连续递增；
   - span 的打开、关闭与父子关系；
   - `actor`、`role`；
   - 每条事件都是 `recorded_run`；
   - 只有模型请求和响应带 `representation` 与 `sdk`。

   此外还要满足：模型事件的 `data.representation`（v1 字段）与元数据一致；首条事件是唯一的 `run_start`，末条是唯一的 `done`；至少有一次模型请求；`run_start.data` 中的 `mode` 为 `live`，`lesson_id`、`model`、`provider_id`、`provider_label`、`trace_representation`、`locale` 与元数据一致。
7. `source_hash` 与当前源码一致。不一致时报“源码已变化，请重新录制”，不静默沿用。

### 6.5 只读接口

录制是课程资源，不写入运行存储，不出现在 `/api/runs` 中，也不能显示为“你的运行”。`{id}` 接受 slug 或别名，响应中统一返回 slug。

| 接口 | 作用 | 主要错误码 |
| --- | --- | --- |
| `GET /api/lessons/{id}/recordings` | `{lesson_id, recordings: [{name, valid, error_code, metadata}]}`，不含事件。源码过期的录制返回 `valid=false, error_code="recording_stale"`，并附元数据；结构、完整性或安全检查失败的录制，`metadata` 为 `null` | `404 lesson_not_found`、`404 lesson_not_available` |
| `GET /api/lessons/{id}/recordings/{name}` | 完整校验通过后返回 `{lesson_id, name, metadata, events}`；校验失败时不返回事件 | `404 recording_not_found`（含名称不合法）、`409 recording_stale`、`422 recording_invalid` |

每次请求都会重新校验，校验时使用后端当前配置的密钥。错误响应不包含录制名称、位置或任何被检出的内容。

自动化测试（`tests/test_recordings.py`）只在临时目录中构造课程、运行存储和录制，从不向仓库写入录制文件。真实录制需要用户先用真实模型运行，再用导出脚本导出。

## 7. 流式、审批与检查点

对应课程：流式输出与取消（`streaming-cancel`）、Hooks 与审批闸门（`hooks-approval`）、人工介入、检查点与恢复（`human-in-the-loop`）。这些事件只能由平台写：课程代码通过 `RunContext` 的方法产生它们，`context.emit()` 拒绝这些类型。

### 7.1 流式响应

`context.complete_stream(body, round_number=1, *, branch=None, include_usage=True, flush_interval_s=0.25, flush_max_chunks=40, stop_when=None)`：

```json
{"type": "request", "data": {"stream": true, "representation": "http_body",
  "body": {"model": "qwen-plus", "messages": ["…"], "stream": true, "stream_options": {"include_usage": true}}}}
{"type": "response_delta", "data": {"delta_index": 1, "chunk_range": [1, 1], "received_ms": [412, 412],
  "text": "", "chunks": [{"id": "chatcmpl-…", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": null}]}],
  "representation": "http_body"}}
{"type": "response_delta", "data": {"delta_index": 2, "chunk_range": [2, 9], "received_ms": [431, 655], "text": "检查点把执行位置…", "chunks": ["…8 个分块…"]}}
{"type": "response", "data": {"representation": "http_body", "duration_ms": 1890,
  "body": {"id": "chatcmpl-…", "model": "qwen-plus", "choices": [{"index": 0, "message": {"role": "assistant", "content": "…"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 22, "completion_tokens": 17, "total_tokens": 39}},
  "stream": {"assembled_from_chunks": true, "status": "completed", "chunk_count": 19, "delta_events": 4,
             "first_chunk_ms": 412, "first_token_ms": 431, "done_marker": true}}}
```

- **分块原样记录**：百炼原生 HTTP 的每个分块是一条 SSE `data:` 行里的 JSON（去掉 SSE 分隔，`data: [DONE]` 记为 `done_marker: true`，LiteLLM 拿不到这个标记，写 `null`）；LiteLLM 的每个分块是 SDK 分块对象的 `model_dump()`。信封的 `representation` 照旧按运行路径标注（`http_body` / `sdk_standardized` 附 SDK 版本）。
- **节流不丢块**：第一块单独成一条 `response_delta`，首块到达时刻在时间线上可见；之后每 `flush_interval_s` 秒或每 `flush_max_chunks` 块合并成一条。`chunk_range` 是本条覆盖的分块序号，相邻两条首尾相接；`received_ms` 是本条第一块和最后一块从请求发出前起算的毫秒数（本进程计时）。`text` / `reasoning` 是这些分块给第一个选项新增的文字，只为方便显示，完整内容以 `chunks` 为准。
- **拼合的响应**：最后一条 `response` 的 `body` 是平台按 OpenAI 兼容客户端的规则把分块拼成的对象（文字按选项拼接，工具调用片段按 `index` 合并，最后一个 `finish_reason` 和用量分块生效），不是服务商发来的单个响应体，`data.stream.assembled_from_chunks` 标明这一点。没有用量分块时 `body` 里没有 `usage`，界面写“未报告”。它关闭 `request` 打开的 `llm` span。
- **结束方式** `data.stream.status`：`completed`（流正常结束）、`stopped`（课程的 `stop_when` 返回真，另有 `stop_reason: "lesson"`）、`cancelled`（运行被停止：另有 `cancel_reason` 与 `discarded_after_cancel`，即停止时已经到达但没有交给运行、因此没有记录的分块数；之后到达的分块既不记录也不计数）、`error`（断流或服务商在流里返回 `error` 对象，另有 `error`）。`cancelled` 和 `error` 在记下 `response` 之后抛出，运行随后以 `cancelled` / `error` 结束。
- 一次流式请求计一次模型调用；请求在建立连接时就失败（例如 HTTP 401）时没有 `response`，与非流式请求相同。

### 7.2 审批

`context.request_approval(kind, summary, payload, *, timeout_s=300, risk=None, editable=False)`：

```json
{"type": "approval_requested", "span_kind": "approval", "data": {"approval_id": "approval-1", "kind": "file.write",
  "summary": "写入 notes/plan.md", "payload": {"path": "notes/plan.md", "content": "…"},
  "payload_digest": "sha256:…", "risk": "high", "editable": false, "timeout_s": 300, "expires_at": "2026-10-20T08:05:00+00:00"}}
{"type": "approval_resolved", "span_kind": "approval", "data": {"approval_id": "approval-1", "outcome": "approved",
  "decided_by": "learner", "note": "路径核对过", "payload_digest": "sha256:…", "requested_digest": "sha256:…",
  "edited": false, "waited_ms": 8123}}
```

- `payload_digest` 是参数的规范化 JSON（键排序、无多余空白、保留非 ASCII）的 sha256。提交决定时必须带上同一个摘要，证明决定针对的是页面上看到的那组参数。
- `outcome`：`approved`、`rejected`、`timeout`（`timeout_s` 内没人决定，`decided_by: "timeout"`）、`cancelled`（等待中运行被停止，`decided_by: "run_cancelled"`）。`decided_by: "learner"` 表示经接口提交，`offline_fixture` 表示离线测试夹具给的决定（只在离线测试模式出现）。
- `editable` 的请求可以批准修改后的参数：`edited: true`，`payload` 是实际批准的参数，`payload_digest` 是它的摘要，`requested_digest` 是原参数的摘要。
- 接口只接受：当前仍在执行的运行（否则 `409 approval_run_finished`）、当前待决的这条 `approval_id`（已决定、超时或停止后 `409 no_pending_approval`）、摘要一致（`409 approval_digest_mismatch`）；同一请求只接受一次。中间件照旧拒绝跨站请求。回放和录制只读显示审批记录，不能再批准。
- 等待期间运行状态是 `paused`，决定后回到 `running`；`approval` span 覆盖等待的区间，时间线上单独一条泳道。

### 7.3 检查点与恢复

`context.checkpoint(name, state)` 记一条瞬时事件：

```json
{"type": "checkpoint", "data": {"checkpoint_id": "cp-1", "name": "before-save", "state": {"draft": "…", "operation_id": "save-1"},
  "state_digest": "sha256:…", "thread_id": "<第一次运行的 run_id>", "source_hash": "sha256:…"}}
```

- `state` 必须能序列化为 JSON，序列化后不超过 64000 字符；一次运行最多 100 个检查点。`source_hash` 是课程源码哈希，规则与录制的 `source_hash` 相同。
- `POST /api/runs/{run_id}/resume {checkpoint_id}` 用来源运行的课程、练习、问题、输入、模式和运行语言启动新运行。新运行的 `run_start.data.resumed_from` 是 `{run_id, checkpoint_id, name, seq, state, state_digest}`，`run_start.data.thread_id` 与运行记录的 `thread_id` 相同；课程从 `context.resume_state` 读状态。
- 恢复**不重放**来源运行的任何请求、响应或工具调用；新运行里的请求都是真实的新请求。
- 拒绝恢复的情况：来源运行还在执行（`run_still_active`）；没有这个检查点（`checkpoint_not_found`）；课程源码在保存检查点之后变了（`checkpoint_stale`）；另一次运行正在执行（`run_busy`）。来源运行的状态不限：完成、出错、停止和被中断（服务异常退出后标为 `interrupted`）的运行都可以恢复。检查点存在运行存储里，服务重启后照常可用。
- 检查点只保存课程交给它的状态。外部副作用是否已经发生，要由课程在状态里记录操作标识并在恢复后核对；不能凭检查点存在就说外部动作天然幂等。
