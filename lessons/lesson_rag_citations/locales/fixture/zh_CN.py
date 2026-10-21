"""rag-citations offline script text: Chinese (source language)."""
from lessons.lesson_rag_citations.locales.fixture import Texts

TEXTS = Texts(
    claims={
        "fee_cap": "每册资料的逾期费用累计最高 20 元。",
        "fee_daily": "逾期按每册每天 0.5 元计算。",
        "sunday": "周日 9:00–18:00 开放，18:00 闭馆。",
        "b2_limit": "B2 研究证最多能借 15 册。",
        "pickup": "预留的书到馆后会在取书架上保留 5 个开放日。",
    },
    quotes={
        "fee_cap": "每册资料的逾期费用累计最高 20 元。",
        "fee_daily": "每册每天收取 0.5 元逾期费用",
        "sunday": "周六、周日 9:00–18:00 开放。",
        "sunday_old": "周日 10:00–17:00 开放",
        "b2_limit": "B2 研究证：最多 15 册",
        "pickup": "书会在一楼服务台旁的取书架上保留 5 个开放日",
    },
    conflict_topic="周日开放时间",
    conflict_resolution="hours（2026-03）声明取代 hours-2025（2025-01），以 2026 版为准。",
    missing="提供的片段里没有能回答这个问题的内容。",
    error_notes={
        "q01": "离线夹具故意编造了一个本次没有提供的片段 ID，不是模型的输出。",
        "q10": "离线夹具故意把摘录和结论里的 5 改成了 7，不是模型的输出。",
    },
    quote_edit=("5 个开放日", "7 个开放日"),
)
