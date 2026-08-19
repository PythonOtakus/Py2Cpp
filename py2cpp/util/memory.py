"""块状内存原语（``char[:]`` 直写）；``serde`` / ``str`` 热路径共用。

**纯 Python**：``copyBuf`` / ``loadU64Le*`` 直接复用参照实现；``str.fromBuf`` 见 ``text/str``；缓冲扩容见 ``array.reserve``。
"""
from __future__ import annotations

from ..builtins import *

from ..text import str
from ..util.span import span
from ffi.crt.string import pyiStrlen


@immutable
def strCbuf(s: str, cap: int) -> byte[:]:
  """把 ``s`` 写入长度 ``cap`` 的 ``byte[:]``（含 ``NUL``，供 ``CStr`` 形参）。"""
  buf: byte[:] = new(cap)
  s.copyToSpan(buf.view)
  return buf

@immutable
def _cstrView(p: CStr) -> span[byte]:
  """将 NUL 终止 ``CStr`` 转为不含终止符的 ``span[byte]``。"""
  if p is None:
    return span[byte]()
  addr: uintptr = cast(p)
  raw: Pointer[byte] = cast(addr)
  return new(raw, int(pyiStrlen(p)))

@immutable
def cstrSlice(p: CStr, start: int, n: int) -> str:
  """从 ``CStr`` 的字节视图拷 ``n`` 个字节为 ``str``。"""
  if n <= 0:
    return ""
  return str.fromSpan(p.view[start:start + n])

@immutable
def appendChars(buf: char[:], at: int, src: char[:], end: int) -> int:
  """把 ``src[0:end]`` 写入 ``buf[at:]``，返回新尾下标（``copyBuf`` + ``reshape``）。"""
  if end <= 0:
    return at
  need: int = at + end
  n: int = len(buf)
  if need > n:
    buf.reshape(need, n)
  for i in range(end):
    buf[at + i] = src[i]
  return need


@immutable
def copyBufRef(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """``src[:n]`` → ``dst``（纯 Python；``@native copyBuf`` 的语义参照）。"""
  if n <= 0:
    return
  for i in range(n):
    dst[i] = src[i]


def copyBuf(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """连续 ``n`` 个 ``PyChar``：``src`` → ``dst``。"""
  copyBufRef(dst, src, n)


@immutable
def loadU64LeRef(p: Pointer[char], off: int) -> uint64:
  """自 ``p+off`` 读 8 字节 little-endian（纯 Python；``@native loadU64Le`` 的语义参照）。"""
  if p is None:
    return 0
  v: uint64 = 0
  for i in range(8):
    part: uint64 = int(p[off + i]) & 0xFF
    sh: uint64 = i * 8
    v |= part << sh
  return v


@immutable
def loadU64Le(p: Pointer[char], off: int) -> uint64:
  """自 ``PyChar`` 缓冲 ``p+off`` 读 8 字节 little-endian（取各码点低 8 位）。"""
  return loadU64LeRef(p, off)


@immutable
def loadU64LeBytesRef(p: Pointer[byte], off: int) -> uint64:
  """自裸 ``byte`` 缓冲 ``p+off`` 读 8 字节（纯 Python；``@native loadU64LeBytes`` 的语义参照）。"""
  if p is None:
    return 0
  v: uint64 = 0
  for i in range(8):
    part: uint64 = int(p[off + i]) & 0xFF
    sh: uint64 = i * 8
    v |= part << sh
  return v


@immutable
def loadU64LeBytes(p: Pointer[byte], off: int) -> uint64:
  """自裸 ``byte`` 缓冲 ``p+off`` 读 8 字节 little-endian。"""
  return loadU64LeBytesRef(p, off)


@immutable
def loadU64LeAtAddress(addr: uintptr) -> uint64:
  """自 ``uintptr`` 地址读 8 字节 little-endian（``LARGE_INTEGER`` 等 FFI 对象）。"""
  p: Pointer[byte] = cast(addr)
  return loadU64LeBytes(p, 0)
