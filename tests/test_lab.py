"""lab.py 判断“要不要装 npm 依赖、要不要重新构建”的规则。"""
import os
import tempfile
import time
import unittest
from pathlib import Path

import lab


def touch(path: Path, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, (mtime, mtime))


class NeedsInstallTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.now = time.time()

    def test_missing_node_modules_needs_install(self):
        touch(self.dir / "package-lock.json", self.now)
        self.assertTrue(lab.needs_install(self.dir))

    def test_lockfile_newer_than_last_install_needs_install(self):
        touch(self.dir / "node_modules" / ".package-lock.json", self.now - 100)
        touch(self.dir / "package-lock.json", self.now)
        self.assertTrue(lab.needs_install(self.dir))

    def test_installed_after_lockfile_is_current(self):
        touch(self.dir / "package-lock.json", self.now - 100)
        touch(self.dir / "node_modules" / ".package-lock.json", self.now)
        self.assertFalse(lab.needs_install(self.dir))


class NeedsBuildTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.now = time.time()

    def test_missing_build_needs_build(self):
        touch(self.dir / "src" / "main.tsx", self.now)
        self.assertTrue(lab.needs_build(self.dir))

    def test_source_newer_than_build_needs_build(self):
        touch(self.dir / "dist" / "index.html", self.now - 100)
        # 改动深在子目录里也要算进去。
        touch(self.dir / "src" / "stage" / "AgentStage.tsx", self.now)
        self.assertTrue(lab.needs_build(self.dir))

    def test_build_newer_than_every_input_is_current(self):
        touch(self.dir / "src" / "main.tsx", self.now - 100)
        touch(self.dir / "package-lock.json", self.now - 100)
        touch(self.dir / "dist" / "index.html", self.now)
        self.assertFalse(lab.needs_build(self.dir))

    def test_files_outside_the_inputs_do_not_trigger_a_build(self):
        touch(self.dir / "dist" / "index.html", self.now - 100)
        touch(self.dir / "e2e" / "studio.spec.ts", self.now)
        self.assertFalse(lab.needs_build(self.dir))


if __name__ == "__main__":
    unittest.main()
