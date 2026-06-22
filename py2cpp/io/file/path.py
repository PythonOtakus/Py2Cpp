"""``os.path``：纯路径与元数据检测（对齐 Python 3.13 ``ntpath`` / ``genericpath``）。

C 层：``exists`` / ``isfile`` / ``isdir`` / ``lexists`` / ``islink`` / ``isjunction`` /
``isdevdrive`` / ``realpath``（``templates/io/-file.inl`` → ``io/file/path.inl`` 同批 paste_before）。
其余在 Python 侧实现，复用 ``py2cpp.text.str``。
"""
from ...builtins import *
from ...core.exceptions import OSError, ValueError
from ...util.list import list
from ...text import str

curdir: str = "."
pardir: str = ".."
extsep: str = "."
sep: str = "\\"
pathsep: str = ";"
altsep: str = "/"
defpath: str = ".;C:\\bin"
devnull: str = "nul"
supports_unicode_filenames: bool = True

_SEP: str = sep
_ALT: str = altsep
_SEP_CHARS: str = "\\/"
_DOT: str = curdir
_PARDIR: str = pardir


@immutable
def _last_sep_index(path: str) -> int:
  sep_index: int = path.rfind(_SEP)
  alt: int = path.rfind(_ALT)
  if alt > sep_index:
    sep_index = alt
  return sep_index


@immutable
def _norm_tail(path: str) -> str:
  return path.rstrip(_SEP_CHARS)


@immutable
def _norm_head(path: str) -> str:
  if not path:
    return path
  out: str = path.lstrip(_SEP_CHARS)
  if not out:
    return _SEP
  return out


@immutable
def splitroot(path: str) -> (str, str, str):
  """``(drive, root, tail)``（``ntpath.splitroot`` 纯 Python 回退）。"""
  normp: str = path.replace(_ALT, _SEP)
  n: int = len(normp)
  if not n:
    return "", "", ""
  if normp[:1] == _SEP:
    if n >= 2 and normp[1:2] == _SEP:
      start: int = 2
      if n >= 8 and normp[:8].upper() == "\\\\?\\UNC\\":
        start = 8
      idx: int = normp.find(_SEP, start)
      if idx < 0:
        return path, "", ""
      idx2: int = normp.find(_SEP, idx + 1)
      if idx2 < 0:
        return path, "", ""
      return path[:idx2], path[idx2 : idx2 + 1], path[idx2 + 1 :]
    return "", normp[:1], normp[1:]
  if n >= 2 and normp[1:2] == ":":
    if n >= 3 and normp[2:3] == _SEP:
      return path[:2], path[2:3], path[3:]
    return path[:2], "", path[2:]
  return "", "", path


def join(path: str, other: str) -> str:
  """拼接两段路径（绝对后缀覆盖前缀）。"""
  pd: str
  pr: str
  pp: str
  pd, pr, pp = splitroot(other)
  if pr or pd:
    return pd + pr + pp
  p: str = _norm_tail(path)
  o: str = _norm_head(other)
  if not p:
    return o
  if not o:
    return p
  return p + _SEP + o


@immutable
def _join_paths(base: str, parts: list[str]) -> str:
  out: str = base
  for p in parts:
    out = join(out, p)
  return out


@native
def exists(path: str) -> bool:
  """路径是否存在。"""
  ...


@native
def isfile(path: str) -> bool:
  """是否为常规文件。"""
  ...


@native
def isdir(path: str) -> bool:
  """是否为目录。"""
  ...


@native
def lexists(path: str) -> bool:
  """是否存在（不跟随符号链接失败时仍检测）。"""
  ...


@native
def islink(path: str) -> bool:
  """是否为符号链接。"""
  ...


@native
def isjunction(path: str) -> bool:
  """是否为目录联结（Windows junction）。"""
  ...


@native
def isdevdrive(path: str) -> bool:
  """是否在 Dev Drive 卷上（暂恒 ``False``）。"""
  ...


@native
def realpath(path: str) -> str:
  """规范绝对路径（Win ``GetFullPathName`` / POSIX ``realpath``）。"""
  ...


def basename(path: str) -> str:
  tail: str
  *_, tail = splitroot(path)
  pos: int = _last_sep_index(tail)
  if pos < 0:
    return tail
  if pos >= len(tail) - 1:
    return ""
  return tail[pos + 1 :]


