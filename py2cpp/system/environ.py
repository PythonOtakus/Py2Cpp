"""进程环境变量（对齐 Python 3.13 ``os.environ`` / ``ntpath.expandVars`` / ``expandUser``）。

``Environ`` 映射经 ``ffi.windows`` 读写 OS 环境块。**不**暴露 ``putenv`` / ``getenv`` 模块函数。
"""
from ..builtins import *
from ..core.exceptions import KeyError, OSError
from ..util.list import list
from ..text import str

from ffi.windows import (
  PyiErrorEnvvarNotFound,
  pyiFreeEnvironmentStringsA,
  pyiGetEnvironmentStrings,
  pyiGetEnvironmentVariableA,
  pyiGetLastError,
  pyiSetEnvironmentVariableA,
)

_Varchars: str = (
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)
_Quote: str = "'"
_Percent: str = "%"
_Brace: str = "{"
_Rbrace: str = "}"
_Dollar: str = "$"
_Tilde: str = "~"
_SepChars: str = "\\/"




@immutable
def _envKeyHas(key: str) -> bool:
  with key.useUtf8() as ckey:
    n: uint = pyiGetEnvironmentVariableA(ckey, "", 0)
  if n == 0:
    if pyiGetLastError() == PyiErrorEnvvarNotFound:
      return False
  return True


@immutable
def _envGetValue(key: str) -> str:
  with key.useUtf8() as ckey:
    return str.fromUtf8Writer(
      lambda p, capacity: pyiGetEnvironmentVariableA(ckey, p, capacity)
    )


@copyable
class Environ:
  """类字典进程环境映射（读写即时作用于 OS，对齐 ``os._Environ``）。"""

  def __init__(self):
    pass

  @immutable
  def __getitem__(self, key: str) -> str:
    if not _envKeyHas(key):
      raise KeyError(key)
    return _envGetValue(key)

  def __setitem__(self, key: str, value: str) -> None:
    with key.useUtf8() as ckey:
      with value.useUtf8() as cvalue:
        if pyiSetEnvironmentVariableA(ckey, cvalue) == 0:
          raise OSError()

  def __delitem__(self, key: str) -> None:
    if not _envKeyHas(key):
      raise KeyError(key)
    with key.useUtf8() as ckey:
      if pyiSetEnvironmentVariableA(ckey, None) == 0:
        err: uint = pyiGetLastError()
        if err != PyiErrorEnvvarNotFound:
          raise OSError()

  @immutable
  def __contains__(self, key: str) -> bool:
    return _envKeyHas(key)

  @immutable
  def get(self, key: str, default: str = "") -> str:
    if _envKeyHas(key):
      return _envGetValue(key)
    return default

  @immutable
  def keys(self) -> list[str]:
    out: list[str] = []
    block: utf8ptr = pyiGetEnvironmentStrings()
    if block is None:
      return out
    base: utf8ptr = block
    off: int = 0
    while base[off] != 0:
      i: int = 0
      eq: int = -1
      while base[off + i] != 0:
        if base[off + i] == ord("="):
          eq = i
        i += 1
      slen: int = i
      if eq > 0:
        out.append(str.fromSpanBytes(base.view[off:off + eq]))
      off += slen + 1
    pyiFreeEnvironmentStringsA(block)
    return out

  @immutable
  def __iter__(self) -> list[str]:
    return self.keys()

  @immutable
  def expandVars(self, path: str) -> str:
    """``$var`` / ``${var}`` / ``%var%``；未知变量保留原样（``ntpath.expandVars``）。"""
    if _Dollar not in path and _Percent not in path:
      return path
    res: str = ""
    index: int = 0
    pathlen: int = len(path)
    while index < pathlen:
      c: str = path[index : index + 1]
      if c == _Quote:
        path = path[index + 1 :]
        pathlen = len(path)
        try:
          index = path.index(_Quote)
          res += _Quote + path[: index + 1]
        except ValueError:
          res += _Quote + path
          index = pathlen - 1
      elif c == _Percent:
        if path[index + 1 : index + 2] == _Percent:
          res += c
          index += 1
        else:
          path = path[index + 1 :]
          pathlen = len(path)
          try:
            index = path.index(_Percent)
          except ValueError:
            res += _Percent + path
            index = pathlen - 1
          else:
            var: str = path[:index]
            if var in self:
              res += self[var]
            else:
              res += _Percent + var + _Percent
      elif c == _Dollar:
        if path[index + 1 : index + 2] == _Dollar:
          res += c
          index += 1
        elif path[index + 1 : index + 2] == _Brace:
          path = path[index + 2 :]
          pathlen = len(path)
          try:
            index = path.index(_Rbrace)
          except ValueError:
            res += _Dollar + _Brace + path
            index = pathlen - 1
          else:
            var = path[:index]
            if var in self:
              res += self[var]
            else:
              res += _Dollar + _Brace + var + _Rbrace
        else:
          var = ""
          index += 1
          c = path[index : index + 1]
          while c and c in _Varchars:
            var += c
            index += 1
            c = path[index : index + 1]
          if var in self:
            res += self[var]
          else:
            res += _Dollar + var
          if c:
            index -= 1
      else:
        res += c
      index += 1
    return res

  @immutable
  def expandUser(self, path: str) -> str:
    """``~`` / ``~user``（``ntpath.expandUser``；依赖 ``USERPROFILE`` / ``HOMEPATH`` 等）。"""
    if not path.startsWith(_Tilde):
      return path
    i: int = 1
    n: int = len(path)
    while i < n and path[i] not in _SepChars:
      i += 1
    userhome: str = ""
    if "USERPROFILE" in self:
      userhome = self["USERPROFILE"]
    elif "HOMEPATH" not in self:
      return path
    else:
      drive: str = self.get("HOMEDRIVE", "")
      userhome = drive + self["HOMEPATH"]
    if i != 1:
      targetUser: str = path[1:i]
      currentUser: str = self.get("USERNAME", "")
      if targetUser != currentUser:
        sepAt: int = userhome.rfind("\\")
        if sepAt < 0:
          sepAt = userhome.rfind("/")
        if sepAt < 0 or currentUser != userhome[sepAt + 1:]:
          return path
        userhome = userhome[:sepAt + 1] + targetUser
    return userhome + path[i:]


environ: Environ = new()
