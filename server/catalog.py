"""声明式课程注册：课程规划决定可用性，各课声明自己的实现与教学资源。"""
import json
import keyword
import re
from importlib import import_module
from pathlib import Path, PurePosixPath

# LessonValidationError 定义在 server.curriculum，这里继续导出以保持原有导入路径。
from server.code_reading import compare_target, lesson_code, source_role, validate_code_scene
from server.content import lesson_content_model, load_lesson_content
from server.curriculum import LessonValidationError, _require, index_catalog  # noqa: F401
from server.lesson_refs import check_refs, resolve_refs

ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_FIELDS = {
    "schema_version", "id", "subtitle", "content", "sources", "exercises",
    "runtime", "testing", "ui", "input_defaults",
}
_SOURCE_EXTENSIONS = {".py", ".json", ".md", ".txt", ".ts", ".tsx", ".js", ".jsx"}
_PRIVATE_NAMES = {"local_config", "secrets", "credentials", "credential", "tokens", "token", "api_keys"}


def _object(value, location, allowed=None):
    _require(isinstance(value, dict), location, "必须是对象")
    if allowed is not None:
        _require(not set(value) - allowed, location, "包含未支持的字段")
    return value


def _text(value, location):
    _require(isinstance(value, str) and bool(value.strip()), location, "必须是非空字符串")
    return value


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LessonValidationError(f"{path}: 无法读取有效 JSON") from error


def _safe_file(root, relative, location, *, inside=None, source=False):
    """同时检查声明路径与最终解析位置，拒绝 Windows 路径及符号链接外逃。"""
    _text(relative, location)
    parts = PurePosixPath(relative).parts
    _require("\\" not in relative and ":" not in relative and not relative.startswith("/")
             and all(part not in ("", ".", "..") for part in relative.split("/")),
             location, "必须使用无路径逃逸的相对路径")
    _require(parts and all(not part.startswith(".") and part.casefold() != "__pycache__" for part in parts),
             location, "不能访问隐藏目录、环境目录或缓存")
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve()
    boundary = (inside or root).resolve()
    _require(resolved.is_relative_to(boundary), location, "路径或符号链接超出允许目录")
    _require(candidate.is_file(), location, "文件不存在")
    if source:
        _require(parts[0] in ("lessons", "course") and len(parts) > 1,
                 location, "源码仅允许 lessons/ 与 course/ 内显式声明的文件")
        _require(resolved.is_relative_to((root / parts[0]).resolve())
                 and (root / parts[0]).resolve().is_relative_to(root.resolve()),
                 location, "源码链接超出允许目录")
        _require(candidate.suffix.casefold() in _SOURCE_EXTENSIONS and resolved.suffix.casefold() in _SOURCE_EXTENSIONS,
                 location, "不支持的源码文件类型")
        _require(all(Path(part).stem.casefold() not in _PRIVATE_NAMES for part in parts),
                 location, "不能展示私密配置文件")
        _require(all(Path(part).stem.casefold() not in _PRIVATE_NAMES
                     and not part.startswith(".") for part in resolved.relative_to(root.resolve()).parts),
                 location, "不能通过链接展示私密配置文件")
    return resolved


def _reference(root, module, reference, location, *, callable_required):
    _text(reference, location)
    pieces = reference.split(":")
    _require(len(pieces) == (2 if callable_required else 1), location,
             "使用本课 module:function" if callable_required else "使用本课模块名")
    names = pieces[0].split(".")
    _require(all(name.isascii() and name.isidentifier() and not keyword.iskeyword(name) for name in names),
             location, "模块必须位于课程自身包内")
    if callable_required:
        _require(pieces[1].isascii() and pieces[1].isidentifier() and not keyword.iskeyword(pieces[1]),
                 location, "函数名无效")
    relative = "lessons/" + module + "/" + "/".join(names) + ".py"
    _safe_file(root, relative, location, inside=root / "lessons" / module)
    return reference


