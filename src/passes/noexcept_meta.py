"""``@noexcept``：静态收集 ``raise`` 类型、校验装饰器形态。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import has_named_decorator
from ..constant.stdlib_layout import EXCEPTIONS_NS

if TYPE_CHECKING:
  from ..translator import Translator

NOEXCEPT_DECORATOR = "noexcept"

# ``py2cpp.core.exceptions`` 单继承链（用于多 ``raise`` 类型求最近公共基类）
_EXCEPTION_BASES: dict[str, str] = {
  "StatisticsError": "ValueError",
  "LinAlgError": "ValueError",
  "FileNotFoundError": "OSError",
  "FileExistsError": "OSError",
  "StopIteration": "Exception",
  "TypeError": "Exception",
  "KeyError": "Exception",
  "IndexError": "Exception",
  "ValueError": "Exception",
  "RuntimeError": "Exception",
  "ReferenceError": "Exception",
  "OSError": "Exception",
  "AssertionError": "Exception",
  "Exception": "Exception",
}


def _exception_ancestors(name: str) -> list[str]:
  chain: list[str] = []
  cur = name
  seen: set[str] = set()
  while cur and cur not in seen:
    seen.add(cur)
    chain.append(cur)
    cur = _EXCEPTION_BASES.get(cur, "Exception")
    if cur == chain[-1]:
      break
  return chain


def resolve_noexcept_err_type(exc_names: frozenset[str]) -> str:
  """``raise`` 集合 → ``E`` 的 C++ 类型（``py2cpp::core::exceptions::…``）。"""
  if not exc_names:
    return f"{EXCEPTIONS_NS}::Exception"
  if len(exc_names) == 1:
    return f"{EXCEPTIONS_NS}::{next(iter(exc_names))}"
  sets = [set(_exception_ancestors(n)) for n in exc_names]
  common = sets[0]
  for s in sets[1:]:
    common &= s
  if not common:
    return f"{EXCEPTIONS_NS}::Exception"
  best = "Exception"
  best_depth = -1
  for name in common:
    chain = _exception_ancestors(name)
    depth = len(chain)
    if depth > best_depth:
      best_depth = depth
      best = name
  return f"{EXCEPTIONS_NS}::{best}"


def collect_raise_exception_names(func: ast.FunctionDef) -> frozenset[str]:
  """函数体内（含 ``try``/``except``）所有 ``raise Exc`` / ``raise Exc()`` 的类名。"""
  names: set[str] = set()
  for node in ast.walk(func):
    if not isinstance(node, ast.Raise) or node.exc is None:
      continue
    match node.exc:
      case ast.Call(func=ast.Name(id=name)):
        names.add(name)
      case ast.Name(id=name):
        names.add(name)
  return frozenset(names)


def check_noexcept_decorator(func: ast.FunctionDef, *, label: str) -> None:
  """``@noexcept`` 无参；与其它互斥装饰器在分析阶段报错。"""
  if not has_named_decorator(func, NOEXCEPT_DECORATOR):
    return
  for dec in func.decorator_list:
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
      if dec.func.id == NOEXCEPT_DECORATOR:
        raise ValueError(f"{label}: @noexcept 不接受参数")
  if has_named_decorator(func, "native"):
    raise ValueError(f"{label}: @noexcept 与 @native 互斥")
  for node in ast.walk(func):
    if isinstance(node, (ast.Yield, ast.YieldFrom)):
      raise ValueError(f"{label}: @noexcept 与 yield 互斥")
    if isinstance(node, ast.AsyncFunctionDef):
      raise ValueError(f"{label}: @noexcept 不支持 async def")
  if func.name in ("__next__", "send", "__resume"):
    raise ValueError(f"{label}: @noexcept 与迭代器协议方法互斥")


def check_noexcept_functions(tr: Translator) -> None:
  for _mp, func in tr.module_functions:
    check_noexcept_decorator(func, label=func.name)
  for info in tr.classes.values():
    for method in info.methods.values():
      check_noexcept_decorator(method, label=f"{info.name}.{method.name}")
