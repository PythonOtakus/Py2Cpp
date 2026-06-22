"""进程环境变量（对齐 Python 3.13 ``os.environ`` / ``ntpath.expandvars`` / ``expanduser``）。

C 层：``PyEnviron`` 映射方法（``templates/system/-environ.inl`` → ``system/environ.inl``）。
**不**暴露 ``putenv`` / ``getenv`` 模块函数。
"""
from ..builtins import *
from ..io.file.path import basename, dirname, join
from ..util.list import list, list_iterator
from ..text import str

_VARCHARS: str = (
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)
_QUOTE: str = "'"
_PERCENT: str = "%"
_BRACE: str = "{"
_RBRACE: str = "}"
_DOLLAR: str = "$"
_TILDE: str = "~"
_SEP_CHARS: str = "\\/"


@native_name("Py*")
@copyable
class Environ:
  """类字典进程环境映射（读写即时作用于 OS，对齐 ``os._Environ``）。"""

  def __init__(self):
    pass

  @native
  @immutable
  def __getitem__(self, key: str) -> str:
    ...

  @native
  def __setitem__(self, key: str, value: str) -> None:
    ...

  @native
  def __delitem__(self, key: str) -> None:
    ...

  @native
  @immutable
  def __contains__(self, key: str) -> bool:
    ...

  @native
  @immutable
  def get(self, key: str, default: str = "") -> str:
    ...

  @native
  @immutable
  def keys(self) -> list[str]:
    ...

  @immutable
  def __iter__(self) -> list_iterator[str]:
    return new(self.keys())

  @immutable
  def expandvars(self, path: str) -> str:
    """``$var`` / ``${var}`` / ``%var%``；未知变量保留原样（``ntpath.expandvars``）。"""
    if _DOLLAR not in path and _PERCENT not in path:
      return path
    res: str = ""
    index: int = 0
    pathlen: int = len(path)
    while index < pathlen:
      c: str = path[index : index + 1]
      if c == _QUOTE:
        path = path[index + 1 :]
        pathlen = len(path)
        try:
          index = path.index(_QUOTE)
          res += _QUOTE + path[: index + 1]
        except ValueError:
          res += _QUOTE + path
          index = pathlen - 1
      elif c == _PERCENT:
        if path[index + 1 : index + 2] == _PERCENT:
          res += c
          index += 1
        else:
          path = path[index + 1 :]
          pathlen = len(path)
          try:
            index = path.index(_PERCENT)
          except ValueError:
            res += _PERCENT + path
            index = pathlen - 1
          else:
            var: str = path[:index]
            if var in self:
              res += self[var]
            else:
              res += _PERCENT + var + _PERCENT
      elif c == _DOLLAR:
        if path[index + 1 : index + 2] == _DOLLAR:
          res += c
          index += 1
        elif path[index + 1 : index + 2] == _BRACE:
          path = path[index + 2 :]
          pathlen = len(path)
          try:
            index = path.index(_RBRACE)
          except ValueError:
            res += _DOLLAR + _BRACE + path
            index = pathlen - 1
          else:
            var = path[:index]
            if var in self:
              res += self[var]
            else:
              res += _DOLLAR + _BRACE + var + _RBRACE
        else:
          var = ""
          index += 1
          c = path[index : index + 1]
          while c and c in _VARCHARS:
            var += c
            index += 1
            c = path[index : index + 1]
          if var in self:
            res += self[var]
          else:
            res += _DOLLAR + var
          if c:
            index -= 1
      else:
        res += c
      index += 1
    return res

  @immutable
  def expanduser(self, path: str) -> str:
    """``~`` / ``~user``（``ntpath.expanduser``；依赖 ``USERPROFILE`` / ``HOMEPATH`` 等）。"""
    if not path.startswith(_TILDE):
      return path
    i: int = 1
    n: int = len(path)
    while i < n and path[i] not in _SEP_CHARS:
      i += 1
    userhome: str = ""
    if "USERPROFILE" in self:
      userhome = self["USERPROFILE"]
    elif "HOMEPATH" not in self:
      return path
    else:
      drive: str = self.get("HOMEDRIVE", "")
      userhome = join(drive, self["HOMEPATH"])
    if i != 1:
      target_user: str = path[1:i]
      current_user: str = self.get("USERNAME", "")
      if target_user != current_user:
        if current_user != basename(userhome):
          return path
        userhome = join(dirname(userhome), target_user)
    return userhome + path[i:]


environ: Environ = new()
