#!/usr/bin/env python3
"""修复命名规范后 src/ 中仍引用旧 snake 路径 / C++ 关键字 / serializable 方法名。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def to_camel(s: str) -> str:
  parts = [p for p in s.split("_") if p]
  return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def fix_text_replace(path: Path, pairs: list[tuple[str, str]]) -> None:
  t = path.read_text(encoding="utf-8")
  orig = t
  for a, b in pairs:
    t = t.replace(a, b)
  if t != orig:
    path.write_text(t, encoding="utf-8", newline="\n")
    print(f"replace {path.relative_to(ROOT)}")


def fix_language_keyword() -> None:
  p = ROOT / "src/constant/language.py"
  t = p.read_text(encoding="utf-8")
  t2 = t.replace('"thread_local"', '"thread_local"')
  if t2 != t:
    p.write_text(t2, encoding="utf-8", newline="\n")
    print("language thread_local keyword")


def fix_serializable() -> None:
  p = ROOT / "src/passes/serializable.py"
  t = p.read_text(encoding="utf-8")
  # .snake_case( → .camelCase(
  t = re.sub(
    r"\.([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\(",
    lambda m: "." + to_camel(m.group(1)) + "(",
    t,
  )
  for old in (
    "load_list_element",
    "skip_field",
    "skip_spaces",
    "serde_push_slot",
    "serde_commit_push",
    "parse_int_at_ascii",
    "parse_int_at",
    "str_assign_from_seg",
    "ascii_ok",
    "src_char",
    "src_len",
  ):
    t = re.sub(rf"\b{re.escape(old)}\b", to_camel(old), t)
  p.write_text(t, encoding="utf-8", newline="\n")
  print("serializable camelCase API strings")


def fix_inline_range() -> None:
  p = ROOT / "src/passes/inline_range.py"
  t = p.read_text(encoding="utf-8")
  t2 = t.replace('INLINE_RANGE = "inline_range"', 'INLINE_RANGE = "inlineRange"')
  if t2 != t:
    p.write_text(t2, encoding="utf-8", newline="\n")
    print("inlineRange constant")


def fix_s02_s03() -> None:
  p = ROOT / "src/passes/strict_style.py"
  t = p.read_text(encoding="utf-8")
  if "startsWith" not in t:
    t = t.replace(
      "'startswith', 'endswith'",
      "'startswith', 'endswith', 'startsWith', 'endsWith'",
    )
  if "getSize" not in t:
    t = t.replace(
      "'getstate', 'setstate'",
      "'getstate', 'setstate', 'getState', 'setState', 'getsize', 'getSize', "
      "'getmtime', 'getMtime', 'getctime', 'getCtime', 'getatime', 'getAtime'",
    )
  t = t.replace(
    "if node.name.startswith('scan_test_'):",
    "if node.name.startswith('scan_test_') or node.name.startswith('scanTest'):",
  )
  p.write_text(t, encoding="utf-8", newline="\n")
  print("strict_style S02/S03")


def fix_default_iter() -> None:
  p = ROOT / "src/passes/default_iter.py"
  t = p.read_text(encoding="utf-8")
  if "_default_seq_iterator_name" in t:
    print("default_iter already patched")
    return
  # inject helper before _make_iterator_class
  needle = "def _make_iterator_class("
  helper = '''def _default_seq_iterator_name(host_name: str) -> str:
  """``list`` → ``ListIterator``；``MySeq`` → ``MySeqIterator``。"""
  if "_" in host_name:
    parts = [p for p in host_name.split("_") if p]
    base = "".join(p[:1].upper() + p[1:] for p in parts)
  elif host_name and host_name[0].islower():
    base = host_name[:1].upper() + host_name[1:]
  else:
    base = host_name
  return f"{base}Iterator"


'''
  if needle not in t:
    print("default_iter: pattern missing")
    return
  t = t.replace(needle, helper + needle)
  t = t.replace(
    'iter_name = f"{host_info.name}_iterator"',
    "iter_name = _default_seq_iterator_name(host_info.name)",
  )
  t = t.replace(
    'if f"{info.name}_iterator" in tr.classes:',
    "if _default_seq_iterator_name(info.name) in tr.classes:",
  )
  p.write_text(t, encoding="utf-8", newline="\n")
  print("default_iter ListIterator naming")


def fix_analyzer_host() -> None:
  p = ROOT / "src/analysis/analyzer.py"
  t = p.read_text(encoding="utf-8")
  old = '''        if info.name.endswith("_iterator") and field == "_host":
          host_py = info.name[: -len("_iterator")]
          host_info = self._classes.get(host_py)
          if host_info is not None:
            self._set_field_cpp_type(
              info, field, f"{host_info.template_cpp_type()}*",
            )
            clear_field_ann_ast(info, field)
            continue'''
  new = '''        if field == "_host":
          host_py = iterator_owner_host_py_name(info.name)
          if host_py is not None:
            host_info = self._classes.get(host_py)
            if host_info is not None:
              self._set_field_cpp_type(
                info, field, f"{host_info.template_cpp_type()}*",
              )
              clear_field_ann_ast(info, field)
              continue'''
  if old in t:
    t = t.replace(old, new)
  old2 = '''    if info.name.endswith("_iterator") and "_host" in info.fields:
      host_py = info.name[: -len("_iterator")]
      host_info = self._classes.get(host_py)
      if host_info is not None:
        self._set_field_cpp_type(info, "_host", f"{host_info.template_cpp_type()}*")'''
  new2 = '''    if "_host" in info.fields:
      host_py = iterator_owner_host_py_name(info.name)
      if host_py is not None:
        host_info = self._classes.get(host_py)
        if host_info is not None:
          self._set_field_cpp_type(info, "_host", f"{host_info.template_cpp_type()}*")'''
  if old2 in t:
    t = t.replace(old2, new2)
  p.write_text(t, encoding="utf-8", newline="\n")
  print("analyzer host host")


def main() -> None:
  fix_language_keyword()
  fix_text_replace(
    ROOT / "src/constant/namespace.py",
    [("util/StackArray", "util/stack_array")],
  )
  fix_text_replace(
    ROOT / "src/constant/stdlib_modules.py",
    [("util/StackArray", "util/stack_array")],
  )
  fix_text_replace(
    ROOT / "src/constant/primitive_headers.py",
    [("py2cpp/utf8ptr.h", "py2cpp/c_str.h")],
  )
  fix_text_replace(ROOT / "src/constant/umbrella.py", [("utf8ptr.h", "c_str.h")])
  fix_text_replace(ROOT / "src/constant/inject_specs.py", [("utf8ptr.h", "c_str.h")])
  fix_text_replace(
    ROOT / "src/codegen/stdlib_mirror_codegen.py",
    [
      ("util/StackArray", "util/stack_array"),
      ("utf8ptr.h", "c_str.h"),
      ("py2cpp/utf8ptr", "py2cpp/c_str"),
    ],
  )
  fix_text_replace(
    ROOT / "src/emit/layout_emit.py",
    [
      ('f"{RUNTIME_PREFIX}/utf8ptr"', 'f"{RUNTIME_PREFIX}/c_str"'),
      ("utf8ptr.h", "c_str.h"),
    ],
  )
  for rel in [
    "src/tests/test_array_emit.py",
    "src/tests/test_header_usings.py",
    "src/tests/test_expand_mirror_codegen.py",
    "src/tests/test_type_deps.py",
    "src/tests/test_stdlib_module_order.py",
    "src/tests/test_class_stubs.py",
  ]:
    fix_text_replace(ROOT / rel, [("util/StackArray", "util/stack_array")])
  fix_inline_range()
  fix_s02_s03()
  fix_default_iter()
  fix_analyzer_host()
  fix_serializable()
  # tests for inlineRange
  for rel in [
    "src/tests/test_inline_range.py",
    "src/tests/test_expand_iter_fields_loops.py",
  ]:
    fix_text_replace(
      ROOT / rel,
      [("in inline_range(", "in inlineRange("), ('"inline_range"', '"inlineRange"')],
    )


if __name__ == "__main__":
  main()
