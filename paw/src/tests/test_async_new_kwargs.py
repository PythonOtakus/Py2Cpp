"""async 状态机中的 ``new.xxx`` 上下文与 ``**kwargs`` 转发。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translator import Translator


class AsyncNewKwargsTests(unittest.TestCase):
  def _translate(self, src: str, *, debug: bool = False) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(src, encoding="utf-8")
      _h, cpp_path = Translator.translate_file(
        str(py), output_dir=str(out), include_stdlib=True, debug=debug,
      )
      text = cpp_path.read_text(encoding="utf-8")
      inl = cpp_path.with_suffix(".inl")
      if inl.is_file():
        text += inl.read_text(encoding="utf-8")
      return text

  def test_await_new_static_and_async_return_new_static(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Sock:
  @staticmethod
  def from_socket(fd: int) -> Self:
    out: Self = new()
    return out

  @staticmethod
  async def open(fd: int) -> Self:
    return new.from_socket(fd)

async def use() -> Sock:
  s: Sock = await new.open(1)
  return new.from_socket(2)
'''
    )
    self.assertIn("Sock::open", cpp)
    self.assertIn("Sock::from_socket", cpp)
    self.assertNotIn("new.open", cpp)
    self.assertNotIn("new.from_socket", cpp)

  def test_async_kwargs_forward_inside_await(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Options:
  timeout: float = 0.0

@copyable
class Client:
  async def request(self, method: str, url: str, **options: Options) -> int:
    return 7

  async def get(self, url: str, **options: Options) -> int:
    return await self.request("GET", url, **options)
'''
    )
    self.assertIn("request", cpp)
    self.assertNotIn("**options", cpp)

  def test_await_async_method_on_host_field_keeps_coroutine_type(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Sock:
  async def sendAll(self) -> None:
    return None

@copyable
class Writer:
  sock: Sock = new()

  async def write(self) -> int:
    await self.sock.sendAll()
    return 1
'''
    )
    self.assertNotIn("PyInt __seq", cpp)
    self.assertIn("Sock_sendAll_coroutine __seq", cpp)

  def test_debug_wrap_ref_return_keeps_reference(self):
    cpp = self._translate(
      '''
from py2cpp import *

@copyable
class Box:
  value: int = 0

g_box: Box = new()

def get_box() -> Box @ref:
  return g_box

def use() -> int:
  b: Box @ref = get_box()
  b.value = 9
  return get_box().value
''',
      debug=True,
    )
    self.assertRegex(cpp, r'_py2cpp_debug_wrap\("[^"]*mod\.py:\d+ get_box\(\)", ::mod::get_box\(\)\)')
    self.assertNotIn('_py2cpp_debug_wrap_val', cpp.split("PyInt use()", 1)[1])

  def test_wrapper_infers_internal_coroutine_return_type(self):
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
'''
    )
    self.assertIn("State_read_coroutine mod::Reader::read()", cpp)
    self.assertNotIn("Reader_read_coroutine mod::Reader::read()", cpp)


if __name__ == "__main__":
  unittest.main()
