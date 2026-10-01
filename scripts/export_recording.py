"""从运行存储原样导出一份随课录制（recorded_run）。

只导出真实模型（live）且状态为 completed 或 error 的运行；事件只把 provenance 改为
recorded_run。导出前检查密钥与本机私有路径，发现时拒绝并只报告位置。

用法：python scripts/export_recording.py --run <run_id> --name <kebab-case 名称>
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, help="运行编号（32 位十六进制，可在 /api/runs 中查到）")
    parser.add_argument("--name", required=True, help="录制名称，kebab-case，例如 sum-qwen-plus")
    parser.add_argument("--db", type=Path, default=ROOT / ".runtime" / "runs.sqlite3", help="运行存储路径")
    parser.add_argument("--replace", action="store_true", help="替换同名录制")
    args = parser.parse_args(argv)

    from server.catalog import load_lessons
    from server.providers import ProviderRegistry
    from server.recordings import ExportRefused, export_run

    try:
        specs = load_lessons(root=ROOT, include_planned=True)
        # 只能读取本进程可见的密钥（环境变量与本地配置）；网页中临时填写的密钥在写库时已被脱敏。
        target = export_run(args.db, args.run, args.name, root=ROOT, specs=specs,
                            keys=ProviderRegistry().api_keys(), replace=args.replace)
    except ExportRefused as error:
        print(f"拒绝导出：{error}", file=sys.stderr)
        return 1
    print(f"已导出：{target.relative_to(ROOT).as_posix()}")
    print("请运行 python scripts/validate_recordings.py 复核，并在提交前人工检查内容。")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
