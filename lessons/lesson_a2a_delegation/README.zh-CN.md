# A2A 与跨进程委派（`a2a-delegation`）

[English](README.md) · 简体中文

前面各课的工具都是函数，MCP 把函数搬进了独立的服务。本课再往前一步：把一件**有状态的任务**交给另一个进程里的 Agent。青石图书馆的咨询台 Agent（委派方，在运行器里）读不到服务手册，手册归资料核对员（被委派方，`worker.py` 启动的另一个进程）管。运行器用官方 `a2a-sdk` 读它的 Agent Card（能力发现），发一条消息创建任务，跟着任务状态 `SUBMITTED → WORKING → COMPLETED` 走，取回产物，再自己验收。四个练习分别走正常委派、超时后取消、远端失败、远端报告完成但结果不完整。## 一个重要的取舍：被委派方是确定性程序

被委派方是另一个进程，拿不到本次运行的 `RunContext`。它若调用模型，请求不会被记录，还得把密钥交给子进程，违反“密钥只在后端”和“运行数据只来自真实事件”两条红线。所以资料核对员**不调用模型**：它用 BM25 检索（复用 `lessons.lesson_keyword_retrieval.bm25` 和 `lessons.lesson_document_loading` 的青石图书馆手册语料，只 import，不改）加一条版本规则（现行版本取代旧版本，并在 `superseded` 里注明）。委派方的模型照常经 `RunContext.complete` 调用，请求和响应都被记录。

这是教学取舍，不是 A2A 的要求：协议只看 Agent Card、任务状态和产物，不关心对方里面是模型还是规则。正文第七节和“真实系统里远端有模型时，观测和凭据怎么分开”一节说明被取舍掉的部分。平台目前没有“子进程把模型请求转回父进程”的能力，本课没有自建绕过 `RunContext` 的通道。

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。

## 文件

- `runtime.py`：输入模型（`fault`、`deadline_seconds`）、委派会话 `Session`：
  - `discover`：读 Agent Card，检查 JSONRPC 接口、卡里的地址是否等于本次启动的地址、是否有技能接受 `application/json`；
  - `delegation_tool`：把卡里的技能写成模型唯一的工具 `delegate_task`；
  - `delegate`、`follow`：发消息、读流、按终态分类；
  - `cancel_after_timeout`：到期后 `CancelTask`，再 `GetTask` 读回终态确认；
  - `accept`：委派方的结果验收；
  - `_report`：实验报告。
- `worker.py`：被委派方。`ReferenceChecker.execute` 按 SUBMITTED、WORKING、产物、终态的顺序往事件队列放事件；`--fault slow|fail|partial` 注入故障；`--locale` 决定它写出文字的语言。自己绑 127.0.0.1 的空闲端口，第一行输出 `PORT <n>`。
- `locales/zh_CN.py`、`locales/en.py`：委派方的系统提示词、错误、报告文字；`locales/worker/`：被委派方的 Agent Card 与状态说明；`locales/fixture/`：离线脚本的说法与回答模板。
- `fixtures.py`、`test_lesson.py`：确定性测试模型与行为测试（真实子进程；两种运行语言；超时、远端失败、不完整结果；坏提议；指向别处的卡；停止后进程被回收；子进程拿不到密钥）。
- 平台：`course/protocols.py`（`spawn_local_service`、`run_until_cancelled`、`safe_child_environment`）。

## 四个练习

| 练习 | 被委派方的故障参数 | 看什么 |
| --- | --- | --- |
| 正常委派 | `none` | Agent Card → 工具 → 消息 → Task（SUBMITTED）→ 多次 WORKING → 产物 → COMPLETED → 验收通过 |
| 超时后取消 | `slow`（开工前先等 60 秒），时限 2 秒 | 到期后 `CancelTask`，再 `GetTask` 读回 CANCELED；没有无限等待 |
| 远端失败 | `fail` | 终态 FAILED，附对方的说明；协议是通的，不重试，不编答案 |
| 远端返回不完整结果 | `partial`（只核对第一条说法） | 状态是 COMPLETED，委派方的结果检查却没有通过 |

练习问题默认是同一句：“B2 研究证最多能借几册？周日几点闭馆？”模型要把它拆成 1 到 3 条说法一起交出去；每次运行只能委派一次。

## 证据

