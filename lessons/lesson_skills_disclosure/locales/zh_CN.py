"""skills-disclosure runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_skills_disclosure.locales import Texts

TEXTS = Texts(
    vague_description="帮助学习。",
    task_messages={
        "make_cards": (
            "把下面这段学习笔记整理成复习卡：\n"
            "Python 的列表可以修改，元组创建后不能修改。字典按键取值，键必须是不可变类型，"
            "所以元组可以当键，列表不行。集合会自动去重，但不保证元素顺序；"
            "判断一个元素在不在集合里，通常比在列表里查找快得多。"
        ),
        "chat": "你好！今天周五，跟我打个招呼吧。",
        "review_question": "帮我复习一下：Python 的列表和元组有什么区别？一两句话说清楚就行。",
    },
    full_prompt=(
        "你是学习助手。下面是你会的全部技能，每个都附有完整做法。"
        "用户的任务符合某个技能的描述时，严格按它的做法完成；都不符合时直接正常回答，不要套用技能。"
    ),
    catalog_prompt=(
        "你是学习助手。下面的技能目录只列出每个技能的名字和描述。"
        "用户的任务符合某个技能的描述时，先调用 load_skill 读取它的完整做法，再按做法完成；"
        "都不符合时直接正常回答，不要加载技能。"
    ),
    full_section="## 技能 {name}\n描述：{description}\n\n{body}",
    catalog_heading="技能目录：",
    catalog_line="- {name}：{description}",
    load_skill_description="读取一个技能的完整做法。name 必须是技能目录里列出的名字。",
    load_skill_name_description="技能目录里的名字",
    unknown_skill="没有名为 {name} 的技能；技能目录里只有：{names}。",
    loading_not_applicable="不适用：全部正文常驻",
    loading_none_correct="正确：没有加载",
    loading_missed="漏触发：该加载却没加载",
    loading_false="误触发：加载了 {names}",
    loading_correct="正确：加载了 {names}",
    loading_wrong="加载错技能：{names}",
    card_question_prefixes=("问：", "问:"),
    card_answer_prefixes=("答：", "答:"),
    format_no_answer="没有回答",
    format_cards="{asked} 个“问：”、{answered} 个“答：”，技能要求 3–5 张卡",
    format_not_cards="没有写成复习卡",
    format_cards_written="写成了 {asked} 张复习卡",
    mode_labels={"full": "全量注入", "on_demand": "目录 + 按需加载"},
    task_labels={"make_cards": "整理复习卡", "chat": "闲聊", "review_question": "复习提问"},
    answer_section="【{mode}】\n{answer}",
    no_answer="{limit} 次请求内没有得到回答。",
    unparsable_arguments="（参数无法解析）",
    value_not_reported="未报告",
    tokens_partly_reported="{total}（{missing} 次未报告）",
    value_empty="（空）",
    separator="、",
    label_task="任务",
    label_description="review-cards 的描述",
    value_vague="模糊",
    value_precise="精确",
    label_expected="本课认定该用的技能",
    value_expect_none="不该加载任何技能",
    proposals="第 {round} 次请求提出 {names}",
    proposals_separator="；",
    value_all_resident="全部常驻",
    value_no_proposal="没有提出加载",
    format_passed="通过：",
    format_failed="未通过：",
    label_first_tokens="第 1 次请求的提示 Token（{mode}）",
    check_full_bodies="全量注入：请求里带着全部技能正文",
    check_full_bodies_detail="在实际发出的消息里找到 {count} 个技能的正文。",
    check_catalog_only="按需加载：第 1 次请求里没有任何技能正文",
    check_catalog_only_detail="第 1 次请求的系统提示词 {chars} 个字符，只含目录。",
    check_loading="按需加载：加载判定",
    check_rejected="未登记的技能名被拒绝",
    check_rejected_detail="{names} 不在白名单里，工具结果是结构化错误。",
    check_format="{mode}：回答格式初筛",
    check_format_detail="{detail}。只看格式，不代表内容正确。",
    label_model_calls="模型调用数",
    label_note="学习者备注",
    title_separator=" 与 ",
    report_title="{modes}：{task}",
    report_summary=(
        "提示 Token 来自每次响应的 usage，没有报告的写“未报告”；加载判定只看 load_skill 的工具结果，"
        "格式初筛只看回答像不像复习卡。"
    ),
    columns=("方式", "模型调用数", "每次提示 Token", "提示 Token 合计", "加载记录", "加载判定", "格式初筛"),
)
