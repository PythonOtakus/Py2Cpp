"""``scripts/match_test_files.py`` 路径匹配。"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "match_test_files.py"


def _run(*patterns: str) -> subprocess.CompletedProcess[str]:
  return subprocess.run(
    [sys.executable, str(SCRIPT), *patterns],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    check=False,
  )


class MatchTestFilesTests(unittest.TestCase):
  def test_substring_vararg(self):
    cp = _run("vararg")
    self.assertEqual(cp.returncode, 0)
    lines = [ln for ln in cp.stdout.splitlines() if ln]
    self.assertEqual(lines, ["lang\\test_vararg_pack.py"])

  def test_substring_variadic(self):
    cp = _run("variadic")
    self.assertEqual(cp.returncode, 0)
    self.assertIn("lang\\test_variadic_template.py", cp.stdout)

  def test_wildcard(self):
    cp = _run(r"lang\test_*variadic*")
    self.assertEqual(cp.returncode, 0)
    self.assertIn("lang\\test_variadic_template.py", cp.stdout)
    self.assertNotIn("test_vararg_pack", cp.stdout)

  def test_no_match(self):
    cp = _run("zzz_no_such_test_zzz")
    self.assertEqual(cp.returncode, 1)
    self.assertEqual(cp.stdout.strip(), "")


if __name__ == "__main__":
  unittest.main()
