"""``time``：时钟、``c_time`` 与格式化（对齐 Python 3.13 ``time`` 子集）。

参考 [time — Time access and conversions](https://docs.python.org/3.13/library/time.html)
与 ``Modules/timemodule.c``。C 层：``py_time`` / ``gmtime`` / ``localtime`` / ``mktime`` /
``strftime``（``templates/system/-time.inl`` → ``time.inl``）。**无** ``tzset`` / ``zoneinfo`` / ``*_ns``。

``strptime`` / ``asctime`` / ``ctime`` 在 Python 侧（``strptime`` 为受支持格式码子集）。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text import str


@immutable
def _weekday_name(wday: int) -> str:
  return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wday]


@immutable
def _month_name(mon: int) -> str:
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
class c_time:
  """``c_time``（对齐 ``time.struct_time``；9 元组字段；``n_fields`` = 9）。"""

  tm_year: int = 1970

  tm_mon: int = 1

  tm_mday: int = 1

  tm_hour: int = 0

  tm_min: int = 0

  tm_sec: int = 0

  tm_wday: int @optional = 0

  tm_yday: int @optional = 1

  tm_isdst: int @optional = -1

  @immutable
  def __str__(self) -> str:
    return asctime(self)


def format_duration(seconds: float64) -> str:
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
  """进入时记下 ``perf_counter``，退出时打印标签与 ``format_duration`` 耗时。"""
  label: str = tag or "stopwatch"
  start: float64 = perf_counter()
  yield
  end: float64 = perf_counter()
  elapsed: float64 = end - start
  dur: str = format_duration(elapsed)
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
def perf_counter() -> float64:
  """高分辨率性能计数器秒数。"""
  ...


@native
def process_time() -> float64:
  """当前进程 CPU 时间（秒）。"""
  ...


@native
def gmtime(secs: float64) -> c_time:
  """UTC ``c_time``（纪元秒）。"""
  ...


@native
def gmtime_now() -> c_time:
  """``gmtime(time())``。"""
  ...


@native
def localtime(secs: float64) -> c_time:
  """本地 ``c_time``（纪元秒）。"""
  ...


@native
def localtime_now() -> c_time:
  """``localtime(time())``。"""
  ...


@native
@global_call("py_*")
def mktime(st: c_time) -> float64:
  """本地日历 → 纪元秒（失败返回 ``-1.0``）。"""
  ...


@native
def py_strftime(fmt: str, st: c_time) -> str:
  """``strftime`` C 库实现（格式码以平台支持为准；C++ 同名）。"""
  ...


@immutable
def strftime(fmt: str, st: c_time) -> str:
  """``strftime``；``%Y-%m-%d`` 走 Python 组合，其余委托 C。"""
  if fmt == "%Y-%m-%d":
    return str(st.tm_year) + "-" + _two(st.tm_mon) + "-" + _two(st.tm_mday)
  return py_strftime(fmt, st)


@immutable
def _parse_int_field(s: str, start: int, width: int) -> int:
  end: int = start + width
  part: str = s[start:end]
  if not part.isdigit():
    raise ValueError("strptime")
  n: int = 0
  for i in range(width):
    n = n * 10 + (int(part[i]) - ord("0"))
  return n


@immutable
def _strptime_fixed(s: str, fmt: str) -> c_time:
  """受支持格式：``%Y-%m-%d``、``%Y-%m-%d %H:%M:%S``、``%Y/%m/%d %H:%M:%S``。"""
  match fmt:
    case "%Y-%m-%d":
      y: int = _parse_int_field(s, 0, 4)
      if s.data[4] != ord("-"):
        raise ValueError("strptime")
      mo: int = _parse_int_field(s, 5, 2)
      if s.data[7] != ord("-"):
        raise ValueError("strptime")
      d: int = _parse_int_field(s, 8, 2)
      return new(y, mo, d, 0, 0, 0)
    case "%Y-%m-%d %H:%M:%S":
      y2: int = _parse_int_field(s, 0, 4)
      if s.data[4] != ord("-"):
        raise ValueError("strptime")
      mo2: int = _parse_int_field(s, 5, 2)
      if s.data[7] != ord("-"):
        raise ValueError("strptime")
      d2: int = _parse_int_field(s, 8, 2)
      if s.data[10] != ord(" "):
        raise ValueError("strptime")
      h: int = _parse_int_field(s, 11, 2)
      if s.data[13] != ord(":"):
        raise ValueError("strptime")
      mi: int = _parse_int_field(s, 14, 2)
      if s.data[16] != ord(":"):
        raise ValueError("strptime")
      sec: int = _parse_int_field(s, 17, 2)
      return new(y2, mo2, d2, h, mi, sec)
    case "%Y/%m/%d %H:%M:%S":
      y3: int = _parse_int_field(s, 0, 4)
      if s.data[4] != ord("/"):
        raise ValueError("strptime")
      mo3: int = _parse_int_field(s, 5, 2)
      if s.data[7] != ord("/"):
        raise ValueError("strptime")
      d3: int = _parse_int_field(s, 8, 2)
      if s.data[10] != ord(" "):
        raise ValueError("strptime")
      h3: int = _parse_int_field(s, 11, 2)
      if s.data[13] != ord(":"):
        raise ValueError("strptime")
      mi3: int = _parse_int_field(s, 14, 2)
      if s.data[16] != ord(":"):
        raise ValueError("strptime")
      sec3: int = _parse_int_field(s, 17, 2)
      return new(y3, mo3, d3, h3, mi3, sec3)
    case _:
      raise ValueError("strptime")


def strptime(s: str, fmt: str) -> c_time:
  """解析固定格式子集（见 ``_strptime_fixed``）。"""
  return _strptime_fixed(s, fmt)


@immutable
def _zfill_int(n: int, width: int) -> str:
  """非负整数左补零（``str.zfill``）。"""
  return str(n).zfill(width)


@immutable
def _two(n: int) -> str:
  return _zfill_int(n, 2)


@immutable
def asctime(st: c_time) -> str:
  """``Sun Oct  6 12:34:56 2024`` 风格（无时区）。"""
  t: c_time = st
  wd: str = _weekday_name(t.tm_wday)
  mon: str = _month_name(t.tm_mon)
  pad: str = " " if t.tm_mday < 10 else ""
  return f"{wd} {mon} {pad}{t.tm_mday} {_two(t.tm_hour)}:{_two(t.tm_min)}:{_two(t.tm_sec)} {t.tm_year}"


@immutable
def asctime_now() -> str:
  """``asctime(localtime_now())``。"""
  return asctime(localtime_now())


@immutable
def ctime(secs: float64) -> str:
  """``asctime(localtime(secs))``。"""
  return asctime(localtime(secs))


@immutable
def ctime_now() -> str:
  """``asctime(localtime_now())``（同 CPython ``ctime()``）。"""
  return asctime(localtime_now())
