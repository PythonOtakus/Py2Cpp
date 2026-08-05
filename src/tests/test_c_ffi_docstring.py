"""``c_ffi_pyi.doxygen_to_python_docstring`` / ``_emit_docstring_lines``."""
from __future__ import annotations

import unittest

from src.tools.c_ffi_pyi import (
  _emit_docstring_lines,
  doxygen_to_python_docstring,
)


class TestCFfiDocstring(unittest.TestCase):

  def test_param_return_google(self) -> None:
    raw = """\
/*!
 * @brief Sets the close flag.
 * @param window The window.
 * @param value The value.
 * @return None.
 */
"""
    doc = doxygen_to_python_docstring(raw)
    assert doc is not None
    self.assertIn("Sets the close flag.", doc)
    self.assertIn("Args:", doc)
    self.assertIn("  window: The window.", doc)
    self.assertIn("Returns:", doc)

  def test_ref_stripped(self) -> None:
    raw = "/*! See @ref glfwCreateWindow and [docs](@ref GLFW). */"
    doc = doxygen_to_python_docstring(raw)
    assert doc is not None
    self.assertNotIn("@ref", doc)
    self.assertIn("glfwCreateWindow", doc)
    self.assertIn("docs", doc)

  def test_param_in_indented(self) -> None:
    """GLFW 风格：`` *  @param[in]`` 行首有空格。"""
    raw = """\
/*! @brief Sets the close flag.
 *
 *  Longer description here.
 *
 *  @param[in] window The window whose flag to change.
 *  @param[in] value The new value.
 *
 *  @errors Possible errors include @ref GLFW_NOT_INITIALIZED.
 *
 *  @thread_safety This function may be called from any thread.
 *
 *  @sa @ref window_close
 *
 *  @since Added in version 3.0.
 */
"""
    doc = doxygen_to_python_docstring(raw)
    assert doc is not None
    self.assertIn("Args:", doc)
    self.assertIn("  window: The window whose flag to change.", doc)
    self.assertIn("  value: The new value.", doc)
    self.assertIn("Errors:", doc)
    self.assertIn("Thread safety:", doc)
    self.assertIn("See also:", doc)
    self.assertIn("Since:", doc)
    self.assertNotIn("@param", doc)
    self.assertNotIn("@ref", doc)

  def test_emit_def_style(self) -> None:
    lines = _emit_docstring_lines("One line.")
    self.assertEqual(lines, ['  """One line."""'])
    multi = _emit_docstring_lines("A\n\nB")
    self.assertEqual(multi[0], '  """')
    self.assertEqual(multi[-1], '  """')
    self.assertIn("  A", multi)
    self.assertIn("  B", multi)

  def test_empty(self) -> None:
    self.assertIsNone(doxygen_to_python_docstring(None))
    self.assertEqual(_emit_docstring_lines(""), [])


if __name__ == "__main__":
  unittest.main()