- `lesson.a2a_message`：每条 A2A 协议对象一条，带 `name`、`method`、`direction`（`client_to_agent` / `agent_to_client`）、`captured: "sdk_protobuf_message"` 和 `message`；有任务状态的带 `state`，终态另带 `terminal: true`。`message` 是 SDK 的 protobuf 对象用 `MessageToDict` 按协议字段名导出的内容，**不是线路上的原始字节**：没有 HTTP 头，也没有 JSON-RPC 外层；`method` 是本课按 SDK 调用写下的协议方法名。
- `lesson.a2a_process`：被委派方进程的 `started`（进程号、端口、故障参数、收到的环境变量**名**）和 `stopped`（端口是否已不再接受连接）。
- `request`/`response`、`tool_call`/`tool_result`：委派方的模型调用与委派工具的结果（`ok: false` 时带 `DelegationTimeout`、`RemoteTaskFailed`、`IncompleteResult`、`RemoteUnavailable` 等错误类型）。被委派方没有 `request` 事件，因为它不调用模型。
- `lesson.report`：能力发现、只连本次启动的地址、任务编号一致、等待有上限、结果验收、没有密钥、进程已停止这些检查；委派结果、最后状态、状态序列、时限、本方模型调用数、消息数、进程号、故障注入来源等指标；以及按时间排列的消息表。

## 实验看什么

1. **正常委派：从 Agent Card 到产物**：Agent Card、由卡生成的工具、发出的消息、SUBMITTED 的 Task、WORKING 与进度说明、产物、终态标记、任务编号核对和结果验收。预测题：这次运行会记下几条 `lesson.a2a_message`。
2. **三条失败路径：超时、远端失败、结果不完整**：`CancelTask` 及其回复、等待有上限的检查、终态标记、三种错误类型、结果检查、委派结果和模型的回答。
3. **进程边界：看不见的内部与拿不到的密钥**：子进程收到的环境变量名、没有密钥的检查、本方模型调用数、消息表、故障来源和端口关闭。

离线夹具（`fixtures.py`）只服务自动化测试：第一轮固定提出一次 `delegate_task`，拿到工具结果后引用返回的片段编号回答，委派失败时如实说“这次没能核对”。服务进程、A2A 消息和 BM25 检索都是真实执行的，只有模型的决定是脚本。夹具模拟的故障由被委派方的启动参数注入，报告里写明来源。真实模型可能拆出别的说法，结论以你自己的真实运行为准。

## 运行

```powershell
# 离线测试（确定性模型数据；被委派方进程、A2A 消息与检索真实执行；约一分钟）
.\.venv\Scripts\python.exe -m unittest lessons.lesson_a2a_delegation.test_lesson -v
# 单独启动被委派方看它的样子（第一行输出端口，Ctrl+C 退出）
.\.venv\Scripts\python.exe -m lessons.lesson_a2a_delegation.worker --locale zh-CN --fault none
# 真实运行（会产生模型用量）；--locale en 用英文运行
.\.venv\Scripts\python.exe scripts/run_live.py a2a-delegation delegate --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py a2a-delegation timeout --url http://127.0.0.1:8765
```

**运行语言：**委派方和被委派方的文字都来自各自的 `locales/` 目录；被委派方用 `--locale` 拿到同一份目录。工具名、技能 id、协议方法名和状态名是代码，各语言相同。

**停止与回收：**整个委派会话包在 `run_until_cancelled` 里；点停止时当前的 A2A 调用被取消，SDK 收尾，随后 `with spawn_local_service(...)` 退出：子进程先收到终止信号，3 秒后强杀。运行器再连一次端口，连不上才记 `port_closed`。子进程只拿 SDK 的安全环境变量，API 密钥不会传过去，测试在父进程里放了假密钥确认这一点。

## 参考与署名

Agent Card、Agent 执行器、产物与事件队列的划分，以及 MCP 与 A2A 的分工，参考 Microsoft AI Agents for Beginners 的 `11-agentic-protocols`（MIT）；不共享上下文的协作、Agent 间的通信与控制（状态查询、优雅与强制终止、级联取消）、跨组织协作 A2A 与多 Agent 失败模式，参考《深入理解 AI Agent》第 10 章与第 4 章“协作工具”一节，以及 `chapter10/parallel-web-research/message_bus.py` 的消息信封写法（[bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）。任务状态、取消语义（`TaskNotCancelableError`）、`contextId`、轮询与推送核对了 A2A 规范（a2a-protocol.org，Apache-2.0），SDK 用法核对了 `a2a-sdk` 1.2.x（[a2aproject/a2a-python](https://github.com/a2aproject/a2a-python)，Apache-2.0）。服务端、运行器、实验与语料用法由本项目编写，没有复制上述代码。
