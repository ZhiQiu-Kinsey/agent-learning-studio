"""Skills 与渐进式披露：同一个任务，技能正文全部放进系统提示词，或只放目录、用到再加载。

skills/<name>/SKILL.md 是本课自己写的教学材料：两行 --- 之间写 name 和 description，后面是正文。
"""
import json
from pathlib import Path
from typing import Literal

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    mode: Literal["both", "full", "on_demand"] = "both"
    task: Literal["make_cards", "chat", "review_question"] = "make_cards"
    description: Literal["precise", "vague"] = "precise"


INPUT_MODEL = Inputs

SKILLS_DIR = Path(__file__).with_name("skills")
# 白名单：只有登记在这里的技能会进目录、能被加载；skills/ 里多放一个文件不会自动生效。
SKILL_NAMES = ("review-cards", "error-question", "unit-test-checklist", "three-sentence-summary")
# “模糊描述”只替换 review-cards 的 description，正文和其他技能都不变。
VAGUE_DESCRIPTION = "帮助学习。"


def read_skill(name: str) -> dict:
    """读一个 SKILL.md：两行 --- 之间是 name 和 description，其余是正文。"""
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    _, header, body = text.split("---\n", 2)
    fields = dict(line.split(":", 1) for line in header.strip().splitlines())
    if fields.get("name", "").strip() != name:
        raise ValueError(f"{name}/SKILL.md 里的 name 与登记的名字不一致。")
    return {"name": name, "description": fields["description"].strip(), "body": body.strip()}


def skill_list(description: str) -> list[dict]:
    skills = [read_skill(name) for name in SKILL_NAMES]
    if description == "vague":
        skills[0]["description"] = VAGUE_DESCRIPTION
    return skills


def load_skill(name: str) -> dict:
    """load_skill 工具：模型给的名字只拿来查白名单，查到了才读对应的文件。"""
    if name not in SKILL_NAMES:
        # ValueError 由 execute_tool 整理成 ok 为 false 的结构化错误，交还给模型。
        raise ValueError(f"没有名为 {name} 的技能；技能目录里只有：{'、'.join(SKILL_NAMES)}。")
    return {"name": name, "instructions": read_skill(name)["body"]}


AVAILABLE_TOOLS = {"load_skill": load_skill}

NOTE = ("Python 的列表可以修改，元组创建后不能修改。字典按键取值，键必须是不可变类型，"
        "所以元组可以当键，列表不行。集合会自动去重，但不保证元素顺序；"
        "判断一个元素在不在集合里，通常比在列表里查找快得多。")
# 每个任务：发给模型的用户消息，以及本课认定该用的技能（None 表示不该加载任何技能）。
TASKS = {
    "make_cards": ("把下面这段学习笔记整理成复习卡：\n" + NOTE, "review-cards"),
    "chat": ("你好！今天周五，跟我打个招呼吧。", None),
    "review_question": ("帮我复习一下：Python 的列表和元组有什么区别？一两句话说清楚就行。", None),
}
ON_DEMAND_LIMIT = 3  # 按需加载最多请求 3 次：提出加载、拿到正文后回答，再留一次余量


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    question, expected = TASKS[values.task]
    skills = skill_list(values.description)
    passes = []
    # 两种都跑时，先全量注入（第 1 次请求），再按需加载（从第 2 次请求开始）。
    if values.mode in ("both", "full"):
        passes.append(run_full(context, skills, question, round_number=1))
    if values.mode in ("both", "on_demand"):
        passes.append(run_on_demand(context, skills, question, first_round=len(passes) + 1))
    _report(context, values, expected, passes)
    return "\n\n".join(f"【{MODE_LABELS[item['mode']]}】\n{_answer_text(item)}" for item in passes)


TOOLS = [{"type": "function", "function": {
    "name": "load_skill",
    "description": "读取一个技能的完整做法。name 必须是技能目录里列出的名字。",
    "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "技能目录里的名字"}},
                   "required": ["name"], "additionalProperties": False}}}]
FULL_PROMPT = ("你是学习助手。下面是你会的全部技能，每个都附有完整做法。"
               "用户的任务符合某个技能的描述时，严格按它的做法完成；都不符合时直接正常回答，不要套用技能。")
CATALOG_PROMPT = ("你是学习助手。下面的技能目录只列出每个技能的名字和描述。"
                  "用户的任务符合某个技能的描述时，先调用 load_skill 读取它的完整做法，再按做法完成；"
                  "都不符合时直接正常回答，不要加载技能。")


def full_prompt(skills: list[dict]) -> str:
    # 全量注入：每个技能的描述和正文都拼进系统提示词，之后每次请求都带着。
    sections = [f"## 技能 {skill['name']}\n描述：{skill['description']}\n\n{skill['body']}" for skill in skills]
    return FULL_PROMPT + "\n\n" + "\n\n".join(sections)


