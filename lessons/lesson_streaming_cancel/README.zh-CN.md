# 流式输出与取消（`streaming-cancel`）

[English](README.md) · 简体中文

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。`long-stream` 的停止和断开两组没有真实运行过，需要有人在网页上操作。

## 本课的问题

模型的回答可以一块一块地到。程序边收边记，之后要分清三件看上去相似的事：**用户点停止**、**客户端断开**（只是读事件的连接关了）和**后端真正结束**。本课回答五个问题：

- 流式响应是什么（数据块、SSE 的 `data:` 行、用量块、`[DONE]`），为什么对读的人来说，首字延迟比总耗时更要紧；
- 数据块怎样拼成一份回答，拼合的响应和非流式响应有哪些不同（它由平台拼出，不是服务商发来的响应体）；
- 取消请求做了什么：之后不再记录新的数据块，已到达但没交给运行的计入 `discarded_after_cancel`，`done` 写明原因；
- 为什么客户端断开不会停止运行，为什么终态以后端的 `done` 为准；
- 停止留下的半截文字怎么办：标明不完整，由程序核对，不能当成写完的 assistant 消息放回去。

本课每个练习都调用模型。课程里没有沙箱，也不执行模型写的代码。

## 任务与数字

每个练习都让模型写一份编号清单（第 1 条到第 N 条，每条一行，每条一句或三句），内容是 Agent 循环的一轮里发生了什么。任务朴素是故意的：清单是否完整，Python 能核对（编号 1 到 N 各一次、每行以句子结尾），所以被截断的回答靠数据判断，不靠文字读着是否通顺。

首块到达（`first_chunk_ms`）、首字延迟（`first_token_ms`）和总耗时，来自平台在本进程里的计时，从请求发出前算起。没有一个数是估算的，页面也不做逐字打出的效果。唯一的例外是对照里的非流式一侧：`context.complete` 只返回响应体，所以运行器自己给这次调用计时，报告里写明了这一点。服务商没发的用量写“未报告”，不写 0。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：四个场景（`compare`、`long`、`stop`、`continue`），停止函数 `stop_at` 和两种续写请求 |
| `reports.py` | 各场景的 `lesson.report` 与运行器自己写的回答；每个数都取自平台的测量或一次核对 |
| `analysis.py` | 纯函数核对：编号条目、截断落在哪里（`analyse_partial`）、两种合并规则、编号核对、响应结构 |
| `locales/` | 运行时文本，每种语言一份；`locales/fixture/` 只服务测试夹具 |
| `fixtures.py` | 离线测试模型：分块之间带小段休眠的脚本流，以及非流式和续写的回复 |
| `test_lesson.py` | 行为测试：分析函数、两种语言下的每个练习、流中途被停止，以及真实运行路径（停止按钮、关闭事件流） |
| `course/execution.py` | 平台代码，本课就是讲它，所以放进读码页：`complete_stream` 与 `StreamResult` |

## 平台调用与事件

运行器调用 `context.complete_stream(body, round, stop_when=...)` 和 `context.complete`，自己只写 `lesson.report`；流式事件都由平台写。请求体里没有课程自己的 `stream` 字段：平台加上 `stream: true` 和 `stream_options: {include_usage: true}`。

| 事件 | 含义 |
| --- | --- |
| `request` | 流式请求带 `data.stream: true` |
| `response_delta` | 自上一条事件以来收到的数据块，原样记录；第一块单独一条，之后按时间或块数合并；`chunk_range` 与 `received_ms` 标明位置 |
| `response` | 平台按数据块拼出的响应体，以及 `data.stream`：`status`、`chunk_count`、`first_chunk_ms`、`first_token_ms`、`done_marker`，另有 `stop_reason`（课程停止）或 `cancel_reason` 与 `discarded_after_cancel`（取消） |
| `lesson.report` | 实验报告：检查、指标和表格。被取消的运行没有它，因为停止之后的代码不会执行 |
| `done` | 后端的终态；停止后有 `cancel_reason`，事件流被关闭过则有 `client_disconnects` |

## 练习

