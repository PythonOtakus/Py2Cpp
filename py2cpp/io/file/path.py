"""``os.path``：纯路径与元数据检测（对齐 Python 3.13 ``ntpath`` / ``genericpath``）。

C 层：``exists`` / ``isFile`` / ``isDir`` / ``lExists`` / ``isLink`` / ``isJunction`` /
``isDevDrive`` / ``realPath``（``templates/io/-file.inl`` → ``io/file/path.inl`` 同批 paste_before）。
其余在 Python 侧实现，复用 ``py2cpp.text.str``。
"""
from ...builtins import *
from ...core.exceptions import OSError, ValueError
from ...util.list import list
from ...text import str

CurDir: str = "."
ParDir: str = ".."
ExtSep: str = "."
sep: str = "\\"
PathSep: str = ";"
AltSep: str = "/"
DefPath: str = ".;C:\\bin"
DevNull: str = "nul"
supportsUnicodeFilenames: bool = True

_Sep: str = sep
_Alt: str = AltSep
_SepChars: str = "\\/"
_Dot: str = CurDir
_Pardir: str = ParDir


@immutable
def _lastSepIndex(path: str) -> int:
  sepIndex: int = path.rfind(_Sep)
  alt: int = path.rfind(_Alt)
  if alt > sepIndex:
    sepIndex = alt
  return sepIndex


@immutable
def _normTail(path: str) -> str:
  return path.rstrip(_SepChars)


@immutable
def _normHead(path: str) -> str:
  if not path:
    return path
  out: str = path.lstrip(_SepChars)
  if not out:
    return _Sep
  return out


@immutable
def splitRoot(path: str) -> (str, str, str):
  """``(drive, root, tail)``（``ntpath.splitRoot`` 纯 Python 回退）。"""
  normp: str = path.replace(_Alt, _Sep)
  n: int = len(normp)
  if not n:
    return "", "", ""
  if normp[:1] == _Sep:
    if n >= 2 and normp[1:2] == _Sep:
      start: int = 2
      if n >= 8 and normp[:8].upper() == "\\\\?\\UNC\\":
        start = 8
      idx: int = normp.find(_Sep, start)
      if idx < 0:
        return path, "", ""
      idx2: int = normp.find(_Sep, idx + 1)
      if idx2 < 0:
        return path, "", ""
      return path[:idx2], path[idx2 : idx2 + 1], path[idx2 + 1 :]
    return "", normp[:1], normp[1:]
  if n >= 2 and normp[1:2] == ":":
    if n >= 3 and normp[2:3] == _Sep:
      return path[:2], path[2:3], path[3:]
    return path[:2], "", path[2:]
  return "", "", path


def join(path: str, other: str) -> str:
  """拼接两段路径（绝对后缀覆盖前缀）。"""
  pd: str
  pr: str
  pp: str
  pd, pr, pp = splitRoot(other)
  if pr or pd:
    return pd + pr + pp
  p: str = _normTail(path)
  o: str = _normHead(other)
  if not p:
    return o
  if not o:
    return p
  return p + _Sep + o


@immutable
def _joinPaths(base: str, parts: list[str]) -> str:
  out: str = base
  for p in parts:
    out = join(out, p)
  return out


@native
def exists(path: str) -> bool:
  """路径是否存在。"""
  ...


@native
def isFile(path: str) -> bool:
  """是否为常规文件。"""
  ...


@native
def isDir(path: str) -> bool:
  """是否为目录。"""
  ...


@native
def lExists(path: str) -> bool:
  """是否存在（不跟随符号链接失败时仍检测）。"""
  ...


@native
def isLink(path: str) -> bool:
  """是否为符号链接。"""
  ...


@native
def isJunction(path: str) -> bool:
  """是否为目录联结（Windows junction）。"""
  ...


@native
def isDevDrive(path: str) -> bool:
  """是否在 Dev Drive 卷上（暂恒 ``False``）。"""
  ...


