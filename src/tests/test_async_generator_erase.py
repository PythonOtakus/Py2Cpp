"""``PyAsyncGenerator`` 类型映射与 ``makeAsyncGenerator`` 表达式。"""
import ast
import unittest
from src.analysis.analyzer import TypeParser
from src.analysis.type_pred import is_concrete_coroutine_type, is_py_async_generator_type
from src.analysis.type_extract import async_generator_type_args
from src.analysis.ir import cpp_make_py_async_generator_expr

class PyAsyncGeneratorTypeTests(unittest.TestCase):

    def test_parse_async_generator_ann_storage(self):
        tp = TypeParser()
        ann = ast.parse('AsyncGeneratorType[int, None]').body[0].value
        cpp = tp.parse_storage_type(ann, set())
        self.assertEqual(cpp, 'PyAsyncGenerator<PyInt, PyNone>')

    def test_py_async_generator_type_args(self):
        args = async_generator_type_args('PyAsyncGenerator<PyInt, PyNone>')
        self.assertEqual(args, ('PyInt', 'PyNone'))

    def test_make_py_async_generator_expr(self):
        got = cpp_make_py_async_generator_expr('PyAsyncGenerator<PyInt, PyNone>', 'async_gen_pair_coroutine()')
        self.assertEqual(got, 'makeAsyncGenerator<PyInt, PyNone>(async_gen_pair_coroutine())')

    def test_concrete_coroutine_to_async_generator_erase(self):
        self.assertTrue(is_concrete_coroutine_type('async_gen_pair_coroutine'))
        self.assertFalse(is_concrete_coroutine_type('PyAsyncGenerator<PyInt, PyNone>'))
        self.assertTrue(is_py_async_generator_type('PyAsyncGenerator<PyInt, PyNone>'))
if __name__ == '__main__':
    unittest.main()
