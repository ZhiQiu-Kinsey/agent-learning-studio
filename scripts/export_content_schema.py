"""导出课程内容 v2 的 JSON Schema；前端再由它生成 TS 类型（npm run content:types）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.content_schema import json_schemas  # noqa: E402

SCHEMA_DIR = ROOT / "curriculum" / "schema"


def render(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, schema in json_schemas().items():
        (SCHEMA_DIR / name).write_text(render(schema), encoding="utf-8", newline="\n")
        print(f"写入 curriculum/schema/{name}")


if __name__ == "__main__":
    main()
