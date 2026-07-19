"""块状内存原语（``memcpy`` / ``char[:]`` 直写）；``serde`` / ``str`` 热路径共用。

**严格原子化**：``copy_buf`` / ``load_u64_le`` / ``load_u64_le_bytes`` 标 ``@native``（C++ 叶子加速）；
``str.from_buf`` 见 ``text/str``；``str.from_span`` / ``copy_from_span`` 为纯 Python + ``copy_buf`` 叶子；缓冲扩容见 ``array.reserve``。
"""
from __future__ import annotations

from ..builtins import *


@immutable
def append_chars(buf: char[:], at: int, src: char[:], end: int) -> int:
  """把 ``src[0:end]`` 写入 ``buf[at:]``，返回新尾下标（``copy_buf`` + ``reshape``）。"""
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
def copy_buf_ref(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """``src[:n]`` → ``dst``（纯 Python；``@native copy_buf`` 的语义参照）。"""
  if n <= 0:
    return
  for i in range(n):
    dst[i] = src[i]


@native
def copy_buf(dst: Pointer[char], src: Pointer[char], n: int) -> None:
  """连续 ``n`` 个 ``PyChar``：``src`` → ``dst``（``memcpy``）。"""
  ...


@immutable
def load_u64_le_ref(p: Pointer[char], off: int) -> uint64:
  """自 ``p+off`` 读 8 字节 little-endian（纯 Python；``@native load_u64_le`` 的语义参照）。"""
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
def load_u64_le(p: Pointer[char], off: int) -> uint64:
  """自 ``PyChar`` 缓冲 ``p+off`` 读 8 字节 little-endian（取各码点低 8 位）。"""
  ...


@immutable
def load_u64_le_bytes_ref(p: Pointer[byte], off: int) -> uint64:
  """自裸 ``byte`` 缓冲 ``p+off`` 读 8 字节（纯 Python；``@native load_u64_le_bytes`` 的语义参照）。"""
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
def load_u64_le_bytes(p: Pointer[byte], off: int) -> uint64:
  """自裸 ``byte`` 缓冲 ``p+off`` 读 8 字节 little-endian（``memcpy``）。"""
  ...
