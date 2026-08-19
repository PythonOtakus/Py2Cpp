"""C 串缓冲：``str`` ↔ ``CStr`` / ``byte[:]``（``ffi`` 路径与 CRT 共用）。"""
from ..builtins import *
from ..text import str


@immutable
def strCbuf(s: str, cap: int) -> byte[:]:
  """把 ``s`` 写入长度 ``cap`` 的 ``byte[:]``（含 ``NUL``，供 ``CStr`` 形参）。"""
  buf: byte[:] = new(cap)
  s.copyToSpan(buf.view)
  return buf


@immutable
def cstrLen(p: CStr) -> int:
  """``strlen`` 子集（上限 4096）。"""
  if p is None:
    return 0
  for i in range(4096):
    if int(p[i]) == 0:
      return i
  return 4096


@immutable
def cstrSlice(p: CStr, start: int, n: int) -> str:
  """从 ``CStr`` 拷 ``n`` 个字节为 ``str``。"""
  if n <= 0:
    return ""
  buf: char[:] = new(n)
  for i in range(n):
    buf[i] = char(p[start + i])
  return str.fromBuf(buf, n)
