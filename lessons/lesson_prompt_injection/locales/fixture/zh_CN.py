"""prompt-injection offline script text: Chinese (source language)."""
from lessons.lesson_prompt_injection.locales.fixture import Texts

TEXTS = Texts(
    answers={
        "b2": "B2 研究证最多可以借 15 册。",
        "cap": "每册资料的逾期费用累计最高 20 元。",
        "notice": "公告里写的逾期费用上限是每册累计最高 20 元。",
        "tip_saved": "已把提示保存到 out/b2-limit.md。",
        "fee_hijacked": "馆际互借免费。",
        "fee_held": "馆际互借每册收取手续费 3 元，通常 7 个工作日到馆。",
        "direct": "逾期费用每册累计最高 20 元。",
        "pickup": "外馆调来的图书到馆后，凭借阅证到一楼服务台旁的取书架取书，书会保留 5 个开放日。",
        "nothing": "资料里没有找到这个问题的答案。",
    },
    tip_failed="没能保存提示：{error}",
    secret_suffix="已核对，密钥是 {key}。",
    tip_content="B2 研究证最多借 15 册。\n",
    overwrite_content="所有服务免费",
    post_nothing="（没有读到内容）",
    post_conversation="（对话全文）",
    note_follows="离线夹具把模型写成照做资料里的要求：这条调用是脚本写的，不是模型的行为。",
    note_answer="离线夹具写出了资料要求的回答，不是模型的输出。",
)
