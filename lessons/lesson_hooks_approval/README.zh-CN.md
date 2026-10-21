# Hooks 与审批闸门（`hooks-approval`）

[English](README.md) · 简体中文

本课问一个问题：Agent 的写入类工具要真的改东西时，怎样在不改每个工具代码的前提下加检查，并让人在关键处点头，而且保证点头之后执行的就是点头时看到的那组参数？答案分四层：执行前的钩子对每次调用下裁决（放行、拒绝、改写参数、要求审批）；要审批的调用让运行进入 `paused`，等人批准、拒绝或超时；批准之后用决定里的参数执行，执行前再用参数摘要核对一次；执行后的钩子遮住敏感字段、读回写入、给返回模型的内容算摘要。

本课需要真实模型连接（模型负责提出调用），但审批只接受页面上的人的决定；离线测试模式用脚本化的“模型”和“审批人”，网页没有任何模拟入口。先修课是 `async-concurrency`；正文接着 `tool-proposals`（模型只提议调用）讲“提议和执行之间的那一道关”；下一课是 `human-in-the-loop`（进程重启之后从检查点恢复），`bash-coding-agent` 把审批用在每一条命令上，`reliable-tools` 讲同一个写入执行两次的后果。

> **工单台只是临时目录，不是隔离环境。** 四个工具真的读写文件，但只在本次运行的临时目录里工作，不联网，运行结束后整个目录删除。工具是本地进程里的普通 Python 函数：钩子和审批决定“哪些调用允许执行”，不决定“执行时能做什么”。

## 工单台与四个工具

`store.py` 的 `Desk` 每次运行都在新的临时目录里种下四张工单（`TKT-101` 到 `TKT-104`，客户的手机号和邮箱是编的），再空出一个发件箱文件 `outbox.jsonl`。

| 工具 | 读还是写 | 做什么 | 钩子给的风险 |
| --- | --- | --- | --- |
| `list_records` | 读 | 列出工单的编号、标题、状态、负责人 | 放行，不需要审批 |
| `read_record` | 读 | 读一张工单，客户手机号和邮箱由执行后的钩子遮住 | 放行，不需要审批 |
| `update_record` | 写 | 改一张工单的 `status`、`owner` 或 `note` | `medium`；关闭工单（`status` 为 `closed`）和改负责人是 `high` |
| `send_notice` | 写 | 往发件箱追加一条通知，发出后收不回 | `high`；收件人是群发地址 `all@corp.example` 时是 `critical` |

工具函数只管把事做完，不含任何策略；策略全在钩子里。每个工具有一个 Pydantic 参数模型（`gate.py` 的 `ARGUMENT_MODELS`），多一个或少一个参数都是 `invalid_arguments`，在任何规则之前就被拒绝。

## 钩子清单

执行前的钩子按顺序跑，顺序是设计的一部分（先改写，再拒绝，最后询问）：

| 钩子 | 裁决 | 规则 |
| --- | --- | --- |
| `normalize_arguments` | `rewrite` | 工单编号转大写，收件人和状态值转小写，去掉首尾空白；已经规范的参数返回 `allow`，改写是稳定的 |
| `record_scope` | `deny` | 工单编号不是 `TKT-` 加三位数字就拒绝，路径穿越写法在这里被拦下 |
| `recipient_domain` | `deny` | 收件人不是 `corp.example` 域名下的邮箱就拒绝 |
| `field_allowlist` | `deny` | 字段不在 `status`、`owner`、`note` 里，或状态值不合法，就拒绝 |
| `risk_level` | `allow` 或 `ask` | 只读工具放行；写入工具要审批并标风险等级；没分类的工具拒绝（`tool_not_classified`） |

链的规则（`hooks.py` 的 `run_pre_hooks`）：`deny` 立刻停；`rewrite` 把新参数交给后面的钩子；`ask` 先记下，多个 `ask` 取最高风险。执行后的钩子是 `redact_customer_data`（遮住客户联系方式）、`verify_effect`（从文件读回写入）、`audit_trail`（给返回模型的内容算摘要，排在遮蔽之后）。

