"""``os``：进程环境与文件系统（对齐 Python 3.13 ``os`` / ``nt`` 子集）。

磁盘与 ``os.path`` 均在 ``path.py``（纯 Python + ``ffi.crt`` / ``ffi.windows``）。
"""
from ...builtins import *
from ...core.exceptions import OSError, FileNotFoundError
from ...util.list import list
from ...text import str
from .path import (
  CStat,
  InvalidHandle,
  access,
  applyUtime,
  baseName as pathBaseName,
  chdir,
  chmod,
  dirName as pathDirName,
  exists as pathExists,
  findClose,
  findDataName,
  findFirst,
  findNext,
  getCwd,
  isDir as pathIsDir,
  isDotName,
  isFile as pathIsFile,
  isLink as pathIsLink,
  join as pathJoin,
  link,
  listDir,
  mkdir,
  readLink,
  remove,
  rename,
  replace,
  rmdir,
  split as pathSplit,
  stat,
  symlink,
)
from ffi.windows.windows import PyiWin32FindDataa

SIfdir: int = 0x4000
SIfreg: int = 0x8000
SIflnk: int = 0xA000
SIfchr: int = 0x2000
SIfblk: int = 0x6000
SIfifo: int = 0x1000
SIfsock: int = 0xC000
FOk: int = 0
ROk: int = 4
WOk: int = 2
XOk: int = 1

name: str = "nt"
sep: str = "\\"
AltSep: str = "/"
ExtSep: str = "."
PathSep: str = ";"
CurDir: str = "."
ParDir: str = ".."
DefPath: str = ".;C:\\bin"
DevNull: str = "nul"


@dataclass
class DirEntry:
  """``os.scandir`` 项（``name`` + 绝对 ``fullPath``）。"""

  name: str = ""
  fullPath: str = ""

  @immutable
  def isDir(self) -> bool:
    return pathIsDir(self.fullPath)

  @immutable
  def isFile(self) -> bool:
    return pathIsFile(self.fullPath)

  @immutable
  def isSymlink(self) -> bool:
    return pathIsLink(self.fullPath)

  @immutable
  def stat(self) -> CStat:
    return stat(self.fullPath)


@immutable
def getCwdb() -> bytes:
  return getCwd().encode()


@immutable
def lstat(pathName: str) -> CStat:
  """``stat`` 别名（Windows 上与 ``stat`` 相同）。"""
  return stat(pathName)


def makeDirs(name: str, mode: int = 0o777, existOk: bool = False) -> None:
  """递归创建目录（对齐 ``os.makeDirs``）。"""
  parts: (str, str) = pathSplit(name)
  head: str = parts[0]
  tail: str = parts[1]
  if tail:
    makeDirs(head, mode, existOk)
  if pathExists(name):
    if existOk and pathIsDir(name):
      return
    raise OSError()
  mkdir(name, mode)


@immutable
def unlink(pathName: str) -> None:
  """删除文件（``remove`` 别名）。"""
  remove(pathName)


def removeDirs(name: str) -> None:
  rmdir(name)
  parent: str = pathDirName(name)
  if parent and parent != name:
    removeDirs(parent)


def renames(old: str, new: str) -> None:
  head: str = pathDirName(new)
  if head and not pathExists(head):
    makeDirs(head)
  rename(old, new)


def utime(pathName: str, times: (float64, float64)) -> None:
  """设置访问/修改时间（``(atime, mtime)``）。"""
  at: float64 = times[0]
  mt: float64 = times[1]
  applyUtime(pathName, at, mt)


def walk(
  top: str,
  topdown: bool = True,
  followlinks: bool = False,
) -> GeneratorType[(str, list[str], list[str]), None, None]:
  """目录树遍历（``os.walk`` 子集；无 ``onerror`` 回调）。"""
  stack: list[str] = []
  stack.append(top)
  while stack:
    current: str = stack.pop()
    dirs: list[str] = []
    nonDirs: list[str] = []
    ent: DirEntry = new()
    for ent in scandir(current):
      if ent.isDir():
        if not followlinks or not ent.isSymlink():
          dirs.append(ent.name)
        else:
          nonDirs.append(ent.name)
      else:
        nonDirs.append(ent.name)
    if topdown:
      yield current, dirs, nonDirs
    idx: int = 0
    for idx in range(len(dirs) - 1, -1, -1):
      stack.append(pathJoin(current, dirs[idx]))
    if not topdown:
      yield current, dirs, nonDirs


@uncopyable
class ScandirIterator:
  """惰性 ``os.scandir`` 迭代器（Win ``FindNextFile``）。"""

  _path: str = ""
  _handle: uintptr = 0
  _data: PyiWin32FindDataa = new()
  _pending: bool = False
  _closed: bool = True

  def __init__(self, pathName: str = "."):
    self._path = pathName
    self._closed = False
    pair: (uintptr, PyiWin32FindDataa) = findFirst(pathName + "\\*")
    self._handle = pair[0]
    self._data = pair[1]
    if self._handle == InvalidHandle:
      self._closed = True
      self._pending = False
      raise FileNotFoundError()
    self._pending = True

  def __del__(self):
    self.close()

  def close(self) -> None:
    if self._closed:
      return
    findClose(self._handle)
    self._handle = InvalidHandle
    self._pending = False
    self._closed = True

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> DirEntry:
    while self._pending and not self._closed:
      name: str = findDataName(self._data)
      self._pending = findNext(self._handle, self._data)
      if isDotName(name):
        continue
      ent: DirEntry = new()
      ent.name = name
      ent.fullPath = pathJoin(self._path, name)
      return ent
    self.close()
    raise StopIteration


def scandir(pathName: str = ".") -> ScandirIterator:
  """目录扫描（惰性；对齐 CPython 3.13 ``os.scandir``）。"""
  return new(pathName)
