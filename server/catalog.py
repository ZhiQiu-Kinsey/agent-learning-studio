"""声明式课程注册：课程规划决定可用性，各课声明自己的实现与教学资源。"""
import json
import keyword
import logging
import re
from importlib import import_module
from pathlib import Path, PurePosixPath

from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE, module_name, resolve_locale
# LessonValidationError 定义在 server.curriculum，这里继续导出以保持原有导入路径。
from server.code_reading import compare_target, lesson_code, source_role, validate_code_scene
from server.content import lesson_content_model, load_lesson_content
from server.curriculum import LessonValidationError, _require, index_catalog  # noqa: F401
from server.lesson_refs import check_refs, resolve_refs
from server.outline import check_details, enrich

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


_CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")


def _runtime_locales(value, location):
    """runtime.locales：本课的运行语言，必须含源语言 zh-CN，且都在平台支持的运行语言里。"""
    _require(isinstance(value, list) and value and all(isinstance(item, str) for item in value)
             and len(set(value)) == len(value), location, "必须是不重复的语言代码数组")
    _require(SOURCE_LOCALE in value, location, f"必须包含源语言 {SOURCE_LOCALE}")
    unknown = [item for item in value if item not in RUNTIME_LOCALES]
    _require(not unknown, location, f"不支持的运行语言 {unknown}；平台支持 {list(RUNTIME_LOCALES)}")
    # 按平台顺序保存：源语言在前，各处列举语言时顺序一致。
    return [locale for locale in RUNTIME_LOCALES if locale in value]


def _check_source_locales(sources, locales, location):
    """运行时文本目录（locales/ 及其子目录下的文件）的登记规则。

    - zh_CN.py、en.py 这类语言文件必须写 locale，且与文件名一致；运行时读取的其他文本数据（如 Markdown 手册）
      同样按语言放进 locales/ 下的子目录，写成 zh_CN.md、en.md；其他文件不能写 locale；
    - 同一个 locales/ 目录登记了语言文件时，本课的每种运行语言都要有一份，读码页切换语言时总有对应文件。
    """
    groups: dict[str, set[str]] = {}
    for source in sources:
        parts = source["path"].split("/")
        locale = source.get("locale")
        texts_file = source_role(source["path"]) == "texts" and parts[-1] != "__init__.py"
        if not texts_file:
            _require(locale is None, location, f"{source['path']} 不是语言文件，不能写 locale")
            continue
        _require(locale in locales, location, f"{source['path']} 必须写 locale，且是本课的运行语言 {locales}")
        _require(parts[-1].rsplit(".", 1)[0] == module_name(locale), location,
                 f"{source['path']} 的文件名应为 {module_name(locale)}.<扩展名>（与 locale「{locale}」一致）")
        groups.setdefault("/".join(parts[:-1]), set()).add(locale)
    for directory, found in groups.items():
        _require(found == set(locales), location,
                 f"{directory}/ 只登记了 {sorted(found)}，本课的每种运行语言 {locales} 都要登记一份")


def _preset(value, locales, location, *, text=False):
    """练习问题与预设输入：标量，或按运行语言分别填写的 {"zh-CN": ..., "en": ...}。

    支持多种运行语言的课里，含中文的字符串必须按语言分别填写，否则英文运行会发出中文。
    """
    if isinstance(value, dict):
        _require(set(value) == set(locales), location, f"按语言填写时，键必须恰好是本课的运行语言 {locales}")
        for locale, item in value.items():
            _preset_scalar(item, f"{location}.{locale}", text)
        return
    _preset_scalar(value, location, text)
    _require(len(locales) == 1 or not (isinstance(value, str) and _CJK.search(value)), location,
             f"本课支持 {locales}，自然语言预设要按语言分别填写")


def _preset_scalar(value, location, text):
    if text:
        _text(value, location)
    _require(value is None or isinstance(value, (str, int, float, bool)), location,
             "必须是字符串、数字、布尔值或 null")


def localized(value, locale):
    """按运行语言取预设值：{"zh-CN": ..., "en": ...} 取该语言那一项，标量原样返回。"""
    return value[locale] if isinstance(value, dict) else value


