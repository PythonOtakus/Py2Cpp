"""``@native`` 类体字段注解（如 ``_sock: uint64``）须写入类头声明。"""
import unittest
from pathlib import Path

from src.translator import Translator


class TestNativeClassFields(unittest.TestCase):
  def test_tcp_socket_uint64_bool_members_in_header(self):
    root = Path(__file__).resolve().parents[2]
    src = root / "py2cpp" / "web" / "socket.py"
    out = root / "generated"
    Translator.translate_file(
      str(src),
      output_dir=str(out),
      include_stdlib=False,
      emit_main=False,
      strict=False,
    )
    header = (out / "runtime" / "py2cpp" / "web" / "socket.h").read_text(encoding="utf-8")
    self.assertIn("PyUInt64 _sock", header)
    self.assertIn("PyBool _closed", header)
    self.assertNotIn("web_tcp_socket_tail", header)

  def test_text_io_wrapper_uintptr_bool_members_in_header(self):
    root = Path(__file__).resolve().parents[2]
    src = root / "py2cpp" / "io" / "__init__.py"
    out = root / "generated"
    Translator.translate_file(
      str(src),
      output_dir=str(out),
      include_stdlib=True,
      emit_main=False,
      strict=False,
    )
    header = (out / "runtime" / "py2cpp" / "io.h").read_text(encoding="utf-8")
    self.assertIn("PyUPtr _fp", header)
    self.assertIn("PyBool _closed", header)
    self.assertNotIn("io_textiowrapper_tail", header)
    self.assertNotIn("FILE* _fp", header)


if __name__ == "__main__":
  unittest.main()
