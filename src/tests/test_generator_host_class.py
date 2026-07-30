"""类方法 ``*_generator`` 宿主类解析（``Self._…`` 静态调用）。"""
import ast
import copy
import re
import tempfile
import unittest
from pathlib import Path

from src.passes.generators import (
  COROUTINE_SUFFIX,
  GENERATOR_SUFFIX,
  _desugar_generator_yield_from_to_for,
  _for_iter_suspend_fields,
  _host_class_from_gen_name,
  _host_substitute_ann,
  _infer_hoisted_field_ann,
  _infer_iter_type,
  _list_ann_from_generator_name,
  _meth_host_from_generator_name,
  _auto_register_member_generator_friends,
  _static_method_returns_list_elem,
  _yield_from_fields,
)
from src.translator import Translator


class _HoistTr:
  classes: dict = {"Host_close_coroutine": object()}


class _PathTr:
  classes: dict = {
    "Path": type(
      "CI",
      (),
      {
        "methods": {
          "_glob_select": type(
            "M",
            (),
            {
              "returns": ast.Subscript(
                value=ast.Name(id="Generator"),
                slice=ast.Tuple(
                  elts=[
                    ast.Name(id="str"),
                    ast.Constant(value=None),
                    ast.Constant(value=None),
                  ],
                ),
              ),
            },
          )(),
          "_glob_select_parts": type(
            "M",
            (),
            {
              "returns": ast.Subscript(
                value=ast.Name(id="Generator"),
                slice=ast.Tuple(
                  elts=[
                    ast.Name(id="str"),
                    ast.Constant(value=None),
                    ast.Constant(value=None),
                  ],
                ),
              ),
            },
          )(),
        },
        "cpp_name": lambda self: "Path",
      },
    )(),
    "Path__glob_select_generator": object(),
  }


