# MCP 连接生命周期与多服务（`mcp-lifecycle`）

[English](README.md) · 简体中文

上一课（`mcp-basics`）只连一个 MCP 服务。本课的宿主同时连着两个独立的服务进程：馆藏（`catalog`）和借阅（`loans`），两个服务都有一个叫 `search` 的工具。运行器用官方 Python SDK（`mcp` 2.x）的 `legacy` 模式连接它们，看清连接的五个阶段（启动、`initialize` 握手、`tools/list` 发现、调用、关闭）；给工具加服务前缀，只登记该给的工具，有副作用的工具要本次运行显式允许；然后真的杀掉借阅服务的进程，看调用怎么失败、重连怎么受限、回来的服务丢了什么、工具定义变了怎么办，最后核对退出时没有留下服务进程。三个本地练习不调用模型；Agent 练习需要真实模型连接。## 两个服务

两个服务都是 `MCPServer` 写的 stdio 进程，由运行器以 `python -m lessons.lesson_mcp_lifecycle.<模块> --locale <语言>` 启动，工具描述与业务错误来自 `locales/servers/`。

| 服务 | 工具 | 宿主登记 |
| --- | --- | --- |
| 馆藏 `catalog_server.py` | `search(query, limit)`、`get_book(book_id)`、`service_info()` | `search`、`get_book`（只读） |
| 借阅 `loans_server.py` | `search(member_id)`、`register_loan(book_id, member_id)`、`purge_loans()`、`service_info()` | `search`（只读）、`register_loan`（写）；`purge_loans` 与 `service_info` 不登记 |

- 借阅记录只存在借阅服务的进程内存里，编号 `L-0001` 起；进程重启，记录为空。
- `--variant v2`：`register_loan` 多一个必填参数 `due_days`（7–30），另有 `renew_loan`；用来演示重启后回来的服务换了定义。
- `--fault exit-on-start | hang-on-start`：故障注入，只给重启用——进程真的启动，然后立刻退出，或者活着却不读标准输入。
- `service_info` 报告进程号、借阅条数和进程收到的环境变量**名**（不含取值），宿主靠它确认连接、核对进程回收、检查没有密钥进入子进程。

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。模型组在 4 轮上限处结束（中间重试了一次读调用），没有看到模型自己对断连的说法。

## 四个练习

| 练习 | 模型 | 做什么 |
| --- | --- | --- |
| 两个服务：握手、命名与权限（`lifecycle`） | 不调用 | 连两个服务；用 `catalog__search`、`loans__search` 各做一次探测；再试三种越权调用（裸名 `search`、未登记的 `loans__purge_loans`、未允许时的 `loans__register_loan`）；关闭并检查进程 |
| 借阅服务崩溃：第二次重连成功（`crash-recover`） | 不调用 | 登记一笔借阅 → 运行器 `SIGKILL` 借阅服务 → 断连期间再写一笔（-32000）→ 在上限内重连（第一次重启注入 `exit-on-start`，第二次成功）→ 查借阅（`count` 为 0）→ 再次提交两笔写入（都不重发）→ 关闭并检查进程 |
| 重连超时，回来的服务换了定义（`crash-changed`） | 不调用 | 同上，但第一次重启注入 `hang-on-start`（等满读超时 5 秒，-32001），第二次连上的是 v2：重检发现 `register_loan` 变了、`renew_loan` 新增，变化的工具暂停调用 |
| 模型通过两个服务借书，中途断连（`agent`） | 调用 | 模型每轮只看到当前能用的带前缀工具；先 `catalog__search`，再 `loans__register_loan`；登记确认后运行器杀掉借阅服务，模型的 `loans__search` 得到 `ConnectionLost`；两轮之间宿主重连；最多 4 次模型调用 |

输入（`lab.inputs`）：`task`、`allow_writes`（默认关闭）、`restart_fault`、`failing_restarts`（0–3）、`max_reconnects`（0–3）、`restart_variant`（`v1`/`v2`）、`query`、`member_id`。改 `max_reconnects` 和 `failing_restarts` 能看到“用完次数，放弃”的路径。

