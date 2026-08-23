"""外部子进程（Python ``subprocess.Popen`` 受限子集）。

``Popen`` 只启动明确的 ``list[str]`` 参数，不隐式经过 shell。
语义在 Python + ``ffi.windows`` / ``ffi.crt``；无业务模板 ``.inl``。
"""
from ..builtins import *
from ..core.exceptions import OSError, RuntimeError, ValueError
from ..text import str
from ..util.dict import dict
from ..util.list import list
from ffi.crt.stdlib import pyiFree, pyiMalloc
from ffi.crt.string import pyiStrlen
from ffi.windows import (
  PyiCreateUnicodeEnvironment,
  PyiFileShareRead,
  PyiFileShareWrite,
  PyiHandleFlagInherit,
  PyiInfinite,
  PyiOpenExisting,
  PyiProcessInformation,
  PyiSecurityAttributes,
  PyiStartfUsestdhandles,
  PyiStartupinfoW,
  PyiWaitTimeout,
  pyiCloseHandle,
  pyiCreateFileW,
  pyiCreatePipe,
  pyiCreateProcessW,
  pyiGetExitCodeProcess,
  pyiGetStdHandle,
  pyiGetTickCount64,
  pyiPeekNamedPipe,
  pyiReadFile,
  pyiSetHandleInformation,
  pyiTerminateProcess,
  pyiWaitForSingleObject,
  pyiWriteFile,
)

Pipe: int = -1
DevNull: int = -2

_StdInputHandle: uint = 4294967286
_StdOutputHandle: uint = 4294967285
_StdErrorHandle: uint = 4294967284
_WaitObject0: uint = 0
_GenericRead: uint = 0x80000000
_GenericWrite: uint = 0x40000000
_CmdlineCap: int = 32768
_EnvBlockCap: int = 65536
_SecurityAttributesSize: uint = 24
_StartupinfoWSize: uint = 104


@native
@native_name("::py2cpp::console::py_popen::_startupSetStdHandles")
def _startupSetStdHandles(
  si: PyiStartupinfoW,
  stdinH: uintptr,
  stdoutH: uintptr,
  stderrH: uintptr,
) -> None:
  ...


@native
@native_name("::py2cpp::console::py_popen::_processInfoProcessHandle")
def _processInfoProcessHandle(pi: PyiProcessInformation) -> uintptr:
  ...


@native
@native_name("::py2cpp::console::py_popen::_processInfoThreadHandle")
def _processInfoThreadHandle(pi: PyiProcessInformation) -> uintptr:
  ...


@dataclass
class ProcessResult:
  """已结束子进程的参数、退出码和已捕获输出。"""

  args: list[str] @optional = []
  returnCode: int = 0
  stdout: str = ""
  stderr: str = ""


@immutable
def _closeHandle(h: uintptr) -> None:
  if h in {uintptr(0), uintptr(-1)}:
    return
  pyiCloseHandle(h)


@immutable
def _inheritSecurityAttributes() -> PyiSecurityAttributes:
  sa: PyiSecurityAttributes = new(
    nLength=_SecurityAttributesSize,
    lpSecurityDescriptor=uintptr(0),
    bInheritHandle=1,
  )
  return sa


@immutable
def _createPipePair() -> (uintptr, uintptr):
  sa: PyiSecurityAttributes = _inheritSecurityAttributes()
  readH: uintptr = 0
  writeH: uintptr = 0
  if pyiCreatePipe(id(readH), id(writeH), id(sa), uint(0)) == 0:
    raise OSError()
  pyiSetHandleInformation(readH, PyiHandleFlagInherit, uint(0))
  return (readH, writeH)


@immutable
def _nulHandle(write: bool) -> uintptr:
  sa: PyiSecurityAttributes = _inheritSecurityAttributes()
  access: uint = _GenericWrite if write else _GenericRead
  nulName: str = "NUL"
  with nulName.useUtf16() as name:
    h: uintptr = pyiCreateFileW(
      name,
      access,
      PyiFileShareRead | PyiFileShareWrite,
      id(sa),
      PyiOpenExisting,
      uint(0),
      uintptr(0),
    )
  if h == uintptr(-1):
    raise OSError()
  return h


@immutable
def _stdStreamHandle(fd: int) -> uintptr:
  if fd == 0:
    return pyiGetStdHandle(_StdInputHandle)
  if fd == 1:
    return pyiGetStdHandle(_StdOutputHandle)
  return pyiGetStdHandle(_StdErrorHandle)


