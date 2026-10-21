"""langgraph-state offline test model text: Simplified Chinese (the source language)."""
from lessons.lesson_langgraph_state.locales.fixture import Texts

TEXTS = Texts(answer="按课时表，这几课共 {total_minutes} 分钟，每天 {minutes_per_day} 分钟，需要 {days} 天。")
