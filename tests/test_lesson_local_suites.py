"""把各课目录里的 test_lesson.py 并入完整测试；新课的行为测试放在课程目录，与实现一起维护。"""
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_tests(loader, standard_tests, pattern):
    for path in sorted((ROOT / "lessons").glob("lesson_*/test_lesson.py")):
        module = importlib.import_module(f"lessons.{path.parent.name}.test_lesson")
        standard_tests.addTests(loader.loadTestsFromModule(module))
    return standard_tests
