"""连续发送同类请求，对照三种请求结构下服务商报告的缓存命中。

三组的规则、手册和问题完全相同，只改“动态内容”那一行放在哪里，以及要不要先发一次预热请求。
命中多少只看响应里的缓存字段；前缀是否逐字相同由运行器在本地用哈希核对。
"""
import hashlib
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_prompt_caching.cache_usage import hit_ratio, normalize_cache_usage


class Inputs(LessonInputs):
    layout: Literal["dynamic_first", "stable_prefix", "warmup"] = "stable_prefix"
    repeats: int = Field(default=4, ge=3, le=5)
    isolate_run: bool = True


INPUT_MODEL = Inputs
HANDBOOK = Path(__file__).with_name("handbook.md").read_text(encoding="utf-8")
RULES = "你是青石社区图书馆的咨询助手。只根据下面的手册回答，用一两句话；手册没有写的，就说手册没有写。"
QUESTIONS = (
    "普通读者证一次最多能借几册书？借期多长？",
    "图书逾期归还，每天收多少滞纳金？有没有上限？",
    "几岁以下的儿童进少儿阅览室必须有家属陪同？",
    "哪些图书不接受捐赠？",
    "志愿者临时不能到岗，最晚什么时候通知谁？",
)
WARMUP_QUESTION = "这是一次预热请求，不用回答问题，只回复“已读”。"
LAYOUT_NAMES = {"dynamic_first": "动态内容在前", "stable_prefix": "稳定前缀", "warmup": "稳定前缀 + 预热"}


def dynamic_line(number: int) -> str:
    """每次请求都不同的一行：请求序号和发送时间。"""
    return f"请求序号：{number}；发送时间：{datetime.now().astimezone().isoformat(timespec='seconds')}"


def build_messages(layout: str, session: str, question: str, dynamic: str) -> list[dict]:
    """三组用完全相同的规则、手册和问题，只改动态那一行的位置。"""
    stable = f"会话标记：{session}\n{RULES}\n\n{HANDBOOK}"
    if layout == "dynamic_first":
        # 动态行写在系统提示词第一行：比到请求序号就不一样了，后面的手册再相同也用不上。
        return [{"role": "system", "content": f"{dynamic}\n{stable}"},
                {"role": "user", "content": question}]
    # 动态行挪到最后一条 user 消息末尾：规则和手册成为每次逐字相同的开头。
    return [{"role": "system", "content": stable},
            {"role": "user", "content": f"{question}\n（{dynamic}）"}]


def _serialize(messages: list[dict]) -> str:
    return json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prefix_hash(messages: list[dict]) -> str:
    """最后一条消息之前的全部消息（本课就是 system）序列化后取 sha256 前 12 位。"""
    return hashlib.sha256(_serialize(messages[:-1]).encode("utf-8")).hexdigest()[:12]


def shared_prefix_chars(previous: list[dict] | None, current: list[dict]) -> int | None:
    """和上一次请求从头逐字比较，到第一个不同的字符为止共有多少字符；第一次请求没有比较对象。"""
    if previous is None:
        return None
    return len(os.path.commonprefix([_serialize(previous), _serialize(current)]))