## 宿主做了什么

- **一个服务一条连接**：`Host` 里每个服务一个 `ServiceConnection`，各有一个拥有者任务（`_own`）管进入、使用和退出 `async with Client(...)`，所以连接可以按任意顺序关闭。
- **登记与前缀**：`ServiceSpec` 写明服务标识、模块、期望的 `serverInfo.name`、登记工具及读写类型、探测调用；`qualified_name` / `build_routes` 生成 `<服务>__<工具>` 的路线，重名直接报错。发现了但没登记的工具没有路线。
- **三道关**：登记了吗；本次运行允许写入吗（`available` 的白名单）；服务现在是已连接且工具没有被暂停吗。被拒绝的调用不发出任何 `tools/call`。
- **写入记录**：每笔写入由“工具名 + 参数”识别，状态为已发出、已确认、被服务拒绝、结果不明；已确认和结果不明的不再发送（`WriteNotRepeated`）。
- **重连**：旧客户端不复用；次数上限对整个运行有效；退避 0.2、0.5、1.0 秒；每次新连接重新握手、发现、调用 `service_info`，再做一次可用性探测，通过才算接通；用完次数记为已放弃重连。
- **定义重检**：第一次发现后记下每个工具定义（名称、描述、输入 Schema）的指纹作基线；重连后对比，变化的登记工具暂停调用（`ToolChanged`），新增的不获得权限。
- **关闭**：`close_and_count` 关闭全部连接，再对握手成功的进程号做真实检查（`wait_gone`）。握手失败的进程由 SDK 回收，课程测试在 Linux 上另扫 `/proc`。
- **密钥**：子进程只继承 SDK 的安全环境变量，`service_info` 报告变量名，报告检查有没有疑似密钥的名字。

## 证据

- `lesson.mcp_message`：平台 `recording_stdio` 记下的每条 JSON-RPC 消息，带 `server`（`catalog` / `loans`）、`direction` 和 `captured: "sdk_session_message"`。这是 SDK 消息对象按协议字段名导出的内容，不是原始字节。
- `lesson.service_state`：每次连接状态变化：已连接（协议版本、`serverInfo`、能力、工具名、进程号、重检结果）、进程被终止（`cause: "fault_injection"`）、连接断开（错误码）、正在重连（次数、注入的故障）、重连失败、已放弃重连。
- `tool_call` / `tool_result`：运行器发起的调用标 `origin: course_program`；Agent 练习里是模型提议的调用，用调用 id 配对，两条之间夹着协议层的 `tools/call`。
- `lesson.report`：每个练习一份。握手、命名、权限、写入门、密钥、进程回收；断连、重连上限、数据丢失、不重发、重检；模型看到的工具、断连调用都不算成功、写入记录。没有执行的检查不带 `passed`。

## 实验看什么

1. **两个服务：握手、命名与权限**（两组：只读、放开写入）：每个服务的握手回复和 `tools` 能力；借阅服务列出的四个工具；`search` 变成两个名字；三次越权调用只在宿主这一层被拒绝；写入门随 `allow_writes` 翻转；没有密钥；遗留进程数。预测题：这次运行记几条 `lesson.mcp_message`。
2. **断连：写入结果不明，重连后数据没了**（三组：第二次重连成功、两次都失败放弃、模型经两个服务借书）：`stopped` → `lost`（-32000）→ `ConnectionLost` → 失败的重连 → 重连后 `count` 为 0 → 不重发；放弃的路径；模型看到的断连结果。
3. **回来的服务换了定义**（两组：v2、仍是 v1）：读超时 -32001；重连后 `tools/list` 里 `register_loan` 的新 Schema；重检结果；暂停的写入没有发给服务端。

离线夹具（`fixtures.py`）只服务自动化测试：Agent 练习里模型固定先检索、再登记第一本书、再查借阅、最后写一段如实说明断连的回答。服务进程、协议消息、杀进程、重连和进程回收都是真实发生的，只有模型的决定是脚本。真实模型会不会照系统提示词如实处理断连，离线验证不了。

