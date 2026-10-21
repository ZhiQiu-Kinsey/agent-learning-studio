"""agentic-rag 离线测试脚本的文字：中文。"""
from lessons.lesson_agentic_rag.locales.fixtures import Texts

TEXTS = Texts(
    hop_one="B2 研究证 研讨室 楼层",
    hop_two="三楼研究区几点关闭",
    no_answer_queries=("停车场", "停车场", "图书馆 停车 车位"),
    answer_complete=("持 B2 研究证的读者可以预约三楼的研讨室（R-301 至 R-303、R-305）。三楼研究区工作日 20:00 关闭，"
                     "周末与全馆同时关闭。2025 年版写的是工作日 19:30 关闭，已被 2026-03 版取代。"),
    answer_first_hop="持 B2 研究证的读者可以预约三楼的研讨室（R-301 至 R-303、R-305）。检索结果里没有三楼的关闭时间。",
    missing_first_hop="三楼几点关门",
    answer_none="手册里没有找到关于停车场的内容，无法回答。",
    missing_none="图书馆是否有停车场",
)
