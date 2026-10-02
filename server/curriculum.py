"""完整课程规划的唯一数据源；目录登记不代表已实现可执行课程。

课程 ID 规则：
- 每课的主 ID 是稳定的 kebab-case slug（如 ``tool-selection``），对外接口一律返回 slug。
- ``aliases`` 只保存改名前的旧 slug，用于解析旧链接、旧请求和旧存储；别名不得与任何 slug 或其他别名重复。
  不接受数字别名：数字会和按目录顺序计算的显示课号混淆（插入新课后，旧数字指向的课程与显示课号不再一致）。
- 显示课号（``number``）由 ``lessons`` 数组的目录顺序计算，从 1 开始，不在 JSON 中手写。
- 目录内对课程的引用（模块 ``lesson_ids``、``prerequisites``、选修先修）一律写 slug。
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "curriculum" / "catalog.json"
SLUG_MAX_LENGTH = 48
_SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
# 别名只能是改名前的旧 slug；数字会和显示课号混淆，不再接受。
_ALIAS = _SLUG


class LessonValidationError(ValueError):
    """课程声明错误；消息定位到文件及字段，不展示文件内容。"""


def _require(condition, location, message):
    if not condition:
        raise LessonValidationError(f"{location}: {message}")


def is_slug(value):
    return isinstance(value, str) and len(value) <= SLUG_MAX_LENGTH and _SLUG.fullmatch(value) is not None


@dataclass(frozen=True)
class CatalogIndex:
    """校验后的课程身份索引：slug 顺序、显示课号与 slug/别名查找表。"""
    order: tuple
    entries: dict
    numbers: dict
    lookup: dict = field(repr=False)

    def resolve(self, identifier):
        """把 slug 或别名解析为 slug；未知或非字符串返回 None。"""
        return self.lookup.get(identifier) if isinstance(identifier, str) else None

    def aliases(self, slug):
        return list(self.entries[slug].get("aliases", []))


def _reference(index_lookup, slugs, value, location):
    """目录内引用必须写 slug；误写别名时提示应改成哪个 slug。"""
    if value in slugs:
        return value
    canonical = index_lookup.get(value) if isinstance(value, str) else None
    _require(canonical is None, location, f"引用必须使用课程 slug「{canonical}」，不能使用别名")
    _require(False, location, "引用的课程不存在")


def index_catalog(catalog, location="curriculum"):
    """校验课程身份（slug、别名、先修、层级）并建立索引；标题等教学字段由调用方校验。"""
    _require(isinstance(catalog, dict), location, "必须是对象")
    entries = catalog.get("lessons")
    _require(isinstance(entries, list), location, "lessons 必须是数组")
    order, by_slug, lookup = [], {}, {}
    for position, entry in enumerate(entries):
        where = f"{location}.lessons[{position}]"
        _require(isinstance(entry, dict), where, "必须是对象")
        identifier = entry.get("id")
        _require(isinstance(identifier, str) and identifier.strip(), where + ".id", "必须是非空字符串")
        _require(is_slug(identifier), where + ".id",
                 f"课程 id 必须是不超过 {SLUG_MAX_LENGTH} 字符的 kebab-case slug，例如 tool-selection")
        _require(identifier not in by_slug, location, "课程 id 不能重复：" + identifier)
        _require(identifier not in lookup, location, f"课程 id「{identifier}」与已有别名冲突")
        aliases = entry.get("aliases", [])
        _require(isinstance(aliases, list), where + ".aliases", "必须是字符串数组")
        for alias in aliases:
            _require(isinstance(alias, str) and _ALIAS.fullmatch(alias) is not None, where + ".aliases",
                     "别名必须是 kebab-case slug（改名前的旧 slug），不能是数字")
            _require(alias != identifier, where + ".aliases", "别名不能与本课 slug 相同")
            _require(alias not in lookup, location, f"别名「{alias}」与其他课程 slug 或别名冲突")
            lookup[alias] = identifier
        order.append(identifier)
        by_slug[identifier] = entry
        lookup[identifier] = identifier
    numbers = {slug: number for number, slug in enumerate(order, 1)}
    slugs = set(order)
    for slug in order:
        prerequisites = by_slug[slug].get("prerequisites", [])
        where = f"{location}.lessons[{slug}].prerequisites"
        _require(isinstance(prerequisites, list), where, "必须是数组")
        targets = []
        for prerequisite in prerequisites:
            target = _reference(lookup, slugs, prerequisite, where)
            _require(target not in targets, where, "先修不能重复")
            targets.append(target)
            # 先修只能指向目录中更靠前的课程，既保证可学顺序，也排除循环依赖。
            _require(numbers[target] < numbers[slug], where, f"先修「{target}」必须排在本课之前")
    if "categories" in catalog:
        _check_hierarchy(catalog["categories"], by_slug, order, lookup, location)
    for position, elective in enumerate(catalog.get("electives", [])):
        where = f"{location}.electives[{position}].prerequisites"
        _require(isinstance(elective, dict), where, "选修必须是对象")
        prerequisites = elective.get("prerequisites", [])
        _require(isinstance(prerequisites, list), where, "必须是数组")
        for prerequisite in prerequisites:
            _reference(lookup, slugs, prerequisite, where)
    return CatalogIndex(tuple(order), by_slug, numbers, lookup)


def _check_hierarchy(categories, by_slug, order, lookup, location):
    """大类→模块→课程的遍历顺序必须与 lessons 顺序一致，导航与显示课号才不会错位。"""
    _require(isinstance(categories, list), location + ".categories", "必须是数组")
    slugs = set(order)
    traversal, module_ids = [], set()
    for category in categories:
        _require(isinstance(category, dict) and isinstance(category.get("modules"), list),
                 location + ".categories", "每个大类必须包含 modules 数组")
        for module in category["modules"]:
            _require(isinstance(module, dict), f"{location}.categories[{category.get('id')}]", "模块必须是对象")
            where = f"{location}.categories[{category.get('id')}].modules[{module.get('id')}]"
            _require(module.get("id") not in module_ids, where, "模块 id 不能重复")
            module_ids.add(module.get("id"))
            lesson_ids = module.get("lesson_ids")
            _require(isinstance(lesson_ids, list), where + ".lesson_ids", "必须是数组")
            for lesson_id in lesson_ids:
                slug = _reference(lookup, slugs, lesson_id, where + ".lesson_ids")
                entry = by_slug[slug]
                _require(entry.get("category_id", category.get("id")) == category.get("id")
                         and entry.get("module_id", module.get("id")) == module.get("id"),
                         where, f"课程「{slug}」的 category_id/module_id 与所在模块不一致")
                traversal.append(slug)
    _require(sorted(traversal) == sorted(order), location + ".categories", "每课必须且只能登记在一个模块中")
    _require(traversal == order, location + ".categories",
             "模块中的课程顺序必须与 lessons 顺序一致；显示课号按 lessons 顺序计算")


def load_curriculum():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def public_curriculum():
    """附加计算出的显示课号；local_path 只供本机调研，不公开。"""
    catalog = load_curriculum()
    index = index_catalog(catalog)
    for lesson in catalog["lessons"]:
        lesson["number"] = index.numbers[lesson["id"]]
        lesson.setdefault("aliases", [])
    for source in catalog["sources"]:
        source.pop("local_path", None)
    from server.lesson_refs import resolve_refs  # 延迟导入：lesson_refs 依赖本模块的错误类型
    return resolve_refs(catalog, index.numbers)


def roadmap():
    catalog = load_curriculum()
    planned_categories = {lesson["category_id"] for lesson in catalog["lessons"]
                          if lesson["status"] == "planned"}
    return [{"id": category["id"], "title": category["title"],
             "description": category["description"], "available": False}
            for category in catalog["categories"] if category["id"] in planned_categories]
