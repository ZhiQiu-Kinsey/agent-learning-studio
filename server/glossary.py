"""术语表单一来源：curriculum/glossary.json。

结构约定（schema_version 1）：
- 术语映射（不可被译文层改动）：id、zh、en、first_lesson。
- 可译文本：definition、aliases。``glossary.{locale}.json`` 按术语 id 覆盖 definition，
  并为该语言提供显示名 term 与别名 aliases（路径见 server/data_overlay.py 的 glossary_slots）；
  缺失或过期的条目回落到源文件：显示名用 en，释义用中文。
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


def public_glossary(root, catalog_index, locale=None):
    """附加显示名与首次出现课程的显示课号；不改变源数据。

    源语言：display 是“中文（English）”。其他语言（如 en）：term 与 display 是该语言的显示名
    （没有译文时用 en），definition 合并译文层，local_aliases 是该语言的别名，
    definition_locale 标出这条释义实际是哪种语言（回落时界面据此标注 lang）。
    中文名、中文别名与 not_in 原样保留，回落成中文的正文仍能匹配术语。
    """
    from server.content import localize  # 延迟导入：content 依赖 curriculum 的错误类型
    from server.data_overlay import glossary_slots

    data = load_glossary(root, catalog_index)
    source = data["locale"]
    localized = bool(locale) and locale != source
    terms = []
    for term in data["terms"]:
        item = {**term, "kind": term.get("kind", "concept"), "aliases": list(term.get("aliases", [])),
                "not_in": list(term.get("not_in", [])), "display": display_label(term)}
        if "first_lesson" in term:
            item["first_lesson_number"] = catalog_index.numbers[term["first_lesson"]]
        if localized:
            item.update(term=term["en"], local_aliases=[])
        terms.append(item)
    if not localized:
        # 源语言不读译文层；每条术语有 term、definition、aliases 三个可译位置。
        info = {"requested": locale or source, "locale": source, "source_language": source,
                "total": 3 * len(terms), "translated": 3 * len(terms), "missing": [], "stale": []}
        return {"schema_version": data["schema_version"], "locale": source, "i18n": info, "terms": terms}
    slots = glossary_slots(terms)
    info = localize(root.joinpath(*GLOSSARY_FILE), slots, locale, source)
    pending = set(info["missing"]) | set(info["stale"])
    for item in terms:
        item["display"] = item["term"]
        item["definition_locale"] = source if f"{item['id']}.definition" in pending else locale
    return {"schema_version": data["schema_version"], "locale": info["locale"], "i18n": info, "terms": terms}
