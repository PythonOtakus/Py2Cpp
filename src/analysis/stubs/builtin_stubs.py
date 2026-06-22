"""从 ``py2cpp/__init__.py`` 桩函数 AST 推导内建派发元数据。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache

from ..ir import decorator_string_arg, has_named_decorator
from .paths import stdlib_builtins_path, stdlib_init_path

# 仍为 dunder 桩，但译器有专用 emit（优化 / 非 dunder 形态）
_DUNDER_STUB_SPECIAL_EMIT: frozenset[str] = frozenset({
  "len",
  "repr",
})


@dataclass(frozen=True)
class BuiltinDunderForward:
  """``def len(obj): return obj.__len__()`` 等。"""

  name: str
  dunder: str
  receiver_index: int
  extra_arg_indices: tuple[int, ...]


@dataclass(frozen=True)
class BuiltinGlobalCall:
  """``@global_call`` / ``@global_call(\"fn\")``：生成 ``::fn(...)``。"""

  name: str
  cpp_name: str
  arg_counts: tuple[int, ...]


def _strip_docstring_prefix(body: list[ast.stmt]) -> list[ast.stmt]:
  i = 0
  while i < len(body):
    stmt = body[i]
    if (
      isinstance(stmt, ast.Expr)
      and isinstance(stmt.value, ast.Constant)
      and isinstance(stmt.value.value, str)
    ):
      i = i + 1
      continue
    break
  return body[i:]


def _positional_arg_counts(func: ast.FunctionDef) -> tuple[int, ...]:
  n_pos = len(func.args.args)
  n_def = len(func.args.defaults)
  required = n_pos - n_def
  if required < 0:
    return ()
  if required == n_pos:
    return (n_pos,)
  return tuple(range(required, n_pos + 1))


def function_global_cpp_name(func: ast.FunctionDef) -> str | None:
  """模块/包根函数 ``@global_call`` → C++ 名（无 ``::`` 前缀）。"""
  return _global_cpp_from_decorator(func)


def function_cpp_rename(func: ast.FunctionDef) -> str | None:
  """模块函数 ``@native_name`` / ``@global_call`` → C++ 标识符（``native_name`` 保留 ``::`` 限定）。"""
  if has_named_decorator(func, "native_name"):
    cpp = decorator_string_arg(func, "native_name")
    if cpp:
      return cpp
  return function_global_cpp_name(func)


def _global_cpp_from_decorator(func: ast.FunctionDef) -> str | None:
  if not has_named_decorator(func, "global_call"):
    return None
  cpp = decorator_string_arg(func, "global_call")
  if cpp is None:
    cpp = func.name
  elif not cpp:
    cpp = func.name
  if cpp.startswith("::"):
    cpp = cpp[2:]
  return cpp


def _parse_dunder_forward(func: ast.FunctionDef) -> BuiltinDunderForward | None:
  body = _strip_docstring_prefix(func.body)
  if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
    return None
  expr = body[0].value
  if not isinstance(expr, ast.Call):
    return None
  if not isinstance(expr.func, ast.Attribute):
    return None
  dunder = expr.func.attr
  if not (dunder.startswith("__") and dunder.endswith("__")):
    return None
  if not isinstance(expr.func.value, ast.Name):
    return None
  recv_name = expr.func.value.id
  param_names = [a.arg for a in func.args.args]
  if recv_name not in param_names:
    return None
  receiver_index = param_names.index(recv_name)
  extra_indices: list[int] = []
  for arg in expr.args:
    if not isinstance(arg, ast.Name):
      return None
    if arg.id not in param_names:
      return None
    idx = param_names.index(arg.id)
    if idx == receiver_index:
      return None
    extra_indices.append(idx)
  if expr.keywords:
    return None
  return BuiltinDunderForward(
    func.name,
    dunder,
    receiver_index,
    tuple(extra_indices),
  )


def _iter_package_root_functions() -> list[ast.FunctionDef]:
  path = stdlib_builtins_path()
  tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


@lru_cache(maxsize=1)
def _load_dunder_forwards() -> dict[str, BuiltinDunderForward]:
  out: dict[str, BuiltinDunderForward] = {}
  for func in _iter_package_root_functions():
    fwd = _parse_dunder_forward(func)
    if fwd is not None:
      out[fwd.name] = fwd
  return out


@lru_cache(maxsize=1)
def _load_global_calls() -> dict[str, BuiltinGlobalCall]:
  out: dict[str, BuiltinGlobalCall] = {}
  for func in _iter_package_root_functions():
    cpp = _global_cpp_from_decorator(func)
    if cpp is None:
      continue
    counts = _positional_arg_counts(func)
    if not counts:
      continue
    out[func.name] = BuiltinGlobalCall(func.name, cpp, counts)
  return out


def builtin_dunder_forward(name: str) -> BuiltinDunderForward | None:
  return _load_dunder_forwards().get(name)


def builtin_global_call(name: str) -> BuiltinGlobalCall | None:
  return _load_global_calls().get(name)


def _skip_runtime_func_stub(func: ast.FunctionDef) -> bool:
  """``@global_call`` 与双下划线名不生成包根 runtime ``.inl``。"""
  if _global_cpp_from_decorator(func) is not None:
    return True
  if func.name.startswith("__") and func.name.endswith("__"):
    return True
  return False


@lru_cache(maxsize=1)
def load_builtins_cpp_runtime_funcs() -> frozenset[str]:
  translation_only = load_translation_only_funcs()

  names: set[str] = set()
  for func in _iter_package_root_functions():
    if func.name in translation_only:
      continue
    if _global_cpp_from_decorator(func) is not None:
      names.add(func.name)
      continue
    fwd = _parse_dunder_forward(func)
    if fwd is None:
      continue
    if _skip_runtime_func_stub(func):
      continue
    names.add(fwd.name)
  return frozenset(names)


# 包根 ``from py2cpp import …`` 须全限定 ``py2cpp::…``（C++ 关键字 / 与 ``using`` 冲突）
_PACKAGE_ROOT_QUALIFIED_DECORATORS = frozenset({"override", "overload"})
@lru_cache(maxsize=1)
def _package_root_global_call_cpp_aliases() -> frozenset[str]:
  """包根 ``@global_call("…")`` 且 C++ 名与 Python 名不同时，须全限定引入。"""
  from ...constant.stdlib_layout import RUNTIME_BUILTINS_MODULE
  from .class_stubs import _scan_function_cpp_renames

  aliases: set[str] = set()
  for (mp, name), cpp in _scan_function_cpp_renames(stdlib_builtins_path()).items():
    if mp == RUNTIME_BUILTINS_MODULE and cpp != name:
      aliases.add(cpp)
  return frozenset(aliases)


@lru_cache(maxsize=1)
def load_runtime_pkg_qualified_symbols() -> frozenset[str]:
  """``RUNTIME_PKG_QUALIFIED_SYMBOLS``：包根内建 / 装饰器 C++ 名，勿 ``using`` 短名引入。"""
  translation_only = load_translation_only_funcs()

  symbols: set[str] = set(_PACKAGE_ROOT_QUALIFIED_DECORATORS)
  symbols.update(_package_root_global_call_cpp_aliases())
  symbols.add("new")

  runtime_funcs = load_builtins_cpp_runtime_funcs()
  forwards = _load_dunder_forwards()
  for name in runtime_funcs:
    if name in translation_only:
      continue
    if name not in forwards:
      continue
    if name in _DUNDER_STUB_SPECIAL_EMIT:
      continue
    symbols.add(name)
  return frozenset(symbols)


def _returns_identity_param(func: ast.FunctionDef, *names: str) -> bool:
  body = _strip_docstring_prefix(func.body)
  if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
    return False
  val = body[0].value
  return isinstance(val, ast.Name) and val.id in names


MEMORY_API_FUNCS = frozenset({
  "alloc",
  "free",
  "allocArray",
  "allocRawArray",
  "freeArray",
  "init",
  "destroy",
  "id",
})

# C++ 从实参推导模板形参；禁止 ``fn[T](…)``（``strict_style`` / ``call_emit`` 共用）
DEDUCED_TEMPLATE_MEMORY_FUNCS = frozenset({
  "id",
  "init",
  "destroy",
  "free",
  "freeArray",
})


def _is_translation_only_package_func(func: ast.FunctionDef) -> bool:
  if func.name in MEMORY_API_FUNCS or func.name == "cast":
    return True
  if func.name in {
    "native", "native_name", "global_call", "immutable", "virtual", "override",
    "overload", "delegate", "context", "decorator",
  }:
    return True
  if _returns_identity_param(func, "cls", "func", "method", "c"):
    return True
  if func.name in {"enum", "dataclass"}:
    return True
  return False


@lru_cache(maxsize=1)
def load_translation_only_funcs() -> frozenset[str]:
  """``py2cpp/__init__.py`` 翻译期桩（装饰器 / 内存 API / ``id`` 等），不生成模块函数 TU。"""
  names: set[str] = set()
  for func in _iter_package_root_functions():
    if _is_translation_only_package_func(func):
      names.add(func.name)
  return frozenset(names)


@lru_cache(maxsize=1)
def load_builtin_emit_special() -> frozenset[str]:
  """不走通用 dunder 转发的包根内建（专用 emit / ``@global_call``）。"""
  translation_only = load_translation_only_funcs()

  forwards = _load_dunder_forwards()
  global_calls = _load_global_calls()
  special: set[str] = set()
  for func in _iter_package_root_functions():
    name = func.name
    if name in translation_only:
      continue
    if name in global_calls:
      special.add(name)
      continue
    if name not in forwards:
      special.add(name)
      continue
    if name in _DUNDER_STUB_SPECIAL_EMIT:
      special.add(name)
  return frozenset(special)