@native
def realPath(path: str) -> str:
  """规范绝对路径（Win ``GetFullPathName`` / POSIX ``realPath``）。"""
  ...


def baseName(path: str) -> str:
  tail: str
  *_, tail = splitRoot(path)
  pos: int = _lastSepIndex(tail)
  if pos < 0:
    return tail
  if pos >= len(tail) - 1:
    return ""
  return tail[pos + 1 :]


def dirName(path: str) -> str:
  d: str
  r: str
  tail: str
  d, r, tail = splitRoot(path)
  pos: int = _lastSepIndex(tail)
  if pos < 0:
    return d + r
  if pos == 0:
    return d + r + _Sep
  head: str = tail[:pos]
  return d + r + _normTail(head)


def normPath(path: str) -> str:
  """折叠 ``.`` / ``..`` 与重复分隔符。"""
  if not path:
    return ""
  p: str = path.replace(_Alt, _Sep)
  drive: str
  root: str
  rest: str
  drive, root, rest = splitRoot(p)
  prefix: str = drive + root
  parts: list[str] = rest.split(_Sep)
  comps: list[str] = []
  for part in parts:
    if not part or part == _Dot:
      continue
    if part == _Pardir:
      if comps and comps[-1] != _Pardir:
        comps.pop()
      elif not root:
        comps.append(_Pardir)
      continue
    comps.append(part)
  if not prefix and not comps:
    comps.append(_Dot)
  out: str = prefix
  for i in range(len(comps)):
    if i > 0 or prefix:
      out += _Sep
    out += comps[i]
  return out


@immutable
def normCase(path: str) -> str:
  if not path:
    return path
  p: str = path.replace(_Alt, _Sep)
  return p.lower()


@immutable
def split(path: str) -> (str, str):
  d: str
  r: str
  tail: str
  d, r, tail = splitRoot(path)
  pos: int = len(tail)
  while pos > 0 and tail[pos - 1 : pos] not in _SepChars:
    pos -= 1
  head: str = tail[:pos]
  leaf: str = tail[pos:]
  return d + r + _normTail(head), leaf


@immutable
def splitDrive(path: str) -> (str, str):
  d: str
  r: str
  tail: str
  d, r, tail = splitRoot(path)
  return d, r + tail


@immutable
def splitExt(path: str) -> (str, str):
  sepIndex: int = _lastSepIndex(path)
  dotIndex: int = path.rfind(".")
  if dotIndex > sepIndex:
    stem: str = path[sepIndex + 1 : dotIndex]
    stemBody: str = stem.replace(".", "")
    if stemBody:
      return path[:dotIndex], path[dotIndex:]
  return path, ""


@immutable
def isAbs(path: str) -> bool:
  if not path:
    return False
  norm: str = path[:3].replace(_Alt, _Sep)
  if len(norm) >= 2 and norm[1:2] == ":" and len(norm) >= 3 and norm[2:3] == _Sep:
    return True
  if path.startsWith("\\\\"):
    return True
  if path.startsWith(_Sep) or path.startsWith(_Alt):
    return True
  if len(path) >= 2 and path[1:2] == ":":
    return True
  return False


@native
def getSize(path: str) -> int:
  """文件字节大小。"""
  ...


@native
def getMtime(path: str) -> float64:
  """修改时间。"""
  ...


@native
def getAtime(path: str) -> float64:
  """访问时间。"""
  ...


@native
def getCtime(path: str) -> float64:
  """创建/元数据变更时间。"""
  ...


@native
def _pathGetcwd() -> str:
  """当前工作目录（供 ``absPath``）。"""
  ...


@immutable
def commonPrefix(m: list[str]) -> str:
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
def absPath(path: str) -> str:
  p: str = normPath(path)
  if not isAbs(p):
    p = normPath(join(_pathGetcwd(), p))
  return realPath(p)


