"""工作流模式：提示链（带检查门）、路由（带兜底）、并行与串行。

三种模式的划分参考 claude-cookbooks patterns/agents/basic_workflows（MIT）。那份示例的路由遇到
未知标签会出错，本课改为记录原文并走兜底路径；工单、检查门、计时与实验由本项目编写。
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    pattern: Literal["chain", "routing", "serial", "parallel"] = "routing"


INPUT_MODEL = Inputs

# ---------- 提示链 ----------
NOTE = ("第 7 课讲消息与上下文：模型只看到本次请求里的消息，历史要由应用程序重发；"
        "assistant 的工具调用和 tool 消息必须成对出现；上下文越长，越要注意哪些信息真的需要。")
CHAIN = [
    ("提取要点", "从下面的笔记里提取恰好 3 个要点。每行一个，以“- ”开头，不要写别的。"),
    ("改写问答", "把下面每个要点改写成一组问答。每组两行：第一行以“Q: ”开头，第二行以“A: ”开头。只输出这 6 行。"),
    ("起标题", "给下面三组问答各起一个不超过 8 个字的标题。只输出一个 JSON 字符串数组，例如 [\"标题一\", \"标题二\", \"标题三\"]。"),
]


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def gate(step: int, output: str) -> tuple[bool, str]:
    """每一步之后的程序检查；不通过就停在这一步，不把不合格的结果传下去。"""
    lines = _lines(output)
    if step == 0:
        ok = len(lines) == 3 and all(line.startswith("- ") for line in lines)
        return ok, f"{len(lines)} 行，" + ("都以“- ”开头" if ok else "需要恰好 3 行且都以“- ”开头")
    if step == 1:
        questions = [line for line in lines if line.startswith("Q: ")]
        answers = [line for line in lines if line.startswith("A: ")]
        ok = len(lines) == 6 and len(questions) == 3 and len(answers) == 3
        return ok, f"Q {len(questions)} 行、A {len(answers)} 行，共 {len(lines)} 行"
    try:
        titles = json.loads(output.strip())
    except json.JSONDecodeError:
        return False, "不是合法的 JSON"
    ok = isinstance(titles, list) and len(titles) == 3 and all(isinstance(t, str) and 0 < len(t) <= 8 for t in titles)
    return ok, "3 个不超过 8 字的标题" if ok else "需要 3 个不超过 8 字的字符串"


# ---------- 路由 ----------
LABELS = {"course": "课程内容", "account": "账号与登录", "error": "运行报错", "other": "其他"}
FALLBACK = "other"
# 20 张人工标注的工单；标签是本课作者标的，有几张故意写得模棱两可。
TICKETS = [
    ("t01", "第 9 课说字符数不等于 token，那 token 到底怎么算？", "course"),
    ("t02", "登录后一直跳回首页，清了缓存也不行。", "account"),
    ("t03", "运行第 3 课时报 ZeroDivisionError，是我哪里写错了？", "error"),
    ("t04", "能不能开个夜间模式？", "other"),
    ("t05", "第 4 课的任务卡和第 5 课的结构化输出有什么区别？", "course"),
    ("t06", "改了邮箱以后收不到验证码。", "account"),
    ("t07", "点运行之后一直转圈，控制台显示 HTTP 400。", "error"),
    ("t08", "课程有没有配套的纸质书？", "other"),
    ("t09", "ReAct 和原生工具调用到底差在哪？", "course"),
    ("t10", "账号被锁了，提示尝试次数过多。", "account"),
    ("t11", "导出录制时报错：源码哈希不一致。", "error"),
    ("t12", "想推荐给同事，有没有团队版？", "other"),
    ("t13", "为什么提醒要放在 tool 消息之后？第 14 课没看懂。", "course"),
    ("t14", "忘记密码了，重置链接过期了。", "account"),
    ("t15", "第 13 课跑完提示 JSONDecodeError。", "error"),
    ("t16", "页面字体能调大一点吗？", "other"),
    ("t17", "第 10 课的记忆和第 8 课的状态是一回事吗？", "course"),
    ("t18", "换了电脑以后学习进度没了，是账号没同步吗？", "account"),
    ("t19", "运行到一半我点了停止，然后再也运行不了，提示上一次运行尚未结束。", "error"),
    ("t20", "第 15 课的备份数据源是不是也会坏？", "course"),
]
ROUTER_SYSTEM = ("你负责给学习平台的工单分类。只输出一个标签，不要解释。可选标签："
                 + "；".join(f"{key}（{name}）" for key, name in LABELS.items()) + "。")


def parse_label(content: str) -> tuple[str, bool]:
    """取回复第一行的标签；不在列表里就走兜底，并如实标记 fallback。"""
    lines = (content or "").strip().splitlines()
    first = lines[0].strip().strip("`'\"。.").lower() if lines else ""
    return (first, False) if first in LABELS else (FALLBACK, True)


def confusion(rows: list[tuple[str, str]]) -> list[list]:
    keys = list(LABELS)
    table = []
    for gold in keys:
        counts = [sum(1 for g, p in rows if g == gold and p == predicted) for predicted in keys]
        table.append([LABELS[gold], *counts])
    return table


# ---------- 并行与串行 ----------
TOPICS = {
    "7": "模型只看到本次请求里的消息，历史要由应用程序重发。",
    "8": "应用状态记录目标和证据，消息列表不会自动更新它。",
    "9": "压缩上下文时，工具调用和工具结果要成对保留或成对删除。",
}
SUMMARY_SYSTEM = "用一句不超过 30 字的话复述要点，不要加别的内容。"


def _text(response: dict) -> str:
    content = response["choices"][0].get("message", {}).get("content")
    return content if isinstance(content, str) else ""


def run_chain(context: RunContext) -> str:
    current, rows, stopped = NOTE, [], None
    for index, (name, instruction) in enumerate(CHAIN):
        context.check_cancelled()
        response = context.complete({"messages": [{"role": "user", "content": f"{instruction}\n\n{current}"}],
                                     "temperature": 0}, index + 1)
        output = _text(response)
        passed, detail = gate(index, output)
        context.emit("lesson.chain_step", {"step": index + 1, "name": name, "gate_passed": passed,
                                           "gate_detail": detail, "output": output}, index + 1)
        rows.append([index + 1, name, "通过" if passed else "未通过", detail])
        if not passed:
            stopped = name
            break
        current = output
    context.emit("lesson.report", {
        "title": "提示链", "summary": "每一步之后由程序检查格式，不通过就停在这一步，不把不合格的结果传给下一步。",
        "checks": [{"label": f"第 {row[0]} 步检查门：{row[1]}", "passed": row[2] == "通过", "detail": row[3]} for row in rows],
        "metrics": [{"label": "模型调用数", "value": len(rows)},
                    {"label": "停在", "value": stopped or "全部完成"},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["步", "名称", "检查门", "说明"], "rows": rows},
    })
    return f"提示链停在“{stopped}”：检查门未通过。" if stopped else "提示链三步都通过了检查门。最终输出：" + current


def run_routing(context: RunContext) -> str:
    pairs, rows, fallbacks = [], [], 0
    for index, (ticket_id, text, gold) in enumerate(TICKETS, 1):
        context.check_cancelled()
        response = context.complete({"messages": [{"role": "system", "content": ROUTER_SYSTEM},
                                                  {"role": "user", "content": text}], "temperature": 0}, index)
        raw = _text(response)
        predicted, fallback = parse_label(raw)
        fallbacks += fallback
        context.emit("lesson.route", {"ticket": ticket_id, "gold": gold, "predicted": predicted, "raw": raw,
                                      "fallback": fallback, "correct": predicted == gold}, index)
        pairs.append((gold, predicted))
        if predicted != gold or fallback:
            rows.append([ticket_id, text, LABELS[gold], LABELS[predicted], raw if fallback else "—"])
    correct = sum(g == p for g, p in pairs)
    context.emit("lesson.report", {
        "title": "路由准确率", "summary": "准确率按作者的人工标注计算；标注本身也可能有争议，错分的工单列在下表供复核。",
        "checks": [{"label": "每张工单都有路由结果", "passed": len(pairs) == len(TICKETS),
                    "detail": f"{len(pairs)}/{len(TICKETS)}，其中 {fallbacks} 张走了兜底"}],
        "metrics": [{"label": "准确率", "value": f"{correct}/{len(TICKETS)}"},
                    {"label": "兜底次数", "value": fallbacks},
                    {"label": "模型调用数", "value": len(pairs)},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["工单", "内容", "标注", "预测", "兜底前的原文"], "rows": rows},
    })
    context.emit("lesson.report", {
        "title": "混淆矩阵", "summary": "行是人工标注，列是路由结果；对角线以外的格子就是分错的工单数。",
        "table": {"columns": ["标注 → 预测",*LABELS.values()], "rows": confusion(pairs)},
    })
    return f"路由完成：{correct}/{len(TICKETS)} 与标注一致，{fallbacks} 张走了兜底。"


def run_fanout(context: RunContext, parallel: bool) -> str:
    """同样三个互不依赖的子任务，串行或并行发出；时间用服务端 perf_counter 测量。"""
    origin = time.perf_counter()
    spans: dict[str, dict] = {}

    def one(lesson: str) -> str:
        context.check_cancelled()
        started = time.perf_counter()
        response = context.complete({"messages": [{"role": "system", "content": SUMMARY_SYSTEM},
                                                  {"role": "user", "content": TOPICS[lesson]}], "temperature": 0},
                                    1 if parallel else int(lesson) - 6, branch=f"lesson-{lesson}" if parallel else None)
        ended = time.perf_counter()
        spans[lesson] = {"branch": f"lesson-{lesson}", "started_ms": round((started - origin) * 1000),
                         "ended_ms": round((ended - origin) * 1000)}
        return _text(response)

    if parallel:
        with ThreadPoolExecutor(max_workers=len(TOPICS)) as pool:
            futures = {lesson: pool.submit(one, lesson) for lesson in TOPICS}
            outputs = {lesson: future.result() for lesson, future in futures.items()}
    else:
        outputs = {lesson: one(lesson) for lesson in TOPICS}
    wall = round((time.perf_counter() - origin) * 1000)
    branches = [{**spans[lesson], "duration_ms": spans[lesson]["ended_ms"] - spans[lesson]["started_ms"]} for lesson in TOPICS]
    total = sum(item["duration_ms"] for item in branches)
    context.emit("lesson.parallel", {"mode": "parallel" if parallel else "serial", "wall_ms": wall,
                                     "sum_of_branches_ms": total, "branches": branches})
    context.emit("lesson.report", {
        "title": "并行" if parallel else "串行",
        "summary": "墙钟时间与各分支耗时都由服务端 perf_counter 测量；网络和服务商排队会让每次结果不同。",
        "checks": [{"label": "三个子任务都有回答", "passed": all(outputs.values()),
                    "detail": "、".join(f"第 {k} 课" for k, v in outputs.items() if v) or "无"}],
        "metrics": [{"label": "墙钟时间（毫秒）", "value": wall}, {"label": "各分支耗时之和（毫秒）", "value": total},
                    {"label": "模型调用数", "value": len(outputs)},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["分支", "开始（毫秒）", "结束（毫秒）", "耗时（毫秒）", "回答"],
                  "rows": [[b["branch"], b["started_ms"], b["ended_ms"], b["duration_ms"], outputs[lesson]]
                           for lesson, b in zip(TOPICS, branches)]},
    })
    return f"{'并行' if parallel else '串行'}完成：墙钟 {wall} 毫秒，三个分支耗时之和 {total} 毫秒。"


def run(context: RunContext) -> str:
    pattern = Inputs.model_validate(context.inputs).pattern
    context.check_cancelled()
    if pattern == "chain":
        return run_chain(context)
    if pattern == "routing":
        return run_routing(context)
    return run_fanout(context, parallel=pattern == "parallel")
