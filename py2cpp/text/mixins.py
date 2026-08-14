"""``str`` / ``bytes`` 共享序列逻辑（``StringMixin[T]``）。

宿主须声明 ``_data: T[:]`` 或 ``_data: array[T, StackLength]``（``StackLength>0`` 时 ``array`` 内联 SSO；``str`` 用 ``StringMixin._SSO_CAP``）；
``str(StringMixin[char])``、``bytes(StringMixin[byte])``。
注解 ``Self`` 的空序列用 ``new()``（S06b）；``char[:]``/``byte[:]`` 缓冲见编码规范 §2.1。
"""
from ..builtins import *
from ..core.protocols import Generator
from ..core.exceptions import ValueError
from ..util.dict import dict
from ..util.list import list
from ..util.slice import slice


@mixin
class StringMixin[T: oneof[char, byte]]:
  """不可变堆序列（码点/字节）共享核心。"""

  _END_INDEX: int @const = int.Min
  _SSO_CAP: int @const = 22

  @staticmethod
  def _append(buf: T[:], at: int, c: T) -> int:
    buf[at] = c
    return at + 1

  @immutable
  @staticmethod
  def _norm_end(n: int, end: int) -> int:
    if end == Self._END_INDEX:
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
  def _norm_start(n: int, start: int) -> int:
    if start < 0:
      start += n
    if start < 0:
      return 0
    if start > n:
      return n
    return start

  @immutable
  @staticmethod
  def _kmp_build_lps(sub: Self, subn: int) -> int[:]:
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
  def _find_sub_forward_kmp(self, sub: Self, i: int, j: int, subn: int) -> int:
    if subn == 1:
      c0: T = sub._data[0]
      for k in range(i, j):
        if self._data[k] == c0:
          return k
      return -1
    lps: int[:] = Self._kmp_build_lps(sub, subn)
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
  def _find_sub_backward_kmp(self, sub: Self, i: int, j: int, subn: int) -> int:
    if subn == 1:
      c0: T = sub._data[0]
      for k in range(j - 1, i - 1, -1):
        if self._data[k] == c0:
          return k
      return -1
    lps: int[:] = Self._kmp_build_lps(sub, subn)
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
    i: int = Self._norm_start(n, start)
    j: int = Self._norm_end(n, end)
    if j < i:
      j = i
    m: int = j - i
    buf: T[:] = new(m)
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
  def __getitem__(self, index: int) -> T:
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
      buf: T[:] = new(cnt)
      for at in range(cnt):
        buf[at] = self._data[start + at * step]
      return new(buf)
    if start <= stop:
      return new()
    cnt: int = (start - stop - step - 1) // (-step)
    buf: T[:] = new(cnt)
    for at in range(cnt):
      buf[at] = self._data[start + at * step]
    return new(buf)

  @immutable
  def __contains__(self, sub: Self) -> bool:
    return self.find(sub) >= 0

  def __add__(self, other: Self) -> Self:
    n: int = len(self._data)
    m: int = len(other._data)
    buf: T[:] = new(n + m)
    for i in range(n):
      buf[i] = self._data[i]
    for j in range(m):
      buf[n + j] = other._data[j]
    return new(buf)

  def __mul__(self, n: int) -> Self:
    if n <= 0:
      return new()
    unit: int = len(self._data)
    total: int = unit * n
    buf: T[:] = new(total)
    at: int = 0
    for _ in range(n):
      for i in range(unit):
        buf[at] = self._data[i]
        at += 1
    return new(buf)

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
  def find(self, sub: Self, start: int = 0, end: int = Self._END_INDEX) -> int:
    n: int = len(self)
    i: int = Self._norm_start(n, start)
    j: int = Self._norm_end(n, end)
    subn: int = len(sub)
    if subn == 0:
      return i
    if subn > j - i:
      return -1
    return self._find_sub_forward_kmp(sub, i, j, subn)

  @immutable
  def index(self, sub: Self, start: int = 0, end: int = Self._END_INDEX) -> int:
    pos: int = self.find(sub, start, end)
    if pos < 0:
      raise ValueError("substring not found")
    return pos

  @immutable
  def rfind(self, sub: Self, start: int = 0, end: int = Self._END_INDEX) -> int:
    n: int = len(self)
    i: int = Self._norm_start(n, start)
    j: int = Self._norm_end(n, end)
    subn: int = len(sub)
    if subn == 0:
      return j
    if subn > j - i:
      return -1
    return self._find_sub_backward_kmp(sub, i, j, subn)

  @immutable
  def rindex(self, sub: Self, start: int = 0, end: int = Self._END_INDEX) -> int:
    pos: int = self.rfind(sub, start, end)
    if pos < 0:
      raise ValueError("substring not found")
    return pos

  @immutable
  def count(self, sub: Self, start: int = 0, end: int = Self._END_INDEX) -> int:
    n: int = len(self)
    i: int = Self._norm_start(n, start)
    j: int = Self._norm_end(n, end)
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
  def startswith(self, prefix: Self, start: int = 0, end: int = Self._END_INDEX) -> bool:
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
  def startswith(self, prefix: T[:], start: int = 0, end: int = Self._END_INDEX) -> bool:
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
  def startswith(self, prefixes: list[Self], start: int = 0, end: int = Self._END_INDEX) -> bool:
    cnt: int = len(prefixes)
    for i in range(cnt):
      if self.startswith(prefixes[i], start, end):
        return True
    return False

  @immutable
  @overload
  def startswith(self, prefixes: Self[:], start: int = 0, end: int = Self._END_INDEX) -> bool:
    cnt: int = len(prefixes)
    for i in range(cnt):
      if self.startswith(prefixes[i], start, end):
        return True
    return False

  @immutable
  @overload
  def endswith(self, suffix: Self, start: int = 0, end: int = Self._END_INDEX) -> bool:
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
  def endswith(self, suffix: T[:], start: int = 0, end: int = Self._END_INDEX) -> bool:
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
  def endswith(self, suffixes: list[Self], start: int = 0, end: int = Self._END_INDEX) -> bool:
    cnt: int = len(suffixes)
    for i in range(cnt):
      if self.endswith(suffixes[i], start, end):
        return True
    return False

  @immutable
  @overload
  def endswith(self, suffixes: Self[:], start: int = 0, end: int = Self._END_INDEX) -> bool:
    cnt: int = len(suffixes)
    for i in range(cnt):
      if self.endswith(suffixes[i], start, end):
        return True
    return False

  @immutable
  def _glob_normcase(self) -> Self:
    """``fnmatch`` 大小写规范化（``/``→``\\`` + ASCII ``lower``，对齐 ``io.file.path.normcase``）。"""
    n: int = len(self)
    if n == 0:
      return self
    buf: T[:] = new(n)
    alt: T = ord("/")
    sep: T = ord("\\")
    for i in range(n):
      c: T = self._data[i]
      if c == alt:
        buf[i] = sep
      else:
        buf[i] = Self._to_lower_char(c)
    return new(buf)

  @immutable
  def _glob_class_body_contains(self, c: T, start: int, end: int) -> bool:
    has_dash: bool = False
    for i in range(start, end):
      if self._data[i] == ord("-"):
        has_dash = True
        break
    if not has_dash:
      for i in range(start, end):
        if c == self._data[i]:
          return True
      return False
    chunks: list[Self] = []
    i: int = start
    k: int = start + 1
    while True:
      dash: int = self.find(Self._from_code(ord("-")), k, end)
      if dash < 0:
        tail: Self = self._sub(i, end)
        if tail:
          chunks.append(tail)
        elif chunks:
          last: Self = chunks[-1]
          chunks[-1] = last + Self._from_code(ord("-"))
        break
      chunks.append(self._sub(i, dash))
      i = dash + 1
      k = dash + 3
    cnt: int = len(chunks)
    for j in range(cnt):
      chunk: Self = chunks[j]
      if chunk._glob_class_chunk_contains(c):
        return True
    return False

  @immutable
  def _glob_class_chunk_contains(self, c: T) -> bool:
    cn: int = len(self)
    match cn:
      case 0:
        return False
      case 1:
        return c == self._data[0]
      case 2:
        lo: T = self._data[0]
        hi: T = self._data[1]
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
  def _glob_class_contains(self, c: T) -> bool:
    bn: int = len(self)
    neg: bool = False
    start: int = 0
    if bn > 0 and self._data[0] == ord("!"):
      neg = True
      start = 1
    matched: bool = True
    if start < bn:
      matched = self._glob_class_body_contains(c, start, bn)
    if neg:
      return not matched
    return matched

  @immutable
  def _glob_match_bracket(self, c: T, pi: int) -> int:
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
    if not body._glob_class_contains(c):
      return -1
    return close + 1

  @immutable
  def _glob_match_at(self, pat: Self, ni: int, pi: int) -> bool:
    nn: int = len(self)
    pn: int = len(pat)
    while True:
      if pi >= pn:
        return ni >= nn
      star_c: T = pat._data[pi]
      if star_c == ord("*"):
        pi += 1
        while pi < pn and pat._data[pi] == star_c:
          pi += 1
        if pi >= pn:
          return True
        for trial in range(ni, nn + 1):
          if self._glob_match_at(pat, trial, pi):
            return True
        return False
      if ni >= nn:
        return False
      pc: T = pat._data[pi]
      if pc == ord("?"):
        ni += 1
        pi += 1
        continue
      if pc == ord("["):
        next_pi: int = pat._glob_match_bracket(self._data[ni], pi)
        if next_pi < 0:
          return False
        ni += 1
        pi = next_pi
        continue
      if self._data[ni] != pat._data[pi]:
        return False
      ni += 1
      pi += 1

  @immutable
  def _glob_match(self, pat: Self) -> bool:
    return self._glob_match_at(pat, 0, 0)

  @immutable
  def glob(self, pattern: Self, ignore_case: bool = True) -> bool:
    """Shell 通配匹配（语义对齐 ``fnmatch`` / ``fnmatchcase``；非 ``pathlib.Path.glob``）。"""
    name: Self = self
    pat: Self = pattern
    if ignore_case:
      name = self._glob_normcase()
      pat = pattern._glob_normcase()
    return name._glob_match(pat)

  @immutable
  @staticmethod
  def _from_code(code: int) -> Self:
    """单码点/单字节子串（``find(r\"\\n\")`` 等）；勿 ``Self(ord(...))``（``bytes(n)`` 为定长构造）。"""
    buf: T[:] = new(1)
    buf[0] = code
    return new(buf)

  @immutable
  @staticmethod
  def _reverse_self_list(items: list[Self]) -> list[Self]:
    out: list[Self] = []
    cnt: int = len(items)
    for i in range(cnt):
      out.append(items[cnt - 1 - i])
    return out

  @immutable
  def join(self, iterable: list[Self]) -> Self:
    total: int = 0
    sep_n: int = len(self)
    cnt: int = len(iterable)
    for i in range(cnt):
      total += len(iterable[i])
    if cnt > 1:
      total += sep_n * (cnt - 1)
    buf: T[:] = new(total)
    at: int = 0
    for i in range(cnt):
      part: Self = iterable[i]
      pn: int = len(part)
      for j in range(pn):
        buf[at] = part._data[j]
        at += 1
      if i + 1 < cnt:
        for j in range(sep_n):
          buf[at] = self._data[j]
          at += 1
    return new(buf)

  @immutable
  def removeprefix(self, prefix: Self) -> Self:
    pn: int = len(prefix)
    if pn == 0:
      return self
    if not self.startswith(prefix):
      return self
    return self._sub(pn, len(self))

  @immutable
  def removesuffix(self, suffix: Self) -> Self:
    sn: int = len(suffix)
    if sn == 0:
      return self
    if not self.endswith(suffix):
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
  def replace(self, old: Self, new: Self, count: int = -1) -> Self:
    n: int = len(self)
    oldn: int = len(old)
    if oldn == 0:
      return self
    limit: int = count
    if limit < 0:
      limit = n + 1
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
      while i < n and Self._is_field_whitespace(self._data[i]):
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
      while j > 0 and Self._is_field_whitespace(self._data[j - 1]):
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
  def striplines(self, min_indent: int = 0) -> Self:
    """???????????????????? ``min_indent`` ????"""
    if min_indent < 0:
      raise ValueError("min_indent must be non-negative")
    lines: list[Self] = self.splitlines()
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
    prefix: Self = Self._from_code(ord(" ")) * min_indent
    out: list[Self] = []
    for i in range(begin, end):
      line: Self = lines[i]
      if line.strip():
        out.append(prefix + line._sub(common, len(line)))
      else:
        out.append(Self())
    return Self._from_code(ord("\n")).join(out)

  @immutable
  @overload
  def split(self, maxsplit: int = -1) -> list[Self]:
    return self.split(Self(), maxsplit)

  @immutable
  @overload
  def split(self, sep: Self, maxsplit: int = -1) -> list[Self]:
    """分隔子串匹配走 ``find``（KMP）。"""
    out: list[Self] = []
    n: int = len(self)
    if sep:
      sepn: int = len(sep)
      i: int = 0
      splits: int = 0
      while i <= n:
        if maxsplit >= 0 and splits >= maxsplit:
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
      while i < n and Self._is_field_whitespace(self._data[i]):
        i += 1
      if i >= n:
        break
      if maxsplit >= 0 and splits >= maxsplit:
        out.append(self._sub(i, n))
        return out
      j: int = i
      while j < n and not Self._is_field_whitespace(self._data[j]):
        j += 1
      out.append(self._sub(i, j))
      i = j
      splits += 1
    return out

  @immutable
  @overload
  def rsplit(self, maxsplit: int = -1) -> list[Self]:
    return self.rsplit(Self(), maxsplit)

  @immutable
  @overload
  def rsplit(self, sep: Self, maxsplit: int = -1) -> list[Self]:
    """分隔子串匹配走 ``rfind``（KMP）。"""
    n: int = len(self)
    sepn: int = len(sep)
    out: list[Self] = []
    if sepn > 0:
      splits: int = 0
      i: int = n
      while i >= 0:
        if maxsplit >= 0 and splits >= maxsplit:
          out.append(self._sub(0, i))
          break
        pos: int = self.rfind(sep, 0, i)
        if pos < 0:
          out.append(self._sub(0, i))
          break
        out.append(self._sub(pos + sepn, i))
        i = pos
        splits += 1
      return Self._reverse_self_list(out)
    splits = 0
    j: int = n
    while j > 0:
      while j > 0 and Self._is_field_whitespace(self._data[j - 1]):
        j -= 1
      if j == 0:
        break
      if maxsplit >= 0 and splits >= maxsplit:
        out.append(self._sub(0, j))
        break
      k: int = j
      while k > 0 and not Self._is_field_whitespace(self._data[k - 1]):
        k -= 1
      out.append(self._sub(k, j))
      j = k
      splits += 1
    return Self._reverse_self_list(out)

  @immutable
  @overload
  def split_prefix(self) -> Self:
    """无 ``sep``：等同 ``split(maxsplit=1)[0]``（无字段时 ``new()``）；不构造 ``list``。"""
    n: int = len(self)
    i: int = 0
    while i < n and Self._is_field_whitespace(self._data[i]):
      i += 1
    if i >= n:
      return new()
    j: int = i
    while j < n and not Self._is_field_whitespace(self._data[j]):
      j += 1
    return self._sub(i, j)

  @immutable
  @overload
  def split_prefix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``split(sep, 1)[0]``；``find`` + ``_sub``。"""
    pos: int = self.find(sep)
    if pos < 0:
      return self
    return self._sub(0, pos)

  @immutable
  @overload
  def split_suffix(self) -> Self:
    """无 ``sep``：等同 ``split(maxsplit=1)[1]``（仅一段或无时 ``new()``）；不构造 ``list``。"""
    n: int = len(self)
    i: int = 0
    while i < n and Self._is_field_whitespace(self._data[i]):
      i += 1
    if i >= n:
      return new()
    j: int = i
    while j < n and not Self._is_field_whitespace(self._data[j]):
      j += 1
    i = j
    while i < n and Self._is_field_whitespace(self._data[i]):
      i += 1
    if i >= n:
      return new()
    return self._sub(i, n)

  @immutable
  @overload
  def split_suffix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``split(sep, 1)[1]`` / ``partition(sep)[2]``；``find`` + ``_sub``。"""
    pos: int = self.find(sep)
    if pos < 0:
      return new()
    return self._sub(pos + len(sep), len(self))

  @immutable
  @overload
  def rsplit_prefix(self) -> Self:
    """无 ``sep``：等同 ``rsplit(maxsplit=1)[0]``；不构造 ``list``。"""
    n: int = len(self)
    j: int = n
    splits: int = 0
    found: bool = False
    while j > 0:
      while j > 0 and Self._is_field_whitespace(self._data[j - 1]):
        j -= 1
      if j == 0:
        break
      if splits >= 1:
        return self._sub(0, j)
      k: int = j
      while k > 0 and not Self._is_field_whitespace(self._data[k - 1]):
        k -= 1
      found = True
      j = k
      splits += 1
    if found and splits == 1:
      return self
    return new()

  @immutable
  @overload
  def rsplit_prefix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``rsplit(sep, 1)[0]``；``rfind`` + ``_sub``。"""
    pos: int = self.rfind(sep)
    if pos < 0:
      return new()
    return self._sub(0, pos)

  @immutable
  @overload
  def rsplit_suffix(self) -> Self:
    """无 ``sep``：等同 ``rsplit(maxsplit=1)[-1]``；不构造 ``list``。"""
    n: int = len(self)
    j: int = n
    splits: int = 0
    tail: Self = new()
    have_tail: bool = False
    while j > 0:
      while j > 0 and Self._is_field_whitespace(self._data[j - 1]):
        j -= 1
      if j == 0:
        break
      if splits >= 1:
        if have_tail:
          return tail
        return new()
      k: int = j
      while k > 0 and not Self._is_field_whitespace(self._data[k - 1]):
        k -= 1
      tail = self._sub(k, j)
      have_tail = True
      j = k
      splits += 1
    if have_tail:
      return tail
    return new()

  @immutable
  @overload
  def rsplit_suffix(self, sep: Self) -> Self:
    """有 ``sep``：等同 ``rsplit(sep, 1)[-1]``；``rfind`` + ``_sub``。"""
    pos: int = self.rfind(sep)
    if pos < 0:
      return self
    return self._sub(pos + len(sep), len(self))

  @overload
  def xsplit(self, maxsplit: int = -1) -> Generator[Self, None, None]:
    return self.xsplit(Self(), maxsplit)

  @overload
  def xsplit(self, sep: Self, maxsplit: int = -1) -> Generator[Self, None, None]:
    """``split`` 的生成器版：逐段 ``yield``，语义与 ``split`` 一致。"""
    i: int = 0
    splits: int = 0
    if not sep:
      while i < len(self):
        while i < len(self) and Self._is_field_whitespace(self._data[i]):
          i += 1
        if i >= len(self):
          return
        if maxsplit >= 0 and splits >= maxsplit:
          yield self._sub(i, len(self))
          return
        j: int = i
        while j < len(self) and not Self._is_field_whitespace(self._data[j]):
          j += 1
        yield self._sub(i, j)
        i = j
        splits += 1
      return
    sepn: int = len(sep)
    while i <= len(self):
      if maxsplit >= 0 and splits >= maxsplit:
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
  def xrsplit(self, maxsplit: int = -1) -> Generator[Self, None, None]:
    return self.xrsplit(Self(), maxsplit)

  def _xrsplit_collect(
    self, sep: Self, maxsplit: int, starts: int[:], ends: int[:],
  ) -> int:
    """``xrsplit`` 收集阶段：写入 ``starts``/``ends``，返回段数（非生成器，避免嵌套 ``while`` 状态机问题）。"""
    cnt: int = 0
    if sep:
      sepn: int = len(sep)
      splits: int = 0
      i: int = len(self)
      done: bool = False
      while i >= 0 and not done:
        if maxsplit >= 0 and splits >= maxsplit:
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
        while j > 0 and Self._is_field_whitespace(self._data[j - 1]):
          j -= 1
        if j == 0:
          done = True
        elif maxsplit >= 0 and splits >= maxsplit:
          starts[cnt] = 0
          ends[cnt] = j
          cnt += 1
          done = True
        else:
          k: int = j
          while k > 0 and not Self._is_field_whitespace(self._data[k - 1]):
            k -= 1
          starts[cnt] = k
          ends[cnt] = j
          cnt += 1
          j = k
          splits += 1
    return cnt

  @overload
  def xrsplit(self, sep: Self, maxsplit: int = -1) -> Generator[Self, None, None]:
    """``rsplit`` 的生成器版：产出顺序与 ``rsplit`` 列表一致（``int[:]`` 存区间，无 ``list[Self]``）。"""
    starts: int[:] = new(maxsplit + 1 if maxsplit >= 0 else len(self) + 1)
    ends: int[:] = new(maxsplit + 1 if maxsplit >= 0 else len(self) + 1)
    cnt: int = self._xrsplit_collect(sep, maxsplit, starts, ends)
    for out_i in range(cnt - 1, -1, -1):
      yield self._sub(starts[out_i], ends[out_i])

  @immutable
  def _find_linebreak(self, start: int, end: int) -> int:
    """``[start, end)`` 内首行行界；无则 ``end``。常见 ``\\n``/``\\r`` 等走 ``find``。"""
    best: int = end
    pos: int = self.find(Self._from_code(ord("\n")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    pos = self.find(Self._from_code(ord("\r")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    pos = self.find(Self._from_code(ord("\v")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    pos = self.find(Self._from_code(ord("\f")), start, end)
    if pos >= 0 and pos < best:
      best = pos
    if best < end:
      return best
    for i in range(start, end):
      if Self._is_linebreak(self._data[i]):
        return i
    return end

  @immutable
  def splitlines(self, keepends: bool = False) -> list[Self]:
    out: list[Self] = []
    n: int = len(self)
    i: int = 0
    while i < n:
      j: int = self._find_linebreak(i, n)
      consumed: int = 1
      if j + 1 < n:
        if Self._is_cr_lf_pair(self._data[j], self._data[j + 1]):
          consumed = 2
      piece: Self = self._sub(i, j)
      if keepends and j < n:
        endb: T[:] = new(consumed)
        for k in range(consumed):
          endb[k] = self._data[j + k]
        piece += Self(endb)
      out.append(piece)
      if j >= n:
        break
      i = j + consumed
    return out

  @overload
  def xsplitlines(self, keepends: bool = False) -> Generator[Self, None, None]:
    """``splitlines`` 的生成器版：逐行 ``yield``，语义与 ``splitlines`` 一致。"""
    n: int = len(self)
    i: int = 0
    while i < n:
      j: int = self._find_linebreak(i, n)
      consumed: int = 1
      if j + 1 < n:
        if Self._is_cr_lf_pair(self._data[j], self._data[j + 1]):
          consumed = 2
      piece: Self = self._sub(i, j)
      if keepends and j < n:
        endb: T[:] = new(consumed)
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
    buf: T[:] = new(n)
    buf[0] = Self._to_upper_char(self._data[0])
    for i in range(1, n):
      buf[i] = Self._to_lower_char(self._data[i])
    return new(buf)

  @immutable
  @overload
  def center(self, width: int) -> Self:
    return self.center(width, Self._default_pad_char())

  @immutable
  @overload
  def center(self, width: int, fillchar: T) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    pad: int = width - n
    left: int = pad // 2
    right: int = pad - left
    buf: T[:] = new(width)
    for i in range(left):
      buf[i] = fillchar
    for i in range(n):
      buf[left + i] = self._data[i]
    for i in range(right):
      buf[left + n + i] = fillchar
    return new(buf)

  @staticmethod
  def _expandtabs_resets_col(c: T) -> bool:
    return c in "\n\r"

  @immutable
  def expandtabs(self, tabsize: int = 8) -> Self:
    n: int = len(self)
    out_cap: int = n + n * tabsize
    buf: T[:] = new(out_cap)
    out: int = 0
    col: int = 0
    sp: T = Self._default_pad_char()
    for i in range(n):
      c: T = self._data[i]
      if c == ord("\t"):
        spaces: int = tabsize - (col % tabsize)
        if spaces == 0:
          spaces = tabsize
        for _ in range(spaces):
          out = Self._append(buf, out, sp)
          col += 1
      elif Self._expandtabs_resets_col(c):
        out = Self._append(buf, out, c)
        col = 0
      else:
        out = Self._append(buf, out, c)
        col += 1
    trimmed: T[:] = new(out)
    for i in range(out):
      trimmed[i] = buf[i]
    return new(trimmed)

  @immutable
  def isalnum(self) -> bool:
    if not self:
      return False
    for i in range(len(self)):
      if not Self._is_alnum_char(self._data[i]):
        return False
    return True

  @immutable
  def isalpha(self) -> bool:
    if not self:
      return False
    for i in range(len(self)):
      if not Self._is_alpha_char(self._data[i]):
        return False
    return True

  @immutable
  def isascii(self) -> bool:
    for i in range(len(self)):
      if not Self._is_ascii(self._data[i]):
        return False
    return True

  @immutable
  def isdecimal(self) -> bool:
    if not self:
      return False
    for i in range(len(self)):
      if not Self._is_digit_char(self._data[i]):
        return False
    return True

  @immutable
  def isdigit(self) -> bool:
    return self.isdecimal()

  @immutable
  def islower(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    has_cased: bool = False
    for i in range(n):
      c: T = self._data[i]
      if Self._is_cased(c):
        has_cased = True
        if c < ord("a") or c > ord("z"):
          if c >= ord("A") and c <= ord("Z"):
            return False
    return has_cased

  @immutable
  def isspace(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    for i in range(n):
      if not Self._is_field_whitespace(self._data[i]):
        return False
    return True

  @immutable
  def isupper(self) -> bool:
    n: int = len(self)
    if n == 0:
      return False
    has_cased: bool = False
    for i in range(n):
      c: T = self._data[i]
      if Self._is_cased(c):
        has_cased = True
        if c < ord("A") or c > ord("Z"):
          if c >= ord("a") and c <= ord("z"):
            return False
    return has_cased

  @immutable
  @overload
  def ljust(self, width: int) -> Self:
    return self.ljust(width, Self._default_pad_char())

  @immutable
  @overload
  def ljust(self, width: int, fillchar: T) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    buf: T[:] = new(width)
    for i in range(n):
      buf[i] = self._data[i]
    for i in range(n, width):
      buf[i] = fillchar
    return new(buf)

  @immutable
  def lower(self) -> Self:
    n: int = len(self)
    buf: T[:] = new(n)
    for i in range(n):
      buf[i] = Self._to_lower_char(self._data[i])
    return new(buf)

  @immutable
  @overload
  def rjust(self, width: int) -> Self:
    return self.rjust(width, Self._default_pad_char())

  @immutable
  @overload
  def rjust(self, width: int, fillchar: T) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    pad: int = width - n
    buf: T[:] = new(width)
    for i in range(pad):
      buf[i] = fillchar
    for i in range(n):
      buf[pad + i] = self._data[i]
    return new(buf)

  @immutable
  def swapcase(self) -> Self:
    n: int = len(self)
    buf: T[:] = new(n)
    for i in range(n):
      c: T = self._data[i]
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
    buf: T[:] = new(n)
    new_word: bool = True
    for i in range(n):
      c: T = self._data[i]
      if Self._is_alpha_char(c):
        if new_word:
          buf[i] = Self._to_upper_char(c)
          new_word = False
        else:
          buf[i] = Self._to_lower_char(c)
      else:
        buf[i] = c
        new_word = True
    return new(buf)

  @immutable
  def upper(self) -> Self:
    n: int = len(self)
    buf: T[:] = new(n)
    for i in range(n):
      buf[i] = Self._to_upper_char(self._data[i])
    return new(buf)

  @immutable
  def zfill(self, width: int) -> Self:
    n: int = len(self)
    if width <= n:
      return self
    sign: T = Self._zfill_pad_char()
    body_start: int = 0
    has_sign: bool = False
    if n > 0:
      c0: T = self._data[0]
      if c0 in "+-":
        has_sign = True
        sign = c0
        body_start = 1
    pad: int = width - n
    buf: T[:] = new(width)
    at: int = 0
    if has_sign:
      buf[at] = sign
      at += 1
    zc: T = Self._zfill_pad_char()
    for _ in range(pad):
      buf[at] = zc
      at += 1
    for i in range(body_start, n):
      buf[at] = self._data[i]
      at += 1
    return new(buf)

  @staticmethod
  @overload
  def maketrans(table: dict[T, T]) -> dict[T, T]:
    """``maketrans(dict)``：直接返回映射表。"""
    return table

  @staticmethod
  @overload
  def maketrans(frm: Self, to: Self, remove: Self = new()) -> dict[T, T]:
    """``maketrans(from, to[, remove])``；``remove`` 写入 ``_translate_delete_marker``。"""
    table: dict[T, T] = {}
    n: int = len(frm)
    for i in range(n):
      table[frm._data[i]] = to._data[i]
    zlen: int = len(remove)
    for i in range(zlen):
      table[remove._data[i]] = Self._translate_delete_marker()
    return table

  @immutable
  def translate(self, table: dict[T, T], delete: Self = new()) -> Self:
    """``translate(table[, delete])``；表内删除哨兵由宿主 ``_translate_delete_marker`` 提供。"""
    n: int = len(self)
    cap: int = Self._translate_buf_len(n)
    buf: T[:] = new(cap)
    at: int = 0
    for i in range(n):
      c: T = self._data[i]
      if Self(c) in delete:
        continue
      if c in table:
        mapped: T = table[c]
        if mapped == Self._translate_delete_marker():
          continue
        at = Self._append(buf, at, mapped)
      else:
        at = Self._append(buf, at, c)
    trimmed: T[:] = new(at)
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
