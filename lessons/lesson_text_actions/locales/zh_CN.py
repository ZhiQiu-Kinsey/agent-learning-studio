"""text-actions runtime text: Chinese (source language)."""
from lessons.lesson_text_actions.locales import Texts

TEXTS = Texts(
    text_system="""你是学习助教，可以使用下面的工具：
lookup_quiz_score：查询学生最近一次练习的得分、尝试次数和更新日期。输入 JSON：{"student_id": "学号"}

每次只写一步，严格按这个格式：
Thought: 你的思考
Action: 工具名
Action Input: JSON 参数

写完 Action Input 就停下，等系统给你 Observation。拿到 Observation 后，如果已经能回答，写：
Thought: 你的思考
Final Answer: 给用户的回答""",
    native_system="你是学习助教。需要学生成绩时调用 lookup_quiz_score，不要猜测数据。",
    question="学号 {student_id} 最近一次练习得了多少分？及格线是 {pass_line} 分，他及格了吗？",
    tool_description="查询学生最近一次练习的得分、尝试次数和更新日期。",
    tool_student_id="学号，如 s-1042",
    unknown_student="没有学号为 {student_id} 的记录。",
    invalid_json="Action Input 不是合法 JSON：{error}",
    not_an_object="Action Input 必须是 JSON 对象",
    no_action="既没有 Action，也没有 Final Answer",
    value_not_reported="未报告",
    row_tool_calls="{count} 个 tool_calls",
    row_text_answer="文本回答",
    text_parse_failed="文本协议没有得到最终回答：解析失败，已停止。",
    text_no_final="文本协议没有得到最终回答：{limit} 步内没有 Final Answer。",
    native_no_answer="原生调用在 {limit} 步内没有得到最终回答。",
    text_report_title_stop="文本动作协议（带 stop）",
    text_report_title_no_stop="文本动作协议（不带 stop）",
    text_report_summary="每次模型输出都经过解析并记成 lesson.parse；解析失败就停止，不猜测修复。工具由程序按解析结果执行，模型自己写的 Observation 不进入上下文。",
    check_not_leaked="模型自写的 Observation 没有进入后续上下文",
    detail_fabricated="本次模型自己写了 {count} 段 Observation。",
    check_final_answer="得到了 Final Answer",
    detail_no_final="达到步数上限或解析失败时没有最终回答。",
    detail_final_after_observation="最终回答来自模型看到真实 Observation 之后的输出。",
    native_report_title="原生工具调用",
    native_report_summary="动作由服务商在 tool_calls 字段里结构化返回，程序不解析自由文本。",
    check_native_answer="得到了最终回答",
    detail_native_answer="最终回答来自模型看到 tool 消息之后的输出。",
    detail_native_unfinished="{limit} 步内没有结束。",
    label_protocol="协议",
    label_model_calls="模型调用数",
    label_parse_failures="解析失败",
    label_fabricated="模型自写 Observation",
    label_student="学号",
    label_note="学习者备注",
    value_empty_note="（空）",
    text_columns=("步", "finish_reason", "解析结果", "错误"),
    native_columns=("步", "finish_reason", "模型输出"),
)
