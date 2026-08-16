"""``os``：进程环境与文件系统（对齐 Python 3.13 ``os`` / ``nt`` 子集）。

磁盘 API 由 ``templates/io/-file.inl`` paste_before 注入 ``io/file.inl``；``os.path`` 见 ``path.py``。
"""
from ...builtins import *
from ...core.exceptions import OSError, FileNotFoundError
from ...util.list import list
from ...text import str
from .path import (
  baseName as pathBaseName,
  dirName as pathDirName,
  exists as pathExists,
  isDir as pathIsDir,
  isFile as pathIsFile,
  isLink as pathIsLink,
  join as pathJoin,
  split as pathSplit,
)

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


@copyable
@native_name("CStat")
class CStat:
  """``CStat``（``os.stat`` / ``os.lstat`` 结果）。"""

  def __init__(self):
    self.stMode: int = 0
    self.stSize: int = 0
    self.stMtime: float64 = 0.0
    self.stAtime: float64 = 0.0
    self.stCtime: float64 = 0.0
    self.stDev: int = 0
    self.stIno: int = 0


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


@native
@native_name("fs_*")
def getCwd() -> str:
  """当前工作目录。"""
  ...


@immutable
@native_name("fs_*")
def getCwdb() -> bytes:
  return getCwd().encode()


@native
@native_name("fs_*")
def stat(pathName: str) -> CStat:
  """路径元数据；不存在时 ``FileNotFoundError``。"""
  ...


@native
@native_name("fs_*")
def lstat(pathName: str) -> CStat:
  """``stat`` 别名（Windows 上与 ``stat`` 相同）。"""
  ...


@native
@native_name("fs_*")
def listDir(pathName: str = ".") -> list[str]:
  """目录项名（不含 ``.`` / ``..``）。"""
  ...


@native
@native_name("fs_*")
def mkdir(pathName: str, mode: int = 0o777) -> None:
  """创建单级目录。"""
  ...


@native_name("fs_*")
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


@native
@native_name("fs_*")
def remove(pathName: str) -> None:
  """删除文件。"""
  ...


@native
@native_name("fs_*")
def unlink(pathName: str) -> None:
  """删除文件（``remove`` 别名）。"""
  ...


@native
@native_name("fs_*")
def rmdir(pathName: str) -> None:
  """删除空目录。"""
  ...


@native_name("fs_*")
def removeDirs(name: str) -> None:
  rmdir(name)
  parent: str = pathDirName(name)
  if parent and parent != name:
    removeDirs(parent)


@native
@native_name("fs_*")
def replace(src: str, dst: str) -> None:
  """原子替换（目标存在时覆盖）。"""
  ...


@native
@native_name("fs_*")
def rename(src: str, dst: str) -> None:
  """重命名（目标存在时失败）。"""
  ...


@native_name("fs_*")
def renames(old: str, new: str) -> None:
  head: str = pathDirName(new)
  if head and not pathExists(head):
    makeDirs(head)
  rename(old, new)


@native
@native_name("fs_*")
def chdir(pathName: str) -> None:
  """切换当前工作目录。"""
  ...


@native
@native_name("fs_*")
def access(pathName: str, mode: int) -> bool:
  """检测访问权限（``FOk`` / ``ROk`` / ``WOk`` / ``XOk``）。"""
  ...


@native
@native_name("fs_*")
def chmod(pathName: str, mode: int) -> None:
  """修改权限位。"""
  ...


@native
@native_name("fs_*")
def applyUtime(pathName: str, atime: float64, mtime: float64) -> None:
  ...


@native_name("fs_*")
def utime(pathName: str, times: (float64, float64)) -> None:
  """设置访问/修改时间（``(atime, mtime)``）。"""
  at: float64 = times[0]
  mt: float64 = times[1]
  applyUtime(pathName, at, mt)


@native
@native_name("fs_*")
def link(src: str, dst: str) -> None:
  """硬链接。"""
  ...


@native
@native_name("fs_*")
def symlink(src: str, dst: str) -> None:
  """符号链接。"""
  ...


@native
@native_name("fs_*")
def readLink(pathName: str) -> str:
  """读取符号链接目标。"""
  ...


@native_name("fs_*")
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


@native
@uncopyable
class ScandirIterator:
  """惰性 ``os.scandir`` 迭代器（Win ``FindNextFile`` / POSIX ``readdir``）。"""

  _path: str = ""
  _state: uintptr = 0

  def __init__(self, pathName: str = "."):
    ...

  def __del__(self):
    ...

  def close(self) -> None:
    ...

  def __iter__(self) -> Self:
    ...

  def __next__(self) -> IterResult[DirEntry, None]:
    ...


def scandir(pathName: str = ".") -> ScandirIterator:
  """目录扫描（惰性；对齐 CPython 3.13 ``os.scandir``）。"""
  return new(pathName)
