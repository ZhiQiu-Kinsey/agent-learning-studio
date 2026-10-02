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
    if kind == "native":
        manifest["runtime"]["max_rounds"] = 3
        manifest["testing"] = {"completion_factory": "fixtures:create_completion"}
        manifest["sources"].append({"path": f"{prefix}/tools.py", "language": "python"})
    else:
        manifest["input_defaults"] = {"label": "课程脚手架"}
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
        "__init__.py": '"""课程实现；以 curriculum/catalog.json 中的状态为准。"""\n',
        "lesson.json": _json(manifest),
        "content.json": _json(content),
        "README.md": (
            f"# 第 {number} 课 · {lesson['title']}（待实现）\n\n"
            f"课程 ID：`{canonical}`。课号按目录顺序计算，只用于显示；代码与链接使用课程 ID。\n\n"
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
            """待实现：替换为本课教学提示词。"""

            from lessons.{directory}.tools import AVAILABLE_TOOLS, TOOLS


            SYSTEM_PROMPT = "调用 echo_text 工具复述文本，并依据工具结果回答。"
            ''')
        files["tools.py"] = textwrap.dedent('''\
            """无副作用的接入示例；请替换为课程需要的真实工具。"""


            def echo_text(text):
                if not isinstance(text, str) or not text.strip() or len(text) > 200:
                    raise ValueError("text 必须是 1 至 200 字符的非空文本。")
                return {"text": text.strip()}


            TOOLS = [{
                "type": "function",
                "function": {
                    "name": "echo_text", "description": "原样返回待复述文本。",
                    "parameters": {
                        "type": "object", "properties": {"text": {"type": "string", "maxLength": 200}},
                        "required": ["text"], "additionalProperties": False,
                    },
                },
            }]
            AVAILABLE_TOOLS = {"echo_text": echo_text}
            ''')
        files["fixtures.py"] = textwrap.dedent('''\
            """仅供自动化测试的确定性模型响应；不会解释自由输入。"""

            import json


            def create_completion(exercise_id, inputs=None):
                if exercise_id != "starter":
                    raise ValueError("未知测试练习。")

                def complete(body, api_key):
                    results = [message for message in body["messages"] if message["role"] == "tool"]
                    message = {"role": "assistant", "content": None}
                    if results:
                        result = json.loads(results[-1]["content"])
                        message["content"] = "【确定性测试】" + json.dumps(result, ensure_ascii=False)
                    else:
                        message["tool_calls"] = [{
                            "id": "starter_call", "type": "function",
                            "function": {"name": "echo_text", "arguments": json.dumps({"text": "课程脚手架"}, ensure_ascii=False)},
                        }]
                    return {"id": "starter_response", "object": "chat.completion", "model": "offline-script",
                            "choices": [{"index": 0, "message": message,
                                         "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]}
                return complete
            ''')
        files["test_lesson.py"] = textwrap.dedent(f'''\
            """接入冒烟测试；发布前补充本课验收，不调用外部模型。"""

            import unittest

            from course.runner import execute_tool, run_agent
            from lessons.{directory} import main
            from lessons.{directory}.fixtures import create_completion


            class LessonTests(unittest.TestCase):
                def test_real_tool_round_trip(self):
                    results = []
                    completion = create_completion("starter")

                    def execute(tool_call, available_tools):
                        results.append(execute_tool(tool_call, available_tools))
                        return results[-1]

                    answer = run_agent("请复述：课程脚手架。", main.SYSTEM_PROMPT, main.TOOLS, main.AVAILABLE_TOOLS, 3,
                                       complete=lambda body, number: completion(body, ""), execute=execute)
                    self.assertEqual(results[0], {{"ok": True, "result": {{"text": "课程脚手架"}}}})
                    self.assertIn("课程脚手架", answer)


            if __name__ == "__main__":
                unittest.main()
            ''')
    else:
        files["runtime.py"] = textwrap.dedent('''\
            """无模型的定制运行器示例；替换为本课实际流程。"""

            from pydantic import Field

            from course.execution import LessonInputs, RunContext


            class Inputs(LessonInputs):
                label: str = Field(default="课程脚手架", min_length=1, max_length=200)


            INPUT_MODEL = Inputs


            def run(context: RunContext):
                context.check_cancelled()
                label = context.inputs["label"]
                context.emit("lesson.step", {"title": "本地示例步骤", "label": label})
                # 平台记录返回值为 answer；此示例没有调用模型。
                return "本地脚手架已执行：" + label
            ''')
        files["test_lesson.py"] = textwrap.dedent(f'''\
            """定制流程冒烟测试；发布前补充平台接入与本课验收测试。"""

            from types import SimpleNamespace
            import unittest

            from pydantic import ValidationError

            from lessons.{directory}.runtime import INPUT_MODEL, run


            class LessonTests(unittest.TestCase):
                def test_local_step_uses_validated_input(self):
                    events = []
                    context = SimpleNamespace(
                        inputs=INPUT_MODEL(label="实验").model_dump(),
                        check_cancelled=lambda: None,
                        emit=lambda kind, data: events.append((kind, data)),
                    )
                    self.assertEqual(run(context), "本地脚手架已执行：实验")
                    self.assertEqual(events[0], ("lesson.step", {{"title": "本地示例步骤", "label": "实验"}}))

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
