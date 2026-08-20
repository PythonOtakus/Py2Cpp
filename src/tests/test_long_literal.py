"""``varint`` 整型字面量 → ``PyVarInt("…")``。"""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from src.analysis.type_pred import is_varint_type
from src.analysis.ir import format_cpp_varint
from src.translator import Translator

class TestVarintLiteral(unittest.TestCase):

    def test_format_cpp_varint(self):
        self.assertEqual(format_cpp_varint(100), 'PyVarInt(PyStr("100"))')
        self.assertEqual(format_cpp_varint(-42), 'PyVarInt(PyStr("-42"))')

    def test_format_cpp_varint_huge(self):
        self.assertEqual(format_cpp_varint(9223372036854775808), 'PyVarInt(PyStr("9223372036854775808"))')
        self.assertEqual(format_cpp_varint(-10000000000000000000), 'PyVarInt(PyStr("-10000000000000000000"))')

    def test_is_cpp_varint_type(self):
        self.assertTrue(is_varint_type('PyVarInt'))
        self.assertFalse(is_varint_type('PyInt'))

    def _translate(self, body: str) -> str:
        src = f'from py2cpp import varint\n\ndef probe():\n{body}'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            py = out / 'mod.py'
            py.write_text(src, encoding='utf-8')
            _h, cpp_path = Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False)
            return cpp_path.read_text(encoding='utf-8')

    def test_huge_int_literal_ann_assign(self):
        cpp = self._translate('  x: varint = 9223372036854775808\n')
        self.assertIn('PyVarInt(PyStr("9223372036854775808"))', cpp)

    def test_huge_negative_int_literal(self):
        cpp = self._translate('  x: varint = -10000000000000000000\n')
        self.assertIn('PyVarInt(PyStr("-10000000000000000000"))', cpp)
if __name__ == '__main__':
    unittest.main()
