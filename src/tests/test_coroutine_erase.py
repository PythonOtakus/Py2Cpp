"""``PyCoroutine`` 类型映射与 ``makePyCoroutine`` 表达式。"""
import ast
import unittest
from src.analysis.analyzer import TypeParser
from src.analysis.type_pred import is_concrete_coroutine_type, is_py_coroutine_type
from src.analysis.type_extract import coroutine_type_args
from src.analysis.ir import cpp_make_py_coroutine_expr

class PyCoroutineTypeTests(unittest.TestCase):

    def test_parse_coroutine_ann_storage(self):
        tp = TypeParser()
        ann = ast.parse('Coroutine[int, None, None]').body[0].value
        cpp = tp.parse_storage_type(ann, set())
        self.assertEqual(cpp, 'PyCoroutine<PyInt, PyNone, PyNone>')

    def test_py_coroutine_type_args(self):
        args = coroutine_type_args('PyCoroutine<PyInt, PyNone, PyNone>')
        self.assertEqual(args, ('PyInt', 'PyNone', 'PyNone'))

    def test_make_py_coroutine_expr(self):
        got = cpp_make_py_coroutine_expr('PyCoroutine<PyInt, PyNone, PyNone>', 'async_pair_coroutine()')
        self.assertEqual(got, 'makeCoroutine<PyInt, PyNone, PyNone>(async_pair_coroutine())')

    def test_concrete_coroutine_detect(self):
        self.assertTrue(is_concrete_coroutine_type('async_pair_coroutine'))
        self.assertFalse(is_concrete_coroutine_type('PyCoroutine<PyInt, PyNone, PyNone>'))
        self.assertTrue(is_py_coroutine_type('PyCoroutine<PyInt, PyNone, PyNone>'))
if __name__ == '__main__':
    unittest.main()
