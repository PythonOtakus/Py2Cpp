"""Runtime bootstrap 增量：输入未变则跳过 ``main.py py2cpp/__init__.py``。

扫描 ``py2cpp/``、``templates/``（不含 clangd 生成的 ``~macro/``）、``ffi/``、译器
``src``（``translator.py`` 与 ``analysis`` / ``passes`` / ``codegen`` / ``emit`` /
``constant``，不含 stamp 自身与 ``compile.py``）、``main.py``。
``PY2CPP_FORCE_BOOTSTRAP=1`` 强制全量翻译。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STAMP_REL = Path("generated") / "runtime" / ".bootstrap.stamp"
FORCE_ENV = "PY2CPP_FORCE_BOOTSTRAP"
_INPUT_DIRS = ("py2cpp", "templates", "ffi")
_INPUT_FILES = ("main.py",)
_SRC_CODEGEN_DIRS = ("analysis", "passes", "codegen", "emit", "constant")
_SRC_CODEGEN_FILES = ("translator.py",)


def repo_root() -> Path:
  return Path(__file__).resolve().parents[2]


def stamp_path(root: Path | None = None) -> Path:
  return (root or repo_root()) / STAMP_REL


def _header_only_flag() -> bool:
  from ..constant.runtime_libs import header_only_mode

  return header_only_mode()


def iter_bootstrap_input_files(root: Path):
  """bootstrap 输入文件（mtime 新于 stamp 则须重译）。"""
  for d in _INPUT_DIRS:
    p = root / d
    if not p.is_dir():
      continue
    for f in p.rglob("*"):
      if not f.is_file():
        continue
      if "__pycache__" in f.parts or f.suffix in {".pyc", ".pyo"}:
        continue
      # clangd 桩：每次 build.bat 末尾会刷新，不得打穿翻译 skip
      if "~macro" in f.parts:
        continue
      yield f
  src = root / "src"
  if src.is_dir():
    for name in _SRC_CODEGEN_FILES:
      f = src / name
      if f.is_file():
        yield f
    for d in _SRC_CODEGEN_DIRS:
      p = src / d
      if not p.is_dir():
        continue
      for f in p.rglob("*.py"):
        if "__pycache__" in f.parts:
          continue
        if f.name == "bootstrap_stamp.py":
          continue
        yield f
  for name in _INPUT_FILES:
    f = root / name
    if f.is_file():
      yield f


def newest_input_mtime(root: Path) -> float:
  newest = 0.0
  for f in iter_bootstrap_input_files(root):
    try:
      m = f.stat().st_mtime
    except OSError:
      continue
    if m > newest:
      newest = m
  return newest


def stamp_payload(*, debug: bool, header_only: bool) -> dict:
  return {"debug": bool(debug), "header_only": bool(header_only)}


def should_skip_translate(
  *,
  debug: bool = False,
  header_only: bool | None = None,
  root: Path | None = None,
) -> bool:
  if os.environ.get(FORCE_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
    return False
  root = root or repo_root()
  stamp = stamp_path(root)
  umbrella = root / "generated" / "runtime" / "py2cpp" / "minimal.h"
  if not stamp.is_file() or not umbrella.is_file():
    return False
  ho = _header_only_flag() if header_only is None else header_only
  try:
    data = json.loads(stamp.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return False
  if bool(data.get("debug")) != bool(debug):
    return False
  if bool(data.get("header_only")) != bool(ho):
    return False
  try:
    stamp_m = stamp.stat().st_mtime
  except OSError:
    return False
  return newest_input_mtime(root) <= stamp_m


def write_stamp(
  *,
  debug: bool = False,
  header_only: bool | None = None,
  root: Path | None = None,
) -> Path:
  root = root or repo_root()
  ho = _header_only_flag() if header_only is None else header_only
  path = stamp_path(root)
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(
    json.dumps(stamp_payload(debug=debug, header_only=ho), indent=2) + "\n",
    encoding="utf-8",
  )
  return path


def main(argv: list[str] | None = None) -> int:
  args = list(sys.argv[1:] if argv is None else argv)
  debug = "--debug" in args
  args = [a for a in args if a != "--debug"]
  cmd = args[0] if args else ""
  if cmd == "skip":
    return 0 if should_skip_translate(debug=debug) else 1
  if cmd == "write":
    write_stamp(debug=debug)
    return 0
  print("usage: bootstrap_stamp skip|write [--debug]", file=sys.stderr)
  return 2


if __name__ == "__main__":
  raise SystemExit(main())
