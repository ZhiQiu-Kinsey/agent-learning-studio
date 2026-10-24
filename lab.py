"""Agent Learning Studio 的统一入口：所有平台都用 `uv run lab.py <命令>`。

    uv run lab.py          装好前端依赖、按需构建前端，然后启动 http://127.0.0.1:8765
    uv run lab.py check    提交前的检查：课程校验、Python 测试、前端构建、前端单元测试、翻译键
    uv run lab.py site     构建并预览官网（site/）

`uv run` 会先按 uv.lock 同步 Python 依赖；npm 依赖和前端构建由这里判断是否过期，
没变就跳过。Windows 下 npm 是 npm.cmd，这里用 shutil.which 找，命令在各平台相同。
单独的命令（run_web.py、scripts/*.py、npm --prefix …）照常可用。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
SITE = ROOT / "site"
HOST, PORT = "127.0.0.1", 8765

# 前端构建产物依赖的输入；任何一个比 dist/index.html 新，就重新构建。
BUILD_INPUTS = ("src", "public", "index.html", "package.json", "package-lock.json", "vite.config.ts",
                "tsconfig.json")


class LabError(RuntimeError):
    """给使用者看的错误：说清缺了什么、怎么补，不打印堆栈。"""


def newest_mtime(paths: list[Path]) -> float:
    """这些文件和目录（递归）里最新的修改时间；都不存在时为 0。"""
    newest = 0.0
    for path in paths:
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    newest = max(newest, item.stat().st_mtime)
    return newest


def needs_install(package_dir: Path) -> bool:
    """node_modules 不存在，或 package-lock.json 比上次安装记录新。"""
    marker = package_dir / "node_modules" / ".package-lock.json"
    lock = package_dir / "package-lock.json"
    return not marker.is_file() or (lock.is_file() and lock.stat().st_mtime > marker.stat().st_mtime)


def needs_build(package_dir: Path, inputs: tuple[str, ...] = BUILD_INPUTS) -> bool:
    """dist/index.html 不存在，或任何构建输入比它新。"""
    built = package_dir / "dist" / "index.html"
    if not built.is_file():
        return True
    return newest_mtime([package_dir / name for name in inputs]) > built.stat().st_mtime


def npm() -> str:
    found = shutil.which("npm")
    if not found:
        raise LabError("npm was not found. Install Node.js 22.12+ (it includes npm), then run this again.")
    return found


def run(step: str, command: list[str]) -> None:
    # 显示 python / npm 而不是本机的绝对路径（npm.cmd 的 stem 也是 npm）。
    program = "python" if command[0] == sys.executable else Path(command[0]).stem
    print(f"\n== {step}\n$ {' '.join([program, *command[1:]])}", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise LabError(f"{step} failed (exit code {result.returncode}).")


def ensure_frontend(force_build: bool = False) -> None:
    if needs_install(FRONTEND):
        run("Install frontend dependencies", [npm(), "--prefix", "frontend", "ci"])
    if force_build or needs_build(FRONTEND):
        run("Build the web UI", [npm(), "--prefix", "frontend", "run", "build"])


def start(args: argparse.Namespace) -> None:
    ensure_frontend(force_build=args.rebuild)
    import uvicorn  # 依赖由 uv run 同步；放在这里，check / site 不需要它

    print(f"\nAgent Learning Studio: http://{HOST}:{args.port}\nKeep this terminal open. Press Ctrl+C to stop.",
          flush=True)
    uvicorn.run("server.app:app", host=HOST, port=args.port, log_level="warning", access_log=False)


# 与 .github/workflows/ci.yml 相同的检查（浏览器测试除外），外加 AGENTS.md 要求的硬编码中文基线。
# 快的放前面：几秒就能报出的问题，不必等十几分钟的完整测试。
CHECKS = (
    ("Validate lessons", ["scripts/validate_lessons.py"]),
    ("Content v2 migration check", ["scripts/migrate_content.py", "--check"]),
    ("Course plan in sync", ["scripts/export_curriculum.py", "--check"]),
    ("Trace contract in sync", ["scripts/export_trace_contract.py", "--check"]),
    ("Content JSON Schema in sync", ["scripts/export_content_schema.py", "--check"]),
    ("Code-reading notes aligned", ["scripts/realign_notes.py", "--check"]),
    ("Hard-coded Chinese baseline", ["scripts/cjk_baseline.py", "--check"]),
)


def check(_: argparse.Namespace) -> None:
    for step, arguments in CHECKS:
        run(step, [sys.executable, *arguments])
    if needs_install(FRONTEND):
        run("Install frontend dependencies", [npm(), "--prefix", "frontend", "ci"])
    run("Type-check and build the web UI", [npm(), "--prefix", "frontend", "run", "build"])
    run("Frontend unit tests", [npm(), "--prefix", "frontend", "run", "test"])
    run("Translation keys", [npm(), "--prefix", "frontend", "run", "i18n:check"])
    # 完整的 Python 测试最慢，放在最后。
    run("Python tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    print("\nAll checks passed. Browser tests are separate: see docs/architecture/validation.md.")


def site(_: argparse.Namespace) -> None:
    if needs_install(SITE):
        run("Install website dependencies", [npm(), "--prefix", "site", "ci"])
    run("Build the website", [npm(), "--prefix", "site", "run", "build"])
    print("\nWebsite preview: http://127.0.0.1:4173/agent-learning-studio/", flush=True)
    run("Preview the website", [npm(), "--prefix", "site", "run", "preview"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uv run lab.py", description="Agent Learning Studio: one entry point.")
    parser.set_defaults(handler=start, port=PORT, rebuild=False)
    commands = parser.add_subparsers(title="commands", metavar="[start | check | site]")
    start_parser = commands.add_parser("start", help="install, build when needed and start the server (default)")
    start_parser.add_argument("--port", type=int, default=PORT, help=f"port to listen on (default {PORT})")
    start_parser.add_argument("--rebuild", action="store_true", help="rebuild the web UI even if it looks current")
    start_parser.set_defaults(handler=start)
    commands.add_parser("check", help="run the checks to pass before a commit").set_defaults(handler=check)
    commands.add_parser("site", help="build and preview the website in site/").set_defaults(handler=site)
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except LabError as error:
        print(f"\n{error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