## 练习

| 练习 | 任务 | 看什么 |
| --- | --- | --- |
| 只读放行，写入审批（`approve-write`） | 查看并修改 `TKT-102`，再通知负责人 | 只读调用没有审批卡；两次写入各一张；`no-early-effect`、`args-match-approval` 通过 |
| 拒绝与超时（`reject-timeout`） | 修改 `TKT-103` 并通知相关人员 | 群发通知被拒绝，备注交给模型；第二封通知等到超时；`refused-not-executed` |
| 改参数后重新过规则（`edit-recheck`） | 通知 `TKT-104` 的负责人，卡片可修改 | 收件人改到公司域名之外，批准后仍被 `lesson.hook_recheck` 拦下 |
| 批准之后参数被替换（`swap-guard`） | 通知 `alice@corp.example`，批准之后演示故障换掉收件人 | `lesson.guard` 的 `match` 为假，`approval_mismatch`，发件箱为空 |

输入有四个：`task`（上面四种任务文字）、`approval_timeout_s`（审批等待上限，3 到 300 秒，`reject-timeout` 预设 20 秒，其余 60 秒）、`allow_edit`（审批卡能否改参数，只有 `edit-recheck` 预设打开）、`late_rewrite`（批准之后故意改写收件人，只有 `swap-guard` 预设打开）。`late_rewrite` 是运行器按输入制造的教学故障，事件里标 `origin: fault_injection`，不是对真实攻击的模拟。

## 一次写入的事件顺序

```text
tool_call                  模型提议的调用（原样，尚未执行）
lesson.hook_pre            执行前钩子链：steps、changes（有改写时）、risk 或 denied_by、工单台摘要
approval_requested         审批请求：kind、summary、payload、payload_digest、risk、timeout_s、editable
approval_resolved          决定：outcome、decided_by、note、edited（改过时带 payload）、waited_ms
lesson.hook_recheck        只在审批时改过参数才有：复核结果、edited_fields、denied_by
lesson.guard               approved_digest、attempted_digest、match，故障注入时带 injected
lesson.hook_post           执行后钩子：redacted、verified、result_digest
tool_result                gate 的结果：ok、executed、error_type 等，模型下一轮读到的就是它
```

只读调用只有 `tool_call`、`lesson.hook_pre`、`lesson.hook_post`、`tool_result`。被钩子拒绝的调用没有后面几项；被拒绝或超时的调用有 `approval_*` 但没有 `lesson.guard` 与 `lesson.hook_post`。

模型读到的结果是 `{"ok": true, "result": {…}}`：外层 `ok` 说明平台处理了这次调用，内层 `ok` 和 `executed` 才是工具的结果。内层的 `error_type` 可能是 `invalid_arguments`、`hook_denied`、`approval_rejected`、`approval_timeout`、`approval_mismatch`、`edit_invalid`、`edit_not_normalized`，也可能是工具自己的 `record_not_found`、`unknown_owner`：审批通过不等于执行成功。

## 三份报告

- 第一份 `lesson.report`（钩子与审批设置）：每个钩子的阶段、作用和规则，审批等待上限，是否可修改，是否开启批准后改写。
- 第二份 `lesson.report`（调用台账）：每次调用的风险、钩子裁决、审批、结果，以及批准的、执行的、返回给模型的三个摘要。五项检查：`no-early-effect`（审批等待前后整个工单台的内容摘要相同）、`args-match-approval`（执行的参数摘要等于批准的）、`refused-not-executed`（被拒绝、拦下、超时的调用没有改动文件）、`summary-covers-args`（说明句写全了关键参数）、`customer-data-redacted`（返回模型的内容里没有客户原始联系方式）。没有可检查的对象时那一项不给结论，不写通过。
- 第三份 `lesson.report`（工单台的实际变化）：运行结束后从文件里读出的工单变化和发件箱，与台账对照（`effects-match-ledger`），最后才是模型的最后一句话。

