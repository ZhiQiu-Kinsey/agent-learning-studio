"""课程正文的用词检查：术语、代码名和裸英文词。

网页按 frontend/src/content/glossary/match.ts 标注正文：术语表里的词在每页第一次出现处加下划线和释义卡，
本课源码里的名字显示成代码样式。这里用同样的规则在 Python 端找出问题，供测试、validate_lessons
和 scripts/term_report.py 共用：

- 课程概念只在引入课（first_lesson）写一次“中文（English）”，其他课只写中文，靠悬浮卡回顾；
- first_lesson 必须是最早用到这个术语的可运行课，避免先用后讲；
- 正文里的小写英文词要么是术语，要么是本课源码里的名字，不留无法解释的裸英文；
- code_notes 只能说明本课源码里真有、正文里真用到的名字。

中文术语有没有收录，机器判断不了，需要作者对照 scripts/term_report.py 的输出逐课审读
（规则见 docs/architecture/terminology.md）。
"""
import re

# 与 match.ts 的 CODE_TOKEN 相同；re.ASCII 让 \w 只匹配 ASCII（JS 不带 u 标志时也是如此）。
CODE_TOKEN = re.compile(
    r"(?<![\w.$])(?:[a-z_]\w*=[\w\"'.-]+"
    r"|[A-Za-z_]\w*(?:\[\d+\])?(?:\.[A-Za-z_]\w*(?:\[\d+\])?)+(?:\([^()\n]{0,30}\))?"
    r"|[A-Za-z_]\w*_\w*(?:\[\d+\])*(?:\.[A-Za-z_]\w*)*(?:\([^()\n]{0,30}\))?"
    r"|[A-Za-z_]\w*\[\d+\](?:\.[A-Za-z_]\w*)*)(?!\w)",
    re.ASCII,
)
_BACKTICK = re.compile(r"`[^`\n]*`")
_LATIN = re.compile(r"[A-Za-z0-9]")
# 小写开头的英文词（可带连字符），例如 evidence、tokenizer、s-1042。
BARE_WORD = re.compile(r"(?<![A-Za-z0-9_.$-])[a-z][A-Za-z0-9_-]*(?![A-Za-z0-9_])")


def _blank(text):
    """把代码样式的片段换成等长空格：位置不变，里面的字也不再参与术语匹配。"""
    text = _BACKTICK.sub(lambda m: " " * len(m.group(0)), text)
    return CODE_TOKEN.sub(lambda m: " " * len(m.group(0)), text)


def _normalise(value):
    return re.sub(r"\s+", " ", value.strip().lower())


class TermMatcher:
    """match.ts buildMatcher 的 Python 版本：最长形式优先，拉丁字母两端要有词边界，not_in 词组整体跳过。"""

    def __init__(self, terms):
        self.forms = {}
        for term in terms:
            for form in (term["zh"], term["en"], *term.get("aliases", [])):
                self.forms.setdefault(_normalise(form), term)
        for term in terms:
            for phrase in term.get("not_in", []):
                self.forms.setdefault(_normalise(phrase), None)
        parts = []
        for form in sorted(self.forms, key=len, reverse=True):
            head = r"(?<![A-Za-z0-9_])" if _LATIN.match(form[0]) else ""
            tail = r"(?![A-Za-z0-9_])" if _LATIN.match(form[-1]) else ""
            parts.append(head + r"\s*".join(re.escape(piece) for piece in form.split(" ")) + tail)
        self.regex = re.compile("|".join(parts), re.IGNORECASE)

    def find(self, text):
        """[(start, end, term)]：正文里每一处术语命中（代码样式的片段不算）。"""
        hits = []
        for match in self.regex.finditer(_blank(text)):
            term = self.forms.get(_normalise(match.group(0)))
            if term is not None:
                hits.append((match.start(), match.end(), term))
        return hits

    def first_hits(self, text):
        """{term_id: start}：每个术语第一次出现的位置。"""
        first = {}
        for start, _, term in self.find(text):
            first.setdefault(term["id"], start)
        return first


def pair_label(term):
    return f"{term['zh']}（{term['en']}）"


def bare_words(text, code_names, matcher):
    """正文里既不是术语、也不是代码名的小写英文词：[(词, 上下文)]。"""
    known = set(code_names)
    blanked = _blank(text)
    covered = [False] * len(text)
    for start, end, _ in matcher.find(text):
        covered[start:end] = [True] * (end - start)
    found = []
    for match in BARE_WORD.finditer(blanked):
        word = match.group(0).rstrip("-")
        if word in known or covered[match.start()]:
            continue
        found.append((word, text[max(0, match.start() - 12):match.end() + 12]))
    return found


