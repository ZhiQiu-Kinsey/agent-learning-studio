"""messages-context runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_07_messages_context.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "你是课程助教。只根据本次消息回答；缺少依据就说无法确定，不要猜。"
        "回答最后单独写一行“依据：”，说明用到了哪句对话、哪个工具结果。"
    ),
    conversation="这周我只有{day}晚上能复习。先帮我查一下 {student_id} 最近一次练习。",
    question="我那次练习及格了吗？这周哪天复习？",
    weekdays={"mon": "周一", "tue": "周二", "wed": "周三", "thu": "周四", "fri": "周五", "sat": "周六", "sun": "周日"},
    basis_keyword="依据",
    variant_names={
        "full": "完整上下文",
        "no_system": "去掉系统提示词",
        "no_conversation": "去掉之前的对话",
        "no_tool_pair": "去掉工具调用和结果",
        "no_tool_result": "只去掉工具结果",
    },
    unknown_student="没有学号为 {student_id} 的记录。",
    lookup_failed="本地成绩查询失败。",
    protocol_passed="通过",
    protocol_rejected="拒绝：{error}",
    missing_message="模型响应缺少 choices[0].message。",
    no_text_answer="模型没有返回可比较的文本回答。",
    parts_detail=(
        "五条消息都由运行器组装：system、两条 user 是本课写好的样本；带 tool_calls 的 assistant "
        "消息由运行器写入，不是模型提出的；tool 消息的内容是本次真实执行 lookup_score 的返回值。"
    ),
    outcome_not_sent="未发送",
    outcome_provider_rejected="服务商拒绝，见 lesson.provider_error",
    final_answer="{sent} 组请求已发送，{blocked} 组在发送前被协议检查拦下。请对照报告表格和每次 request 的 messages。",
    report_title="一次只拿掉一部分",
    report_summary=(
        "同一问题、同一模型，每组只比完整上下文少一部分。消息数和协议检查由程序算出；"
        "“提到分数”“提到复习日”“写了依据行”是关键词初筛，要对照回答原文复核。"
    ),
    check_protocol="发出的每组请求都先通过了协议检查",
    check_protocol_detail="validate_tool_history 在每次 complete 之前运行。",
    check_blocked="只去掉工具结果的那组被拦下，没有发送",
    check_blocked_none="本次没有组被拦下。",
    label_model_calls="模型调用数",
    label_blocked="被拦下的组",
    label_tool_calls="工具调用数",
    label_student_id="学号",
    label_free_day="能复习的日子",
    label_note="学习者备注",
    note_empty="（空）",
    columns=("上下文", "消息数", "协议检查", "回答", "提到分数", "提到复习日", "写了依据行"),
)
