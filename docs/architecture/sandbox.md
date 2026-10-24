# 执行模型生成命令的隔离方案

[English](sandbox.en.md) · **简体中文**

确认日期：2026-10-20。实现：`course/sandbox.py`；测试：`tests/test_sandbox.py`。

> **维护者决定（2026-10-20）**：没有容器引擎时，接受“受限执行器 + 每条命令人工审批”作为编码 Agent 课的执行方式，课程页与运行事件都要醒目标注“未隔离 · 命令在你的机器上执行”。受限执行器**不是安全沙箱**，它防不住什么见第 7 节；有容器时优先用容器。验收测试用标准库 `unittest`。课程仍要等真实模型验收后才开放。

## 1. 为什么需要

AGENTS.md 的“安全与配置”写明：本地进程中的课程代码不是沙箱，需要执行模型生成代码的课程，必须先有隔离方案。

课程代码是维护者审过、登记在清单里的，属于受信任代码。编码 Agent 课（`bash-coding-agent`、`file-edit-evidence`，以及之后的综合项目）不一样：它们要执行模型当场写出的命令。那些命令不受信任，可能出于模型失误，也可能来自夹具或工具输出里的提示注入。

本方案只管“模型写的命令在哪里执行、能碰到什么、怎样留下证据”。课程循环、事件和审批界面仍由 `RunContext` 与平台负责。

## 2. 威胁模型

**要保护的东西**

- 学习者的文件：本仓库（含 `local_config.py`、`.runtime/`、`.venv/`）、用户目录、其他项目。
- 密钥：环境变量里的服务商密钥、`local_config.py`、网页提交后只存在后端内存里的临时密钥、`~/.ssh`、云服务凭证。
- 本机可用性：CPU、内存、磁盘、进程数，以及正在运行的学习平台服务本身。
- 网络身份：学习者的网络出口不能被拿去外传数据或攻击别人。

**威胁来源**，按在本平台出现的可能性排：

1. 模型失误：删错目录、写出死循环、启动一个不会退出的服务、打印几百 MB 日志。最常见。
2. 提示注入：夹具文件、测试输出或网页内容里藏着“读取密钥并发出去”之类的指令。
3. 刻意构造的恶意命令：单人本地学习场景下不是主要威胁，但不能排除，因为学习者可能换用任意模型或修改提示词。

**具体威胁与对应手段**

| 威胁 | 例子 | 容器后端 | 受限执行器 | 命令策略 |
| --- | --- | --- | --- | --- |
| 删除或改写工作区外的文件 | `rm -rf ~/project` | 只挂载工作区副本，挡住 | 挡不住，靠审批 | 拒绝 `..`、`~`、绝对路径 |
| 读密钥 | `cat local_config.py`、`echo $DASHSCOPE_API_KEY` | 文件不在容器里，环境变量不传入 | 清空环境变量；文件挡不住 | 拒绝常见密钥文件名和变量名 |
| 读服务进程的内存或环境 | `cat /proc/<pid>/environ` | 进程命名空间隔离，挡住 | **挡不住**（同一用户） | 拒绝字面写法 |
| 联网外传 | `curl -d @local_config.py http://…` | `--network none`，挡住 | 只设无效代理，原始 socket 挡不住 | 拒绝常见网络命令 |
| 无限循环、挂起 | `while true; do :; done`、等待输入 | 超时后 `kill` 容器 | 超时后杀进程树；标准输入关闭 | — |
| fork 炸弹、资源耗尽 | `:(){ :\|:& };:` | `--pids-limit`、`--memory` | Linux 用 setrlimit，Windows 用作业对象；macOS 基本只有超时 | 拒绝经典写法 |
| 后台进程残留 | `python server.py &` | 容器随命令删除 | 每条命令结束都清理整个进程组或作业 | 拒绝 `&`、`nohup`、`setsid` |
| 输出洪泛 | `yes` | 首尾截断，超过上限杀掉 | 同左 | — |
| 提权、改系统 | `sudo`、`systemctl`、`pkill python` | 去掉全部 capability，`no-new-privileges` | 挡不住，靠审批 | 拒绝 |
| 改测试骗过验收 | 把失败断言删掉 | 不属于隔离问题 | 同左 | — |

最后一行是诚实问题，不是安全问题：平台用 `Workspace.protected_changes` 检查受保护文件，并自己重新运行测试，不采信 Agent 的自述。

## 3. 各平台可用的隔离手段与取舍

