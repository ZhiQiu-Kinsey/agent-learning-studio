"""导出课程内容 v2 的 JSON Schema；前端再由它生成 TS 类型（npm run content:types）。

用法：python scripts/export_content_schema.py [--check]
--check 只比较已提交的 schema 与模型是否一致，不写文件；不一致时以非零状态退出。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.content_schema import json_schemas  # noqa: E402

SCHEMA_DIR = ROOT / "curriculum" / "schema"


def render(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    stale = []
    for name, schema in json_schemas().items():
        path = SCHEMA_DIR / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != render(schema):
                stale.append(name)
            continue
        SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(render(schema), encoding="utf-8", newline="\n")
        print(f"写入 curriculum/schema/{name}")
    for name in stale:
        print(f"过期：curriculum/schema/{name}（运行 scripts/export_content_schema.py 重新导出）")
    return 1 if stale else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