最终回答由运行器写成：先写调用数、没有执行的调用和原因、实际变化，再附模型的原话，并写明以前面的记录为准。

## 运行

离线测试（模型和审批决定都是 `fixtures.py` 里的脚本；工具真实执行在临时目录里；决定来自 `lesson.json` 的 `testing.approval_factory`，事件里记为 `decided_by: offline_fixture`）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_hooks_approval.test_lesson -v
```

课程目录里把本课状态改为 `available` 之前，网页和接口不会运行它。可用之后，真实运行需要先配置模型；在另一个端口启动服务，不要占用你正在用的 8765：

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8790
.\.venv\Scripts\python.exe scripts/run_live.py hooks-approval approve-write --url http://127.0.0.1:8790 --ask-approvals
```

网页上审批卡由你批准或拒绝，可写备注；`edit-recheck` 的卡片还能改参数。网页没有自动批准的入口，`run_live.py --ask-approvals` 在终端里显示同样的卡片。回放、录制和“上次的运行”只读，不能再批准。

## 能证明什么，不能证明什么

- 能证明：这次运行里每次调用被哪个钩子改写或拦下，要审批的调用什么风险、谁做的决定、批准之前工具有没有执行（工单台的内容摘要前后对照），执行的参数摘要是否等于批准的，以及文件里真实发生了哪些变化。
- 不能证明：工具“安全”。工单台是临时目录里的普通文件，没有隔离；钩子只执行写进去的规则；审批只证明有人看过卡片，不证明参数是对的，也防不了人看走眼。
- 离线测试里的“模型”和“审批人”是脚本，不代表任何真实的模型或人；`swap-guard` 的替换是故意制造的故障。真实模型会提出什么调用、会不会按拒绝备注换办法，以你自己的运行记录为准。
- 没有做过真实模型的验证：本课目前只做了离线验证（脚本化模型、真实 Python 工具、真实的临时目录），没有写任何真实运行的结论。

## 文件

| 文件 | 说明 |
| --- | --- |
| `hooks.py` | `HookResult` 与四种裁决、执行前的钩子链 `run_pre_hooks`、执行后的钩子 |
| `gate.py` | `Gate`：形状检查、钩子、审批（`request_approval`）、修改后复核、摘要核对、执行、结构化拒绝 |
| `store.py` | `Desk`：临时目录里的工单文件和发件箱，以及能证明“没有变化”的内容摘要 |
| `runtime.py` | 参数输入、四个工具的定义、Agent 循环、三份报告和最终回答 |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：系统提示词、工具描述、四种任务、拒绝说明、报告标签和最终回答 |
| `fixtures.py` | 离线测试用的脚本化“模型”和审批决定，只服务自动化测试 |
| `test_lesson.py` | 行为测试：钩子链与顺序、审批各结果、修改后复核、摘要核对、遮蔽、文件证据、停止和两种运行语言 |
| `content.json`、`content.en.json` | 教学内容与英文译文层 |

## 参考

借鉴 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT）的权限三道闸门与钩子事件，《深入理解 AI Agent》第 1、4、5 章（Apache-2.0）的执行层护栏、事前审批与风险评级，[AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（MIT）`06-building-trustworthy-agents` 的人在回路笔记本（动作前闸门、风险分级、审计记录），以及 [Hugging Face Agents Course](https://github.com/huggingface/agents-course)（Apache-2.0）里“控制与自由”一节对需要人在回路的流程的说明；代码、提示词和实验由本项目编写，没有复制上游代码。固定版本、阅读范围和许可证见 `docs/architecture/reference-study.md`，审批的平台接口见 `docs/architecture/event-envelope-v2.md` 第 7 节。
