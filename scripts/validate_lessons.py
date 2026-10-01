"""检查全部课程实现清单、课程 ID 与术语表，包含 planned 草稿，不调用模型。"""

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def validate(root):
    # 放在函数中，导入时的配置错误也能在 CLI 中显示为开发诊断。
    from server.catalog import load_lessons

    return load_lessons(root=Path(root).resolve(), include_planned=True)


def validate_glossary(root):
    """术语表存在时校验 id、必填字段与课程引用；返回条目数，缺少文件时返回 None。"""
    from server.catalog import _json
    from server.curriculum import index_catalog
    from server.glossary import GLOSSARY_FILE, load_glossary

    root = Path(root).resolve()
    if not root.joinpath(*GLOSSARY_FILE).is_file():
        return None
    index = index_catalog(_json(root / "curriculum" / "catalog.json"))
    return len(load_glossary(root, index)["terms"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="包含 curriculum/catalog.json 的项目根目录")
    args = parser.parse_args(argv)
    try:
        specs = validate(args.root)
        terms = validate_glossary(args.root)
        available = sum(spec.get("status") == "available" for spec in specs)
        print(f"校验通过：{len(specs)} 份课程实现清单（{available} 可用，{len(specs) - available} 规划草稿）。")
        for spec in specs:
            aliases = "、".join(spec.get("aliases", [])) or "无"
            print(f"  第 {spec['number']} 课 {spec['id']}（别名：{aliases}）[{spec['status']}] {spec['title']}")
        print(f"术语表：{terms} 条。" if terms is not None else "术语表：未找到 curriculum/glossary.json，已跳过。")
        print("未调用模型；结构校验不代替课程测试与教学验收，planned 课程不会因此解锁。")
        return 0
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(f"课程校验失败（项目：{args.root.resolve()}）：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
