"""``async def`` 内 ``yield from`` 翻译期拒绝（Python 3.13）。"""
from __future__ import annotations

import unittest

from src.passes.coroutine_desugar import check_yield_from_in_async_def
from src.passes.generators import expand_generators
from src.translation_error import TranslationError
from src.translator import Translator


def _check_body(body: str, *, run_expand: bool = False) -> Translator:
  tr = Translator("mod", "mod.py")
  tr.entry_module_path = "mod"
  tr._parse_modules([("mod", f"from py2cpp import *\n\n{body}")])
  check_yield_from_in_async_def(tr)
  if run_expand:
    expand_generators(tr)
  return tr


class YieldFromAsyncCheckTests(unittest.TestCase):
  def test_rejects_yield_from_in_async_generator(self) -> None:
    with self.assertRaises(TranslationError) as ctx:
      _check_body(
        """
async def inner() -> AsyncGenerator[int, None]:
  yield 1

async def outer() -> AsyncGenerator[int, None]:
  yield from inner()
""",
      )
    self.assertIn("yield from", str(ctx.exception))

  def test_allows_await_desugar_after_check(self) -> None:
    _check_body(
      """
async def foo() -> int:
  return 1

async def bar() -> int:
  return await foo()
""",
      run_expand=True,
    )

  def test_allows_yield_from_in_nested_sync_def(self) -> None:
    _check_body(
      """
async def outer() -> AsyncGenerator[int, None]:
  def inner():
    xs: list[int] = [1, 2]
    yield from xs
  yield 1
""",
      run_expand=True,
    )


if __name__ == "__main__":
  unittest.main()
