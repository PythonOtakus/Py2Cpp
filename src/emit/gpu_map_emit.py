"""``.map(...)` → OpenMP 点wise 或 CUDA launch（由 ``gpu_backend`` 选择）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.patterns import temp_name
from ..constant.gpu import GPU_BACKEND_CUDA, GPU_MAP_METHOD
from ..passes.gpu_common import find_gpu_kernel_run, gpu_device_meta_functions, host_inherits_gpu_kernel
from ..translation_error import raise_translation_error
from .call_emit import class_info_from_receiver
from .gpu_run_emit import emit_gpu_scalar_result, gpu_device_cpp_name

if TYPE_CHECKING:
  from ..translator import Translator

_MAP_NAME = GPU_MAP_METHOD


def _is_gpu_map_call(node: ast.expr) -> bool:
  return (
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == _MAP_NAME
  )


def _field_cpp(tr: Translator, expr: ast.expr) -> str:
  return tr._visit_value_expr(expr)


def _emit_gpu_map_omp(
  tr: Translator,
  *,
  host_info,
  run: ast.FunctionDef,
  run_params: list[str],
  recv_cpp: str,
  input_fields: list[ast.expr],
  out_cpp: str,
  size_cpp: str,
  block_size: int,
) -> None:
  idx = temp_name("gi")
  param_map: dict[str, str] = {}
  for param_name, field_expr in zip(run_params, input_fields, strict=True):
    fcpp = _field_cpp(tr, field_expr)
    param_map[param_name] = f"{fcpp}.unsafeGet({idx})"

  device_funcs: dict[str, str] = {}
  for mp, func in gpu_device_meta_functions(tr):
    device_funcs[func.name] = gpu_device_cpp_name(mp, func.name)

  result_expr = emit_gpu_scalar_result(
    tr,
    run.body,
    self_name="self",
    self_cpp=recv_cpp,
    host_info=host_info,
    param_map=param_map,
    device_funcs=device_funcs,
    node=run,
  )

  tr.uses_openmp = True
  tr.write_line(f"const int _gpu_n = {size_cpp};")
  tr.write_line("#pragma omp parallel for schedule(static)")
  tr.write_line(f"for (int {idx} = 0; {idx} < _gpu_n; ++{idx}) {{")
  tr.write_line(f"  {out_cpp}.unsafeSet({idx}, {result_expr});")
  tr.write_line("}")
  tr.write_line(f"(void){block_size};")


def _emit_gpu_map_body(tr: Translator, node: ast.Call) -> None:
  if not getattr(tr, "gpu_enabled", False):
    raise_translation_error(tr, node, "`.map` 需要翻译时启用 `--gpu`")

  host_info = class_info_from_receiver(tr, node.func.value)
  if not host_inherits_gpu_kernel(host_info, tr.classes):
    raise_translation_error(tr, node, "`.map` 接收者须为 `GpuKernelMixin` 子类实例")
  if host_info is None:
    raise_translation_error(tr, node, "`.map` 接收者须为 `GpuKernelMixin` 子类实例")

  if len(node.args) < 1:
    raise_translation_error(tr, node, "`.map` 至少须有一个 output `Field` 参数")

  input_fields = list(node.args[:-1])
  out_field = node.args[-1]
  run = find_gpu_kernel_run(host_info)
  if run is None:
    raise_translation_error(tr, node, f"`{host_info.name}` 缺少 `run` 方法")

  run_params = [a.arg for a in run.args.args if a.arg not in ("self",)]
  if len(run_params) != len(input_fields):
    raise_translation_error(
      tr,
      node,
      f"`.map` input `Field` 个数 ({len(input_fields)}) 与 `run` 形参 ({len(run_params)}) 不一致",
    )

  recv_cpp = tr._visit_value_expr(node.func.value)
  out_cpp = _field_cpp(tr, out_field)
  size_cpp: str | None = None
  for field_expr in input_fields:
    fcpp = _field_cpp(tr, field_expr)
    size_cpp = f"static_cast<int>({fcpp}.__len__())"
    break
  if size_cpp is None:
    size_cpp = f"static_cast<int>({out_cpp}.__len__())"

  block_size = 256
  for stmt in host_info.node.body:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
      if stmt.target.id == "blockSize" and isinstance(stmt.value, ast.Constant):
        if isinstance(stmt.value.value, int):
          block_size = stmt.value.value

  backend = getattr(tr, "gpu_backend", "omp")
  if backend == GPU_BACKEND_CUDA:
    from ..codegen.gpu_backend_cuda import emit_cuda_host_map

    emit_cuda_host_map(
      tr,
      host_info=host_info,
      run=run,
      run_params=run_params,
      recv_cpp=recv_cpp,
      input_fields=input_fields,
      out_field=out_field,
      size_cpp=size_cpp,
    )
    return

  _emit_gpu_map_omp(
    tr,
    host_info=host_info,
    run=run,
    run_params=run_params,
    recv_cpp=recv_cpp,
    input_fields=input_fields,
    out_cpp=out_cpp,
    size_cpp=size_cpp,
    block_size=block_size,
  )


def try_emit_gpu_map_call(tr: Translator, node: ast.Call) -> str | None:
  """表达式上下文不支持 OpenMP；须走 ``emit_gpu_map_stmt``。"""
  if _is_gpu_map_call(node):
    raise_translation_error(tr, node, "`.map` 须作为独立语句（不可嵌在表达式内）")
  return None


def emit_gpu_map_stmt(tr: Translator, node: ast.Call) -> bool:
  if not _is_gpu_map_call(node):
    return False
  _emit_gpu_map_body(tr, node)
  return True
