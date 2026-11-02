"""``protocol_traits_gen`` 全局二元探测与 ``operators.h`` 一致。"""
import unittest

from src.codegen.protocol_traits_gen import _sfinae_binary_global_probe


class ProtocolEmitPowProbeTests(unittest.TestCase):
  def test_pow_uses_global_pow_not_dunder(self):
    line = _sfinae_binary_global_probe("__pow__", "U")
    self.assertIsNotNone(line)
    assert line is not None
    self.assertIn("::pow(", line)
    self.assertNotIn("::__pow__(", line)


if __name__ == "__main__":
  unittest.main()
