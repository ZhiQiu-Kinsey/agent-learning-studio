"""Platform runtime text: Simplified Chinese (the source language)."""
from course.locales import Texts

TEXTS = Texts(
    tool_arguments_not_object="工具参数必须是 JSON 对象。",
    unknown_tool="不认识这个工具：{name}",
    rounds_exceeded="工具调用超过 {rounds} 轮，为避免无限循环已停止。",
    run_cancelled="已停止后续步骤。",
    model_budget_exceeded="本课模型请求超过 {limit} 次，已停止后续调用。",
    stage_result_title="原生子流程结果",
    bailian_http_error=(
        "百炼返回 HTTP {status}。请求没有自动重发，请先检查配置和余额；"
        "确认原因后再手动重试，避免重复计费。\n{detail}"
    ),
    bailian_unreachable="连接百炼失败；请求没有自动重发。确认网络和服务状态后再手动重试。\n{reason}",
    provider_not_configured="请先配置所选服务商的模型与服务地址。",
    provider_key_missing="请先配置所选服务商的 API Key。",
    embedding_not_configured=(
        "所选服务商还没有可用的 Embedding 模型配置。本课需要 Embedding 请求，平台不会改用别的模型；"
        "请在模型设置里填写 Embedding 模型，或按文档设置对应的环境变量后再运行。"
    ),
    embedding_response_invalid="Embedding 响应里的向量数量（{actual}）与输入条数（{expected}）不一致，已停止。",
    stream_interrupted="流式响应中途断开，已收到的分块已经记录；请求没有自动重发。\n{reason}",
    stream_provider_error="服务商在流式响应中返回了错误，已收到的分块已经记录：{detail}",
    cli_model="当前模型：{model}",
    cli_examples="可尝试：",
    cli_prompt="\n你：",
    cli_no_question="没有收到问题，已退出。",
    cli_checking_key="\n正在检查进程环境变量 DASHSCOPE_API_KEY……",
    cli_key_not_in_env="当前 Python 进程没有读到 DASHSCOPE_API_KEY。你可以在接下来的隐藏输入中提供 API Key。",
    cli_key_prompt="请输入与本地百炼配置对应地域的 API Key（输入时不会显示）：",
    cli_key_from_env="已从进程环境变量读取到 API Key（不会显示其内容）。",
    cli_no_key="没有提供 API Key，已退出。",
    cli_key_ready="Key 已就绪；请求日志不会包含认证密钥。",
    cli_request_body="\n第 {round} 轮：完整 HTTP 请求体（不包含认证请求头）",
    cli_waiting="正在等待响应，网络超时为 60 秒……",
    cli_tool_request="\n模型请求工具：{name}({arguments})",
    cli_tool_result="Python 执行结果：{result}",
    cli_answer="\nAgent 回答：\n{answer}",
    cli_failed="\n运行失败：{error}",
)
