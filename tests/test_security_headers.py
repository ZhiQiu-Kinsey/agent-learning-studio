import unittest

from fastapi.testclient import TestClient

from server.app import app


class SecurityHeadersTest(unittest.TestCase):
    def test_csp_allows_webassembly_but_not_script_eval(self):
        client = TestClient(app, base_url="http://localhost")
        policy = client.get("/api/status").headers["content-security-policy"]
        directives = dict(
            (part.split()[0], part.split()[1:])
            for part in (item.strip() for item in policy.split(";"))
            if part
        )
        self.assertEqual(directives["script-src"], ["'self'", "'wasm-unsafe-eval'"])
        self.assertNotIn("'unsafe-eval'", policy)
        self.assertEqual(directives["frame-ancestors"], ["'none'"])
        self.assertIn("blob:", directives["img-src"])
        self.assertEqual(directives["connect-src"], ["'self'", "blob:"])


if __name__ == "__main__":
    unittest.main()
