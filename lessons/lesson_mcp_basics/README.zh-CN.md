# MCP 原理与工具接入（`mcp-basics`）

[English](README.md) · 简体中文

前面各课的工具都是 Agent 代码里的 Python 函数。本课用官方 Python SDK（`mcp` 2.x）把手册检索做成一个独立的 MCP 服务端进程，运行器经标准输入输出（`stdio`）连上它：真实地发现工具（`tools/list`）、调用工具（`tools/call`），再看参数不符、未知工具、业务错误和服务崩溃四种失败各落在哪一层；最后把发现的工具交给模型，分清“协议负责发现与传输”和“Agent 负责调度与决策”。三个本地练习不调用模型；Agent 练习需要真实模型连接。课程目前仍是 `planned`，只做过离线验证。

## 服务端与语料

- `server.py` 用 `MCPServer`（1.x 里叫 `FastMCP`）登记三个工具，检索复用 `lessons.lesson_keyword_retrieval.bm25` 和 `lessons.lesson_document_loading` 的青石图书馆手册语料（只 import，不改）：
  - `search_handbook(query, top_k=3)`：BM25 检索，`top_k` 限 1–5；返回 `query`、`count`、`hits`（片段编号、标题、锚点、得分、原文）。返回类型是 TypedDict，所以有 `outputSchema` 和 `structuredContent`。空检索词抛 `ToolError`。
  - `read_chunk(chunk_id)`：只按本服务索引里的片段编号读，传路径也只是“查不到的编号”，用 `ToolError` 回说明。
  - `service_status()`：报告进程号、片段数和收到的环境变量**名**（不含值），用来证明密钥没有传进子进程。
- 工具描述与业务错误按启动参数 `--locale` 来自 `locales/`；`--fault exit-on-search` 只在错误练习的第二个服务上使用（故障注入：收到检索就退出进程）。
- 服务端由 `course.protocols.python_module_server` 以 `python -m lessons.lesson_mcp_basics.server` 启动：只允许 `lessons.` 包下的模块，子进程只继承 SDK 的安全环境变量列表，标准错误输出被丢弃。

## 四个练习

| 练习 | 协议版本 | 模型 | 做什么 |
| --- | --- | --- | --- |
| 发现与调用（2025-11-25 握手） | `legacy`：`initialize` → `notifications/initialized` | 不调用 | 列工具；检索一次命中、一次没有命中（`count: 0` 也是正常结果）；调用 `service_status` |
| 发现与调用（2026-07-28 discover） | `auto`：先发 `server/discover`，每个请求在 `params._meta` 里带版本 | 不调用 | 同上，对照连接开头的差别 |
| 错误路径 | `legacy` | 不调用 | 参数不符（`top_k=50`）、未知工具、业务错误（`read_chunk("../../local_config.py")`），再起一个故障注入的服务：调用中途进程退出，以及崩溃后再请求 |
| 模型按发现的工具选择调用 | `legacy` | 调用 | `tools/list` → 宿主按 `MODEL_TOOLS` 只交出两个工具 → `to_model_tool` 原样转换 → `context.complete` → 调用提议经 `execute_proposal` 与 `call_over_mcp` 走 `tools/call` → 回答或停止（最多 3 次模型调用；连接断开即停） |

错误分层（本课锁定的 SDK 版本实测）：前三条收到 `isError: true` 的结果（工具错误，协议是通的）；后两条客户端抛出错误码 -32000 的 `MCPError`（协议错误，没有结果）。规范把“未知工具”列为 JSON-RPC 协议错误（示例 -32602），这个 SDK 却返回 `isError: true` 的结果，报告如实记的是实测分层。

## 证据

- `lesson.mcp_message`：平台 `recording_stdio` 记下的每条 JSON-RPC 消息，带 `server`、`direction`（`client_to_server` / `server_to_client`）和 `captured: "sdk_session_message"`。这是 SDK 消息对象按协议字段名导出的内容，不是原始字节：键顺序和空白不保留。
- Agent 练习另有 `request`/`response`（模型调用）和 `tool_call`/`tool_result`（平台记录，按调用 id 配对）；每次调用的 `tools/call` 消息夹在 `tool_call` 和 `tool_result` 之间。
- `lesson.report`：发现与调用的检查（握手、发现、命中、没有命中、没有密钥）、协议版本与工具表；错误路径每条一项检查和一行表格（哪一层回答、客户端看到什么）、故障注入说明；Agent 练习的宿主筛选、每个调用提议都经 MCP 执行、模型调用数、`tools/call` 次数、停止原因和责任分层表。

