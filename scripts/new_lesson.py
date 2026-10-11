"""为已规划课程生成独立实现目录；不会把课程自动标为可用。"""

import argparse
import json
from pathlib import Path
import re
import sys
import textwrap


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.curriculum import index_catalog  # noqa: E402


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def lesson_directory(slug):
    """新课目录名：lesson_ + slug 的 snake_case 形式，例如 document-loading → lesson_document_loading。"""
    return "lesson_" + slug.replace("-", "_")


def build_scaffold(root, lesson_id, slug=None, kind="native"):
    """先验证所有输入并生成内存中的文件计划，不写文件。

    lesson_id 可以是课程 slug 或改名前的旧 slug 别名；slug 参数可省略，提供时必须与目录中的 slug 一致
    （允许写成 snake_case），仅为兼容旧命令保留。
    """
    root = Path(root).resolve()
    if kind not in {"native", "custom"}:
        raise ValueError("kind 只能是 native 或 custom。")
    if slug is not None and not re.fullmatch(r"[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*", slug):
        raise ValueError("slug 只允许小写字母、数字和单个连字符或下划线，例如 task-contract。")
    catalog_path = root / "curriculum" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    index = index_catalog(catalog, str(catalog_path))
    canonical = index.resolve(str(lesson_id))
    if canonical is None:
        raise ValueError(f"{catalog_path}: 必须先登记课程 {lesson_id}（课程 slug 或旧 slug 别名）。")
    if slug is not None and slug.replace("_", "-") != canonical:
        raise ValueError(f"--slug 与目录中的课程 slug「{canonical}」不一致；可以省略 --slug。")
    lesson = index.entries[canonical]
    number = index.numbers[canonical]
    if lesson.get("status") != "planned":
        raise ValueError(f"第 {number} 课（{canonical}）不是 planned，拒绝为已可用课程生成模板。")
    lessons_path = root / "lessons"
    if lessons_path.is_symlink() or lessons_path.resolve() != lessons_path:
        raise ValueError("lessons 目录必须位于项目根目录内，不能通过链接跳转。")
    known_ids = {canonical, *index.aliases(canonical)}
    for existing in lessons_path.glob("lesson_*/lesson.json"):
        manifest = json.loads(existing.read_text(encoding="utf-8"))
        if manifest.get("id") in known_ids:
            raise ValueError(f"第 {number} 课（{canonical}）已有实现清单：{existing}")
    directory = lesson_directory(canonical)
    target = lessons_path / directory
    if target.exists() or target.is_symlink():
        raise ValueError(f"目标已存在，拒绝覆盖：{target}")
    if not target.resolve().is_relative_to(root):
        raise ValueError("目标目录必须位于项目根目录内。")
    prefix = f"lessons/{directory}"
    manifest = {
        "schema_version": 1,
        "id": canonical,
        "content": "content.json",
        "sources": [
            {"path": f"{prefix}/{'main.py' if kind == 'native' else 'runtime.py'}", "language": "python"},
        ],
        "exercises": [
            {"id": "starter", "title": "待编写：课程实验", "question": "请复述：课程脚手架。"},
        ],
        "runtime": {"kind": kind, "entrypoint": "main" if kind == "native" else "runtime:run", "requires_model": kind == "native"},
    }
    # 新课从第一天起就是多语言的：运行时文本写在 locales/ 消息目录，问题与自然语言预设按语言分别填写。
    manifest["runtime"]["locales"] = ["zh-CN", "en"]
    manifest["exercises"][0]["question"] = {"zh-CN": "请复述：课程脚手架。", "en": "Please repeat: lesson scaffold."}
    manifest["sources"] += [{"path": f"{prefix}/locales/zh_CN.py", "language": "python", "locale": "zh-CN"},
                            {"path": f"{prefix}/locales/en.py", "language": "python", "locale": "en"}]
    if kind == "native":
        manifest["runtime"]["max_rounds"] = 3
        manifest["testing"] = {"completion_factory": "fixtures:create_completion"}
        manifest["sources"].insert(1, {"path": f"{prefix}/tools.py", "language": "python"})
    else:
        manifest["input_defaults"] = {"label": {"zh-CN": "课程脚手架", "en": "lesson scaffold"}}
        manifest["ui"] = {"lab": "structured-inputs"}
    manifest["sources"].append({"path": f"{prefix}/content.json", "language": "json"})
    content = {
        "sections": [
            {"title": "待编写：引言与学习目标", "body": "这是课程作者脚手架，尚未实现本课教学。请结合课程目录中的目标，解释本课为什么值得学习、先修知识与成功标准。"},
            {"title": "待编写：最小实现与实验", "body": "替换示例运行器，补充真实源码解读、可复现实验、失败边界和验收证据后，再开放课程。"},
        ],
        "observe": ["待编写：指出一个来自实际运行事件、可以核对的观察点。"],
        "quiz": [{
            "id": "authoring-check", "prompt": "这个脚手架是否表示本课已完成？",
            "options": [{"id": "yes", "text": "是，生成目录即已完成教学。"}, {"id": "no", "text": "否，还需要课程实现、教学内容和验证。"}],
            "correct_option": "no", "explanation": "脚手架只提供接入结构；课程仍保留 planned 状态。",
        }],
        "presentation": {
            "eyebrow": "课程草稿 · 待完成教学",
            "headline": "待编写：本课要解决什么问题",
            "highlight": "从问题到证据",
            "takeaway": "待编写：用一句话说明本课值得记住的机制。",
            "concepts": [
                {"label": "问题", "title": "待编写：学习动机", "description": "说明已有方法的边界和本课要解决的问题。", "token": "WHY"},
                {"label": "机制", "title": "待编写：关键概念", "description": "用最小例子解释机制，避免堆砌术语。", "token": "HOW"},
                {"label": "证据", "title": "待编写：验收方法", "description": "说明学生应从真实事件中核对什么。", "token": "PROOF"},
            ],
            "flow": {
                "title": "待编写：机制教学示意", "description": "这是作者占位示意，不是实际运行记录。",
                "steps": [
                    {"label": "目标", "actor": "学习者", "title": "待编写：确定目标", "body": "给出可验证的问题和成功标准。", "code": "# 待编写：真实示例代码", "language": "python", "evidence": "待编写：对应观察点"},
                    {"label": "实践", "actor": "课程实现", "title": "待编写：执行机制", "body": "解释本课实现如何推进任务。", "code": "# 待编写：真实示例代码", "language": "python", "evidence": "待编写：对应运行事件"},
                    {"label": "验收", "actor": "学习者", "title": "待编写：检查证据", "body": "用运行结果验证目标，而不是只看回答是否流畅。", "code": "# 待编写：真实验收代码", "language": "python", "evidence": "待编写：成功与失败边界"},
                ],
            },
        },
    }
    files = {
        "__init__.py": '"""Lesson implementation; whether it is open is decided by curriculum/catalog.json."""\n',
        "lesson.json": _json(manifest),
        "content.json": _json(content),
        "README.md": (
            f"# {lesson['title']}（待实现）\n\n"
            f"课程 ID：`{canonical}`。课号按目录顺序计算，只在网页上显示；文件里提到课程一律写课名或课程 ID。\n\n"
            "这是作者脚手架，课程仍为 `planned`，网页继续置灰。\n\n"
            "1. 以 `curriculum/catalog.json` 的目标与验收为准，替换占位实验和示例运行器。\n"
            "2. 完成 `content.json` 的引言、机制解释、观察点、自测，并替换 presentation 动效占位内容。\n"
            "3. 在 `lesson.json` 登记实际源码和练习；补全成功、失败、停止与输入校验测试。\n"
            "4. 运行课程测试和 `python scripts/validate_lessons.py`，再将目录状态改为 `available`。\n"
            "5. 运行 `python scripts/export_curriculum.py`，重启后端验证导航、实验和回放。\n\n"
            "脚手架自检（仅验证示例通路，不代表课程验收）：\n\n"
            f"```powershell\n.\\.venv\\Scripts\\python.exe -m unittest lessons.{directory}.test_lesson -v\n```\n\n"
            "完整接入规范：`docs/architecture/adding-lessons.md`。\n"
        ),
    }
    if kind == "native":
        files["main.py"] = textwrap.dedent(f'''\
            """TODO: replace with this lesson's agent setup."""

            from course.runner import AgentSetup
            from lessons.{directory}.locales import texts_for
            from lessons.{directory}.tools import available_tools, tool_definitions


            def setup(locale):
                """What the native loop sends in one run, in the run's language."""
                return AgentSetup(texts_for(locale).system_prompt, tool_definitions(locale), available_tools(locale))
            ''')
        files["tools.py"] = textwrap.dedent(f'''\
            """A side-effect-free example tool; replace it with the tools this lesson needs."""

            from functools import partial

            from lessons.{directory}.locales import texts_for


            def tool_definitions(locale):
                t = texts_for(locale)
                return [{{
                    "type": "function",
                    "function": {{
                        "name": "echo_text", "description": t.echo_text,
                        "parameters": {{
                            "type": "object", "properties": {{"text": {{"type": "string", "maxLength": 200}}}},
                            "required": ["text"], "additionalProperties": False,
                        }},
                    }},
                }}]


            def echo_text(t, /, text):
                # t (error messages of the run's language) is positional-only: model arguments cannot replace it.
                if not isinstance(text, str) or not text.strip() or len(text) > 200:
                    raise ValueError(t.text_invalid)
                return {{"text": text.strip()}}


            def available_tools(locale):
                return {{"echo_text": partial(echo_text, texts_for(locale))}}
            ''')
        files["locales/__init__.py"] = textwrap.dedent('''\
            """Runtime text of this lesson; zh_CN.py and en.py each fill every field."""
            from dataclasses import dataclass

            from course.i18n import catalog


            @dataclass(frozen=True)
            class Texts:
                system_prompt: str
                echo_text: str
                text_invalid: str


            texts_for = catalog(__name__, Texts)
            ''')
        files["locales/zh_CN.py"] = textwrap.dedent(f'''\
            """Runtime text: Simplified Chinese (the source language)."""
            from lessons.{directory}.locales import Texts

            TEXTS = Texts(
                system_prompt="调用 echo_text 工具复述文本，并依据工具结果回答。",
                echo_text="原样返回待复述文本。",
                text_invalid="text 必须是 1 至 200 字符的非空文本。",
            )
            ''')
        files["locales/en.py"] = textwrap.dedent(f'''\
            """Runtime text: English."""
            from lessons.{directory}.locales import Texts

            TEXTS = Texts(
                system_prompt="Call the echo_text tool to repeat the text, and answer from the tool result.",
                echo_text="Return the text to repeat, unchanged.",
                text_invalid="text must be non-empty text of 1 to 200 characters.",
            )
            ''')
        files["fixtures.py"] = textwrap.dedent('''\
            """Deterministic model responses for automated tests only; they never interpret free input."""

            import json

            from server.offline import offline_marker

            REPEAT = {"zh-CN": "课程脚手架", "en": "lesson scaffold"}


            def create_completion(exercise_id, inputs=None, locale="zh-CN"):
                if exercise_id != "starter":
                    raise ValueError(f"unknown offline exercise {exercise_id!r}")

                def complete(body, api_key):
                    results = [message for message in body["messages"] if message["role"] == "tool"]
                    message = {"role": "assistant", "content": None}
                    if results:
                        result = json.loads(results[-1]["content"])
                        message["content"] = offline_marker(locale) + json.dumps(result, ensure_ascii=False)
                    else:
                        message["tool_calls"] = [{
                            "id": "starter_call", "type": "function",
                            "function": {"name": "echo_text",
                                         "arguments": json.dumps({"text": REPEAT[locale]}, ensure_ascii=False)},
                        }]
                    return {"id": "starter_response", "object": "chat.completion", "model": "offline-script",
                            "choices": [{"index": 0, "message": message,
                                         "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]}
                return complete
            ''')
        files["test_lesson.py"] = textwrap.dedent(f'''\
            """Smoke test of the scaffold; add this lesson's acceptance tests before release. Never calls a model."""

            import unittest

            from course.runner import execute_tool, run_agent
            from lessons.{directory} import main
            from lessons.{directory}.fixtures import REPEAT, create_completion


            class LessonTests(unittest.TestCase):
                def test_real_tool_round_trip_in_every_locale(self):
                    for locale in ("zh-CN", "en"):
                        with self.subTest(locale=locale):
                            results = []
                            completion = create_completion("starter", locale=locale)
                            agent = main.setup(locale)

                            def execute(tool_call, available_tools):
                                results.append(execute_tool(tool_call, available_tools, locale))
                                return results[-1]

                            answer = run_agent("repeat", agent.system_prompt, agent.tools, agent.available_tools, 3,
                                               complete=lambda body, number: completion(body, ""), execute=execute,
                                               locale=locale)
                            self.assertEqual(results[0], {{"ok": True, "result": {{"text": REPEAT[locale]}}}})
                            self.assertIn(REPEAT[locale], answer)


            if __name__ == "__main__":
                unittest.main()
            ''')
    else:
        files["runtime.py"] = textwrap.dedent(f'''\
            """A custom runner example without a model; replace it with this lesson's flow."""

            from pydantic import Field

            from course.execution import LessonInputs, RunContext
            from lessons.{directory}.locales import texts_for


            class Inputs(LessonInputs):
                # No default: the preset in lesson.json supplies it in the run's language.
                label: str = Field(min_length=1, max_length=200)


            INPUT_MODEL = Inputs


            def run(context: RunContext):
                t = texts_for(context.locale)
                context.check_cancelled()
                label = context.inputs["label"]
                context.emit("lesson.step", {{"title": t.step_title, "label": label}})
                # The platform records the return value as the answer; this example calls no model.
                return t.answer.format(label=label)
            ''')
        files["locales/__init__.py"] = textwrap.dedent('''\
            """Runtime text of this lesson; zh_CN.py and en.py each fill every field."""
            from dataclasses import dataclass

            from course.i18n import catalog


            @dataclass(frozen=True)
            class Texts:
                step_title: str
                answer: str  # {label}


            texts_for = catalog(__name__, Texts)
            ''')
        files["locales/zh_CN.py"] = textwrap.dedent(f'''\
            """Runtime text: Simplified Chinese (the source language)."""
            from lessons.{directory}.locales import Texts

            TEXTS = Texts(step_title="本地示例步骤", answer="本地脚手架已执行：{{label}}")
            ''')
        files["locales/en.py"] = textwrap.dedent(f'''\
            """Runtime text: English."""
            from lessons.{directory}.locales import Texts

            TEXTS = Texts(step_title="Local example step", answer="The local scaffold ran: {{label}}")
            ''')
        files["test_lesson.py"] = textwrap.dedent(f'''\
            """Smoke test of the custom flow; add platform and acceptance tests before release."""

            from types import SimpleNamespace
            import unittest

            from pydantic import ValidationError

            from lessons.{directory}.runtime import INPUT_MODEL, run


            class LessonTests(unittest.TestCase):
                def test_local_step_uses_validated_input(self):
                    events = []
                    context = SimpleNamespace(
                        inputs=INPUT_MODEL(label="demo").model_dump(), locale="en",
                        check_cancelled=lambda: None,
                        emit=lambda kind, data: events.append((kind, data)),
                    )
                    self.assertEqual(run(context), "The local scaffold ran: demo")
                    self.assertEqual(events[0], ("lesson.step", {{"title": "Local example step", "label": "demo"}}))

                def test_rejects_invalid_input(self):
                    with self.assertRaises(ValidationError):
                        INPUT_MODEL(label="")


            if __name__ == "__main__":
                unittest.main()
            ''')
    # 所有生成代码先经过语法检查；失败时不会留下半套目录。
    for name, source in files.items():
        if name.endswith(".py"):
            compile(source, str(target / name), "exec")
    return target, files


