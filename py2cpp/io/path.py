"""面向对象路径（对齐 Python 3.13 ``pathlib.Path`` / ``PurePath``；模块 ``py2cpp.io.path``）。

纯路径计算与文件系统叶子均在本模块实现；C / Win32 调用统一经 ``ffi``。
"""
from ..builtins import *
from ..core.exceptions import FileExistsError, FileNotFoundError, OSError, ValueError
from ..system.environ import environ
from ..system.time import time
from ..text.bytes import bytes
from ..text import str
from ..util.list import list
from . import TextIOWrapper
from ffi.crt.direct import pyiChdir, pyiGetcwd, pyiMkdir, pyiRmdir
from ffi.crt.stat import PyiSIfdir, PyiSIfreg, PyiStat64I32, pyiStat64I32
from ffi.crt.stdio import pyiRemove
from ffi.crt.io import pyiAccess, pyiChmod
from ffi.crt.utime import PyiUtimbuf64, pyiUtime64
from ffi.windows import (
  PyiFileAttributeReparsePoint,
  PyiFileFlagBackupSemantics,
  PyiFileFlagOpenReparsePoint,
  PyiFileNameNormalized,
  PyiFileShareDelete,
  PyiFileShareRead,
  PyiFileShareWrite,
  PyiMovefileReplaceExisting,
  PyiOpenExisting,
  PyiWin32FindDataa,
  pyiCloseHandle,
  pyiCreateFileA,
  pyiCreateHardLinkA,
  pyiCreateSymbolicLinkA,
  pyiFindClose,
  pyiFindFirstFileA,
  pyiFindNextFileA,
  pyiGetFileAttributesA,
  pyiGetFinalPathNameByHandleA,
  pyiGetFullPathNameA,
  pyiMoveFileExA,
)

_PathBufferSize: int = 4096
_PathInvalidHandle: uintptr = -1
_PathInvalidFileAttr: uint = 4294967295
_PathGenericRead: uint = 2147483648
_PathSymlinkTag: uint = 2684354572
_PathJunctionTag: uint = 2684354563
_PathSIfblk: int = 0x6000
_PathSIfchr: int = 0x2000
_PathSIfdir: int = 0x4000
_PathSIfifo: int = 0x1000
_PathSIflnk: int = 0xA000
_PathSIfreg: int = 0x8000
_PathSIfsock: int = 0xC000

_PathSep: str = "\\"
_PathAlt: str = "/"


@copyable
@dataclass
class PathStat:
  """``Path.stat()`` 的文件元数据。"""

  stMode: int = 0
  stSize: int = 0
  stMtime: float64 = 0.0
  stAtime: float64 = 0.0
  stCtime: float64 = 0.0
  stDev: int = 0
  stIno: int = 0


