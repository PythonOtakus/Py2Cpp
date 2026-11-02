"""Rename integration-test path tokens test→tests without touching paw.test / src/tests."""
from __future__ import annotations

from pathlib import Path

ROOTS = [Path("paw"), Path("zeus"), Path(".cursor")]
SKIP_DIRS = {".git", "generated", "__pycache__", "node_modules", "vendor", ".cache"}
EXTS = {".py", ".paw", ".bat", ".md", ".txt", ".json", ".h", ".inl", ".cpp"}

HOLDERS = [
  ("paw/test/", "paw/test/"),
  ("paw\\tests\\", "paw\test\"),
  ("paw.test.", "paw.test."),
  ("paw/test\"", "paw/test""),
  ("paw/test'", "paw/test'"),
  ("src/tests", "src/tests"),
  ("src\\tests", "src\tests"),
]

# Order matters: longer / more specific first
REPLACEMENTS = [
  ("generated/tests/", "generated/tests/"),
  ("generated\\tests\\", "generated\\tests\\"),
  ("generated/test\"", "generated/tests\""),
  ("generated\\tests\"", "generated\\tests\""),
  ("modules/tests/", "modules/tests/"),
  ("tests/**/test_", "tests/**/test_"),
  ("test\\**\\test_", "tests\\**\\test_"),
  ("tests/**/*.py", "tests/**/*.py"),
  ("tests/**/*.paw", "tests/**/*.paw"),
  ("ROOT / \"test\"", 'ROOT / "tests"'),
  ("root / \"test\"", 'root / "tests"'),
  ("REPO / \"test\"", 'REPO / "tests"'),
  ("Path(\"test\")", 'Path("tests")'),
  ("Path('tests')", "Path('tests')"),
  ('/ "tests"', '/ "tests"'),
  (" / \"test\" /", ' / "tests" /'),
  (" / \"test\"", ' / "tests"'),
  ('"tests/",', '"tests/",'),
  ("'tests/',", "'tests/',"),
  ("src_root=\"test\"", 'src_root="tests"'),
  ("src_root='tests'", "src_root='tests'"),
  ('_SCAN_ROOTS = ("paw", "tests", "examples")', '_SCAN_ROOTS = ("paw", "tests", "examples")'),
  ('for root in ("paw", "tests", "compiler/paw")', 'for root in ("paw", "tests", "compiler/paw")'),
  ('default=["paw", "tests", "compiler"]', 'default=["paw", "tests", "compiler"]'),
  ('("paw", "tests", "examples")', '("paw", "tests", "examples")'),
  ('["paw", "tests", "examples"]', '["paw", "tests", "examples"]'),
  ('for d in ("paw", "tests", "examples")', 'for d in ("paw", "tests", "examples")'),
  ('for root_name in ("paw", "tests", "examples")', 'for root_name in ("paw", "tests", "examples")'),
  ('DIRS = ("paw", "tests", "examples"', 'DIRS = ("paw", "tests", "examples"'),
  ('Section("集成测试", "tests",', 'Section("集成测试", "tests",'),
  ('test_dir = ROOT / "tests"', 'test_dir = ROOT / "tests"'),
  ('test_dir = root / "tests"', 'test_dir = root / "tests"'),
  ('fail_dir = ROOT / "tests"', 'fail_dir = ROOT / "tests"'),
  ('TEST_DIR = ROOT / "tests"', 'TEST_DIR = ROOT / "tests"'),
  ('test_root = ROOT / "generated" / "tests"', 'test_root = ROOT / "generated" / "tests"'),
  ('Job(rel=rel, src_root="tests")', 'Job(rel=rel, src_root="tests")'),
  ('Job(rel=rel, src_root="tests", expect_fail=True)', 'Job(rel=rel, src_root="tests", expect_fail=True)'),
  ('src_root = "tests"', 'src_root = "tests"'),
  ('"tests" in parts or "examples"', '"tests" in parts or "examples"'),
  ("'tests' in parts or 'examples'", "'tests' in parts or 'examples'"),
  ('norm.startswith(\'tests/fail/\')', "norm.startswith('tests/fail/')"),
  ('norm.startswith("tests/fail/")', 'norm.startswith("tests/fail/")'),
  ('"modules/tests/', '"modules/tests/'),
  ("'modules/tests/", "'modules/tests/"),
  ('out / "tests" /', 'out / "tests" /'),
  (' / "tests" / "serde"', ' / "tests" / "serde"'),
  ('Path("generated/tests/', 'Path("generated/tests/'),
  ("Path('generated/tests/", "Path('generated/tests/"),
  ('root=ROOT / "tests"', 'root=ROOT / "tests"'),
  ('ROOT / "tests",', 'ROOT / "tests",'),
  ('list((root / "tests")', 'list((root / "tests")'),
  ('(root / "tests")', '(root / "tests")'),
  ('--root tests ', '--root tests '),
  ("test\\fail\\", "tests\\fail\\"),
  ("tests/fail/", "tests/fail/"),
  ("test\\perf\\", "tests\\perf\\"),
  ("tests/perf/", "tests/perf/"),
  ("test\\lang\\", "tests\\lang\\"),
  ("tests/lang/", "tests/lang/"),
  ("test\\misc\\", "tests\\misc\\"),
  ("tests/misc/", "tests/misc/"),
  ("test\\serde\\", "tests\\serde\\"),
  ("tests/serde/", "tests/serde/"),
  ("test\\ui\\", "tests\\ui\\"),
  ("tests/ui/", "tests/ui/"),
  ("test\\io\\", "tests\\io\\"),
  ("tests/io/", "tests/io/"),
  ("test\\util\\", "tests\\util\\"),
  ("tests/util/", "tests/util/"),
  ("test\\web\\", "tests\\web\\"),
  ("tests/web/", "tests/web/"),
  ("test\\core\\", "tests\\core\\"),
  ("tests/core/", "tests/core/"),
  ("test\\import_tests", "tests\\import_tests"),
  ("tests/import_tests", "tests/import_tests"),
  ("under tests/", "under tests/"),
  ("``tests/", "``tests/"),
  ("`tests/", "`tests/"),
  (" tests/", " tests/"),
  ("\\tests\\", "\\tests\\"),
  # bats echo text
  ("test\\**\\", "tests\\**\\"),
]


def main() -> None:
  n = 0
  for base in ROOTS:
    if not base.exists():
      continue
    for path in base.rglob("*"):
      if not path.is_file():
        continue
      if any(s in path.parts for s in SKIP_DIRS):
        continue
      if path.suffix.lower() not in EXTS and path.name not in {".clangd"}:
        continue
      # skip stdlib package files (paw/paw/**)
      try:
        path.relative_to(Path("paw") / "paw")
        continue
      except ValueError:
        pass
      try:
        text = path.read_text(encoding="utf-8")
      except OSError:
        continue
      orig = text
      for a, b in HOLDERS:
        text = text.replace(a, b)
      for a, b in REPLACEMENTS:
        text = text.replace(a, b)
      for a, b in HOLDERS:
        text = text.replace(b, a)
      # restore over-eager "test"→"tests" for common false positives
      undos = [
        ('expect_fail=True) for rel in rels]', None),  # noop marker
      ]
      # False positives from bare "test"/"tests" quote replace:
      # - unittest names, TestCase, etc. already protected if not exact 'test'
      # - {"source_note": "tests"} from "test" — acceptable
      # - _SCAN_ROOTS and defaults should be tests
      # Fix: parts check in compile — handled if "test" in parts became need "tests"
      if text != orig:
        path.write_text(text, encoding="utf-8", newline="\n")
        n += 1
        print(path)
  print(f"updated {n}")


if __name__ == "__main__":
  main()
