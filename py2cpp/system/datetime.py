"""``datetime``：日历类型（对齐 Python 3.13 ``datetime`` 子集，**无** ``tzinfo`` / ``timezone``）。

``timedelta`` / ``date`` / ``time`` / ``datetime``；``strftime`` / ``strptime``（经 ``system.time``）；
``now`` / ``utcnow`` / ``fromtimestamp`` 使用本地/UTC 墙钟，**不**支持时区类与 ``astimezone``。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text import str
from .time import (
  _two,
  _zfill_int,
  gmtime,
  localtime,
  localtime_now,
  mktime,
  c_time,
  strftime,
  time as wall_time,
)

_MINYEAR: int = 1
_MAXYEAR: int = 9999
_US_PER_DAY_I: int64 = 86400000000
_US_PER_SEC_I: int64 = 1000000
_HOUR_US_I: int64 = 3600000000
_MINUTE_US_I: int64 = 60000000
_DI4Y: int = 1461
_DI100Y: int = 36524
_DI400Y: int = 146097


@copyable
@dataclass(eq=False, repr=False)
class _YMD:
  """公历 ``(year, month, day)``：仅作 ``_ord_to_ymd`` / ``__add__`` 等中间结果，勿替代 ``date``。"""

  year: int

  month: int

  day: int


@copyable
@dataclass(eq=False, repr=False)
class _HMSUS:
  """日内时分秒微秒：仅作 ``_split_us`` 等中间结果，勿替代 ``time``。"""

  hour: int

  minute: int

  second: int

  us: int


@immutable
def _split_us(us: int64) -> _HMSUS:
  """将 ``0 <= us < _US_PER_DAY`` 拆为时分秒微秒（避免 ``int64``→``PyInt`` 窄化）。"""
  r: int64 = us % _HOUR_US_I
  tail: int64 = r % _MINUTE_US_I
  return new(
    int(us // _HOUR_US_I),
    int(r // _MINUTE_US_I),
    int(tail // _US_PER_SEC_I),
    int(tail % _US_PER_SEC_I),
  )


@immutable
def _is_leap(year: int) -> bool:
  if year % 4 != 0:
    return False
  if year % 100 != 0:
    return True
  if year % 400 != 0:
    return False
  return True


@immutable
def _days_before_month_base(month: int) -> int:
  return [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][month - 1]

@immutable
def _days_before_month(year: int, month: int) -> int:
  days: int = _days_before_month_base(month)
  if month > 2:
    if _is_leap(year):
      days += 1
  return days

@immutable
def _days_in_month_base(month: int) -> int:
  return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]

@immutable
def _days_in_month(year: int, month: int) -> int:
  if month == 2:
    if _is_leap(year):
      return 29
    return 28
  return _days_in_month_base(month)


@immutable
def _days_before_year(year: int) -> int:
  y: int = year - 1
  return y * 365 + y // 4 - y // 100 + y // 400


@immutable
def _ymd_to_ord(year: int, month: int, day: int) -> int:
  return _days_before_year(year) + _days_before_month(year, month) + day


@immutable
def _ord_to_ymd(ord: int) -> _YMD:
  """与 CPython ``ord_to_ymd`` 一致（``01-Jan-0001`` 为序数 1）。"""
  n: int = ord - 1
  n400: int = n // _DI400Y
  n %= _DI400Y
  year: int = n400 * 400 + 1
  n100: int = n // _DI100Y
  n %= _DI100Y
  n4: int = n // _DI4Y
  n %= _DI4Y
  n1: int = n // 365
  n %= 365
  year += n100 * 100 + n4 * 4 + n1
  if n1 == 4 or n100 == 4:
    return new(year - 1, 12, 31)
  leapyear: bool = n1 == 3 and (n4 != 24 or n100 == 3)
  month: int = (n + 50) // 32
  preceding: int = _days_before_month_base(month)
  if month > 2:
    if leapyear:
      preceding += 1
  if preceding > n:
    month -= 1
    preceding -= _days_in_month(year, month)
  n -= preceding
  day: int = n + 1
  return new(year, month, day)


@immutable
def _check_date(year: int, month: int, day: int) -> None:
  if year < _MINYEAR or year > _MAXYEAR:
    raise ValueError("year out of range")
  if month < 1 or month > 12:
    raise ValueError("month out of range")
  dim: int = _days_in_month(year, month)
  if day < 1 or day > dim:
    raise ValueError("day out of range")


@immutable
def _us_from_timestamp(ts: float64) -> int:
  """时间戳秒的小数部分 → 微秒（``now`` / ``fromtimestamp`` 共用）。"""
  return int((ts - int(ts)) * 1000000.0)


@immutable
def _check_time(hour: int, minute: int, second: int, microsecond: int) -> None:
  if hour < 0 or hour > 23:
    raise ValueError("hour out of range")
  if minute < 0 or minute > 59:
    raise ValueError("minute out of range")
  if second < 0 or second > 59:
    raise ValueError("second out of range")
  if microsecond < 0 or microsecond > 999999:
    raise ValueError("microsecond out of range")


@copyable
@native_name("PyTimeDelta")
class timedelta(friends=(date, datetime)):
  """时间差（内部：总微秒 ``int64``）。"""

  def __init__(
    self,
    days: int = 0,
    seconds: int = 0,
    microseconds: int = 0,
  ):
    self._us: int64 = microseconds
    self._us += seconds * _US_PER_SEC_I
    self._us += days * _US_PER_DAY_I

  @immutable
  def __str__(self) -> str:
    return repr(self)

  @immutable
  def __repr__(self) -> str:
    sec: float64 = self.total_seconds()
    return f"datetime.timedelta({sec})"

  @immutable
  def __cmp__(self, other: Self) -> int:
    return __cmp__(self._us, other._us)

  @immutable
  def __add__(self, other: Self) -> Self:
    return new(0, 0, int(self._us + other._us))

  @immutable
  def __sub__(self, other: Self) -> Self:
    return new(0, 0, int(self._us - other._us))

  @immutable
  def __neg__(self) -> Self:
    return new(0, 0, int(-self._us))

  @immutable
  def total_seconds(self) -> float64:
    num: float64 = self._us * 1.0
    return num / 1000000.0


@copyable
@native_name("PyDate")
class date:
  """日期（内部：公历序数 ``_ord``）。"""

  @staticmethod
  @immutable
  def fromordinal(ord: int) -> Self:
    ymd: _YMD = _ord_to_ymd(ord)
    return new(ymd.year, ymd.month, ymd.day)

  @staticmethod
  @immutable
  def today() -> Self:
    st: c_time = localtime_now()
    return new(st.tm_year, st.tm_mon, st.tm_mday)

  def __init__(self, year: int, month: int, day: int):
    _check_date(year, month, day)
    self._year: int = year
    self._month: int = month
    self._day: int = day
    self._ord: int = _ymd_to_ord(year, month, day)

  @immutable
  def __str__(self) -> str:
    return self.isoformat()

  @immutable
  def __repr__(self) -> str:
    return f"datetime.date({self.year}, {self.month}, {self.day})"

  @immutable
  def __cmp__(self, other: Self) -> int:
    return __cmp__(self._ord, other._ord)

  @property
  @immutable
  def year(self) -> int:
    return self._year

  @property
  @immutable
  def month(self) -> int:
    return self._month

  @property
  @immutable
  def day(self) -> int:
    return self._day

  @immutable
  def __add__(self, other: timedelta) -> Self:
    return new.fromordinal(self._ord + int(other._us // _US_PER_DAY_I))

  @immutable
  def __sub__(self, other: Self) -> timedelta:
    return new(self._ord - other._ord, 0, 0)

  @immutable
  def isoformat(self) -> str:
    return f"{_zfill_int(self.year, 4)}-{_two(self.month)}-{_two(self.day)}"

  @immutable
  def strftime(self, fmt: str) -> str:
    st: c_time = new(self.year, self.month, self.day, 0, 0, 0)
    return strftime(fmt, st)

  @immutable
  def toordinal(self) -> int:
    return self._ord


@copyable
@native_name("PyTime")
class time:
  """日内时间（无时区）。"""

  def __init__(
    self,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
  ):
    _check_time(hour, minute, second, microsecond)
    self.hour: int = hour
    self.minute: int = minute
    self.second: int = second
    self.microsecond: int = microsecond

  @immutable
  def __str__(self) -> str:
    return self.isoformat()

  @immutable
  def __repr__(self) -> str:
    return f"datetime.time({self.hour}, {self.minute}, {self.second})"

  @immutable
  def __cmp__(self, other: Self) -> int:
    return __cmp__(self.hour, other.hour) or __cmp__(self.minute, other.minute) or __cmp__(self.second, other.second) or __cmp__(self.microsecond, other.microsecond)

  @immutable
  def isoformat(self) -> str:
    base: str = f"{_two(self.hour)}:{_two(self.minute)}:{_two(self.second)}"
    if self.microsecond != 0:
      return f"{base}.{_zfill_int(self.microsecond, 6)}"
    return base

  @immutable
  def strftime(self, fmt: str) -> str:
    st: c_time = new(1900, 1, 1, self.hour, self.minute, self.second)
    return strftime(fmt, st)


@copyable
@native_name("PyDateTime")
class datetime:
  """日期 + 时间（无时区；``_ord`` + 日内微秒）。"""

  @staticmethod
  @immutable
  def combine(d: date, t: time) -> Self:
    return new(d.year, d.month, d.day, t.hour, t.minute, t.second, t.microsecond)

  @staticmethod
  @immutable
  def fromtimestamp(ts: float64) -> Self:
    st: c_time = localtime(ts)
    us: int = _us_from_timestamp(ts)
    return new._from_parts(
      st.tm_year,
      st.tm_mon,
      st.tm_mday,
      st.tm_hour,
      st.tm_min,
      st.tm_sec,
      us,
    )

  @staticmethod
  @immutable
  def now() -> Self:
    ts: float64 = wall_time()
    st: c_time = localtime(ts)
    us: int = _us_from_timestamp(ts)
    return new._from_parts(
      st.tm_year,
      st.tm_mon,
      st.tm_mday,
      st.tm_hour,
      st.tm_min,
      st.tm_sec,
      us,
    )

  @staticmethod
  @immutable
  def today() -> Self:
    d: date = new.today()
    return new(d.year, d.month, d.day, 0, 0, 0, 0)

  @staticmethod
  @immutable
  def utcnow() -> Self:
    ts: float64 = wall_time()
    st: c_time = gmtime(ts)
    us: int = _us_from_timestamp(ts)
    return new._from_parts(
      st.tm_year,
      st.tm_mon,
      st.tm_mday,
      st.tm_hour,
      st.tm_min,
      st.tm_sec,
      us,
    )

  @staticmethod
  @immutable
  def _from_parts(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    microsecond: int,
  ) -> Self:
    return new(year, month, day, hour, minute, second, microsecond)

  @staticmethod
  @immutable
  def _from_ymd_us(ymd: _YMD, us: int64) -> Self:
    p: _HMSUS = _split_us(us)
    return new(ymd.year, ymd.month, ymd.day, p.hour, p.minute, p.second, p.us)

  def __init__(
    self,
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
  ):
    _check_date(year, month, day)
    _check_time(hour, minute, second, microsecond)
    self._year: int = year
    self._month: int = month
    self._day: int = day
    self._hour: int = hour
    self._minute: int = minute
    self._second: int = second
    self._microsecond: int = microsecond
    self._ord: int = _ymd_to_ord(year, month, day)
    self._us: int64 = microsecond
    self._us += second * _US_PER_SEC_I
    self._us += minute * _MINUTE_US_I
    self._us += hour * _HOUR_US_I

  @immutable
  def __str__(self) -> str:
    return self.isoformat(" ")

  @immutable
  def __repr__(self) -> str:
    return (
      f"datetime.datetime({self.year}, {self.month}, {self.day}, "
      f"{self.hour}, {self.minute}, {self.second})"
    )

  @immutable
  def __cmp__(self, other: Self) -> int:
    return __cmp__(self._ord, other._ord) or __cmp__(self._us, other._us)

  @property
  @immutable
  def year(self) -> int:
    return self._year

  @property
  @immutable
  def month(self) -> int:
    return self._month

  @property
  @immutable
  def day(self) -> int:
    return self._day

  @property
  @immutable
  def hour(self) -> int:
    return self._hour

  @property
  @immutable
  def minute(self) -> int:
    return self._minute

  @property
  @immutable
  def second(self) -> int:
    return self._second

  @property
  @immutable
  def microsecond(self) -> int:
    return self._microsecond

  @immutable
  def __add__(self, other: timedelta) -> Self:
    new_us: int64 = self._us + other._us
    extra: int64 = new_us // _US_PER_DAY_I
    new_us %= _US_PER_DAY_I
    p: _HMSUS = _split_us(new_us)
    if extra == 0:
      return new(
        self._year,
        self._month,
        self._day,
        p.hour,
        p.minute,
        p.second,
        p.us,
      )
    ymd: _YMD = _ord_to_ymd(self._ord + int(extra))
    return new(ymd.year, ymd.month, ymd.day, p.hour, p.minute, p.second, p.us)

  @immutable
  def __sub__(self, other: Self) -> timedelta:
    days: int = self._ord - other._ord
    us: int64 = self._us - other._us
    us += days * _US_PER_DAY_I
    return new(0, 0, int(us))

  @immutable
  def date(self) -> date:
    return new.fromordinal(self._ord)

  @immutable
  def isoformat(self, sep: str = "T") -> str:
    return self.date().isoformat() + sep + self.time().isoformat()

  @immutable
  def strftime(self, fmt: str) -> str:
    st: c_time = new(
      self.year,
      self.month,
      self.day,
      self.hour,
      self.minute,
      self.second,
    )
    return strftime(fmt, st)

  @immutable
  def time(self) -> time:
    return new(self.hour, self.minute, self.second, self.microsecond)

  @immutable
  def timestamp(self) -> float64:
    st: c_time = new(
      self.year,
      self.month,
      self.day,
      self.hour,
      self.minute,
      self.second,
    )
    base: float64 = mktime(st)
    frac: float64 = self.microsecond * 1.0
    base += frac / 1000000.0
    return base
