"""async-concurrency offline script text: Chinese (source language)."""
from lessons.lesson_async_concurrency.locales.fixture import Texts

TEXTS = Texts(
    summaries={
        "messages-context": "每次请求都要带上完整的消息历史，工具调用和工具结果要成对。",
        "application-state": "状态由程序保存，模型只看到程序放进上下文的部分。",
        "context-budget": "上下文有上限，超出预算时先留系统提示词和最近的消息。",
        "prompt-caching": "把不变的内容放在请求最前面，才能命中缓存。",
    },
)
