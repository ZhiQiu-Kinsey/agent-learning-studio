# 目标循环与放弃条件（`goal-loops`）

[English](README.md) · 简体中文

本课回答一个问题：一个会反复尝试的循环，什么时候该停，谁说了算。答案分三层：每轮结束由独立的目标评估按事先写好的完成条件判断继续、完成或放弃；预算（轮数、模型调用数、用时）和放弃条件（不可达、同样的失败重复、连续没有进展）事先写明；结局分完成、放弃、预算耗尽三种，每种都有原因，也都不冒充别的。本课需要真实模型连接，课程目前仍是 `planned`，只做过离线验证。

任务固定为“按四份资料填写读书会通知卡”：日期来自日程表，教室来自预约回执，开始时间来自主讲人回信，第四份是上次活动的纪要，里面的日期、教室和开始时间形状相同、来源不对，专门用来混淆。资料用 `read_note` 读取。课程用 slug 指代前后课，不写会随课程表变化的课号。

| 练习 | 目标 | 执行者 | 轮数上限 | 看什么 |
| --- | --- | --- | --- | --- |
| 可达目标：预算内完成 | 日期、教室、开始时间 | 认真 | 5 | 每轮读了什么、通过几项、为什么继续，最后一轮判完成 |
| 不可达目标：资料里没有联系电话 | 再加联系电话 | 认真 | 5 | 四份来源读完后判无法完成并放弃，三项通过也不算完成 |
| 预算太小：有进展，但轮数用完 | 同第一个 | 认真 | 2 | 轮数用完，结局是预算耗尽，不是放弃 |
| 执行者自报完成，评估不通过 | 同第一个 | 赶工：催它第一轮就报 done | 5 | `status` 与评估结论不一致的轮数；原因交回执行者 |

练习之外，网页实验台还能逐项调整七个参数：`goal`、`worker_style`、`max_rounds`、`max_model_calls`、`max_seconds`、`max_stall`、`repeat_limit`。

## 机制

- **完成条件**（`CRITERIA`）：每个字段有值的形状（正则表达式）和来源资料。值要原样出现在来源里，而且这份资料在本次运行中读过；猜对的值不算。
- **目标评估**（`evaluate_goal`）：只读通知卡和 `read_note` 真正返回过的资料，不读执行者的 `status`。结论三种：`complete`（每项都过）、`unreachable`（某项的所有来源都读过仍没有符合形状的值）、`continue`（其余）。
- **放弃条件**（`Progress` 与 `decide`）：不可达；同样的失败（检查项、状态、值都相同）连续 `repeat_limit` 轮；通过项连续 `max_stall` 轮没有超过历史最好成绩。
- **预算**：`max_rounds`、`max_model_calls`、`max_seconds`，只在一轮开始前检查；剩余模型调用数不够一轮（最多 `ROUND_STEPS` 次）就不开新一轮。
- **决定顺序**：先目标结论，再放弃条件，最后预算。所以最后一轮完成仍是完成，不会记成预算耗尽。
- **结局**：完成、放弃、预算耗尽。最终回答由程序按结局拼，放弃和预算耗尽都写“目标没有完成”，附原因、停下时通过的项数和当前的卡。

## 事件

| 事件 | 内容 |
| --- | --- |
| `lesson.task_card` | 运行前发出：目标、输入范围、产物、证据要求、放弃条件和预算 |
| `lesson.completion_claim` | 执行者每轮的卡片和 `status`；读不出来的回复记为 `invalid`，写明 `parse_error` |
| `lesson.goal_evaluation` | 每轮一条评估记录：`evidence`（读过的资料和这一轮的卡）、`claim`、`verdict`、`checks`、`claim_agrees`、`progress`、`budget`、`decision`、`reason_code`、`reason` |
| `lesson.report` | 结局、停止原因、通过项、轮数、模型调用数、累计 `total_tokens`、报 done 的轮数、声明不一致的轮数，以及逐轮表 |

`reason_code` 共八种：`goal_met`、`unreachable`、`repeated_failure`、`no_progress`、`max_rounds`、`max_model_calls`、`max_seconds`、`keep_going`。`total_tokens` 只累加服务商报告的值，缺的写明几次未报告，不估算、不写 0。

## 文件

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 自定义运行器：`CRITERIA`、`evaluate_goal`、`Progress`、`decide`、`Worker`、`run` |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：资料原文、提示词、评估原因、报告文字；字段名、资料编号、原因代码是代码，各语言相同 |
| `fixtures.py` | 离线测试用的确定性模型：每个练习一份固定的执行者脚本，只服务测试 |
| `test_lesson.py` | 27 个行为测试：评估规则、放弃条件、预算、取消、输入校验、两种运行语言 |
| `content.json`、`content.en.json` | 教学内容（中文源文本、英文译文层） |
| `lesson.json`、`lesson.en.json` | 实现清单与英文译文层 |

## 运行

离线测试（不需要密钥，工具和评估程序真实执行，模型回答来自夹具）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_goal_loops.test_lesson -v
```

真实运行需要先配置模型（见 `local_config.example.py`），会产生模型用量。自动化代理请另起端口，不占用 8765：

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8813
.\.venv\Scripts\python.exe scripts/run_live.py goal-loops reachable --url http://127.0.0.1:8813 --locale zh-CN
```

四个练习在两种运行语言下都要各跑一次，再回放一遍，核对正文的说法。本课尚未做过真实模型验证。

## 实验看什么

1. **继续、完成与放弃**（可达目标 / 不可达目标）：任务卡的 `failure` 字段；第一条评估记录里的 `notes_read` 和 `checks`；报告里联系电话那一项（`field_contact_phone`）为什么没通过；结局和停止原因。
2. **预算耗尽不等于放弃**（5 轮 / 2 轮）：任务卡的 `stop`；评估记录里的 `budget` 与 `progress`；逐轮表的最后一行；停止原因写的是轮数，不是放弃条件。
3. **执行者自报完成**（认真 / 赶工）：`lesson.completion_claim` 的 `status`；`claim_agrees`；报 done 的轮数和不一致的轮数；没通过的检查项。

## 边界

- 评估只查值的形状和来源，不查资料本身是否正确；通过只说明卡片和读过的资料一致。
- 离线夹具里执行者读什么、填什么、报什么都是脚本写的。真实模型读到评估原因后能不能改对、一次读完几份资料，要看真实运行，正文不预设。
- 用时上限只在一轮开始前检查，不是硬截止；费用没有单独设上限，用模型调用数代替。

## 参考与署名

循环的形状（在停止边界上放一个独立的判断，`ok` 与 `impossible` 两种结论，连续拦截次数的上限）参考 [Learn Claude Code](https://github.com/shareAI-lab/learn-claude-code)（MIT）的 `s17_goal_loop`；停止条件、验证分层与预算—能力曲线参考《深入理解 AI Agent》（[ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）第一、七、九章；自我评估只能当参考的提醒参考 [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（MIT）的 09-metacognition 一章。任务、资料、程序验收器、进展与重复失败规则、结局划分和实验由本项目编写，没有复制上游代码。
