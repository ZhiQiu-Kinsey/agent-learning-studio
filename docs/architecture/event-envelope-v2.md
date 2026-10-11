# 事件信封 v2 与运行存储

确认日期：2026-10-01。对应[重构方案](redesign-plan.md)第一阶段子任务 3，约束来自[课程调研](curriculum-research.md) 6.1、6.3、6.5 与决策 4、5。

## 1. 运行是服务端资源

| 接口 | 作用 | 主要错误码 |
| --- | --- | --- |
| `POST /api/runs` | 请求体与原 `/api/run` 相同（`lesson_id`、`mode`、`question`、`exercise_id`、`inputs`）；校验通过后在后台启动，返回 `202 {run_id}` | `409 run_busy`（执行互斥） |
| `GET /api/runs/{id}/events?from_seq=N` | SSE：先回放存储中 `seq ≥ N` 的事件，再接续实时事件，收到 `done` 后结束；也接受 `Last-Event-ID` 头 | `404 run_not_found` |
| `GET /api/runs?limit=` | 运行列表（新到旧），只含元数据 | |
| `GET /api/runs/{id}` | 单次运行元数据，含 `event_count`、`last_seq` | `404 run_not_found` |
| `DELETE /api/runs` | 一键清除全部记录 | `409 run_active` |
| `POST /api/runs/{id}/cancel` | 停止指定运行的后续步骤 | `409 run_not_active`、`404` |
| `POST /api/runs/{id}/approvals` | 审批骨架，请求体 `{approval_id, decision: approve\|reject, note?}` | `409 no_pending_approval`、`404 run_not_found` |

错误响应为 `{"detail": "中文说明", "code": "稳定错误码"}`；`detail` 与旧接口一致，前端照常显示。

旧的 `POST /api/run` 已删除：前端、Python 测试、浏览器测试和 `scripts/verify_providers_live.py` 全部迁移到新接口，保留两条执行路径只会让“断线即取消”和“断线可续读”两种语义并存。

### 停止与断线

- 读取事件的连接断开**不会**取消运行，重连后按 `from_seq` 续读。
- 前端点击“停止运行”或页面关闭（`pagehide`，`keepalive` 请求）时调用 `cancel`，沿用原来“关闭页面即停止后续步骤”的行为。已经发出的模型请求仍受 60 秒网络超时约束。
- 运行结束时先把 `done` 与运行状态写入存储、释放执行互斥，再对读者公开 `done`；客户端收到 `done` 时即可开始下一次运行。

### 续读如何做到不重不漏

`seq` 在单次运行内从 1 连续递增，存储以 `(run_id, seq)` 为主键。运行中只向读者公开已经提交的事件（`published` 水位）；读者断线后带 `from_seq = 最后收到的 seq + 1` 重连，服务端从存储回放，前端再丢弃 `seq ≤ 已收到` 的事件。连续重试 5 次都没有新事件才报告失败。

## 2. 信封字段

保留 v1 的 `schema_version`、`type`、`round`、`timestamp`、`data`，`schema_version` 改为 `2`，并新增：

| 字段 | 说明 |
| --- | --- |
| `run_id` | 32 位十六进制运行编号 |
| `seq` | 单次运行内从 1 单调递增 |
| `span_id` / `parent_span_id` / `span_kind` | 事件所属的 span 及其父级；`span_kind` 取 `run`、`agent`、`step`、`llm`、`tool` |
| `actor` / `role` | 默认 `"agent"` / `null`；为多 Agent 与规划者、评审者等角色预留 |
| `provenance` | `real_run`、`recorded_run`、`offline_recompute`、`illustration`；本平台运行一律写 `real_run` |
| `representation` | 只在 `request` / `response` 上有值，其余事件为 `null` |
| `sdk` | 只在 `representation = sdk_standardized` 时有值：`{name, version}` |

信封字段全部由服务端填写，课程代码只能发出 `type/round/data`，无法自行声明来源或表示层级。

### representation 如何确定

