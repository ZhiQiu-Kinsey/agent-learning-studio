"""课程源码里的代码名。

正文里写到的 evidence、stop、lesson.plan 这类名字来自课程源码。前端据此把它们显示成代码样式，
内容里的 code_notes 再给其中需要的名字挂一条本课说明。名字只从本课登记的源码文件里取，不靠猜。
"""
import ast
import io
import re
import tokenize

# 字符串字面量只收像名字的短值，例如 "stop"、"lesson.plan"、"Final Answer:"、"s-1042"；句子不收。
_LITERAL = re.compile(r"[A-Za-z][\w.-]*(?: [A-Za-z][\w-]*){0,2}")


def names_in_source(text):
    """一个 Python 源文件里的标识符与短字符串字面量；注释和文档字符串不算。"""
    names = set()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return names
    for token in tokens:
        if token.type == tokenize.NAME:
            names.add(token.string)
        elif token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                continue
            if isinstance(value, str):
                value = value.strip().rstrip(":").strip()
                if _LITERAL.fullmatch(value):
                    names.add(value)
    return names


def platform_names():
    """每课都可能提到的平台与协议名字：消息角色、JSON 字面量、运行事件名和运行终态。取自平台常量。"""
    from server.envelope import SPAN_EVENTS
    from server.run_store import FINAL_STATUSES
    return {"system", "user", "assistant", "tool", "true", "false", "null",
            *SPAN_EVENTS, *FINAL_STATUSES}


def code_names(sources, glossary_forms=()):
    """多个源文件的代码名加平台名字，去掉与术语表名称重名的（术语优先，同一个词不会一处是术语一处是代码）。"""
    taken = {form.casefold() for form in glossary_forms}
    names = platform_names()
    for text in sources:
        names |= names_in_source(text)
    return sorted(name for name in names if name.casefold() not in taken)
