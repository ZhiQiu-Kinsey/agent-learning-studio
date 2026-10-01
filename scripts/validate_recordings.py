"""校验 lessons/*/recordings/ 下的全部随课录制，不调用模型。

检查完整性哈希、信封 v2 结构（seq 连续、span 配对）、provenance、表示层级与元数据一致、
源码哈希是否与当前实现一致，以及是否含密钥或本机私有路径。
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def collect(root, specs=None):
    """返回 (通过数, [(相对路径, 错误)])；specs 为空时按 root 重新加载全部课程（含 planned）。"""
    from server.catalog import load_lessons
    from server.providers import ProviderRegistry
    from server.recordings import validate_lesson_recordings

    root = Path(root).resolve()
    if specs is None:
        specs = load_lessons(root=root, include_planned=True)
    return validate_lesson_recordings(root, specs, ProviderRegistry().api_keys())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="项目根目录")
    args = parser.parse_args(argv)
    try:
        passed, failures = collect(args.root)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        print(f"录制校验失败：{error}", file=sys.stderr)
        return 1
    for path, message in failures:
        print(f"录制无效 {path}：{message}", file=sys.stderr)
    print(f"随课录制：{passed} 份通过，{len(failures)} 份未通过。")
    return 1 if failures else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