def write_scaffold(target, files):
    """独占创建新目录，所有文件用 x 模式；从不覆盖现有文件。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    for name, source in files.items():
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        with (target / name).open("x", encoding="utf-8", newline="\n") as output:
            output.write(source)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="curriculum/catalog.json 中已有 planned 课程的 slug")
    parser.add_argument("--slug", help="可选；兼容旧命令，必须与目录中的课程 slug 一致（可写成 snake_case）")
    parser.add_argument("--kind", choices=("native", "custom"), default="native")
    parser.add_argument("--root", type=Path, default=ROOT, help="项目根目录，默认当前脚本所属项目")
    parser.add_argument("--dry-run", action="store_true", help="仅验证并列出将生成的文件")
    args = parser.parse_args(argv)
    try:
        target, files = build_scaffold(args.root, args.id, args.slug, args.kind)
        print(f"{'将创建' if args.dry_run else '创建'}：{target}")
        for name in files:
            print(f"  {target / name}")
        if not args.dry_run:
            write_scaffold(target, files)
        print("课程保持 planned，网页继续置灰；模板通过结构检查不代表课程已完成。")
        print("写正文前先读 docs/architecture/terminology.md（术语与代码名）；"
              "写完用 scripts/term_report.py --lesson <slug> --full 检查用词。")
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        print(f"课程脚手架失败：{error}", file=sys.stderr)
        print("没有覆盖现有文件；若写入中断，请检查新目录后再继续。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
