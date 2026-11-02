#!/usr/bin/env python3
"""按目录统计 Paw / Zeus 代码行数（源树 + out/ 生成物）。"""
from __future__ import annotations

import argparse
import unicodedata
from dataclasses import dataclass
from pathlib import Path

GLOBAL_SKIP_DIR_NAMES = frozenset({
  ".git",
  ".cache",
  ".cursor",
  "__pycache__",
  "node_modules",
  "out",
  "saved",
})

SOURCE_SKIP_DIR_NAMES = GLOBAL_SKIP_DIR_NAMES | frozenset({"out"})

# 在 out/ 内统计时勿把目录名 ``out`` 本身列入 skip（否则整树被跳过）
GENERATED_SKIP_DIR_NAMES = frozenset({
  ".git",
  ".cache",
  ".cursor",
  "__pycache__",
  "node_modules",
  "saved",
  ".build_logs",
  "mid_emit",
})

SKIP_FILE_SUFFIXES = frozenset({
  ".vsix",
  ".pyc",
  ".pyo",
})

CPP_SUFFIXES = frozenset({".h", ".inl", ".cpp"})


@dataclass(frozen=True)
class Section:
  label: str
  rel_dir: str
  patterns: tuple[str, ...]
  skip_subdirs: frozenset[str] = frozenset()
  skip_dirs: frozenset[str] = SOURCE_SKIP_DIR_NAMES


# Paw 产品根（``paw/``）相对路径
SOURCE_SECTIONS: tuple[Section, ...] = (
  Section("CLI", "cmd", ("**/*.py",)),
  Section("译器", "host", ("**/*.py",), skip_subdirs=frozenset({"tests"})),
  Section("译器单测", "host/tests", ("**/*.py",)),
  Section("标准库", "lib/paw", ("**/*.py", "**/*.paw")),
  Section(
    "自举 compiler",
    "compiler",
    ("**/*.py", "**/*.paw"),
    skip_subdirs=frozenset({"stages"}),
  ),
  Section("集成测试", "tests", ("**/*.py", "**/*.paw")),
  Section("示例", "examples", ("**/*.py", "**/*.paw")),
  Section("FFI", "ffi", ("**/*.paw", "**/*.pyi")),
  Section(
    "模板",
    "templates",
    ("**/*.h", "**/*.inl"),
    skip_subdirs=frozenset({"~macro"}),
  ),
  Section("文档", "docs", ("**/*.md",)),
  Section("插件", "extensions", ("**/*.py", "**/*.js", "**/*.ts")),
  Section("仓库脚本", "tools", ("**/*.py", "**/*.bat")),
)

GENERATED_SECTIONS: tuple[Section, ...] = (
  Section(
    "生成 runtime",
    "out/runtime",
    ("**/*.h", "**/*.inl", "**/*.cpp"),
    skip_dirs=GENERATED_SKIP_DIR_NAMES,
  ),
  Section(
    "生成 tests",
    "out/tests",
    ("**/*.h", "**/*.inl", "**/*.cpp"),
    skip_dirs=GENERATED_SKIP_DIR_NAMES,
  ),
  Section(
    "生成 examples",
    "out/examples",
    ("**/*.h", "**/*.inl", "**/*.cpp"),
    skip_dirs=GENERATED_SKIP_DIR_NAMES,
  ),
)

# Zeus 引擎根（``zeus/``）相对路径；仅当与 paw 并列存在时统计
ZEUS_SOURCE_SECTIONS: tuple[Section, ...] = (
  Section("Zeus runtime", "engine/source/zeus/runtime", ("**/*.py",)),
  Section("Zeus editor", "engine/source/zeus/editor", ("**/*.py",)),
  Section("Zeus developer", "engine/source/zeus/developer", ("**/*.py",)),
  Section("Zeus programs", "engine/source/zeus/programs", ("**/*.py",)),
  Section("Zeus samples", "samples", ("**/*.py",)),
  Section("Zeus FFI", "engine/ffi", ("**/*.paw", "**/*.pyi")),
  Section("Zeus 文档", "docs", ("**/*.md",)),
  Section("Zeus tools", "tools", ("**/*.py", "**/*.bat")),
)

ZEUS_GENERATED_SECTIONS: tuple[Section, ...] = (
  Section(
    "Zeus 生成 out",
    "out",
    ("**/*.h", "**/*.inl", "**/*.cpp"),
    skip_dirs=GENERATED_SKIP_DIR_NAMES,
  ),
)


