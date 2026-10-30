"""CUDA AOT：``.map`` → ``.cu``（``__device__`` / ``__global__`` + Host launch 包装）。"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import cpp_ident
from ..constant.gpu import GPU_LAUNCH_BLOCK_SIZE_FIELD
from ..passes.gpu_common import gpu_device_meta_functions
from ..emit.gpu_run_emit import emit_gpu_scalar_result, gpu_device_cpp_name

if TYPE_CHECKING:
  from ..analysis.ir import ClassInfo
  from ..translator import Translator


@dataclass
class GpuCudaKernelJob:
  """一次 ``.map`` 对应的 Device kernel 记录。"""

  class_name: str
  kernel_name: str
  launch_name: str
  host_info: ClassInfo
  run: ast.FunctionDef
  run_params: list[str]
  uniforms: list[str]
  block_size: int
  elem_cpp: str = "float"


def gpu_kernel_cpp_name(class_name: str) -> str:
  return cpp_ident(f"_gpu_k_{class_name}")


def gpu_launch_cpp_name(class_name: str) -> str:
  return cpp_ident(f"_gpu_launch_{class_name}")


def _uniform_fields(info: ClassInfo) -> list[str]:
  out: list[str] = []
  for name in info.fields:
    if name == GPU_LAUNCH_BLOCK_SIZE_FIELD:
      continue
    if name.startswith("_"):
      continue
    out.append(name)
  return out


def _block_size(info: ClassInfo) -> int:
  for stmt in info.node.body:
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
      if stmt.target.id == GPU_LAUNCH_BLOCK_SIZE_FIELD and isinstance(stmt.value, ast.Constant):
        if isinstance(stmt.value.value, int):
          return stmt.value.value
  return 256


def register_cuda_kernel_job(
  tr: Translator,
  *,
  host_info: ClassInfo,
  run: ast.FunctionDef,
  run_params: list[str],
) -> GpuCudaKernelJob:
  jobs: list[GpuCudaKernelJob] | None = getattr(tr, "gpu_cuda_jobs", None)
  if jobs is None:
    jobs = []
    tr.gpu_cuda_jobs = jobs  # type: ignore[attr-defined]
  for existing in jobs:
    if existing.class_name == host_info.name:
      return existing
  job = GpuCudaKernelJob(
    class_name=host_info.name,
    kernel_name=gpu_kernel_cpp_name(host_info.name),
    launch_name=gpu_launch_cpp_name(host_info.name),
    host_info=host_info,
    run=run,
    run_params=list(run_params),
    uniforms=_uniform_fields(host_info),
    block_size=_block_size(host_info),
  )
  jobs.append(job)
  return job


def _member_access(tr: Translator, info: ClassInfo, self_cpp: str, attr: str) -> str:
  return f"{self_cpp}.{tr._member_cpp_name(info, attr)}"


def emit_cuda_host_map(
  tr: Translator,
  *,
  host_info: ClassInfo,
  run: ast.FunctionDef,
  run_params: list[str],
  recv_cpp: str,
  input_fields: list[ast.expr],
  out_field: ast.expr,
  size_cpp: str,
) -> None:
  """Host：H2D → launch → D2H（缓冲仍为 ``Field`` Host ``array``）。"""
  job = register_cuda_kernel_job(tr, host_info=host_info, run=run, run_params=run_params)
  tr.uses_cuda = True  # type: ignore[attr-defined]
  out_cpp = tr._visit_value_expr(out_field)
  field_cpps = [tr._visit_value_expr(f) for f in input_fields]

  tr.write_line("{")
  tr.write_line(f"  const int _gpu_n = {size_cpp};")
  tr.write_line("  if (_gpu_n > 0) {")
  tr.write_line(f"    {job.elem_cpp}* _h_out = {out_cpp}.unsafePtr();")
  for i, fcpp in enumerate(field_cpps):
    tr.write_line(f"    {job.elem_cpp}* _h_in{i} = {fcpp}.unsafePtr();")
  tr.write_line(f"    {job.elem_cpp}* _d_out = nullptr;")
  for i in range(len(field_cpps)):
    tr.write_line(f"    {job.elem_cpp}* _d_in{i} = nullptr;")
  nbytes = f"static_cast<size_t>(_gpu_n) * sizeof({job.elem_cpp})"
  tr.write_line(f"    cudaMalloc(reinterpret_cast<void**>(&_d_out), {nbytes});")
  for i in range(len(field_cpps)):
    tr.write_line(f"    cudaMalloc(reinterpret_cast<void**>(&_d_in{i}), {nbytes});")
    tr.write_line(
      f"    cudaMemcpy(_d_in{i}, _h_in{i}, {nbytes}, cudaMemcpyHostToDevice);"
    )
  uniform_args = [
    _member_access(tr, host_info, recv_cpp, u) for u in job.uniforms
  ]
  launch_args = [
    *uniform_args,
    *[f"_d_in{i}" for i in range(len(field_cpps))],
    "_d_out",
    "_gpu_n",
    str(job.block_size),
  ]
  tr.write_line(f"    {job.launch_name}({', '.join(launch_args)});")
  tr.write_line(
    f"    cudaMemcpy(_h_out, _d_out, {nbytes}, cudaMemcpyDeviceToHost);"
  )
  for i in range(len(field_cpps)):
    tr.write_line(f"    cudaFree(_d_in{i});")
  tr.write_line("    cudaFree(_d_out);")
  tr.write_line("  }")
  tr.write_line("}")


def _cuda_scalar_cpp(cpp_type: str) -> str:
  """Device TU 不用 py2cpp Host 标量包装类型。"""
  mapping = {
    "PyFloat": "float",
    "float": "float",
    "double": "double",
    "PyInt": "int",
    "int": "int",
    "int64": "long long",
    "int32": "int",
    "uint64": "unsigned long long",
    "bool": "bool",
    "void": "void",
  }
  return mapping.get(cpp_type, cpp_type)


def build_cuda_source(tr: Translator) -> str | None:
  """生成入口旁 ``.cu`` 全文；无 job 则 ``None``。"""
  jobs: list[GpuCudaKernelJob] = getattr(tr, "gpu_cuda_jobs", None) or []
  if not jobs:
    return None

  lines: list[str] = [
    "// 由 py2cpp 自动生成（CUDA AOT），请勿手动编辑",
    f"// 源文件: {tr.source_path}",
    "#include <cuda_runtime.h>",
    "",
  ]

  for mp, func in gpu_device_meta_functions(tr):
    ret_ann = func.returns
    ret_cpp = _cuda_scalar_cpp(tr._parse_type(ret_ann, ()) if ret_ann else "void")
    params: list[str] = []
    param_map: dict[str, str] = {}
    for arg in func.args.args:
      if arg.arg == "self":
        continue
      ann = arg.annotation or ast.Name(id="float", ctx=ast.Load())
      ptype = _cuda_scalar_cpp(tr._parse_type(ann, ()))
      params.append(f"{ptype} {arg.arg}")
      param_map[arg.arg] = arg.arg
    device_funcs = {
      f.name: gpu_device_cpp_name(m, f.name)
      for m, f in gpu_device_meta_functions(tr)
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
    name = gpu_device_cpp_name(mp, func.name)
    lines.append(f"__device__ {ret_cpp} {name}({', '.join(params)}) {{")
    lines.append(f"  return {body_expr};")
    lines.append("}")
    lines.append("")

  for job in jobs:
    class RewriteSelf(ast.NodeTransformer):
      def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "self":
          if node.attr in job.uniforms:
            return ast.copy_location(ast.Name(id=node.attr, ctx=ast.Load()), node)
        return node

    body = [RewriteSelf().visit(copy.deepcopy(s)) for s in job.run.body]
    param_map = {p: f"{p}[i]" for p in job.run_params}
    for u in job.uniforms:
      param_map[u] = u
    device_funcs = {
      f.name: gpu_device_cpp_name(mp, f.name)
      for mp, f in gpu_device_meta_functions(tr)
    }
    result_expr = emit_gpu_scalar_result(
      tr,
      body,
      self_name="self",
      self_cpp="",
      host_info=None,
      param_map=param_map,
      device_funcs=device_funcs,
      node=job.run,
    )

    uniform_sig = [f"{job.elem_cpp} {u}" for u in job.uniforms]
    in_sig = [f"const {job.elem_cpp}* {p}" for p in job.run_params]
    kparams = [*uniform_sig, *in_sig, f"{job.elem_cpp}* out", "int n"]
    lines.append(f"__global__ void {job.kernel_name}({', '.join(kparams)}) {{")
    lines.append("  int i = blockIdx.x * blockDim.x + threadIdx.x;")
    lines.append("  if (i >= n) return;")
    lines.append(f"  out[i] = {result_expr};")
    lines.append("}")
    lines.append("")

    launch_params = [
      *uniform_sig,
      *in_sig,
      f"{job.elem_cpp}* out",
      "int n",
      "int blockSize",
    ]
    launch_args = [*job.uniforms, *job.run_params, "out", "n"]
    lines.append(f'extern "C" void {job.launch_name}({", ".join(launch_params)}) {{')
    lines.append("  if (n <= 0) return;")
    lines.append("  int bs = blockSize > 0 ? blockSize : 256;")
    lines.append("  int gs = (n + bs - 1) / bs;")
    lines.append(f"  {job.kernel_name}<<<gs, bs>>>({', '.join(launch_args)});")
    lines.append("}")
    lines.append("")

  return "\n".join(lines) + "\n"


def cuda_extern_decl_lines(tr: Translator) -> list[str]:
  """``extern \"C\"`` launch 声明行（插入 ``.cpp`` include 区之后）。"""
  jobs: list[GpuCudaKernelJob] = getattr(tr, "gpu_cuda_jobs", None) or []
  lines: list[str] = []
  for job in jobs:
    uniform_sig = [f"{job.elem_cpp} {u}" for u in job.uniforms]
    in_sig = [f"{job.elem_cpp}* {p}" for p in job.run_params]
    launch_params = [
      *uniform_sig,
      *in_sig,
      f"{job.elem_cpp}* out",
      "int n",
      "int blockSize",
    ]
    lines.append(f'extern "C" void {job.launch_name}({", ".join(launch_params)});')
  return lines


def emit_cuda_extern_decls(tr: Translator) -> None:
  for line in cuda_extern_decl_lines(tr):
    tr.write_line(line)
