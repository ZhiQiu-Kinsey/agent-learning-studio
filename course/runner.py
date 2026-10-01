"""复用的工具分发、agent 循环和命令行启动逻辑。"""

import getpass
import json
import os
import sys
import copy
import time

from course.api_client import send_bailian


def execute_tool(tool_call, available_tools, quiet=False):
    """只运行课程显式登记的工具，并把失败转换成可回传结果。"""
    name = tool_call["function"]["name"]
    raw_arguments = tool_call["function"].get("arguments", "{}")
    if not quiet:
        print("\n模型请求工具：{}({})".format(name, raw_arguments))

    try:
        arguments = json.loads(raw_arguments)
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是 JSON 对象。")

        function = available_tools.get(name)
        if function is None:
            raise ValueError("不认识这个工具：{}".format(name))

        result = function(**arguments)
        if not quiet:
            print("Python 执行结果：{}".format(json.dumps(result, ensure_ascii=False)))
        return {"ok": True, "result": result}
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        if not quiet:
            print("工具执行失败：{}".format(error))
        return {
            "ok": False,
            "error_type": type(error).__name__,
            "error": str(error),
        }


class RunCancelled(RuntimeError):
    """停止后续步骤；已经发出的 HTTP 请求仍受网络超时约束。"""


def run_agent(question, api_key, system_prompt, tools, available_tools, max_tool_rounds,
              *, completion=None, model=None, emit=None, cancelled=None, quiet=False,
              representation="http_body"):
    """运行工具调用循环，直到模型回答或达到最大轮数。"""
    if model is None:
        from local_config import MODEL
        model = MODEL
    completion = completion or send_bailian

    def event(kind, data, round_number):
        if emit:
            emit(kind, copy.deepcopy(data), round_number)

    def check_cancelled():
        if cancelled and cancelled():
            raise RunCancelled("已停止后续调用。")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    for round_number in range(1, max_tool_rounds + 1):
        check_cancelled()
        body = copy.deepcopy({"model": model, "messages": messages,
                              "tools": tools, "tool_choice": "auto"})
        event("request", {"body": body, "representation": representation}, round_number)
        if not quiet:
            title = "完整 HTTP 请求体" if representation == "http_body" else "SDK 标准化输入"
            print("\n第 {} 轮：{}（不包含认证请求头）".format(round_number, title), flush=True)
            print(json.dumps(body, ensure_ascii=False, indent=2), flush=True)
            print("正在等待响应，网络超时为 60 秒……", flush=True)
        started = time.perf_counter()
        response = completion(body, api_key)
        event("response", {"body": response, "representation": representation,
                           "duration_ms": round((time.perf_counter()-started)*1000)}, round_number)
        check_cancelled()
        assistant_message = response["choices"][0]["message"]
        tool_calls = assistant_message.get("tool_calls") or []

        if not tool_calls:
            answer = assistant_message.get("content") or ""
            event("answer", {"content": answer}, round_number)
            if not quiet:
                print("\nAgent 回答：\n{}".format(answer))
            return answer

        # 保留模型的工具调用消息，服务端需要 tool_call_id 匹配工具结果。
        messages.append(assistant_message)
        for tool_call in tool_calls:
            check_cancelled()
            event("tool_call", tool_call, round_number)
            result = execute_tool(tool_call, available_tools, quiet=quiet)
            event("tool_result", {"tool_call_id": tool_call["id"],
                                  "name": tool_call["function"]["name"], "result": result}, round_number)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError(
        "工具调用超过 {} 轮，为避免无限循环已停止。".format(max_tool_rounds)
    )


def run_cli(title, examples, system_prompt, tools, available_tools, max_tool_rounds):
    """统一处理密钥输入、问题输入和 lesson 启动。"""
    from local_config import MODEL

    print(title)
    print("当前模型：{}".format(MODEL))
    print("可尝试：")
    for example in examples:
        print("  - {}".format(example))

    question = input("\n你：").strip()
    if not question:
        print("没有收到问题，已退出。")
        return

    print("\n正在检查进程环境变量 DASHSCOPE_API_KEY……", flush=True)
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print(
            "当前 Python 进程没有读到 DASHSCOPE_API_KEY。"
            "你可以在接下来的隐藏输入中提供 API Key。",
            flush=True,
        )
        api_key = getpass.getpass("请输入与本地百炼配置对应地域的 API Key（输入时不会显示）：").strip()
    else:
        print("已从进程环境变量读取到 API Key（不会显示其内容）。", flush=True)

    if not api_key:
        print("没有提供 API Key，已退出。")
        return

    print("Key 已就绪；请求日志不会包含认证密钥。", flush=True)
    try:
        run_agent(
            question=question,
            api_key=api_key,
            system_prompt=system_prompt,
            tools=tools,
            available_tools=available_tools,
            max_tool_rounds=max_tool_rounds,
        )
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
        print("\n运行失败：{}".format(error), file=sys.stderr)
