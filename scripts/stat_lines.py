#!/usr/bin/env python3
"""按目录统计 Py2Cpp 仓库代码行数（源树 + generated/ 生成物）。"""
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
})

SOURCE_SKIP_DIR_NAMES = GLOBAL_SKIP_DIR_NAMES | frozenset({"generated"})

GENERATED_SKIP_DIR_NAMES = GLOBAL_SKIP_DIR_NAMES | frozenset({".build_logs"})

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


SOURCE_SECTIONS: tuple[Section, ...] = (
  Section("译器", "src", ("**/*.py",), skip_subdirs=frozenset({"tests"})),
  Section("译器单测", "src/tests", ("**/*.py",)),
  Section("标准库", "py2cpp", ("**/*.py",)),
  Section("集成测试", "test", ("**/*.py",)),
  Section("示例", "examples", ("**/*.py",)),
  Section(
    "模板",
    "templates",
    ("**/*.h", "**/*.inl"),
    skip_subdirs=frozenset({"~macro"}),
  ),
  Section("文档", "docs", ("**/*.md",)),
  Section("插件", "plugins", ("**/*.py", "**/*.js", "**/*.ts")),
  Section("仓库脚本", "scripts", ("**/*.py", "**/*.bat")),
)

GENERATED_SECTIONS: tuple[Section, ...] = (
  Section(
    "生成 runtime",
    "generated/runtime",
    ("**/*.h", "**/*.inl", "**/*.cpp"),
    skip_dirs=GENERATED_SKIP_DIR_NAMES,
  ),
  Section(
    "生成 test",
    "generated/test",
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
    rows.append((section.label, result.files, result.lines))
    total.add(result)
    if py_total is not None:
      py_total.add(count_section(repo_root, section, suffixes=frozenset({".py"})))
    if cpp_total is not None:
      cpp_total.add(count_section(repo_root, section, suffixes=CPP_SUFFIXES))


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Py2Cpp 分模块代码行数统计")
  parser.add_argument(
    "--root",
    type=Path,
    default=Path(__file__).resolve().parents[1],
    help="仓库根目录",
  )
  args = parser.parse_args(argv)
  repo_root = args.root.resolve()

  print("Py2Cpp 代码行数统计")
  print(f"仓库: {repo_root}")
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

  print("【源树】")
  source_rows = rows.copy()
  _print_table(
    source_rows,
    footers=[("源树小计", source_total.files, source_total.lines)],
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
  print("【生成物 generated/】")
  if gen_rows:
    _print_table(
      gen_rows,
      footers=[("生成物小计", generated_total.files, generated_total.lines)],
    )
  else:
    print("(未找到 generated/ 或目录为空；先运行 bootstrap / build 生成)")
  print()

  grand = CountResult()
  grand.add(source_total)
  grand.add(generated_total)
  summary_rows: list[tuple[str, int, int]] = [
    ("总计", grand.files, grand.lines),
    ("其中 Python", py_total.files, py_total.lines),
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
    "说明: generated/ 含 runtime 与 test 译出 .h/.inl/.cpp（不含 .build_logs）；"
    "templates/ 不含生成的 ~macro/（clangd 桩）。",
  )
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
