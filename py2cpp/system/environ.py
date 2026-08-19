"""进程环境变量（对齐 Python 3.13 ``os.environ`` / ``ntpath.expandVars`` / ``expandUser``）。

``Environ`` 映射经 ``ffi.windows.windows`` 读写 OS 环境块。**不**暴露 ``putenv`` / ``getenv`` 模块函数。
"""
from ..builtins import *
from ..core.exceptions import KeyError, OSError
from ..io.file.path import baseName, dirName, join
from ..util.list import list
from ..text import str
from ..util.cbuf import cstrSlice, strCbuf

from ffi.windows.windows import (
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
def _strCbuf(s: str, cap: int) -> byte[:]:
  return strCbuf(s, cap)


@immutable
def _cstrSlice(p: CStr, start: int, n: int) -> str:
  return cstrSlice(p, start, n)


@immutable
def _envKeyHas(key: str) -> bool:
  kbuf: byte[:] = _strCbuf(key, 4096)
  n: uint = pyiGetEnvironmentVariableA(kbuf.view.at(0), "", 0)
  if n == 0:
    if pyiGetLastError() == PyiErrorEnvvarNotFound:
      return False
  return True


@immutable
def _envGetValue(key: str) -> str:
  kbuf: byte[:] = _strCbuf(key, 4096)
  vbuf: byte[:] = new(32767)
  n: uint = pyiGetEnvironmentVariableA(kbuf.view.at(0), vbuf.view.at(0), 32767)
  if n == 0:
    if pyiGetLastError() == PyiErrorEnvvarNotFound:
      return ""
  return _cstrSlice(vbuf.view.at(0), 0, int(n))


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
    kbuf: byte[:] = _strCbuf(key, 4096)
    vbuf: byte[:] = _strCbuf(value, 32767)
    if pyiSetEnvironmentVariableA(kbuf.view.at(0), vbuf.view.at(0)) == 0:
      raise OSError()

  def __delitem__(self, key: str) -> None:
    if not _envKeyHas(key):
      raise KeyError(key)
    kbuf: byte[:] = _strCbuf(key, 4096)
    if pyiSetEnvironmentVariableA(kbuf.view.at(0), None) == 0:
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
    block: CStr = pyiGetEnvironmentStrings()
    if block is None:
      return out
    base: CStr = block
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
        out.append(_cstrSlice(base, off, eq))
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
      userhome = join(drive, self["HOMEPATH"])
    if i != 1:
      targetUser: str = path[1:i]
      currentUser: str = self.get("USERNAME", "")
      if targetUser != currentUser:
        if currentUser != baseName(userhome):
          return path
        userhome = join(dirName(userhome), targetUser)
    return userhome + path[i:]


environ: Environ = new()