def _manifest(root, path, catalog_lesson):
    data = _object(_json(path), path, _MANIFEST_FIELDS)
    _require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
             path, "schema_version 必须为 1")
    module = path.parent.name
    _require(module.isascii() and module.isidentifier(), path, "课程目录必须是有效 Python 包名")
    _require(path.resolve().is_relative_to((root / "lessons").resolve())
             and (root / "lessons").resolve().is_relative_to(root), path, "课程声明超出 lessons/ 目录")
    subtitle = _text(data.get("subtitle", catalog_lesson["summary"]), str(path) + ": subtitle")
    content_relative = _text(data.get("content"), str(path) + ": content")
    content_path = _safe_file(root / "lessons" / module, content_relative, str(path) + ": content")
    sources = data.get("sources")
    _require(isinstance(sources, list) and sources, path, "sources 必须显式列出教学源码")
    source_paths = set()
    for source in sources:
        _object(source, str(path) + ": sources", {"path", "language"})
        _safe_file(root, source.get("path"), str(path) + ": sources.path", source=True)
        _require(source["path"] not in source_paths, path, "sources.path 不能重复")
        source_paths.add(source["path"])
        _text(source.get("language"), str(path) + ": sources.language")
    exercises = data.get("exercises")
    _require(isinstance(exercises, list) and exercises, path, "exercises 必须包含至少一个实验")
    exercise_ids = set()
    for exercise in exercises:
        _object(exercise, str(path) + ": exercises", {"id", "title", "question", "offline_only", "inputs"})
        for key in ("id", "title", "question"):
            _text(exercise.get(key), str(path) + ": exercises." + key)
        _require(exercise["id"] not in exercise_ids, path, "同一课程的 exercise.id 不能重复")
        exercise_ids.add(exercise["id"])
        _require(type(exercise.get("offline_only", False)) is bool, path, "offline_only 必须为布尔值")
        _object(exercise.get("inputs", {}), str(path) + ": exercises.inputs")
    runtime = _object(data.get("runtime"), str(path) + ": runtime",
                      {"kind", "entrypoint", "max_rounds", "requires_model"})
    kind = runtime.get("kind")
    _require(kind in ("native", "custom"), path, "runtime.kind 必须为 native 或 custom")
    _reference(root, module, runtime.get("entrypoint"), str(path) + ": runtime.entrypoint", callable_required=kind == "custom")
    runtime = {"max_rounds": 3, "requires_model": True, **runtime}
    _require(type(runtime["max_rounds"]) is int and 1 <= runtime["max_rounds"] <= 100,
             path, "max_rounds 必须为 1 到 100 的整数")
    _require(type(runtime["requires_model"]) is bool, path, "requires_model 必须为布尔值")
    _require(kind != "native" or runtime["requires_model"], path, "native 运行器必须声明 requires_model=true")
    testing = _object(data.get("testing", {}), str(path) + ": testing", {"completion_factory"})
    _require(not runtime["requires_model"] or "completion_factory" in testing,
             path, "模型课程必须声明 testing.completion_factory")
    if "completion_factory" in testing:
        _reference(root, module, testing["completion_factory"], str(path) + ": testing.completion_factory", callable_required=True)
    ui = _object(data.get("ui", {}), str(path) + ": ui", {"guide", "lab", "inspector", "question_label", "question_help"})
    for key, value in ui.items():
        if key in {"question_label", "question_help"}:
            _require(isinstance(value, str) and 0 < len(value.strip()) <= 300, path, f"ui.{key} 必须为 1–300 字符的说明")
        else:
            _require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]*", value), path, f"ui.{key} 必须为扩展键")
    defaults = _object(data.get("input_defaults", {}), str(path) + ": input_defaults")
    content_model = lesson_content_model(content_path, {"id": data["id"], "subtitle": subtitle, "exercises": exercises})
    # 读码批注必须对准本课白名单源码中真实存在的行。
    validate_code_scene(content_model, sources,
                        lambda relative: _safe_file(root, relative, str(path) + ": sources.path",
                                                    source=True).read_text(encoding="utf-8"),
                        str(content_path))
    return {"id": data["id"], "number": catalog_lesson["number"], "aliases": list(catalog_lesson.get("aliases", [])),
            "title": catalog_lesson["title"], "description": catalog_lesson["summary"],
            "objectives": catalog_lesson["objectives"], "subtitle": subtitle, "exercises": exercises,
            "runtime": runtime, "testing": testing, "ui": ui, "input_defaults": defaults,
            "status": catalog_lesson["status"], "available": catalog_lesson["status"] == "available",
            "capabilities": {"requires_model": runtime["requires_model"], "custom_runtime": kind == "custom", "supports_inputs": kind == "custom"},
            "root": root, "module": module, "package": "lessons." + module,
            "content": content_relative, "content_path": content_path, "sources": sources,
            "code_compare": compare_target(content_model)}