| 运行路径 | `representation` | `sdk` |
| --- | --- | --- |
| 百炼原生 HTTP（`course/api_client.send_bailian`，请求体即 urllib 发送的 JSON） | `http_body` | `null` |
| LiteLLM 多服务商（`course/providers.SDKCompletion`，输入是 SDK 参数，输出是 `model_dump()`） | `sdk_standardized` | `{"name": "litellm", "version": 已安装版本}` |
| 确定性测试适配器（仅自动化测试） | `sdk_standardized` | `{"name": "deterministic-test-adapter", "version": null}` |
| 不调用模型的本地课程 | `null` | `null` |

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
| `answer`、`error`、`lesson.*` 及其他未声明类型 | 瞬时 | 挂在当前 span |

- **step**：没有独立事件。同一 `round` 的事件属于同一个 step span，`round` 变化即开始新 step，父级是 run。`agent` 层预留给多 Agent 课程，当前单 Agent 运行不生成。
- `llm`/`tool` span 的父级是当前 step；事件没有 `round` 时父级是 run。
- `response` 带 `branch` 时关闭同一 `branch` 的 `llm` span，不带时关闭最近一个未关闭的 `llm` span（课程用 `context.complete(..., branch=...)` 发起并行请求）；`tool_result` 关闭 `id` 相同的 `tool` span。找不到可关闭的 span 时按瞬时事件处理，不凭空配对。
- 瞬时事件挂在最内层未关闭的 `llm`/`tool` span；没有时，有 `round` 挂在该轮 step，无 `round` 挂在 run。
- 新 step 开始或运行结束时，仍未关闭的 `llm`/`tool` span 保持未关闭，表示“没有结果”（例如被停止），不补造结束事件。
- 开始/结束事件的 `span_id` 就是它打开/关闭的 span；瞬时事件的 `span_id` 是所在 span。span id 形如 `run-1`、`step-2`、`llm-3`、`tool-1`，只在单次运行内唯一。

## 4. 运行存储

- 文件：`.runtime/runs.sqlite3`（已在 `.gitignore`），首次创建运行时才打开；WAL 模式、`synchronous=FULL`、`secure_delete=ON`。
- 表：`runs`（`run_id`、`lesson_id`、`exercise_id`、`mode`、`model`、`provider_id`、`representation`、`provenance`、`schema_version`、`status`、`created_at`、`finished_at`、`locale`）与 `events`（`run_id`、`seq`、`type`、`event`），`(run_id, seq)` 为主键。`locale` 是运行语言；加入它之前建的库在打开时补上这一列，旧运行都是中文运行，记为 `zh-CN`。
- append-only：每个事件写入后立即提交；`events` 上的触发器拒绝 `UPDATE`。`done` 与运行状态在同一事务提交。唯一的删除路径是一键清除，清除后截断 WAL。
- 只存储已脱敏的事件：`scrub()` 先作用于 `data`，再序列化写库；信封字段由平台生成，不含用户输入。存储中的事件文本就是 SSE 发送的文本。
- 状态：`running`、`completed`、`error`、`cancelled`；服务启动时把遗留的 `running` 标为 `interrupted`，这类运行没有 `done`，读取到末尾即结束。
- 自动化测试通过 `tests/run_support.py` 把存储换到临时目录，从不写入真实 `.runtime/`。

## 5. 兼容策略

- 事件类型 `run_start/request/response/tool_call/tool_result/answer/error/done` 与 `lesson.*` 名称、`data` 内容均不变。
- `run_start.data.locale` 记录运行语言（`zh-CN`、`en`）；界面请求的语言本课不支持、回落到源语言时，另记 `requested_locale`。没有 `locale` 的旧运行都是中文运行。运行语言决定事件里所有文字的语言，回放按记录原样显示，界面语言不同时只加标注，不翻译。
- 前端 `Trace` 类型同时接受 v1 与 v2，v2 字段按可选读取；`isTraceV2()` 判断是否可以推导 span。v1 记录只能按数组顺序读取。
- 下载的运行记录增加 `run_id`，事件为 v2；目前没有导入功能，将来导入时 v1 记录按上述规则读取。
- 随课录制（`recorded_run`）见第 6 节；审批事件（`approval.requested/resolved`）与哈希链在后续子任务实现。

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