class GeneratorHostClassTests(unittest.TestCase):
  def _translate(self, src: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      h_path, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True, strict=False,
      )
      return (
        Path(h_path).read_text(encoding="utf-8")
        + "\n"
        + Path(cpp_path).read_text(encoding="utf-8")
      )

  def test_infer_iter_type_self_async_method(self):
    expr = ast.Call(
      func=ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr="close",
        ctx=ast.Load(),
      ),
      args=[],
      keywords=[],
    )
    ann = _infer_iter_type(expr, _HoistTr(), [], host_class="Host")
    self.assertIsInstance(ann, ast.Name)
    self.assertEqual(ann.id, f"Host_close{COROUTINE_SUFFIX}")

  def test_host_from_class_method_generator(self):
    self.assertEqual(
      _host_class_from_gen_name("str_xsplit_generator", "xsplit"),
      "str",
    )

  def test_host_from_class_method_coroutine(self):
    self.assertEqual(
      _host_class_from_gen_name("str_foo_coroutine", "foo"),
      "str",
    )

  def test_module_level_generator_has_no_host(self):
    self.assertIsNone(
      _host_class_from_gen_name(f"gen_three{GENERATOR_SUFFIX}", "gen_three"),
    )

  def test_unrelated_name(self):
    self.assertIsNone(
      _host_class_from_gen_name("str_xsplit_generator", "rsplit"),
    )

  def test_hoisted_ann_from_ann_assign(self):
    body = [
      ast.AnnAssign(
        target=ast.Name(id="out", ctx=ast.Store()),
        annotation=ast.Subscript(
          value=ast.Name(id="list", ctx=ast.Load()),
          slice=ast.Name(id="Self", ctx=ast.Load()),
        ),
        value=ast.List(elts=[]),
        simple=1,
      ),
    ]
    ann = _infer_hoisted_field_ann("out", body, _HoistTr())
    self.assertIsInstance(ann, ast.Subscript)
    self.assertEqual(ann.value.id, "list")

  def test_hoisted_ann_inside_while_if(self):
    body = [
      ast.While(
        test=ast.Constant(value=True),
        body=[
          ast.If(
            test=ast.Constant(value=True),
            body=[
              ast.AnnAssign(
                target=ast.Name(id="endb", ctx=ast.Store()),
                annotation=ast.Subscript(
                  value=ast.Name(id="byte", ctx=ast.Load()),
                  slice=ast.Slice(),
                ),
                value=ast.Call(func=ast.Name(id="new"), args=[ast.Name(id="n")]),
                simple=1,
              ),
            ],
            orelse=[],
          ),
        ],
        orelse=[],
      ),
    ]
    ann = _infer_hoisted_field_ann("endb", body, _HoistTr())
    self.assertIsInstance(ann, ast.Subscript)
    self.assertEqual(ann.value.id, "byte")

  def test_host_substitute_self_in_yield_ann(self):
    ann = _host_substitute_ann(ast.Name(id="Self"), "Path", _PathTr())
    self.assertIsInstance(ann, ast.Name)
    self.assertEqual(ann.id, "Path")

  def test_infer_iter_type_self_static_generator_method(self):
    expr = ast.Call(
      func=ast.Attribute(
        value=ast.Name(id="Self", ctx=ast.Load()),
        attr="_glob_select",
        ctx=ast.Load(),
      ),
      args=[ast.Constant(value="."), ast.Constant(value="*")],
      keywords=[],
    )
    ann = _infer_iter_type(expr, _PathTr(), [], host_class="Path")
    self.assertIsInstance(ann, ast.Name)
    self.assertEqual(ann.id, f"Path__glob_select{GENERATOR_SUFFIX}")

  def test_static_method_returns_list_elem(self):
    elem = _static_method_returns_list_elem("Path", "_glob_select", _PathTr())
    self.assertIsNone(elem)

  def test_static_generator_host_from_class_name(self):
    from src.analysis.ir import ClassInfo
    from src.translator import Translator

    gen_cls = ast.ClassDef(
      name=f"Path__glob_select_parts{GENERATOR_SUFFIX}",
      bases=[],
      keywords=[],
      body=[],
      decorator_list=[],
    )
    path_cls = ast.ClassDef(
      name="Path",
      bases=[],
      keywords=[],
      body=[
        ast.FunctionDef(
          name="_glob_select_parts",
          args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
          ),
          body=[],
          decorator_list=[],
        ),
      ],
      decorator_list=[],
    )
    tr = Translator("path", "path.py", strict=False)
    tr.classes = {
      "Path": ClassInfo(path_cls, "py2cpp/io/path"),
      gen_cls.name: ClassInfo(gen_cls, "py2cpp/io/path"),
    }
    tr.class_info = tr.classes[gen_cls.name]
    host = tr._static_generator_host_class_info()
    self.assertIsNotNone(host)
    self.assertEqual(host.name, "Path")
    self.assertIsNone(tr._generator_host_class_info())

    expr = ast.Call(
      func=ast.Name(id="scandir", ctx=ast.Load()),
      args=[ast.Name(id="root", ctx=ast.Load())],
      keywords=[],
    )
    ann = _infer_iter_type(expr, _PathTr(), [])
    self.assertIsInstance(ann, ast.Name)
    self.assertEqual(ann.id, "ScandirIterator")

  def test_scandir_iter_uses_assign_not_copy_from(self):
    from src.passes.generators import _yield_from_iter_uses_assign

    self.assertFalse(_yield_from_iter_uses_assign(ast.Name(id="ScandirIterator")))

  def test_meth_host_from_generator_name(self):
    hm = _meth_host_from_generator_name(
      f"Path__glob_select_parts{GENERATOR_SUFFIX}", _PathTr(),
    )
    self.assertEqual(hm, ("Path", "_glob_select_parts"))

  def test_list_ann_before_generator_registered(self):
    tr = _PathTr()
    pair = _list_ann_from_generator_name(
      f"Path__glob_select_parts{GENERATOR_SUFFIX}", tr,
    )
    self.assertIsNotNone(pair)
    it_ann, seq_ann = pair
    self.assertEqual(it_ann.value.id, "list_iterator")
    self.assertEqual(seq_ann.value.id, "list")

  def test_for_suspend_materializes_nested_generator(self):
    body = [
      ast.For(
        target=ast.Name(id="hit", ctx=ast.Store()),
        iter=ast.Call(
          func=ast.Attribute(
            value=ast.Name(id="Self", ctx=ast.Load()),
            attr="_glob_select_parts",
            ctx=ast.Load(),
          ),
          args=[
            ast.Name(id="root", ctx=ast.Load()),
            ast.Name(id="parts", ctx=ast.Load()),
            ast.Constant(value=0),
          ],
          keywords=[],
        ),
        body=[ast.Expr(value=ast.Yield(value=ast.Name(id="hit", ctx=ast.Load())))],
        orelse=[],
      ),
    ]
    fields = _for_iter_suspend_fields(
      body, _PathTr(), host_class="Path",
      current_gen=f"Path__glob_select{GENERATOR_SUFFIX}",
      elem_ann=ast.Name(id="str"),
    )
    self.assertEqual(len(fields), 1)
    it_field, it_ann, seq_ann = fields[0]
    self.assertEqual(it_field, "_for0_it")
    self.assertEqual(it_ann.value.id, "list_iterator")
    self.assertEqual(seq_ann.value.id, "list")

  def test_desugar_static_yield_from_sub_generator(self):
    ann_body = [
      ast.Expr(
        value=ast.YieldFrom(
          value=ast.Call(
            func=ast.Attribute(
              value=ast.Name(id="Self", ctx=ast.Load()),
              attr="_glob_select_parts",
              ctx=ast.Load(),
            ),
            args=[
              ast.Name(id="root", ctx=ast.Load()),
              ast.Name(id="parts", ctx=ast.Load()),
              ast.Constant(value=0),
            ],
            keywords=[],
          ),
        ),
      ),
    ]
    tr = _PathTr()
    gen_name = f"Path__glob_select{GENERATOR_SUFFIX}"
    body = _desugar_generator_yield_from_to_for(
      copy.deepcopy(ann_body),
      tr,
      host_class="Path",
      current_gen=gen_name,
      ann_body=ann_body,
    )
    self.assertEqual(len(body), 1)
    self.assertIsInstance(body[0], ast.For)
    yf = _yield_from_fields(
      body, tr, host_class="Path", current_gen=gen_name, ann_body=ann_body,
    )
    self.assertEqual(yf, [])

  def test_member_coroutine_auto_registered_as_host_friend(self):
    from src.analysis.ir import ClassInfo
    from src.translator import Translator

    host_cls = ast.ClassDef(
      name="Reader",
      bases=[],
      keywords=[],
      body=[
        ast.FunctionDef(
          name="_fill",
          args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
          ),
          body=[],
          decorator_list=[],
        ),
      ],
      decorator_list=[],
    )
    coro_cls = ast.ClassDef(
      name=f"Reader__fill{COROUTINE_SUFFIX}",
      bases=[],
      keywords=[],
      body=[],
      decorator_list=[],
    )
    tr = Translator("m", "m.py", strict=False)
    tr.classes = {
      "Reader": ClassInfo(host_cls, "m"),
      coro_cls.name: ClassInfo(coro_cls, "m"),
    }

    _auto_register_member_generator_friends(tr)

    self.assertIn(coro_cls.name, tr.classes["Reader"].friend_classes)

  def test_coroutine_slice_param_hoists_as_pointer_field(self):
    cpp = self._translate(
      '''
from py2cpp import *
from py2cpp.concur.task import Task

async def fill(buf: byte[:]) -> int:
  await Task.sleep(0)
  buf[0] = 42
  return buf[0]
'''
    )
    self.assertIn("PyArray<PyByte, 0>* buf;", cpp)
    self.assertIn("this->buf = (&(buf));", cpp)
    self.assertIn("this->buf[0].__setitem__(0, PyByte(42));", cpp)

  def test_coroutine_ref_param_hoists_as_pointer_field(self):
    cpp = self._translate(
      '''
from py2cpp import *
from py2cpp.concur.task import Task

@copyable
class Box:
  value: int = 0

async def fill(box: Box @ref) -> int:
  await Task.sleep(0)
  box.value = 42
  return box.value
'''
    )
    self.assertIn("Box* box;", cpp)
    self.assertIn("this->box = (&(box));", cpp)
    self.assertIn("this->box[0].value = 42;", cpp)

  def test_coroutine_ref_param_method_await_keeps_child_coroutine_type(self):
    cpp = self._translate(
      '''
from py2cpp import *
from py2cpp.concur.task import Task

@copyable
class Reader:
  async def read(self) -> int:
    await Task.sleep(0)
    return 7

async def outer(reader: Reader @ref) -> int:
  return await reader.read()
'''
    )
    self.assertIn("Reader* reader;", cpp)
    self.assertIn("Reader_read_coroutine _yf0_it;", cpp)
    self.assertIn("((this->reader[0]).read()).__await__()", cpp)

  def test_coroutine_wrapper_await_uses_forwarded_child_type(self):
    cpp = self._translate(
      '''
from py2cpp import *

@refcount
class State:
  async def read(self) -> int:
    return 7

@copyable
class Reader:
  _state: State = new()

  def __init__(self):
    self._state = new()

  def read(self):
    return self._state.read()

async def outer(reader: Reader @ref) -> int:
  return await reader.read()
'''
    )
    self.assertIn("State_read_coroutine _yf0_it;", cpp)
    self.assertNotIn("Reader_read_coroutine _yf0_it;", cpp)

  def test_statement_await_before_value_await_does_not_skip_value_await(self):
    cpp = self._translate(
      '''
from py2cpp import *
from py2cpp.concur.task import Task

async def no_op() -> None:
  return None

async def val() -> int:
  await Task.sleep(0)
  return 3

async def outer() -> int:
  await no_op()
  x: int = await val()
  return x
'''
    )
    self.assertNotRegex(cpp, re.compile(r"continue;\\s*this->_state\\s*="))
    self.assertIn("this->g_x = __yf", cpp)


if __name__ == "__main__":
  unittest.main()
