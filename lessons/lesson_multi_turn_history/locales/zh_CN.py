"""multi-turn-history runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_multi_turn_history.locales import Texts

TEXTS = Texts(
    system_prompt="你是简洁的助手，每次只用一句话回答。",
    turns=(
        "我养了一只猫，名字叫团子，今年三岁。请只回答“记住了”。",
        "我的猫叫什么名字？",
        "它今年几岁？",
    ),
    fact="团子",
    missing_choices="模型响应缺少 choices[0]，无法读取回答。",
    report_title="每轮发出的消息与用量",
    summary_full="每轮都把整段历史重发一遍。数字来自各轮 response 的 usage；没有报告的写“未报告”。",
    summary_latest_only="每轮只发 system 和这一轮的问题。数字来自各轮 response 的 usage；没有报告的写“未报告”。",
    check_fact_sent="第二轮请求里有第一轮说的事实",
    check_fact_sent_detail="逐条检查第二轮实际发出的 messages 里有没有“{fact}”。",
    check_fact_answered="第二轮回答提到了这个事实",
    check_fact_answered_detail="检查第二轮 response 的 content，只说明这一次的回答。",
    label_mode="模式",
    mode_values={"full": "整段历史", "latest_only": "只发本轮问题"},
    label_model_calls="模型调用数",
    label_last_message_count="最后一轮发出的消息数",
    label_prompt_growth="提示 Token 从第一轮到最后一轮",
    prompt_growth="{first} → {last}",
    label_note="学习者备注",
    columns=("轮", "发出的消息数", "包含事实", "提示 Token", "完成 Token", "回答"),
    value_yes="是",
    value_no="否",
    value_not_reported="未报告",
    value_empty="（空）",
)
