"""反思与有界修订：同一个正则表达式任务，分别由模型自评和真实测试结果驱动修订。

任务产物是一条正则表达式，测试用 Python re.fullmatch 在固定用例上真实执行，不运行模型写的代码。
“自我评估与纠正”的讲法参考 Microsoft AI Agents for Beginners 09（MIT），
任务、测试、评审格式、停止条件与实验由本项目编写。
"""
import json
import re
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    reviewer: Literal["self", "tests"] = "tests"
    max_iters: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
SPEC = "学号形如 s-1042：小写字母 s、一个连字符、四位数字，且第一位数字不能是 0。必须整串匹配。"
CASES = [("s-1042", True), ("s-9999", True), ("s-1000", True),
         ("s-0420", False), ("S-1042", False), ("s-104", False), ("s-10422", False), ("s1042", False), ("s-12a4", False)]
MAX_PATTERN = 200
WRITER_SYSTEM = ('你写 Python 正则表达式。只输出一个 JSON 对象：{"regex": "你的正则"}。'
                 "正则会用 re.fullmatch 匹配，不需要写 ^ 和 $。")
SELF_REVIEW_SYSTEM = ('你是评审，检查一条正则是否满足需求。只输出 JSON：'
                      '{"verdict": "pass" 或 "revise", "issues": ["问题，没有就留空"]}。')


def extract_json(content: str) -> dict:
    """读取回复里的第一个 JSON 对象；允许前后有说明文字或代码围栏，其余不做修复。"""
    start = content.find("{")
    if start < 0:
        raise ValueError("回复里没有 JSON 对象。")
    value, _ = json.JSONDecoder().raw_decode(content[start:])
    if not isinstance(value, dict):
        raise ValueError("回复里的 JSON 不是对象。")
    return value


def run_tests(pattern: str) -> dict:
    """在固定用例上真实执行 re.fullmatch。编译失败时所有用例都算失败。"""
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN:
        return {"compiled": False, "error": f"正则必须是 1–{MAX_PATTERN} 个字符的字符串。", "passed": 0,
                "failed": len(CASES), "cases": []}
    try:
        compiled = re.compile(pattern)
    except re.error as error:
        return {"compiled": False, "error": f"正则无法编译：{error}", "passed": 0, "failed": len(CASES), "cases": []}
    cases = [{"text": text, "expected": expected, "actual": compiled.fullmatch(text) is not None} for text, expected in CASES]
    passed = sum(case["expected"] == case["actual"] for case in cases)
    return {"compiled": True, "error": None, "passed": passed, "failed": len(CASES) - passed, "cases": cases}


def failures_of(tests: dict) -> list[str]:
    if not tests["compiled"]:
        return [tests["error"]]
    return [f"{case['text']} 应该{'匹配' if case['expected'] else '不匹配'}，实际{'匹配' if case['actual'] else '不匹配'}"
            for case in tests["cases"] if case["expected"] != case["actual"]]


def _tokens(response: dict) -> int | None:
    usage = response.get("usage")
    total = usage.get("total_tokens") if isinstance(usage, dict) else None
    return total if isinstance(total, int) else None


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    usage: list[int | None] = []
    rounds = 0

    def ask(system: str, user: str) -> str:
        nonlocal rounds
        rounds += 1
        response = context.complete({"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                                     "temperature": 0}, rounds)
        usage.append(_tokens(response))
        content = response["choices"][0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    def draft(user: str, version: int, previous: str | None) -> str:
        content = ask(WRITER_SYSTEM, user)
        try:
            pattern = extract_json(content).get("regex")
            pattern = pattern if isinstance(pattern, str) else ""
            error = None if pattern else "JSON 里没有字符串字段 regex"
        except ValueError as exc:
            pattern, error = "", str(exc)
        context.emit("lesson.draft", {"version": version, "regex": pattern, "previous": previous,
                                      "unchanged": previous is not None and pattern == previous,
                                      "parse_error": error, "raw": content}, rounds)
        return pattern

    pattern = draft("需求：" + SPEC, 0, None)
    stop_reason, history = "达到迭代上限", []
    for iteration in range(1, values.max_iters + 1):
        context.check_cancelled()
        if values.reviewer == "tests":
            tests = run_tests(pattern)
            context.emit("lesson.tests", {"version": iteration - 1, **tests}, rounds)
            issues = failures_of(tests)
            verdict = "pass" if not issues else "revise"
            context.emit("lesson.review", {"iteration": iteration, "source": "tests", "verdict": verdict,
                                           "issues": issues}, rounds)
        else:
            content = ask(SELF_REVIEW_SYSTEM, f"需求：{SPEC}\n正则：{pattern}")
            try:
                review = extract_json(content)
                verdict = review.get("verdict") if review.get("verdict") in ("pass", "revise") else "invalid"
                issues = [str(item) for item in review.get("issues", [])] if isinstance(review.get("issues"), list) else []
            except ValueError:
                verdict, issues = "invalid", []
            context.emit("lesson.review", {"iteration": iteration, "source": "model", "verdict": verdict,
                                           "issues": issues, "raw": content}, rounds)
        history.append([iteration, pattern, "测试" if values.reviewer == "tests" else "模型自评", verdict,
                        "；".join(issues) or "—"])
        if verdict == "pass":
            stop_reason = "评审通过"
            break
        if verdict == "invalid":
            stop_reason = "评审输出不合格式"
            break
        if iteration == values.max_iters:
            break
        previous = pattern
        pattern = draft(f"需求：{SPEC}\n上一版正则：{previous}\n评审意见：" + json.dumps(issues, ensure_ascii=False)
                        + "\n请修订。", iteration, previous)
        if pattern == previous:
            stop_reason = "修订后没有变化"
            break
    # 不论评审来自哪里，最后都用同一组真实测试检查最终版本。
    final = run_tests(pattern)
    context.emit("lesson.tests", {"version": "final", **final}, rounds)
    reported = [value for value in usage if value is not None]
    context.emit("lesson.report", {
        "title": "模型自评驱动修订" if values.reviewer == "self" else "测试结果驱动修订",
        "summary": "最终版本一律用同一组真实用例检查；评审说通过，不等于测试通过。",
        "checks": [{"label": "最终版本通过全部用例", "passed": final["failed"] == 0,
                    "detail": f"{final['passed']}/{len(CASES)} 通过" + (f"；{final['error']}" if final["error"] else "")}],
        "metrics": [{"label": "停止原因", "value": stop_reason},
                    {"label": "迭代次数", "value": len(history)}, {"label": "迭代上限", "value": values.max_iters},
                    {"label": "模型调用数", "value": rounds},
                    {"label": "累计 total_tokens", "value": sum(reported) if len(reported) == len(usage) else
                     (f"{sum(reported)}（{len(usage) - len(reported)} 次未报告）" if reported else "未报告")},
                    {"label": "最终正则", "value": pattern or "（空）"},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["迭代", "被评审的正则", "评审来源", "结论", "意见"], "rows": history},
    })
    outcome = "通过" if final["failed"] == 0 else "未通过"
    return f"停止原因：{stop_reason}。最终正则 {pattern or '（空）'} 在真实用例上{outcome}（{final['passed']}/{len(CASES)}）。"
