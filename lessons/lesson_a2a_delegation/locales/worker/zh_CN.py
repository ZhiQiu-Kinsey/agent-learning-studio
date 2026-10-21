"""a2a-delegation remote agent text: Simplified Chinese (the source language)."""
from lessons.lesson_a2a_delegation.locales.worker import Texts

TEXTS = Texts(
    agent_description="青石图书馆的资料核对员：在服务手册里为每条说法查找证据片段，标出已被新版取代的旧版本。不判断说法对错。",
    skill_name="查找手册证据",
    skill_description=("输入 1 到 3 条说法（数据部分 claims，每条带 id 和 text），"
                       "为每条返回最多 3 个手册片段；旧版本会换成现行版本并在 superseded 里注明。"),
    skill_examples=("B2 研究证最多能借几册", "周日几点闭馆"),
    status_received="已收到 {count} 条说法，开始在 {chunks} 个手册片段里检索。",
    status_waiting_index="档案索引正在重建，已等待 {seconds} 秒。",
    status_checked="{claim_id} 已核对，找到 {evidence} 个证据片段。",
    status_done="核对完成。",
    status_failed="档案索引损坏，本次无法核对任何说法。",
    status_rejected="消息里没有合法的 claims：需要 1 到 3 条带 id 和 text 的说法，并在 metadata.skill_id 写明技能。",
    status_canceled="已按委派方的要求取消。",
    artifact_summary="为 {count} 条说法找到的手册证据；已被取代的旧版本已注明。",
    superseded_note="{old} 已被 {new} 取代，以现行版本为准。",
)