def dirname(path: str) -> str:
  d: str
  r: str
  tail: str
  d, r, tail = splitroot(path)
  pos: int = _last_sep_index(tail)
  if pos < 0:
    return d + r
  if pos == 0:
    return d + r + _SEP
  head: str = tail[:pos]
  return d + r + _norm_tail(head)


def normpath(path: str) -> str:
  """折叠 ``.`` / ``..`` 与重复分隔符。"""
  if not path:
    return ""
  p: str = path.replace(_ALT, _SEP)
  drive: str
  root: str
  rest: str
  drive, root, rest = splitroot(p)
  prefix: str = drive + root
  parts: list[str] = rest.split(_SEP)
  comps: list[str] = []
  for part in parts:
    if not part or part == _DOT:
      continue
    if part == _PARDIR:
      if comps and comps[-1] != _PARDIR:
        comps.pop()
      elif not root:
        comps.append(_PARDIR)
      continue
    comps.append(part)
  if not prefix and not comps:
    comps.append(_DOT)
  out: str = prefix
  for i in range(len(comps)):
    if i > 0 or prefix:
      out += _SEP
    out += comps[i]
  return out


@immutable
def normcase(path: str) -> str:
  if not path:
    return path
  p: str = path.replace(_ALT, _SEP)
  return p.lower()


@immutable
def split(path: str) -> (str, str):
  d: str
  r: str
  tail: str
  d, r, tail = splitroot(path)
  pos: int = len(tail)
  while pos > 0 and tail[pos - 1 : pos] not in _SEP_CHARS:
    pos -= 1
  head: str = tail[:pos]
  leaf: str = tail[pos:]
  return d + r + _norm_tail(head), leaf


@immutable
def splitdrive(path: str) -> (str, str):
  d: str
  r: str
  tail: str
  d, r, tail = splitroot(path)
  return d, r + tail


@immutable
def splitext(path: str) -> (str, str):
  sep_index: int = _last_sep_index(path)
  dot_index: int = path.rfind(".")
  if dot_index > sep_index:
    stem: str = path[sep_index + 1 : dot_index]
    stem_body: str = stem.replace(".", "")
    if stem_body:
      return path[:dot_index], path[dot_index:]
  return path, ""


@immutable
def isabs(path: str) -> bool:
  if not path:
    return False
  norm: str = path[:3].replace(_ALT, _SEP)
  if len(norm) >= 2 and norm[1:2] == ":" and len(norm) >= 3 and norm[2:3] == _SEP:
    return True
  if path.startswith("\\\\"):
    return True
  if path.startswith(_SEP) or path.startswith(_ALT):
    return True
  if len(path) >= 2 and path[1:2] == ":":
    return True
  return False


@native
def getsize(path: str) -> int:
  """文件字节大小。"""
  ...


@native
def getmtime(path: str) -> float64:
  """修改时间。"""
  ...


@native
def getatime(path: str) -> float64:
  """访问时间。"""
  ...


@native
def getctime(path: str) -> float64:
  """创建/元数据变更时间。"""
  ...


@native
def _path_getcwd() -> str:
  """当前工作目录（供 ``abspath``）。"""
  ...


@immutable
def commonprefix(m: list[str]) -> str:
  if not m:
    return ""
  s1: str = m[0]
  s2: str = m[0]
  for i in range(len(m)):
    if m[i] < s1:
      s1 = m[i]
    if m[i] > s2:
      s2 = m[i]
  limit: int = len(s1)
  if len(s2) < limit:
    limit = len(s2)
  i: int = 0
  for i in range(limit):
    if s1[i] != s2[i]:
      return s1[:i]
  return s1[:limit]


@immutable
def abspath(path: str) -> str:
  p: str = normpath(path)
  if not isabs(p):
    p = normpath(join(_path_getcwd(), p))
  return realpath(p)


