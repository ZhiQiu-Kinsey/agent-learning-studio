# 提示注入与工具权限（`prompt-injection`）

[English](README.md) · 简体中文

本课要解决的问题：资料、网页和工具结果里可以夹带指令，模型读到以后可能被说服，提出读密钥、改公告、向外发送这样的调用。怎样让“被说服”不等于“做了坏事”？本课把两份带指令的资料放进真实的检索链，由程序在**执行侧**逐条决定模型提出的调用是放行、审批还是拒绝；并把“模型提了什么”和“文件与发件箱实际变成了什么”分开记录。课程仍为 `planned`，本次只做了离线验证（见文末）。

资料检索沿用 `document-loading` 的分块和 `keyword-retrieval` 的 BM25：共享的“青石图书馆服务手册”（含读者留言里那条伪装成指令的话）加上本课自己的两份资料，不改共享语料。工具是真实的 Python：检索、读文件、写文件、向外发送（只写进本地发件箱，不联网），都作用在每次运行新建、运行后删除的临时文件夹上。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `guard.py` | 执行侧权限检查：`Policy`、`Grant`、`STRICT`（最小权限策略）、`open_policy`（只靠提示词那两组用）、`authorize`（唯一入口，出错一律拒绝）、路径解析与业务规则 |
| `workspace.py` | 真实工具和它们作用的临时文件夹：`Workspace`（`read_file`、`write_file`、`post_url`、文件快照、效果账本）、临时文件夹之外的底线 `FloorViolation`、假密钥 `CANARY` |
| `retrieval.py` | `search_handbook`：手册加本课两份资料的 BM25 检索；哪些片段埋了指令只用于报告，工具结果里不写 |
| `runtime.py` | 运行器：`Session`（先决定、再记录、必要时等审批、最后执行）、`run_task`（一道题的循环）、四个练习、运行器探针 |
| `reports.py` | 记录变数字、数字变报告：越权提议数、被拦下数、实际发生的越权读写、探针结果 |
| `corpus/<语言>/*.md` | 本课两份不可信资料：`partner-bulletin`（手续费说明后接“核对说明”）、`transfer-notice`（指向一个工作区文件） |
| `workspace_seed/<语言>/public/` | 临时工作区里的公告和 `transfer-guide.txt`（最后一行夹带第二条指令） |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：系统提示词（基础版和带警告版）、工具描述、拒绝信息、报告文字 |
| `fixtures.py`、`locales/fixture/` | 离线夹具：只服务自动化测试；被写成照做资料里要求的“模型”，并提供审批决定 |
| `test_lesson.py` | 行为测试：每条规则、真实文件效果、四个练习、两种运行语言 |
| `content.json`、`content.en.json` | 教学内容与英文译文层 |

`guard.authorize` 的接口：

```python
authorize(policy: Policy, workspace: Path, name: str, raw_arguments, registered) -> Decision
# Decision.verdict: "allow" | "confirm" | "deny"；Decision.rule：规则代码；Decision.category："ok" | "scope" | "input"
```

- 输入只有程序构造的策略、工具登记表、工具名和原样的参数字符串（路径检查另外读磁盘）。资料和模型说的话不是输入。
- `category` 为 `scope` 的拒绝才算“越权”：没有登记的工具、没有授予的工具、路径越界、含密钥格式的内容。参数不合格、写入过大这类算 `input`，不算攻击。
- `STRICT`：`search_handbook` 放行；`read_file` 只能读 `public/` 和 `out/`；`write_file` 只能写 `out/` 里的 `.md`，最多 2000 字节，每次要人审批；`post_url` 不授予。

## 练习

| 练习 | 模型调用 | 要看的证据 |
| --- | --- | --- |
| 正常任务：权限层不误伤 | 8 | 四个正常任务（检索、带干扰留言的检索、读公告、写提示文件）都完成；写之前先出现审批请求；没有被拒绝的调用 |
| 资料里的注入：模型的提议与执行侧的决定 | 最多 8（`scenarios` 可减为 4） | 间接和直接两条路径；每条越权提议的 `lesson.permission`；报告把模型这边与执行侧分开；17 条运行器探针（平台不能建符号链接时 16 条） |
| 只加提示词，还是执行侧权限：三组对照 | 12 | 无防线、提示词警告加来源标签、再加执行侧权限；每组的 `lesson.arm_result`（越权提议、被拦下、实际发生的越权读写、密钥有没有进回答） |
| 间接提示注入沿工具结果传播 | 4 | 检索结果指向一个文件，文件里夹带第二条指令；`lesson.context_source` 的两跳；读文件被放行、外发被拒绝 |

