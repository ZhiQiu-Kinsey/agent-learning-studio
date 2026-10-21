# LangChain 与原生实现对照（`langchain-vs-native`）

[English](README.md) · 简体中文

同一个任务用两种写法各做一遍：平台已有的原生工具循环（`course/runner.py` 的 `run_agent`），和用 LangChain 写的同一个循环。两边共用问题、系统提示词、Python 工具函数、轮数上限（各 3 轮）和验收函数 `accept`，放在同一次运行里先后执行，时间线上可以逐轮对照。本课要回答：框架接手了哪几步（消息对象、工具定义生成、调用解析、结果回填），哪几步仍要自己写（循环、停止条件、错误处理、模型调用数上限、验收）。

课程状态仍是 `planned`。本课的实现只做过离线验证（确定性夹具 + 真实执行的 Python 工具），**没有用真实模型运行过**。

## 文件

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：`run_native`（复用 `run_agent` 与前面课程的 `setup`）、`run_langchain`（框架消息、`bind_tools`、`invoke`、`execute_tool_calls`，循环自己写）、共用的 `accept`、请求体逐字段对照 `request_diff`，以及两个不调用模型的练习 |
| `tools.py` | 用 `@tool` 把 `tool-selection`、`fail-safely` 的同一份工具函数登记成 LangChain 工具；`StrictNumbers` 是严格参数 Schema |
| `locales/zh_CN.py`、`locales/en.py` | 报告标签、程序写出的回答、样本说明。系统提示词和工具描述直接复用前两课的运行时文本，两种实现发出的文字因此完全相同 |
| `fixtures.py` | 只服务测试的确定性模型：没有工具结果时提一个调用（实参按紧凑格式写），有了就回答 |
| `test_lesson.py` | 行为测试：两种实现的事件序列、请求体差异、框架请求体与记录一致、失败任务、轮数上限、模型调用数上限、坏调用与缺 id、两个本地练习、生成 Schema 的版本锁定、英文运行无中文、取消 |

框架只用平台适配层 `course/frameworks.py`（`RunContextChatModel`、`execute_tool_calls`、`tools_as_callables`、`RunContextCallbackHandler`、`ai_message_from_response`），在 `local_tracing_only()` 里运行；不用 LangGraph 预置的工具节点，它会绕过事件记录。依赖只有 `langchain-core`（锁定 1.6.x，已装 1.6.12），不装 `langchain` 整包和服务商集成包。

## 练习

| 练习 | 调用模型 | 看什么 |
| --- | --- | --- |
| 正常任务：加法 | 是，最多 2 × 3 次 | 第 1–2 轮是原生循环，第 3 轮起是 LangChain；`lesson.framework_input` → `request` → `response` → `lesson.framework_output` 的分层；两份 `lesson.report`：责任映射表（每格数字来自本次运行）和请求体逐字段对照 |
| 失败任务：除数为零 | 是 | 两边都得到 `ok=false` 的结构化错误，失败写进了下一次请求；`lesson.framework_callback` 里的 `on_tool_error` |
| 实参转换（运行器构造） | 否 | 同一段实参交给原生工具、默认 `@tool`、严格 Schema：字符串数字、布尔值、多余参数在默认 `@tool` 下都“成功”了 |
| 调用解析（运行器构造） | 否 | 运行器构造的服务商响应（截断的 JSON、数组实参、缺调用 id）经适配层解析：`invalid_tool_calls`、补的 `framework_call_1_3`、回填顺序变化 |

两个本地练习的输入由运行器构造，事件标 `origin: course_program`，样本响应记为 `lesson.sample_response`，不是模型输出。

## 实验看什么

- **同一任务，两种实现**：第一对请求的差异来自 `@tool` 生成的工具定义（没有参数描述、没有 `additionalProperties`）和缺省的 `tool_choice`；第二对请求的差异来自框架重新序列化的 `arguments` 和被转成浮点数的工具结果（42 对 42.0）。验收函数只读工具结果和请求体。
- **框架悄悄做掉的事**：默认值掩盖失败（宽松校验）、无效调用提议不在 `tool_calls` 里、缺 id 由适配层补并单独列出、有效调用先回填。

## 运行

离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_langchain_vs_native.test_lesson -v
```

真实运行（课程改为 `available` 之后，会产生模型用量；两种运行语言各跑一次）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py langchain-vs-native sum --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py langchain-vs-native divide-zero --url http://127.0.0.1:8765 --locale en
```

真实运行时要核对：服务商对缺省 `tool_choice` 的处理、服务商发来的 `arguments` 写法（决定第二对请求有没有差异）、两边回答是否都通过验收。不要预设结果，以事件为准。

**运行语言：**支持中文和英文运行。工具名、参数名、事件名是代码，各语言相同；英文运行的事件里没有中文（Pydantic 的校验错误本身是英文）。

## 参考

- Hugging Face Agents Course（Apache-2.0）unit2 的框架介绍、LangGraph 与 LlamaIndex 入门页：什么时候需要框架、框架应提供的部件。
- Microsoft AI Agents for Beginners（MIT）02 与 04 课：模块化组件；工具 Schema 由带类型注解的函数生成。
- 《深入理解 AI Agent》（Apache-2.0）第一章“Harness 工程：模型之外的竞争力”：运行层五要素，框架主要覆盖上下文与工具。
- learn-claude-code（MIT）s01：没有上限的最小循环，作为“框架在骨架上叠层”的对照。
- LangChain 官方文档 tools 页（2026-10-20 核对）与已装 langchain-core 1.6.12 源码：`tool`、`bind_tools`、`AIMessage.tool_calls` / `invalid_tool_calls`、`parse_tool_call`、`convert_to_openai_tool`。

只借鉴组织方式和观点，代码和正文由本项目编写。