def _exercise_in(exercise, locale):
    result = {**exercise, "question": localized(exercise["question"], locale)}
    if "inputs" in exercise:
        result["inputs"] = {name: localized(value, locale) for name, value in exercise["inputs"].items()}
    return result


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
    runtime = _object(data.get("runtime"), str(path) + ": runtime",
                      {"kind", "entrypoint", "max_rounds", "requires_model", "locales"})
    locales = _runtime_locales(runtime.get("locales", [SOURCE_LOCALE]), str(path) + ": runtime.locales")
    sources = data.get("sources")
    _require(isinstance(sources, list) and sources, path, "sources 必须显式列出教学源码")
    source_paths = set()
    for source in sources:
        _object(source, str(path) + ": sources", {"path", "language", "locale"})
        _safe_file(root, source.get("path"), str(path) + ": sources.path", source=True)
        _require(source["path"] not in source_paths, path, "sources.path 不能重复")
        source_paths.add(source["path"])
        _text(source.get("language"), str(path) + ": sources.language")
    _check_source_locales(sources, locales, str(path) + ": sources")
    exercises = data.get("exercises")
    _require(isinstance(exercises, list) and exercises, path, "exercises 必须包含至少一个实验")
    exercise_ids = set()
    for exercise in exercises:
        _object(exercise, str(path) + ": exercises",
                {"id", "title", "question", "offline_only", "requires_model", "requires_embedding", "inputs"})
        for key in ("id", "title"):
            _text(exercise.get(key), str(path) + ": exercises." + key)
        _require(exercise["id"] not in exercise_ids, path, "同一课程的 exercise.id 不能重复")
        exercise_ids.add(exercise["id"])
        where = f"{path}: exercises[{exercise['id']}]"
        _preset(exercise.get("question"), locales, where + ".question", text=True)
        _require(type(exercise.get("offline_only", False)) is bool, path, "offline_only 必须为布尔值")
        _require(type(exercise.get("requires_model", True)) is bool, path, "exercise.requires_model 必须为布尔值")
        _require(type(exercise.get("requires_embedding", False)) is bool, path,
                 "exercise.requires_embedding 必须为布尔值")
        for name, value in _object(exercise.get("inputs", {}), where + ".inputs").items():
            _preset(value, locales, f"{where}.inputs.{name}")
    kind = runtime.get("kind")
    _require(kind in ("native", "custom"), path, "runtime.kind 必须为 native 或 custom")
    _reference(root, module, runtime.get("entrypoint"), str(path) + ": runtime.entrypoint", callable_required=kind == "custom")
    runtime = {"max_rounds": 3, "requires_model": True, **runtime, "locales": locales}
    _require(type(runtime["max_rounds"]) is int and 1 <= runtime["max_rounds"] <= 100,
             path, "max_rounds 必须为 1 到 100 的整数")
    _require(type(runtime["requires_model"]) is bool, path, "requires_model 必须为布尔值")
    _require(kind != "native" or runtime["requires_model"], path, "native 运行器必须声明 requires_model=true")
    # 单个练习可以不调用模型（如运行器构造的故障注入），只在独立运行器里由课程代码分流。
    _require(kind == "custom" or all(exercise.get("requires_model", True) for exercise in exercises),
             path, "只有 custom 运行器的练习可以声明 requires_model=false")
    # stream_factory 给 context.complete_stream 提供确定性分块；approval_factory 给 context.request_approval
    # 提供确定性决定。两者都只在离线测试模式使用，学生网页没有入口。
    testing = _object(data.get("testing", {}), str(path) + ": testing",
                      {"completion_factory", "embedding_factory", "stream_factory", "approval_factory"})
    # Embedding 与流式请求也是模型调用：只做 Embedding（或只发流式请求）的课可以只声明对应的夹具。
    _require(not runtime["requires_model"]
             or any(name in testing for name in ("completion_factory", "embedding_factory", "stream_factory")),
             path, "模型课程必须声明 testing.completion_factory（只用 Embedding 的课声明 testing.embedding_factory，"
                   "只发流式请求的课声明 testing.stream_factory）")
    for factory in ("completion_factory", "embedding_factory", "stream_factory", "approval_factory"):
        if factory in testing:
            _reference(root, module, testing[factory], f"{path}: testing.{factory}", callable_required=True)
    # 要不要 Embedding（server/app.py 据此在真实模式先检查配置）：练习可以显式声明 requires_embedding，
    # 没写时，调用模型的练习跟随课程是否声明 embedding_factory。不调用模型的练习不能要求 Embedding。
    for exercise in exercises:
        calls_model = exercise.get("requires_model", runtime["requires_model"])
        if exercise.get("requires_embedding"):
            _require("embedding_factory" in testing, path,
                     f"exercises[{exercise['id']}] 要求 Embedding，课程必须声明 testing.embedding_factory")
            _require(calls_model, path, f"exercises[{exercise['id']}] 不调用模型，不能要求 Embedding")
    ui = _object(data.get("ui", {}), str(path) + ": ui", {"guide", "lab", "inspector", "question_label", "question_help"})
    for key, value in ui.items():
        if key in {"question_label", "question_help"}:
            _require(isinstance(value, str) and 0 < len(value.strip()) <= 300, path, f"ui.{key} 必须为 1–300 字符的说明")
        else:
            _require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]*", value), path, f"ui.{key} 必须为扩展键")
    defaults = _object(data.get("input_defaults", {}), str(path) + ": input_defaults")
    for name, value in defaults.items():
        _preset(value, locales, f"{path}: input_defaults.{name}")
    # 练习问题与预设输入按运行语言各存一份；spec["exercises"] 与 spec["input_defaults"] 是源语言那份。
    presets = {locale: {"exercises": [_exercise_in(exercise, locale) for exercise in exercises],
                        "input_defaults": {name: localized(value, locale) for name, value in defaults.items()}}
               for locale in locales}
    exercises, defaults = presets[SOURCE_LOCALE]["exercises"], presets[SOURCE_LOCALE]["input_defaults"]
    content_model = lesson_content_model(content_path, {"id": data["id"], "subtitle": subtitle, "exercises": exercises})
    # 读码批注必须对准本课白名单源码中真实存在的行。
    validate_code_scene(content_model, sources,
                        lambda relative: _safe_file(root, relative, str(path) + ": sources.path",
                                                    source=True).read_text(encoding="utf-8"),
                        str(content_path))
    return {"id": data["id"], "number": catalog_lesson["number"], "aliases": list(catalog_lesson.get("aliases", [])),
            "title": catalog_lesson["title"], "description": catalog_lesson["summary"],
            "objectives": catalog_lesson["objectives"], "subtitle": subtitle, "exercises": exercises,
            "runtime": runtime, "testing": testing, "ui": ui, "input_defaults": defaults, "presets": presets,
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
    # 目录、导学和课程文件里提到其他课一律写 {{lesson:<slug>}}，课号在读取时计算。
    check_refs(curriculum, index.numbers, "curriculum")
    onboarding = root / "curriculum" / "onboarding.json"
    if onboarding.is_file():
        check_refs(_json(onboarding), index.numbers, str(onboarding))
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
        check_details(entry, f"curriculum.lessons[{identifier}]")
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
        check_refs(declaration, index.numbers, str(path))
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


_manifest_cache: dict = {}


def _manifest_text(spec):
    """实现清单里可译的那几项（按文件修改时间缓存）。"""
    path = spec["root"] / "lessons" / spec["module"] / "lesson.json"
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _manifest_cache:
        if len(_manifest_cache) > 256:
            _manifest_cache.clear()
        _manifest_cache[key] = _json(path)
    raw = _manifest_cache[key]
    return path, {name: raw[name] for name in ("subtitle", "exercises", "ui") if name in raw}


def localized_manifest(spec, locale=None, exercises=None):
    """返回（subtitle, exercises, ui, 语言信息）：合并 lesson.<locale>.json，只换标题与说明文字。

    exercises 默认是源语言的练习（问题与预设输入）；subtitle 为 None 表示清单没写，沿用目录简介。
    """
    import copy

    from server.content import localize
    from server.data_overlay import manifest_slots

    path, raw = _manifest_text(spec)
    text = copy.deepcopy(raw)
    info = localize(path, manifest_slots(text), locale, finish=_refs_in(locale))
    titles = {exercise["id"]: exercise["title"] for exercise in text.get("exercises", [])}
    exercises = [{**exercise, "title": titles.get(exercise["id"], exercise["title"])}
                 for exercise in (spec["exercises"] if exercises is None else exercises)]
    ui = {**spec["ui"], **{key: value for key, value in text.get("ui", {}).items()
                           if key in ("question_label", "question_help")}}
    return text.get("subtitle"), exercises, ui, info


def run_locale(spec, requested=None):
    """本课一次运行用的语言：请求的语言在本课 runtime.locales 里就用它，否则按 course/i18n.py 的规则回落。"""
    return resolve_locale(requested, spec["runtime"].get("locales", [SOURCE_LOCALE]))


def lesson_presets(spec, locale):
    """（练习, input_defaults）：问题与自然语言预设输入取运行语言 locale 那一份。

    不是由 load_lessons 生成的 spec（测试里手写的）没有 presets，按只有源语言处理。
    """
    if "presets" not in spec:
        return spec["exercises"], spec.get("input_defaults", {})
    entry = spec["presets"][locale]
    return entry["exercises"], entry["input_defaults"]


def lesson_sources(spec, locale):
    """本课在运行语言 locale 下展示的源码：不分语言的文件，加上该语言的运行时文本文件。"""
    return [source for source in spec["sources"] if source.get("locale") in (None, locale)]


_catalog_cache: dict = {}


def localized_entries(locale=None):
    """{slug: 已合并译文的目录条目}；目录或译文文件变化时重新读取。"""
    from server.content import overlay_path
    from server.curriculum import CATALOG_PATH, public_curriculum

    files = [CATALOG_PATH] + ([overlay_path(CATALOG_PATH, locale)] if locale else [])
    key = (locale, tuple((file.stat().st_mtime_ns, file.stat().st_size) if file.is_file() else None
                         for file in files))
    if key not in _catalog_cache:
        if len(_catalog_cache) > 16:
            _catalog_cache.clear()
        _catalog_cache[key] = {lesson["id"]: lesson for lesson in public_curriculum(locale)["lessons"]}
    return _catalog_cache[key]


def public_lesson(spec, locale=None):
    """课程卡片与详情共用的公开字段。locale 选择目录与实现清单的译文层，逐条回落到源语言。

    练习问题与预设输入是运行事实，取的是这次界面语言对应的运行语言（runtime_locale）那一份：
    本课支持该语言时与界面一致，不支持时是源语言，运行和回放也都是这种语言。
    """
    language = run_locale(spec, locale)
    exercises, defaults = lesson_presets(spec, language)
    public = {key: spec[key] for key in ("id", "number", "aliases", "title", "description", "objectives", "subtitle",
                                         "available", "ui", "capabilities")}
    public.update(exercises=exercises, input_defaults=defaults, runtime_locale=language,
                  runtime_locales=list(spec["runtime"]["locales"]))
    if locale:
        entry = localized_entries(locale).get(spec["id"])
        if entry is not None:
            public.update(title=entry["title"], description=entry["summary"], objectives=entry["objectives"])
        subtitle, exercises, ui, _ = localized_manifest(spec, locale, exercises)
        # 没写 subtitle 的课在加载时沿用了目录简介，译文也跟着目录走。
        public.update(subtitle=public["description"] if subtitle is None else subtitle, exercises=exercises, ui=ui)
    public["exercises"] = resolve_refs(public["exercises"], CATALOG_INDEX.numbers, language)
    return resolve_refs(public, CATALOG_INDEX.numbers)


def _refs_in(locale):
    """只作用于合并进来的译文：按目标语言写课号；其余文本随后按源语言写。"""
    return lambda text: resolve_refs(text, CATALOG_INDEX.numbers, locale)


def lesson_runtime(spec):
    reference = spec["runtime"]["entrypoint"]
    return import_module(spec["package"] + "." + reference.split(":", 1)[0])


def exercise_requires_embedding(spec, exercise):
    """这个练习是否发 Embedding 请求：显式声明优先，否则调用模型的练习跟随课程的 embedding_factory。"""
    calls_model = exercise.get("requires_model", spec["runtime"].get("requires_model", True))
    default = calls_model and "embedding_factory" in spec.get("testing", {})
    return bool(exercise.get("requires_embedding", default))


def lesson_callable(spec, reference):
    """加载已验证的本课函数；不能借声明导入其他课或任意系统模块。"""
    _reference(spec["root"], spec["module"], reference, "lesson callable", callable_required=True)
    module_name, function_name = reference.split(":")
    function = getattr(import_module(spec["package"] + "." + module_name), function_name, None)
    _require(callable(function), "lesson " + spec["id"], "声明的入口函数不存在或不可调用")
    return function


def lesson_code_view(spec, locale=None):
    """读码场景数据：只读本课 sources 白名单，批注取自已合并译文层的内容。

    运行时文本文件只给出运行语言那一份：界面是英文、本课也有英文运行时，就看 en.py。
    """
    content_path = _safe_file(spec["root"] / "lessons" / spec["module"], spec["content"], "lesson content")
    learning, _ = load_lesson_content(content_path, spec, locale, _refs_in(locale))
    view = lesson_code(spec, LESSONS, resolve_refs(learning, CATALOG_INDEX.numbers), run_locale(spec, locale))
    # “本课新增”对照的那一课标题来自实现清单（源语言），这里按目录译文换成界面语言。
    compare = view["whats_new"]["compare_with"]
    entry = localized_entries(locale).get(compare["id"]) if compare and locale else None
    if entry is not None:
        compare["title"] = entry["title"]
    return view


def lesson_detail(spec, locale=None):
    from course.execution import validate_inputs
    module = lesson_runtime(spec)
    content_path = _safe_file(spec["root"] / "lessons" / spec["module"], spec["content"], "lesson content")
    public = public_lesson(spec, locale)
    language = public["runtime_locale"]
    sources = []
    for source in lesson_sources(spec, language):
        path = _safe_file(spec["root"], source["path"], "lesson sources", source=True)
        sources.append({**source, "role": source_role(source["path"]), "content": path.read_text(encoding="utf-8")})
    # Publish actual validated presets, including model defaults, so the parameter
    # editor shows every value the lesson will receive rather than hidden values.
    learning, learning_i18n = load_lesson_content(content_path, spec, locale, _refs_in(locale))
    # 练习标题来自实现清单译文层；问题与预设输入是发给模型的事实，取运行语言那一份。
    exercises = [{**exercise, "inputs": validate_inputs(module, {**public["input_defaults"],
                                                                 **exercise.get("inputs", {})})}
                 for exercise in public["exercises"]]
    # 自定义运行器的输入模型导出 JSON Schema，前端据此生成参数控件；最终仍由后端校验。
    input_model = getattr(module, "INPUT_MODEL", None)
    input_schema = input_model.model_json_schema() if spec["capabilities"]["supports_inputs"] and input_model else None
    learning = resolve_refs(learning, CATALOG_INDEX.numbers)
    # 原生课由 setup(locale) 给出这次运行发给模型的系统提示词与工具定义；独立运行器发工具时导出（或导入）
    # tool_definitions(locale)，读码页据此给工具函数加“看运行证据”的入口。还没改造的课仍可导出常量。
    setup = module.setup(language) if callable(getattr(module, "setup", None)) else None
    definitions = getattr(module, "tool_definitions", None)
    tools = (setup.tools if setup else definitions(language) if callable(definitions)
             else getattr(module, "TOOLS", []))
    return {**public, "exercises": exercises, "input_schema": input_schema,
            "system_prompt": setup.system_prompt if setup else getattr(module, "SYSTEM_PROMPT", ""),
            "tools": tools,
            "learning": learning, "learning_i18n": learning_i18n,
            "sources": sources, "code_names": lesson_code_names(spec, sources)}


_learning_cache: dict = {}


def _learning(spec, locale=None):
    """课程表细纲用的 content 输出（已换好课号），按内容与译文文件的修改时间缓存。"""
    from server.content import overlay_path

    path = spec["content_path"]
    files = [path] + ([overlay_path(path, locale)] if locale else [])
    key = (str(path), locale, tuple((file.stat().st_mtime_ns, file.stat().st_size) if file.is_file() else None
                                    for file in files))
    if key not in _learning_cache:
        if len(_learning_cache) > 256:
            _learning_cache.clear()
        learning, _ = load_lesson_content(path, spec, locale, _refs_in(locale))
        _learning_cache[key] = resolve_refs(learning, CATALOG_INDEX.numbers)
    return _learning_cache[key]


def curriculum_outline(*, strict: bool = False, locale=None):
    """/api/curriculum 与课程表文档：在 catalog 之上补小节、是否调用模型与本课术语（见 server/outline.py）。

    strict（导出文档时用）：术语表有错直接抛出，不生成缺了“本课术语”的文档。
    locale：目录、正文小节与本课术语换成该语言的译文，缺的条目回落到源语言。
    """
    from server.curriculum import public_curriculum
    from server.glossary import public_glossary
    try:
        terms = public_glossary(ROOT, CATALOG_INDEX, locale)["terms"]
    except (LessonValidationError, OSError) as error:
        if strict:
            raise
        # 网页照常显示课程表，只是没有“本课术语”；原因写进服务端日志，不悄悄吞掉。
        logging.getLogger(__name__).warning("术语表加载失败，课程表暂不显示本课术语：%s", error)
        terms = []
    return enrich(public_curriculum(locale), LESSONS, lambda spec: _learning(spec, locale), terms)


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
    python = [source for source in sources if source["language"] == "python"]
    # 运行时文本（locales/ 下的消息目录）里的字符串值是自然语言，不当代码名；见 server/code_names.py。
    return code_names([source["content"] for source in python if source_role(source["path"]) != "texts"], forms,
                      catalogs=[source["content"] for source in python if source_role(source["path"]) == "texts"])