def load_lessons(root=ROOT, curriculum=None, *, include_planned=False):
    """按课程规划顺序加载声明；计划中的实现也校验，但默认不会获得执行权限。

    映射规则：lessons/*/lesson.json 的 id 必须等于 catalog 中的课程 slug（不能写别名）；
    目录名只决定 Python 包名，不参与课程身份判断。
    """
    root = Path(root).resolve()
    curriculum = _object(curriculum if curriculum is not None else _json(root / "curriculum" / "catalog.json"), "curriculum")
    index = index_catalog(curriculum)
    # 目录正文里提到其他课一律写 {{lesson:<slug>}}，课号在读取时计算。
    check_refs(curriculum, index.numbers, "curriculum")
    catalog = {}
    for identifier in index.order:
        entry = index.entries[identifier]
        _require(entry.get("status") in ("available", "planned"), "curriculum", "课程状态必须为 available 或 planned")
        _text(entry.get("title"), "curriculum.lessons.title")
        _text(entry.get("summary"), "curriculum.lessons.summary")
        objectives = entry.get("objectives")
        _require(isinstance(objectives, list) and objectives, "curriculum", "objectives 必须为非空数组")
        for objective in objectives:
            _text(objective, "curriculum.lessons.objectives")
        catalog[identifier] = {**entry, "number": index.numbers[identifier], "aliases": index.aliases(identifier)}
    found = {}
    for path in sorted((root / "lessons").glob("lesson_*/lesson.json")):
        declaration = _object(_json(path), path)
        identifier = _text(declaration.get("id"), str(path) + ": id")
        canonical = index.resolve(identifier)
        _require(canonical is None or canonical == identifier, path,
                 f"id 必须使用课程 slug「{canonical}」，不能使用别名")
        _require(identifier in catalog, path, "课程 id 未登记在 curriculum/catalog.json")
        _require(identifier not in found, path, "课程实现 id 重复")
        found[identifier] = _manifest(root, path, catalog[identifier])
        check_refs(_json(found[identifier]["content_path"]), index.numbers, str(found[identifier]["content_path"]))
    for identifier, entry in catalog.items():
        _require(entry["status"] != "available" or identifier in found,
                 "curriculum lesson " + identifier, "available 课程缺少 lessons/lesson_*/lesson.json 实现声明")
    for identifier, spec in found.items():
        target = spec["code_compare"]
        if target is not None:
            # whats-new 的对比课可以写 slug 或别名，但必须是另一门已有实现的课程。
            canonical = index.resolve(target)
            _require(canonical in found and canonical != identifier, str(spec["content_path"]),
                     f"whats-new.compare_with「{target}」必须引用另一门已有实现的课程")
            spec["code_compare"] = canonical
    return [found[identifier] for identifier in catalog if identifier in found
            and (include_planned or found[identifier]["available"])]


LESSONS = load_lessons()


CATALOG_INDEX = index_catalog(_json(ROOT / "curriculum" / "catalog.json"))


def lesson_spec(lesson_id):
    """按 slug 或别名查找可执行课程；返回的 spec["id"] 始终是 slug。"""
    if not isinstance(lesson_id, str):
        return None
    return next((item for item in LESSONS if lesson_id == item["id"] or lesson_id in item["aliases"]), None)


