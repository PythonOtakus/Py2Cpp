"""``@GpuDeviceMeta`` / ``GpuKernelMixin.run``：Device 子集与 Host 调用禁令。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..constant.gpu import GPU_KERNEL_MIXIN
from ..translation_error import raise_translation_error
from .gpu_common import (
  gpu_device_meta_functions,
  host_inherits_gpu_kernel,
)

if TYPE_CHECKING:
  from ..translator import Translator

_HOST_FORBIDDEN_GPU_CALLS = frozenset({"run"})


def _enclosing_function(stack: list[ast.AST]) -> ast.FunctionDef | None:
  for node in reversed(stack):
    if isinstance(node, ast.FunctionDef):
      return node
  return None


def _enclosing_class(stack: list[ast.AST]) -> ast.ClassDef | None:
  for node in reversed(stack):
    if isinstance(node, ast.ClassDef):
      return node
  return None


def _in_device_context(
  stack: list[ast.AST],
  device_meta_names: set[str],
  tr: Translator,
) -> bool:
  """``run``（GpuKernelMixin 子类）或模块级 ``@GpuDeviceMeta`` 体内。"""
  enclosing = _enclosing_function(stack)
  if enclosing is None:
    return False
  if enclosing.name in device_meta_names and _enclosing_class(stack) is None:
    return True
  if enclosing.name != "run":
    return False
  cls = _enclosing_class(stack)
  if cls is None:
    return False
  info = tr.classes.get(cls.name)
  if info is None:
    for ci in tr.classes.values():
      if ci.name == cls.name:
        info = ci
        break
  return host_inherits_gpu_kernel(info, tr.classes)


def _collect_host_gpu_violations(tr: Translator) -> list[tuple[ast.AST, str]]:
  violations: list[tuple[ast.AST, str]] = []
  device_meta_names: set[str] = set()
  for _mp, func in gpu_device_meta_functions(tr):
    device_meta_names.add(func.name)

  for _mp, tree in tr.module_asts.items():
    if tree is None:
      continue
    stack: list[ast.AST] = []

    class Walker(ast.NodeVisitor):
      def generic_visit(self, node: ast.AST) -> None:
        stack.append(node)
        super().generic_visit(node)
        stack.pop()

      def visit_Call(self, node: ast.Call) -> None:
        in_device = _in_device_context(stack, device_meta_names, tr)
        func = node.func
        if (
          not in_device
          and isinstance(func, ast.Attribute)
          and func.attr in _HOST_FORBIDDEN_GPU_CALLS
        ):
          recv_name = None
          if isinstance(func.value, ast.Name):
            recv_name = func.value.id
          if recv_name is not None:
            info = tr.classes.get(recv_name)
            if info is None:
              for ci in tr.classes.values():
                if ci.name == recv_name and host_inherits_gpu_kernel(ci, tr.classes):
                  violations.append((node, f"Host 不可调用 GPU kernel 的 `{func.attr}`"))
                  break
            elif host_inherits_gpu_kernel(info, tr.classes):
              violations.append((node, f"Host 不可直接调用 GPU kernel 的 `{func.attr}`"))
        if (
          not in_device
          and isinstance(func, ast.Name)
          and func.id in device_meta_names
        ):
          violations.append((node, f"Host 不可调用 `@GpuDeviceMeta` 函数 `{func.id}`"))
        if _is_gpu_map_attribute(func) and not getattr(tr, "gpu_enabled", False):
          violations.append((node, "`.map` 需要翻译时启用 `--gpu`"))
        self.generic_visit(node)

    Walker().visit(tree)
  return violations


def _is_gpu_map_attribute(node: ast.expr) -> bool:
  return isinstance(node, ast.Attribute) and node.attr == "map"


def _check_gpu_run_body(run: ast.FunctionDef) -> list[str]:
  errs: list[str] = []
  for node in ast.walk(run):
    if isinstance(node, ast.For):
      errs.append("GPU `run` P1 禁止显式 `for`（由 `.map` 外包 grid）")
    if isinstance(node, ast.Raise):
      errs.append("GPU `run` 禁止 `raise`")
    if isinstance(node, (ast.Try, ast.With, ast.AsyncFunctionDef, ast.Yield, ast.YieldFrom)):
      errs.append(f"GPU `run` 禁止 {type(node).__name__}")
  return errs


def check_gpu_run(tr: Translator) -> None:
  if not getattr(tr, "gpu_enabled", False):
    for v in _collect_host_gpu_violations(tr):
      raise_translation_error(tr, v[0], v[1])
    return

  for info in tr.classes.values():
    if not host_inherits_gpu_kernel(info, tr.classes):
      continue
    run = info.methods.get("run")
    if run is None:
      raise_translation_error(
        tr,
        info.node,
        f"类 `{info.name}` 混入 `{GPU_KERNEL_MIXIN}` 须实现 `def run(...) -> T`",
      )
    for err in _check_gpu_run_body(run):
      raise_translation_error(tr, run, f"`{info.name}.run`：{err}")

  for v in _collect_host_gpu_violations(tr):
    if "需要翻译时启用" not in v[1]:
      raise_translation_error(tr, v[0], v[1])

  for _mp, func in gpu_device_meta_functions(tr):
    for err in _check_gpu_run_body(func):
      raise_translation_error(tr, func, f"`@GpuDeviceMeta` `{func.name}`：{err}")
