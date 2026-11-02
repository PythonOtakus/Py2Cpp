"""``long`` 整型字面量 → ``PyLong("…")``。"""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from src.analysis.type_pred import is_long_type
from src.analysis.ir import format_cpp_long
from src.translator import Translator

class TestLongLiteral(unittest.TestCase):

    def test_format_cpp_long(self):
        self.assertEqual(format_cpp_long(100), 'PyLong(PyStr("100"))')
        self.assertEqual(format_cpp_long(-42), 'PyLong(PyStr("-42"))')

    def test_format_cpp_long_huge(self):
        self.assertEqual(format_cpp_long(9223372036854775808), 'PyLong(PyStr("9223372036854775808"))')
        self.assertEqual(format_cpp_long(-10000000000000000000), 'PyLong(PyStr("-10000000000000000000"))')

    def test_is_cpp_long_type(self):
        self.assertTrue(is_long_type('PyLong'))
        self.assertFalse(is_long_type('PyInt'))

    def _translate(self, body: str) -> str:
        src = f'from py2cpp import *\n\ndef probe():\n{body}'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            py = out / 'mod.py'
            py.write_text(src, encoding='utf-8')
            _h, cpp_path = Translator.translate_file(str(py), output_dir=str(out), include_stdlib=False)
            return cpp_path.read_text(encoding='utf-8')

    def test_huge_int_literal_ann_assign(self):
        cpp = self._translate('  x: long = 9223372036854775808\n')
        self.assertIn('PyLong(PyStr("9223372036854775808"))', cpp)

    def test_huge_negative_int_literal(self):
        cpp = self._translate('  x: long = -10000000000000000000\n')
        self.assertIn('PyLong(PyStr("-10000000000000000000"))', cpp)
if __name__ == '__main__':
    unittest.main()
