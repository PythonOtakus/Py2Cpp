"""``time``：时钟、``CTime`` 与格式化（对齐 Python 3.13 ``time`` 子集）。

参考 [time — Time access and conversions](https://docs.python.org/3.13/library/time.html)
与 ``Modules/timemodule.c``。超越函数与 OS 时钟经 ``ffi.crt.time`` / ``ffi.windows.windows``；
``strptime`` / ``ascTime`` / ``ctime`` 在 Python 侧（``strptime`` 为受支持格式码子集）。

**无** ``tzset`` / ``zoneinfo`` / ``*_ns``。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text import str
from ..util.cbuf import cstrSlice, strCbuf
from ..util.memory import loadU64LeAtAddress
from ffi.crt.time import PyiTm, pyiGmtime64S, pyiLocaltime64S, pyiMktime64, pyiStrftime, pyiTime64
from ffi.windows.windows import PyiFiletime, PyiLargeInteger
import ffi.windows.windows as win32


@immutable
def _weekdayName(wday: int) -> str:
  return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wday]


@immutable
def _monthName(mon: int) -> str:
  return [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ][mon - 1]


@copyable
@dataclass(repr=False, order=True)
@native_name("CTime")
class CTime:
  """``CTime``（对齐 ``time.struct_time``；9 元组字段；``n_fields`` = 9）。"""

  tmYear: int = 1970

  tmMon: int = 1

  tmMday: int = 1

  tmHour: int = 0

  tmMin: int = 0

  tmSec: int = 0

  tmWday: int @optional = 0

  tmYday: int @optional = 1

  tmIsdst: int @optional = -1

  @immutable
  def __str__(self) -> str:
    return ascTime(self)


@immutable
def _dayOfWeek(y: int, m: int, d: int) -> int:
  t: list[int] = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
  if m < 3:
    y -= 1
  return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7


@immutable
def _cstrSlice(p: CStr, start: int, n: int) -> str:
  return cstrSlice(p, start, n)


@immutable
def _strCbuf(s: str, cap: int) -> byte[:]:
  return strCbuf(s, cap)


@immutable
def _largeIntegerQuad(li: PyiLargeInteger) -> int64:
  addr: uintptr = cast(id(li))
  return int64(loadU64LeAtAddress(addr))


@immutable
def _filetimeQuad(ft: PyiFiletime) -> uint64:
  return (uint64(ft.dwHighDateTime) << 32) | uint64(ft.dwLowDateTime)


@immutable
def _tmToCTime(tm: PyiTm, is_dst: int) -> CTime:
  st: CTime = new(
    tm.tmYear + 1900,
    tm.tmMon + 1,
    tm.tmMday,
    tm.tmHour,
    tm.tmMin,
    tm.tmSec,
  )
  st.tmWday = tm.tmWday
  st.tmYday = tm.tmYday + 1
  st.tmIsdst = is_dst
  return st


@immutable
def _ctimeToTm(st: CTime, tm: PyiTm) -> None:
  tm.tmYear = st.tmYear - 1900
  tm.tmMon = st.tmMon - 1
  tm.tmMday = st.tmMday
  tm.tmHour = st.tmHour
  tm.tmMin = st.tmMin
  tm.tmSec = st.tmSec
  tm.tmWday = _dayOfWeek(st.tmYear, st.tmMon, st.tmMday)
  tm.tmIsdst = st.tmIsdst


def formatDuration(seconds: float64) -> str:
  """将秒数格式化为人类可读耗时（``>=1s`` 用秒，否则 ``ms``/``us``/``ns``）。"""
  if seconds >= 1.0:
    return f"{seconds:.6f}s"
  if seconds >= 0.001:
    ms: float64 = seconds * 1000.0
    return f"{ms:.3f}ms"
  if seconds >= 0.000001:
    us: float64 = seconds * 1000000.0
    return f"{us:.3f}us"
  ns: float64 = seconds * 1000000000.0
  return f"{ns:.3f}ns"


@context
def stopwatch(tag: str = None):
  """进入时记下 ``perfCounter``，退出时打印标签与 ``formatDuration`` 耗时。"""
  label: str = tag or "stopwatch"
  start: float64 = perfCounter()
  yield
  end: float64 = perfCounter()
  elapsed: float64 = end - start
  dur: str = formatDuration(elapsed)
  print(f"stopwatch {label}: {dur}")


@immutable
def time() -> float64:
  """自纪元起的秒数（``time.time()``）。"""
  return float64(pyiTime64(None))


@immutable
def sleep(seconds: float64) -> None:
  """阻塞 ``seconds`` 秒（``seconds < 0`` 时无操作）。"""
  if seconds <= 0.0:
    return
  ms: float64 = seconds * 1000.0
  if ms > 4294967294.0:
    ms = 4294967294.0
  dw: uint = uint(ms + 0.5)
  if dw == 0:
    dw = 1
  win32.pyiSleep(dw)


@immutable
def monotonic() -> float64:
  """单调时钟秒数。"""
  return float64(win32.pyiGetTickCount64()) / 1000.0


@immutable
def perfCounter() -> float64:
  """高分辨率性能计数器秒数。"""
  freq: PyiLargeInteger = new()
  ctr: PyiLargeInteger = new()
  if win32.pyiQueryPerformanceFrequency(id(freq)) and win32.pyiQueryPerformanceCounter(id(ctr)):
    f: int64 = _largeIntegerQuad(freq)
    if f != 0:
      c: int64 = _largeIntegerQuad(ctr)
      return float64(c) / float64(f)
  return monotonic()


@immutable
def processTime() -> float64:
  """当前进程 CPU 时间（秒）。"""
  create: PyiFiletime = new()
  exit_ft: PyiFiletime = new()
  kernel: PyiFiletime = new()
  user: PyiFiletime = new()
  if win32.pyiGetProcessTimes(
    win32.pyiGetCurrentProcess(),
    id(create),
    id(exit_ft),
    id(kernel),
    id(user),
  ):
    k: uint64 = _filetimeQuad(kernel)
    u: uint64 = _filetimeQuad(user)
    return float64(k + u) / 10000000.0
  return 0.0


@immutable
def gmTime(secs: float64) -> CTime:
  """UTC ``CTime``（纪元秒）。"""
  tm: PyiTm = new()
  secs_i = int64(secs)
  if pyiGmtime64S(id(tm), id(secs_i)) == 0:
    return _tmToCTime(tm, -1)
  return new(1970, 1, 1, 0, 0, 0)


@immutable
def gmTimeNow() -> CTime:
  """``gmTime(time())``。"""
  return gmTime(time())


@immutable
def localTime(secs: float64) -> CTime:
  """本地 ``CTime``（纪元秒）。"""
  tm: PyiTm = new()
  secs_i = int64(secs)
  if pyiLocaltime64S(id(tm), id(secs_i)) == 0:
    is_dst: int = tm.tmIsdst
    return _tmToCTime(tm, is_dst)
  return new(1970, 1, 1, 0, 0, 0)


@immutable
def localTimeNow() -> CTime:
  """``localTime(time())``。"""
  return localTime(time())


@immutable
def mkTime(st: CTime) -> float64:
  """本地日历 → 纪元秒（失败返回 ``-1.0``）。"""
  tm: PyiTm = new()
  _ctimeToTm(st, tm)
  out: int64 = pyiMktime64(id(tm))
  if out == -1:
    return -1.0
  return float64(out)


@immutable
def pyStrftime(fmt: str, st: CTime) -> str:
  """``strftime`` C 库实现（格式码以平台支持为准）。"""
  tm: PyiTm = new()
  _ctimeToTm(st, tm)
  buf: byte[:] = new(256)
  fmtBuf: byte[:] = _strCbuf(fmt, 256)
  n: uint64 = pyiStrftime(buf.view.at(0), 256, fmtBuf.view.at(0), id(tm))
  if n == 0:
    return ""
  return _cstrSlice(buf.view.at(0), 0, int(n))


@immutable
def strftime(fmt: str, st: CTime) -> str:
  """``strftime``；``%Y-%m-%d`` 走 Python 组合，其余委托 C。"""
  if fmt == "%Y-%m-%d":
    return str(st.tmYear) + "-" + _two(st.tmMon) + "-" + _two(st.tmMday)
  return pyStrftime(fmt, st)


@immutable
def _parseIntField(s: str, start: int, width: int) -> int:
  end: int = start + width
  part: str = s[start:end]
  if not part.isDigit():
    raise ValueError("strptime")
  n: int = 0
  for i in range(width):
    n = n * 10 + (int(part[i]) - ord("0"))
  return n


@immutable
def _strptimeFixed(s: str, fmt: str) -> CTime:
  """受支持格式：``%Y-%m-%d``、``%Y-%m-%d %H:%M:%S``、``%Y/%m/%d %H:%M:%S``。"""
  match fmt:
    case "%Y-%m-%d":
      y: int = _parseIntField(s, 0, 4)
      if s[4] != ord("-"):
        raise ValueError("strptime")
      mo: int = _parseIntField(s, 5, 2)
      if s[7] != ord("-"):
        raise ValueError("strptime")
      d: int = _parseIntField(s, 8, 2)
      return new(y, mo, d, 0, 0, 0)
    case "%Y-%m-%d %H:%M:%S":
      y2: int = _parseIntField(s, 0, 4)
      if s[4] != ord("-"):
        raise ValueError("strptime")
      mo2: int = _parseIntField(s, 5, 2)
      if s[7] != ord("-"):
        raise ValueError("strptime")
      d2: int = _parseIntField(s, 8, 2)
      if s[10] != ord(" "):
        raise ValueError("strptime")
      h: int = _parseIntField(s, 11, 2)
      if s[13] != ord(":"):
        raise ValueError("strptime")
      mi: int = _parseIntField(s, 14, 2)
      if s[16] != ord(":"):
        raise ValueError("strptime")
      sec: int = _parseIntField(s, 17, 2)
      return new(y2, mo2, d2, h, mi, sec)
    case "%Y/%m/%d %H:%M:%S":
      y3: int = _parseIntField(s, 0, 4)
      if s[4] != ord("/"):
        raise ValueError("strptime")
      mo3: int = _parseIntField(s, 5, 2)
      if s[7] != ord("/"):
        raise ValueError("strptime")
      d3: int = _parseIntField(s, 8, 2)
      if s[10] != ord(" "):
        raise ValueError("strptime")
      h3: int = _parseIntField(s, 11, 2)
      if s[13] != ord(":"):
        raise ValueError("strptime")
      mi3: int = _parseIntField(s, 14, 2)
      if s[16] != ord(":"):
        raise ValueError("strptime")
      sec3: int = _parseIntField(s, 17, 2)
      return new(y3, mo3, d3, h3, mi3, sec3)
    case _:
      raise ValueError("strptime")


def strptime(s: str, fmt: str) -> CTime:
  """解析固定格式子集（见 ``_strptimeFixed``）。"""
  return _strptimeFixed(s, fmt)


@immutable
def _zfillInt(n: int, width: int) -> str:
  """非负整数左补零（``str.zfill``）。"""
  return str(n).zfill(width)


@immutable
def _two(n: int) -> str:
  return _zfillInt(n, 2)


@immutable
def ascTime(st: CTime) -> str:
  """``Sun Oct  6 12:34:56 2024`` 风格（无时区）。"""
  t: CTime = st
  wd: str = _weekdayName(t.tmWday)
  mon: str = _monthName(t.tmMon)
  pad: str = " " if t.tmMday < 10 else ""
  return f"{wd} {mon} {pad}{t.tmMday} {_two(t.tmHour)}:{_two(t.tmMin)}:{_two(t.tmSec)} {t.tmYear}"


@immutable
def ascTimeNow() -> str:
  """``ascTime(localTimeNow())``。"""
  return ascTime(localTimeNow())


@immutable
def ctime(secs: float64) -> str:
  """``ascTime(localTime(secs))``。"""
  return ascTime(localTime(secs))


@immutable
def ctimeNow() -> str:
  """``ascTime(localTimeNow())``（同 CPython ``ctime()``）。"""
  return ascTime(localTimeNow())