@immutable
def relPath(path: str, start: str = ".") -> str:
  if not path:
    raise ValueError("no path specified")
  startAbs: str = absPath(start)
  pathAbs: str = absPath(path)
  sd: str
  srest: str
  sd, _, srest = splitRoot(startAbs)
  pd: str
  prest: str
  pd, _, prest = splitRoot(pathAbs)
  if normCase(sd) != normCase(pd):
    raise ValueError("path is on mount")
  startParts: list[str] = srest.split(_Sep)
  if not srest:
    startParts = []
  pathParts: list[str] = prest.split(_Sep)
  if not prest:
    pathParts = []
  si: list[str] = []
  pi: list[str] = []
  for part in startParts:
    if part and part != _Dot:
      si.append(part)
  for part in pathParts:
    if part and part != _Dot:
      pi.append(part)
  commonLen: int = 0
  n: int = len(si)
  if len(pi) < n:
    n = len(pi)
  for i in range(n):
    if normCase(si[i]) != normCase(pi[i]):
      break
    commonLen = i + 1
  rel: list[str] = []
  for j in range(commonLen, len(si)):
    rel.append(_Pardir)
  for k in range(commonLen, len(pi)):
    rel.append(pi[k])
  if not rel:
    return _Dot
  out: str = rel[0]
  for ri in range(1, len(rel)):
    out = join(out, rel[ri])
  return out


@immutable
def commonPath(paths: list[str]) -> str:
  if not paths:
    raise ValueError("commonPath() arg is an empty iterable")
  drives: list[str] = []
  roots: list[str] = []
  splitPaths: list[list[str]] = []
  for p in paths:
    norm: str = p.replace(_Alt, _Sep)
    d: str
    r: str
    tail: str
    d, r, tail = splitRoot(norm)
    drives.append(d.lower())
    roots.append(r)
    parts: list[str] = tail.split(_Sep)
    cleaned: list[str] = []
    for part in parts:
      if part and part != _Dot:
        cleaned.append(part)
    splitPaths.append(cleaned)
  for i in range(len(paths) - 1):
    if drives[i] != drives[i + 1]:
      raise ValueError("Paths don't have the same drive")
    if roots[i] != roots[i + 1]:
      raise ValueError("Can't mix rooted and not-rooted paths")
  d0: str
  r0: str
  d0, r0, _ = splitRoot(paths[0].replace(_Alt, _Sep))
  common: list[str] = []
  if splitPaths:
    s1: list[str] = splitPaths[0]
    for sp in splitPaths:
      if len(sp) < len(s1):
        s1 = sp
    for idx in range(len(s1)):
      c: str = s1[idx]
      ok: bool = True
      for sp in splitPaths:
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
def isMount(path: str) -> bool:
  absP: str = absPath(path)
  d: str
  r: str
  rest: str
  d, r, rest = splitRoot(absP)
  if d and d[0] in _SepChars:
    return not rest
  if r and not rest:
    return True
  return False


@immutable
def _isReservedName(name: str) -> bool:
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
def isReserved(path: str) -> bool:
  tail: str
  *_, tail = splitRoot(path)
  norm: str = tail.replace(_Alt, _Sep)
  segs: list[str] = norm.split(_Sep)
  for i in range(len(segs) - 1, -1, -1):
    if segs[i] and _isReservedName(segs[i]):
      return True
  return False


@native
def _pathStatDev(path: str) -> int:
  ...


@native
def _pathStatIno(path: str) -> int:
  ...


@immutable
def sameStat(st1, st2) -> bool:
  return st1.stIno == st2.stIno and st1.stDev == st2.stDev


@immutable
def sameFile(path1: str, path2: str) -> bool:
  return _pathStatDev(path1) == _pathStatDev(path2) and _pathStatIno(path1) == _pathStatIno(path2)


@immutable
def sameOpenFile(fp1: int, fp2: int) -> bool:
  _ = fp1
  _ = fp2
  raise OSError()
