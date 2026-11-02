"""包根 ``py2cpp/__init__.py`` AST 推导符号 + C++ 限定构造 helper。"""
from __future__ import annotations

from .stubs.builtin_stubs import (
  load_builtin_emit_special,
  load_builtins_cpp_runtime_funcs,
  load_runtime_pkg_qualified_symbols,
  load_translation_only_funcs,
)
from .stubs.class_stubs import (
  load_package_root_native_names,
  load_stdlib_exception_types,
)


def _build_runtime_root_cpp_types() -> dict[str, str]:
  return {
    cpp: f"::py2cpp::{cpp}"
    for cpp in load_package_root_native_names().values()
  }


TRANSLATION_ONLY_FUNCS = load_translation_only_funcs()

# 包根 ``py2cpp/__init__.py`` 桩 AST → runtime 内建名（``expand_generators`` 同步）
BUILTINS_CPP_RUNTIME_FUNCS = load_builtins_cpp_runtime_funcs()
BUILTIN_EMIT_SPECIAL = load_builtin_emit_special()
RUNTIME_PKG_QUALIFIED_SYMBOLS = load_runtime_pkg_qualified_symbols()
RUNTIME_ROOT_CPP_TYPES = _build_runtime_root_cpp_types()
CPP_EXCEPTION_TYPES = load_stdlib_exception_types()


def qualify_runtime_root_cpp_type(cpp: str) -> str:
  base = cpp.strip().rstrip("&").strip()
  suffix = cpp[len(base) :]
  qual = RUNTIME_ROOT_CPP_TYPES.get(base)
  if qual:
    return qual + suffix
  for short, q in RUNTIME_ROOT_CPP_TYPES.items():
    if base.startswith(short + "<"):
      return q + base[len(short) :] + suffix
  return cpp


def runtime_root_ctor_expr(cpp: str, args: str) -> str:
  if cpp.startswith("::py2cpp::"):
    return f"({cpp})({args})" if args else f"({cpp})()"
  return f"{cpp}({args})" if args else f"{cpp}()"


def runtime_make_range_expr(args: str) -> str:
  from ..constant.stdlib_layout import cpp_stdlib_class

  qual = f"::{cpp_stdlib_class('util/range', 'PyRange')}"
  if not args:
    return f"{qual}()"
  # 多实参勿 ``(T)(a, b, c)``：MSVC 会按逗号运算符解析为 ``(T)(c)``。
  if "," in args:
    return f"{qual}({args})"
  return f"({qual})({args})"