def name_used(name, text):
    """代码名在正文里是否作为完整的名字出现（前后不是标识符字符）。"""
    pattern = r"(?<![\w.$-])" + re.escape(name) + r"(?![\w-]|\.\w)"
    return re.search(pattern, text, re.ASCII) is not None


def marked_texts(model):
    """网页会标注术语的文字，按阅读顺序；与 frontend/src/content/glossary/texts.ts 的 blockTexts 一致，
    再加实验里的观察要点（理解页末尾的“运行时观察”）。标题、选项等不加下划线，不在其中。"""
    values = []
    blocks = model.scenes.understand.blocks if model.scenes.understand else []
    for block in blocks:
        kind = block.type
        if kind == "concepts":
            values += [item.description for item in block.items]
        elif kind in ("prose", "callout"):
            values += block.paragraphs
        elif kind == "walkthrough":
            values += [step.body for step in block.steps]
        elif kind == "steps":
            values += [*block.paragraphs, *(item.text for item in block.items)]
        elif kind == "compare":
            values += [*block.paragraphs, *(cell for row in block.rows for cell in row)]
        elif kind == "misconception":
            values += [block.claim, block.correction]
    if model.scenes.lab:
        values += [point.text for experiment in model.scenes.lab.experiments for point in experiment.observe]
    return values


def all_texts(model):
    """本课全部可读文字（各场景与 hero），用于找裸英文词与代码名。"""
    from server.content_overlay import text_slots
    values = []
    for name in ("understand", "code", "lab", "check"):
        scene = getattr(model.scenes, name)
        if scene is not None:
            values += [slot.value for slot in text_slots(scene, scene.model_dump(mode="json")).values()]
    return values


def lesson_problems(lesson_id, model, terms, numbers, code_names, available):
    """一课的用词问题：[(类别, 说明)]。numbers：slug → 课号；available：可运行课程的 slug 集合。"""
    from server.lesson_refs import resolve_refs

    matcher = TermMatcher(terms)
    problems = []
    # 课程引用 {{lesson:<slug>}} 在网页上显示为“第 N 课”，按显示后的文字检查。
    marked = "\n".join(resolve_refs(marked_texts(model), numbers))
    everything = "\n".join(resolve_refs(all_texts(model), numbers))
    first = matcher.first_hits(marked)
    seen = matcher.first_hits(everything)
    by_id = {term["id"]: term for term in terms}
    for term_id, start in seen.items():
        term = by_id[term_id]
        if term.get("kind", "concept") != "concept":
            continue
        intro = term.get("first_lesson")
        if intro == lesson_id:
            continue
        if intro is None or intro not in available or numbers[intro] > numbers[lesson_id]:
            where = "尚无引入课" if intro is None else f"引入课是第 {numbers[intro]} 课"
            problems.append(("先用后讲", f"{term['zh']}：本课已用到，但{where}；"
                             f"把 first_lesson 改成最早用到它的课，或改写本课措辞：…{everything[start:start + 24]}…"))
    for term in terms:
        names = (term["zh"], *term.get("aliases", []))
        pairs = [f"{name}（{term['en']}）" for name in names if term["zh"] != term["en"]]
        is_intro = term.get("kind", "concept") == "concept" and term.get("first_lesson") == lesson_id
        if is_intro and term["zh"] != term["en"]:
            start = first.get(term["id"])
            if start is not None and not any(marked.startswith(pair, start) for pair in pairs):
                problems.append(("缺中英并列", f"{term['zh']} 在本课引入，第一次出现要写成 {pairs[0]}："
                                 f"…{marked[start:start + 24]}…"))
            if start is None:
                problems.append(("引入课未出现", f"{term['zh']} 的 first_lesson 是本课，但本课加下划线的正文里没有用到它"))
        elif not is_intro:
            for pair in pairs:
                if pair in everything:
                    problems.append(("多余的中英并列", f"{pair} 只在引入课写一次，本课写成“{term['zh']}”即可"))
    for word, context in bare_words(everything, code_names, matcher):
        problems.append(("裸英文词", f"{word}：既不是术语也不是本课源码里的名字：…{context}…"))
    for item in model.code_notes:
        if item.name not in code_names and not CODE_TOKEN.fullmatch(item.name):
            problems.append(("代码说明无出处", f"code_notes.{item.name} 不在本课登记的源码里"))
        elif not name_used(item.name, everything):
            problems.append(("代码说明未使用", f"code_notes.{item.name} 没有出现在本课正文里"))
    return problems
