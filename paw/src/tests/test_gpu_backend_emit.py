"""GPU ``--gpu-backend=cuda`` 生成 ``.cu``。"""
from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
import tempfile

from src.translator import Translator


class GpuBackendCudaEmitTests(unittest.TestCase):
  def _translate(self, code: str, *, gpu_backend: str = "cuda") -> tuple[Path, Path]:
    src = textwrap.dedent(code).strip() + "\n"
    tmp = tempfile.mkdtemp()
    out = Path(tmp)
    py = out / "mod.py"
    py.write_text(src, encoding="utf-8")
    return Translator.translate_file(
      str(py),
      output_dir=str(out),
      include_stdlib=True,
      emit_main=False,
      strict=False,
      gpu_enabled=True,
      gpu_backend=gpu_backend,
    )

  def test_cuda_backend_writes_cu(self):
    _, cpp = self._translate(
      """
      from paw import *
      from paw.gpu import Field, GpuKernelMixin, gpuSync

      @dataclass
      class Add(GpuKernelMixin):
        c: float
        def run(self, a: float, b: float) -> float:
          return a + b + self.c

      def work() -> None:
        n: int = 4
        a: Field[float] = new.zeros(n)
        b: Field[float] = new.ones(n)
        out: Field[float] = new.zeros(n)
        with gpuSync():
          op: Add = new(c=1.0)
          op.map(a, b, out)
      """,
      gpu_backend="cuda",
    )
    cu = cpp.with_suffix(".cu")
    self.assertTrue(cu.is_file(), f"missing {cu}")
    text = cu.read_text(encoding="utf-8")
    self.assertIn("__global__", text)
    self.assertIn("launch_Add", text)
    self.assertIn("cudaDeviceSynchronize", cpp.read_text(encoding="utf-8"))
    self.assertIn("cudaMalloc", cpp.read_text(encoding="utf-8"))

  def test_omp_backend_no_cu(self):
    _, cpp = self._translate(
      """
      from paw import *
      from paw.gpu import Field, GpuKernelMixin

      @dataclass
      class Add(GpuKernelMixin):
        c: float
        def run(self, a: float, b: float) -> float:
          return a + b + self.c

      def work() -> None:
        a: Field[float] = new.zeros(2)
        b: Field[float] = new.ones(2)
        out: Field[float] = new.zeros(2)
        op: Add = new(c=1.0)
        op.map(a, b, out)
      """,
      gpu_backend="omp",
    )
    self.assertFalse(cpp.with_suffix(".cu").is_file())
    self.assertIn("#pragma omp", cpp.read_text(encoding="utf-8"))


if __name__ == "__main__":
  unittest.main()
