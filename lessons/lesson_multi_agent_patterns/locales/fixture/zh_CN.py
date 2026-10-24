"""multi-agent-patterns offline script text: Chinese (source language)."""
from lessons.lesson_multi_agent_patterns.locales.fixture import Texts

TEXTS = Texts(
    questions={
        "fallback_label": "路由时，回复第一行不是可选标签，工单走哪个兜底标签？",
        "worker_cap": "编排者最多能拆出几个子任务？",
        "max_iters": "修订循环的迭代上限 max_iters 最大是几？",
    },
    quotes={
        "d1": "回复第一行不在可选标签里，就走兜底标签 other",
        "d2": "子任务最多 4 个，超出就整份不用",
        "d3": "迭代上限 max_iters 最大为 3",
        "d4": "编排者最多拆出 6 个子任务",
    },
)
