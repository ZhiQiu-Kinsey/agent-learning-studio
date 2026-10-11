"""prompt-caching runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_prompt_caching.locales import Texts

TEXTS = Texts(
    rules="你是青石社区图书馆的咨询助手。只根据下面的手册回答，用一两句话；手册没有写的，就说手册没有写。",
    questions=(
        "普通读者证一次最多能借几册书？借期多长？",
        "图书逾期归还，每天收多少滞纳金？有没有上限？",
        "几岁以下的儿童进少儿阅览室必须有家属陪同？",
        "哪些图书不接受捐赠？",
        "志愿者临时不能到岗，最晚什么时候通知谁？",
    ),
    warmup_question="这是一次预热请求，不用回答问题，只回复“已读”。",
    dynamic_line="请求序号：{number}；发送时间：{sent_at}",
    question_with_dynamic="{question}\n（{dynamic}）",
    session_tag="会话标记：{session}",
    not_isolated="不隔离",
    purpose_warmup="预热",
    purpose_measure="测量",
    layout_names={"dynamic_first": "动态内容在前", "stable_prefix": "稳定前缀", "warmup": "稳定前缀 + 预热"},
    answer=(
        "已连续发送 {count} 次请求（{layout}）。逐次的前缀哈希、缓存命中 Token "
        "和耗时见实验报告；命中数以每次 response 的用量字段为准。"
    ),
    value_not_reported="未报告",
    value_empty="（空）",
    list_separator="、",
    check_hash="各次请求的前缀哈希相同",
    check_hash_detail="{count} 次请求共出现 {distinct} 个不同的前缀哈希{suffix}",
    check_hash_detail_one="{count} 次请求只出现了 1 个前缀哈希{suffix}",
    hash_suffix_warmup="（预热请求也算在内）。",
    hash_suffix_plain="。",
    check_reported="每次响应都报告了缓存字段",
    check_reported_all="全部报告。",
    check_reported_missing="第 {rounds} 次没有报告，表中写“未报告”，没有记成 0。",
    check_explained="报告命中的请求，前缀都在本次运行里发过",
    check_explained_all="命中都出现在前缀重复的请求上。",
    unexplained_item="第 {round} 次（命中 {cached}）",
    check_explained_detail=(
        "{items}的前缀在本次运行里第一次出现：命中来自本次运行之前的缓存，或服务商按更短的前缀命中。"
    ),
    report_title="提示缓存对照：{layout}",
    report_summary=(
        "规则、手册和问题与另外两组相同，只改动态那一行的位置。前缀哈希由运行器在本地计算；缓存命中 Token 取自"
        "响应的用量字段，没有报告的写“未报告”。耗时是运行器在 complete 前后计时，比 response 事件的 "
        "duration_ms 多出记录事件的几毫秒。"
    ),
    report_summary_offline="离线测试模式下的 Token 数与命中数由夹具按前缀是否重复生成，不代表任何服务商。",
    label_mode="运行模式",
    value_mode_offline="离线测试（数字来自夹具）",
    value_mode_live="真实模型",
    label_layout="请求结构",
    label_model_calls="模型调用数",
    label_reported="报告缓存字段的请求",
    label_hits="测量请求中报告命中的次数",
    label_ratio="测量请求合计命中比例",
    label_fields="缓存字段",
    label_session="会话标记",
    label_note="学习者备注",
    columns=("次序", "用途", "前缀哈希", "与上一次相同的前缀（字符）", "输入 Token", "缓存命中 Token",
             "命中比例", "耗时（毫秒）"),
)
