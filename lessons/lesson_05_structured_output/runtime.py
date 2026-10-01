"""Parse, type-check, then independently verify a model-generated task card."""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from course.execution import LessonInputs, RunContext


FACTS = {"lesson_id": "4", "lesson_title": "任务目标与验收", "prerequisite": "3"}


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_field", "wrong_fact"] = "normal"
    repair: bool = True


INPUT_MODEL = Inputs


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lesson_id: str = Field(min_length=1, max_length=8)
    lesson_title: str = Field(min_length=1, max_length=60)
    prerequisite: str = Field(min_length=1, max_length=8)
    exercise: str = Field(min_length=8, max_length=120)


def reject_non_json_constant(value: str):
    raise ValueError("非标准 JSON 常量：" + value)


def inspect_output(raw: str) -> tuple[TaskCard | None, list[dict]]:
    checks = []
    try:
        parsed = json.loads(raw, parse_constant=reject_non_json_constant)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, [{"label": "JSON 格式", "passed": False, "detail": str(exc)}]
    checks.append({"label": "JSON 格式", "passed": True, "detail": "可解析为 JSON"})
    try:
        card = TaskCard.model_validate(parsed)
    except ValidationError as exc:
        checks.append({"label": "字段 Schema", "passed": False,
                       "detail": "; ".join(".".join(map(str, e["loc"])) + ": " + e["type"] for e in exc.errors())[:300]})
        return None, checks
    checks.append({"label": "字段 Schema", "passed": True, "detail": "必填、类型、长度及额外字段检查通过"})
    mismatches = [key for key, expected in FACTS.items() if getattr(card, key) != expected]
    checks.append({"label": "业务事实", "passed": not mismatches,
                   "detail": "与给定课程事实一致" if not mismatches else "与给定资料不符：" + ", ".join(mismatches)})
    return card, checks


def _content(response: dict) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("模型响应没有可读取的 message.content") from exc
    if not isinstance(value, str):
        raise ValueError("模型响应内容必须为文本")
    return value


def _report(context: RunContext, checks: list[dict], attempt: int) -> None:
    accepted = len(checks) == 3 and all(c["passed"] for c in checks)
    stage = "初稿" if attempt == 1 else "修复稿"
    context.emit("lesson.report", {
        "title": stage + "：结构化输出三层校验",
        "summary": stage + ("通过已执行的全部检查" if accepted else "未通过；后续层级在上游失败时不作判断"),
        "checks": checks,
        "metrics": [{"label": "模型调用次数", "value": attempt},
                    {"label": "本稿验收", "value": "通过" if accepted else "失败"},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["阶段", "结果"],
                  "rows": [[c["label"], "通过" if c["passed"] else c["detail"]] for c in checks]},
    })


def run(context: RunContext) -> str:
    scenario = context.inputs["scenario"]
    facts_text = json.dumps(FACTS, ensure_ascii=False)
    system = "只输出一个 JSON 对象，字段 lesson_id、lesson_title、prerequisite、exercise。不得编造给定事实；exercise 是 8 到 120 字的练习说明。"
    user = f"把这些可信课程事实整理为学习任务卡：{facts_text}。练习要求：用固定输入 19+23 比较运行结束和验收通过。"
    if scenario == "missing_field":
        user += " 本轮故意省略 prerequisite 字段，供校验器展示字段错误。"
    elif scenario == "wrong_fact":
        user += " 本轮故意把 prerequisite 写成 2，供校验器展示事实错误。"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    raw = _content(context.complete({"messages": messages, "temperature": 0}, 1))
    card, checks = inspect_output(raw)
    attempts = 1
    _report(context, checks, attempts)
    if (not all(item["passed"] for item in checks) and context.inputs["repair"]
            and context.max_model_calls >= 2):
        context.check_cancelled()
        messages.extend([{"role": "assistant", "content": raw},
                         {"role": "user", "content": "上一版未通过：" + "; ".join(c["detail"] for c in checks if not c["passed"])
                          + "。只按原始可信事实输出完整 JSON 对象。"}])
        raw = _content(context.complete({"messages": messages, "temperature": 0}, 2))
        card, checks = inspect_output(raw)
        attempts = 2
        _report(context, checks, attempts)
    accepted = len(checks) == 3 and all(c["passed"] for c in checks)
    return "验收通过：" + card.model_dump_json() if accepted else "模型输出未通过校验；请查看响应和三层检查。"
