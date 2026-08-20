"""``str`` / ``bytes`` 共享序列逻辑（``StringMixin[T]``）。

宿主须声明 ``_data: T[:]`` 或 ``_data: array[T, StackLength]``（``StackLength>0`` 时 ``array`` 内联 SSO；``str`` 用 ``StringMixin._SsoCap``）；
``str(StringMixin[char])``、``bytes(StringMixin[byte])``。
注解 ``Self`` 的空序列用 ``new()``（S06b）；``char[:]``/``byte[:]`` 缓冲见编码规范 §2.1。
"""
from ..builtins import *
from ..core.protocols import GeneratorType
from ..core.exceptions import ValueError
from ..util.dict import dict
from ..util.list import list
from ..util.slice import slice
from ..util.span import span


@mixin
class StringMixin[Host: oneof[char, byte]]:
  """不可变堆序列（码点/字节）共享核心。"""

  _SsoCap: int @const = 22

  @staticmethod
  def _append(buf: Host[:], at: int, c: Host) -> int:
    buf[at] = c
    return at + 1

  def _didChangeData(self) -> None:
    """宿主在缓冲写入后更新派生状态（``str`` 的哈希缓存等）。"""
    pass

  def copyTo(self, buf: Host[:], at: int = 0) -> int:
    """把序列写入 ``buf[at:]``，返回新尾下标。"""
    size: int = len(self)
    if size == 0:
      return at
    end: int = at + size
    if end > len(buf):
      buf.reshape(end, len(buf))
    for i in range(size):
      buf[at + i] = self._data[i]
    return end

  def copySliceTo(
    self,
    buf: Host[:],
    at: int = 0,
    start: int = 0,
    end: int = int.Max,
  ) -> int:
    """``self[start:end]`` 写入 ``buf[at:]``，返回新尾下标。"""
    size: int = len(self)
    if start < 0:
      start = 0
    if start > size:
      start = size
    if end > size:
      end = size
    if end < start:
      end = start
    count: int = end - start
    if count <= 0:
      return at
    nextAt: int = at + count
    buf.reserve(nextAt)
    for i in range(count):
      buf[at + i] = self._data[start + i]
    return nextAt

  @staticmethod
  @immutable
  def concat(parts: list[Self]) -> Self:
    empty: Self = new()
    return empty.join(parts)

  def replaceSlice(
    self,
    repl: Self,
    start: int = 0,
    end: int = int.Max,
  ) -> Self:
    """单次分配拼接 ``self[:start] + repl + self[end:]``。"""
    size: int = len(self)
    if start < 0:
      start = 0
    if start > size:
      start = size
    if end > size:
      end = size
    if end < start:
      end = start
    if start == 0 and end == size:
      return repl
    tail: int = size - end
    total: int = start + len(repl) + tail
    if total == 0:
      return new()
    if tail == 0 and not repl and start == size:
      return self
    data: Host[:] = new(total)
    at: int = 0
    for i in range(start):
      data[at + i] = self._data[i]
    at += start
    for i in range(len(repl)):
      data[at + i] = repl._data[i]
    at += len(repl)
    for i in range(tail):
      data[at + i] = self._data[end + i]
    return new(data)

  @staticmethod
  @immutable
  def fromArray(buf: Host[:], end: int = int.Max) -> Self:
    """由 ``buf[:end]`` 拷贝构造。"""
    end = Self._normEnd(len(buf), end)
    return Self.fromSpan(buf.view[:end])

  @staticmethod
  @immutable
  def fromArrayRef(buf: Host[:], end: int = int.Max) -> Self:
    """``fromArray`` 的纯 Python 语义参照。"""
    return Self.fromArray(buf, end)

  @staticmethod
  @immutable
  def fromSpan(seg: span[Host]) -> Self:
    """由 ``span[Host]`` 拷贝构造。"""
    out: Self = new()
    out.copyFromSpan(seg)
    return out

  def copyFromSpan(self, seg: span[Host]) -> None:
    """将 ``span[Host]`` 写入已有序列。"""
    size: int = len(seg)
    if len(self._data) != size:
      self._data.reshape(size, 0)
    for i in range(size):
      self._data[i] = seg[i]
    self._didChangeData()

  @immutable
  def copyToSpan(self, dest: span[Host]) -> None:
    """把原始元素写入 ``dest`` 并以零值收尾。"""
    cap: int = len(dest)
    if cap <= 0:
      return
    size: int = len(self)
    limit: int = cap - 1
    if size < limit:
      limit = size
    for i in range(limit):
      dest[i] = self._data[i]
    dest[limit] = cast[Host](0)

  @immutable
  def toArray(self) -> Host[:]:
    """返回原始元素的独立数组副本。"""
    size: int = len(self)
    data: Host[:] = new(size)
    for i in range(size):
      data[i] = self._data[i]
    return data

  def adoptSpan(self, seg: span[Host]) -> None:
    """接管 ``span[Host]`` 的底层缓冲。"""
    self._data.adoptSpan(seg)
    self._didChangeData()

  @property
  @immutable
  def view(self) -> span[Host]:
    """只读原始元素视图。"""
    return self._data.view

  @immutable
  @staticmethod
  def _normEnd(n: int, end: int) -> int:
    if end == int.Max:
      return n
    if end < 0:
      end += n
    if end < 0:
      return 0
    if end > n:
      return n
    return end

  @immutable
  @staticmethod
  def _normStart(n: int, start: int) -> int:
    if start < 0:
      start += n
    if start < 0:
      return 0
    if start > n:
      return n
    return start

  @immutable
  @staticmethod
  def _kmpBuildLps(sub: Self, subn: int) -> int[:]:
    """KMP 前缀函数表（长度 ``subn``）。"""
    lps: int[:] = new(subn)
    length: int = 0
    k: int = 1
    lps[0] = 0
    while k < subn:
      if sub._data[k] == sub._data[length]:
        length += 1
        lps[k] = length
        k += 1
      elif length > 0:
        length = lps[length - 1]
      else:
        lps[k] = 0
        k += 1
    return lps

  @immutable
  def _findSubForwardKmp(self, sub: Self, i: int, j: int, subn: int) -> int:
    if subn == 1:
      c0: Host = sub._data[0]
      for k in range(i, j):
        if self._data[k] == c0:
          return k
      return -1
    lps: int[:] = Self._kmpBuildLps(sub, subn)
    pat: int = 0
    pos: int = i
    while pos < j:
      if self._data[pos] == sub._data[pat]:
        pos += 1
        pat += 1
        if pat == subn:
          return pos - subn
      elif pat > 0:
        pat = lps[pat - 1]
      else:
        pos += 1
    return -1

  @immutable
  def _findSubBackwardKmp(self, sub: Self, i: int, j: int, subn: int) -> int:
    if subn == 1:
      c0: Host = sub._data[0]
      for k in range(j - 1, i - 1, -1):
        if self._data[k] == c0:
          return k
      return -1
    lps: int[:] = Self._kmpBuildLps(sub, subn)
    pat: int = 0
    pos: int = i
    last: int = -1
    while pos < j:
      if self._data[pos] == sub._data[pat]:
        pos += 1
        pat += 1
        if pat == subn:
          last = pos - subn
          pat = lps[pat - 1]
      elif pat > 0:
        pat = lps[pat - 1]
      else:
        pos += 1
    return last

  @immutable
  def _sub(self, start: int, end: int) -> Self:
    n: int = len(self)
    i: int = Self._normStart(n, start)
    j: int = Self._normEnd(n, end)
    if j < i:
      j = i
    m: int = j - i
    buf: Host[:] = new(m)
    for k in range(m):
      buf[k] = self._data[i + k]
    return new(buf)

  @immutable
  def _compare(self, other: Self) -> int:
    """按元素逐字比较（与 ``list`` 字典序一致）。"""
    na: int = len(self._data)
    nb: int = len(other._data)
    lim: int = na
    if nb < lim:
      lim = nb
    for i in range(lim):
      if self._data[i] < other._data[i]:
        return -1
      if self._data[i] > other._data[i]:
        return 1
    if na < nb:
      return -1
    if na > nb:
      return 1
    return 0

  @immutable
  def __len__(self) -> int:
    return len(self._data)

  @immutable
  def __bool__(self) -> bool:
    return len(self._data) > 0

  @immutable
  @overload
  def __getitem__(self, index: int) -> Host:
    if index < 0:
      index = len(self._data) + index
    return self._data[index]

  @immutable
  @overload
  def __getitem__(self, index: slice[int, int]) -> Self:
    n: int = len(self)
    start: int = 0
    stop: int = 0
    step: int = 0
    start, stop, step = index.indices(n)
    if step > 0:
      if start >= stop:
        return new()
      cnt: int = (stop - start + step - 1) // step
      buf: Host[:] = new(cnt)
      for at in range(cnt):
        buf[at] = self._data[start + at * step]
      return new(buf)
    if start <= stop:
      return new()
    cnt: int = (start - stop - step - 1) // (-step)
    buf: Host[:] = new(cnt)
    for at in range(cnt):
      buf[at] = self._data[start + at * step]
    return new(buf)

  @immutable
  def __contains__(self, sub: Self) -> bool:
    return self.find(sub) >= 0

  @immutable
  def __add__(self, other: Self) -> Self:
    n: int = len(self._data)
    m: int = len(other._data)
    buf: Host[:] = new(n + m)
    for i in range(n):
      buf[i] = self._data[i]
    for j in range(m):
      buf[n + j] = other._data[j]
    return new(buf)

  @immutable
  def __mul__(self, n: int) -> Self:
    if n <= 0:
      return new()
    unit: int = len(self._data)
    total: int = unit * n
    buf: Host[:] = new(total)
    at: int = 0
    for _ in range(n):
      for i in range(unit):
        buf[at] = self._data[i]
        at += 1
    return new(buf)

  @immutable
  def __rmul__(self, n: int) -> Self:
    return self * n

  @immutable
  def __lt__(self, other: Self) -> bool:
    return self._compare(other) < 0

  @immutable
  def __le__(self, other: Self) -> bool:
    return self._compare(other) <= 0

  @immutable
  def __gt__(self, other: Self) -> bool:
    return self._compare(other) > 0

  @immutable
  def __ge__(self, other: Self) -> bool:
    return self._compare(other) >= 0

  @immutable
  def find(self, sub: Self, start: int = 0, end: int = int.Max) -> int:
    n: int = len(self)
    i: int = Self._normStart(n, start)
    j: int = Self._normEnd(n, end)
    subn: int = len(sub)
    if subn == 0:
      return i
    if subn > j - i:
      return -1
    return self._findSubForwardKmp(sub, i, j, subn)

  @immutable
  def index(self, sub: Self, start: int = 0, end: int = int.Max) -> int:
    pos: int = self.find(sub, start, end)
    if pos < 0:
      raise ValueError("substring not found")
    return pos

  @immutable
  def rfind(self, sub: Self, start: int = 0, end: int = int.Max) -> int:
    n: int = len(self)
    i: int = Self._normStart(n, start)
    j: int = Self._normEnd(n, end)
    subn: int = len(sub)
    if subn == 0:
      return j
    if subn > j - i:
      return -1
    return self._findSubBackwardKmp(sub, i, j, subn)

  @immutable
  def rindex(self, sub: Self, start: int = 0, end: int = int.Max) -> int:
    pos: int = self.rfind(sub, start, end)
    if pos < 0:
      raise ValueError("substring not found")
    return pos

  @immutable
  def count(self, sub: Self, start: int = 0, end: int = int.Max) -> int:
    n: int = len(self)
    i: int = Self._normStart(n, start)
    j: int = Self._normEnd(n, end)
    subn: int = len(sub)
    if subn == 0:
      if j < i:
        return 0
      return (j - i) + 1
    cnt: int = 0
    pos: int = i
    while pos <= j - subn:
      at: int = self.find(sub, pos, j)
      if at < 0:
        break
      cnt += 1
      pos = at + subn
    return cnt

  @immutable
  @overload
  def startsWith(self, prefix: Self, start: int = 0, end: int = int.Max) -> bool:
    sub: Self = self._sub(start, end)
    subn: int = len(sub)
    pren: int = len(prefix)
    if pren > subn:
      return False
    for i in range(pren):
      if sub._data[i] != prefix._data[i]:
        return False
    return True

  @immutable
  @overload
  def startsWith(self, prefix: Host[:], start: int = 0, end: int = int.Max) -> bool:
    sub: Self = self._sub(start, end)
    subn: int = len(sub)
    pren: int = len(prefix)
    if pren > subn:
      return False
    for i in range(pren):
      if sub._data[i] != prefix[i]:
        return False
    return True

  @immutable
  @overload
  def startsWith(self, prefixes: list[Self], start: int = 0, end: int = int.Max) -> bool:
    cnt: int = len(prefixes)
    for i in range(cnt):
      if self.startsWith(prefixes[i], start, end):
        return True
    return False

  @immutable
  @overload
  def startsWith(self, prefixes: Self[:], start: int = 0, end: int = int.Max) -> bool:
    cnt: int = len(prefixes)
    for i in range(cnt):
      if self.startsWith(prefixes[i], start, end):
        return True
    return False

  @immutable
  @overload
  def endsWith(self, suffix: Self, start: int = 0, end: int = int.Max) -> bool:
    sub: Self = self._sub(start, end)
    subn: int = len(sub)
    sufn: int = len(suffix)
    if sufn > subn:
      return False
    off: int = subn - sufn
    for i in range(sufn):
      if sub._data[off + i] != suffix._data[i]:
        return False
    return True

  @immutable
  @overload
  def endsWith(self, suffix: Host[:], start: int = 0, end: int = int.Max) -> bool:
    sub: Self = self._sub(start, end)
    subn: int = len(sub)
    sufn: int = len(suffix)
    if sufn > subn:
      return False
    off: int = subn - sufn
    for i in range(sufn):
      if sub._data[off + i] != suffix[i]:
        return False
    return True

  @immutable
  @overload
  def endsWith(self, suffixes: list[Self], start: int = 0, end: int = int.Max) -> bool:
    cnt: int = len(suffixes)
    for i in range(cnt):
      if self.endsWith(suffixes[i], start, end):
        return True
    return False

  @immutable
  @overload
  def endsWith(self, suffixes: Self[:], start: int = 0, end: int = int.Max) -> bool:
    cnt: int = len(suffixes)
    for i in range(cnt):
      if self.endsWith(suffixes[i], start, end):
        return True
    return False

  @immutable
  def _globNormcase(self) -> Self:
    """``fnmatch`` 大小写规范化（``/``→``\\`` + ASCII ``lower``，对齐 ``Path`` 内部的 ``normCase`` 等价规范化）。"""
    n: int = len(self)
    if n == 0:
      return self
    buf: Host[:] = new(n)
    alt: Host = ord("/")
    sep: Host = ord("\\")
    for i in range(n):
      c: Host = self._data[i]
      if c == alt:
        buf[i] = sep
      else:
        buf[i] = Self._toLowerChar(c)
    return new(buf)

  @immutable
  def _globClassBodyContains(self, c: Host, start: int, end: int) -> bool:
    hasDash: bool = False
    for i in range(start, end):
      if self._data[i] == ord("-"):
        hasDash = True
        break
    if not hasDash:
      for i in range(start, end):
        if c == self._data[i]:
          return True
      return False
    chunks: list[Self] = []
    i: int = start
    k: int = start + 1
    while True:
      dash: int = self.find(Self._fromCode(ord("-")), k, end)
      if dash < 0:
        tail: Self = self._sub(i, end)
        if tail:
          chunks.append(tail)
        elif chunks:
          last: Self = chunks[-1]
          chunks[-1] = last + Self._fromCode(ord("-"))
        break
      chunks.append(self._sub(i, dash))
      i = dash + 1
      k = dash + 3
    cnt: int = len(chunks)
    for j in range(cnt):
      chunk: Self = chunks[j]
      if chunk._globClassChunkContains(c):
        return True
    return False

  @immutable
  def _globClassChunkContains(self, c: Host) -> bool:
    cn: int = len(self)
    match cn:
      case 0:
        return False
      case 1:
        return c == self._data[0]
      case 2:
        lo: Host = self._data[0]
        hi: Host = self._data[1]
        if lo <= hi:
          return lo <= c and c <= hi
        if c == lo:
          return True
        return c == hi
      case _:
        for i in range(cn):
          if c == self._data[i]:
            return True
        return False

  @immutable
  def _globClassContains(self, c: Host) -> bool:
    bn: int = len(self)
    neg: bool = False
    start: int = 0
    if bn > 0 and self._data[0] == ord("!"):
      neg = True
      start = 1
    matched: bool = True
    if start < bn:
      matched = self._globClassBodyContains(c, start, bn)
    if neg:
      return not matched
    return matched

  @immutable
  def _globMatchBracket(self, c: Host, pi: int) -> int:
    """匹配 ``[…]``；成功返回 pattern 新下标，失败返回 ``-1``。"""
    pn: int = len(self)
    j: int = pi + 1
    if j < pn and self._data[j] == ord("!"):
      j += 1
    if j < pn and self._data[j] == ord("]"):
      j += 1
    close: int = j
    while close < pn and self._data[close] != ord("]"):
      close += 1
    if close >= pn:
      if c == self._data[pi]:
        return pi + 1
      return -1
    body: Self = self._sub(pi + 1, close)
    if not body._globClassContains(c):
      return -1
    return close + 1

  @immutable
  def _globMatchAt(self, pat: Self, ni: int, pi: int) -> bool:
    nn: int = len(self)
    pn: int = len(pat)
    while True:
      if pi >= pn:
        return ni >= nn
      starC: Host = pat._data[pi]
      if starC == ord("*"):
        pi += 1
        while pi < pn and pat._data[pi] == starC:
          pi += 1
        if pi >= pn:
          return True
        for trial in range(ni, nn + 1):
          if self._globMatchAt(pat, trial, pi):
            return True
        return False
      if ni >= nn:
        return False
      pc: Host = pat._data[pi]
      if pc == ord("?"):
        ni += 1
        pi += 1
        continue
      if pc == ord("["):
        nextPi: int = pat._globMatchBracket(self._data[ni], pi)
        if nextPi < 0:
          return False
        ni += 1
        pi = nextPi
        continue
      if self._data[ni] != pat._data[pi]:
        return False
      ni += 1
      pi += 1

  @immutable
  def _globMatch(self, pat: Self) -> bool:
    return self._globMatchAt(pat, 0, 0)

  @immutable
  def glob(self, pattern: Self, ignoreCase: bool = True) -> bool:
    """Shell 通配匹配（语义对齐 ``fnmatch`` / ``fnmatchcase``；非 ``pathlib.Path.glob``）。"""
    name: Self = self
    pat: Self = pattern
    if ignoreCase:
      name = self._globNormcase()
      pat = pattern._globNormcase()
    return name._globMatch(pat)

  @immutable
  @staticmethod
  def _fromCode(code: int) -> Self:
    """单码点/单字节子串（``find(r\"\\n\")`` 等）；勿 ``Self(ord(...))``（``bytes(n)`` 为定长构造）。"""
    buf: Host[:] = new(1)
    buf[0] = code
    return new(buf)

  @immutable
  @staticmethod
  def _reverseSelfList(items: list[Self]) -> list[Self]:
    out: list[Self] = []
    cnt: int = len(items)
    for i in range(cnt):
      out.append(items[cnt - 1 - i])
    return out

  @immutable
  def join(self, iterable: list[Self]) -> Self:
    total: int = 0
    sepN: int = len(self)
    cnt: int = len(iterable)
    for i in range(cnt):
      total += len(iterable[i])
    if cnt > 1:
      total += sepN * (cnt - 1)
    buf: Host[:] = new(total)
    at: int = 0
    for i in range(cnt):
      part: Self = iterable[i]
      pn: int = len(part)
      for j in range(pn):
        buf[at] = part._data[j]
        at += 1
      if i + 1 < cnt:
        for j in range(sepN):
          buf[at] = self._data[j]
          at += 1
    return new(buf)

  @immutable
  def removePrefix(self, prefix: Self) -> Self:
    pn: int = len(prefix)
    if pn == 0:
      return self
    if not self.startsWith(prefix):
      return self
    return self._sub(pn, len(self))

  @immutable
  def removeSuffix(self, suffix: Self) -> Self:
    sn: int = len(suffix)
    if sn == 0:
      return self
    if not self.endsWith(suffix):
      return self
    return self._sub(0, len(self) - sn)

  @immutable
  def partition(self, sep: Self) -> (Self, Self, Self):
    pos: int = self.find(sep)
    if pos < 0:
      z: Self = new()
      return (self, z, z)
    before: Self = self._sub(0, pos)
    after: Self = self._sub(pos + len(sep), len(self))
    return (before, sep, after)

  @immutable
  def rpartition(self, sep: Self) -> (Self, Self, Self):
    pos: int = self.rfind(sep)
    if pos < 0:
      z: Self = new()
      return (z, z, self)
    before: Self = self._sub(0, pos)
    after: Self = self._sub(pos + len(sep), len(self))
    return (before, sep, after)

  @immutable
  def replace(self, old: Self, new: Self, count: int = int.Max) -> Self:
    n: int = len(self)
    oldn: int = len(old)
    if oldn == 0:
      return self
    if count < 0:
      raise ValueError("count must be non-negative")
    limit: int = count
    out: list[Self] = []
    start: int = 0
    replaced: int = 0
    while start <= n - oldn:
      if replaced >= limit:
        break
      pos: int = self.find(old, start, n)
      if pos < 0:
        break
      if pos > start:
        out.append(self._sub(start, pos))
      out.append(new)
      replaced += 1
      start = pos + oldn
    if start < n:
      out.append(self._sub(start, n))
    if not out:
      return self
    result: Self = out[0]
    for j in range(1, len(out)):
      result += out[j]
    return result

  @immutable
  @overload
  def lstrip(self) -> Self:
    return self.lstrip(Self())

  @immutable
  @overload
  def lstrip(self, chars: Self) -> Self:
    n: int = len(self)
    i: int = 0
    if not chars:
      while i < n and Self._isFieldWhitespace(self._data[i]):
        i += 1
    else:
      while i < n and Self(self._data[i]) in chars:
        i += 1
    return self._sub(i, n)

  @immutable
  @overload
  def rstrip(self) -> Self:
    return self.rstrip(Self())

  @immutable
  @overload
  def rstrip(self, chars: Self) -> Self:
    n: int = len(self)
    j: int = n
    if not chars:
      while j > 0 and Self._isFieldWhitespace(self._data[j - 1]):
        j -= 1
    else:
      while j > 0 and Self(self._data[j - 1]) in chars:
        j -= 1
    return self._sub(0, j)

  @immutable
  @overload
  def strip(self) -> Self:
    return self.strip(Self())

  @immutable
  @overload
  def strip(self, chars: Self) -> Self:
    return self.lstrip(chars).rstrip(chars)

  @immutable
  def stripLines(self, minIndent: int = 0) -> Self:
    """去掉首尾空行与公共前导空格缩进，再为每行补 ``minIndent`` 个空格。"""
    if minIndent < 0:
      raise ValueError("minIndent must be non-negative")
    lines: list[Self] = self.splitLines()
    begin: int = 0
    end: int = len(lines)
    while begin < end and not lines[begin].strip():
      begin += 1
    while end > begin and not lines[end - 1].strip():
      end -= 1
    if begin >= end:
      return new()
    common: int = -1
    for i in range(begin, end):
      line: Self = lines[i]
      if not line.strip():
        continue
      indent: int = 0
      while indent < len(line) and line._data[indent] == ord(" "):
        indent += 1
      if common < 0 or indent < common:
        common = indent
    if common < 0:
      return new()
    prefix: Self = Self._fromCode(ord(" ")) * minIndent
    out: list[Self] = []
    for i in range(begin, end):
      line: Self = lines[i]
      if line.strip():
        out.append(prefix + line._sub(common, len(line)))
      else:
        out.append(Self())
    return Self._fromCode(ord("\n")).join(out)

  @immutable
  @overload
  def split(self, maxSplit: int = int.Max) -> list[Self]:
    return self.split(Self(), maxSplit)

  @immutable
  @overload
  def split(self, sep: Self, maxSplit: int = int.Max) -> list[Self]:
    """分隔子串匹配走 ``find``（KMP）。"""
    if maxSplit < 0:
      raise ValueError("maxSplit must be non-negative")
    out: list[Self] = []
    n: int = len(self)
    if sep:
      sepn: int = len(sep)
      i: int = 0
      splits: int = 0
      while i <= n:
        if splits >= maxSplit:
          out.append(self._sub(i, n))
          return out
        pos: int = self.find(sep, i, n)
        if pos < 0:
          out.append(self._sub(i, n))
          return out
        out.append(self._sub(i, pos))
        i = pos + sepn
        splits += 1
      return out
    i: int = 0
    splits: int = 0
    while i < n:
      while i < n and Self._isFieldWhitespace(self._data[i]):
        i += 1
      if i >= n:
        break
      if splits >= maxSplit:
        out.append(self._sub(i, n))
        return out
      j: int = i
      while j < n and not Self._isFieldWhitespace(self._data[j]):
        j += 1
      out.append(self._sub(i, j))
      i = j
      splits += 1
    return out

  @immutable
  @overload
  def rsplit(self, maxSplit: int = int.Max) -> list[Self]:
    return self.rsplit(Self(), maxSplit)

  @immutable
  @overload
  def rsplit(self, sep: Self, maxSplit: int = int.Max) -> list[Self]:
    """分隔子串匹配走 ``rfind``（KMP）。"""
    if maxSplit < 0:
      raise ValueError("maxSplit must be non-negative")
    n: int = len(self)
    sepn: int = len(sep)
    out: list[Self] = []
    if sepn > 0:
      splits: int = 0
      i: int = n
      while i >= 0:
        if splits >= maxSplit:
          out.append(self._sub(0, i))
          break
        pos: int = self.rfind(sep, 0, i)
        if pos < 0:
          out.append(self._sub(0, i))
          break
        out.append(self._sub(pos + sepn, i))
        i = pos
        splits += 1
      return Self._reverseSelfList(out)
    splits = 0
    j: int = n
    while j > 0:
      while j > 0 and Self._isFieldWhitespace(self._data[j - 1]):
        j -= 1
      if j == 0:
        break
      if splits >= maxSplit:
        out.append(self._sub(0, j))
        break
      k: int = j
      while k > 0 and not Self._isFieldWhitespace(self._data[k - 1]):
        k -= 1
      out.append(self._sub(k, j))
      j = k
      splits += 1
    return Self._reverseSelfList(out)

  @immutable
  @overload
  def splitPrefix(self) -> Self:
    """无 ``sep``：等同 ``split(maxSplit=1)[0]``（无字段时 ``new()``）；不构造 ``list``。"""
    n: int = len(self)
    i: int = 0
    while i < n and Self._isFieldWhitespace(self._data[i]):
      i += 1
    if i >= n:
      return new()
    j: int = i
    while j < n and not Self._isFieldWhitespace(self._data[j]):
      j += 1
    return self._sub(i, j)

  @immutable
  @overload
  def splitPrefix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``split(sep, 1)[0]``；``find`` + ``_sub``。"""
    pos: int = self.find(sep)
    if pos < 0:
      return self
    return self._sub(0, pos)

  @immutable
  @overload
  def splitSuffix(self) -> Self:
    """无 ``sep``：等同 ``split(maxSplit=1)[1]``（仅一段或无时 ``new()``）；不构造 ``list``。"""
    n: int = len(self)
    i: int = 0
    while i < n and Self._isFieldWhitespace(self._data[i]):
      i += 1
    if i >= n:
      return new()
    j: int = i
    while j < n and not Self._isFieldWhitespace(self._data[j]):
      j += 1
    i = j
    while i < n and Self._isFieldWhitespace(self._data[i]):
      i += 1
    if i >= n:
      return new()
    return self._sub(i, n)

  @immutable
  @overload
  def splitSuffix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``split(sep, 1)[1]`` / ``partition(sep)[2]``；``find`` + ``_sub``。"""
    pos: int = self.find(sep)
    if pos < 0:
      return new()
    return self._sub(pos + len(sep), len(self))

  @immutable
  @overload
  def rsplitPrefix(self) -> Self:
    """无 ``sep``：等同 ``rsplit(maxSplit=1)[0]``；不构造 ``list``。"""
    n: int = len(self)
    j: int = n
    splits: int = 0
    found: bool = False
    while j > 0:
      while j > 0 and Self._isFieldWhitespace(self._data[j - 1]):
        j -= 1
      if j == 0:
        break
      if splits >= 1:
        return self._sub(0, j)
      k: int = j
      while k > 0 and not Self._isFieldWhitespace(self._data[k - 1]):
        k -= 1
      found = True
      j = k
      splits += 1
    if found and splits == 1:
      return self
    return new()

  @immutable
  @overload
  def rsplitPrefix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``rsplit(sep, 1)[0]``；``rfind`` + ``_sub``。"""
    pos: int = self.rfind(sep)
    if pos < 0:
      return new()
    return self._sub(0, pos)

  @immutable
  @overload
  def rsplitSuffix(self) -> Self:
    """无 ``sep``：等同 ``rsplit(maxSplit=1)[-1]``；不构造 ``list``。"""
    n: int = len(self)
    j: int = n
    splits: int = 0
    tail: Self = new()
    haveTail: bool = False
    while j > 0:
      while j > 0 and Self._isFieldWhitespace(self._data[j - 1]):
        j -= 1
      if j == 0:
        break
      if splits >= 1:
        if haveTail:
          return tail
        return new()
      k: int = j
      while k > 0 and not Self._isFieldWhitespace(self._data[k - 1]):
        k -= 1
      tail = self._sub(k, j)
      haveTail = True
      j = k
      splits += 1
    if haveTail:
      return tail
    return new()

  @immutable
  @overload
  def rsplitSuffix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``rsplit(sep, 1)[-1]``；``rfind`` + ``_sub``。"""
    pos: int = self.rfind(sep)
    if pos < 0:
      return self
    return self._sub(pos + len(sep), len(self))

  @overload
  def xsplit(self, maxSplit: int = int.Max) -> GeneratorType[Self, None, None]:
    return self.xsplit(Self(), maxSplit)

  @overload
  def xsplit(self, sep: Self, maxSplit: int = int.Max) -> GeneratorType[Self, None, None]:
    """``split`` 的生成器版：逐段 ``yield``，语义与 ``split`` 一致。"""
    if maxSplit < 0:
      raise ValueError("maxSplit must be non-negative")
    i: int = 0
    splits: int = 0
    if not sep:
      while i < len(self):
        while i < len(self) and Self._isFieldWhitespace(self._data[i]):
          i += 1
        if i >= len(self):
          return
        if splits >= maxSplit:
          yield self._sub(i, len(self))
          return
        j: int = i
        while j < len(self) and not Self._isFieldWhitespace(self._data[j]):
          j += 1
        yield self._sub(i, j)
        i = j
        splits += 1
      return
    sepn: int = len(sep)
    while i <= len(self):
      if splits >= maxSplit:
        yield self._sub(i, len(self))
        return
      pos: int = self.find(sep, i, len(self))
      if pos < 0:
        yield self._sub(i, len(self))
        return
      yield self._sub(i, pos)
      i = pos + sepn
      splits += 1

  @overload
  def xrsplit(self, maxSplit: int = int.Max) -> GeneratorType[Self, None, None]:
    return self.xrsplit(Self(), maxSplit)

  def _xrsplitCollect(
    self, sep: Self, maxSplit: int, starts: int[:], ends: int[:],
  ) -> int:
    """``xrsplit`` 收集阶段：写入 ``starts``/``ends``，返回段数（非生成器，避免嵌套 ``while`` 状态机问题）。"""
    cnt: int = 0
    if sep:
      sepn: int = len(sep)
      splits: int = 0
      i: int = len(self)
      done: bool = False
      while i >= 0 and not done:
        if splits >= maxSplit:
          starts[cnt] = 0
          ends[cnt] = i
          cnt += 1
          done = True
        else:
          pos: int = self.rfind(sep, 0, i)
          if pos < 0:
            starts[cnt] = 0
            ends[cnt] = i
            cnt += 1
            done = True
          else:
            starts[cnt] = pos + sepn
            ends[cnt] = i
            cnt += 1
            i = pos
            splits += 1
    else:
      splits = 0
      j: int = len(self)
      done = False
      while j > 0 and not done:
        while j > 0 and Self._isFieldWhitespace(self._data[j - 1]):
          j -= 1
        if j == 0:
          done = True
        elif splits >= maxSplit:
          starts[cnt] = 0
          ends[cnt] = j
          cnt += 1
          done = True
        else:
          k: int = j
          while k > 0 and not Self._isFieldWhitespace(self._data[k - 1]):
            k -= 1
          starts[cnt] = k
          ends[cnt] = j
          cnt += 1
          j = k
          splits += 1
    return cnt

  @overload
  def xrsplit(self, sep: Self, maxSplit: int = int.Max) -> GeneratorType[Self, None, None]:
    """``rsplit`` 的生成器版：产出顺序与 ``rsplit`` 列表一致（``int[:]`` 存区间，无 ``list[Self]``）。"""
    if maxSplit < 0:
      raise ValueError("maxSplit must be non-negative")
    cap: int = len(self) + 1
    if maxSplit < cap:
      cap = maxSplit + 1
    starts: int[:] = new(cap)
    ends: int[:] = new(cap)
    cnt: int = self._xrsplitCollect(sep, maxSplit, starts, ends)
    for outI in range(cnt - 1, -1, -1):
      yield self._sub(starts[outI], ends[outI])

  @immutable
  def _findLinebreak(self, start: int, end: int) -> int:
    """``[start, end)`` 内首行行界；无则 ``end``。常见 ``\\n``/``\\r`` 等走 ``find``。"""
    best: int = end
    pos: int = self.find(Self._fromCode(ord("\n")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    pos = self.find(Self._fromCode(ord("\r")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    pos = self.find(Self._fromCode(ord("\v")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    pos = self.find(Self._fromCode(ord("\f")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    if best < end:
      return best
    for i in range(start, end):
      if Self._isLinebreak(self._data[i]):
        return i
    return end

  @immutable
  def splitLines(self, keepEnds: bool = False) -> list[Self]:
    out: list[Self] = []
    n: int = len(self)
    i: int = 0
    while i < n:
      j: int = self._findLinebreak(i, n)
      consumed: int = 1
      if j + 1 < n:
        if Self._isCrLfPair(self._data[j], self._data[j + 1]):
          consumed = 2
      piece: Self = self._sub(i, j)
      if keepEnds and j < n:
        endb: Host[:] = new(consumed)
        for k in range(consumed):
          endb[k] = self._data[j + k]
        piece += Self(endb)
      out.append(piece)
      if j >= n:
        break
      i = j + consumed
    return out

  @overload
  def xsplitLines(self, keepEnds: bool = False) -> GeneratorType[Self, None, None]:
    """``splitLines`` 的生成器版：逐行 ``yield``，语义与 ``splitLines`` 一致。"""
    n: int = len(self)
    i: int = 0
    while i < n:
      j: int = self._findLinebreak(i, n)
      consumed: int = 1
      if j + 1 < n:
        if Self._isCrLfPair(self._data[j], self._data[j + 1]):
          consumed = 2
      piece: Self = self._sub(i, j)
      if keepEnds and j < n:
        endb: Host[:] = new(consumed)
        for k in range(consumed):
          endb[k] = self._data[j + k]
        piece += Self(endb)
      yield piece
      if j >= n:
        break
      i = j + consumed

  @immutable
  def capitalize(self) -> Self:
    n: int = len(self)
    if n == 0:
      return new()
    buf: Host[:] = new(n)
    buf[0] = Self._toUpperChar(self._data[0])
    for i in range(1, n):
      buf[i] = Self._toLowerChar(self._data[i])
    return new(buf)

  @immutable
  @overload
  def center(self, width: int) -> Self:
    return self.center(width, Self._defaultPadChar())

  @immutable
  @overload
  def center(self, width: int, fillChar: Host) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    pad: int = width - n
    left: int = pad // 2
    right: int = pad - left
    buf: Host[:] = new(width)
    for i in range(left):
      buf[i] = fillChar
    for i in range(n):
      buf[left + i] = self._data[i]
    for i in range(right):
      buf[left + n + i] = fillChar
    return new(buf)

  @staticmethod
  def _expandTabsResetsCol(c: Host) -> bool:
    return c in "\n\r"

  @immutable
  def expandTabs(self, tabSize: int = 8) -> Self:
    n: int = len(self)
    outCap: int = n + n * tabSize
    buf: Host[:] = new(outCap)
    out: int = 0
    col: int = 0
    sp: Host = Self._defaultPadChar()
    for i in range(n):
      c: Host = self._data[i]
      if c == ord("\t"):
        spaces: int = tabSize - (col % tabSize)
        if spaces == 0:
          spaces = tabSize
        for _ in range(spaces):
          out = Self._append(buf, out, sp)
          col += 1
      elif Self._expandTabsResetsCol(c):
        out = Self._append(buf, out, c)
        col = 0
      else:
        out = Self._append(buf, out, c)
        col += 1
    trimmed: Host[:] = new(out)
    for i in range(out):
      trimmed[i] = buf[i]
    return new(trimmed)

  @immutable
  def isAlnum(self) -> bool:
    if not self:
      return False
    for i in range(len(self)):
      if not Self._isAlnumChar(self._data[i]):
        return False
    return True

  @immutable
  def isAlpha(self) -> bool:
    if not self:
      return False
    for i in range(len(self)):
      if not Self._isAlphaChar(self._data[i]):
        return False
    return True

  @immutable
  def isAscii(self) -> bool:
    for i in range(len(self)):
      if not Self._isAscii(self._data[i]):
        return False
    return True

  @immutable
  def isDecimal(self) -> bool:
    if not self:
      return False
    for i in range(len(self)):
      if not Self._isDigitChar(self._data[i]):
        return False
    return True

  @immutable
  def isDigit(self) -> bool:
    return self.isDecimal()

  @immutable
  def isLower(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    hasCased: bool = False
    for i in range(n):
      c: Host = self._data[i]
      if Self._isCased(c):
        hasCased = True
        if c < ord("a") or c > ord("z"):
          if c >= ord("A") and c <= ord("Z"):
            return False
    return hasCased

  @immutable
  def isSpace(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    for i in range(n):
      if not Self._isFieldWhitespace(self._data[i]):
        return False
    return True

  @immutable
  def isUpper(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    hasCased: bool = False
    for i in range(n):
      c: Host = self._data[i]
      if Self._isCased(c):
        hasCased = True
        if c < ord("A") or c > ord("Z"):
          if c >= ord("a") and c <= ord("z"):
            return False
    return hasCased

  @immutable
  @overload
  def ljust(self, width: int) -> Self:
    return self.ljust(width, Self._defaultPadChar())

  @immutable
  @overload
  def ljust(self, width: int, fillChar: Host) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    buf: Host[:] = new(width)
    for i in range(n):
      buf[i] = self._data[i]
    for i in range(n, width):
      buf[i] = fillChar
    return new(buf)

  @immutable
  def lower(self) -> Self:
    n: int = len(self)
    buf: Host[:] = new(n)
    for i in range(n):
      buf[i] = Self._toLowerChar(self._data[i])
    return new(buf)

  @immutable
  @overload
  def rjust(self, width: int) -> Self:
    return self.rjust(width, Self._defaultPadChar())

  @immutable
  @overload
  def rjust(self, width: int, fillChar: Host) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    pad: int = width - n
    buf: Host[:] = new(width)
    for i in range(pad):
      buf[i] = fillChar
    for i in range(n):
      buf[pad + i] = self._data[i]
    return new(buf)

  @immutable
  def swapCase(self) -> Self:
    n: int = len(self)
    buf: Host[:] = new(n)
    for i in range(n):
      c: Host = self._data[i]
      if c >= ord("A") and c <= ord("Z"):
        buf[i] = c + 32
      elif c >= ord("a") and c <= ord("z"):
        buf[i] = c - 32
      else:
        buf[i] = c
    return new(buf)

  @immutable
  def title(self) -> Self:
    n: int = len(self)
    buf: Host[:] = new(n)
    newWord: bool = True
    for i in range(n):
      c: Host = self._data[i]
      if Self._isAlphaChar(c):
        if newWord:
          buf[i] = Self._toUpperChar(c)
          newWord = False
        else:
          buf[i] = Self._toLowerChar(c)
      else:
        buf[i] = c
        newWord = True
    return new(buf)

  @immutable
  def upper(self) -> Self:
    n: int = len(self)
    buf: Host[:] = new(n)
    for i in range(n):
      buf[i] = Self._toUpperChar(self._data[i])
    return new(buf)

  @immutable
  def zfill(self, width: int) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    sign: Host = Self._zfillPadChar()
    bodyStart: int = 0
    hasSign: bool = False
    if n > 0:
      c0: Host = self._data[0]
      if c0 in "+-":
        hasSign = True
        sign = c0
        bodyStart = 1
    pad: int = width - n
    buf: Host[:] = new(width)
    at: int = 0
    if hasSign:
      buf[at] = sign
      at += 1
    zc: Host = Self._zfillPadChar()
    for _ in range(pad):
      buf[at] = zc
      at += 1
    for i in range(bodyStart, n):
      buf[at] = self._data[i]
      at += 1
    return new(buf)

  @staticmethod
  @overload
  def makeTrans(table: dict[Host, Host]) -> dict[Host, Host]:
    """``makeTrans(dict)``：直接返回映射表。"""
    return table

  @staticmethod
  @overload
  def makeTrans(frm: Self, to: Self, remove: Self = new()) -> dict[Host, Host]:
    """``makeTrans(from, to[, remove])``；``remove`` 写入 ``_translateDeleteMarker``。"""
    table: dict[Host, Host] = {}
    n: int = len(frm)
    for i in range(n):
      table[frm._data[i]] = to._data[i]
    zlen: int = len(remove)
    for i in range(zlen):
      table[remove._data[i]] = Self._translateDeleteMarker()
    return table

  @immutable
  def translate(self, table: dict[Host, Host], delete: Self = new()) -> Self:
    """``translate(table[, delete])``；表内删除哨兵由宿主 ``_translateDeleteMarker`` 提供。"""
    n: int = len(self)
    cap: int = Self._translateArrayLen(n)
    buf: Host[:] = new(cap)
    at: int = 0
    for i in range(n):
      c: Host = self._data[i]
      if Self(c) in delete:
        continue
      if c in table:
        mapped: Host = table[c]
        if mapped == Self._translateDeleteMarker():
          continue
        at = Self._append(buf, at, mapped)
      else:
        at = Self._append(buf, at, c)
    trimmed: Host[:] = new(at)
    for k in range(at):
      trimmed[k] = buf[k]
    return new(trimmed)

  @immutable
  def __eq__(self, other: Self) -> bool:
    return self._compare(other) == 0

  @immutable
  def __hash__(self) -> int:
    h: int = 0
    n: int = len(self._data)
    for i in range(n):
      h = h * 31 + self._data[i]
    return h