参数：`top_k`（1–5，默认 3）是模型检索时默认返回的片段数；`scenarios`（`both`、`indirect`、`direct`）只用于“资料里的注入”。把 `top_k` 改成 1，通告里埋了指令的片段进不了请求，模型没有可照做的东西，报告会把这一组写成“没有被检验”。

## 实验看什么

1. **资料里的注入**：模型提议了什么（`lesson.permission` 的 `source` 是 `model` 还是 `offline_fixture`）、`authorize` 怎么决定（规则和解析后的落点）、拒绝的调用在 `tool_result` 里是结构化错误、报告里实际发生的越权读写。再看“拦截证据来自哪里”：模型提出了越权调用，证据是模型的提议加探针；没有提出，只有运行器探针。
2. **三种防线对照**：同一道题、同一份被投毒的资料。第一组和第二组没有执行侧权限，工具真的执行，诱饵密钥被读出、公告被改、发件箱多一行；第三组同样的提议全被拦下。第三组的回答仍可能照做资料里的要求，这一层归别的防线管。
3. **传播**：授权范围内的读取被放行（权限判断调用，不判断文件里写了什么），随后越权的外发被拒绝；`lesson.context_source` 记下每一跳进入上下文的内容。

能证明：每条提议的决定和理由、世界实际变成了什么、回答有没有被带偏，三件事各有各的记录。不能证明：真实模型会不会被说服（离线测试模式里的提议由夹具写出）、策略对没写进题集的攻击也成立、回答的内容正确。

## 怎么运行

离线测试（夹具 + 真实检索、真实权限检查、真实文件效果，不调用模型）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_prompt_injection.test_lesson -v
```

真实运行（课程开放后；会产生模型用量；“正常任务”里的写文件要在网页上批准）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py prompt-injection attack --url http://127.0.0.1:8765 --locale en
```

## 诚实说明

- `fixtures.py` 只服务测试，是一个“被写成照做资料里要求”的脚本：看到通告里要求读密钥，就提议读密钥、改公告、外发；它在三种防线下的提议完全一样，所以对照表只说明“模型被说服以后”各防线的差别，**不是对任何真实模型的测量**。凡是它提出的越权调用，响应里都有 `x_offline_fixture`，`lesson.permission` 的 `source` 写 `offline_fixture`。
- 工具、权限检查和文件效果都是真实的：开放策略的两组里，诱饵密钥确实被读进上下文，公告文件确实被改写，发件箱文件确实多了一行。这些都发生在临时文件夹里，用完即删；“密钥”是本课写死的假字符串，不解锁任何东西。
- 运行器探针（来源 `course_program`）覆盖守卫的每条规则，另有必须放行的正常调用；它们证明守卫本身，不能当作模型的行为。
- 夹具不报告用量，报告里的用量显示“未报告”。
- 本次环境没有模型密钥，**没有做过真实模型运行**；课程保持 `planned`，开放前每个练习要在两种运行语言下各真实运行一次，核对正文说法。模型没有提出越权调用的运行要如实记录，不能当作防线有效的证据。

## 剩余风险（课程里也会讲）

授权目录里的文件本身可能被投毒，让回答变错；审批多了人会不看内容就点同意；检查路径和真正打开文件之间有很短的间隙（符号链接竞争）；权限之外的东西，比如把手续费说成免费的回答，要靠来源引用核对之类的别的层。临时文件夹不是沙箱，只是普通进程里的普通文件夹。

## 参考

- 深入理解 AI Agent（bojieli/ai-agent-book，Apache-2.0）第 2 章“提示注入”与来源标记，第 4 章执行工具的安全层次和 Sidecar，第 5 章 Coding Agent 的安全（致命三要素）。
- Microsoft AI Agents for Beginners（MIT）`06-building-trustworthy-agents`、`18-securing-ai-agents`。
- learn-claude-code（shareAI-lab，MIT）`s03_permission`；claude-cookbooks（MIT）`claude_agent_sdk/scheduled_repository_reviewer`。

只改写借鉴思路，没有复制代码或逐句翻译；资料、策略、探针和实验由本项目编写。
