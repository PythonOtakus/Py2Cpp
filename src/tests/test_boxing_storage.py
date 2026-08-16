"""``@boxing`` 存储类型：泛型 ``Self`` 须与 ``cpp_specialization()`` 形参名无关地转为指针。"""
import ast
import unittest

from src.analysis.ir import ClassInfo


class TestBoxingStorage(unittest.TestCase):
  def test_generic_template_args_become_pointer(self):
    src = '''
from py2cpp import DictKeyType, Self, boxing

@boxing
class DictEntryUnsafe[Key: DictKeyType, Value]:
  pass
'''
    info = ClassInfo(ast.parse(src).body[-1], module_path="py2cpp/util/dict.py")
    classes = {"DictEntryUnsafe": info}
    t = "PyDictEntryUnsafe<Key, Value>"
    self.assertEqual(
      ClassInfo.apply_boxing_storage_cpp_type(t, classes),
      "PyDictEntryUnsafe<Key, Value>*",
    )
    self.assertEqual(
      ClassInfo.apply_boxing_storage_cpp_type(
        f"PyArray<{t}>", classes,
      ),
      "PyArray<PyDictEntryUnsafe<Key, Value>*>",
    )


if __name__ == "__main__":
  unittest.main()
