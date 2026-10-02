"""编排者-工人与评估者-优化者：同一个出题任务，对照单次调用，统计多出来的调用和用量。

两种模式的划分参考 claude-cookbooks patterns/agents（MIT）。原示例的编排者实际串行执行工人、
评估循环没有上限；本课的工人并行执行，评估循环必须有 max_iters。任务、格式检查与实验由本项目编写。
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    pattern: Literal["single", "orchestrator", "evaluator"] = "orchestrator"
    max_iters: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
NOTES = {
    "7": "模型只看到本次请求里的消息，历史要由应用程序重发。",
    "8": "应用状态记录目标和证据，消息列表不会自动更新它。",
    "9": "压缩上下文时，工具调用和工具结果要成对保留或成对删除。",
}
TASK = "为第 7、8、9 课各出一道四选一的选择题，题目要考到该课要点。"
QUESTION_FORMAT = ('只输出一个 JSON 对象：{"question": "题干", "options": ["A", "B", "C", "D"], '
                   '"answer": 正确选项的下标 0-3, "explanation": "为什么这个选项对"}')
SINGLE_SYSTEM = ('你是出题老师，一次写完全部题目。只输出一个 JSON 数组，按第 7、8、9 课的顺序，每个元素是'
                 '{"question": "题干", "options": ["A", "B", "C", "D"], "answer": 正确选项的下标 0-3, '
                 '"explanation": "为什么这个选项对"}')
ORCHESTRATOR_SYSTEM = ('你是编排者，只负责拆分任务，不写题目。只输出 JSON：'
                       '{"subtasks": [{"id": "w1", "lesson": "7", "instruction": "交给工人的一句话指令"}]}。'
                       "最多 4 个子任务，lesson 只能是 7、8、9。")
WORKER_SYSTEM = "你是出题老师，只完成交给你的一道题。" + QUESTION_FORMAT
EVALUATOR_SYSTEM = ('你是评审。按量规检查一道选择题：题干考的是给定要点；四个选项都合理但只有一个正确；'
                    '解释说明了为什么正确。只输出 JSON：{"verdict": "pass" 或 "revise", "feedback": ["具体问题"]}。')
MAX_WORKERS = 4


def extract_json(content: str):
    """读取回复里的第一个 JSON 值；允许前后有说明文字或代码围栏，其余不做修复。"""
    starts = [index for index in (content.find("{"), content.find("[")) if index >= 0]
    if not starts:
        raise ValueError("回复里没有 JSON。")
    value, _ = json.JSONDecoder().raw_decode(content[min(starts):])
    return value


def check_question(value) -> list[str]:
    """程序能确定的格式检查；内容好坏交给评审。"""
    if not isinstance(value, dict):
        return ["不是 JSON 对象"]
    problems = []
    if not isinstance(value.get("question"), str) or not value["question"].strip():
        problems.append("缺少题干")
    options = value.get("options")
    if not isinstance(options, list) or len(options) != 4 or not all(isinstance(o, str) and o.strip() for o in options):
        problems.append("options 必须是 4 个非空字符串")
    elif len(set(options)) != 4:
        problems.append("四个选项不能重复")
    if type(value.get("answer")) is not int or not 0 <= value["answer"] <= 3:
        problems.append("answer 必须是 0 到 3 的整数")
    if not isinstance(value.get("explanation"), str) or not value["explanation"].strip():
        problems.append("缺少解释")
    return problems


class Ledger:
    """记录每次模型调用的角色和服务商报告的 total_tokens；没有报告就记 None，不估算。"""

    def __init__(self, context: RunContext):
        self.context = context
        self.rows: list[dict] = []

    def call(self, role: str, system: str, user: str, round_number: int, branch: str | None = None) -> str:
        started = time.perf_counter()
        response = self.context.complete({"messages": [{"role": "system", "content": system},
                                                       {"role": "user", "content": user}], "temperature": 0},
                                         round_number, branch=branch)
        usage = response.get("usage")
        tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        self.rows.append({"role": role, "branch": branch, "round": round_number,
                          "tokens": tokens if isinstance(tokens, int) else None,
                          "ms": round((time.perf_counter() - started) * 1000)})
        content = response["choices"][0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    def total(self) -> str | int:
        reported = [row["tokens"] for row in self.rows if row["tokens"] is not None]
        missing = len(self.rows) - len(reported)
        if not reported:
            return "未报告"
        return sum(reported) if not missing else f"{sum(reported)}（{missing} 次未报告）"


def run_single(context: RunContext, ledger: Ledger) -> tuple[dict, list]:
    content = ledger.call("单次调用", SINGLE_SYSTEM, TASK + "\n要点：" + json.dumps(NOTES, ensure_ascii=False), 1)
    try:
        value = extract_json(content)
        questions = value if isinstance(value, list) else []
    except ValueError:
        questions = []
    results = {}
    for index, lesson in enumerate(NOTES):
        item = questions[index] if index < len(questions) else None
        results[lesson] = {"question": item, "problems": check_question(item) if item is not None else ["没有这道题"]}
    return results, [[f"第 {k} 课", "；".join(v["problems"]) or "格式通过"] for k, v in results.items()]


def run_orchestrator(context: RunContext, ledger: Ledger) -> tuple[dict, list]:
    content = ledger.call("编排者", ORCHESTRATOR_SYSTEM, TASK, 1)
    try:
        plan = extract_json(content)
        subtasks = plan.get("subtasks") if isinstance(plan, dict) else None
        valid = (isinstance(subtasks, list) and 0 < len(subtasks) <= MAX_WORKERS
                 and all(isinstance(s, dict) and s.get("lesson") in NOTES and isinstance(s.get("id"), str)
                         and isinstance(s.get("instruction"), str) for s in subtasks)
                 and len({s["id"] for s in subtasks}) == len(subtasks))
    except ValueError:
        valid, subtasks = False, None
    if not valid:
        context.emit("lesson.plan_error", {"error": "编排者的子任务列表不合格式", "raw": content}, 1)
        return {}, [["编排者", "子任务列表不合格式，没有派出工人"]]
    steps = [{"id": s["id"], "content": f"第 {s['lesson']} 课：{s['instruction']}", "status": "in_progress"} for s in subtasks]
    context.emit("lesson.plan", {"version": 1, "event": "created", "reason": "编排者拆出的子任务", "diff": {}, "steps": steps}, 1)

    def work(subtask: dict) -> tuple[dict, str]:
        context.check_cancelled()
        user = f"{subtask['instruction']}\n要点：{NOTES[subtask['lesson']]}"
        return subtask, ledger.call("工人", WORKER_SYSTEM, user, 2, branch=subtask["id"])

    results, rows = {}, []
    with ThreadPoolExecutor(max_workers=len(subtasks)) as pool:
        outputs = list(pool.map(work, subtasks))
    for subtask, output in outputs:
        try:
            question = extract_json(output)
        except ValueError:
            question = None
        problems = check_question(question) if question is not None else ["没有 JSON"]
        results.setdefault(subtask["lesson"], {"question": question, "problems": problems})
        context.emit("lesson.worker", {"id": subtask["id"], "lesson": subtask["lesson"], "problems": problems,
                                       "output": output}, 2)
        for step in steps:
            if step["id"] == subtask["id"]:
                step["status"] = "done" if not problems else "failed"
        rows.append([subtask["id"], "；".join(problems) or "格式通过"])
    context.emit("lesson.plan", {"version": 1, "event": "progress", "reason": "", "diff": {}, "steps": steps}, 2)
    return results, rows


def run_evaluator(context: RunContext, ledger: Ledger, max_iters: int) -> tuple[dict, list, str]:
    lesson, rows, feedback, previous = "9", [], [], None
    stop_reason = "达到迭代上限"
    question = None
    for iteration in range(1, max_iters + 1):
        context.check_cancelled()
        user = f"为第 {lesson} 课出一道选择题。要点：{NOTES[lesson]}"
        if previous is not None:
            user += f"\n上一版：{previous}\n评审意见：" + json.dumps(feedback, ensure_ascii=False) + "\n请修订。"
        output = ledger.call("生成者", WORKER_SYSTEM, user, len(ledger.rows) + 1)
        try:
            question = extract_json(output)
        except ValueError:
            question = None
        problems = check_question(question) if question is not None else ["没有 JSON"]
        context.emit("lesson.draft", {"version": iteration - 1, "question": question, "previous": previous,
                                      "format_problems": problems}, len(ledger.rows))
        if problems:
            verdict, feedback, source = "revise", problems, "format-check"
        else:
            review = ledger.call("评估者", EVALUATOR_SYSTEM, f"要点：{NOTES[lesson]}\n题目：{output}", len(ledger.rows) + 1)
            try:
                parsed = extract_json(review)
                verdict = parsed.get("verdict") if isinstance(parsed, dict) and parsed.get("verdict") in ("pass", "revise") else "invalid"
                feedback = [str(item) for item in parsed.get("feedback", [])] if isinstance(parsed, dict) and isinstance(parsed.get("feedback"), list) else []
            except ValueError:
                verdict, feedback = "invalid", []
            source = "evaluator"
        context.emit("lesson.review", {"iteration": iteration, "source": source, "verdict": verdict, "issues": feedback},
                     len(ledger.rows))
        rows.append([iteration, source, verdict, "；".join(feedback) or "—"])
        if verdict == "pass":
            stop_reason = "评审通过"
            break
        if verdict == "invalid":
            stop_reason = "评审输出不合格式"
            break
        previous = output
    return {lesson: {"question": question, "problems": check_question(question) if question is not None else ["没有 JSON"]}}, rows, stop_reason


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    ledger = Ledger(context)
    stop_reason = None
    if values.pattern == "single":
        results, rows = run_single(context, ledger)
        columns = ["题目", "格式检查"]
    elif values.pattern == "orchestrator":
        results, rows = run_orchestrator(context, ledger)
        columns = ["工人", "格式检查"]
    else:
        results, rows, stop_reason = run_evaluator(context, ledger, values.max_iters)
        columns = ["轮", "评审来源", "结论", "意见"]
    expected = ["9"] if values.pattern == "evaluator" else list(NOTES)
    ok = [lesson for lesson in expected if lesson in results and not results[lesson]["problems"]]
    context.emit("lesson.report", {
        "title": {"single": "单次调用", "orchestrator": "编排者-工人", "evaluator": "评估者-优化者"}[values.pattern],
        "summary": "格式由程序检查；题目质量只有评估者模式请了模型评审。用量只累加服务商报告的 total_tokens。",
        "checks": [{"label": "每道题都通过格式检查", "passed": len(ok) == len(expected),
                    "detail": f"{len(ok)}/{len(expected)} 道通过"}],
        "metrics": [{"label": "模型调用数", "value": len(ledger.rows)},
                    {"label": "累计 total_tokens", "value": ledger.total()},
                    {"label": "各角色调用", "value": "、".join(f"{role} {sum(r['role'] == role for r in ledger.rows)}"
                                                         for role in dict.fromkeys(r["role"] for r in ledger.rows))},
                    *([{"label": "停止原因", "value": stop_reason}] if stop_reason else []),
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": columns, "rows": rows},
    })
    context.emit("lesson.cost", {"calls": ledger.rows, "total_tokens": ledger.total()})
    return f"共 {len(ledger.rows)} 次模型调用，{len(ok)}/{len(expected)} 道题通过格式检查" + (f"，停止原因：{stop_reason}。" if stop_reason else "。")