主力平台是 Windows（PowerShell），也支持 macOS 和 Linux，不能假设装了 Docker。

| 手段 | 平台 | 隔离强度 | 取舍 |
| --- | --- | --- | --- |
| Docker / Podman 容器 | Windows（Docker Desktop 需要 WSL2 或 Hyper-V；Podman Desktop）、macOS（Docker Desktop、Colima、OrbStack、Podman）、Linux | 文件系统、进程、网络命名空间隔离；资源上限。与宿主共享内核（Windows、macOS 上是共享一个轻量虚拟机的内核） | 需要学习者另装软件、预先准备镜像；每条命令启动约 1 秒。Linux 上能操作 docker 的用户等同 root |
| bubblewrap、nsjail、firejail | 仅 Linux | 接近容器，不需要守护进程 | 主力平台用不上；可作为以后的第三个后端 |
| macOS `sandbox-exec` | 仅 macOS | 中等 | 已被苹果标为弃用，规则语言没有公开文档 |
| Windows Sandbox | Windows 专业版、企业版 | 强（独立虚拟机） | 家庭版没有；启动慢，没有适合逐条命令调用的接口 |
| AppContainer、低完整性令牌 | Windows | 中等 | 需要大量 Win32 调用，标准库不支持，维护成本高 |
| WSL2 | Windows | 弱 | 默认把 Windows 磁盘挂在 `/mnt/c`，同一用户的文件都能改，不算隔离 |
| 受限执行器（本方案） | 全部 | **不是隔离边界** | 零依赖；靠人工审批加护栏减少事故 |

结论：实现两个后端。

- `ContainerRunner`：唯一被当作隔离边界的后端（`isolated = True`）。
- `RestrictedRunner`：没有容器时的退路（`isolated = False`），必须配合逐条审批。

bubblewrap 后端暂不实现：主力平台用不上。若维护者希望 Linux 学习者不装 Docker 也有真隔离，可以照 mini-swe-agent 的 `BubblewrapEnvironment` 再加一个后端，接口不变。

## 4. 默认策略

| 情况 | 后端 | 网络 | 审批 | 说明 |
| --- | --- | --- | --- | --- |
| docker/podman 可用且镜像已在本地 | 容器，每条命令一个新容器 | 禁用 | 默认不逐条审批（课程可以另加） | `default_approval_mode` 返回 `none` |
| 没有可用容器 | 受限执行器 | **未隔离**（只设无效代理） | **每条命令都要人工审批** | `default_approval_mode` 返回 `every_command` |
| 需要审批但没有审批通道 | — | — | **拒绝执行** | 结果为 `approval_unavailable`（失败即关闭，fail closed） |

另外三条，不论哪个后端都成立：

- 命令先过命令策略（第 8 节）。被拒绝的命令不进入审批，也不执行。
- 平台不会自动拉取镜像：拉取需要联网，也耗时间。`ContainerRunner.detect` 报 `image_missing`，并给出要执行的拉取命令。
- 平台不会静默降级：`select_runner` 同时返回所选后端和检测结果，课程应在事件里写明 `backend`、`isolated` 和没用容器的原因。

## 5. 容器后端

每条命令执行一次 `docker run --rm`（或 `podman run --rm`），主要参数：

| 参数 | 作用 |
| --- | --- |
| `--network none` | 没有网络出口。对应书中“致命三要素”的第三条：即使读到了数据，也传不出去 |
| `--mount type=bind,source=<工作区副本>,target=/workspace`，`--workdir /workspace` | 只挂载一次性副本；仓库、用户目录、密钥文件都不在容器里 |
| `--read-only`，`--tmpfs /tmp` | 根文件系统只读，临时文件写进内存盘 |
| `--cap-drop ALL`，`--security-opt no-new-privileges` | 去掉全部 capability，禁止 setuid 提权 |
| `--memory`、`--memory-swap`、`--cpus`、`--pids-limit` | 内存、CPU、进程数上限，防死循环、内存耗尽和 fork 炸弹 |
| `--init` | 回收僵尸进程、转发信号 |
| `--user <uid>:<gid>`（Linux docker），`--userns keep-id`（Linux podman） | 写出的文件仍归学习者所有，清理时删得掉 |
| 只有 `--env HOME=/tmp` 等几项 | 宿主环境变量一个都不传进容器 |

超时、取消或输出超限时，先 `docker kill <名字>`，再 `docker rm -f`，最后清理本地 CLI 进程。只杀 CLI 进程不会停止容器。

