"""网页运行入口：除法练习走原生工具循环；两组故障注入不调用模型。

故障注入由运行器直接构造一条有问题的调用，交给与模型提议相同的检查（execute_tool）。
模型不一定会提出这样的调用，所以不靠模型制造；事件标为程序发起，不冒充模型提出过的调用。
"""
from course.execution import RunContext
from lessons.lesson_03_fail_safely import main
# 提示词与工具页从入口模块的 setup(locale) 读取，与 main.py 用的是同一份。
from lessons.lesson_03_fail_safely.main import setup  # noqa: F401
from lessons.lesson_03_fail_safely.tools import AVAILABLE_TOOLS

# 练习 id → 程序构造的调用：未登记的工具名，或无法解析的参数文本。
FAULTS = {
    "unknown": ("unregistered_tool", "{}"),
    "malformed": ("divide_numbers", "{bad json"),
}


def run(context: RunContext) -> str:
    fault = FAULTS.get(context.exercise_id)
    if fault is None:
        # 除法练习：与原生课程相同的工具循环，最多两轮模型请求。
        return context.run_native(main, max_rounds=2, publish_answer=True)
    name, arguments = fault
    result = context.submit_call(name, arguments, AVAILABLE_TOOLS)
    # 回答由程序按真实结果写出：本组没有模型，也就没有模型的回答。
    return (f"本组没有调用模型。运行器构造的调用 {name}（参数 {arguments}）"
            f"在执行前被拒绝：{result['error_type']}：{result['error']}。没有任何工具函数被执行。")
