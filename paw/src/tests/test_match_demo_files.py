"""``scripts/match_demo_files.py`` 路径匹配。"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "match_demo_files.py"


def _run(*patterns: str) -> subprocess.CompletedProcess[str]:
  return subprocess.run(
    [sys.executable, str(SCRIPT), *patterns],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    check=False,
  )


class MatchDemoFilesTests(unittest.TestCase):
  def test_substring_panel(self):
    cp = _run("panel")
    self.assertEqual(cp.returncode, 0)
    lines = [ln for ln in cp.stdout.splitlines() if ln]
    self.assertEqual(lines, ["ui_panel_demo.py"])

  def test_wildcard(self):
    cp = _run("*ui*")
    self.assertEqual(cp.returncode, 0)
    self.assertIn("ui_panel_demo.py", cp.stdout)

  def test_no_match(self):
    cp = _run("zzz_no_such_demo_zzz")
    self.assertEqual(cp.returncode, 1)
    self.assertEqual(cp.stdout.strip(), "")


if __name__ == "__main__":
  unittest.main()
