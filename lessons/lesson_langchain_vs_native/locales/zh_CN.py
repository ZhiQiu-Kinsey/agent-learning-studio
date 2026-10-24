"""langchain-vs-native runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_langchain_vs_native.locales import Texts

TEXTS = Texts(
    absent="（无此字段）",
    none="无",
    list_separator="、",
    outcome_ok="ok：{result}",
    outcome_error="{error_type}：{error}",
    stop_reasons={"answered": "模型给出回答", "rounds": "用完轮数上限，没有回答"},
    verdicts=("未通过", "通过"),
    report_task_title={"sum": "同一任务两种实现：加法", "divide": "同一任务两种实现：除数为零"},
    report_task_summary=(
        "两种实现用同一个问题、系统提示词、工具函数、轮数上限和验收规则，先跑原生循环，再跑 LangChain。"
        "表里的数字来自这次运行的请求体和工具结果。"
    ),
    acceptance_rules={
        "sum": "add_numbers 返回 ok=true，且最终回答里出现这个和。",
        "divide": "divide_numbers 全部返回 ok=false，且这条失败被写进了下一次请求的 tool 消息。",
    },
    check_native_accepted="原生循环通过验收",
    check_langchain_accepted="LangChain 通过验收",
    check_same_tools="两边登记的工具名相同",
    check_same_tools_detail="比较两边第一次请求里 tools 的名字和顺序；工具函数是同一份 Python 代码。",
    label_native_calls="原生循环的模型调用数",
    label_langchain_calls="LangChain 的模型调用数",
    label_native_rounds="原生循环的轮次",
    label_langchain_rounds="LangChain 的轮次",
    label_framework_version="langchain-core 版本",
    columns_responsibility=("环节", "原生循环（自己写）", "LangChain（框架或适配层做）"),
    row_messages="消息",
    cell_native_messages="字典，role 依次为 {kinds}",
    cell_langchain_messages="消息对象，type 依次为 {kinds}",
    row_tools="工具定义",
    cell_native_tools="手写 JSON，参数带描述 {count} 个",
    cell_langchain_tools="@tool 从类型注解生成，参数带描述 {count} 个",
    row_parsing="调用解析",
    cell_native_parsing="arguments 原样保留，执行时 json.loads；调用提议 {count} 个",
    cell_langchain_parsing="解析进 AIMessage：tool_calls {valid} 个，invalid_tool_calls {invalid} 个",
    row_feedback="结果回填",
    cell_native_feedback="自己拼 role=tool 消息 {count} 条",
    cell_langchain_feedback="execute_tool_calls 返回 ToolMessage {count} 条",
    row_stop="停止条件",
    cell_stop="没有调用提议就停，最多 {limit} 轮：{stop}",
    row_errors="失败的工具结果",
    cell_errors="{count} 条，都以结构化错误回填",
    row_acceptance="验收（同一个函数）",
    report_diff_title="请求体逐字段对照",
    report_diff_summary=(
        "按调用顺序把两边的请求体配对，列出值不同或只有一边有的字段。"
        "原生一侧是原生循环交给 complete 的请求体；LangChain 一侧是适配层由框架消息转换出的请求体，"
        "转换前的框架输入见 lesson.framework_input。工具定义每次请求都相同，只在第 1 对列出，后面几对只列消息里的差异。"
    ),
    label_diff_count="第 {n} 对请求的不同字段数",
    request_pair="第 {n} 对",
    columns_diff=("请求", "字段", "原生循环", "LangChain"),
    answer_task="原生循环：{native}\nLangChain：{langchain}",
    report_arguments_title="同一组实参，三种工具入口",
    report_arguments_summary=(
        "本练习不调用模型。运行器把同一段 arguments 原样提交给三个入口：原生 add_numbers、"
        "默认 @tool（从 a: float, b: float 推断参数 schema）、严格 schema（StrictNumbers）。"
        "三个入口最后调用的是同一个 Python 函数。"
    ),
    check_default_agrees="默认 @tool 的结论与原生一致",
    check_strict_agrees="严格 schema 的结论与原生一致",
    agree_detail="{ok}/{total} 组一致（都成功或都失败）",
    label_masked="原生拒绝、默认 @tool 却放过的组数",
    label_masked_cases="被放过的实参",
    argument_cases={"valid": "合法数字", "string": "数字写成字符串", "boolean": "布尔值", "extra": "多一个参数"},
    columns_arguments=("实参", "arguments 原文", "原生 add_numbers", "默认 @tool", "严格 schema"),
    answer_arguments=(
        "本组没有调用模型。{total} 组实参里，原生工具拒绝、默认 @tool 却执行成功的有 {masked} 组；"
        "严格 schema 与原生结论一致的有 {strict} 组。"
    ),
    sample_note="运行器构造的服务商响应样本，不是模型输出；用来演示框架怎样解析调用提议。",
    report_parsing_title="框架怎样解析一条坏掉的调用提议",
    report_parsing_summary=(
        "本练习不调用模型。运行器构造一条含三个调用的服务商响应：参数被截断、参数是数组、缺调用 id。"
        "原生循环把这条 assistant 消息原样放回消息历史；框架先解析成 AIMessage，再转换回请求格式。"
    ),
    check_all_answered="每个调用都有工具结果",
    answered_detail="{answered}/{total} 个调用得到了工具结果",
    check_same_order="回填顺序与服务商发来的顺序一致",
    order_detail="服务商：{provider}；框架：{framework}",
    label_valid_calls="tool_calls（解析成功）",
    label_invalid_calls="invalid_tool_calls（解析失败）",
    label_synthesized="适配层补的调用 id",
    place_valid="tool_calls",
    place_invalid="invalid_tool_calls",
    columns_parsing=("序号", "服务商给的 id", "服务商给的 arguments", "AIMessage 里的去向", "回填用的 id",
                     "回填的 arguments", "工具结果"),
    answer_parsing=(
        "本组没有调用模型。框架把样本解析成 {valid} 个有效调用、{invalid} 个无效调用，"
        "补了 {synthesized} 个调用 id；每个调用都按回填的 id 得到了工具结果。"
    ),
)
