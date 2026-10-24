"""Runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_observability_cost.locales import Texts

TEXTS = Texts(
    classify_system=(
        "你在核对差旅报销。把用户给出的一条报销说明归入三类之一：transport（交通）、lodging（住宿）、meals（餐饮）。"
        "只输出一个 JSON 对象，例如 {\"category\": \"transport\"}，不要输出别的文字。"
    ),
    batch_system=(
        "你在核对差旅报销。用户会给出一个 JSON 数组，每一项有 id 和 description。"
        "把每一项归入三类之一：transport（交通）、lodging（住宿）、meals（餐饮）。"
        "只输出一个 JSON 数组，每一项形如 {\"id\": \"r1\", \"category\": \"transport\"}，顺序与输入相同，不要输出别的文字。"
    ),
    receipts={
        "r1": "从机场打车到酒店",
        "r2": "会议期间两晚的酒店房费",
        "r3": "和客户的工作午餐",
        "r4": "从机场打车到酒店",
    },
    unknown_currency="汇率表里没有币种 {currency}。",
    unknown_category="没有类别 {category}，只能是 transport、lodging 或 meals。",
    strategy_names={"baseline": "基线：逐条请求、不缓存", "tool_cache": "只开工具缓存", "batched": "只合并请求"},
    kind_names={"llm": "模型请求", "tool": "工具调用", "cache": "缓存命中"},
    status_names={"ok": "成功", "error": "失败"},
    reason_names={
        "ok": "通过",
        "unparsed": "模型回复无法解析",
        "tool_error": "工具返回错误",
        "wrong_category": "类别与人工标注不一致",
        "wrong_amount": "金额与人工标注不一致",
    },
    mode_offline="离线测试模式",
    mode_live="真实运行",
    value_not_reported="未报告",
    value_not_applicable="—",
    value_none="无",
    value_empty="（空）",
    tokens_partly_reported="{total}（另有 {missing} 次未报告）",
    list_separator="；",
    ledger_title="步骤账本 · {strategy}",
    ledger_summary=(
        "每行是一个跨度：一次模型请求、一次工具调用或一次缓存命中。耗时由运行器在调用前后计时；"
        "用量原样取自响应里的 usage，响应没有给的写“未报告”。步骤号就是事件的轮次，工具行的关联 ID 就是 tool_call 事件的 id。"
    ),
    offline_note="这是离线测试模式：模型回复和用量由测试夹具给出，只用来检查程序，不代表任何服务商。",
    label_mode="运行模式",
    label_model="模型",
    label_model_calls="模型调用数",
    label_tool_calls="工具调用数",
    label_cache_hits="缓存命中次数",
    label_end_to_end="端到端耗时（ms）",
    label_step_sum="各步耗时之和（ms）",
    label_total_tokens="已报告的 Token 合计",
    label_unreported="没有报告用量的模型调用",
    label_quality="题集通过",
    label_cost="估算费用",
    label_note="学习者备注",
    quality_value="{passed}/{total}",
    check_quality="分类和金额与人工标注一致",
    check_quality_detail="{passed}/{total} 条一致。{failures}",
    failure_item="{receipt}：{reason}",
    check_usage="每次模型调用都报告了用量",
    check_usage_all="每个响应都带 usage。",
    check_usage_missing="第 {steps} 步的响应没有 usage，这些调用的 Token 记为未报告，没有计入合计。",
    cost_none="未折算：没有填写价格来源和日期",
    cost_no_usage="无法折算：模型调用都没有报告用量",
    cost_value=(
        "约 {amount} {currency}（估算，不是账单）。模型 {model}；价格来源 {source}，{date}；"
        "覆盖 {covered}/{calls} 次模型调用，没有区分缓存命中的价格。"
    ),
    columns_ledger=("步骤", "类型", "名称", "收据", "关联 ID", "指纹", "耗时 ms", "输入 Token", "输出 Token", "状态", "重复"),
    bottleneck_title="瓶颈：慢步骤与重复调用 · {strategy}",
    bottleneck_summary=(
        "按耗时从高到低排出实际执行的跨度，缓存命中不算执行。指纹相同就是重复：同一个工具、同样的参数，"
        "或一字不差的模型请求体。"
    ),
    label_slowest="最慢的一步",
    label_repeated="重复执行的调用",
    label_extra_ms="重复调用多花的耗时（ms）",
    label_extra_tokens="重复请求多花的 Token",
    slowest_value="第 {step} 步 {name}：{ms} ms，占端到端 {share}",
    repeat_item="{kind} {name} 在第 {steps} 步共执行 {count} 次",
    repeat_cell="与第 {step} 步相同",
    check_no_repeats="没有重复执行的调用",
    check_no_repeats_ok="每个指纹只执行了一次。",
    check_no_repeats_found="有 {count} 组指纹执行了不止一次，见下方表格的“重复”列。",
    columns_bottleneck=("排名", "步骤", "类型", "名称", "耗时 ms", "占端到端", "重复"),
    compare_title="优化前后对照：{baseline} → {strategy}",
    compare_summary="两次运行用同一组 4 条报销和同一份人工标注。先看质量有没有退化，再看省下了什么。",
    row_quality="题集通过",
    row_model_calls="模型调用数",
    row_tool_calls="工具调用数",
    row_end_to_end="端到端耗时（ms）",
    row_tokens="已报告的 Token 合计",
    row_unreported="没有报告用量的模型调用",
    row_repeats="重复执行的调用",
    label_regressions="从通过变成失败",
    label_fixes="从失败变成通过",
    label_token_change="Token 变化",
    label_latency_change="端到端耗时变化（ms）",
    check_no_regression="质量没有退化",
    check_no_regression_ok="同一题集里没有从通过变成失败的条目。",
    check_no_regression_found="从通过变成失败：{items}",
    check_failures="失败条数没有增加",
    check_failures_detail="失败条数 {before} → {after}。",
    columns_compare=("指标", "基线", "优化后", "变化"),
    answer=(
        "按“{strategy}”核对了 {total} 条报销：{passed}/{total} 条与人工标注一致；"
        "{calls} 次模型调用、{tools} 次工具调用、{hits} 次缓存命中，端到端 {ms} ms。"
    ),
    answer_compare="对照“{baseline}”和“{strategy}”：{regressions}",
)