默认镜像 `python:3.12-slim` 只是起点：它没有 pytest。编码课需要的工具应写进一个小镜像，由课程 README 给出构建命令；镜像名通过 `image=` 传入。

**容器也防不住的**：内核或容器运行时的逃逸漏洞；Docker Desktop 里学习者自己放宽的设置；挂载进去的工作区副本可以被任意修改（这是预期行为，证据靠前后哈希）；被投毒的镜像（镜像来源由维护者指定）。

## 6. 受限执行器做了什么

`RestrictedRunner` 在本机启动子进程，每一项都用来减少事故：

- **工作目录固定**：`cwd` 是工作区副本 `repo/`。`HOME`、`TMP` 指向同一临时目录下的 `home/`、`tmp/`，所以工具写缓存不会碰到真实用户目录，也不会出现在 diff 里。
- **环境变量白名单**：从空字典开始，只放入 `PATH`、`LANG` 等（Windows 另有 `SYSTEMROOT`、`PATHEXT` 等启动必需项）。父进程的密钥一个都不继承。课程额外传入的变量名若像密钥（含 KEY、TOKEN、SECRET 等），直接报错。
- **减少意外联网**：设 `HTTP(S)_PROXY` 为一个没人监听的本机端口，并设 `PIP_NO_INDEX=1`。pip、curl、requests 这类遵守代理设置的程序会立刻失败。原始 socket 不受影响。
- **标准输入关闭**：等待输入的命令立刻读到 EOF，不会挂起。
- **超时**：默认 30 秒，上限 600 秒。
- **进程树清理**：每条命令结束后都清理，不只在超时时：
  - POSIX：shell 是新会话的组长，结束时 `killpg(SIGKILL)`；
  - Windows：shell 加入作业对象（kill-on-close），结束时 `TerminateJobObject`；作业对象建不起来时退回 `taskkill /T /F`。
  - POSIX 上先确认 shell 已退出但不回收它（`waitid(WNOWAIT)`），等进程组清理完再回收，避免进程号被复用后误杀别的进程组。
- **资源上限**（尽力而为）：
  - Linux：shell 由一个很小的 Python 启动器先调用 `setrlimit` 再 `exec` 成 shell（进程号不变，进程组清理照常），限制线程数（当前用户线程数加余量）、地址空间（默认 2 GiB）和单文件大小（默认 64 MiB）。在 exec 之前设置，避免从外部 prlimit 时快命令抢在限制生效前跑完的竞态（测试曾实际撞到过）；
  - Windows：作业对象限制活动进程数和总内存；
  - macOS：同一个启动器，实际只有单文件大小生效（macOS 不执行地址空间限制，进程数上限没有设置），主要靠超时与进程组清理。
- **输出首尾截断**：每个流保留开头 4000 字节和结尾 4000 字节，中间换成标注 `[... N bytes omitted ...]`，并记录总字节数和 `truncated`。总量超过 16 MiB 立即杀掉进程树（`output_limit_exceeded`）。只留首尾，是因为错误原因通常在开头，测试总结通常在结尾。
- **路径脱敏**：输出里出现的工作区、临时目录、解释器目录和项目目录的绝对路径换成 `<workspace>`、`<tmp>`、`<python-bin>`、`<project>`，事件里不留本机路径。
- **Shell**：Unix 用 bash（没有就用 sh）。Windows 优先用 Git for Windows 的 bash：只在它的安装位置找，**不从 PATH 找**，因为 PATH 上的 `bash.exe` 常是 WSL，会把命令送进另一个系统。找不到时用 PowerShell，结果里的 `shell` 字段写明实际用的是哪个。

## 7. 受限执行器防不住什么

**无容器模式不是安全沙箱。** 下面这些它都挡不住，命令策略也只能挡住其中最直白的写法：

- 子进程是同一个用户，能读写该用户能读写的任何文件。绝对路径可以用变量拼出来，策略看不见。
- 能联网：原始 socket、不遵守代理设置的程序都能出去。
- Linux 上同一用户的进程可以读 `/proc/<服务进程号>/environ`，拿到启动服务时环境变量里的密钥。Windows 上同一用户的进程默认可以打开平台进程读内存，网页提交、只存在后端内存的密钥也可能被读到。
- 调用 `setsid` 或连续 fork 两次的进程会离开进程组，逃过清理。结果里的 `escaped_processes_suspected` 只在它还握着输出管道时能发现。
- Windows 上 shell 在加入作业对象前的一瞬间若已经启动子进程，那个子进程不在作业里（`taskkill /T` 仍可能通过父子关系找到它）。
- 以 root 运行时 Linux 不执行线程数上限；macOS 只有单文件大小上限。
- 能修改项目的 `.venv`、`local_config.py` 所在目录里的其他文件，能结束用户的其他进程（策略拒绝 `kill`、`pkill`，但 Python 一行就能绕过）。

