"""把课程内容与导学迁移到当前 content 版本并写回（幂等；比平台新的内容会报错且不改动）。

用法：python scripts/migrate_content.py [--check]
--check 只检查是否还有待迁移文件，有则以非零状态退出。
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.content_migrations import LESSON_STEPS, ONBOARDING_STEPS, migrate  # noqa: E402
from server.content_schema import CONTENT_VERSION, LessonContent, Onboarding  # noqa: E402

SCHEMA_DIR = ROOT / "curriculum" / "schema"


def schema_ref(path: Path, name: str) -> str:
    return Path(os.path.relpath(SCHEMA_DIR / name, path.parent)).as_posix()


def dump(model, ref: str) -> str:
    # 默认值只在 schema 里声明，文件不重复写；$schema 只为编辑器补全，不进入模型输出。
    data = {"$schema": ref, **model.model_dump(mode="json", by_alias=True, exclude_defaults=True)}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def targets():
    for lesson_path in sorted((ROOT / "lessons").glob("*/lesson.json")):
        lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
        path = lesson_path.parent / lesson.get("content", "content.json")
        context = {"lesson": lesson["id"], "subtitle": lesson["subtitle"], "exercises": lesson["exercises"]}
        yield path, LESSON_STEPS, context, LessonContent, "content.v2.schema.json"
    yield ROOT / "curriculum" / "onboarding.json", ONBOARDING_STEPS, {}, Onboarding, "onboarding.v2.schema.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    pending = []
    for path, steps, context, model, schema_name in targets():
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = migrate(raw, steps, context)
        text = dump(model.model_validate(data), schema_ref(path, schema_name))
        if path.read_text(encoding="utf-8") != text:
            pending.append(path)
            if not args.check:
                path.write_text(text, encoding="utf-8", newline="\n")
    label = "待迁移" if args.check else "已写入"
    for path in pending:
        print(f"{label}：{path.relative_to(ROOT).as_posix()}")
    print(f"content v{CONTENT_VERSION}：{len(pending)} 个文件{label}")
    return 1 if args.check and pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
