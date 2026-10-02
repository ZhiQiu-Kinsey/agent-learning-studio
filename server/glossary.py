"""术语表单一来源：curriculum/glossary.json。

结构约定（schema_version 1）：
- 术语映射（不可被译文层改动）：id、zh、en、first_lesson。
- 可译文本：definition、aliases。将来的 ``glossary.{locale}.json`` 只按 id 覆盖这些字段，
  并可为该语言提供 term（显示名）；本模块暂不实现译文合并。
- 显示形式为“中文（English）”；zh 与 en 相同（如 JSON Schema）时只显示一次。
- kind：concept（课程概念，默认）在 first_lesson 那一课写一次中英并列，之后只写中文；
  background（背景词，如分词器）不是课程主线，只靠悬浮卡解释，不设 first_lesson。
"""
import json
import re

from server.curriculum import LessonValidationError, _require

GLOSSARY_FILE = ("curriculum", "glossary.json")
SCHEMA_VERSION = 1
MAPPING_FIELDS = ("id", "zh", "en", "first_lesson", "kind")
TRANSLATABLE_FIELDS = ("definition", "aliases", "not_in")
DEFINITION_MAX_LENGTH = 160
_TERM_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_TERM_FIELDS = {"id", "zh", "en", "definition", "aliases", "not_in", "first_lesson", "kind"}
KINDS = ("concept", "background")
_TOP_FIELDS = {"schema_version", "locale", "terms"}


def _text(value, location, limit=None):
    _require(isinstance(value, str) and bool(value.strip()) and value == value.strip(), location,
             "必须是非空字符串且首尾无空白")
    if limit is not None:
        _require(len(value) <= limit, location, f"不能超过 {limit} 个字符")
    return value


def display_label(term):
    return term["zh"] if term["zh"] == term["en"] else f"{term['zh']}（{term['en']}）"


def validate_glossary(data, catalog_index, location="curriculum/glossary.json"):
    """检查结构、id 唯一、必填字段、名称不冲突，以及 first_lesson 引用已登记课程的 slug。"""
    _require(isinstance(data, dict), location, "必须是对象")
    _require(not set(data) - _TOP_FIELDS, location, "包含未支持的顶层字段")
    _require(type(data.get("schema_version")) is int and data["schema_version"] == SCHEMA_VERSION,
             location, f"schema_version 必须为 {SCHEMA_VERSION}")
    _require(data.get("locale") == "zh-CN", location, "源文件 locale 必须为 zh-CN；其他语言使用译文层")
    terms = data.get("terms")
    _require(isinstance(terms, list) and terms, location, "terms 必须是非空数组")
    ids, names = set(), {}
    for position, term in enumerate(terms):
        where = f"{location}: terms[{position}]"
        _require(isinstance(term, dict), where, "必须是对象")
        _require(not set(term) - _TERM_FIELDS, where, "包含未支持的字段")
        identifier = term.get("id")
        _require(isinstance(identifier, str) and _TERM_ID.fullmatch(identifier) is not None,
                 where + ".id", "必须是 kebab-case，例如 tool-calling")
        _require(identifier not in ids, location, "术语 id 不能重复：" + identifier)
        ids.add(identifier)
        where = f"{location}: terms[{identifier}]"
        _text(term.get("zh"), where + ".zh", 40)
        _text(term.get("en"), where + ".en", 60)
        _text(term.get("definition"), where + ".definition", DEFINITION_MAX_LENGTH)
        aliases = term.get("aliases", [])
        _require(isinstance(aliases, list), where + ".aliases", "必须是字符串数组")
        for alias in aliases:
            _text(alias, where + ".aliases", 40)
        # 中文名与别名在全表唯一，将来正文按名称匹配 term_id 时不会出现歧义。
        own = [term["zh"], *aliases]
        _require(len({name.casefold() for name in own}) == len(own), where + ".aliases", "别名不能重复或与中文名相同")
        for name in own:
            owner = names.get(name.casefold())
            _require(owner is None, where, f"名称「{name}」已被术语 {owner} 使用")
            names[name.casefold()] = identifier
        # 中文没有词边界：not_in 列出含有本术语名字、但意思不同的更长词组，正文里这些词组整体跳过。
        not_in = term.get("not_in", [])
        _require(isinstance(not_in, list), where + ".not_in", "必须是字符串数组")
        for phrase in not_in:
            _text(phrase, where + ".not_in", 40)
            _require(any(name.casefold() in phrase.casefold() and name.casefold() != phrase.casefold()
                         for name in own), where + ".not_in", f"「{phrase}」必须比术语名更长并包含它")
        kind = term.get("kind", "concept")
        _require(kind in KINDS, where + ".kind", "只能是 concept 或 background")
        _require(not (kind == "background" and "first_lesson" in term), where + ".first_lesson",
                 "背景词不是课程主线，不设 first_lesson")
        if "first_lesson" in term:
            first = term["first_lesson"]
            _require(isinstance(first, str), where + ".first_lesson", "必须是课程 slug")
            canonical = catalog_index.resolve(first)
            _require(canonical is not None, where + ".first_lesson", "引用的课程不存在")
            _require(canonical == first, where + ".first_lesson",
                     f"必须使用课程 slug「{canonical}」，不能使用别名")
    return data


def load_glossary(root, catalog_index):
    path = root.joinpath(*GLOSSARY_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise LessonValidationError(f"{path}: 无法读取有效 JSON") from error
    return validate_glossary(data, catalog_index, str(path))


def public_glossary(root, catalog_index):
    """附加显示名与首次出现课程的显示课号；不改变源数据。"""
    data = load_glossary(root, catalog_index)
    terms = []
    for term in data["terms"]:
        item = {**term, "kind": term.get("kind", "concept"), "aliases": list(term.get("aliases", [])),
                "not_in": list(term.get("not_in", [])), "display": display_label(term)}
        if "first_lesson" in term:
            item["first_lesson_number"] = catalog_index.numbers[term["first_lesson"]]
        terms.append(item)
    return {"schema_version": data["schema_version"], "locale": data["locale"], "terms": terms}