## 实验看什么

1. **课程检索 MCP 服务：发现与调用**：两种协议版本的第一条请求、`tools/list` 里的 `inputSchema`、第一次检索的 `structuredContent`、没有命中被当作正常结果、服务进程看到的环境变量名。
2. **四条错误路径落在哪一层**：参数不符的回复里 `isError` 为真；未知工具与业务错误同样有回复；服务崩溃和崩溃后的请求都抛 `MCPError`；故障注入写在报告里。
3. **Agent 经 MCP 调用：谁负责什么**：请求里只有两个工具、模型的调用提议、同一调用的 `tools/call`、`tool_result`、责任分层表与停止原因。

离线夹具（`fixtures.py`）只服务自动化测试：第一轮固定提出一次 `search_handbook`，拿到工具结果后按排第一的片段写一句带来源的回答。服务进程、协议消息和 BM25 检索都是真实执行的，只有模型的决定是脚本。真实模型可能选别的检索词或调用 `read_chunk`，结论以你自己的真实运行为准。

## 文件

- `server.py`：MCP 服务端（`build_server`、`main`）。
- `runtime.py`：输入模型、连接（`connect`）、错误分层（`attempt`、`classify`）、MCP 工具到模型工具定义的转换（`to_model_tool`）、经 MCP 执行调用提议的桥（`call_over_mcp`）、三个任务和报告。
- `locales/zh_CN.py`、`locales/en.py`：服务端的工具描述与业务错误、系统提示词、报告文字；`locales/fixture/` 是离线脚本的检索词和回答模板。
- `fixtures.py`、`test_lesson.py`：确定性测试模型与行为测试（真实子进程；两种运行语言；Schema 越界、未登记工具、轮数上限、连接断开；停止后进程被回收；子进程拿不到密钥）。
- 平台：`course/protocols.py`（`python_module_server`、`recording_stdio`、`run_until_cancelled`）。

## 运行

```powershell
# 离线测试（确定性模型数据；MCP 服务进程与检索真实执行）
.\.venv\Scripts\python.exe -m unittest lessons.lesson_mcp_basics.test_lesson -v
# 单独启动服务端看它的样子（它只读标准输入，Ctrl+C 退出）
.\.venv\Scripts\python.exe -m lessons.lesson_mcp_basics.server --locale zh-CN
# 课程开放后真实运行（Agent 练习会产生模型用量）；--locale en 用英文运行
.\.venv\Scripts\python.exe scripts/run_live.py mcp-basics tour --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py mcp-basics agent --url http://127.0.0.1:8765
```

**运行语言：**工具描述、业务错误、提示词和报告文字按运行语言来自 `locales/`（服务端用 `--locale` 拿到同一份目录）；工具名、参数名、协议方法名是代码，各语言相同。SDK 自己生成的文字（Pydantic 校验说明、`Unknown tool`、`Connection closed`）在两种运行里都是英文。

**停止：**整个协议会话包在 `run_until_cancelled` 里；点停止时 SDK 关闭标准输入、宽限后终止服务进程，运行记为已取消。

## 参考与署名

MCP 的客户端-服务器架构、三类原语、`tools/list` 的 token 成本和第三方服务端的三类风险参考《深入理解 AI Agent》第 4 章与其 `chapter4/` 配套代码（[bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）；宿主、客户端、服务端的划分参考 Microsoft AI Agents for Beginners 的 `11-agentic-protocols`（MIT）；MCP 作为统一工具接口与 smolagents 接入示例参考 Hugging Face Agents Course unit1/unit2（Apache-2.0）；宿主侧权限表与“注解不能当授权依据”参考 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) s14（MIT）。错误分类与工具注解的要求核对了 MCP 规范 2025-11-25 / 2026-07-28 的 Tools 一节，SDK 差异核对了官方 Python SDK 的 v2 迁移指南（2026-10-20）。服务端、运行器、实验与语料用法由本项目编写，没有复制上述代码。