@immutable
def _resolveIoHandle(mode: int, pipeRead: uintptr, pipeWrite: uintptr, stdFd: int, writeEnd: bool) -> uintptr:
  if mode == Pipe:
    return pipeWrite if writeEnd else pipeRead
  if mode == DevNull:
    return _nulHandle(writeEnd)
  return _stdStreamHandle(stdFd)


@immutable
def _argNeedsQuote(s: str) -> bool:
  for i in range(len(s)):
    c: char = s[i]
    if c in " \t\"":
      return True
  return False


@immutable
def _appendWide(dst: uint16[:], at: int, src: uint16[:], end: int) -> int:
  i: int = 0
  while i < end and at + 1 < _CmdlineCap:
    dst[at] = src[i]
    at += 1
    i += 1
  return at


@immutable
def _appendQuotedArg(dst: uint16[:], at: int, arg: str) -> int:
  w: uint16[:] = arg.toArrayUtf16()
  wlen: int = len(w) - 1
  if not _argNeedsQuote(arg):
    return _appendWide(dst, at, w, wlen)
  if at + 1 < _CmdlineCap:
    dst[at] = uint16(34)
    at += 1
  for i in range(wlen):
    if at + 2 >= _CmdlineCap:
      break
    if w[i] == uint16(34):
      dst[at] = uint16(92)
      at += 1
    dst[at] = w[i]
    at += 1
  if at + 1 < _CmdlineCap:
    dst[at] = uint16(34)
    at += 1
  return at


@immutable
def _buildCmdline(args: list[str]) -> uint16[:]:
  buf: uint16[:] = new(_CmdlineCap)
  at: int = 0
  n: int = len(args)
  for i in range(n):
    if i > 0 and at + 1 < _CmdlineCap:
      buf[at] = uint16(32)
      at += 1
    at = _appendQuotedArg(buf, at, args[i])
  if at < _CmdlineCap:
    buf[at] = uint16(0)
  return buf


@immutable
def _appendEnvPair(block: uint16[:], at: int, key: str, val: str) -> int:
  wk: uint16[:] = key.toArrayUtf16()
  wv: uint16[:] = val.toArrayUtf16()
  klen: int = len(wk) - 1
  vlen: int = len(wv) - 1
  at = _appendWide(block, at, wk, klen)
  if at + 2 < _EnvBlockCap:
    block[at] = uint16(61)
    at += 1
  at = _appendWide(block, at, wv, vlen)
  if at + 1 < _EnvBlockCap:
    block[at] = uint16(0)
    at += 1
  return at


@immutable
def _buildEnvBlock(env: dict[str, str]) -> uintptr:
  if not env:
    return uintptr(0)
  block: uint16[:] = new(_EnvBlockCap)
  at: int = 0
  for i in range(len(env)):
    at = _appendEnvPair(block, at, env.keyAt(i), env.valueAt(i))
  if at + 1 < _EnvBlockCap:
    block[at] = uint16(0)
    at += 1
  bytes: int = (at + 1) * 2
  heap: uintptr = pyiMalloc(uint64(bytes))
  if heap == uintptr(0):
    raise OSError()
  dst: Pointer[uint16] = cast(heap)
  for j in range(at + 1):
    dst[j] = block[j]
  return heap


@immutable
def _freeEnvBlock(heap: uintptr) -> None:
  if heap != uintptr(0):
    pyiFree(heap)


@immutable
def _appendReadChunk(text: str, data: byte[:], n: int) -> str:
  if n <= 0:
    return text
  codes: char[:] = new(n)
  for i in range(n):
    codes[i] = cast(data[i])
  return text + str(codes)


@immutable
def _drainHandle(h: uintptr, acc: str) -> str:
  if h == 0:
    return acc
  out: str = acc
  buf: byte[:] = new(4096)
  raw: Pointer[byte] = buf.view.at()
  while True:
    avail: uint = 0
    if pyiPeekNamedPipe(h, uintptr(0), uint(0), None, id(avail), None) == 0:
      return out
    if avail == 0:
      return out
    want: uint = avail
    if want > uint(len(buf)):
      want = uint(len(buf))
    got: uint = 0
    if pyiReadFile(h, cast[uintptr](raw), want, id(got), None) == 0 or got == 0:
      return out
    out = _appendReadChunk(out, buf, int(got))
  return out