所以，它的安全性来自“每条命令执行前都有人看过”，护栏只是让常见事故少一些、看得清一些。审批界面必须显示将要执行的原文（`ApprovalRequest.command` 就是交给 shell 的那个字符串），并标明“未隔离”。

## 8. 命令策略

`CommandPolicy.evaluate(command)` 按固定顺序匹配规则，返回 `allow`，或带规则 id 和匹配片段的 `deny`：

| 规则 | 拒绝什么 |
| --- | --- |
| `empty_command`、`command_too_long`、`control_characters` | 空命令、超过 4000 字符、含控制字符 |
| `fork_bomb` | `:(){ :\|:& };:`、`%0\|%0`、`os.fork` |
| `privilege` | `sudo`、`su`、`doas`、`runas`、`-Verb RunAs` |
| `system_control` | 关机、分区、`systemctl`、`crontab`、`schtasks`、`reg`、`git config --global`、`dd if=/of=` |
| `process_control` | `kill`、`pkill`、`taskkill`、`Stop-Process` |
| `secret_file` | `local_config`、`.env`、`.ssh`、`id_rsa`、`.aws`、`.netrc`、`.git-credentials`、`credentials.json` 等 |
| `secret_env` | `$…KEY`、`%…TOKEN%`、`$env:…SECRET`、`os.environ['…_API_KEY']`、`XXX_API_KEY` |
| `environment_dump` | `env`、`printenv`、`set`、`Get-ChildItem env:`、`/proc/*/environ`、`os.environ` |
| `network` | `curl`、`wget`、`ssh`、`Invoke-WebRequest`、`git clone/fetch/pull/push`、在命令里 import 网络库、URL |
| `package_install` | `pip install`、`npm install`、`apt install`、`python -m pip` 等 |
| `background_process` | POSIX 的单个 `&`、`nohup`、`setsid`、`screen`；PowerShell 的 `Start-Job`、`Start-Process` |
| `obfuscation` | `eval`、管道进 shell、`base64 -d`、`Invoke-Expression`、`powershell -enc`、`exec(`、`__import__(` |
| `parent_traversal`、`home_path`、`absolute_path` | 路径段 `..`；`~`、`$HOME`、`%USERPROFILE%`；盘符路径、UNC 路径、首段存在于主机根目录的 `/…` 路径（`/dev/null` 除外） |

几点说明：

- 绝对路径只看首段是否真在主机根目录下，所以 `awk '/def/'`、`grep "/api/"` 这类模式不会误伤。
- 规则偏严：引号里的 `&` 也会被拒绝。被拒绝时模型拿到 `error_type: policy_denied` 和规则 id，可以换个写法。
- **策略不是安全边界。** 书里讲过，shell 的组合方式太多，关键字黑名单挡不住刻意绕过：`c''url`、`$(printf …)`、先把脚本写进文件再执行，都能过。测试里专门有一条用例证明这一点。真正的边界只有容器。
- 容器模式下也跑同一套策略：它让模型的行为在两种后端下一致，也让课程能讲“策略判定”。

## 9. 工作区与变更证据

`Workspace(source)` 把夹具仓库复制到一次性目录。

- 夹具里有符号链接，或超过文件数、大小上限，都直接拒绝。
- 复制时忽略 `__pycache__`、`.pytest_cache` 这类副产物。
- 复制完立刻记录基线：每个文件的 sha256，以及小文件的原文，所以 diff 不依赖夹具源目录保持不变。

证据接口：

- `snapshot()`、`changes()`：前后哈希对比，状态分 `added`、`removed`、`modified`。
- `diff()`：统一 diff。二进制或过大的文件只写名字；总长度超过上限时首尾截断并标注。
- `protected_changes(["tests/*"])`：Agent 改了不该改的文件时，验收应判失败。
- `resolve(path)`：把模型给的相对路径解析到工作区内，先跟随符号链接再检查。拒绝绝对路径、`..` 越界、`~`，Windows 上还拒绝 `:`（盘符相对路径和备用数据流）。`file-edit-evidence` 的文件工具应只通过它取路径。
- `redact(text)`：去掉本机绝对路径。
- 清理：`cleanup()`，或用 `with` 语句；对象被回收或进程退出时也会删除。