def catalog_prompt(skills: list[dict]) -> str:
    # 渐进式披露：每个技能在系统提示词里只占一行；正文等模型调用 load_skill 时才给。
    lines = [f"- {skill['name']}：{skill['description']}" for skill in skills]
    return CATALOG_PROMPT + "\n\n技能目录：\n" + "\n".join(lines)


def run_full(context: RunContext, skills: list[dict], question: str, round_number: int) -> dict:
    messages = [{"role": "system", "content": full_prompt(skills)}, {"role": "user", "content": question}]
    # 全量注入只发一次请求：做法已经都在系统提示词里，不需要工具。
    response = context.complete({"messages": messages, "temperature": 0}, round_number)
    record = _record(context, "full", round_number, messages, response, skills)
    return {"mode": "full", "answer": _content(response), "requests": [record], "loaded": None}


def run_on_demand(context: RunContext, skills: list[dict], question: str, first_round: int) -> dict:
    # 1. 系统提示词只放目录；技能正文只能经由 load_skill 的工具结果进入消息历史。
    messages = [{"role": "system", "content": catalog_prompt(skills)}, {"role": "user", "content": question}]
    requests, loaded = [], []
    for round_number in range(first_round, first_round + ON_DEMAND_LIMIT):
        context.check_cancelled()
        # 2. 每次请求都带着 load_skill：加载不加载、加载哪个，由模型决定。
        response = context.complete({"messages": messages, "tools": TOOLS, "tool_choice": "auto",
                                     "temperature": 0}, round_number)
        requests.append(_record(context, "on_demand", round_number, messages, response, skills))
        message = response["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        # 3. 没有调用提议：content 就是回答。
        if not calls:
            return {"mode": "on_demand", "answer": message.get("content") or "", "requests": requests,
                    "loaded": loaded}
        # 4. 执行模型提出的 load_skill；正文作为工具结果放回消息历史，下一次请求才看得到。
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            result = context.execute_proposal(call, AVAILABLE_TOOLS)
            if result["ok"]:
                loaded.append(result["result"]["name"])
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    # 用完轮数上限，模型还在要技能：不再请求，如实记为没有回答。
    return {"mode": "on_demand", "answer": None, "requests": requests, "loaded": loaded}


def judge_loading(expected: str | None, loaded: list[str] | None) -> tuple[bool | None, str]:
    """对照“本课认定该用的技能”和事件里真正加载成功的技能。"""
    if loaded is None:
        return None, "不适用：全部正文常驻"
    if not loaded:
        return (True, "正确：没有加载") if expected is None else (False, "漏触发：该加载却没加载")
    names = "、".join(dict.fromkeys(loaded))
    if expected is None:
        return False, f"误触发：加载了 {names}"
    return (True, f"正确：加载了 {names}") if set(loaded) == {expected} else (False, f"加载错技能：{names}")


def count_cards(answer: str) -> tuple[int, int]:
    """数以“问：”“答：”开头的行；先去掉 Markdown 星号和行首编号。"""
    asked = answered = 0
    for line in answer.splitlines():
        text = line.replace("*", "").strip().lstrip("-#>0123456789.、 ")
        asked += text.startswith(("问：", "问:"))
        answered += text.startswith(("答：", "答:"))
    return asked, answered


def format_screen(expected: str | None, answer: str | None) -> tuple[bool, str]:
    """格式初筛：只看回答像不像复习卡，不判断内容对不对。"""
    if answer is None:
        return False, "没有回答"
    asked, answered = count_cards(answer)
    if expected == "review-cards":
        return 3 <= asked <= 5 and asked == answered, f"{asked} 个“问：”、{answered} 个“答：”，技能要求 3–5 张卡"
    return asked == 0, "没有写成复习卡" if asked == 0 else f"写成了 {asked} 张复习卡"


# ---------- 平台：记录每次请求、发布报告 ----------

MODE_LABELS = {"full": "全量注入", "on_demand": "目录 + 按需加载"}
TASK_LABELS = {"make_cards": "整理复习卡", "chat": "闲聊", "review_question": "复习提问"}


def _content(response: dict) -> str:
    content = response["choices"][0]["message"].get("content")
    return content if isinstance(content, str) else ""


def _answer_text(item: dict) -> str:
    return item["answer"] if item["answer"] is not None else f"{ON_DEMAND_LIMIT} 次请求内没有得到回答。"


def _proposed_name(call: dict) -> str:
    try:
        name = json.loads(call["function"].get("arguments") or "{}").get("name")
    except (json.JSONDecodeError, AttributeError):
        name = None
    return name if isinstance(name, str) else "（参数无法解析）"


def _record(context: RunContext, mode: str, round_number: int, messages: list[dict], response: dict,
            skills: list[dict]) -> dict:
    """一次请求的证据：服务商报告的提示 Token、这次发出的消息里有哪些技能正文、响应提出加载哪些技能。"""
    usage = response.get("usage")
    tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    sent = "\n".join(str(message.get("content") or "") for message in messages)
    # 全量注入时正文在系统提示词里原样出现；按需加载时在工具结果里，是 JSON 转义后的样子。
    in_context = [skill["name"] for skill in skills
                  if skill["body"] in sent or json.dumps(skill["body"], ensure_ascii=False)[1:-1] in sent]
    calls = response["choices"][0]["message"].get("tool_calls") or []
    record = {"mode": mode, "round": round_number,
              "prompt_tokens": tokens if type(tokens) is int else None,
              "system_chars": len(messages[0]["content"]), "skills_in_context": in_context,
              "proposed_loads": [_proposed_name(call) for call in calls]}
    context.emit("lesson.skill_request", record, round_number)
    return record


def _tokens(values: list[int | None]) -> tuple[str, int | str]:
    shown = " → ".join("未报告" if value is None else str(value) for value in values)
    missing = sum(value is None for value in values)
    total = sum(value for value in values if value is not None)
    return shown, total if not missing else ("未报告" if missing == len(values) else f"{total}（{missing} 次未报告）")


def _report(context: RunContext, values: Inputs, expected: str | None, passes: list[dict]) -> None:
    rows, checks = [], []
    metrics = [{"label": "任务", "value": TASK_LABELS[values.task]},
               {"label": "review-cards 的描述", "value": "模糊" if values.description == "vague" else "精确"},
               {"label": "本课认定该用的技能", "value": expected or "不该加载任何技能"}]
    for item in passes:
        label, first = MODE_LABELS[item["mode"]], item["requests"][0]
        shown, total = _tokens([record["prompt_tokens"] for record in item["requests"]])
        loading_ok, loading = judge_loading(expected, item["loaded"])
        format_ok, format_detail = format_screen(expected, item["answer"])
        proposals = "；".join(f"第 {record['round']} 次请求提出 {'、'.join(record['proposed_loads'])}"
                             for record in item["requests"] if record["proposed_loads"])
        rows.append([label, len(item["requests"]), shown, total,
                     proposals or ("全部常驻" if item["loaded"] is None else "没有提出加载"),
                     loading, ("通过：" if format_ok else "未通过：") + format_detail])
        metrics.append({"label": f"第 1 次请求的提示 Token（{label}）",
                        "value": "未报告" if first["prompt_tokens"] is None else first["prompt_tokens"]})
        if item["mode"] == "full":
            checks.append({"label": "全量注入：请求里带着全部技能正文",
                           "passed": len(first["skills_in_context"]) == len(SKILL_NAMES),
                           "detail": f"在实际发出的消息里找到 {len(first['skills_in_context'])} 个技能的正文。"})
        else:
            checks.append({"label": "按需加载：第 1 次请求里没有任何技能正文",
                           "passed": not first["skills_in_context"],
                           "detail": f"第 1 次请求的系统提示词 {first['system_chars']} 个字符，只含目录。"})
            checks.append({"label": "按需加载：加载判定", "passed": loading_ok, "detail": loading})
            rejected = [name for record in item["requests"] for name in record["proposed_loads"]
                        if name not in SKILL_NAMES]
            if rejected:
                checks.append({"label": "未登记的技能名被拒绝", "passed": True,
                               "detail": f"{'、'.join(rejected)} 不在白名单里，工具结果是结构化错误。"})
        checks.append({"label": f"{label}：回答格式初筛", "passed": format_ok,
                       "detail": format_detail + "。只看格式，不代表内容正确。"})
    metrics += [{"label": "模型调用数", "value": sum(len(item["requests"]) for item in passes)},
                {"label": "学习者备注", "value": context.question or "（空）"}]
    context.emit("lesson.report", {
        "title": " 与 ".join(MODE_LABELS[item["mode"]] for item in passes) + "：" + TASK_LABELS[values.task],
        "summary": "提示 Token 来自每次响应的 usage，没有报告的写“未报告”；加载判定只看 load_skill 的工具结果，"
                   "格式初筛只看回答像不像复习卡。",
        "checks": checks, "metrics": metrics,
        "table": {"columns": ["方式", "模型调用数", "每次提示 Token", "提示 Token 合计", "加载记录", "加载判定",
                              "格式初筛"], "rows": rows},
    })
