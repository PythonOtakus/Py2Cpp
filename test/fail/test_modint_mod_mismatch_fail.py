"""负向：不同模数的 ``ModInt`` 相加应 MSVC 编译失败。"""
from py2cpp import *
from py2cpp.numeric.modint import ModInt


def main() -> int:
  a: ModInt[int, 7] = new(1)
  b: ModInt[int, 11] = new(2)
  c: ModInt[int, 7] = a + b
  return int(c)
