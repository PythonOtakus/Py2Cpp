"""``prange`` OpenMP emit。"""
from __future__ import annotations

import ast
import textwrap
import unittest

from src.emit.prange_emit import _omp_pragma, _reduction_clause, parse_prange_call
from src.translator import Translator


class PrangeEmitTests(unittest.TestCase):
  def _translate_snippet(self, code: str, *, openmp: bool = True) -> str:
    import tempfile
    from pathlib import Path

    src = textwrap.dedent(code).strip() + "\n"
    with tempfile.TemporaryDirectory() as tmpdir:
      out = Path(tmpdir)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _, cpp = Translator.translate_file(
        str(py),
        output_dir=str(out),
        include_stdlib=True,
        emit_main=False,
        strict=False,
        openmp_enabled=openmp,
      )
      return cpp.read_text(encoding="utf-8")

  def test_omp_pragma_reduction(self):
    clause = _reduction_clause((("total", "+"), ("acc", "+")))
    self.assertIn("reduction(+:acc,total)", clause.replace(" ", ""))

  def test_static_schedule_omits_clause(self):
    from src.emit.prange_emit import PrangeSpec

    p = PrangeSpec("0", "n", "1", "static", None, None, 0, "0", ())
    self.assertEqual(_omp_pragma(p), "#pragma omp parallel for")

  def test_th_skips_omp_for_small_const_trip(self):
    cpp = self._translate_snippet(
      """
      from py2cpp.concur.parallel import prange

      def work() -> None:
        for i in prange(64, th=10000):
          pass
      """,
      openmp=True,
    )
    self.assertNotIn("#pragma omp", cpp)
    self.assertIn("for (int i = 0;", cpp)

  def test_th_zero_keeps_omp(self):
    cpp = self._translate_snippet(
      """
      from py2cpp.concur.parallel import prange

      def work() -> None:
        for i in prange(64, th=0):
          pass
      """,
      openmp=True,
    )
    self.assertIn("#pragma omp parallel for", cpp)

  def test_th_large_const_trip_uses_omp(self):
    cpp = self._translate_snippet(
      """
      from py2cpp.concur.parallel import prange

      def work() -> None:
        for i in prange(10000, th=10000):
          pass
      """,
      openmp=True,
    )
    self.assertIn("#pragma omp parallel for", cpp)
    self.assertNotIn("if (", cpp)

  def test_th_runtime_emits_branch(self):
    cpp = self._translate_snippet(
      """
      from py2cpp.concur.parallel import prange

      def work(n: int) -> None:
        for i in prange(n, th=10000):
          pass
      """,
      openmp=True,
    )
    self.assertIn("#pragma omp parallel for", cpp)
    self.assertIn(">=10000", cpp.replace(" ", ""))
    self.assertNotIn("[&]()", cpp)

  def test_th_len_emits_branch(self):
    cpp = self._translate_snippet(
      """
      from py2cpp.concur.parallel import prange

      def work(s: int[:]) -> None:
        for i in prange(len(s), th=10000):
          pass
      """,
      openmp=True,
    )
    self.assertIn("#pragma omp parallel for", cpp)
    self.assertIn(">=10000", cpp.replace(" ", ""))
    self.assertNotIn("[&]()", cpp)
    self.assertIn("__len__()", cpp)

  def test_openmp_disabled_emits_plain_for(self):
    cpp = self._translate_snippet(
      """
      from py2cpp.concur.parallel import prange

      def work(n: int) -> None:
        for i in prange(n):
          pass
      """,
      openmp=False,
    )
    self.assertNotIn("#pragma omp", cpp)
    self.assertIn("for (int i = 0;", cpp)


if __name__ == "__main__":
  unittest.main()
