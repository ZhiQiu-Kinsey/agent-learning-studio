"""后端错误码与前端译文保持一致：每个固定文案的错误码都要有 zh-CN 译文。"""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "frontend" / "src" / "i18n" / "locales" / "zh-CN" / "errors.json"
# 文案由服务商校验动态生成，前端直接显示 detail。
DYNAMIC = {"settings_invalid"}


def backend_codes() -> set[str]:
    codes = set()
    for path in (ROOT / "server").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "ApiError" and len(node.args) >= 2:
                code = node.args[1]
                if isinstance(code, ast.Constant) and isinstance(code.value, str):
                    codes.add(code.value)
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant) and key.value == "code"
                            and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                        codes.add(value.value)
    return codes


class ErrorCodeTests(unittest.TestCase):
    def test_every_fixed_error_code_has_a_translation(self):
        translated = set(json.loads(LOCALE.read_text(encoding="utf-8"))["code"])
        codes = backend_codes()
        self.assertGreaterEqual(len(codes), 20)
        self.assertEqual(sorted(codes - DYNAMIC - translated), [], "缺少前端译文的错误码")
        self.assertEqual(sorted(translated - codes), [], "前端存在后端已不再使用的错误码")


if __name__ == "__main__":
    unittest.main()
