"""长任务一课的运行时文本（中文，源语言）。"""
from lessons.lesson_long_running_tasks.locales import Texts

TEXTS = Texts(
    list_separator="、",
    system=(
        "你是课程助教的巡检助手。耗时的检查用 start_background_job 放到后台：它立刻返回任务编号，不会等任务跑完。"
        "任务结束后，运行层会在之后的某一轮用一条单独的消息把结果交给你，消息开头写明来源，那不是用户说的话。"
        "结果到达之前不要猜测它。暂时没有别的事可做时，直接说明你在等什么，不要反复调用 check_job。"
        "必需的结果齐了，就调用 submit_report 提交简报，简报里的值必须来自后台任务的结果，原样照抄。"
        "后台任务失败时，先看错误原因，再决定要不要重试。"
    ),
    tasks={
        "nightly": (
            "今晚的巡检：1）校验 6 份作业提交包的 SHA-256，用后台任务 checksum_pack，值是摘要；"
            "2）统计 12 位同学的成绩及格人数，用后台任务 grade_stats，值是及格人数。"
            "等两项结果都到了，用 submit_report 提交简报。等待时可以先用 read_policy 查看规则。"
        ),
        "late": (
            "补交成绩巡检：1）校验 6 份作业提交包的 SHA-256，用后台任务 checksum_pack，值是摘要；"
            "2）导入补交成绩表，用后台任务 late_import，值是导入的行数。"
            "等两项结果都到了，用 submit_report 提交简报。"
        ),
        "deep": (
            "期末前的全量巡检：1）校验 6 份作业提交包的 SHA-256，用后台任务 checksum_pack，值是摘要；"
            "2）全量扫描 8 个分片找重复内容，用后台任务 deep_scan，值是重复的分片数。"
            "等两项结果都到了，用 submit_report 提交简报。"
        ),
    },
    policies={
        "pass_line": "及格线是 60 分，60 分及以上算及格。",
        "late_rule": "补交成绩表由助教手工整理，每行写“学号,成绩”。",
    },
    start_description=(
        "把一项耗时检查放到后台运行，立刻返回任务编号 job_id，不等它跑完。种类：checksum_pack 校验提交包，"
        "grade_stats 统计成绩，late_import 导入补交成绩表，deep_scan 全量扫描。结果在任务结束后由运行层单独交给你。"
        "timeout_seconds 是期限（秒，5 到 120），不填用默认值。"
    ),
    check_description="查询一个后台任务的状态和进度。任务结束后，结果交付了才会显示；不要用它代替等待。",
    cancel_description="取消一个还在运行的后台任务，返回取消后的状态。已经结束的任务不能取消。",
    policy_description="读取一条检查规则，topic 是 pass_line 或 late_rule。同步工具，立即返回。",
    report_description="提交简报：每个必需任务一条 kind 和 value，value 照抄后台任务结果里的 value。再次提交会替换上一份。",
    start_note="任务已在后台运行。结果在任务结束后由运行层单独发给你，不会出现在这条工具结果里。",
    result_pending="任务已结束，结果还没有交付。",
    unknown_kind="没有任务种类 {kind}，可用：{kinds}。",
    bad_timeout="timeout_seconds 必须是 5 到 120 的整数。",
    too_many_jobs="同时运行的后台任务已达上限 {limit} 个，等一个结束或取消一个再启动。",
    unknown_job="没有任务 {job_id}。",
    already_finished="{job_id} 已经结束（{status}），不能取消。",
    unknown_topic="没有规则 {topic}，可用：{topics}。",
    report_shape="results 必须是非空数组，每项恰有 kind 和 value 两个字段，value 是字符串。",
    report_kind="kind 不能是 {kind}，也不能重复；可选：{kinds}。",
    detail_checksum="{files} 个文件，共 {size} 字节，SHA-256 前 12 位 {digest}。",
    detail_grades="{total} 人中 {passed} 人及格（{line} 分及以上），平均 {mean} 分。",
    bad_score="第 {row} 行的成绩 {value} 不是整数。",
    detail_import="导入 {rows} 行成绩。",
    detail_scan="扫描 {shards} 个分片，发现 {duplicates} 个重复分片。",
    timeout_detail="超过 {seconds} 秒的期限，后台执行器停止了它。",
    cancel_detail="已取消：{reason}。",
    cancel_reasons={"model_request": "模型请求取消", "run_end": "运行结束，统一取消"},
    injection_header="[后台任务结果 · 来源：运行层的后台执行器，不是用户说的话] 当前是第 {now} 秒（虚拟时钟）。以下任务已经结束：",
    injection_items={
        "completed": "- {job_id} {kind}：已完成，退出码 {exit_code}，第 {finished_at} 秒结束。value={value}。{summary}",
        "failed": "- {job_id} {kind}：失败，退出码 {exit_code}，第 {finished_at} 秒结束。错误：{summary}",
        "timed_out": "- {job_id} {kind}：超时，退出码 {exit_code}，第 {finished_at} 秒结束。{summary}",
    },
    feedback="[运行层 · 目标检查] 第 {round} 轮结束时目标还没有达成：{reason}",
    reasons={
        "goal_met": "每个必需任务都有已交付的结果，简报的值与结果一致。",
        "kind_exhausted": "{kind} 已经启动 {attempts} 次（上限 {limit} 次），都没有成功，也没有在运行；同样的任务再跑还会同样失败。",
        "waiting": "还有后台任务在运行：{jobs}。",
        "open": "还需要启动：{kinds}。",
        "report_missing": "必需任务的结果都已交付，但还没有提交简报。",
        "report_mismatch": "简报与后台结果不一致：{detail}",
        "budget": "{rounds} 轮预算用完，目标还没达成。最后一次检查：{state}",
    },
    goal_done="{job} 已完成，结果已交付",
    goal_running="{job} 还在运行",
    goal_exhausted="启动 {attempts} 次，上限 {limit} 次，没有成功",
    goal_open="已启动 {attempts} 次，上限 {limit} 次；可以启动或重试",
    report_waiting="必需任务还没有全部交付结果，暂不核对简报",
    report_missing="还没有提交简报",
    report_lacks="简报缺少 {kind}",
    report_differs="{kind} 的值与后台结果不一致",
    report_match="简报里每个值都等于对应任务的结果",
    card_goal="在后台完成 {kinds}，再按结果提交一份简报",
    card_input_scope="只用这次运行里后台任务返回的结果；任务在后台执行器里真实运行，时间用虚拟时钟",
    card_output="submit_report：每个必需任务一条 kind 和 value（{kinds}）",
    card_evidence="简报里的 value 必须等于对应任务已交付的结果，由运行层逐项核对",
    card_failure="同一种任务启动 {attempts} 次都失败、也没有在运行，就判定无法完成并停止",
    card_stop="最多 {rounds} 轮模型调用，每轮约 {tick} 秒（虚拟）；用完就停止，并取消还在运行的后台任务",
    schedule_goal="每 {interval} 秒触发一次后台任务 {kind}，观察上一次还没跑完时调度器怎么处理",
    schedule_input_scope="固定间隔的触发，没有模型；任务在后台执行器里真实运行，时间用虚拟时钟",
    schedule_output="每次触发一条记录：到点时刻、决定、对应的运行编号",
    schedule_evidence="触发次数等于时间范围内应有的次数；每个开始的运行都有自己的记录",
    schedule_failure="上一次没跑完时按“{policy}”处理，并写明原因",
    schedule_stop="到第 {horizon} 秒停止，并取消还在运行的任务",
    policy_names={"skip": "跳过", "queue": "排队", "parallel": "有上限的并行"},
    fire_details={
        "started": "到点时没有任务在运行，直接开始一次运行。",
        "started_from_queue": "前一次运行结束了，排队的触发开始运行。",
        "skipped": "上一次还没跑完，这次触发被跳过。",
        "queued": "上一次还没跑完，这次触发排进队列。",
        "dropped": "队列已满，这次触发被丢弃。",
        "denied": "并行运行数已到上限，这次触发被拒绝。",
    },
    fire_actions={"started": "开始", "started_from_queue": "出队开始", "skipped": "跳过", "queued": "排队",
                  "dropped": "丢弃", "denied": "拒绝"},
    fire_reasons={"previous_running": "上一次未结束", "queue_full": "队列已满", "concurrency_limit": "并行已达上限"},
    report_titles={"nightly": "后台任务与结果注入", "late": "任务失败与重试", "deep": "预算、轮询与取消"},
    report_summary="后台任务在执行器里真实运行，时间是虚拟时钟上的秒。结论由运行层的目标检查给出，不取决于模型怎么说。",
    check_report="简报与后台结果一致",
    check_goal_logged="每轮目标检查都有记录和理由",
    detail_goal_logged="{rounds} 轮，{rounds} 条记录",
    check_not_early="后台结果在注入之前没有出现在任何一次请求里",
    detail_not_early="{count} 条注入的结果，首次出现的请求都是注入它的那一轮",
    detail_not_early_bad="这些任务的结果在注入之前就出现过：{jobs}",
    check_no_orphans="运行结束时没有存活的后台线程",
    detail_no_orphans="结束时取消了 {count} 个还在运行的任务，全部线程已回收",
    label_outcome="结论",
    label_stop_reason="停止原因",
    label_rounds="轮数",
    label_max_rounds="轮数预算",
    label_jobs_started="启动的任务",
    label_jobs_completed="完成",
    label_jobs_failed="失败",
    label_jobs_timed_out="超时",
    label_jobs_cancelled="取消",
    label_polls="check_job 次数",
    label_injections="注入次数",
    label_clock_end="结束时刻（虚拟）",
    label_orphans="存活的后台线程",
    label_note="学习者备注",
    value_seconds="{seconds} 秒",
    value_empty="无",
    value_none="无",
    outcomes={"completed": "完成", "abandoned": "放弃：无法完成", "budget_exhausted": "预算用完"},
    status_names={"running": "运行中", "completed": "已完成", "failed": "失败", "timed_out": "超时",
                  "cancelled": "已取消"},
    job_columns=("任务", "种类", "启动（秒）", "启动轮", "结束（秒）", "状态", "退出码", "注入轮", "结束到注入（秒）"),
    answers={
        "completed": "巡检完成（{rounds} 轮）：简报 {results}，已与后台结果逐项核对。",
        "abandoned": "无法完成（{rounds} 轮）：{reason} 已提交的简报：{results}。",
        "budget_exhausted": "目标未达成。{reason} 已提交的简报：{results}。",
    },
    schedule_report_title="定时触发：{policy}",
    schedule_summary="每个到点时刻立即决定并记录；开始的运行是后台执行器里真实运行的任务。时间是虚拟时钟上的秒。",
    check_every_fire="每次到点都有一条触发记录",
    detail_every_fire="触发 {fires} 次，应有 {expected} 次",
    check_every_run="每个开始的运行都有自己的记录",
    detail_every_run="{runs} 次运行，各有一条任务记录",
    label_policy="重叠策略",
    label_fires="触发次数",
    label_runs_started="开始的运行",
    label_skipped="跳过",
    label_queued="排队",
    label_dropped="丢弃",
    label_denied="拒绝",
    label_runs_finished="完成的运行",
    label_cancelled_at_end="结束时取消",
    label_waiting_at_end="结束时仍在排队",
    fire_columns=("触发", "到点（秒）", "决定时刻（秒）", "决定", "运行", "原因"),
    schedule_answer=(
        "触发 {fires} 次，策略“{policy}”：开始 {started} 次运行，跳过 {skipped}，排队 {queued}，"
        "丢弃 {dropped}，拒绝 {denied}；结束时取消 {cancelled} 个还在运行的任务。"
    ),
)
