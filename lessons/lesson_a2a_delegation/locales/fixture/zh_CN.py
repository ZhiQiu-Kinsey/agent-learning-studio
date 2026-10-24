"""a2a-delegation offline test model text: Simplified Chinese (the source language)."""
from lessons.lesson_a2a_delegation.locales.fixture import Texts

TEXTS = Texts(
    claims=("B2 研究证最多能借几册", "周日几点闭馆"),
    answer="资料核对员返回了证据，请按片段原文核对：{lines}",
    claim_line="{claim_id}“{claim}”的依据见 {chunks}",
    superseded="（旧版 {chunks} 已被取代，不采用）",
    line_separator="；",
    not_delegated="这次没能核对（{error_type}）：{error} 所以我不给出答案，请稍后再问。",
)
