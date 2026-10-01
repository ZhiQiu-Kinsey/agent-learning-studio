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
| `request` → `response` | 开始 / 结束 | `llm` |
| `tool_call` → `tool_result` | 开始 / 结束，按 `id` ↔ `tool_call_id` 配对 | `tool` |
| `answer`、`error`、`lesson.*` 及其他未声明类型 | 瞬时 | 挂在当前 span |

- **step**：没有独立事件。同一 `round` 的事件属于同一个 step span，`round` 变化即开始新 step，父级是 run。`agent` 层预留给多 Agent 课程，当前单 Agent 运行不生成。
- `llm`/`tool` span 的父级是当前 step；事件没有 `round` 时父级是 run。
- `response` 关闭最近一个未关闭的 `llm` span；`tool_result` 关闭 `id` 相同的 `tool` span。找不到可关闭的 span 时按瞬时事件处理，不凭空配对。
- 瞬时事件挂在最内层未关闭的 `llm`/`tool` span；没有时，有 `round` 挂在该轮 step，无 `round` 挂在 run。
- 新 step 开始或运行结束时，仍未关闭的 `llm`/`tool` span 保持未关闭，表示“没有结果”（例如被停止），不补造结束事件。
- 开始/结束事件的 `span_id` 就是它打开/关闭的 span；瞬时事件的 `span_id` 是所在 span。span id 形如 `run-1`、`step-2`、`llm-3`、`tool-1`，只在单次运行内唯一。

## 4. 运行存储

- 文件：`.runtime/runs.sqlite3`（已在 `.gitignore`），首次创建运行时才打开；WAL 模式、`synchronous=FULL`、`secure_delete=ON`。
- 表：`runs`（`run_id`、`lesson_id`、`exercise_id`、`mode`、`model`、`provider_id`、`representation`、`provenance`、`schema_version`、`status`、`created_at`、`finished_at`）与 `events`（`run_id`、`seq`、`type`、`event`），`(run_id, seq)` 为主键。
- append-only：每个事件写入后立即提交；`events` 上的触发器拒绝 `UPDATE`。`done` 与运行状态在同一事务提交。唯一的删除路径是一键清除，清除后截断 WAL。
- 只存储已脱敏的事件：`scrub()` 先作用于 `data`，再序列化写库；信封字段由平台生成，不含用户输入。存储中的事件文本就是 SSE 发送的文本。
- 状态：`running`、`completed`、`error`、`cancelled`；服务启动时把遗留的 `running` 标为 `interrupted`，这类运行没有 `done`，读取到末尾即结束。
- 自动化测试通过 `tests/run_support.py` 把存储换到临时目录，从不写入真实 `.runtime/`。

## 5. 兼容策略

- 事件类型 `run_start/request/response/tool_call/tool_result/answer/error/done` 与 `lesson.*` 名称、`data` 内容均不变。
- 前端 `Trace` 类型同时接受 v1 与 v2，v2 字段按可选读取；`isTraceV2()` 判断是否可以推导 span。v1 记录只能按数组顺序读取。
- 下载的运行记录增加 `run_id`，事件为 v2；目前没有导入功能，将来导入时 v1 记录按上述规则读取。
- 随课录制（`recorded_run`）、审批事件（`approval.requested/resolved`）与哈希链在后续子任务实现；本次只保证信封与存储能够承载。
