"""课程源码里的代码名。

正文里写到的 evidence、stop、lesson.plan 这类名字来自课程源码。前端据此把它们显示成代码样式，
内容里的 code_notes 再给其中需要的名字挂一条本课说明。名字只从本课登记的源码文件里取，不靠猜。

运行时文本（locales/ 下的消息目录）只收标识符和字典键：目录里的字符串值是给模型和学习者看的
自然语言，如英文目录的 "passed"、"none"、"yes"，收进来会让英文正文里的普通词显示成代码。
"""
import ast
import io
import re
import tokenize

# 字符串字面量只收像名字的短值，例如 "stop"、"lesson.plan"、"Final Answer:"、"s-1042"；句子不收。
_LITERAL = re.compile(r"[A-Za-z][\w.-]*(?: [A-Za-z][\w-]*){0,2}")


def names_in_source(text, *, literals=True):
    """一个 Python 源文件里的标识符与短字符串字面量；注释和文档字符串不算。

    literals=False（消息目录）：字符串只收字典键，例如 {"vague": ...} 的 vague，值一律不收。
    """
    if not literals:
        return _identifiers(text) | _dict_keys(text)
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


def _identifiers(text):
    names = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.NAME:
                names.add(token.string)
    except (tokenize.TokenError, SyntaxError):
        pass
    return names


def _dict_keys(text):
    """字典字面量里像名字的字符串键；键是程序用来查找的代码值，不是给人读的文本。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    return {key.value for node in ast.walk(tree) if isinstance(node, ast.Dict) for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and _LITERAL.fullmatch(key.value)}


def platform_names():
    """每课都可能提到的平台与协议名字：消息角色、JSON 字面量、运行事件名和运行终态。取自平台常量。"""
    from server.envelope import SPAN_EVENTS
    from server.run_store import FINAL_STATUSES
    return {"system", "user", "assistant", "tool", "true", "false", "null",
            *SPAN_EVENTS, *FINAL_STATUSES}


def code_names(sources, glossary_forms=(), catalogs=()):
    """多个源文件的代码名加平台名字，去掉与术语表名称重名的（术语优先，同一个词不会一处是术语一处是代码）。

    catalogs 是运行时文本（消息目录）文件，只取标识符与字典键，不取字符串值。
    """
    taken = {form.casefold() for form in glossary_forms}
    names = platform_names()
    for text in sources:
        names |= names_in_source(text)
    for text in catalogs:
        names |= names_in_source(text, literals=False)
    return sorted(name for name in names if name.casefold() not in taken)
