"""GPU kernel / Device 辅助：类与函数判定。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, has_named_decorator
from ..constant.gpu import GPU_DEVICE_META, GPU_KERNEL_MIXIN, GPU_MAP_METHOD

if TYPE_CHECKING:
  from ..translator import Translator


def host_inherits_gpu_kernel(info: ClassInfo | None, classes: dict[str, ClassInfo]) -> bool:
  """宿主类是否混入 ``GpuKernelMixin``（含经其它 ``@mixin`` 传递）。"""
  if info is None:
    return False
  seen: set[str] = set()

  def walk(bases: tuple[str, ...]) -> bool:
    for base in bases:
      if base in seen:
        continue
      seen.add(base)
      if base == GPU_KERNEL_MIXIN:
        return True
      bi = classes.get(base)
      if bi is not None and bi.is_mixin and walk(tuple(bi.bases)):
        return True
    return False

  if GPU_KERNEL_MIXIN in info.bases:
    return True
  return walk(tuple(info.bases))


def is_gpu_device_meta_function(func: ast.FunctionDef) -> bool:
  return has_named_decorator(func, GPU_DEVICE_META)


def is_gpu_kernel_run_method(info: ClassInfo, method: ast.FunctionDef, classes: dict[str, ClassInfo]) -> bool:
  return method.name == "run" and host_inherits_gpu_kernel(info, classes)


def is_gpu_kernel_map_method(info: ClassInfo, method: ast.FunctionDef, classes: dict[str, ClassInfo]) -> bool:
  return method.name == GPU_MAP_METHOD and host_inherits_gpu_kernel(info, classes)


def gpu_device_meta_functions(tr: Translator) -> list[tuple[str, ast.FunctionDef]]:
  out: list[tuple[str, ast.FunctionDef]] = []
  for module_path, tree in tr.module_asts.items():
    if tree is None:
      continue
    for node in tree.body:
      if isinstance(node, ast.FunctionDef) and is_gpu_device_meta_function(node):
        out.append((module_path, node))
  return out


def find_gpu_kernel_run(info: ClassInfo) -> ast.FunctionDef | None:
  run = info.methods.get("run")
  if run is not None:
    return run
  for overloads in info.method_overloads.values():
    for method in overloads:
      if method.name == "run":
        return method
  return None