def event_kind(cache: dict) -> str:
    """三种结果分成三种事件：报告命中、报告为 0、没有报告。"""
    if cache["cached_tokens"] is None:
        return "lesson.cache_unreported"
    return "lesson.cache_hit" if cache["cached_tokens"] > 0 else "lesson.cache_miss"


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    # 会话标记在一次运行内不变，不破坏前缀；每次运行换一个，上一次运行留下的缓存就用不上。
    session = secrets.token_hex(4) if values.isolate_run else "不隔离"
    plan = (["预热"] if values.layout == "warmup" else []) + ["测量"] * values.repeats
    questions = iter(QUESTIONS)
    records, previous = [], None
    for number, purpose in enumerate(plan, 1):
        context.check_cancelled()
        # 1. 组装：规则、手册、问题都是固定的，只有动态行每次不同。
        question = WARMUP_QUESTION if purpose == "预热" else next(questions)
        messages = build_messages(values.layout, session, question, dynamic_line(number))
        # 2. 发送前先在本地记下前缀指纹，和上一次请求比较。
        record = {"round": number, "purpose": purpose, "prefix_hash": prefix_hash(messages),
                  "shared_prefix_chars": shared_prefix_chars(previous, messages)}
        # 3. 发请求；回答只要一两句，限制输出长度，减少生成回答对耗时的影响。
        started = time.perf_counter()
        response = context.complete({"messages": messages, "temperature": 0, "max_tokens": 200},
                                    round_number=number)
        record["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        # 4. 读服务商报告的缓存字段：没有报告就是 None，不当成 0。
        cache = normalize_cache_usage(response.get("usage"))
        record.update(cache, ratio=hit_ratio(cache))
        context.emit(event_kind(cache), record, number)
        records.append(record)
        previous = messages
    _report(context, values, session, records)
    return (f"已连续发送 {len(records)} 次请求（{LAYOUT_NAMES[values.layout]}）。逐次的前缀哈希、缓存命中 Token "
            "和耗时见实验报告；命中数以每次 response 的用量字段为准。")


def _cells(record: dict) -> list:
    ratio = record["ratio"]
    return [record["round"], record["purpose"], record["prefix_hash"],
            "—" if record["shared_prefix_chars"] is None else record["shared_prefix_chars"],
            "未报告" if record["input_tokens"] is None else record["input_tokens"],
            "未报告" if record["cached_tokens"] is None else record["cached_tokens"],
            ("未报告" if record["cached_tokens"] is None else "—") if ratio is None else f"{ratio:.1%}",
            record["elapsed_ms"]]


def _report(context: RunContext, values: Inputs, session: str, records: list[dict]) -> None:
    """平台：把逐次记录整理成实验报告；每一项都能在对应的事件里核对。"""
    measured = [record for record in records if record["purpose"] == "测量"]
    reported = [record for record in records if record["cached_tokens"] is not None]
    hashes = {record["prefix_hash"] for record in records}
    missing = [str(record["round"]) for record in records if record["cached_tokens"] is None]
    checks = [
        {"label": "各次请求的前缀哈希相同", "passed": len(hashes) == 1,
         "detail": f"{len(records)} 次请求共出现 {len(hashes)} 个不同的前缀哈希"
                   + ("（预热请求也算在内）。" if values.layout == "warmup" else "。")},
        {"label": "每次响应都报告了缓存字段", "passed": not missing,
         "detail": "全部报告。" if not missing else
         f"第 {'、'.join(missing)} 次没有报告，表中写“未报告”，没有记成 0。"},
    ]
    if reported:
        seen, unexplained = set(), []
        for record in records:
            if record["cached_tokens"] and record["prefix_hash"] not in seen:
                unexplained.append(f"第 {record['round']} 次（命中 {record['cached_tokens']}）")
            seen.add(record["prefix_hash"])
        checks.append({
            "label": "报告命中的请求，前缀都在本次运行里发过", "passed": not unexplained,
            "detail": "命中都出现在前缀重复的请求上。" if not unexplained else
            "、".join(unexplained) + "的前缀在本次运行里第一次出现：命中来自本次运行之前的缓存，或服务商按更短的前缀命中。"})
    known = [record for record in measured if record["cached_tokens"] is not None and record["input_tokens"]]
    total_ratio = (f"{sum(r['cached_tokens'] for r in known) / sum(r['input_tokens'] for r in known):.1%}"
                   if known else "未报告")
    hits = (sum(1 for record in measured if record["cached_tokens"]) if any(
        record["cached_tokens"] is not None for record in measured) else "未报告")
    fields = sorted({record["field"] for record in reported})
    offline = context.mode == "offline"
    context.emit("lesson.report", {
        "title": f"提示缓存对照：{LAYOUT_NAMES[values.layout]}",
        "summary": ("规则、手册和问题与另外两组相同，只改动态那一行的位置。前缀哈希由运行器在本地计算；缓存命中 Token 取自"
                    "响应的用量字段，没有报告的写“未报告”。耗时是运行器在 complete 前后计时，比 response 事件的 "
                    "duration_ms 多出记录事件的几毫秒。")
                   + ("离线测试模式下的 Token 数与命中数由夹具按前缀是否重复生成，不代表任何服务商。" if offline else ""),
        "checks": checks,
        "metrics": [
            {"label": "运行模式", "value": "离线测试（数字来自夹具）" if offline else "真实模型"},
            {"label": "请求结构", "value": LAYOUT_NAMES[values.layout]},
            {"label": "模型调用数", "value": len(records)},
            {"label": "报告缓存字段的请求", "value": f"{len(reported)} / {len(records)}"},
            {"label": "测量请求中报告命中的次数", "value": hits},
            {"label": "测量请求合计命中比例", "value": total_ratio},
            {"label": "缓存字段", "value": "、".join(fields) or "未报告"},
            {"label": "会话标记", "value": session},
            {"label": "学习者备注", "value": context.question or "（空）"},
        ],
        "table": {
            "columns": ["次序", "用途", "前缀哈希", "与上一次相同的前缀（字符）", "输入 Token", "缓存命中 Token",
                        "命中比例", "耗时（毫秒）"],
            "rows": [_cells(record) for record in records],
        },
    })
