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
# 开头排除英文缩写 e.g. / i.e.，它们形似点号取值。
CODE_TOKEN = re.compile(
    r"(?<![\w.$])(?!(?:e\.g|i\.e)\.)(?:[a-z_]\w*=[\w\"'.-]+"
    r"|[A-Za-z_]\w*(?:\[\d+\])?(?:\.[A-Za-z_]\w*(?:\[\d+\])?)+(?:\([^()\n]{0,30}\))?"
    r"|[A-Za-z_]\w*_\w*(?:\[\d+\])*(?:\.[A-Za-z_]\w*)*(?:\([^()\n]{0,30}\))?"
    r"|[A-Za-z_]\w*\[\d+\](?:\.[A-Za-z_]\w*)*)(?!\w)",
    re.ASCII,
)
_BACKTICK = re.compile(r"`[^`\n]*`")
# 服务商没有报告的数（用量、缓存命中）写“未报告”；“未知”留给确实无法知道的值（见 terminology.md 统一用词表）。
UNREPORTED = re.compile(r"(?:用量|Token|命中数?|缓存命中)[^。；，、\n]{0,4}未知|未知的?(?:用量|Token 数|命中数)")
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
    """网页会标注术语的文字，按认领顺序；与 frontend/src/content/glossary/texts.ts 的
    blockTexts / readingTexts 一致：所有“深入一层”块（默认折叠）排在其余块之后，主线正文优先认领术语；
    只在深入块里出现的术语仍由深入块认领。再加实验里的观察要点（理解页末尾的“运行时观察”）。
    标题、选项等不加下划线，不在其中。"""
    values = []
    dives = []
    blocks = model.scenes.understand.blocks if model.scenes.understand else []
    for block in blocks:
        kind = block.type
        if kind == "concepts":
            values += [item.description for item in block.items]
        elif kind in ("prose", "callout"):
            values += block.paragraphs
        elif kind == "deep-dive":
            dives += [*([block.summary] if block.summary else []), *block.paragraphs]
        elif kind == "walkthrough":
            values += [step.body for step in block.steps]
        elif kind == "steps":
            values += [*block.paragraphs, *(item.text for item in block.items)]
        elif kind == "compare":
            values += [*block.paragraphs, *(cell for row in block.rows for cell in row)]
        elif kind == "misconception":
            values += [block.claim, block.correction]
    values += dives
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
    notes = "\n".join(item.note for item in model.code_notes)
    for text in (everything, notes):
        for match in UNREPORTED.finditer(text):
            problems.append(("未报告写成未知", "服务商没有报告的数写“未报告”："
                             f"…{text[max(0, match.start() - 12):match.end() + 12]}…"))
    for item in model.code_notes:
        if item.name not in code_names and not CODE_TOKEN.fullmatch(item.name):
            problems.append(("代码说明无出处", f"code_notes.{item.name} 不在本课登记的源码里"))
        elif not name_used(item.name, everything):
            problems.append(("代码说明未使用", f"code_notes.{item.name} 没有出现在本课正文里"))
    return problems


# —— 英文文本检查 ——
# 上面的规则只看中文源文本。英文译文层（content.en.json、lesson.en.json、curriculum/*.en.json）、
# 英文运行时文本（locales/**/en.py、en.md）和英文界面文案另有三条检查，规则见 docs/architecture/terminology.md 第 5 节。

# 与 scripts/cjk_baseline.py、tests/test_runtime_locales.py 相同：中日韩标点、汉字、兼容汉字与全角字符。
_CJK_CLASS = "[　-〿㐀-䶿一-鿿豈-﫿＀-￯]"
CJK = re.compile(_CJK_CLASS)