def catalog_lesson(lesson_id):
    """按 slug 或别名查找目录登记（含 planned）；用于区分“未开放”和“不存在”。"""
    slug = CATALOG_INDEX.resolve(lesson_id)
    return None if slug is None else {**CATALOG_INDEX.entries[slug], "number": CATALOG_INDEX.numbers[slug]}


def public_lesson(spec, locale=None):
    public = {key: spec[key] for key in ("id", "number", "aliases", "title", "description", "objectives", "subtitle",
                                         "exercises", "available", "ui", "capabilities", "input_defaults")}
    return resolve_refs(public, CATALOG_INDEX.numbers, locale)


def lesson_runtime(spec):
    reference = spec["runtime"]["entrypoint"]
    return import_module(spec["package"] + "." + reference.split(":", 1)[0])


def lesson_callable(spec, reference):
    """加载已验证的本课函数；不能借声明导入其他课或任意系统模块。"""
    _reference(spec["root"], spec["module"], reference, "lesson callable", callable_required=True)
    module_name, function_name = reference.split(":")
    function = getattr(import_module(spec["package"] + "." + module_name), function_name, None)
    _require(callable(function), "lesson " + spec["id"], "声明的入口函数不存在或不可调用")
    return function


def lesson_code_view(spec, locale=None):
    """读码场景数据：只读本课 sources 白名单，批注取自已合并译文层的内容。"""
    content_path = _safe_file(spec["root"] / "lessons" / spec["module"], spec["content"], "lesson content")
    learning, info = load_lesson_content(content_path, spec, locale)
    return lesson_code(spec, LESSONS, resolve_refs(learning, CATALOG_INDEX.numbers, info["locale"]))


def lesson_detail(spec, locale=None):
    from course.execution import validate_inputs
    module = lesson_runtime(spec)
    content_path = _safe_file(spec["root"] / "lessons" / spec["module"], spec["content"], "lesson content")
    sources = []
    for source in spec["sources"]:
        path = _safe_file(spec["root"], source["path"], "lesson sources", source=True)
        sources.append({**source, "role": source_role(source["path"]), "content": path.read_text(encoding="utf-8")})
    # Publish actual validated presets, including model defaults, so the parameter
    # editor shows every value the lesson will receive rather than hidden values.
    learning, learning_i18n = load_lesson_content(content_path, spec, locale)
    exercises = [{**exercise, "inputs": validate_inputs(module, {**spec["input_defaults"], **exercise.get("inputs", {})})}
                 for exercise in spec["exercises"]]
    # 自定义运行器的输入模型导出 JSON Schema，前端据此生成参数控件；最终仍由后端校验。
    input_model = getattr(module, "INPUT_MODEL", None)
    input_schema = input_model.model_json_schema() if spec["capabilities"]["supports_inputs"] and input_model else None
    learning = resolve_refs(learning, CATALOG_INDEX.numbers, learning_i18n["locale"])
    return {**public_lesson(spec, learning_i18n["locale"]), "exercises": exercises, "input_schema": input_schema,
            "system_prompt": getattr(module, "SYSTEM_PROMPT", ""),
            "tools": getattr(module, "TOOLS", []), "learning": learning, "learning_i18n": learning_i18n,
            "sources": sources, "code_names": lesson_code_names(spec, sources)}


def lesson_code_names(spec, sources=None):
    """正文里按代码显示的名字：取自本课登记的 Python 源码，去掉与术语表重名的。"""
    from server.code_names import code_names
    from server.glossary import load_glossary
    if sources is None:
        sources = [{**source, "content": _safe_file(spec["root"], source["path"], "lesson sources", source=True)
                    .read_text(encoding="utf-8")} for source in spec["sources"]]
    try:
        terms = load_glossary(spec["root"], CATALOG_INDEX)["terms"]
    except (LessonValidationError, OSError):
        terms = []  # 术语表缺失或损坏时课程照常打开，只是代码名不扣除术语
    forms = [form for term in terms for form in (term["zh"], term["en"], *term.get("aliases", []))]
    return code_names([source["content"] for source in sources if source["language"] == "python"], forms)