## 10. 与审批的接口

审批由平台负责：`RunContext.request_approval(kind, summary, payload, *, timeout_s, risk, editable)`。它发出平台事件 `approval_requested`、`approval_resolved`（含载荷摘要），等待网页提交 `POST /api/runs/{id}/approvals`，离线测试走夹具的 `approval_policy`，返回 `ApprovalDecision`。本模块不实现审批，只定义调用形状，并提供适配器：

```python
Approver = Callable[[ApprovalRequest], bool | {"decision": "approve" | "reject", "note": str | None}
                                       | ApprovalOutcome | ApprovalDecision]

approve = context_approver(context, summary=lambda request: texts.approve_command.format(command=request.command),
                           risk="high", timeout_s=300, editable=False)
```

`context_approver` 把 `ApprovalRequest.to_dict()` 原样作为载荷，所以 `approval_requested` 里记录着将要执行的命令、后端和 `isolated`。`summary` 是给学习者看的一句话，必须来自课程的 `locales/`。

`ApprovalRequest` 的字段：

| 字段 | 含义 |
| --- | --- |
| `tool` | 工具名 |
| `command` | 将原样执行的字符串 |
| `cwd` | 固定为 `<workspace>` |
| `backend` | 后端名 |
| `isolated` | 是否有隔离边界 |
| `timeout_s` | 超时秒数 |
| `policy` | 策略判定 |

`run_guarded` 的行为：

- 审批函数可以阻塞到有人回答，也可以抛出 `RunCancelled`。
- 拒绝得到 `approval_rejected`，无人决定得到 `approval_timeout`；两种都不执行。
- `editable=True` 时学习者可以改命令后批准：执行的是批准后的文本，并且先重新过一遍命令策略，记录里有 `edited: true`。默认不允许编辑。
- 审批之后、执行之前再调用一次 `check_cancelled`，保证停止生效。
- 回答不是上面几种形状时抛错，不当作批准。

时间线是 `tool_call → approval_requested → approval_resolved → tool_result`，“工具在批准前没有执行”可以从事件里验证。

## 11. 课程怎样用

```python
from course.sandbox import CommandPolicy, Workspace, context_approver, run_guarded, select_runner

FIXTURE = Path(__file__).parent / "fixture_repo"     # 常量，不来自浏览器输入


def run(context):
    texts = texts_for(context.locale)
    with Workspace(FIXTURE) as workspace:
        runner, status = select_runner(workspace, timeout=30)
        context.emit("lesson.report", {...})          # 写明 runner.backend、runner.isolated、status.reason
        policy = CommandPolicy.for_runner(runner)

        approve = context_approver(context, lambda r: texts.approve_command.format(command=r.command))

        def bash(command: str) -> dict:
            result = run_guarded(command, runner=runner, policy=policy, approve=approve,
                                 should_stop=context.cancelled, check_cancelled=context.check_cancelled)
            return result.to_dict(messages=texts.sandbox_errors)   # 按 error_type 给出本语言说明

        ...  # 模型循环：context.complete(...)，context.execute_proposal(call, {"bash": bash})

        # 平台验收：用同一个 runner 重跑测试。命令是平台定的，但它会执行 Agent 写进项目的代码，
        # 学习者批准的是命令而不是文件内容，所以无容器时验收也单独审批（kind: acceptance）
        verdict = run_guarded("python -m unittest discover -s tests", runner=runner, policy=policy,
                              approve=acceptance_approver, should_stop=context.cancelled,
                              check_cancelled=context.check_cancelled)
        tampered = workspace.protected_changes(["tests/*"])
        context.emit("lesson.report", {...})          # verdict.ok、tampered、changes、diff
```

要点：

- 系统提示词要说明 shell 类型（`runner.shell_flavor`）：Windows 上没有 Git Bash 时是 PowerShell。夹具里的命令最好只用两种 shell 都能执行的写法（例如 `python -m unittest …`）。
- `CommandResult.to_dict()` 可以 JSON 序列化，不含本机路径，可以直接作为工具结果或 `lesson.*` 事件数据。
- 结果分开报告“命令执行了”（`exit_code`）、“命令成功了”（`ok`）和“任务验收通过”（平台重跑测试）：这三者不能混为一谈。
- 验收被拒绝或超时，结论写“验收没有完成”，不能写成“没通过”或“通过”。（2026-10-21 起两门编码课都这样做；有容器时按第 4 节默认不逐条审批。）
- 离线测试：夹具给出确定性的模型响应，命令仍由 `RestrictedRunner` 真实执行。审批走 `lesson.json` 的 `testing.approval_factory`（事件里 `decided_by: offline_fixture`）；网页上不得有自动批准入口。
- 课程事件一律用 `lesson.` 前缀。命令记录建议沿用 `tool_result` 加 `lesson.report`，确有需要再提议新的通用视图。

