"""面向对象路径（对齐 Python 3.13 ``pathlib.Path`` / ``PurePath``；模块 ``py2cpp.io.path``）。

纯路径运算复用 ``io/file/path``；存在性检测与目录枚举委托 ``io.file`` C 层。
"""
from ..builtins import *
from ..core.exceptions import FileExistsError, FileNotFoundError, OSError, ValueError
from ..system.environ import environ
from ..system.time import time
from ..text.bytes import bytes
from ..text import str
from ..util.list import list
from . import TextIOWrapper
from .file import (
  SIfblk,
  SIfchr,
  SIfdir,
  SIfifo,
  SIflnk,
  SIfreg,
  SIfsock,
  chmod as fs_chmod,
  getCwd,
  link as fs_link,
  lstat,
  rename as fs_rename,
  replace as fs_replace,
  scandir,
  stat,
  CStat,
  symlink as fs_symlink,
  readLink as fs_readlink,
  utime as fs_utime,
)
from .file import mkdir as fs_mkdir, remove as fs_remove, rmdir as fs_rmdir
from .file import DirEntry
from .file.path import (
  absPath,
  baseName,
  dirName,
  exists,
  isAbs,
  isDevDrive,
  isDir,
  isFile,
  isJunction,
  isLink,
  isMount,
  isReserved,
  join,
  normCase,
  normPath,
  realPath,
  relPath,
  sameFile as path_samefile,
  splitRoot,
)

_PathSep: str = "\\"
_PathAlt: str = "/"


