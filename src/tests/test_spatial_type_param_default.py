"""``py2cpp.spatial`` 泛型标量类型参数默认 ``float``。"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class SpatialTypeParamDefaultTests(unittest.TestCase):
  def test_spatial_headers_default_scalar_to_float(self):
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      cases = [
        ("vector.h", ("PyVector2", "PyVector3", "PyVector4")),
        ("rotator.h", ("PyRotator", "PyQuaternion")),
        ("matrix.h", ("PyMatrix3", "PyMatrix4")),
        ("transform.h", ("PyTransform2D", "PyTransform3D")),
        ("rect.h", ("PyRect",)),
        ("color.h", ("PyColor", "PyColorMatrix")),
      ]
      for header, classes in cases:
        Translator.translate_file(
          str(root / "py2cpp" / "spatial" / header.replace(".h", ".py")),
          output_dir=str(out),
          include_stdlib=True,
          emit_main=False,
        )
        text = (out / "runtime" / "py2cpp" / "spatial" / header).read_text(encoding="utf-8")
        for cls in classes:
          with self.subTest(header=header, cls=cls):
            self.assertRegex(
              text,
              rf"template\s*<\s*typename _Scalar\s*=\s*PyFloat\s*>\s*\n\s*class {re.escape(cls)}",
            )


if __name__ == "__main__":
  unittest.main()
