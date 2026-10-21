# LangChain 工具与结构化适配（`langchain-tools`）

[English](README.md) · 简体中文

本课把 `structured-output` 一课的业务契约（`TaskCard` 与可信事实）原样交给 LangChain 的组件：用工具装饰器登记检索工具 `lookup_lesson`，用 `with_structured_output` 解析课程卡。要回答的问题是：框架接手解析以后，工具失败还算不算失败，解析失败会不会被吞掉，服务商到底支持哪些能力。本课需要真实模型连接；状态仍是 planned，目前只做过离线验证。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：检索（`look_up_facts`，最多 2 次模型调用）→ 生成课程卡（`generate_card`，最多修复 1 次）→ 能力矩阵与最终报告 |
| `components.py` | 业务契约的框架登记：`make_lookup_tool`（`@tool` 加类型注解）、`handwritten_definition`（同一工具的手写定义）、`card_schema`（只补工具描述的 `TaskCard` 子类）、`business_checks`（程序的业务校验） |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：系统提示词、注入指令、工具描述、错误与报告文字 |
| `fixtures.py` | 离线测试夹具，只服务自动化测试：按请求里的 `tool_choice` 判断是检索还是生成课程卡，注入的问题只出现在第一次 |
| `test_lesson.py` | 行为测试：真实执行工具、四个练习两种运行语言、三类“安静的失败”、上限与停止、取消、观察点命中 |

模型调用都经 `course/frameworks.py` 的 `RunContextChatModel` 发出，所以每次调用前后各有一条 `lesson.framework_input` / `lesson.framework_output`，中间是 RunContext 记录的 `request` / `response`。工具一律经 `execute_tool_calls` 执行，不用框架预置的工具节点。框架代码包在 `local_tracing_only()` 里，LangSmith 追踪不会上传数据。依赖只有 `langchain-core`（1.6 系列，实测 1.6.12）。

## 练习

| 练习 | 注入 | 离线运行的请求数 | 看什么 |
| --- | --- | --- | --- |
| 正常：检索后生成课程卡 | 无 | 2 | 生成的工具定义与手写定义一致；第 2 轮 `tool_choice` 为 `required`；原始 `arguments` 字符串与框架 `args` 字典 |
| 故意缺字段 | 第一次课程卡省略 `prerequisite` | 3 | 框架结果 `schema_error`，业务校验未执行；运行器写的修复反馈回答失败的调用 id |
| Schema 合法，事实写错 | 第一次把 `prerequisite` 写成 `dependent-calls` | 3 | 框架结果 `parsed`，业务校验未通过；修复后通过 |
| 工具报错 | 第一次用目录名 `task_contract` 查询 | 3 | `ToolException` 变成 `ok=false` 的工具结果并回到下一次请求；最终报告的工具失败次数仍为 1 |

输入 `repair` 设为 `false` 时，第一次没通过就停止，停止原因写 `repair_off`。注入写在提示词里，真实模型不一定照做（例如服务商按 Schema 约束生成时，缺字段的注入可能不生效），以自己的运行为准。

## 实验看什么

- **结构化学习任务工具适配**：同一个 `TaskCard` 契约，对照框架的解析结果（`parsed`、`schema_error`、`invalid_arguments`、`no_structured_call`）和程序的业务校验。Schema 合法不等于事实正确。
- **工具错误保持失败语义**：`ToolException` → `tools_as_callables` → `ok=false`、`error_type=ValueError`；不打开 `handle_tool_error`，因为它会把异常文字当成正常输出。
- **能力矩阵**：每项能力写本次证据和状态（本次实测 / 适配回退 / 未验证）。离线运行写“离线夹具”；`strict` 与服务商原生 JSON Schema 输出本课没有发送，一律未验证。

## 运行

```powershell
# 离线测试（确定性模型数据，工具真实执行）
.\.venv\Scripts\python.exe -m unittest lessons.lesson_langchain_tools.test_lesson -v
# 课程开放后真实运行（会产生模型用量）
.\.venv\Scripts\python.exe scripts/run_live.py langchain-tools missing-field --url http://127.0.0.1:8765 --locale en
```

本课还没有做过真实模型运行，能力矩阵里没有任何服务商的实测记录。

## 参考与改写

借鉴并改写了：Microsoft AI Agents for Beginners（MIT）`04-tool-use` 的函数 Schema 与错误处理要素；Hugging Face Agents Course（Apache-2.0）unit 2 / unit 3 中同一工具在三个框架下的登记方式与“捕获异常返回空字符串”的反例；《深入理解 AI Agent》（Apache-2.0）第 4 章的工具描述与参数保真原则；claude-cookbooks（MIT）`tool_use` 中用强制工具调用提取结构化 JSON 的做法。langchain-core 的行为（`with_structured_output` 的组成、丢弃 `method` 参数、`handle_tool_error`）在本机 1.6.12 上实测核对。任务、业务表、夹具与实验由本项目编写。