@immutable
def _readRest(h: uintptr) -> str:
  if h == 0:
    return ""
  out: str = ""
  buf: byte[:] = new(4096)
  raw: Pointer[byte] = buf.view.at()
  while True:
    got: uint = 0
    if pyiReadFile(h, cast[uintptr](raw), uint(len(buf)), id(got), None) == 0 or got == 0:
      break
    out = _appendReadChunk(out, buf, int(got))
  return out


@uncopyable
class Popen:
  """外部子进程句柄（对齐 ``subprocess.Popen`` 子集）。

  ``args`` 不经 shell 解析；``stdout`` / ``stderr`` 可使用 ``Pipe`` 或 ``DevNull``。
  """

  _hProcess: uintptr = 0
  _hThread: uintptr = 0
  _outRd: uintptr = 0
  _outWr: uintptr = 0
  _errRd: uintptr = 0
  _errWr: uintptr = 0
  _inRd: uintptr = 0
  _inWr: uintptr = 0
  _exitCode: int = 0
  _started: bool = False
  _done: bool = False
  _args: list[str]
  _cwd: str
  _env: dict[str, str]
  _stdinMode: int
  _stdoutMode: int
  _stderrMode: int
  _pid: int = -1

  def _initPopenFields(
    self,
    args: list[str],
    cwd: str,
    env: dict[str, str],
    stdin: int,
    stdout: int,
    stderr: int,
  ) -> None:
    self._args = args
    self._cwd = cwd
    self._env = env
    self._stdinMode = stdin
    self._stdoutMode = stdout
    self._stderrMode = stderr
    if stdout == Pipe:
      pair: (uintptr, uintptr) = _createPipePair()
      self._outRd = pair[0]
      self._outWr = pair[1]
    if stderr == Pipe:
      pair = _createPipePair()
      self._errRd = pair[0]
      self._errWr = pair[1]
    if stdin == Pipe:
      pair = _createPipePair()
      self._inRd = pair[0]
      self._inWr = pair[1]

  @overload
  def __init__(
    self,
    args: list[str],
    cwd: str = "",
    stdin: int = 0,
    stdout: int = 0,
    stderr: int = 0,
  ):
    empty: dict[str, str] = {}
    self._initPopenFields(args, cwd, empty, stdin, stdout, stderr)

  @overload
  def __init__(
    self,
    args: list[str],
    cwd: str,
    env: dict[str, str],
    stdin: int = 0,
    stdout: int = 0,
    stderr: int = 0,
  ):
    self._initPopenFields(args, cwd, env, stdin, stdout, stderr)

  def __del__(self):
    _closeHandle(self._hProcess)
    _closeHandle(self._hThread)
    _closeHandle(self._outRd)
    _closeHandle(self._outWr)
    _closeHandle(self._errRd)
    _closeHandle(self._errWr)
    _closeHandle(self._inRd)
    _closeHandle(self._inWr)

  def start(self) -> None:
    if self._started:
      return
    if not self._args:
      raise OSError()
    if self._cwd:
      with self._cwd.useUtf16() as wcwd:
        self._startWithCwd(wcwd)
    else:
      self._startWithCwd(None)

  def _startWithCwd(self, wcwd: utf16ptr) -> None:
    cmdline: uint16[:] = _buildCmdline(self._args)
    si: PyiStartupinfoW = new(cb=_StartupinfoWSize, dwFlags=PyiStartfUsestdhandles)
    nulIn: uintptr = 0
    nulOut: uintptr = 0
    nulErr: uintptr = 0
    stdinH: uintptr = _resolveIoHandle(self._stdinMode, self._inRd, self._inWr, 0, False)
    stdoutH: uintptr = _resolveIoHandle(self._stdoutMode, self._outRd, self._outWr, 1, True)
    stderrH: uintptr = _resolveIoHandle(self._stderrMode, self._errRd, self._errWr, 2, True)
    _startupSetStdHandles(si, stdinH, stdoutH, stderrH)
    if self._stdinMode == DevNull:
      nulIn = stdinH
    if self._stdoutMode == DevNull:
      nulOut = stdoutH
    if self._stderrMode == DevNull:
      nulErr = stderrH
    wenv: uintptr = _buildEnvBlock(self._env)
    flags: uint = uint(0)
    if wenv != uintptr(0):
      flags = PyiCreateUnicodeEnvironment
    pi: PyiProcessInformation = new()
    cmdPtr: Pointer[uint16] = cast(cmdline.view.at())
    if pyiCreateProcessW(None, cmdPtr, None, None, 1, flags, wenv, wcwd, id(si), id(pi)) == 0:
      _freeEnvBlock(wenv)
      raise OSError()
    _freeEnvBlock(wenv)
    _closeHandle(nulIn)
    _closeHandle(nulOut)
    _closeHandle(nulErr)
    self._hProcess = _processInfoProcessHandle(pi)
    self._hThread = _processInfoThreadHandle(pi)
    self._pid = int(pi.dwProcessId)
    _closeHandle(self._outWr)
    self._outWr = 0
    _closeHandle(self._errWr)
    self._errWr = 0
    _closeHandle(self._inRd)
    self._inRd = 0
    self._started = True

  def poll(self) -> int:
    if not self._started:
      return -1
    if self._done:
      return self._exitCode
    r: uint = pyiWaitForSingleObject(self._hProcess, uint(0))
    if r != _WaitObject0:
      return -1
    code: uint = 0
    pyiGetExitCodeProcess(self._hProcess, id(code))
    self._exitCode = int(code)
    self._done = True
    return self._exitCode

  def wait(self, timeout: float64 = float.Inf) -> int:
    if not self._started:
      raise OSError()
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    if self._done:
      return self._exitCode
    ms: uint = PyiInfinite
    if timeout != float.Inf:
      ms = uint(timeout * 1000.0)
    r: uint = pyiWaitForSingleObject(self._hProcess, ms)
    if r == PyiWaitTimeout:
      raise RuntimeError()
    code: uint = 0
    pyiGetExitCodeProcess(self._hProcess, id(code))
    self._exitCode = int(code)
    self._done = True
    return self._exitCode

  def terminate(self) -> None:
    if self._started and not self._done:
      pyiTerminateProcess(self._hProcess, uint(1))

  def kill(self) -> None:
    self.terminate()

  def communicate(self, input: str = "", timeout: float64 = float.Inf) -> ProcessResult:
    if not self._started:
      raise OSError()
    if timeout < 0.0:
      raise ValueError("timeout value must be non-negative")
    if self._inWr != 0 and input:
      with input.useUtf8() as buf:
        nbytes: uint = 0
        pyiWriteFile(self._inWr, cast[uintptr](buf), uint(pyiStrlen(buf)), id(nbytes), None)
    _closeHandle(self._inWr)
    self._inWr = 0
    out: str = ""
    err: str = ""
    startMs: uint64 = pyiGetTickCount64()
    totalMs: uint = PyiInfinite
    if timeout != float.Inf:
      totalMs = uint(timeout * 1000.0)
    while True:
      out = _drainHandle(self._outRd, out)
      err = _drainHandle(self._errRd, err)
      if totalMs != PyiInfinite:
        elapsed: uint64 = pyiGetTickCount64() - startMs
        if elapsed >= uint64(totalMs):
          pyiTerminateProcess(self._hProcess, uint(1))
          raise RuntimeError()
      r: uint = pyiWaitForSingleObject(self._hProcess, uint(10))
      if r == _WaitObject0:
        break
    code: uint = 0
    pyiGetExitCodeProcess(self._hProcess, id(code))
    self._exitCode = int(code)
    self._done = True
    out += _readRest(self._outRd)
    err += _readRest(self._errRd)
    result: ProcessResult = new(self._exitCode, out, err)
    result.args = self._args
    return result

  @property
  @immutable
  def returnCode(self) -> int:
    if not self._done:
      return -1
    return self._exitCode

  @property
  @immutable
  def pid(self) -> int:
    if not self._started:
      return -1
    return self._pid

  @property
  @immutable
  def running(self) -> bool:
    if not self._started or self._done:
      return False
    return pyiWaitForSingleObject(self._hProcess, uint(0)) != _WaitObject0

  @staticmethod
  def run(args: list[str]) -> ProcessResult:
    """同步运行一个命令，并默认捕获 stdout/stderr。"""
    env: dict[str, str] = {}
    process: Self = new(args, "", env, 0, Pipe, Pipe)
    process.start()
    return process.communicate()

  def __enter__(self) -> Self:
    self.start()
    return self

  def __exit__(self):
    if self.running:
      self.terminate()