| 练习 | 看什么 |
| --- | --- |
| 流式与非流式对照 | 同一条请求发两次（第 1、2 轮）；表格把首块、首字、总耗时、完成原因、用量和消息结构并排放好 |
| 长输出：停止与断开 | 一份很长的清单；自己跑三次：不操作、点“停止运行”、点“断开事件连接”再重新连接 |
| 程序在第 N 块后停止 | `stop_when` 在停止点（`stop_after_chunks`）之后结束流；结果是 `stopped`，没有完成原因，也没有用量 |
| 不完整内容的下一轮 | 停止之后，把截断的文字用两种方式交回去（第 2、3 轮），再核对合并后的两份清单 |

四个练习都需要真实模型连接。离线测试模式只接受练习预设的输入；真实运行时可以改参数：场景、清单条数、每条的长度和停止点。

## 怎么运行

离线测试（确定性的流式数据；核对和平台的停止路径照常真实执行）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_streaming_cancel.test_lesson -v
```

真实运行：启动服务，在网页里选这门课并配置模型连接，或者用命令行：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py streaming-cancel stream-vs-block --url http://127.0.0.1:8765
```

停止和断开这两组要自己动手：在网页里开始 `long-stream`，文字到达时按“停止运行”或“断开事件连接”，之后读 `response` 和 `done` 事件。真实运行的结果取决于模型和服务商（回答多长、数据块怎么切、有没有发用量块）。课程正文不预设真实运行的结果，只写怎样从事件里核对。离线夹具只服务测试，网页上没有入口。

## 实验看什么

- **流式与非流式**：`first_token_ms` 对比流式的 `duration_ms`，就是读的人早多少看到第一个字；`shape_match` 检查比较两条第一条消息的角色、文字和完成原因，报告还会列出只在一侧出现的顶层字段（例如非流式响应的 `object`）。各一个样本、先流式后非流式：这里的数字都不是服务商的延迟水平。
- **中途取消**：同一个练习，不操作是 `completed`，停止后是带 `cancel_reason` 的 `cancelled`，断开再重连是带 `client_disconnects` 的 `completed`。被停止的运行里，拼合内容只有停止前收到的部分，`finish_reason` 是空的，`discarded_after_cancel` 说明有多少块到达了却没有记录。
- **部分结果的下一轮**：程序停止的流有 `stop_reason: lesson`、空的完成原因、没有用量；两种续写在发出的请求和合并规则上不同，报告用同一套规则核对两份合并后的清单。

## 边界

- 停止结束的是接收，不是服务商的生成。平台在下一块到达或网络超时时才关闭上游连接；服务商是否继续写、继续计费看不到，被停止的流用量未报告。
- 停止是协作式的：`complete_stream` 的循环每 0.05 秒看一次。被停止的运行什么也发布不了，所以没有报告；它收到的内容在平台的 `response` 事件里。
- 编号核对证明结构，不证明内容：它看不出一行之内的拼接错乱，比如半句后面直接粘上重写的整句。
- 只有平台记录过的数据块才算收到。`stopped` 的流也会丢掉排在队列里没交给运行的块，平台不计数（只有取消才记 `discarded_after_cancel`）。
- 离线脚本里“原样接上”的续写是预先写好的：它在新的一行重写被截断的那一条，好让核对有东西可抓。真实模型也可能干净地接上，那时同一个核对会通过。

## 参考与署名

事件的取消式处理、半截输出不是合法前缀、语音系统把被打断的一轮标出来，参考《深入理解 AI Agent》（[bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）第 6 章和 `chapter6/streaming-speech/interruption_manager.py`；流式的好处与首字延迟参考它的第 2 章。延迟指标参考 [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（MIT）的 `10-ai-agents-production`，带类型的流式事件见 [Claude Cookbooks](https://github.com/anthropics/claude-cookbooks)（MIT）的 `extended_thinking`。SSE 格式与 `stream_options.include_usage` 对照了阿里云百炼的流式输出文档和 OpenAI 聊天补全流式接口的说明。运行器、核对、编号清单任务和实验都是为本项目写的，没有复制任何参考项目的代码。
