"""file-edit-evidence runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_file_edit_evidence.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "你是一个编码 Agent，在一个小型 Python 仓库里工作。你只能用给你的工具读写文件、运行测试，没有别的办法。规则：\n"
        "1. 先用 read_file 读文件，再改它。工具会拒绝没读过的文件，也会拒绝在你读过之后被别人改动的文件；被拒绝时重新读取，再基于新内容改。\n"
        "2. 路径都是相对仓库根目录的相对路径。tests/ 下的文件只能读，不能改。\n"
        "3. read_file 结果里每行开头的“行号|”只是显示用的，不属于文件内容。\n"
        "4. 改完后调用 run_tests 运行测试，根据输出判断有没有完成。\n"
        "5. 最后用一两句话说明改了什么、测试结果如何；不要声称你没有做过的事。"
    ),
    task=(
        "仓库里有两个测试失败：\n"
        "1. 订单金额满 300 元应有 20% 折扣（现在最高只有 15%，从 200 元起）。\n"
        "2. 金额正好 50 元就应当免运费（现在要超过 50 元才免）。\n"
        "请只修改 shop/pricing.py，让测试全部通过，不要改 tests/ 下的任何文件；discount_rate 的文档字符串要和新规则一致。\n\n"
        "仓库文件：\n{tree}\n\n"
        "测试命令（run_tests 工具运行它）：{command}"
    ),
    tree_line="{path}（{lines} 行）",
    task_card={
        "goal": "让 tests/ 下的测试全部通过：满 300 元 20% 折扣，正好 50 元免运费",
        "input_scope": "只修改 shop/pricing.py；仓库里的文件都可以读，tests/ 只读",
        "output": "shop/pricing.py 的改动，加一两句说明",
        "evidence": "平台自己重新运行测试通过；每次写入的前后哈希和统一 diff 都对得上",
        "failure": "没读就写、读后被改、old 不唯一、行号失效、路径越界、改测试：工具拒绝并返回结构化错误，文件保持原样",
        "stop": "模型不再提出调用，或用完 10 轮的轮数上限",
    },
    desc_read_file=(
        "读取工作区里的一个文本文件，返回带行号的内容；每行开头的“行号|”只用于显示，不是文件内容。"
        "用 start_line 和 end_line 只读一段（行号从 1 开始，含两端）；不给就从第 1 行读起，最多 400 行。改文件之前必须先读它。"
    ),
    desc_write_file=(
        "把整个文件写成 content；文件不存在就新建。已有的文件必须先用 read_file 读完全部内容，"
        "并且读过之后没有被别人改动，否则会被拒绝。tests/ 下的文件不能写。"
    ),
    desc_edit_file=(
        "精确替换：把文件里的 old 换成 new。old 必须与文件原文逐字相同（不含行号前缀），并且在文件里恰好出现一次；"
        "找不到或出现多次都会报错，文件保持原样。改之前必须先读过这个文件，读过之后文件被别人改动会被拒绝。tests/ 下的文件不能改。"
    ),
    desc_edit_lines=(
        "行号替换：把第 start_line 到第 end_line 行（含两端）换成 new_text。行号必须来自最近一次 read_file；"
        "任何写入之后行号都作废，要先重新读取。读过之后文件被别人改动会被拒绝。tests/ 下的文件不能改。"
    ),
    desc_run_tests=(
        "在工作区里运行测试（python -m unittest discover -s tests），返回退出码和输出。"
        "没有容器隔离时，每次运行都要先经人批准；被拒绝时命令不会执行。"
    ),
    param_path="相对仓库根目录的路径，例如 shop/pricing.py",
    param_start_line="起始行号，从 1 开始，默认 1",
    param_end_line="结束行号（含），默认读到起始行之后 400 行或文件末尾",
    param_content="文件的完整新内容",
    param_old="要被替换的原文，必须逐字相同，并且在文件里恰好出现一次",
    param_new="替换后的文本",
    param_first_line="要替换的第一行的行号（含）",
    param_last_line="要替换的最后一行的行号（含）",
    param_new_text="替换这些行的新文本，可以多行；空字符串表示删除这些行",
    path_outside="路径 {path} 不在工作区内：只能用相对仓库根目录的路径，不能用绝对路径、.. 或 ~。",
    protected_path="{path} 受保护，不能写：tests/ 下的文件只读，任务要改的是代码，不是验收它的测试。",
    file_not_found="找不到文件 {path}。",
    not_a_file="{path} 不是文件。",
    not_text="{path} 不是 UTF-8 文本文件，无法读写。",
    file_too_large="{path} 超过 {limit} 字节，工具不处理。",
    not_read_yet="还没有读过 {path}，没有写入。先用 read_file 读它，再改。",
    stale_read="{path} 在你读过之后被改动了，你手里的内容已经过期，没有写入。先重新 read_file，再基于新内容改。",
    partial_read="你只读了 {path} 的一部分，整文件写入会覆盖没读到的内容，没有写入。先读完全部内容，或者改用局部编辑。",
    line_numbers_stale="自从你上次 read_file 之后，{path} 又被写过，行号已经作废，没有写入。先重新 read_file，再按新行号改。",
    invalid_range="行号范围不对：start_line={start}，end_line={end}，文件共 {total} 行。需要 1 <= start_line <= end_line <= 总行数。",
    invalid_argument="参数 {name} 的类型不对。",
    old_empty="old 不能为空，也必须是字符串。",
    old_not_found="在 {path} 里找不到 old。它必须与文件原文逐字相同，不要带 read_file 显示的行号前缀；重新读取后再复制。",
    old_not_unique="old 在文件里出现了 {count} 次（行号 {lines}），不知道改哪一处，没有写入。把前后几行一起写进 old，让它只出现一次。",
    no_op_edit="这次修改不会改变文件，没有写入。",
    write_failed="操作系统拒绝写入 {path}，文件保持原样。",
    label_isolated="已隔离 · 命令在容器里执行",
    label_unisolated="未隔离 · 命令在你的机器上执行",
    approvals={"every_command": "每条命令先经你批准", "none": "在容器里执行，不逐条审批"},
    environment_text="{label}；{approval}",
    approve_tests="运行测试：{command}。{label}。这会执行智能体改过的代码，目前改动了 {files} 个文件。",
    approve_acceptance="平台验收，重新运行测试：{command}。{label}。这会执行智能体改过的代码，目前改动了 {files} 个文件。",
    sandbox_errors={
        "policy_denied": "命令被策略拒绝（规则 {rule}），没有执行。",
        "approval_rejected": "人拒绝了这条命令，没有执行。",
        "approval_timeout": "超时没有人决定，没有执行。",
        "approval_unavailable": "这条命令需要人批准，但没有可用的审批通道，没有执行。",
        "timeout": "测试运行超过 {timeout_s} 秒，已被终止。",
        "output_limit": "测试输出过多，已被终止。",
        "cancelled": "运行被停止，命令已终止。",
        "nonzero_exit": "测试命令以退出码 {exit_code} 结束；原因看 stdout 与 stderr。",
        "spawn_failed": "无法启动命令。",
    },
    separator="、",
    value_yes="是",
    value_no="否",
    value_none="无",
    value_not_reported="未报告",
    tokens_partly_reported="{total}（另有 {missing} 次响应未报告）",
    label_note="学习者备注",
    label_model_calls="模型调用数",
    label_tool_calls="工具调用数",
    strategies={"rewrite": "整文件重写", "replace": "精确替换", "lines": "行号替换"},
    edit_titles={"rewrite": "整文件重写：write_file", "replace": "精确替换：edit_file", "lines": "行号替换：edit_lines"},
    edit_summary=(
        "同一个修改任务，只给模型一种写入工具。平台自己重新运行测试，检查测试有没有被改、哪些函数变了、"
        "前后哈希是否首尾相接。下面的检查来自文件和命令的真实结果，不来自模型的自述。"
    ),
    check_tests="平台重新运行测试",
    check_tests_detail="运行了 {ran} 个测试，结果 {outcome}。",
    check_tests_not_run="测试没有运行：{reason}。这一项不判定通过。",
    check_untouched="tests/ 下的文件没有被改",
    check_untouched_detail="被改动的受保护文件：{files}。",
    check_scope="改动只落在任务允许的范围内",
    check_scope_detail="改动的文件：{files}；改动、删除或新增的函数：{symbols}；范围之外：{unexpected}。",
    check_scope_unparsable="改动后的文件无法解析成 Python，没法比较改动范围（文件：{files}）。",
    check_chain="每次写入都有前后哈希，并且首尾相接",
    check_chain_ok="{rows} 次生效的写入：每一条的写入前哈希等于上一条的写入后哈希，最后一条等于文件现在的哈希。",
    check_chain_broken="哈希链对不上：{problems}。",
    chain_reasons={
        "broken_chain": "这条记录的起点不是文件当时的哈希",
        "unexplained_change": "文件变了，但没有任何写入记录",
        "final_mismatch": "最后一条记录的终点不是文件现在的哈希",
    },
    label_environment="执行环境",
    label_write_calls="{tool} 调用（成功 / 被拒）",
    write_calls_value="{ok} / {rejected}",
    label_read_calls="read_file 调用数",
    label_test_runs="模型自己运行测试的次数",
    label_write_chars="写入类调用的参数字符数（实际发出的）",
    label_result_chars="工具结果字符数（返回给模型的）",
    label_completion_tokens="完成 Token（服务商报告）",
    label_total_tokens="总 Token（服务商报告）",
    label_lines="生效写入的增 / 删行数",
    lines_value="+{added} / -{removed}",
    label_self_check="最后一次写入之后，模型自己运行过测试",
    label_base_hash="{path} 起始哈希（前 12 位）",
    label_final_hash="{path} 最终哈希（前 12 位）",
    label_diff="统一 diff（相对起始版本，全部文件）",
    journal_columns=("序号", "工具", "路径", "结果", "写入前哈希", "写入后哈希", "增 / 删"),
    outcome_written="已写入",
    outcome_unchanged="无变化",
    verdict_ok="通过",
    verdict_failed="未通过",
    verdict_not_run="没有运行",
    chain_ok="闭合",
    chain_broken="对不上",
    claim_quote="模型自述：{claim}",
    claim_rounds="模型用完 {limit} 轮的轮数上限，没有给出结论。",
    edit_answer=(
        "{strategy}：生效的写入 {writes} 次，被拒 {rejected} 次，改动 {files} 个文件，增 {added} 行、删 {removed} 行。"
        "平台重新运行测试：{tests}。哈希链：{chain}。{claim}"
    ),
    cases={"read_first": "读后才写", "path_scope": "路径与范围", "not_unique": "唯一匹配", "line_drift": "行号漂移",
           "stale": "过期检测"},
    case_titles={
        "read_first": "读后才写：没读过或只读一部分，工具拒绝",
        "path_scope": "路径与范围：越界和改测试，工具拒绝",
        "not_unique": "唯一匹配：找不到或出现多次，工具拒绝",
        "line_drift": "行号漂移：写入之后旧行号作废",
        "stale": "过期检测：读后被别人改了，拒绝覆盖",
    },
    extras={
        "escape_absent": "工作区外没有出现 escape.txt",
        "numbers_shifted": "旧行号确实指向了别的行",
        "external_kept": "外部改动的那一行没有被覆盖",
        "chain": "哈希链和预期一致",
    },
    mark_ok="：是",
    mark_bad="：否",
    case_detail="{steps} 步中 {matched} 步与预期一致；{extras}。",
    external_note="运行器模拟的外部修改：它绕过工具直接写了这个文件，工具并不知情。",
    guards_title="五道防护：读后才写、路径、唯一匹配、行号、过期",
    guards_summary=(
        "这一组不调用模型。运行器像一个粗心或赶时间的模型那样提交调用，每一步先写明预期结果，"
        "再对照工具真实返回的 error_type 和文件哈希。被拒绝的调用必须让所有文件保持原样。"
    ),
    guards_columns=("练习段", "工具", "路径", "预期", "实际", "文件未变"),
    label_rejected="被拒绝的调用数",
    label_writes_applied="生效的写入数",
    label_commands_run="执行的命令数",
    guards_answer="运行了 {cases} 段，提交 {calls} 次调用，其中 {rejected} 次被工具拒绝；逐步对照见报告表格。",
)