@copyable
class Path:
  """路径值类型；内部保存规范化后的 ``str``（``__fspath__`` / ``__str__``）。"""

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
    return normPath(pattern.replace(_PathAlt, _PathSep))

  @staticmethod
  @immutable
  def _tailSegments(path: str) -> list[str]:
    rest: str
    *_, rest = splitRoot(path)
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
    drive, root, _ = splitRoot(path)
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
    if isAbs(pat):
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
    if not isDir(base):
      return
    ent: DirEntry = new()
    for ent in scandir(base):
      if not ent.name.glob(part):
        continue
      child: str = join(base, ent.name)
      yield from Self._globSelectParts(child, parts, idx + 1)

  @staticmethod
  def _globSelectParts(
    base: str,
    parts: list[str],
    idx: int,
  ) -> GeneratorType[str, None, None]:
    if idx >= len(parts):
      if exists(base):
        yield base
      return
    part: str = parts[idx]
    if part == "**":
      yield from Self._globSelectParts(base, parts, idx + 1)
      if not isDir(base):
        return
      ent: DirEntry = new()
      for ent in scandir(base):
        child: str = join(base, ent.name)
        if isDir(child):
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
  def _modeIs(st: CStat, kind: int) -> bool:
    return (st.stMode & 0xF000) == kind

  @staticmethod
  @immutable
  def cwd() -> Self:
    return new(getCwd())

  @staticmethod
  @immutable
  def home() -> Self:
    return new(environ.expandUser("~"))

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
    self._path: str = normPath(path)

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
    return baseName(self._path)

  @property
  @immutable
  def parent(self) -> Self:
    return new(dirName(self._path))

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
    return Self._stemOfName(baseName(self._path))

  @property
  @immutable
  def suffix(self) -> str:
    return Self._suffixOfName(baseName(self._path))

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
    return new(join(self._path, key))

  @immutable
  def __rtruediv__(self, key: str) -> Self:
    return new(join(key, self._path))

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
    return isAbs(self._path)

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

  @immutable
  def isReserved(self) -> bool:
    return isReserved(self._path)

  @immutable
  def match(self, pathPattern: str) -> bool:
    pat: str = Self._normPattern(pathPattern)
    patParts: list[str] = Self._tailSegments(pat)
    if not patParts:
      raise ValueError("empty pattern")
    pathParts: list[str] = Self._tailSegments(self._path)
    if len(pathParts) < len(patParts):
      return False
    if len(pathParts) > len(patParts) and isAbs(pat):
      return False
    start: int = len(pathParts) - len(patParts)
    for i in range(len(patParts)):
      if not pathParts[start + i].glob(patParts[i]):
        return False
    return True

  @immutable
  def fullMatch(self, pattern: str) -> bool:
    pat: str = Self._normPattern(pattern)
    if isAbs(pat):
      return normCase(self._path) == normCase(pat) or self._path.glob(pat)
    full: str = self._path
    if pat.find("**") >= 0:
      hit: str = ""
      for hit in Self._globSelect(dirName(full) if dirName(full) else ".", pat):
        if normCase(hit) == normCase(full):
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
    return new(relPath(self._path, str(op)))

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
        out = join(out, seg)
    return new(out)

  @immutable
  def joinPath(self, *parts: str[:]) -> Self:
    out: str = self._path
    part: str = ""
    for part in parts:
      out = join(out, part)
    return new(out)

  @immutable
  def withName(self, name: str) -> Self:
    return new(join(dirName(self._path), name))

  @immutable
  def withStem(self, stem: str) -> Self:
    base: str = baseName(self._path)
    return new(join(dirName(self._path), stem + Self._suffixOfName(base)))

  @immutable
  def withSuffix(self, suffix: str) -> Self:
    """返回新 ``Path``；``suffix`` 须以 ``.`` 开头（对齐 CPython）。"""
    if not suffix or not suffix.startsWith("."):
      raise ValueError("Invalid suffix")
    base: str = baseName(self._path)
    root: str = Self._stemOfName(base)
    return new(join(dirName(self._path), root + suffix))

  @immutable
  def absolute(self) -> Self:
    if self.isAbsolute():
      return new(self._path)
    if not self._path:
      return new(absPath("."))
    return new(absPath(self._path))

  @immutable
  def resolve(self, strict: bool = False) -> Self:
    _ = strict
    base: str = self._path
    if not isAbs(base):
      base = absPath(base)
    return new(realPath(base))

  @immutable
  def expandUser(self) -> Self:
    return new(environ.expandUser(self._path))

  @immutable
  def exists(self) -> bool:
    return exists(self._path)

  @immutable
  def isDir(self) -> bool:
    return isDir(self._path)

  @immutable
  def isFile(self) -> bool:
    return isFile(self._path)

  @immutable
  def isSymlink(self) -> bool:
    return isLink(self._path)

  @immutable
  def isJunction(self) -> bool:
    return isJunction(self._path)

  @immutable
  def isMount(self) -> bool:
    return isMount(self._path)

  @immutable
  def isBlockDevice(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), SIfblk)

  @immutable
  def isCharDevice(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), SIfchr)

  @immutable
  def isFifo(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), SIfifo)

  @immutable
  def isSocket(self) -> bool:
    if not self.exists():
      return False
    return Self._modeIs(self.stat(), SIfsock)

  @immutable
  def stat(self) -> CStat:
    return stat(self._path)

  @immutable
  def lstat(self) -> CStat:
    return lstat(self._path)

  @immutable
  def sameFile(self, other: str) -> bool:
    return path_samefile(self._path, str(Self(other)))

  @immutable
  def owner(self) -> str:
    raise OSError()

  @immutable
  def group(self) -> str:
    raise OSError()

  def iterDir(self) -> GeneratorType[Self, None, None]:
    if not self.isDir():
      raise FileNotFoundError()
    ent: DirEntry = new()
    for ent in scandir(self._path):
      child: Self = new(join(self._path, ent.name))
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
      ent: DirEntry = new()
      for ent in scandir(current):
        if ent.isDir():
          if not followSymlinks or not ent.isSymlink():
            dirs.append(ent.name)
          else:
            nonDirs.append(ent.name)
        else:
          nonDirs.append(ent.name)
      if topDown:
        yield Self._walkStep(current, dirs, nonDirs)
      idx: int = 0
      for idx in range(len(dirs) - 1, -1, -1):
        stack.append(join(current, dirs[idx]))
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
    fs_mkdir(self._path, mode)

  def chmod(self, mode: int, followSymlinks: bool = True) -> None:
    if followSymlinks:
      fs_chmod(self._path, mode)
    else:
      self.lchmod(mode)

  def lchmod(self, mode: int) -> None:
    fs_chmod(self._path, mode)

  def touch(self, mode: int = 0o666, existOk: bool = True) -> None:
    if not self.exists():
      if not existOk:
        raise FileNotFoundError()
      f: TextIOWrapper = new(self._path, "wb")
      f.close()
    now: float64 = time()
    fs_utime(self._path, (now, now))

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
    fs_rmdir(self._path)

  def unlink(self, missingOk: bool = False) -> None:
    """删除文件（对齐 ``pathlib.Path.unlink`` → ``os.unlink``）。"""
    if not self.exists():
      if missingOk:
        return
      raise FileNotFoundError()
    if self.isDir():
      raise OSError()
    fs_remove(self._path)

  def rename(self, target: str) -> Self:
    fs_rename(self._path, str(target))
    return new(str(target))

  def replace(self, target: str) -> Self:
    fs_replace(self._path, str(target))
    return new(str(target))

  def readLink(self) -> Self:
    return new(fs_readlink(self._path))

  def symlinkTo(self, target: str, targetIsDirectory: bool = False) -> None:
    _ = targetIsDirectory
    fs_symlink(target, self._path)

  def hardlinkTo(self, target: str) -> None:
    fs_link(target, self._path)


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
