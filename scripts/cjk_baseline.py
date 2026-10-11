"""课程与平台运行代码里硬编码中文的基线：只许减少。

统计 course/ 与 lessons/ 下 Python 文件中含中文的字符串字面量（文档字符串也算，注释不算）。
运行时文本应写进 locales/ 消息目录：源语言目录（locales/zh_CN.py）按路径豁免，测试文件（test_*.py）不统计。
用法：python scripts/cjk_baseline.py           # 重新生成 tests/baselines/python-cjk.json
      python scripts/cjk_baseline.py --check   # 只比较，变多或该收紧时以非零状态退出
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "baselines" / "python-cjk.json"
CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
SCOPES = ("course", "lessons")


def exempt(relative: str) -> bool:
    parts = relative.split("/")
    return parts[-1].startswith("test_") or (parts[-1] == "zh_CN.py" and "locales" in parts)


def count(text: str) -> int:
    """含中文的字符串字面量个数；一个 f-string 算一处。"""
    total = 0

    def visit(node, inside_fstring=False):
        nonlocal total
        if isinstance(node, ast.JoinedStr):
            if any(isinstance(part, ast.Constant) and isinstance(part.value, str) and CJK.search(part.value)
                   for part in node.values):
                total += 1
            for part in node.values:
                visit(part, True)
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and not inside_fstring:
            total += bool(CJK.search(node.value))
        for child in ast.iter_child_nodes(node):
            visit(child, inside_fstring and not isinstance(child, ast.FormattedValue))

    visit(ast.parse(text))
    return total


def scan(root: Path = ROOT) -> dict[str, int]:
    counts = {}
    for scope in SCOPES:
        for path in sorted((root / scope).rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if "__pycache__" in relative or exempt(relative):
                continue
            found = count(path.read_text(encoding="utf-8"))
            if found:
                counts[relative] = found
    return counts


def compare(current: dict[str, int], baseline: dict[str, int]) -> tuple[list[str], list[str]]:
    """（变多的文件，已减少、应收紧基线的文件）。"""
    grew = [f"{file}: {baseline.get(file, 0)} -> {value}" for file, value in current.items()
            if value > baseline.get(file, 0)]
    shrank = [f"{file}: {value} -> {current.get(file, 0)}" for file, value in baseline.items()
              if current.get(file, 0) < value]
    return grew, shrank


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    current = scan()
    if args.check:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {}
        grew, shrank = compare(current, baseline)
        for line in grew:
            print("新增硬编码中文（移到 locales/ 消息目录）：" + line, file=sys.stderr)
        for line in shrank:
            print("已减少，请运行 python scripts/cjk_baseline.py 收紧基线：" + line, file=sys.stderr)
        print(f"Python 硬编码中文：{sum(current.values())} 处，{len(current)} 个文件。")
        return 1 if grew or shrank else 0
    BASELINE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"已更新 {BASELINE.relative_to(ROOT).as_posix()}：{sum(current.values())} 处，{len(current)} 个文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