## 12. 验证状态与待确认事项

**已在 Linux 实测**（`tests/test_sandbox.py`，真实子进程）：

- 工作区副本、前后哈希、diff 和受保护文件；
- 超时后孙进程被杀；后台子进程不会活过命令；
- 首尾截断与超限击杀；
- 子进程看不到父进程环境里的 `DASHSCOPE_API_KEY`；
- 资源限制在命令开始前已生效（读子进程的 `/proc/self/limits` 验证）；
- 策略的允许和拒绝用例，以及一个故意绕过成功的用例；
- 审批缺失时拒绝执行，拒绝、超时时不执行，批准后执行；与真实 `RunContext.request_approval`（离线夹具通道）联调，包括编辑后的命令重新过策略；
- 容器检测：本环境装了 docker CLI 但守护进程没有运行，真实检测结果为 `engine_unreachable`。其余分支用替身覆盖。

**未实测**：

- Windows 分支：Git Bash 与 PowerShell 选择、作业对象、`taskkill` 退路、UTF-8 前缀。测试已写，标注为跳过。
- macOS。
- 真实容器运行：本环境没有可用的守护进程，相应用例会跳过。

**维护者已决定（2026-10-20）**：

1. 无容器模式：采用 (a)，接受“受限执行器 + 逐条审批”，课程页与事件明确标注“未隔离”。当时的另两个备选是 (b) 只在容器可用时开放运行、(c) 另加 Linux 的 bubblewrap 后端。
2. 编码课的验收命令用标准库 `unittest`，不新增 pytest 依赖。

**仍待确认**：

1. 镜像：用哪个镜像、由谁构建、怎样固定版本（建议固定摘要），以及课程 README 怎样指导学习者准备。
2. 无容器时审批的超时与风险等级：当前适配器默认 `risk="high"`、300 秒，是否允许编辑命令（默认不允许）。
3. 容器模式下是否也要求逐条审批：当前默认不要求。

## 参考资料

只借鉴设计，没有复制代码。

- mini-swe-agent（MIT）：[`environments/local.py`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/local.py)
  - 借鉴：超时时杀整个进程组。
  - 不同：它的子进程继承完整环境变量，本方案改为白名单。
- mini-swe-agent（MIT）：[`environments/docker.py`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/docker.py)
  - 它用一个长期运行的容器加 `exec`，本方案改为每条命令一个 `run --rm`。
- mini-swe-agent（MIT）：[`environments/extra/bubblewrap.py`](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/environments/extra/bubblewrap.py)
  - Linux 无守护进程隔离的参考，留作以后的扩展。
- 《深入理解 AI Agent》（Apache-2.0）：[第 5 章“Coding Agent 的安全”](https://github.com/bojieli/ai-agent-book/blob/b789c97a8f3de5b405a6f6dfa8289208d679d0b8/book/chapter5.md)
  - 借鉴：“致命三要素”、默认断网、凭证不挂载、资源限额与超时、超时返回结构化错误；
  - 借鉴：语义解析与关键字黑名单之争，本方案据此把策略定位为“减少事故”。
- 同书配套代码：[`chapter5/coding-agent/tools/bash_tool.py`](https://github.com/bojieli/ai-agent-book/blob/b789c97a8f3de5b405a6f6dfa8289208d679d0b8/chapter5/coding-agent/tools/bash_tool.py)
  - 它只截断开头，本方案保留首尾。
- learn-claude-code（MIT）：[`s03_permission`](https://github.com/shareAI-lab/learn-claude-code/blob/ce8f9f186058939da54c9d6fead78dfb5d0fd6c3/s03_permission/README.md)
  - 借鉴：拒绝列表、规则、询问用户三道闸门；它自己也说明字符串匹配不是完整的安全边界。
- learn-claude-code（MIT）：[`s04_hooks`](https://github.com/shareAI-lab/learn-claude-code/blob/ce8f9f186058939da54c9d6fead78dfb5d0fd6c3/s04_hooks/README.md)
  - 借鉴：把审批挂在工具执行前，不写进循环本身。
