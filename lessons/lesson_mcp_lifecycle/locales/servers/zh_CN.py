"""Runtime text of the MCP servers: Simplified Chinese (source language)."""
from lessons.lesson_mcp_lifecycle.locales.servers import Texts

TEXTS = Texts(
    catalog_search_description="按关键词检索馆藏图书，匹配书名、作者和主题。只读，不改任何记录。",
    query_description="检索关键词，例如“工具调用”。",
    limit_description="最多返回几本，1 到 5。",
    get_book_description="按书号读取一本书的详细信息和可借册数。只读。",
    book_id_description="书号，例如 B-101。",
    books={
        "B-101": {"title": "Agent 工具调用实战", "author": "林川", "topic": "工具调用与函数定义"},
        "B-102": {"title": "从零写一个 Agent 循环", "author": "周岚", "topic": "Agent 循环与消息历史"},
        "B-103": {"title": "检索增强生成入门", "author": "陈默", "topic": "检索与来源引用"},
        "B-104": {"title": "协议与服务：MCP 实务", "author": "许宁", "topic": "MCP 服务与工具调用"},
        "B-105": {"title": "评估一个 Agent", "author": "高远", "topic": "评估集与回归"},
    },
    empty_query="检索关键词不能为空。",
    unknown_book="馆藏里没有书号 {book_id}。",
    loans_search_description="按读者证号查询当前借阅记录。只读，不改任何记录。",
    member_id_description="读者证号，例如 M-07。",
    register_description="为读者登记一笔借阅。会改变借阅记录，属于写操作。",
    due_days_description="借期天数，7 到 30。",
    purge_description="清空全部借阅记录。危险的写操作，只供馆员维护使用。",
    renew_description="为一笔借阅续借。会改变借阅记录，属于写操作。",
    loan_id_description="借阅号，例如 L-0001。",
    unknown_member="没有读者证号 {member_id}。",
    no_copies="书号 {book_id} 已经没有可借的册数。",
    unknown_loan="没有借阅号 {loan_id}。",
    info_description="报告服务进程号、启动以来的借阅条数和进程拿到的环境变量名（不含取值）。供宿主诊断用。",
)