# 英文文本里允许出现的中文：(文件, 文本路径, 精确子串, 理由)。文件是相对项目根目录的路径，"*" 表示任意文件；
# 文本路径是译文层 texts 的键，"*" 表示整份文件。子串先从文本里去掉，剩下的部分不能再有中文；
# 条目必须真的用得上，用不上的会报出来，名单只放确有必要的中文。
ENGLISH_CJK_ALLOWED = (
    ("*", "*", "(深入理解 AI Agent)",
     "参考书的中文原书名，括在英文书名后面，读者凭它才能找到这本只有中文版的书"),
    ("curriculum/onboarding.en.json", "how-llm-works.tokens.paragraphs.1", '"函数式编程"',
     "分词示例：讲一个中文词怎样切成几个 Token，必须展示中文原文"),
    ("curriculum/onboarding.en.json", "how-llm-works.tokens.paragraphs.1", '"函数,"', "同一个分词示例的切分结果"),
    ("curriculum/onboarding.en.json", "how-llm-works.tokens.paragraphs.1", '"式,"', "同一个分词示例的切分结果"),
    ("curriculum/onboarding.en.json", "how-llm-works.tokens.paragraphs.1", '"编程,"', "同一个分词示例的切分结果"),
    ("lessons/lesson_reflection_revision/content.en.json", "section-4.paragraphs.2", "`s-1０４２`",
     "全角数字示例：Python 正则的数字类默认也匹配全角数字，正文用它说明测试用例漏掉的情况"),
)

# 服务商没有报告的数在英文里写 not reported，不写 unknown（与上面的 UNREPORTED 对应）。
# 前一种写法“usage … unknown”只允许中间隔几个系动词或介词，避免误中“usage of an unknown tool”；
# 不收单独的 tokens，避免误中分词器里的“unknown tokens”。
_USAGE_NOUN = (r"(?:usage|token counts?|cache hits?|cache hit counts?|hit counts?"
               r"|(?:prompt|completion|reasoning|cached|input|output) tokens)")
EN_UNREPORTED = re.compile(
    r"\b" + _USAGE_NOUN + r"(?:\s+(?:is|are|was|were|stays?|remains?|left|kept|shown|written|recorded|reported"
    r"|marked|counted|treated|as|still))*\s*[:(]?\s*[\"“]?unknown\b"
    r"|\bunknown\s+" + _USAGE_NOUN + r"\b",
    re.IGNORECASE,
)

# 运行时改成双语以前，英文译文只能引用中文原文再加英文注释，写成 "中文" ("gloss")。
# 现在英文运行发的就是英文，英文文本应直接引用英文运行时文本。
GLOSSED_LITERAL = re.compile(r"[\"“][^\"”\n]*" + _CJK_CLASS + r"[^\"”\n]*[\"”]\s*[(（]\s*[\"“]")


def _context(text, start, end, width=24):
    return text[max(0, start - width):end + width].replace("\n", " ")


def english_problems(file, path, text, used=None, unreported=True):
    """一段英文文本的问题：[(类别, 说明)]。file 是相对项目根目录的 posix 路径，path 是文本路径（整份文件写 "*"）。

    used：可选集合，记下命中过的白名单条目下标，供调用方找出用不上的条目。
    unreported=False 跳过 not reported 检查（课程目录里规划中课程的条目，与中文只查可运行课程一致）。
    """
    problems = []
    for match in GLOSSED_LITERAL.finditer(text):
        problems.append(("中文原文加英文注释", "英文文本直接引用英文运行时文本，不写 \"中文\" (\"gloss\")："
                         f"…{_context(text, match.start(), match.end())}…"))
    rest = text
    for index, (allowed_file, allowed_path, substring, _) in enumerate(ENGLISH_CJK_ALLOWED):
        if allowed_file in ("*", file) and allowed_path in ("*", path) and substring in rest:
            rest = rest.replace(substring, " " * len(substring))
            if used is not None:
                used.add(index)
    if not problems:
        for match in re.finditer(_CJK_CLASS + "+", rest):
            problems.append(("英文文本含中文", f"{match.group(0)}：…{_context(text, match.start(), match.end())}…"
                             "（确需保留的，加进 server/vocabulary.py 的 ENGLISH_CJK_ALLOWED 并写明理由）"))
    for match in EN_UNREPORTED.finditer(text) if unreported else ():
        problems.append(("not reported 写成 unknown", "服务商没有报告的数写 not reported："
                         f"…{_context(text, match.start(), match.end())}…"))
    return problems


def unused_allowances(used, exists=None):
    """[(文件, 文本路径, 子串)]：一次也没用上的白名单条目。

    exists(file)：可选，只看文件确实存在的条目，供 validate_lessons --root 校验只含部分课程的项目时使用。
    """
    return [entry[:3] for index, entry in enumerate(ENGLISH_CJK_ALLOWED)
            if index not in used and (exists is None or exists(entry[0]))]
