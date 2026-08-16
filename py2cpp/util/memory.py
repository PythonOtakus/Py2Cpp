"""块状内存原语（``memcpy`` / ``char[:]`` 直写）；``serde`` / ``str`` 热路径共用。

**严格原子化**：``copyBuf`` / ``loadU64Le`` / ``loadU64LeBytes`` 标 ``@native``（C++ 叶子加速）；
``str.fromBuf`` 见 ``text/str``；``str.fromSpan`` / ``copyFromSpan`` 为纯 Python + ``copyBuf`` 叶子；缓冲扩容见 ``array.reserve``。
"""
from __future__ import annotations

from ..builtins import *


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


@native
def copyBuf(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """连续 ``n`` 个 ``PyChar``：``src`` → ``dst``（``memcpy``）。"""
  ...


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


@native
@immutable
def loadU64Le(p: Pointer[char], off: int) -> uint64:
  """自 ``PyChar`` 缓冲 ``p+off`` 读 8 字节 little-endian（取各码点低 8 位）。"""
  ...


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


@native
@immutable
def loadU64LeBytes(p: Pointer[byte], off: int) -> uint64:
  """自裸 ``byte`` 缓冲 ``p+off`` 读 8 字节 little-endian（``memcpy``）。"""
  ...
