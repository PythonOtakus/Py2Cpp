"""负向：``async def`` 内 ``yield from``（Python 3.13 ``SyntaxError``）。"""
from py2cpp import *


async def inner() -> AsyncGenerator[int, None]:
  yield 1


async def outer() -> AsyncGenerator[int, None]:
  yield from inner()


def main() -> int:
  return 0