@copyable
class Path:
  """路径值类型；内部保存规范化后的 ``str``（``__fspath__`` / ``__str__``）。"""

  @staticmethod
  @immutable
  def _lastSepIndex(path: str) -> int:
    sepIndex: int = path.rfind(_PathSep)
    alt: int = path.rfind(_PathAlt)
    if alt > sepIndex:
      sepIndex = alt
    return sepIndex

  @staticmethod
  @immutable
  def _normTail(path: str) -> str:
    return path.rstrip("\\/")

  @staticmethod
  @immutable
  def _normHead(path: str) -> str:
    if not path:
      return path
    out: str = path.lstrip("\\/")
    if not out:
      return _PathSep
    return out

  @staticmethod
  @immutable
  def _splitRoot(path: str) -> (str, str, str):
    normp: str = path.replace(_PathAlt, _PathSep)
    n: int = len(normp)
    if not n:
      return "", "", ""
    if normp[:1] == _PathSep:
      if n >= 2 and normp[1:2] == _PathSep:
        start: int = 2
        if n >= 8 and normp[:8].upper() == "\\\\?\\UNC\\":
          start = 8
        idx: int = normp.find(_PathSep, start)
        if idx < 0:
          return path, "", ""
        idx2: int = normp.find(_PathSep, idx + 1)
        if idx2 < 0:
          return path, "", ""
        return path[:idx2], path[idx2:idx2 + 1], path[idx2 + 1:]
      return "", normp[:1], normp[1:]
    if n >= 2 and normp[1:2] == ":":
      if n >= 3 and normp[2:3] == _PathSep:
        return path[:2], path[2:3], path[3:]
      return path[:2], "", path[2:]
    return "", "", path

  @staticmethod
  @immutable
  def _joinText(path: str, other: str) -> str:
    drive: str
    root: str
    tail: str
    drive, root, tail = Self._splitRoot(other)
    if root or drive:
      return drive + root + tail
    head: str = Self._normTail(path)
    suffix: str = Self._normHead(other)
    if not head:
      return suffix
    if not suffix:
      return head
    return head + _PathSep + suffix

  @staticmethod
  @immutable
  def _baseName(path: str) -> str:
    tail: str
    *_, tail = Self._splitRoot(path)
    pos: int = Self._lastSepIndex(tail)
    if pos < 0:
      return tail
    if pos >= len(tail) - 1:
      return ""
    return tail[pos + 1:]

  @staticmethod
  @immutable
  def _dirName(path: str) -> str:
    drive: str
    root: str
    tail: str
    drive, root, tail = Self._splitRoot(path)
    pos: int = Self._lastSepIndex(tail)
    if pos < 0:
      return drive + root
    if pos == 0:
      return drive + root + _PathSep
    return drive + root + Self._normTail(tail[:pos])

  @staticmethod
  @immutable
  def _normPath(path: str) -> str:
    if not path:
      return ""
    source: str = path.replace(_PathAlt, _PathSep)
    drive: str
    root: str
    rest: str
    drive, root, rest = Self._splitRoot(source)
    prefix: str = drive + root
    parts: list[str] = rest.split(_PathSep)
    comps: list[str] = []
    for part in parts:
      if not part or part == ".":
        continue
      if part == "..":
        if comps and comps[-1] != "..":
          comps.pop()
        elif not root:
          comps.append("..")
        continue
      comps.append(part)
    if not prefix and not comps:
      comps.append(".")
    out: str = prefix
    for i in range(len(comps)):
      if i > 0 or prefix:
        out += _PathSep
      out += comps[i]
    return out

  @staticmethod
  @immutable
  def _normCase(path: str) -> str:
    return path.replace(_PathAlt, _PathSep).lower()

  @staticmethod
  @immutable
  def _isAbsolute(path: str) -> bool:
    if not path:
      return False
    norm: str = path[:3].replace(_PathAlt, _PathSep)
    if len(norm) >= 2 and norm[1:2] == ":" and len(norm) >= 3 and norm[2:3] == _PathSep:
      return True
    if path.startsWith("\\\\") or path.startsWith(_PathSep) or path.startsWith(_PathAlt):
      return True
    return len(path) >= 2 and path[1:2] == ":"

  @staticmethod
  @immutable
  def _realPath(path: str) -> str:
    with path.useUtf8() as cpath:
      out: str = str.fromUtf8Writer(
        lambda p, capacity: pyiGetFullPathNameA(cpath, capacity, p, None)
      )
    if not out:
      raise OSError()
    return out

  @staticmethod
  @immutable
  def _absoluteText(path: str) -> str:
    value: str = Self._normPath(path)
    if not Self._isAbsolute(value):
      value = Self._joinText(str(Self.cwd()), value)
    return Self._realPath(value)

  @staticmethod
  @immutable
  def _relativeText(path: str, start: str) -> str:
    if not path:
      raise ValueError("no path specified")
    startAbs: str = Self._absoluteText(start)
    pathAbs: str = Self._absoluteText(path)
    startDrive: str
    startRest: str
    startDrive, _, startRest = Self._splitRoot(startAbs)
    pathDrive: str
    pathRest: str
    pathDrive, _, pathRest = Self._splitRoot(pathAbs)
    if Self._normCase(startDrive) != Self._normCase(pathDrive):
      raise ValueError("path is on mount")
    startParts: list[str] = []
    for part in startRest.split(_PathSep):
      if part and part != ".":
        startParts.append(part)
    pathParts: list[str] = []
    for part in pathRest.split(_PathSep):
      if part and part != ".":
        pathParts.append(part)
    shared: int = 0
    count: int = len(startParts)
    if len(pathParts) < count:
      count = len(pathParts)
    for i in range(count):
      if Self._normCase(startParts[i]) != Self._normCase(pathParts[i]):
        break
      shared = i + 1
    parts: list[str] = []
    for _ in range(shared, len(startParts)):
      parts.append("..")
    for i in range(shared, len(pathParts)):
      parts.append(pathParts[i])
    if not parts:
      return "."
    out: str = parts[0]
    for i in range(1, len(parts)):
      out = Self._joinText(out, parts[i])
    return out

  @staticmethod
  @immutable
  def _isMountText(path: str) -> bool:
    value: str = Self._absoluteText(path)
    drive: str
    root: str
    tail: str
    drive, root, tail = Self._splitRoot(value)
    if drive and drive[:1] in "\\/":
      return not tail
    if root and not tail:
      return True
    return False

  @staticmethod
  @immutable
  def _stemOfName(name: str) -> str:
    suf: str = Self._suffixOfName(name)
    if not suf:
      return name
    return name[: len(name) - len(suf)]

  @staticmethod
  @immutable
  def _suffixOfName(name: str) -> str:
    """``PurePath.suffix``（``pathlib`` 规则，非 ``os.path.splitExt``）。"""
    i: int = name.rfind(".")
    if 0 < i < len(name) - 1:
      return name[i:]
    return ""

  @staticmethod
  @immutable
  def _normPattern(pattern: str) -> str:
    return Self._normPath(pattern.replace(_PathAlt, _PathSep))

  @staticmethod
  @immutable
  def _tailSegments(path: str) -> list[str]:
    rest: str
    *_, rest = Self._splitRoot(path)
    if not rest:
      return []
    norm: str = rest.replace(_PathAlt, _PathSep)
    raw: list[str] = norm.split(_PathSep)
    out: list[str] = []
    for part in raw:
      if part and part != ".":
        out.append(part)
    return out

  @staticmethod
  @immutable
  def _splitParts(path: str) -> (str, str, list[str]):
    drive: str
    root: str
    drive, root, _ = Self._splitRoot(path)
    return drive, root, Self._tailSegments(path)

  @staticmethod
  @immutable
  def _textEncoding(encoding: str) -> str:
    """``io.text_encoding`` 子集：空串视为默认 UTF-8（无 locale 探测）。"""
    if not encoding:
      return "utf-8"
    return encoding

  @staticmethod
  @immutable
  def _globSelect(
    root: str,
    pattern: str,
  ) -> GeneratorType[str, None, None]:
    pat: str = Self._normPattern(pattern)
    if Self._isAbsolute(pat):
      raise OSError("Non-relative patterns are unsupported")
    if not pat:
      raise ValueError("Unacceptable pattern")
    parts: list[str] = Self._tailSegments(pat)
    if not parts:
      raise ValueError("Unacceptable pattern")
    yield from Self._globSelectParts(root, parts, 0)

  @staticmethod
  def _globSelectDir(
    base: str,
    part: str,
    parts: list[str],
    idx: int,
  ) -> GeneratorType[str, None, None]:
    if not Self._isDirText(base):
      return
    name: str = ""
    for name in Self._listDir(base):
      if not name.glob(part):
        continue
      child: str = Self._joinText(base, name)
      yield from Self._globSelectParts(child, parts, idx + 1)

  @staticmethod
  def _globSelectParts(
    base: str,
    parts: list[str],
    idx: int,
  ) -> GeneratorType[str, None, None]:
    if idx >= len(parts):
      if Self._existsText(base):
        yield base
      return
    part: str = parts[idx]
    if part == "**":
      yield from Self._globSelectParts(base, parts, idx + 1)
      if not Self._isDirText(base):
        return
      name: str = ""
      for name in Self._listDir(base):
        child: str = Self._joinText(base, name)
        if Self._isDirText(child):
          yield from Self._globSelectParts(child, parts, idx)
      return
    yield from Self._globSelectDir(base, part, parts, idx)

  @staticmethod
  @immutable
  def _strToBytes(raw: str) -> bytes:
    n: int = len(raw)
    if n == 0:
      empty: bytes = b""
      return empty
    buf: byte[:] = new(n)
    for i in range(n):
      buf[i] = int(raw[i])
    return new(buf)

  @staticmethod
  @immutable
  def _bytesToWriteBuf(data: bytes) -> char[:]:
    n: int = len(data)
    buf: char[:] = new(n)
    for i in range(n):
      buf[i] = data[i]
    return buf

  @staticmethod
  @immutable
  def _modeIs(st: PathStat, kind: int) -> bool:
    return (st.stMode & 0xF000) == kind

  @staticmethod
  @immutable
  def _fromNativeStat(st: PyiStat64I32) -> PathStat:
    out: PathStat = new()
    out.stMode = int(st.stMode)
    out.stSize = int(st.stSize)
    out.stMtime = float64(st.stMtime)
    out.stAtime = float64(st.stAtime)
    out.stCtime = float64(st.stCtime)
    out.stDev = int(st.stDev)
    out.stIno = int(st.stIno)
    return out

  @staticmethod
  @immutable
  def _tryStat(path: str) -> PathStat | None:
    raw: PyiStat64I32 = new()
    with path.useUtf8() as cpath:
      if pyiStat64I32(cpath, id(raw)) != 0:
        return None
    return Self._fromNativeStat(raw)

  @staticmethod
  @immutable
  def _existsText(path: str) -> bool:
    return Self._tryStat(path) is not None

  @staticmethod
  @immutable
  def _isDirText(path: str) -> bool:
    info: PathStat | None = Self._tryStat(path)
    if info is None:
      return False
    return (info.value.stMode & _PathSIfdir) != 0

  @staticmethod
  @immutable
  def _listDir(path: str) -> list[str]:
    query: str = Self._joinText(path, "*")
    findData: PyiWin32FindDataa = new()
    with query.useUtf8() as cquery:
      handle: uintptr = pyiFindFirstFileA(cquery, id(findData))
    if handle == _PathInvalidHandle:
      raise FileNotFoundError()
    out: list[str] = []
    pending: bool = True
    while pending:
      namePtr: utf8ptr = cast(findData.cFileName)
      name: str = str.fromSpanBytes(namePtr.view)
      if name not in {".", ".."}:
        out.append(name)
      pending = pyiFindNextFileA(handle, id(findData)) != 0
    pyiFindClose(handle)
    return out

  @staticmethod
  @immutable
  def _readReparseTag(path: str) -> uint:
    with path.useUtf8() as cpath:
      attr: uint = pyiGetFileAttributesA(cpath)
      if attr == _PathInvalidFileAttr or (attr & PyiFileAttributeReparsePoint) == 0:
        return 0
      data: PyiWin32FindDataa = new()
      handle: uintptr = pyiFindFirstFileA(cpath, id(data))
    if handle == _PathInvalidHandle:
      return 0
    pyiFindClose(handle)
    return data.dwReserved0
  @staticmethod
  @immutable
  def cwd() -> Self:
    buf: byte[:] = new(_PathBufferSize)
    result: utf8ptr = pyiGetcwd(buf.view.at(0), _PathBufferSize)
    if result is None:
      raise OSError()
    return new(str.fromSpanBytes(result.view))

  @staticmethod
  @immutable
  def home() -> Self:
    return new(environ.expandUser("~"))
  def chdir(self) -> None:
    with self._path.useUtf8() as path:
      if pyiChdir(path) != 0:
        raise OSError()

  @immutable
  def access(self, mode: int) -> bool:
    with self._path.useUtf8() as path:
      return pyiAccess(path, mode) == 0

  @staticmethod
  @immutable
  def fromUri(uri: str) -> Self:
    """``file:`` URI → ``Path``（子集：``file:///`` / ``file://host/``）。"""
    if not uri.startsWith("file:"):
      raise ValueError("URI does not start with 'file:'")
    rest: str = uri[5:]
    if rest.startsWith("//"):
      slash: int = rest.find("/", 2)
      if slash < 0:
        raise ValueError("Invalid file URI")
      rest = rest[slash + 1 :]
    rest = rest.lstrip("/")
    if not rest:
      return new("/")
    return new(rest.replace("/", _PathSep))

  def __init__(self, path: str = ""):
    self._path: str = Self._normPath(path)

  @immutable
  def __str__(self) -> str:
    return self._path

  @immutable
  def __repr__(self) -> str:
    return "Path('" + self._path + "')"

  @immutable
  def __cmp__(self, other: Self) -> int:
    return __cmp__(self._path, other._path)

  @immutable
  def __hash__(self) -> int:
    return hash(self._path)

  @property
  @immutable
  def drive(self) -> str:
    d: str
    d, *_ = Self._splitParts(self._path)
    return d

  @property
  @immutable
  def root(self) -> str:
    r: str
    _, r, _ = Self._splitParts(self._path)
    return r

  @property
  @immutable
  def anchor(self) -> str:
    return self.drive + self.root

  @property
  @immutable
  def name(self) -> str:
    return Self._baseName(self._path)

  @property
  @immutable
  def parent(self) -> Self:
    return new(Self._dirName(self._path))

  @property
  @immutable
  def parents(self) -> list[Self]:
    out: list[Self] = []
    p: Self = self.parent
    while p.name or p.anchor:
      out.append(p)
      nxt: Self = p.parent
      if str(nxt) == str(p):
        break
      p = nxt
    return out

  @property
  @immutable
  def parts(self) -> list[str]:
    d: str
    r: str
    tail: list[str]
    d, r, tail = Self._splitParts(self._path)
    if d or r:
      head: list[str] = []
      head.append(d + r)
      for seg in tail:
        head.append(seg)
      return head
    return tail

  @property
  @immutable
  def stem(self) -> str:
    return Self._stemOfName(Self._baseName(self._path))

  @property
  @immutable
  def suffix(self) -> str:
    return Self._suffixOfName(Self._baseName(self._path))

  @property
  @immutable
  def suffixes(self) -> list[str]:
    name: str = self.name
    if name.endsWith("."):
      return []
    trimmed: str = name
    while trimmed.startsWith("."):
      trimmed = trimmed[1:]
    chunks: list[str] = trimmed.split(".")
    if len(chunks) <= 1:
      return []
    out: list[str] = []
    for i in range(1, len(chunks)):
      out.append("." + chunks[i])
    return out

  @immutable
  def __truediv__(self, key: str) -> Self:
    return new(Self._joinText(self._path, key))

  @immutable
  def __rtruediv__(self, key: str) -> Self:
    return new(Self._joinText(key, self._path))

  @immutable
  def __fspath__(self) -> str:
    return self._path

  @immutable
  def asPosix(self) -> str:
    return self._path.replace("\\", "/")

  @immutable
  def asUri(self) -> str:
    absP: Self = self.absolute()
    posix: str = absP.asPosix()
    if not posix:
      return "file:///"
    if posix.startsWith("//"):
      return "file:" + posix
    return "file:///" + posix

  @immutable
  def isAbsolute(self) -> bool:
    return Self._isAbsolute(self._path)

  @immutable
  def isRelativeTo(self, other: str) -> bool:
    op: Self = new(other)
    if op == self:
      return True
    cur: Self = self.parent
    while cur.name or cur.anchor:
      if cur == op:
        return True
      nxt: Self = cur.parent
      if str(nxt) == str(cur):
        break
      cur = nxt
    return False

  @staticmethod
  @immutable
  def _isReservedName(name: str) -> bool:
    if not name:
      return False
    if name[-1:] in ". " and name not in {".", ".."}:
      return True
    upper: str = name.upper()
    if upper in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}:
      return True
    if len(upper) >= 4 and upper[:3] in {"COM", "LPT"}:
      return True
    return False

  @immutable
  def isReserved(self) -> bool:
    tail: str = self._path.replace(_PathAlt, _PathSep)
    if len(tail) >= 2 and tail[1:2] == ":":
      tail = tail[2:]
    for part in tail.split(_PathSep):
      if Self._isReservedName(part):
        return True
    return False
  @immutable
  def match(self, pathPattern: str) -> bool:
    pat: str = Self._normPattern(pathPattern)
    patParts: list[str] = Self._tailSegments(pat)
    if not patParts:
      raise ValueError("empty pattern")
    pathParts: list[str] = Self._tailSegments(self._path)
    if len(pathParts) < len(patParts):
      return False
    if len(pathParts) > len(patParts) and Self._isAbsolute(pat):
      return False
    start: int = len(pathParts) - len(patParts)
    for i in range(len(patParts)):
      if not pathParts[start + i].glob(patParts[i]):
        return False
    return True

  @immutable
  def fullMatch(self, pattern: str) -> bool:
    pat: str = Self._normPattern(pattern)
    if Self._isAbsolute(pat):
      return Self._normCase(self._path) == Self._normCase(pat) or self._path.glob(pat)
    full: str = self._path
    if pat.find("**") >= 0:
      hit: str = ""
      for hit in Self._globSelect(Self._dirName(full) if Self._dirName(full) else ".", pat):
        if Self._normCase(hit) == Self._normCase(full):
          return True
      return False
    return full.glob(pat)

  @immutable
  def relativeTo(self, other: str, walkUp: bool = False) -> Self:
    if walkUp:
      raise ValueError("walkUp is not supported")
    op: Self = new(other)
    if not self.isRelativeTo(other):
      raise ValueError("path is not relative to base")
    return new(Self._relativeText(self._path, str(op)))

  @immutable
  def withSegments(self, *segments: str[:]) -> Self:
    if not segments:
      return new(self._path)
    out: str = ""
    seg: str = ""
    for seg in segments:
      if not out:
        out = seg
      else:
        out = Self._joinText(out, seg)
    return new(out)

  @immutable
  def joinPath(self, *parts: str[:]) -> Self:
    out: str = self._path
    part: str = ""
    for part in parts:
      out = Self._joinText(out, part)
    return new(out)

  @immutable
  def withName(self, name: str) -> Self:
    return new(Self._joinText(Self._dirName(self._path), name))

  @immutable
  def withStem(self, stem: str) -> Self:
    base: str = Self._baseName(self._path)
    return new(Self._joinText(Self._dirName(self._path), stem + Self._suffixOfName(base)))

  @immutable
  def withSuffix(self, suffix: str) -> Self:
    """返回新 ``Path``；``suffix`` 须以 ``.`` 开头（对齐 CPython）。"""
    if not suffix or not suffix.startsWith("."):
      raise ValueError("Invalid suffix")
    base: str = Self._baseName(self._path)
    root: str = Self._stemOfName(base)
    return new(Self._joinText(Self._dirName(self._path), root + suffix))

  @immutable
  def absolute(self) -> Self:
    if self.isAbsolute():
      return new(self._path)
    if not self._path:
      return new(Self._absoluteText("."))
    return new(Self._absoluteText(self._path))

  @immutable
  def resolve(self, strict: bool = False) -> Self:
    _ = strict
    base: str = self._path
    if not Self._isAbsolute(base):
      base = Self._absoluteText(base)
    return new(Self._realPath(base))

  @immutable
  def expandUser(self) -> Self:
    return new(environ.expandUser(self._path))

  @immutable
  def exists(self) -> bool:
    return Self._tryStat(self._path) is not None

  @immutable
  def isDir(self) -> bool:
    info: PathStat | None = Self._tryStat(self._path)
    if info is None:
      return False
    return (info.value.stMode & _PathSIfdir) != 0

  @immutable
  def isFile(self) -> bool:
    info: PathStat | None = Self._tryStat(self._path)
    if info is None:
      return False
    return (info.value.stMode & _PathSIfreg) != 0

  @immutable
  def isSymlink(self) -> bool:
    return Self._readReparseTag(self._path) == _PathSymlinkTag

  @immutable
  def isJunction(self) -> bool:
    return Self._readReparseTag(self._path) == _PathJunctionTag

  @immutable
  def isMount(self) -> bool:
    return Self._isMountText(self._path)

  @immutable
  def isBlockDevice(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), _PathSIfblk)

  @immutable
  def isCharDevice(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), _PathSIfchr)

  @immutable
  def isFifo(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), _PathSIfifo)

  @immutable
  def isSocket(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), _PathSIfsock)

  @immutable
  def stat(self) -> PathStat:
    result: PathStat | None = Self._tryStat(self._path)
    if result is None:
      raise FileNotFoundError()
    return result

  @immutable
  def lstat(self) -> PathStat:
    return self.stat()

  @immutable
  def sameFile(self, other: str) -> bool:
    left: PathStat = self.stat()
    right: PathStat = Self(other).stat()
    return left.stDev == right.stDev and left.stIno == right.stIno

  @immutable
  def owner(self) -> str:
    raise OSError()

  @immutable
  def group(self) -> str:
    raise OSError()

  def iterDir(self) -> GeneratorType[Self, None, None]:
    if not self.isDir():
      raise FileNotFoundError()
    name: str = ""
    for name in Self._listDir(self._path):
      child: Self = new(Self._joinText(self._path, name))
      yield child

  def glob(self, pattern: str) -> GeneratorType[Self, None, None]:
    hit: str = ""
    for hit in Self._globSelect(self._path, pattern):
      child: Self = new(hit)
      yield child

  def rglob(self, pattern: str) -> GeneratorType[Self, None, None]:
    if not pattern:
      raise ValueError("Unacceptable pattern")
    hit: str = ""
    for hit in Self._globSelect(self._path, "**" + _PathSep + pattern):
      child: Self = new(hit)
      yield child

  @staticmethod
  def _walkStep(root: str, dirs: list[str], files: list[str]) -> WalkStep:
    return new(rootStr=root, dirs=dirs, files=files)

  def walk(
    self,
    topDown: bool = True,
    onError: bool = False,
    followSymlinks: bool = False,
  ) -> GeneratorType[WalkStep, None, None]:
    """目录树遍历（语义对齐 ``os.walk`` / ``pathlib.Path.walk``）。"""
    _ = onError
    stack: list[str] = []
    stack.append(self._path)
    while stack:
      current: str = stack.pop()
      dirs: list[str] = []
      nonDirs: list[str] = []
      name: str = ""
      for name in Self._listDir(current):
        child: Self = new(Self._joinText(current, name))
        if child.isDir():
          if not followSymlinks or not child.isSymlink():
            dirs.append(name)
          else:
            nonDirs.append(name)
        else:
          nonDirs.append(name)
      if topDown:
        yield Self._walkStep(current, dirs, nonDirs)
      idx: int = 0
      for idx in range(len(dirs) - 1, -1, -1):
        stack.append(Self._joinText(current, dirs[idx]))
      if not topDown:
        yield Self._walkStep(current, dirs, nonDirs)

  def mkdir(
    self, mode: int = 0o777, parents: bool = False, existOk: bool = False
  ) -> None:
    """创建目录（对齐 CPython 3.13 ``Path.mkdir``；无 ``try``/``except``，显式检测）。"""
    if self.exists():
      if self.isDir():
        if existOk:
          return
        raise FileExistsError()
      raise FileExistsError()
    par: Self = self.parent
    if not par.exists():
      if not parents:
        raise FileNotFoundError()
      if str(par) == str(self):
        raise FileNotFoundError()
      par.mkdir(mode, True, True)
    _ = mode
    with self._path.useUtf8() as path:
      if pyiMkdir(path) != 0:
        raise OSError()

  def chmod(self, mode: int, followSymlinks: bool = True) -> None:
    _ = followSymlinks
    with self._path.useUtf8() as path:
      if pyiChmod(path, mode) != 0:
        raise OSError()

  def lchmod(self, mode: int) -> None:
    self.chmod(mode, False)

  def touch(self, mode: int = 0o666, existOk: bool = True) -> None:
    if not self.exists():
      if not existOk:
        raise FileNotFoundError()
      f: TextIOWrapper = new(self._path, "wb")
      f.close()
    _ = mode
    stamp: PyiUtimbuf64 = new()
    now: float64 = time()
    stamp.actime = int64(now)
    stamp.modtime = int64(now)
    with self._path.useUtf8() as path:
      if pyiUtime64(path, id(stamp)) != 0:
        raise OSError()

  def open(
    self,
    mode: str = "r",
    buffering: int = -1,
    encoding: str = "",
    errors: str = "",
    newline: str = "",
  ) -> TextIOWrapper:
    """对齐 ``pathlib.Path.open``；``buffering`` / ``errors`` / ``newline`` 暂未实现。"""
    _ = buffering
    _ = errors
    _ = newline
    _ = Self._textEncoding(encoding)
    return new(self._path, mode)

  def readText(
    self, encoding: str = "", errors: str = "", newline: str = ""
  ) -> str:
    _ = errors
    _ = newline
    _ = Self._textEncoding(encoding)
    f: TextIOWrapper = new(self._path, "r")
    data: str = f.read()
    f.close()
    return data

  def readBytes(self) -> bytes:
    f: TextIOWrapper = new(self._path, "rb")
    data: str = f.read()
    f.close()
    return Self._strToBytes(data)

  def writeText(
    self,
    data: str,
    encoding: str = "",
    errors: str = "",
    newline: str = "",
  ) -> int:
    _ = errors
    _ = newline
    _ = Self._textEncoding(encoding)
    f: TextIOWrapper = new(self._path, "w")
    n: int = f.write(data)
    f.close()
    return n

  def writeBytes(self, data: bytes) -> int:
    f: TextIOWrapper = new(self._path, "wb")
    buf: char[:] = Self._bytesToWriteBuf(data)
    n: int = f.write(buf, len(data))
    f.close()
    return n

  def rmdir(self) -> None:
    with self._path.useUtf8() as path:
      if pyiRmdir(path) != 0:
        raise OSError()

  def unlink(self, missingOk: bool = False) -> None:
    """删除文件（对齐 ``pathlib.Path.unlink`` → ``os.unlink``）。"""
    if not self.exists():
      if missingOk:
        return
      raise FileNotFoundError()
    if self.isDir():
      raise OSError()
    with self._path.useUtf8() as path:
      if pyiRemove(path) != 0:
        raise OSError()

  def rename(self, target: str) -> Self:
    with self._path.useUtf8() as src:
      with target.useUtf8() as dst:
        if pyiMoveFileExA(src, dst, 0) == 0:
          raise OSError()
    return new(str(target))

  def replace(self, target: str) -> Self:
    with self._path.useUtf8() as src:
      with target.useUtf8() as dst:
        if pyiMoveFileExA(src, dst, PyiMovefileReplaceExisting) == 0:
          raise OSError()
    return new(str(target))

  def readLink(self) -> Self:
    flags: uint = PyiFileFlagOpenReparsePoint | PyiFileFlagBackupSemantics
    share: uint = PyiFileShareRead | PyiFileShareWrite | PyiFileShareDelete
    with self._path.useUtf8() as cpath:
      handle: uintptr = pyiCreateFileA(cpath, _PathGenericRead, share, None, PyiOpenExisting, flags, 0)
    if handle == _PathInvalidHandle:
      raise OSError()
    try:
      return new(str.fromUtf8Writer(
        lambda p, capacity: pyiGetFinalPathNameByHandleA(
          handle, p, capacity, PyiFileNameNormalized
        )
      ))
    finally:
      pyiCloseHandle(handle)

  def symlinkTo(self, target: str, targetIsDirectory: bool = False) -> None:
    _ = targetIsDirectory
    with target.useUtf8() as src:
      with self._path.useUtf8() as dst:
        if pyiCreateSymbolicLinkA(dst, src, 0) == 0:
          raise OSError()

  def hardlinkTo(self, target: str) -> None:
    with target.useUtf8() as src:
      with self._path.useUtf8() as dst:
        if pyiCreateHardLinkA(dst, src, None) == 0:
          raise OSError()


@copyable
class WalkStep:
  """``Path.walk`` 单步（``root`` 为 ``Path``；``dirs``/``files`` 为相对名，对齐 CPython 3.13）。"""

  rootStr: str = ""
  dirs: list[str] = []
  files: list[str] = []

  @property
  @immutable
  def root(self) -> Path:
    return new(self.rootStr)
