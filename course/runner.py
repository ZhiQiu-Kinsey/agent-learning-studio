"""最小 Agent 循环与工具分发：工具调用课读的就是这里的代码。

循环只做四件事：组装消息历史、发请求、判断是否结束、执行调用提议并把工具结果写回历史。
记录事件、计时、停止检查都放在调用方传入的 complete / execute 两个函数里：
网页运行由 course/execution.py 的 RunContext 提供，命令行由下面的 run_cli 提供。
"""

import getpass
import json
import os
import sys

from course.api_client import send_bailian


def execute_tool(tool_call, available_tools):
    """执行一次调用提议；出错时返回结构化错误交还给模型，而不是让程序崩溃。"""
    name = tool_call["function"]["name"]
    try:
        # arguments 是模型生成的 JSON 字符串，先解析，并确认是参数对象。
        arguments = json.loads(tool_call["function"].get("arguments") or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是 JSON 对象。")
        # 白名单：只在 available_tools 里按名字查函数，模型编出来的名字不会被执行。
        function = available_tools.get(name)
        if function is None:
            raise ValueError("不认识这个工具：{}".format(name))
        return {"ok": True, "result": function(**arguments)}
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        # 参数缺失或多余会在 function(**arguments) 处抛 TypeError，同样整理成结果。
        return {"ok": False, "error_type": type(error).__name__, "error": str(error)}


def run_agent(question, system_prompt, tools, available_tools, max_tool_rounds, *, complete, execute=execute_tool):
    """运行工具调用循环，直到模型给出回答，或用完轮数上限。

    complete(body, round_number)：把请求体发给模型，返回响应。
    execute(tool_call, available_tools)：执行一次调用提议，返回工具结果。
    """
    # 1. 消息历史从系统提示词和用户问题开始。模型不保存上一轮，每轮只看得到这份列表。
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    for round_number in range(1, max_tool_rounds + 1):
        # 2. 每轮都把完整历史和工具定义一起发给模型。
        response = complete({"messages": messages, "tools": tools, "tool_choice": "auto"}, round_number)
        message = response["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        # 3. 没有调用提议，content 就是最终回答。
        if not tool_calls:
            return message.get("content") or ""
        # 4. 先把带调用提议的 assistant 消息放回历史，再逐个执行；
        #    每条工具结果都带上同一个调用 id，下一轮模型才能把结果和调用对上。
        messages.append(message)
        for tool_call in tool_calls:
            result = execute(tool_call, available_tools)
            messages.append({"role": "tool", "tool_call_id": tool_call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    # 轮数用完仍没有回答：报错停止，不返回半截结果。
    raise RuntimeError("工具调用超过 {} 轮，为避免无限循环已停止。".format(max_tool_rounds))


class RunCancelled(RuntimeError):
    """停止后续步骤；已经发出的 HTTP 请求仍受网络超时约束。"""


def run_cli(title, examples, system_prompt, tools, available_tools, max_tool_rounds):
    """命令行入口：读取问题和密钥，打印每轮请求体和工具结果，再运行同一个循环。"""
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

    def complete(body, round_number):
        request = {"model": MODEL, **body}
        print("\n第 {} 轮：完整 HTTP 请求体（不包含认证请求头）".format(round_number), flush=True)
        print(json.dumps(request, ensure_ascii=False, indent=2), flush=True)
        print("正在等待响应，网络超时为 60 秒……", flush=True)
        return send_bailian(request, api_key)

    def execute(tool_call, tools_by_name):
        print("\n模型请求工具：{}({})".format(tool_call["function"]["name"], tool_call["function"].get("arguments")))
        result = execute_tool(tool_call, tools_by_name)
        print("Python 执行结果：{}".format(json.dumps(result, ensure_ascii=False)))
        return result

    try:
        answer = run_agent(question, system_prompt, tools, available_tools, max_tool_rounds,
                           complete=complete, execute=execute)
        print("\nAgent 回答：\n{}".format(answer))
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
        print("\n运行失败：{}".format(error), file=sys.stderr)
