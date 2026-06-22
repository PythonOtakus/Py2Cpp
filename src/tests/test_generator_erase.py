"""``PyGenerator`` 类型映射与 ``makePyGenerator`` 表达式。"""
import ast
import unittest
from src.analysis.analyzer import TypeParser
from src.analysis.type_pred import is_concrete_generator_type, is_py_generator_type
from src.analysis.type_extract import generator_type_args
from src.analysis.ir import cpp_make_py_generator_expr

class PyGeneratorTypeTests(unittest.TestCase):

    def test_parse_generator_ann_storage(self):
        tp = TypeParser()
        ann = ast.parse('Generator[int, None, None]').body[0].value
        cpp = tp.parse_storage_type(ann, set())
        self.assertEqual(cpp, 'PyGenerator<PyInt, PyNone, PyNone>')

    def test_py_generator_type_args(self):
        args = generator_type_args('PyGenerator<PyInt, PyNone, PyNone>')
        self.assertEqual(args, ('PyInt', 'PyNone', 'PyNone'))

    def test_make_py_generator_expr(self):
        got = cpp_make_py_generator_expr('PyGenerator<PyInt, PyNone, PyNone>', 'gen_pair_generator()')
        self.assertEqual(got, 'makeGenerator<PyInt, PyNone, PyNone>(gen_pair_generator())')

    def test_concrete_generator_detect(self):
        self.assertTrue(is_concrete_generator_type('gen_pair_generator'))
        self.assertFalse(is_concrete_generator_type('PyGenerator<PyInt, PyNone, PyNone>'))
        self.assertTrue(is_py_generator_type('PyGenerator<PyInt, PyNone, PyNone>'))
if __name__ == '__main__':
    unittest.main()
