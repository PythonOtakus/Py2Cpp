"""``os``：进程环境与文件系统（对齐 Python 3.13 ``os`` / ``nt`` 子集）。

磁盘 API 由 ``templates/io/-file.inl`` paste_before 注入 ``io/file.inl``；``os.path`` 见 ``path.py``。
"""
from ...builtins import *
from ...core.exceptions import OSError, FileNotFoundError
from ...util.list import list
from ...text import str
from .path import (
  basename as path_basename,
  dirname as path_dirname,
  exists as path_exists,
  isdir as path_isdir,
  isfile as path_isfile,
  islink as path_islink,
  join as path_join,
  split as path_split,
)

S_IFDIR: int = 0x4000
S_IFREG: int = 0x8000
S_IFLNK: int = 0xA000
S_IFCHR: int = 0x2000
S_IFBLK: int = 0x6000
S_IFIFO: int = 0x1000
S_IFSOCK: int = 0xC000
F_OK: int = 0
R_OK: int = 4
W_OK: int = 2
X_OK: int = 1

name: str = "nt"
sep: str = "\\"
altsep: str = "/"
extsep: str = "."
pathsep: str = ";"
curdir: str = "."
pardir: str = ".."
defpath: str = ".;C:\\bin"
devnull: str = "nul"


@copyable
class c_stat:
  """``c_stat``（``os.stat`` / ``os.lstat`` 结果）。"""

  def __init__(self):
    self.st_mode: int = 0
    self.st_size: int = 0
    self.st_mtime: float64 = 0.0
    self.st_atime: float64 = 0.0
    self.st_ctime: float64 = 0.0
    self.st_dev: int = 0
    self.st_ino: int = 0


@dataclass
class DirEntry:
  """``os.scandir`` 项（``name`` + 绝对 ``full_path``）。"""

  name: str = ""
  full_path: str = ""

  @immutable
  def is_dir(self) -> bool:
    return path_isdir(self.full_path)

  @immutable
  def is_file(self) -> bool:
    return path_isfile(self.full_path)

  @immutable
  def is_symlink(self) -> bool:
    return path_islink(self.full_path)

  @immutable
  def stat(self) -> c_stat:
    return stat(self.full_path)


@native
@native_name("fs_*")
def getcwd() -> str:
  """当前工作目录。"""
  ...


@immutable
@native_name("fs_*")
def getcwdb() -> bytes:
  return getcwd().encode()


@native
@native_name("fs_*")
def stat(pathname: str) -> c_stat:
  """路径元数据；不存在时 ``FileNotFoundError``。"""
  ...


@native
@native_name("fs_*")
def lstat(pathname: str) -> c_stat:
  """``stat`` 别名（Windows 上与 ``stat`` 相同）。"""
  ...


@native
@native_name("fs_*")
def listdir(pathname: str = ".") -> list[str]:
  """目录项名（不含 ``.`` / ``..``）。"""
  ...


@native
@native_name("fs_*")
def mkdir(pathname: str, mode: int = 0o777) -> None:
  """创建单级目录。"""
  ...


@native_name("fs_*")
def makedirs(name: str, mode: int = 0o777, exist_ok: bool = False) -> None:
  """递归创建目录（对齐 ``os.makedirs``）。"""
  parts: (str, str) = path_split(name)
  head: str = parts[0]
  tail: str = parts[1]
  if tail:
    makedirs(head, mode, exist_ok)
  if path_exists(name):
    if exist_ok and path_isdir(name):
      return
    raise OSError()
  mkdir(name, mode)


@native
@native_name("fs_*")
def remove(pathname: str) -> None:
  """删除文件。"""
  ...


@native
@native_name("fs_*")
def unlink(pathname: str) -> None:
  """删除文件（``remove`` 别名）。"""
  ...


@native
@native_name("fs_*")
def rmdir(pathname: str) -> None:
  """删除空目录。"""
  ...


@native_name("fs_*")
def removedirs(name: str) -> None:
  rmdir(name)
  parent: str = path_dirname(name)
  if parent and parent != name:
    removedirs(parent)


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
  head: str = path_dirname(new)
  if head and not path_exists(head):
    makedirs(head)
  rename(old, new)


@native
@native_name("fs_*")
def chdir(pathname: str) -> None:
  """切换当前工作目录。"""
  ...


@native
@native_name("fs_*")
def access(pathname: str, mode: int) -> bool:
  """检测访问权限（``F_OK`` / ``R_OK`` / ``W_OK`` / ``X_OK``）。"""
  ...


@native
@native_name("fs_*")
def chmod(pathname: str, mode: int) -> None:
  """修改权限位。"""
  ...


@native
@native_name("fs_*")
def apply_utime(pathname: str, atime: float64, mtime: float64) -> None:
  ...


@native_name("fs_*")
def utime(pathname: str, times: (float64, float64)) -> None:
  """设置访问/修改时间（``(atime, mtime)``）。"""
  at: float64 = times[0]
  mt: float64 = times[1]
  apply_utime(pathname, at, mt)


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
def readlink(pathname: str) -> str:
  """读取符号链接目标。"""
  ...


@native_name("fs_*")
def walk(
  top: str,
  topdown: bool = True,
  followlinks: bool = False,
) -> Generator[(str, list[str], list[str]), None, None]:
  """目录树遍历（``os.walk`` 子集；无 ``onerror`` 回调）。"""
  stack: list[str] = []
  stack.append(top)
  while stack:
    current: str = stack.pop()
    dirs: list[str] = []
    nondirs: list[str] = []
    ent: DirEntry = new()
    for ent in scandir(current):
      if ent.is_dir():
        if not followlinks or not ent.is_symlink():
          dirs.append(ent.name)
        else:
          nondirs.append(ent.name)
      else:
        nondirs.append(ent.name)
    if topdown:
      yield current, dirs, nondirs
    idx: int = 0
    for idx in range(len(dirs) - 1, -1, -1):
      stack.append(path_join(current, dirs[idx]))
    if not topdown:
      yield current, dirs, nondirs


@native
@native_name("ScandirIterator")
class scandir_iterator:
  """惰性 ``os.scandir`` 迭代器（Win ``FindNextFile`` / POSIX ``readdir``）。"""

  _path: str = ""
  _state: uintptr = 0

  def __init__(self, pathname: str = "."):
    ...

  def __del__(self):
    ...

  def close(self) -> None:
    ...

  def __iter__(self) -> Self:
    ...

  def __next__(self) -> IterResult[DirEntry, None]:
    ...


def scandir(pathname: str = ".") -> scandir_iterator:
  """目录扫描（惰性；对齐 CPython 3.13 ``os.scandir``）。"""
  return new(pathname)
