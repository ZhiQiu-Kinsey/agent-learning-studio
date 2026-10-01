"""从 server/envelope.py 生成前端事件信封常量。修改信封常量表后执行；--check 检查是否同步。"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend/src/generated/trace-contract.ts"


def render() -> str:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from server.envelope import trace_contract

    body = json.dumps(trace_contract(), ensure_ascii=False, indent=2)
    return ("// 此文件由 scripts/export_trace_contract.py 从 server/envelope.py 生成，请勿手改。\n"
            "// 修改后端常量表后运行：python scripts/export_trace_contract.py\n"
            f"export const TRACE_CONTRACT = {body} as const;\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != output:
            raise SystemExit("前端事件信封常量需要更新：python scripts/export_trace_contract.py")
        print("Trace contract is in sync.")
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(output, encoding="utf-8", newline="\n")
        print("Updated frontend/src/generated/trace-contract.ts")


if __name__ == "__main__":
    main()
