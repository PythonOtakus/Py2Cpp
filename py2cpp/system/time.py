"""``time``：时钟、``CTime`` 与格式化（对齐 Python 3.13 ``time`` 子集）。

参考 [time — Time access and conversions](https://docs.python.org/3.13/library/time.html)
与 ``Modules/timemodule.c``。C 层：``py_time`` / ``gmTime`` / ``localTime`` / ``mkTime`` /
``strftime``（``templates/system/-time.inl`` → ``time.inl``）。**无** ``tzset`` / ``zoneinfo`` / ``*_ns``。

``strptime`` / ``ascTime`` / ``ctime`` 在 Python 侧（``strptime`` 为受支持格式码子集）。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text import str


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


@native
@global_call("py_*")
def time() -> float64:
  """自纪元起的秒数（``time.time()``）。"""
  ...

@native
@global_call("py_*")
def sleep(seconds: float64) -> None:
  """阻塞 ``seconds`` 秒（``seconds < 0`` 时无操作）。"""
  ...


@native
def monotonic() -> float64:
  """单调时钟秒数。"""
  ...


@native
def perfCounter() -> float64:
  """高分辨率性能计数器秒数。"""
  ...


@native
def processTime() -> float64:
  """当前进程 CPU 时间（秒）。"""
  ...


@native
def gmTime(secs: float64) -> CTime:
  """UTC ``CTime``（纪元秒）。"""
  ...


@native
def gmTimeNow() -> CTime:
  """``gmTime(time())``。"""
  ...


@native
def localTime(secs: float64) -> CTime:
  """本地 ``CTime``（纪元秒）。"""
  ...


@native
def localTimeNow() -> CTime:
  """``localTime(time())``。"""
  ...


@native
@global_call("py_*")
def mkTime(st: CTime) -> float64:
  """本地日历 → 纪元秒（失败返回 ``-1.0``）。"""
  ...


@native
def pyStrftime(fmt: str, st: CTime) -> str:
  """``strftime`` C 库实现（格式码以平台支持为准；C++ 同名）。"""
  ...


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
