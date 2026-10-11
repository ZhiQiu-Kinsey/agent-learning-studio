"""读码场景：从白名单源码计算符号、“本课新增”与批注定位。

符号只来自 Python ast 对真实文件的解析，不手写。比较依据是“名称 + 规范化源码哈希”：
规范化形式为 ``ast.dump(node, include_attributes=False)``，因此空白、注释和行号移动不算变化，
文档字符串和任何语法层面的改动都算变化。
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from course.i18n import SOURCE_LOCALE
from server.content_schema import AnnotatedSource, LessonContent, WhatsNew
from server.curriculum import LessonValidationError

# 模块级常量按 Python 约定用全大写名称识别，如 TOOLS、SYSTEM_PROMPT、INPUT_MODEL。
_CONSTANT = re.compile(r"_?[A-Z][A-Z0-9_]*\Z")
# 与前端按行切分保持一致：只把 \r\n、\r、\n 当作换行（ast 的行号也只认这三种）。
_NEWLINE = re.compile(r"\r\n|\r|\n")
_cache: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
# 同一课内出现同名符号时：沿用优先于变化，变化优先于新增。
_PRIORITY = {"unchanged": 2, "changed": 1, "added": 0}


def split_lines(text: str) -> list[str]:
    lines = _NEWLINE.split(text)
    if lines and lines[-1] == "":
        lines.pop()  # 文件末尾的换行不构成新的一行
    return lines


def line_count(text: str) -> int:
    return len(split_lines(text))


def _names(node: ast.stmt) -> tuple[str, list[str]] | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "function", [node.name]
    if isinstance(node, ast.ClassDef):
        return "class", [node.name]
    if isinstance(node, ast.Assign):
        names = [target.id for target in node.targets
                 if isinstance(target, ast.Name) and _CONSTANT.fullmatch(target.id)]
        return ("constant", names) if names else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and _CONSTANT.fullmatch(node.target.id):
        return "constant", [node.target.id]
    return None


def extract_symbols(text: str) -> list[dict[str, Any]]:
    """列出顶层函数、类与常量及其起止行号（含装饰器）；语法错误直接抛出 SyntaxError。"""
    symbols = []
    for node in ast.parse(text).body:
        found = _names(node)
        if found is None:
            continue
        kind, names = found
        start = min([node.lineno, *(item.lineno for item in getattr(node, "decorator_list", []))])
        digest = hashlib.sha256(ast.dump(node, include_attributes=False).encode("utf-8")).hexdigest()[:16]
        for name in names:
            symbols.append({"name": name, "kind": kind, "start": start, "end": node.end_lineno or node.lineno,
                            "hash": digest})
    return symbols


def extract_texts(text: str) -> list[dict[str, Any]]:
    """运行时文本文件（locales/<语言>.py）里 ``TEXTS = Texts(...)`` 的每个字段，记为 kind=text 的符号。

    名字写成代码里读取它的样子 ``t.<字段>``，与函数、常量不会重名；哈希取字段值的 AST，
    所以提示词改了一个字也算变化，只调整换行或注释不算。
    """
    symbols = []
    lines = split_lines(text)
    for node in ast.parse(text).body:
        if not (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TEXTS"
                                                     for target in node.targets)
                and isinstance(node.value, ast.Call)):
            continue
        keywords = [keyword for keyword in node.value.keywords if keyword.arg is not None]
        for index, keyword in enumerate(keywords):
            # 字段一直延伸到下一个字段之前（含多行字符串的收尾括号），去掉末尾的空行与注释行。
            end = (keywords[index + 1].lineno if index + 1 < len(keywords) else node.end_lineno or keyword.lineno) - 1
            end = max(end, keyword.value.end_lineno or keyword.lineno)
            while end > keyword.lineno and (not lines[end - 1].strip() or lines[end - 1].strip().startswith("#")):
                end -= 1
            digest = hashlib.sha256(ast.dump(keyword.value, include_attributes=False).encode("utf-8")).hexdigest()[:16]
            symbols.append({"name": f"t.{keyword.arg}", "kind": "text", "start": keyword.lineno, "end": end,
                            "hash": digest})
    return symbols


def classify(current: Iterable[dict[str, Any]], baseline: Iterable[dict[str, Any]] | None) -> dict[str, str]:
    """按名称比较：基准中有同名同哈希为沿用，同名不同哈希为变化，没有同名为新增。

    没有基准（第一门课）时全部记为新增。返回 {name: status}；同名多处定义时任一处相同即视为沿用。
    """
    known: dict[str, set[str]] = {}
    for symbol in baseline or []:
        known.setdefault(symbol["name"], set()).add(symbol["hash"])
    statuses: dict[str, str] = {}
    for symbol in current:
        hashes = known.get(symbol["name"])
        status = "added" if not hashes else "unchanged" if symbol["hash"] in hashes else "changed"
        previous = statuses.get(symbol["name"])
        if previous is None or _PRIORITY[status] > _PRIORITY[previous]:
            statuses[symbol["name"]] = status
    return statuses


def _code_blocks(model: LessonContent) -> list[Any]:
    return list(model.scenes.code.blocks) if model.scenes.code else []


def compare_target(model: LessonContent) -> str | None:
    """whats-new 块声明的对比课程（slug 或别名）；没有声明返回 None。"""
    return next((block.compare_with for block in _code_blocks(model)
                 if isinstance(block, WhatsNew) and block.compare_with), None)


def validate_code_scene(model: LessonContent, sources: list[dict[str, Any]], read: Callable[[str], str],
                        location: str) -> None:
    """annotated-source 的 path 必须在本课 sources 中，行号不得超出文件行数，批注须落在声明的范围内。"""
    declared = {source["path"] for source in sources}
    files: dict[str, list[str]] = {}
    for block in _code_blocks(model):
        if not isinstance(block, AnnotatedSource):
            continue
        where = f"{location}: scenes.code 块 {block.id}"
        if block.path not in declared:
            raise LessonValidationError(f"{where}: path「{block.path}」不在本课 sources 中")
        if source_role(block.path) == "texts":
            _check_texts_block(block, sources, read, where)
        if block.path not in files:
            files[block.path] = split_lines(read(block.path))
        lines = files[block.path]
        total = len(lines)
        for name in ("start", "end"):
            value = getattr(block, name)
            if value is not None and value > total:
                raise LessonValidationError(f"{where}: {name}={value} 超出文件行数 {total}")
        low, high = block.start or 1, block.end or total
        for note in block.notes:
            if note.line > total:
                raise LessonValidationError(f"{where}: 批注 {note.id} 的行号 {note.line} 超出文件行数 {total}")
            if not low <= note.line <= high:
                raise LessonValidationError(f"{where}: 批注 {note.id} 的行号 {note.line} 不在 {low}–{high} 范围内")
            if note.anchor not in lines[note.line - 1]:
                raise LessonValidationError(
                    f"{where}: 批注 {note.id} 的锚点「{note.anchor}」不在第 {note.line} 行"
                    f"（该行是「{lines[note.line - 1].strip()[:60]}」）；源码可能已移动，请重新对准批注")
        for fold in block.folds:
            if not low <= fold.start <= fold.end <= high:
                raise LessonValidationError(f"{where}: 折叠 {fold.id} 的 {fold.start}–{fold.end} 不在 {low}–{high} 范围内")


def texts_layout(text: str) -> dict[str, tuple[int, int]]:
    """运行时文本文件的版面：{字段: (起行, 止行)}，外加 ``TEXTS = Texts(`` 那一行（键 "TEXTS"）与收尾的括号（键 ")"）。"""
    layout: dict[str, tuple[int, int]] = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TEXTS"
                                                for target in node.targets):
            layout["TEXTS"] = (node.lineno, node.lineno)
            layout[")"] = (node.end_lineno or node.lineno, node.end_lineno or node.lineno)
    for symbol in extract_texts(text):
        layout[symbol["name"]] = (symbol["start"], symbol["end"])
    return layout


def _slot(layout: dict[str, tuple[int, int]], line: int) -> tuple[str, int] | None:
    """行号落在哪个字段里、是字段的第几行（从 0 数）；不在任何字段里返回 None。"""
    return next(((key, line - start) for key, (start, end) in layout.items() if start <= line <= end), None)


def _texts_counterparts(path: str, sources: list[dict[str, Any]]) -> dict[str, str]:
    """{语言: 同一目录下该语言的运行时文本文件}。"""
    directory = path.rsplit("/", 1)[0]
    return {source["locale"]: source["path"] for source in sources
            if source.get("locale") and source["path"].rsplit("/", 1)[0] == directory}


def _check_texts_block(block: AnnotatedSource, sources: list[dict[str, Any]], read: Callable[[str], str],
                       where: str) -> None:
    """运行时文本文件也可以做读码块（讲提示词的课需要逐行批注），规则比代码多两条：

    - 块写在源语言（zh-CN）那份上，写明 start 与 end；起止行、批注和折叠都要落在某个字段里
      （或 ``TEXTS = Texts(`` 那一行、收尾的括号）；
    - 块覆盖的字段在每种语言的文件里行数相同，界面切换语言时按“第几个字段的第几行”换算到对应文件。
    """
    entry = next(source for source in sources if source["path"] == block.path)
    if entry.get("locale") != SOURCE_LOCALE:
        raise LessonValidationError(f"{where}: 运行时文本的读码块写在源语言 {SOURCE_LOCALE} 的文件上，"
                                    "其他语言由平台按字段换算")
    if block.start is None or block.end is None:
        raise LessonValidationError(f"{where}: 运行时文本的读码块要写明 start 与 end")
    source = texts_layout(read(block.path))
    lines = [block.start, block.end, *(note.line for note in block.notes),
             *(line for fold in block.folds for line in (fold.start, fold.end))]
    for line in lines:
        if _slot(source, line) is None:
            raise LessonValidationError(f"{where}: 第 {line} 行不在 TEXTS 的任何字段里，换算不到其他语言")
    covered = {key for key, (start, end) in source.items() if start <= block.end and end >= block.start}
    for locale, path in _texts_counterparts(block.path, sources).items():
        other = texts_layout(read(path))
        for key in sorted(covered):
            if key not in other or other[key][1] - other[key][0] != source[key][1] - source[key][0]:
                raise LessonValidationError(
                    f"{where}: 字段 {key} 在 {path} 的行数与源语言不同；读码块覆盖的字段在每种语言里要逐行对应")


def localize_texts_block(block: dict[str, Any], source_text: str, target_path: str,
                         target_text: str) -> dict[str, Any]:
    """把写在源语言文本文件上的读码块换算到另一种语言的文件：行号按“字段 + 字段内第几行”对应。

    锚点是源语言的原文，换算后不再适用，所以去掉；批注文字由译文层负责。
    """
    source, target = texts_layout(source_text), texts_layout(target_text)

    def moved(line: int) -> int:
        key, offset = _slot(source, line)  # 校验已保证每一行都落在字段里
        return target[key][0] + offset

    result = {**block, "path": target_path, "start": moved(block["start"]), "end": moved(block["end"]),
              "notes": [{key: value for key, value in {**note, "line": moved(note["line"])}.items() if key != "anchor"}
                        for note in block["notes"]],
              "folds": [{**fold, "start": moved(fold["start"]), "end": moved(fold["end"])}
                        for fold in block.get("folds") or []]}
    return result


# 批注密度门槛：展示范围内每 NOTE_EVERY 个非空、未折叠的行至少一条批注，连续无批注不超过 MAX_GAP 行。
NOTE_EVERY = 8
MAX_GAP = 12


def note_density(block: AnnotatedSource, lines: list[str]) -> dict[str, int]:
    """统计一个读码块的可见非空行数、批注数与最长无批注空段（只数非空、未折叠的行）。"""
    low, high = block.start or 1, block.end or len(lines)
    folded = {line for fold in block.folds for line in range(fold.start, fold.end + 1)}
    noted = {note.line for note in block.notes}
    visible = gap = longest = 0
    for number in range(low, high + 1):
        if number in folded or not lines[number - 1].strip():
            continue
        visible += 1
        gap = 0 if number in noted else gap + 1
        longest = max(longest, gap)
    return {"lines": visible, "notes": len(block.notes), "longest_gap": longest}


def density_issues(model: LessonContent, read: Callable[[str], str]) -> list[str]:
    """不满足批注密度门槛的读码块，返回“块 id：原因”列表（基线比对由调用方完成）。"""
    issues = []
    for block in _code_blocks(model):
        if not isinstance(block, AnnotatedSource):
            continue
        stats = note_density(block, split_lines(read(block.path)))
        needed = -(-stats["lines"] // NOTE_EVERY)
        if stats["notes"] < needed:
            issues.append(f"{block.id}：{stats['lines']} 行只有 {stats['notes']} 条批注，至少需要 {needed} 条")
        if stats["longest_gap"] > MAX_GAP:
            issues.append(f"{block.id}：连续 {stats['longest_gap']} 行没有批注，最多 {MAX_GAP} 行")
    return issues


def _file_symbols(path: Path, texts: bool = False) -> list[dict[str, Any]]:
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size, texts)
    if key not in _cache:
        if len(_cache) > 256:
            _cache.clear()
        text = path.read_text(encoding="utf-8")
        _cache[key] = extract_texts(text) if texts else extract_symbols(text)
    return [dict(symbol) for symbol in _cache[key]]



def source_role(path: str) -> str:
    """源码在读码页里的角色：课程代码（lesson）、平台代码（platform）、只服务自动化测试的夹具（fixture），
    或运行时文本（texts：locales/ 目录及其子目录下按语言分开的提示词与消息，课程与平台都有）。"""
    parts = path.split("/")
    name = parts[-1]
    if "locales" in parts[1:-1]:
        return "texts"
    if not path.startswith("lessons/"):
        return "platform"
    if name == "fixtures.py" or name.startswith("test_"):
        return "fixture"
    return "lesson"


def _files(spec: dict[str, Any], locale: str | None = None) -> list[dict[str, Any]]:
    """本课在运行语言 locale 下展示的文件；locale 为 None 时列出全部（运行时文本按语言各一份）。"""
    from server.catalog import _safe_file  # 延迟导入：catalog 在加载课程时也会导入本模块

    files = []
    for source in spec["sources"]:
        if locale is not None and source.get("locale") not in (None, locale):
            continue
        path = _safe_file(spec["root"], source["path"], "lesson sources", source=True)
        python = path.suffix.casefold() == ".py"
        texts = bool(source.get("locale"))
        files.append({"path": source["path"], "language": source["language"], "role": source_role(source["path"]),
                      **({"locale": source["locale"]} if texts else {}),
                      "lines": line_count(path.read_text(encoding="utf-8")),
                      "symbols": _file_symbols(path, texts) if python else []})
    return files


def _baseline(spec: dict[str, Any], lessons: list[dict[str, Any]]) -> dict[str, Any] | None:
    """whats-new 声明的对比课；未声明或对比课不可用时取目录顺序中的上一门可用课。"""
    explicit = spec.get("code_compare")
    if explicit:
        match = next((item for item in lessons if explicit == item["id"] or explicit in item["aliases"]), None)
        if match is not None:
            return match
    ids = [item["id"] for item in lessons]
    if spec["id"] not in ids:
        return None
    index = ids.index(spec["id"])
    return lessons[index - 1] if index > 0 else None


def _ref(path: str, symbol: dict[str, Any]) -> dict[str, Any]:
    return {"name": symbol["name"], "kind": symbol["kind"], "path": path,
            "start": symbol["start"], "end": symbol["end"]}


def _in_locale(spec: dict[str, Any], annotation: dict[str, Any], locale: str) -> dict[str, Any]:
    """写在源语言文本文件上的读码块，在其他语言的读码页里指向该语言的文件。"""
    from server.catalog import _safe_file  # 延迟导入，理由同 _files

    if source_role(annotation["path"]) != "texts":
        return annotation
    target = _texts_counterparts(annotation["path"], spec["sources"]).get(locale)
    if target is None:
        return annotation

    def read(path):
        return _safe_file(spec["root"], path, "lesson sources", source=True).read_text(encoding="utf-8")

    return localize_texts_block(annotation, read(annotation["path"]), target, read(target))


def lesson_code(spec: dict[str, Any], lessons: list[dict[str, Any]], learning: dict[str, Any],
                locale: str | None = None) -> dict[str, Any]:
    """GET /api/lessons/{id}/code 的响应体；learning 是已合并译文层的 content v2 输出，locale 是运行语言。"""
    # “本课新增”比较课程代码和运行时文本（提示词改了也是本课的新内容）；平台代码和测试夹具不是本课要学的内容。
    # 运行时文本一律按源语言那份比较：对比课还没有这种语言时也能比，各语言看到的结论也一致。
    files = _files(spec, locale)
    baseline_spec = _baseline(spec, lessons)

    def code(items):
        return [symbol for item in items if item["role"] == "lesson" for symbol in item["symbols"]]

    def texts(items):
        return [symbol for item in items if item["role"] == "texts" and "locale" in item for symbol in item["symbols"]]

    statuses = classify(code(files), code(_files(baseline_spec)) if baseline_spec else None)
    text_statuses = classify(texts(_files(spec, SOURCE_LOCALE)),
                             texts(_files(baseline_spec, SOURCE_LOCALE)) if baseline_spec else None)
    groups: dict[str, list[dict[str, Any]]] = {"added": [], "changed": [], "unchanged": []}
    for item in files:
        compared = statuses if item["role"] == "lesson" else text_statuses if "locale" in item else None
        for symbol in item["symbols"]:
            if compared is None:
                symbol["status"] = "context"
                continue
            symbol["status"] = compared.get(symbol["name"], "added")
            groups[symbol["status"]].append(_ref(item["path"], symbol))
    blocks = (learning.get("scenes", {}).get("code") or {}).get("blocks", [])
    annotations = [{key: block[key] for key in ("id", "path", "start", "end", "notes", "folds")}
                   for block in blocks if block.get("type") == "annotated-source"]
    if locale and locale != SOURCE_LOCALE:
        annotations = [_in_locale(spec, annotation, locale) for annotation in annotations]
    compare = ({"id": baseline_spec["id"], "number": baseline_spec["number"], "title": baseline_spec["title"]}
               if baseline_spec else None)
    return {"lesson_id": spec["id"], "runtime_locale": locale, "files": files,
            "whats_new": {"compare_with": compare, **groups},
            "annotations": annotations}
