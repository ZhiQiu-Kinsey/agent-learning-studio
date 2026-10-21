# 文件工具、编辑策略与变更证据（`file-edit-evidence`）

[English](README.md) · 简体中文

编码 Agent 用 `bash -c "sed -i ..."` 改文件，事后只能猜：这条命令改了哪个文件，改成了什么，有没有越出工作区？本课用专门的文件工具替代 Bash，回答三个问题：模型告诉工具“改这里”有哪几种办法（整文件重写、精确替换、行号替换），怎样用哈希和统一 diff 证明一次修改，怎样拒绝基于已经变了的文件做出的写入。让模型改文件的练习会调用模型；“五道防护”不调用模型，也不运行任何命令。

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。

## 工具

每次运行都在 `fixture_repo/` 的一次性副本里进行（一个小商店库：`shop/pricing.py`、`shop/report.py`，7 个测试，其中 2 个失败）。所有路径都经 `course/sandbox.py` 的 `Workspace.resolve`。

| 工具 | 做什么 | 拒绝什么 |
| --- | --- | --- |
| `read_file` | 返回带行号的内容（`start_line`、`end_line`，最多 400 行）和 `version`（sha256 前 12 位）；记住模型看到了什么 | 工作区外的路径，不存在、二进制、非 UTF-8、过大的文件 |
| `write_file` | 写整个文件；新文件不用先读 | 已有文件没读过（`NotReadYet`）、只读了一部分（`PartialRead`）、读后被改（`StaleRead`） |
| `edit_file` | 精确替换：`old` 必须恰好出现一次 | `OldStringNotFound`、`OldStringNotUnique`（带行号）、改了等于没改（`NoOpEdit`） |
| `edit_lines` | 按起止行号替换 | 行号不在文件里（`InvalidRange`）、之前的写入让行号作废（`LineNumbersStale`） |
| `run_tests` | 经受限执行器运行 `python -m unittest discover -s tests` | 没有容器时：人不批准的一律不执行 |

写 `tests/` 下的文件一律拒绝（`ProtectedPath`），读允许。每次写入之后，工具编译（不运行）Python 文件，把语法错误写进返回值。写入是原子的：先写临时文件，再改名覆盖。

## 证据

每个写入类调用在日志（`FileTools.journal`）里留一行，同时作为 `lesson.file_change` 事件发出：工具、路径、`ok`、`changed`、`error_type`、`before_sha256`、`after_sha256`、增删行数、`syntax_ok` 和统一 diff。被拒绝的调用也留一行，前后哈希相同。

`edit` 运行结束时，平台自己核对结果，写进 `lesson.report`（实验报告）：

- `tests_pass`：平台重新运行测试；命令没有运行（审批被拒绝）时这一项没有 `passed`，因为没运行过的命令说明不了代码怎么样；
- `tests_untouched`：`tests/` 下没有文件被改（`Workspace.protected_changes`）；
- `scope`：只有 `shop/pricing.py` 变了，并且其中只有 `discount_rate` 和 `shipping` 被改动或删除（`symbol_changes`）；
- `evidence_chain`：`verify_chain` 拿日志对照工作区自己的哈希重放：每一条的起点是上一条的终点，最后一条的终点是文件现在的哈希。

模型最后的话只被引用，不被采信。指标还统计写入类调用的参数字符数（实际发出的，含被拒绝的）、工具结果字符数、模型调用数；Token 只写服务商报告的数，没有就写“未报告”。

## 未隔离：测试怎么运行

本课唯一的命令是固定的测试命令，但它会执行模型改过的代码。没有容器引擎时，受限执行器**没有隔离**：它以你的身份在你的机器上运行。所以每次运行，包括模型自己的 `run_tests` 和平台的验收运行，都要先等你批准（`RunContext.request_approval`；审批卡写着命令、`isolated: false` 和目前改动的文件），`lesson.sandbox` 事件、报告和审批摘要都写着“未隔离 · 命令在你的机器上执行”。有容器时改用容器，不再逐条审批。离线测试模式固定使用受限执行器，测试不依赖机器上有没有容器引擎。详见 `docs/architecture/sandbox.md`。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `file_tools.py` | `FileTools`：四个工具、守卫（`_check_view`）、共用的写入框架（`_write`）、日志；各个错误类 |
| `evidence.py` | `unified_diff`、`verify_chain`、`symbol_changes`、`unittest_summary` |
| `runtime.py` | `edit` 场景（循环、受限执行器、审批、报告）和 `guards` 场景；入口是 `run(context)` |
| `fixtures.py` | 离线测试用的模型和审批策略（只服务测试，网页上没有入口） |
| `fixture_repo/` | 模型要修的仓库 |
| `locales/` | 提示词、工具描述、工具错误、报告文字，中英各一份 |
| `test_lesson.py` | 行为测试：真实的文件工具、哈希和 diff，在临时工作区里真实运行 `unittest` |

## 练习

| 练习 | 做什么 | 看哪里 |
| --- | --- | --- |
| 整文件重写：`write_file` | 模型拿到读取、`write_file` 和 `run_tests` | `lesson.file_change`；报告里的参数字符数和 `scope` |
| 精确替换：`edit_file` | 同一个任务，改用 `edit_file` | 如果出现，被拒绝的 `OldStringNotUnique`；每次修改的 diff |
| 行号替换：`edit_lines` | 同一个任务，改用 `edit_lines` | 改变行数的写入之后出现的 `LineNumbersStale`；多出来的一次读取 |
| 五道防护（不调用模型） | 运行器提交有问题的调用，先写明预期结果 | 报告表格里每一步的预期、实际和“文件未变”；过期那一组里的 `lesson.external_change` 和断开的哈希链 |

在同一个任务上比较三种策略：参数字符数、被拒绝的调用、模型调用数，以及 `shop/pricing.py` 的最终哈希是否相同。一次运行只是一个样本，每种策略多跑几次再下结论。

## 边界

- 脚本化的离线模型用三种方式做同一个修复，所以离线时三组的最终文件相同；真实模型未必如此。课程正文没有预设任何真实运行的结果。
- `shop/pricing.py` 只有 45 行，看不出大文件上的差距；深入块按 600 行算了一遍。
- 过期检测在写入开始时比较哈希；比较和改名之间还有几毫秒的空隙，本课没有文件锁。
- 工具只处理工作区内的 UTF-8 文本文件。符号链接、二进制和很大的文件只做拒绝。
- 哈希链闭合只证明发生了什么，不证明改对了。

**运行语言：**本课支持中文和英文运行。提示词、工具描述、工具错误和报告文字在 `locales/zh_CN.py` 与 `locales/en.py`；工具名、参数名、事件名和错误类名是代码，两种语言相同。

## 怎么运行

离线测试（真实工具、真实哈希、真实的测试运行；模型是脚本化的测试数据）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_file_edit_evidence.test_lesson -v
```

在网页实验台运行，或用 `scripts/run_live.py file-edit-evidence <练习> --ask-approvals`（模型练习会产生模型用量，`guards` 练习不会）。

参考：《深入理解 AI Agent》第 4 章（专用工具与通用执行器的取舍、参数传递的保真性、执行工具的安全层次）和第 5 章“Coding Agent 中的文件编辑工具”及其配套的 `tools/edit_tool.py`、`read_tool.py`、`write_tool.py`；Learn Claude Code 的 `s02_tool_use`；Mini-SWE-agent 文档（只用 Bash 的路线，作对照）。代码与实验为本项目编写。