@immutable
def relpath(path: str, start: str = ".") -> str:
  if not path:
    raise ValueError("no path specified")
  start_abs: str = abspath(start)
  path_abs: str = abspath(path)
  sd: str
  srest: str
  sd, _, srest = splitroot(start_abs)
  pd: str
  prest: str
  pd, _, prest = splitroot(path_abs)
  if normcase(sd) != normcase(pd):
    raise ValueError("path is on mount")
  start_parts: list[str] = srest.split(_SEP)
  if not srest:
    start_parts = []
  path_parts: list[str] = prest.split(_SEP)
  if not prest:
    path_parts = []
  si: list[str] = []
  pi: list[str] = []
  for part in start_parts:
    if part and part != _DOT:
      si.append(part)
  for part in path_parts:
    if part and part != _DOT:
      pi.append(part)
  common_len: int = 0
  n: int = len(si)
  if len(pi) < n:
    n = len(pi)
  for i in range(n):
    if normcase(si[i]) != normcase(pi[i]):
      break
    common_len = i + 1
  rel: list[str] = []
  for j in range(common_len, len(si)):
    rel.append(_PARDIR)
  for k in range(common_len, len(pi)):
    rel.append(pi[k])
  if not rel:
    return _DOT
  out: str = rel[0]
  for ri in range(1, len(rel)):
    out = join(out, rel[ri])
  return out


@immutable
def commonpath(paths: list[str]) -> str:
  if not paths:
    raise ValueError("commonpath() arg is an empty iterable")
  drives: list[str] = []
  roots: list[str] = []
  split_paths: list[list[str]] = []
  for p in paths:
    norm: str = p.replace(_ALT, _SEP)
    d: str
    r: str
    tail: str
    d, r, tail = splitroot(norm)
    drives.append(d.lower())
    roots.append(r)
    parts: list[str] = tail.split(_SEP)
    cleaned: list[str] = []
    for part in parts:
      if part and part != _DOT:
        cleaned.append(part)
    split_paths.append(cleaned)
  for i in range(len(paths) - 1):
    if drives[i] != drives[i + 1]:
      raise ValueError("Paths don't have the same drive")
    if roots[i] != roots[i + 1]:
      raise ValueError("Can't mix rooted and not-rooted paths")
  d0: str
  r0: str
  d0, r0, _ = splitroot(paths[0].replace(_ALT, _SEP))
  common: list[str] = []
  if split_paths:
    s1: list[str] = split_paths[0]
    for sp in split_paths:
      if len(sp) < len(s1):
        s1 = sp
    for idx in range(len(s1)):
      c: str = s1[idx]
      ok: bool = True
      for sp in split_paths:
        if idx >= len(sp) or sp[idx] != c:
          ok = False
          break
      if not ok:
        break
      common.append(c)
  out: str = d0 + r0
  for part in common:
    out = join(out, part)
  return out


@immutable
def ismount(path: str) -> bool:
  abs_p: str = abspath(path)
  d: str
  r: str
  rest: str
  d, r, rest = splitroot(abs_p)
  if d and d[0] in _SEP_CHARS:
    return not rest
  if r and not rest:
    return True
  return False


@immutable
def _is_reserved_name(name: str) -> bool:
  if not name:
    return False
  if name[-1:] in ". ":
    if name not in {".", ".."}:
      return True
  upper: str = name.upper()
  if upper in {"CON", "PRN", "AUX", "NUL"}:
    return True
  if upper in {"CONIN$", "CONOUT$"}:
    return True
  if len(upper) >= 4 and upper[:3] == "COM":
    return True
  if len(upper) >= 4 and upper[:3] == "LPT":
    return True
  return False


@immutable
def isreserved(path: str) -> bool:
  tail: str
  *_, tail = splitroot(path)
  norm: str = tail.replace(_ALT, _SEP)
  segs: list[str] = norm.split(_SEP)
  for i in range(len(segs) - 1, -1, -1):
    if segs[i] and _is_reserved_name(segs[i]):
      return True
  return False


@native
def _path_stat_dev(path: str) -> int:
  ...


@native
def _path_stat_ino(path: str) -> int:
  ...


@immutable
def samestat(st1, st2) -> bool:
  return st1.st_ino == st2.st_ino and st1.st_dev == st2.st_dev


@immutable
def samefile(path1: str, path2: str) -> bool:
  return _path_stat_dev(path1) == _path_stat_dev(path2) and _path_stat_ino(path1) == _path_stat_ino(path2)


@immutable
def sameopenfile(fp1: int, fp2: int) -> bool:
  _ = fp1
  _ = fp2
  raise OSError()
