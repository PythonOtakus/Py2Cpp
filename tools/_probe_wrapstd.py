#!/usr/bin/env python3
from pathlib import Path
import ast
from src.analysis.stubs.class_stubs import lookup_module_function_cpp_name, _scan_function_cpp_renames
from src.constant.stdlib_layout import stdlib_module_path

mp = stdlib_module_path("io")
renames = _scan_function_cpp_renames(Path("py2cpp/io/__init__.py"))
for k, v in sorted(renames.items()):
  if "wrap" in k[1].lower() or k[1] == "open":
    print(k, "->", v)
print("lookup wrapStd", lookup_module_function_cpp_name(mp, "wrapStd"))
tree = ast.parse(Path("py2cpp/console/__init__.py").read_text(encoding="utf-8"))
for n in tree.body:
  if isinstance(n, ast.ImportFrom):
    print("import", n.module, [a.name for a in n.names])
