"""一次不带工具的模型请求：拼请求体、发出去、从响应里读回答、结束原因和用量。"""
from pydantic import Field

from course.execution import LessonInputs, RunContext

DEFAULT_QUESTION = "用一句话解释什么是 Agent。"
DEFAULT_SYSTEM = "你是编程课的助教。回答简短、具体，不超过两句话。"
# finish_reason 最常见的两个值：模型自己写完是 stop，写到 max_tokens 被截断是 length。
FINISH_REASONS = {"stop": "模型自己写完了", "length": "写到输出上限被截断"}


class Inputs(LessonInputs):
    # 留空表示这次请求不带 system 消息。
    system_prompt: str = Field(default=DEFAULT_SYSTEM, max_length=400)
    # 0 表示请求体里不放 max_tokens，输出上限由服务商决定。
    max_tokens: int = Field(default=0, ge=0, le=1024)


INPUT_MODEL = Inputs


def build_request(question: str, system_prompt: str, max_tokens: int) -> dict:
    """请求体只有本课关心的字段；model 由平台按当前连接补上。"""
    messages = []
    if system_prompt.strip():
        # system 消息写给模型的规则，放在最前面。
        messages.append({"role": "system", "content": system_prompt})
    # user 消息就是这次要问的问题。
    messages.append({"role": "user", "content": question})
    body = {"messages": messages}
    if max_tokens:
        # 输出上限：写到这么多 Token 就停，finish_reason 会是 length。
        body["max_tokens"] = max_tokens
    return body


def read_reply(response: dict) -> dict:
    """从响应里取回答、结束原因和用量；服务商没报告的数记为 None，不当成 0。"""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("模型响应缺少 choices[0]，无法读取回答。")
    message = choices[0].get("message") or {}
    usage = response.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "content": message.get("content") or "",
        # 有的模型先推理再回答：推理写在 reasoning_content 里，不算回答。
        "reasoning": message.get("reasoning_content"),
        "finish_reason": choices[0].get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        # 推理用掉的 Token 也算在 completion_tokens 里，同样受 max_tokens 限制。
        "reasoning_tokens": details.get("reasoning_tokens"),
    }


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    question = context.question.strip() or DEFAULT_QUESTION
    # 1. 拼请求体：只有 messages，按需加 max_tokens。密钥不在这里。
    body = build_request(question, values.system_prompt, values.max_tokens)
    # 2. 发一次请求。request 和 response 两个事件由 context.complete 原样记录。
    response = context.complete(body)
    # 3. 读响应：回答、结束原因、用量。
    reply = read_reply(response)
    _report(context, body, reply)
    return reply["content"] or "（这次响应的 content 为空，请看 finish_reason 和 usage。）"


def _report(context: RunContext, body: dict, reply: dict) -> None:
    """平台：把这次请求的关键字段整理成实验报告。"""
    def shown(value):
        return "未报告" if value is None else value

    reason = reply["finish_reason"]
    metrics = [
        {"label": "system 消息", "value": "有" if body["messages"][0]["role"] == "system" else "无"},
        {"label": "max_tokens", "value": body.get("max_tokens", "未设置")},
        {"label": "回答长度（字符）", "value": len(reply["content"])},
        {"label": "finish_reason", "value": shown(reason)},
        {"label": "结束原因的含义", "value": FINISH_REASONS.get(reason, "未报告" if reason is None else "其他，见服务商文档")},
        {"label": "提示 Token", "value": shown(reply["prompt_tokens"])},
        {"label": "完成 Token", "value": shown(reply["completion_tokens"])},
        {"label": "总 Token", "value": shown(reply["total_tokens"])},
    ]
    if reply["reasoning_tokens"] is not None:
        metrics.append({"label": "其中推理 Token", "value": reply["reasoning_tokens"]})
    if reply["reasoning"] is not None:
        metrics.append({"label": "推理内容（字符）", "value": len(reply["reasoning"])})
    context.emit("lesson.report", {
        "title": "一次请求的关键字段",
        "summary": "数字都来自这次 response 事件里的 usage；服务商没有报告的项写“未报告”。",
        "metrics": metrics,
        "table": {"columns": ["序号", "role", "content"],
                  "rows": [[index, message["role"], message["content"]]
                           for index, message in enumerate(body["messages"])]},
    })
