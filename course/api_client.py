"""负责构造、打印并发送百炼聊天补全请求。"""

import json
import urllib.error
import urllib.request

def call_bailian(messages, tools, api_key, timeout_seconds=60):
    """发送完整请求体；打印请求参数，但不打印认证请求头。"""
    from local_config import API_URL, MODEL

    request_body = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }
    print("\n本次百炼请求体（完整 JSON；不包含认证密钥）：", flush=True)
    print(json.dumps(request_body, ensure_ascii=False, indent=2), flush=True)

    return send_bailian(request_body, api_key, timeout_seconds)


def send_bailian(request_body, api_key, timeout_seconds=60):
    """发送已经记录的请求体；网页和 CLI 使用同一个传输层。"""
    from local_config import API_URL

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(
            "百炼返回 HTTP {}。请求没有自动重发，请先检查配置和余额；"
            "确认原因后再手动重试，避免重复计费。\n{}".format(
                error.code, detail
            )
        ) from None
    except urllib.error.URLError as error:
        raise RuntimeError(
            "连接百炼失败；请求没有自动重发。确认网络和服务状态后再手动重试。\n{}".format(
                error.reason
            )
        ) from None
