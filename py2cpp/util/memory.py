"""块状内存原语（``char[:]`` 直写）；``serde`` / ``str`` 热路径共用。

**纯 Python**：``copyArray`` / ``loadU64Le*`` 直接复用参照实现；``str.fromArray`` 见 ``text/str``；缓冲扩容见 ``array.reserve``。
"""
from __future__ import annotations

from ..builtins import *

from ..text import str
from ..util.span import span
from ffi.crt.string import pyiStrlen, pyiWcslen


@immutable
def _cstrView(p: utf8ptr) -> span[byte]:
  """将 NUL 终止 ``utf8ptr`` 转为不含终止符的 ``span[byte]``。"""
  if p is None:
    return span[byte]()
  addr: uintptr = cast(p)
  raw: Pointer[byte] = cast(addr)
  return new(raw, int(pyiStrlen(p)))


@immutable
def _cwstrView(p: utf16ptr) -> span[uint16]:
  """将 NUL 终止 utf16ptr 转为不含终止符的 UTF-16 span。"""
  if p is None:
    return span[uint16]()
  addr: uintptr = cast(p)
  raw: Pointer[uint16] = cast(addr)
  return new(raw, int(pyiWcslen(p)))

@immutable
def appendChars(buf: char[:], at: int, src: char[:], end: int = int.Max) -> int:
  """把 ``src[0:end]`` 写入 ``buf[at:]``，返回新尾下标（``copyArray`` + ``reshape``）。"""
  if end > len(src):
    end = len(src)
  if end == len(src):
    for i in range(end):
      if src[i] == 0:
        end = i
        break
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
def copyArrayRef(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """``src[:n]`` → ``dst``（纯 Python；``@native copyArray`` 的语义参照）。"""
  if n <= 0:
    return
  for i in range(n):
    dst[i] = src[i]


def copyArray(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """连续 ``n`` 个 ``PyChar``：``src`` → ``dst``。"""
  copyArrayRef(dst, src, n)


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
