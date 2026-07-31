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
  S_IFBLK,
  S_IFCHR,
  S_IFDIR,
  S_IFIFO,
  S_IFLNK,
  S_IFREG,
  S_IFSOCK,
  chmod as fs_chmod,
  getcwd,
  link as fs_link,
  lstat,
  rename as fs_rename,
  replace as fs_replace,
  scandir,
  stat,
  c_stat,
  symlink as fs_symlink,
  readlink as fs_readlink,
  utime as fs_utime,
)
from .file import mkdir as fs_mkdir, remove as fs_remove, rmdir as fs_rmdir
from .file import DirEntry
from .file.path import (
  abspath,
  basename,
  dirname,
  exists,
  isabs,
  isdevdrive,
  isdir,
  isfile,
  isjunction,
  islink,
  ismount,
  isreserved,
  join,
  normcase,
  normpath,
  realpath,
  relpath,
  samefile as path_samefile,
  splitroot,
)

_PATH_SEP: str = "\\"
_PATH_ALT: str = "/"


@copyable
class Path:
  """路径值类型；内部保存规范化后的 ``str``（``__fspath__`` / ``__str__``）。"""

  @staticmethod
  @immutable
  def _stem_of_name(name: str) -> str:
    suf: str = Self._suffix_of_name(name)
    if not suf:
      return name
    return name[: len(name) - len(suf)]

  @staticmethod
  @immutable
  def _suffix_of_name(name: str) -> str:
    """``PurePath.suffix``（``pathlib`` 规则，非 ``os.path.splitext``）。"""
    i: int = name.rfind(".")
    if 0 < i < len(name) - 1:
      return name[i:]
    return ""

  @staticmethod
  @immutable
  def _norm_pattern(pattern: str) -> str:
    return normpath(pattern.replace(_PATH_ALT, _PATH_SEP))

  @staticmethod
  @immutable
  def _tail_segments(path: str) -> list[str]:
    rest: str
    *_, rest = splitroot(path)
    if not rest:
      return []
    norm: str = rest.replace(_PATH_ALT, _PATH_SEP)
    raw: list[str] = norm.split(_PATH_SEP)
    out: list[str] = []
    for part in raw:
      if part and part != ".":
        out.append(part)
    return out

  @staticmethod
  @immutable
  def _split_parts(path: str) -> (str, str, list[str]):
    drive: str
    root: str
    drive, root, _ = splitroot(path)
    return drive, root, Self._tail_segments(path)

  @staticmethod
  @immutable
  def _text_encoding(encoding: str) -> str:
    """``io.text_encoding`` 子集：空串视为默认 UTF-8（无 locale 探测）。"""
    if not encoding:
      return "utf-8"
    return encoding

  @staticmethod
  @immutable
  def _glob_select(
    root: str,
    pattern: str,
  ) -> Generator[str, None, None]:
    pat: str = Self._norm_pattern(pattern)
    if isabs(pat):
      raise OSError("Non-relative patterns are unsupported")
    if not pat:
      raise ValueError("Unacceptable pattern")
    parts: list[str] = Self._tail_segments(pat)
    if not parts:
      raise ValueError("Unacceptable pattern")
    yield from Self._glob_select_parts(root, parts, 0)

  @staticmethod
  def _glob_select_dir(
    base: str,
    part: str,
    parts: list[str],
    idx: int,
  ) -> Generator[str, None, None]:
    if not isdir(base):
      return
    ent: DirEntry = new()
    for ent in scandir(base):
      if not ent.name.glob(part):
        continue
      child: str = join(base, ent.name)
      yield from Self._glob_select_parts(child, parts, idx + 1)

  @staticmethod
  def _glob_select_parts(
    base: str,
    parts: list[str],
    idx: int,
  ) -> Generator[str, None, None]:
    if idx >= len(parts):
      if exists(base):
        yield base
      return
    part: str = parts[idx]
    if part == "**":
      yield from Self._glob_select_parts(base, parts, idx + 1)
      if not isdir(base):
        return
      ent: DirEntry = new()
      for ent in scandir(base):
        child: str = join(base, ent.name)
        if isdir(child):
          yield from Self._glob_select_parts(child, parts, idx)
      return
    yield from Self._glob_select_dir(base, part, parts, idx)

  @staticmethod
  @immutable
  def _str_to_bytes(raw: str) -> bytes:
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
  def _bytes_to_write_buf(data: bytes) -> char[:]:
    n: int = len(data)
    buf: char[:] = new(n)
    for i in range(n):
      buf[i] = data[i]
    return buf

  @staticmethod
  @immutable
  def _mode_is(st: c_stat, kind: int) -> bool:
    return (st.st_mode & 0xF000) == kind

  @staticmethod
  @immutable
  def cwd() -> Self:
    return new(getcwd())

  @staticmethod
  @immutable
  def home() -> Self:
    return new(environ.expanduser("~"))

  @staticmethod
  @immutable
  def from_uri(uri: str) -> Self:
    """``file:`` URI → ``Path``（子集：``file:///`` / ``file://host/``）。"""
    if not uri.startswith("file:"):
      raise ValueError("URI does not start with 'file:'")
    rest: str = uri[5:]
    if rest.startswith("//"):
      slash: int = rest.find("/", 2)
      if slash < 0:
        raise ValueError("Invalid file URI")
      rest = rest[slash + 1 :]
    rest = rest.lstrip("/")
    if not rest:
      return new("/")
    return new(rest.replace("/", _PATH_SEP))

  def __init__(self, path: str = ""):
    self._path: str = normpath(path)

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
    d, *_ = Self._split_parts(self._path)
    return d

  @property
  @immutable
  def root(self) -> str:
    r: str
    _, r, _ = Self._split_parts(self._path)
    return r

  @property
  @immutable
  def anchor(self) -> str:
    return self.drive + self.root

  @property
  @immutable
  def name(self) -> str:
    return basename(self._path)

  @property
  @immutable
  def parent(self) -> Self:
    return new(dirname(self._path))

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
    d, r, tail = Self._split_parts(self._path)
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
    return Self._stem_of_name(basename(self._path))

  @property
  @immutable
  def suffix(self) -> str:
    return Self._suffix_of_name(basename(self._path))

  @property
  @immutable
  def suffixes(self) -> list[str]:
    name: str = self.name
    if name.endswith("."):
      return []
    trimmed: str = name
    while trimmed.startswith("."):
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
  def as_posix(self) -> str:
    return self._path.replace("\\", "/")

  @immutable
  def as_uri(self) -> str:
    abs_p: Self = self.absolute()
    posix: str = abs_p.as_posix()
    if not posix:
      return "file:///"
    if posix.startswith("//"):
      return "file:" + posix
    return "file:///" + posix

  @immutable
  def is_absolute(self) -> bool:
    return isabs(self._path)

  @immutable
  def is_relative_to(self, other: str) -> bool:
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
  def is_reserved(self) -> bool:
    return isreserved(self._path)

  @immutable
  def match(self, path_pattern: str) -> bool:
    pat: str = Self._norm_pattern(path_pattern)
    pat_parts: list[str] = Self._tail_segments(pat)
    if not pat_parts:
      raise ValueError("empty pattern")
    path_parts: list[str] = Self._tail_segments(self._path)
    if len(path_parts) < len(pat_parts):
      return False
    if len(path_parts) > len(pat_parts) and isabs(pat):
      return False
    start: int = len(path_parts) - len(pat_parts)
    for i in range(len(pat_parts)):
      if not path_parts[start + i].glob(pat_parts[i]):
        return False
    return True

  @immutable
  def full_match(self, pattern: str) -> bool:
    pat: str = Self._norm_pattern(pattern)
    if isabs(pat):
      return normcase(self._path) == normcase(pat) or self._path.glob(pat)
    full: str = self._path
    if pat.find("**") >= 0:
      hit: str = ""
      for hit in Self._glob_select(dirname(full) if dirname(full) else ".", pat):
        if normcase(hit) == normcase(full):
          return True
      return False
    return full.glob(pat)

  @immutable
  def relative_to(self, other: str, walk_up: bool = False) -> Self:
    if walk_up:
      raise ValueError("walk_up is not supported")
    op: Self = new(other)
    if not self.is_relative_to(other):
      raise ValueError("path is not relative to base")
    return new(relpath(self._path, str(op)))

  @immutable
  def with_segments(self, *segments: str[:]) -> Self:
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
  def joinpath(self, *parts: str[:]) -> Self:
    out: str = self._path
    part: str = ""
    for part in parts:
      out = join(out, part)
    return new(out)

  @immutable
  def with_name(self, name: str) -> Self:
    return new(join(dirname(self._path), name))

  @immutable
  def with_stem(self, stem: str) -> Self:
    base: str = basename(self._path)
    return new(join(dirname(self._path), stem + Self._suffix_of_name(base)))

  @immutable
  def with_suffix(self, suffix: str) -> Self:
    """返回新 ``Path``；``suffix`` 须以 ``.`` 开头（对齐 CPython）。"""
    if not suffix or not suffix.startswith("."):
      raise ValueError("Invalid suffix")
    base: str = basename(self._path)
    root: str = Self._stem_of_name(base)
    return new(join(dirname(self._path), root + suffix))

  @immutable
  def absolute(self) -> Self:
    if self.is_absolute():
      return new(self._path)
    if not self._path:
      return new(abspath("."))
    return new(abspath(self._path))

  @immutable
  def resolve(self, strict: bool = False) -> Self:
    _ = strict
    base: str = self._path
    if not isabs(base):
      base = abspath(base)
    return new(realpath(base))

  @immutable
  def expanduser(self) -> Self:
    return new(environ.expanduser(self._path))

  @immutable
  def exists(self) -> bool:
    return exists(self._path)

  @immutable
  def is_dir(self) -> bool:
    return isdir(self._path)

  @immutable
  def is_file(self) -> bool:
    return isfile(self._path)

  @immutable
  def is_symlink(self) -> bool:
    return islink(self._path)

  @immutable
  def is_junction(self) -> bool:
    return isjunction(self._path)

  @immutable
  def is_mount(self) -> bool:
    return ismount(self._path)

  @immutable
  def is_block_device(self) -> bool:
    if not self.exists():
      return False
    return Self._mode_is(self.stat(), S_IFBLK)

  @immutable
  def is_char_device(self) -> bool:
    if not self.exists():
      return False
    return Self._mode_is(self.stat(), S_IFCHR)

  @immutable
  def is_fifo(self) -> bool:
    if not self.exists():
      return False
    return Self._mode_is(self.stat(), S_IFIFO)

  @immutable
  def is_socket(self) -> bool:
    if not self.exists():
      return False
    return Self._mode_is(self.stat(), S_IFSOCK)

  @immutable
  def stat(self) -> c_stat:
    return stat(self._path)

  @immutable
  def lstat(self) -> c_stat:
    return lstat(self._path)

  @immutable
  def samefile(self, other: str) -> bool:
    return path_samefile(self._path, str(Self(other)))

  @immutable
  def owner(self) -> str:
    raise OSError()

  @immutable
  def group(self) -> str:
    raise OSError()

  def iterdir(self) -> Generator[Self, None, None]:
    if not self.is_dir():
      raise FileNotFoundError()
    ent: DirEntry = new()
    for ent in scandir(self._path):
      child: Self = new(join(self._path, ent.name))
      yield child

  def glob(self, pattern: str) -> Generator[Self, None, None]:
    hit: str = ""
    for hit in Self._glob_select(self._path, pattern):
      child: Self = new(hit)
      yield child

  def rglob(self, pattern: str) -> Generator[Self, None, None]:
    if not pattern:
      raise ValueError("Unacceptable pattern")
    hit: str = ""
    for hit in Self._glob_select(self._path, "**" + _PATH_SEP + pattern):
      child: Self = new(hit)
      yield child

  @staticmethod
  def _walk_step(root: str, dirs: list[str], files: list[str]) -> WalkStep:
    return new(root_str=root, dirs=dirs, files=files)

  def walk(
    self,
    top_down: bool = True,
    on_error: bool = False,
    follow_symlinks: bool = False,
  ) -> Generator[WalkStep, None, None]:
    """目录树遍历（语义对齐 ``os.walk`` / ``pathlib.Path.walk``）。"""
    _ = on_error
    stack: list[str] = []
    stack.append(self._path)
    while stack:
      current: str = stack.pop()
      dirs: list[str] = []
      nondirs: list[str] = []
      ent: DirEntry = new()
      for ent in scandir(current):
        if ent.is_dir():
          if not follow_symlinks or not ent.is_symlink():
            dirs.append(ent.name)
          else:
            nondirs.append(ent.name)
        else:
          nondirs.append(ent.name)
      if top_down:
        yield Self._walk_step(current, dirs, nondirs)
      idx: int = 0
      for idx in range(len(dirs) - 1, -1, -1):
        stack.append(join(current, dirs[idx]))
      if not top_down:
        yield Self._walk_step(current, dirs, nondirs)

  def mkdir(
    self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False
  ) -> None:
    """创建目录（对齐 CPython 3.13 ``Path.mkdir``；无 ``try``/``except``，显式检测）。"""
    if self.exists():
      if self.is_dir():
        if exist_ok:
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

  def chmod(self, mode: int, follow_symlinks: bool = True) -> None:
    if follow_symlinks:
      fs_chmod(self._path, mode)
    else:
      self.lchmod(mode)

  def lchmod(self, mode: int) -> None:
    fs_chmod(self._path, mode)

  def touch(self, mode: int = 0o666, exist_ok: bool = True) -> None:
    if not self.exists():
      if not exist_ok:
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
    _ = Self._text_encoding(encoding)
    return new(self._path, mode)

  def read_text(
    self, encoding: str = "", errors: str = "", newline: str = ""
  ) -> str:
    _ = errors
    _ = newline
    _ = Self._text_encoding(encoding)
    f: TextIOWrapper = new(self._path, "r")
    data: str = f.read()
    f.close()
    return data

  def read_bytes(self) -> bytes:
    f: TextIOWrapper = new(self._path, "rb")
    data: str = f.read()
    f.close()
    return Self._str_to_bytes(data)

  def write_text(
    self,
    data: str,
    encoding: str = "",
    errors: str = "",
    newline: str = "",
  ) -> int:
    _ = errors
    _ = newline
    _ = Self._text_encoding(encoding)
    f: TextIOWrapper = new(self._path, "w")
    n: int = f.write(data)
    f.close()
    return n

  def write_bytes(self, data: bytes) -> int:
    f: TextIOWrapper = new(self._path, "wb")
    buf: char[:] = Self._bytes_to_write_buf(data)
    n: int = f.write(buf, len(data))
    f.close()
    return n

  def rmdir(self) -> None:
    fs_rmdir(self._path)

  def unlink(self, missing_ok: bool = False) -> None:
    """删除文件（对齐 ``pathlib.Path.unlink`` → ``os.unlink``）。"""
    if not self.exists():
      if missing_ok:
        return
      raise FileNotFoundError()
    if self.is_dir():
      raise OSError()
    fs_remove(self._path)

  def rename(self, target: str) -> Self:
    fs_rename(self._path, str(target))
    return new(str(target))

  def replace(self, target: str) -> Self:
    fs_replace(self._path, str(target))
    return new(str(target))

  def readlink(self) -> Self:
    return new(fs_readlink(self._path))

  def symlink_to(self, target: str, target_is_directory: bool = False) -> None:
    _ = target_is_directory
    fs_symlink(target, self._path)

  def hardlink_to(self, target: str) -> None:
    fs_link(target, self._path)


@copyable
class WalkStep:
  """``Path.walk`` 单步（``root`` 为 ``Path``；``dirs``/``files`` 为相对名，对齐 CPython 3.13）。"""

  root_str: str = ""
  dirs: list[str] = []
  files: list[str] = []

  @property
  @immutable
  def root(self) -> Path:
    return new(self.root_str)
