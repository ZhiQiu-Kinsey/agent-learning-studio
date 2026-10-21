"""human-in-the-loop offline test model text: Simplified Chinese."""
from lessons.lesson_human_in_the_loop.locales.fixture import Texts

TEXTS = Texts(
    draft="练习：{topic}\n\n写一个函数，输入一组数字，返回其中的偶数；输入为空时返回空列表。再写两个测试，一个正常输入，一个空输入。",
    receipt="练习《{title}》的保存结果是 {status}，练习库里这个操作有 {rows} 行。",
    edit_title_suffix="（已改）",
    edit_note="把难度改成挑战，标题加了标记",
)
