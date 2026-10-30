"""``@GpuDeviceMeta`` 模块函数 → static 设备辅助（P1 Host sim）。"""
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_param
from ..passes.gpu_common import gpu_device_meta_functions
from .gpu_run_emit import emit_gpu_scalar_result, gpu_device_cpp_name

if TYPE_CHECKING:
  from ..translator import Translator


def emit_gpu_device_functions(tr: Translator, module_path: str) -> None:
  if not getattr(tr, "gpu_enabled", False):
    return
  for mp, func in gpu_device_meta_functions(tr):
    if mp != module_path:
      continue
    _emit_one_device_func(tr, mp, func)


def _emit_one_device_func(tr: Translator, module_path: str, func: ast.FunctionDef) -> None:
  ret_ann = func.returns
  ret_cpp = tr._parse_type(ret_ann, ()) if ret_ann else "void"
  params: list[str] = []
  param_map: dict[str, str] = {}
  for arg in func.args.args:
    if arg.arg == "self":
      continue
    ann = arg.annotation or ast.Name(id="float", ctx=ast.Load())
    ptype = tr._parse_type(ann, ())
    params.append(f"{ptype} {cpp_param(arg.arg)}")
    param_map[arg.arg] = cpp_param(arg.arg)

  name = gpu_device_cpp_name(module_path, func.name)
  param_str = ", ".join(params)
  device_funcs = {
    f.name: gpu_device_cpp_name(module_path, f.name)
    for _mp, f in gpu_device_meta_functions(tr)
  }
  body_expr = emit_gpu_scalar_result(
    tr,
    func.body,
    self_name="self",
    self_cpp="",
    host_info=None,
    param_map=param_map,
    device_funcs=device_funcs,
    node=func,
  )
  sig = f"static {ret_cpp} {name}({param_str})"
  with tr._use_block(sig):
    tr.write_line(f"return {body_expr};")
  tr.write_line()
