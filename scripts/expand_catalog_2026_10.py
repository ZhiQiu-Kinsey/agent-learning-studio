"""一次性脚本：按 docs/architecture/curriculum-research.md 第 4 节把课程表扩充到 42 课（新增均为 planned）。

运行后删除本脚本无妨；保留在仓库中便于追溯扩充依据。重复运行是幂等的（已存在的 slug 跳过）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "curriculum" / "catalog.json"


def lesson(slug, title, category, module, prerequisites, summary, objectives, topics, experiment, acceptance,
           references, level="必修"):
    return {"id": slug, "aliases": [], "title": title, "category_id": category, "module_id": module, "level": level,
            "status": "planned", "prerequisites": prerequisites, "summary": summary, "objectives": objectives,
            "topics": topics, "experiments": [experiment], "acceptance": acceptance, "references": references}


def exp(title, steps, deliverable):
    return {"title": title, "steps": steps, "deliverable": deliverable}


def ref(source, locator):
    return {"source": source, "locator": locator}


NEW = {
    "prompt-caching": lesson(
        "prompt-caching", "提示缓存与稳定前缀", "C", "C4", ["context-budget"],
        "比较时间戳在前、稳定前缀与预热三种请求结构，用服务商实际报告的缓存字段判断前缀能否复用。",
        ["说明提示缓存依赖完全相同的前缀", "从 usage 读取并归一化缓存命中字段", "区分“服务商报告为 0”与“未报告”"],
        ["前缀稳定性与动态内容位置", "cached / prompt 比例", "首字延迟（TTFT）", "前缀哈希", "各服务商缓存字段差异", "最小缓存长度"],
        exp("三组请求结构对照", [
            "固定一份超过服务商最小缓存长度的文档，分别构造“时间戳在前”“稳定前缀”“稳定前缀加预热”三组请求。",
            "每组运行 5 次，记录 usage 中的缓存字段、首字延迟和前缀哈希。",
            "对没有报告缓存字段的服务商，界面显示“未报告”，不把它记成 0。"],
            "三组对照的用量表、前缀哈希与“未报告”状态说明。"),
        ["每次调用的缓存比例都来自响应实际报告的字段。", "能指出哪一处动态内容破坏了前缀。", "未报告的字段没有被填成 0。"],
        [ref("book", "book/chapter2.md")]),
    "skills-disclosure": lesson(
        "skills-disclosure", "Skills 与渐进式披露", "C", "C4", ["prompt-caching"],
        "对比一次性注入全部技能说明与“目录加按需加载”，并检验技能描述精确程度对触发的影响。",
        ["解释渐进式披露如何控制上下文规模", "实现目录加 load_skill 的按需加载", "用不该触发的提示检验误触发"],
        ["技能目录与描述", "按需加载工具", "触发率与误触发", "分段 token 用量", "技能版本与来源"],
        exp("全量注入与按需加载对照", [
            "准备一组技能说明，分别以全量注入和“目录加 load_skill”两种方式提供给模型。",
            "用一组应触发与不应触发的提示，比较模糊描述与精确描述下的触发情况。",
            "记录每次请求的分段 token（来自 usage）和实际加载了哪个技能。"],
            "两种方式的触发记录、误触发样例与分段用量。"),
        ["加载记录能对应到具体请求。", "至少一条不应触发的提示被正确忽略或如实记录为误触发。", "token 分段来自服务商报告，未报告时明确标注。"],
        [ref("book", "book/chapter2.md"), ref("book", "book/chapter4.md")]),
    "text-actions": lesson(
        "text-actions", "文本动作与原生工具调用", "R", "R1", ["fail-safely", "structured-output"],
        "用正则解析的文本协议与原生 tool_calls 完成同一组任务，观察去掉 stop 时模型如何编造 Observation。",
        ["比较文本动作协议与原生工具调用的可靠性", "识别模型编造的 Observation", "记录解析失败而不是静默忽略"],
        ["ReAct 文本格式", "stop 序列", "解析失败事件", "finish_reason", "原生调用与文本协议的对照"],
        exp("同一任务两种行动协议", [
            "为同一组任务分别实现正则文本协议和原生工具调用两种运行器。",
            "去掉 stop 序列运行文本协议，把模型写出的 Observation 与真实工具结果并列。",
            "统计解析失败事件与 finish_reason。"],
            "原始 content 与 tool_calls 并列的记录、解析失败统计。"),
        ["界面并列显示原始 content 与 tool_calls。", "编造的 Observation 与真实结果的差异有证据。", "解析失败作为事件记录，没有被吞掉。"],
        [ref("huggingface", "units/en/unit1/actions.mdx"), ref("book", "book/chapter2.md")]),
    "todo-planning": lesson(
        "todo-planning", "规划：TODO 清单与状态提示", "R", "R1", ["application-state", "text-actions"],
        "让 Agent 用 todo_write 维护任务清单，比较有无清单、提醒开关时的完成情况，并用第 4 课的验收器判定。",
        ["把多步任务拆成可追踪的 TODO", "区分模型写的计划与运行层注入的提醒", "用独立验收器判断完成"],
        ["todo_write 工具", "TODO 快照与差异", "运行层注入的提醒", "距上次更新的轮数", "完成判定"],
        exp("有无 TODO 与提醒的对照", [
            "同一多步任务分别在“无 TODO”“有 TODO 无提醒”“有 TODO 有提醒”三种条件下运行。",
            "记录每轮 TODO 快照与差异，提醒标注为运行层注入。",
            "用第 4 课的验收器判定最终是否完成。"],
            "三组运行的 TODO 时间线与验收结果。"),
        ["TODO 快照逐轮可回放。", "提醒在界面上标注为运行层注入，而不是模型输出。", "完成由验收器判定，不以模型自称为准。"],
        [ref("microsoft", "07-planning-design/README.md"), ref("book", "book/chapter2.md")]),
    "plan-and-replan": lesson(
        "plan-and-replan", "先规划后执行与重新规划", "R", "R2", ["todo-planning"],
        "夹具工具在第 2 步失败时，比较静态计划、动态重规划与 ReAct 基线的表现。",
        ["区分计划版本与执行状态", "在失败后有依据地修订计划", "用同一任务比较三种策略"],
        ["计划版本", "步骤依赖与验收条件", "修订原因", "计划差异", "ReAct 基线"],
        exp("第 2 步故障下的三种策略", [
            "设计第 2 步必定失败的夹具工具。",
            "分别运行静态计划、动态重规划和 ReAct 基线。",
            "记录带版本的计划、步骤状态、计划差异与修订原因。"],
            "三种策略的计划版本对比与结果。"),
        ["每次修订都有原因与差异。", "步骤状态来自真实执行结果。", "三种策略在同一任务和验收标准下比较。"],
        [ref("microsoft", "07-planning-design/README.md")]),
    "reflection-revision": lesson(
        "reflection-revision", "反思、评审与有界修订", "R", "R2", ["plan-and-replan"],
        "比较模型自评与以真实测试结果为依据的评审，并为修订循环设置迭代上限。",
        ["区分模型自评与外部验证", "把评审结果结构化为可检查的 JSON", "用迭代上限与停止原因约束修订"],
        ["草稿版本差异", "评审 JSON 与量规", "验证器输出", "停止原因", "累计 token"],
        exp("自评与测试依据的对照", [
            "同一编码小任务分别用模型自评和真实 pytest 结果驱动修订。",
            "设置最大迭代次数，记录每版草稿差异、评审 JSON 和验证器输出。",
            "比较两种方式的停止原因与累计用量。"],
            "草稿 v0…vn 的差异、评审记录与停止原因。"),
        ["停止原因明确（通过、达到上限或无改进）。", "以测试为依据的评审引用真实验证输出。", "累计用量来自服务商报告。"],
        [ref("microsoft", "09-metacognition/README.md")]),
    "workflow-patterns": lesson(
        "workflow-patterns", "工作流模式：链式、路由与并行", "R", "R3", ["reflection-revision"],
        "用已标注工单测试路由准确率，并比较并行与串行执行的墙钟时间。",
        ["选择适合任务的工作流模式", "用标注数据评估路由", "测量并行带来的时间差异"],
        ["提示链", "路由决策与兜底", "并行分支", "混淆矩阵", "墙钟时间"],
        exp("路由与并行", [
            "用 20 张已标注工单测试路由，统计准确率与混淆矩阵。",
            "同一组独立子任务分别串行和并行执行，记录墙钟时间。",
            "在时间线上展示并行分支。"],
            "路由混淆矩阵与并行时间线。"),
        ["路由准确率来自标注对照。", "并行与串行的时间来自服务端时间戳。", "兜底路径有记录。"],
        [ref("book", "book/chapter1.md")]),
    "orchestrator-evaluator": lesson(
        "orchestrator-evaluator", "编排者-工人与评估者-优化者", "R", "R3", ["workflow-patterns"],
        "实现编排者拆分任务给工人、评估者驱动优化的两种模式，并度量额外调用带来的成本。",
        ["说明编排的 N+1 次调用成本", "为评估者-优化者设置 max_iters", "在嵌套 span 中追踪工人执行"],
        ["计划产物", "嵌套工人 span", "评审结论", "迭代上限", "成本统计"],
        exp("编排与评估循环", [
            "编排者生成计划并分派给工人，记录嵌套的工人 span。",
            "评估者-优化者在 max_iters 内迭代，记录每轮评审结论。",
            "统计相对单次调用的额外成本。"],
            "嵌套 span 时间线、评审记录与成本对比。"),
        ["工人执行在舞台上表现为嵌套 span。", "评估循环一定在上限内停止。", "成本来自实际用量。"],
        [ref("book", "book/chapter1.md")]),
    "hooks-approval": lesson(
        "hooks-approval", "Hooks 与审批闸门", "E", "E3", ["async-concurrency"],
        "在工具执行前加入钩子与人工审批，运行进入暂停状态，批准或拒绝后续跑。",
        ["区分钩子的阶段与裁决", "实现可暂停、可续跑的审批", "让审批摘要与实际参数一致"],
        ["钩子阶段与处理器", "审批请求与决定", "暂停与续跑", "风险等级", "规范化参数摘要"],
        exp("高风险工具前的审批", [
            "为一个会写入文件的夹具工具加入审批闸门。",
            "运行进入 paused，学习者在界面批准或拒绝，运行据此续跑或终止。",
            "校验审批摘要与实际执行参数一致。"],
            "审批卡记录与暂停、续跑时间线。"),
        ["审批前工具没有执行。", "拒绝后运行如实结束并说明原因。", "审批摘要与实际参数逐项一致。"],
        [ref("microsoft", "06-building-trustworthy-agents/README.md"), ref("book", "book/chapter4.md")]),
    "bash-coding-agent": lesson(
        "bash-coding-agent", "单 bash 工具编码 Agent 与沙箱", "K", "K1", ["hooks-approval"],
        "在带失败测试的夹具仓库中，用单个 bash 工具让 Agent 修复代码，由平台重新运行测试来验收。",
        ["为命令执行设置工作区、超时与环境变量清理", "记录命令证据而不是相信 Agent 自述", "由平台独立验收"],
        ["独立临时工作区", "环境变量清理", "超时与杀进程树", "命令策略判定", "输出首尾截断"],
        exp("修复夹具仓库的失败测试", [
            "为每次运行创建独立临时工作区，复制带失败测试的夹具仓库。",
            "Agent 只有一个 bash 工具；记录每条命令的 cwd、策略判定、退出码、输出首尾与耗时。",
            "运行结束后由平台重新运行 pytest 判定是否修复。"],
            "命令记录、文件 diff 与平台验收结果。"),
        ["子进程拿不到任何密钥。", "超时会终止整棵进程树。", "验收结果来自平台重新运行的测试。"],
        [ref("book", "book/chapter5.md")]),
    "file-edit-evidence": lesson(
        "file-edit-evidence", "文件工具、编辑策略与变更证据", "K", "K1", ["bash-coding-agent"],
        "用专门的读写与编辑工具替代 bash 修改文件，比较编辑策略，并用前后哈希与 diff 证明变更。",
        ["设计安全的文件读写与编辑工具", "比较整文件重写与局部替换", "用哈希与 diff 留下变更证据"],
        ["路径校验", "整文件写入与局部替换", "前后哈希", "统一 diff", "冲突与过期检测"],
        exp("两种编辑策略的对照", [
            "同一修改任务分别用整文件重写和局部替换完成。",
            "记录每次修改的前后哈希与统一 diff。",
            "模拟文件在读取后被外部修改，检查工具能否发现过期。"],
            "两种策略的 diff 记录与过期检测结果。"),
        ["所有路径都被解析并限制在工作区内。", "每次修改都有前后哈希与 diff。", "过期写入被拒绝而不是覆盖。"],
        [ref("book", "book/chapter5.md")]),
    "a2a-delegation": lesson(
        "a2a-delegation", "A2A 与跨进程委派", "G", "G2", ["mcp-lifecycle"],
        "让两个独立进程中的 Agent 通过 A2A 协议委派任务，观察能力发现、任务状态与结果回传。",
        ["说明 A2A 与 MCP 的分工", "追踪跨进程任务的状态变化", "处理委派失败与超时"],
        ["Agent Card 与能力发现", "任务状态", "跨进程消息", "失败与超时", "与 MCP 的对比"],
        exp("两个本地 Agent 之间的委派", [
            "在本机启动两个独立进程的 Agent，一方通过 A2A 委派子任务给另一方。",
            "记录能力发现、任务状态变化与结果回传。",
            "让被委派方超时，检查委派方如何处理。"],
            "跨进程委派时间线与失败处理记录。"),
        ["任务状态变化可回放。", "超时被明确处理，没有无限等待。", "能说明此场景为何用 A2A 而不是 MCP。"],
        [ref("microsoft", "11-agentic-protocols/README.md")], level="选修"),
    "long-running-tasks": lesson(
        "long-running-tasks", "长时任务：后台、定时与目标循环", "H", "H2", ["delegation-budget"],
        "把耗时任务放到后台，在之后的轮次中注入结果，并用目标评估决定继续、完成或放弃。",
        ["管理后台任务的起止与退出码", "在合适的轮次注入后台结果", "用目标评估约束长循环"],
        ["后台任务", "定时触发", "结果注入时机", "目标评估", "预算与放弃条件"],
        exp("后台任务与目标循环", [
            "启动一个耗时的后台夹具任务，记录起止、退出码与注入的轮次。",
            "用目标评估在每轮判断 ok、impossible 或继续。",
            "设置预算上限，观察达到上限时的处理。"],
            "后台泳道时间线与目标评估记录。"),
        ["后台结果在注入轮次之前没有被模型看到。", "目标评估的理由被记录。", "达到预算时明确停止。"],
        [ref("book", "book/chapter6.md")]),
}

MODULES = {
    "C": [{"id": "C4", "title": "缓存与技能", "description": "稳定前缀如何复用，技能说明如何按需进入上下文。",
           "lesson_ids": ["prompt-caching", "skills-disclosure"]}],
    "E": [{"id": "E3", "title": "审批、人工介入与恢复", "description": "在执行前加入闸门，暂停后续跑，并能从检查点恢复。",
           "lesson_ids": ["hooks-approval", "human-in-the-loop"]}],
    "G": [{"id": "G2", "title": "连接生命周期与跨进程委派", "description": "管理多个服务的连接，并比较 MCP 与 A2A 的分工。",
           "lesson_ids": ["mcp-lifecycle", "a2a-delegation"]}],
    "H": [{"id": "H2", "title": "长时任务", "description": "后台执行、定时触发与目标循环的边界。",
           "lesson_ids": ["long-running-tasks"]}],
}
NEW_CATEGORIES = [
    ({"id": "R", "title": "推理与控制模式",
      "description": "从文本动作到规划、反思与工作流模式，比较控制方式带来的可靠性与成本。",
      "modules": [
          {"id": "R1", "title": "行动协议与规划", "description": "文本动作与原生调用的对照，以及 TODO 规划。",
           "lesson_ids": ["text-actions", "todo-planning"]},
          {"id": "R2", "title": "重新规划与有界修订", "description": "失败后的计划修订，与有上限的评审循环。",
           "lesson_ids": ["plan-and-replan", "reflection-revision"]},
          {"id": "R3", "title": "工作流模式", "description": "链式、路由、并行、编排与评估循环。",
           "lesson_ids": ["workflow-patterns", "orchestrator-evaluator"]}]}, "C"),
    ({"id": "K", "title": "编码 Agent 与执行环境",
      "description": "让 Agent 在隔离环境中执行命令和修改文件，并由平台独立验收。",
      "modules": [{"id": "K1", "title": "命令、文件与变更证据", "description": "沙箱化的命令执行与可验证的文件编辑。",
                   "lesson_ids": ["bash-coding-agent", "file-edit-evidence"]}]}, "E"),
]


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    existing = {item["id"] for item in catalog["lessons"]}
    if all(slug in existing for slug in NEW):
        print("已扩充，无需重复执行。")
        return
    categories = catalog["categories"]
    for category in categories:
        for module in MODULES.get(category["id"], []):
            current = next((m for m in category["modules"] if m["id"] == module["id"]), None)
            if current is None:
                # 新模块按编号插入，例如 H2 排在 H1 与 H3 之间。
                position = next((i for i, m in enumerate(category["modules"]) if m["id"] > module["id"]),
                                len(category["modules"]))
                category["modules"].insert(position, module)
            else:  # 已有模块：并入新课，保持给定顺序
                current["lesson_ids"] = [i for i in module["lesson_ids"]]
                current["title"], current["description"] = module["title"], module["description"]
    for category, after in NEW_CATEGORIES:
        index = next(i for i, c in enumerate(categories) if c["id"] == after)
        categories.insert(index + 1, category)
    # 课程数组顺序必须与 分类 → 模块 → lesson_ids 的遍历顺序一致。
    by_id = {item["id"]: item for item in catalog["lessons"]} | NEW
    order = [lesson_id for c in categories for m in c["modules"] for lesson_id in m["lesson_ids"]]
    missing = [item for item in by_id if item not in order]
    if missing:
        raise SystemExit(f"这些课程没有登记在任何模块中：{missing}")
    catalog["lessons"] = [by_id[lesson_id] for lesson_id in order]
    # 毕业项目按决策 2 设两条路线。
    capstone = by_id.get("capstone-study-assistant")
    if capstone:
        capstone["title"] = "毕业项目：本地编码助教 / 本地学习助教"
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"课程总数：{len(catalog['lessons'])}")


if __name__ == "__main__":
    main()