@dataclass
class CountResult:
  files: int = 0
  lines: int = 0

  def add(self, other: CountResult) -> None:
    self.files += other.files
    self.lines += other.lines

  def add_file(self, path: Path) -> None:
    try:
      text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
      text = path.read_text(encoding="utf-8", errors="replace")
    self.files += 1
    self.lines += len(text.splitlines())


def _path_has_skipped_parent(path: Path, base: Path, skip_subdirs: frozenset[str]) -> bool:
  try:
    rel = path.relative_to(base)
  except ValueError:
    return True
  if rel.parts and rel.parts[0] in skip_subdirs:
    return True
  return False


def _iter_files(
  base: Path,
  patterns: tuple[str, ...],
  *,
  skip_dirs: frozenset[str],
) -> list[Path]:
  if not base.is_dir():
    return []
  found: dict[Path, Path] = {}
  for pattern in patterns:
    for path in base.glob(pattern):
      if not path.is_file():
        continue
      if path.suffix.lower() in SKIP_FILE_SUFFIXES:
        continue
      if any(part in skip_dirs for part in path.parts):
        continue
      found[path.resolve()] = path
  return sorted(found.values(), key=lambda p: p.as_posix())


def count_section(
  repo_root: Path,
  section: Section,
  *,
  suffixes: frozenset[str] | None = None,
) -> CountResult:
  base = repo_root / Path(section.rel_dir)
  if not base.is_dir():
    return CountResult()
  result = CountResult()
  for path in _iter_files(base, section.patterns, skip_dirs=section.skip_dirs):
    if suffixes is not None and path.suffix.lower() not in suffixes:
      continue
    if _path_has_skipped_parent(path, base, section.skip_subdirs):
      continue
    result.add_file(path)
  return result


def count_root_files(repo_root: Path, names: tuple[str, ...]) -> CountResult:
  result = CountResult()
  for name in names:
    path = repo_root / name
    if path.is_file():
      result.add_file(path)
  return result


NUM_COL_GAP = "  "


def _display_width(text: str) -> int:
  width = 0
  for ch in text:
    if unicodedata.east_asian_width(ch) in ("F", "W"):
      width += 2
    else:
      width += 1
  return width


def _pad_display(text: str, width: int) -> str:
  return text + " " * max(0, width - _display_width(text))


def _pad_display_right(text: str, width: int) -> str:
  return " " * max(0, width - _display_width(text)) + text


def _column_widths(*rows: tuple[str, int, int]) -> tuple[int, int, int]:
  if not rows:
    return _display_width("部分"), _display_width("文件"), _display_width("行数")
  label_w = max(_display_width("部分"), *(_display_width(label) for label, _, _ in rows))
  file_w = max(_display_width("文件"), *(len(str(files)) for _, files, _ in rows))
  line_w = max(_display_width("行数"), *(len(f"{lines:,}") for _, _, lines in rows))
  return label_w, file_w, line_w


def _stat_header(*, label_w: int, file_w: int, line_w: int) -> str:
  return (
    f"{_pad_display('部分', label_w)}{NUM_COL_GAP}"
    f"{_pad_display_right('文件', file_w)}{NUM_COL_GAP}"
    f"{_pad_display_right('行数', line_w)}"
  )


def _stat_row(
  label: str,
  files: int,
  lines: int,
  *,
  label_w: int,
  file_w: int,
  line_w: int,
) -> str:
  return (
    f"{_pad_display(label, label_w)}{NUM_COL_GAP}"
    f"{files:>{file_w}}{NUM_COL_GAP}"
    f"{lines:>{line_w},}"
  )


def _print_table(
  rows: list[tuple[str, int, int]],
  *,
  footers: list[tuple[str, int, int]] | None = None,
) -> None:
  if not rows and not footers:
    print("(无匹配文件)")
    return
  all_rows = [*rows, *(footers or [])]
  label_w, file_w, line_w = _column_widths(*all_rows)
  print(_stat_header(label_w=label_w, file_w=file_w, line_w=line_w))
  for label, files, lines in rows:
    print(_stat_row(label, files, lines, label_w=label_w, file_w=file_w, line_w=line_w))
  for label, files, lines in footers or []:
    print(_stat_row(label, files, lines, label_w=label_w, file_w=file_w, line_w=line_w))