## 文件

- `runtime.py`：输入模型、`ServiceSpec` 与 `SERVICES`、`qualified_name`、`build_routes`、`fingerprint`、`Host`（连接、重连、重检、探测、`call`）、三个任务和报告。
- `catalog_server.py`、`loans_server.py`、`serving.py`：两个 MCP 服务端，以及它们共用的命令行、启动故障和 `service_info` 内容。
- `processes.py`：`stop_process`（不带宽限地杀进程）、`pid_alive`、`wait_gone`（跨平台）。
- `locales/zh_CN.py`、`locales/en.py`：系统提示词、结构化错误、报告文字；`locales/servers/` 是两个服务端的工具描述、馆藏数据和业务错误；`locales/fixture/` 是离线脚本的检索词和回答。
- `fixtures.py`、`test_lesson.py`：确定性测试模型与行为测试（真实子进程；两种运行语言；握手顺序、命名与权限、断连与重连、状态丢失、不重发、重连上限、读超时、定义变化、停止后回收、子进程拿不到密钥、输入校验）。
- 平台：`course/protocols.py`（`python_module_server`、`recording_stdio`、`run_until_cancelled`）。

## 运行

```powershell
# 离线测试（确定性模型数据；两个 MCP 服务进程、杀进程与重连真实执行，全部约一分钟）
.\.venv\Scripts\python.exe -m unittest lessons.lesson_mcp_lifecycle.test_lesson -v
# 单独启动一个服务端看它的样子（只读标准输入，Ctrl+C 退出）
.\.venv\Scripts\python.exe -m lessons.lesson_mcp_lifecycle.loans_server --locale zh-CN --variant v2
# 真实运行；--locale en 用英文运行
.\.venv\Scripts\python.exe scripts/run_live.py mcp-lifecycle lifecycle --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py mcp-lifecycle agent --url http://127.0.0.1:8765
```

**运行语言：**系统提示词、结构化错误、报告文字和两个服务端的工具描述、馆藏数据、业务错误都按运行语言来自 `locales/`（服务端用 `--locale` 拿到同一份目录）；工具名、参数名、服务标识、状态代码和协议方法名是代码，各语言相同。SDK 自己生成的文字（`Connection closed`、`Request 'initialize' timed out`）在两种运行里都是英文。

**停止：**整个协议会话包在 `run_until_cancelled` 里；点停止时宿主的任务组被取消，SDK 关闭每个服务进程的标准输入并在宽限后终止它们，运行记为已取消，没有进程留下。

## 没做的事

- 真实模型运行两次（2026-10-21，中英文各一次）：断连后模型重试了一次读调用，4 轮用完运行结束，没有看到模型自己对断连的说法。
- 只实测了 stdio 传输；Streamable HTTP 的会话、续传与身份认证只在讲解里按规范 2025-11-25 概述，没有运行。
- SDK 的 `ClientSessionGroup`、新协议模式下的 `listen(tools_list_changed=True)` 只读过接口，没有在本课的服务上运行。
- 握手失败的进程没有进程号，进程回收检查不覆盖它们。

## 参考与署名

多服务的宿主划分、三类服务端风险、工具遮蔽、按需暴露与服务端各自的环境参考《深入理解 AI Agent》第 4 章及其 `chapter4/docker-compose.yml`、`DOCKER_DEPLOYMENT.md`（[bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）；宿主、客户端、服务端的一对一连接参考 Microsoft AI Agents for Beginners 的 `11-agentic-protocols`（MIT）；服务前缀 `mcp__{server}__{tool}`、改名后再查重名、宿主权限表参考 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) s14（MIT）；MCP 作为统一工具接口与 smolagents 接入示例参考 Hugging Face Agents Course unit1/unit2（Apache-2.0）。生命周期、能力协商、关闭顺序、超时与传输的说法核对了 MCP 规范 2025-11-25 的 `basic/lifecycle` 与 `basic/transports`。服务端、宿主、故障注入、实验与测试由本项目编写，没有复制上述代码。
