"""Scripted model text of the offline test model: Simplified Chinese (source language)."""
from lessons.lesson_mcp_lifecycle.locales.fixture import Texts

TEXTS = Texts(
    query="工具调用",
    answer=("已为 M-07 登记借阅 {book}（工具结果确认成功）。随后借阅服务断开，确认查询没有得到结果，"
            "借阅记录可能已随服务重启丢失，请到馆员处核实；我没有重复登记。"),
)