def _append_sections(
  repo_root: Path,
  sections: tuple[Section, ...],
  rows: list[tuple[str, int, int]],
  total: CountResult,
  *,
  py_total: CountResult | None = None,
  cpp_total: CountResult | None = None,
) -> None:
  for section in sections:
    result = count_section(repo_root, section)
    if result.files == 0 and result.lines == 0:
      continue
    rows.append((section.label, result.files, result.lines))
    total.add(result)
    if py_total is not None:
      py_total.add(
        count_section(repo_root, section, suffixes=frozenset({".py", ".paw"})),
      )
    if cpp_total is not None:
      cpp_total.add(count_section(repo_root, section, suffixes=CPP_SUFFIXES))


def _zeus_root(paw_root: Path) -> Path | None:
  z = paw_root.parent / "zeus"
  return z if z.is_dir() else None


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Paw / Zeus 分模块代码行数统计")
  parser.add_argument(
    "--root",
    type=Path,
    default=Path(__file__).resolve().parents[1],
    help="Paw 工程根（默认 tools/ 的上一级）",
  )
  args = parser.parse_args(argv)
  repo_root = args.root.resolve()
  zeus_root = _zeus_root(repo_root)

  print("Paw / Zeus 代码行数统计")
  print(f"Paw:  {repo_root}")
  if zeus_root is not None:
    print(f"Zeus: {zeus_root}")
  print()

  rows: list[tuple[str, int, int]] = []
  source_total = CountResult()
  generated_total = CountResult()
  py_total = CountResult()
  cpp_generated = CountResult()

  cli = count_root_files(repo_root, ("main.py",))
  if cli.files:
    rows.append(("CLI (main.py)", cli.files, cli.lines))
    source_total.add(cli)
    py_total.add(cli)

  _append_sections(
    repo_root,
    SOURCE_SECTIONS,
    rows,
    source_total,
    py_total=py_total,
  )

  print("【Paw 源树】")
  _print_table(
    rows,
    footers=[("Paw 源树小计", source_total.files, source_total.lines)],
  )
  print()

  gen_rows: list[tuple[str, int, int]] = []
  _append_sections(
    repo_root,
    GENERATED_SECTIONS,
    gen_rows,
    generated_total,
    cpp_total=cpp_generated,
  )
  print("【Paw 生成物 out/】")
  if gen_rows:
    _print_table(
      gen_rows,
      footers=[("Paw 生成物小计", generated_total.files, generated_total.lines)],
    )
  else:
    print("(未找到 out/ 或目录为空；先运行 bootstrap / build 生成)")
  print()

  if zeus_root is not None:
    zeus_rows: list[tuple[str, int, int]] = []
    zeus_src = CountResult()
    _append_sections(
      zeus_root,
      ZEUS_SOURCE_SECTIONS,
      zeus_rows,
      zeus_src,
      py_total=py_total,
    )
    print("【Zeus 源树】")
    _print_table(
      zeus_rows,
      footers=[("Zeus 源树小计", zeus_src.files, zeus_src.lines)],
    )
    print()
    source_total.add(zeus_src)

    zeus_gen_rows: list[tuple[str, int, int]] = []
    zeus_gen = CountResult()
    _append_sections(
      zeus_root,
      ZEUS_GENERATED_SECTIONS,
      zeus_gen_rows,
      zeus_gen,
      cpp_total=cpp_generated,
    )
    print("【Zeus 生成物 out/】")
    if zeus_gen_rows:
      _print_table(
        zeus_gen_rows,
        footers=[("Zeus 生成物小计", zeus_gen.files, zeus_gen.lines)],
      )
    else:
      print("(未找到 zeus/out 或目录为空)")
    print()
    generated_total.add(zeus_gen)

  grand = CountResult()
  grand.add(source_total)
  grand.add(generated_total)
  summary_rows: list[tuple[str, int, int]] = [
    ("总计", grand.files, grand.lines),
    ("其中 Python/.paw", py_total.files, py_total.lines),
  ]
  if generated_total.files:
    summary_rows.append(
      ("其中 C++ 生成物", cpp_generated.files, cpp_generated.lines),
    )
  label_w, file_w, line_w = _column_widths(*summary_rows)
  print(_stat_header(label_w=label_w, file_w=file_w, line_w=line_w))
  for label, files, lines in summary_rows:
    print(_stat_row(label, files, lines, label_w=label_w, file_w=file_w, line_w=line_w))
  print()
  print(
    "说明: Paw 按 cmd/host/lib/paw/compiler/tests/… 统计（compiler 不含 stages/）；"
    "Zeus 按 engine/source + samples + tools；"
    "out/ 不含 mid_emit / .build_logs；templates/ 不含 ~macro/。",
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
