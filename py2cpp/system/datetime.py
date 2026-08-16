"""``datetime``：日历类型（对齐 Python 3.13 ``datetime`` 子集，**无** ``tzinfo`` / ``timezone``）。

``timedelta`` / ``date`` / ``time`` / ``datetime``；``strftime`` / ``strptime``（经 ``system.time``）；
``now`` / ``utcnow`` / ``fromTimestamp`` 使用本地/UTC 墙钟，**不**支持时区类与 ``astimezone``。
"""
from ..builtins import *
from ..core.exceptions import ValueError
from ..text import str
from .time import (
  _two,
  _zfillInt,
  gmTime,
  localTime,
  localTimeNow,
  mkTime,
  CTime,
  strftime,
  time as wall_time,
)

_Minyear: int = 1
_Maxyear: int = 9999
_UsPerDayI: int64 = 86400000000
_UsPerSecI: int64 = 1000000
_HourUsI: int64 = 3600000000
_MinuteUsI: int64 = 60000000
_Di4y: int = 1461
_Di100y: int = 36524
_Di400y: int = 146097


@copyable
@dataclass(eq=False, repr=False)
class _YMD:
  """公历 ``(year, month, day)``：仅作 ``_ordToYmd`` / ``__add__`` 等中间结果，勿替代 ``date``。"""

  year: int

  month: int

  day: int


@copyable
@dataclass(eq=False, repr=False)
class _HMSUS:
  """日内时分秒微秒：仅作 ``_splitUs`` 等中间结果，勿替代 ``time``。"""

  hour: int

  minute: int

  second: int

  us: int


@immutable
def _splitUs(us: int64) -> _HMSUS:
  """将 ``0 <= us < _US_PER_DAY`` 拆为时分秒微秒（避免 ``int64``→``PyInt`` 窄化）。"""
  r: int64 = us % _HourUsI
  tail: int64 = r % _MinuteUsI
  return new(
    int(us // _HourUsI),
    int(r // _MinuteUsI),
    int(tail // _UsPerSecI),
    int(tail % _UsPerSecI),
  )


@immutable
def _isLeap(year: int) -> bool:
  if year % 4 != 0:
    return False
  if year % 100 != 0:
    return True
  if year % 400 != 0:
    return False
  return True


@immutable
def _daysBeforeMonthBase(month: int) -> int:
  return [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334][month - 1]

@immutable
def _daysBeforeMonth(year: int, month: int) -> int:
  days: int = _daysBeforeMonthBase(month)
  if month > 2:
    if _isLeap(year):
      days += 1
  return days

@immutable
def _daysInMonthBase(month: int) -> int:
  return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]

@immutable
def _daysInMonth(year: int, month: int) -> int:
  if month == 2:
    if _isLeap(year):
      return 29
    return 28
  return _daysInMonthBase(month)


@immutable
def _daysBeforeYear(year: int) -> int:
  y: int = year - 1
  return y * 365 + y // 4 - y // 100 + y // 400


@immutable
def _ymdToOrd(year: int, month: int, day: int) -> int:
  return _daysBeforeYear(year) + _daysBeforeMonth(year, month) + day


@immutable
def _ordToYmd(ord: int) -> _YMD:
  """与 CPython ``ord_to_ymd`` 一致（``01-Jan-0001`` 为序数 1）。"""
  n: int = ord - 1
  n400: int = n // _Di400y
  n %= _Di400y
  year: int = n400 * 400 + 1
  n100: int = n // _Di100y
  n %= _Di100y
  n4: int = n // _Di4y
  n %= _Di4y
  n1: int = n // 365
  n %= 365
  year += n100 * 100 + n4 * 4 + n1
  if n1 == 4 or n100 == 4:
    return new(year - 1, 12, 31)
  leapyear: bool = n1 == 3 and (n4 != 24 or n100 == 3)
  month: int = (n + 50) // 32
  preceding: int = _daysBeforeMonthBase(month)
  if month > 2:
    if leapyear:
      preceding += 1
  if preceding > n:
    month -= 1
    preceding -= _daysInMonth(year, month)
  n -= preceding
  day: int = n + 1
  return new(year, month, day)


@immutable
def _checkDate(year: int, month: int, day: int) -> None:
  if year < _Minyear or year > _Maxyear:
    raise ValueError("year out of range")
  if month < 1 or month > 12:
    raise ValueError("month out of range")
  dim: int = _daysInMonth(year, month)
  if day < 1 or day > dim:
    raise ValueError("day out of range")


@immutable
def _usFromTimestamp(ts: float64) -> int:
  """时间戳秒的小数部分 → 微秒（``now`` / ``fromTimestamp`` 共用）。"""
  return int((ts - int(ts)) * 1000000.0)


@immutable
def _checkTime(hour: int, minute: int, second: int, microsecond: int) -> None:
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
    self._us += seconds * _UsPerSecI
    self._us += days * _UsPerDayI

  @immutable
  def __str__(self) -> str:
    return repr(self)

  @immutable
  def __repr__(self) -> str:
    sec: float64 = self.totalSeconds()
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
  def totalSeconds(self) -> float64:
    num: float64 = self._us * 1.0
    return num / 1000000.0


@copyable
class date:
  """日期（内部：公历序数 ``_ord``）。"""

  @staticmethod
  @immutable
  def fromOrdinal(ord: int) -> Self:
    ymd: _YMD = _ordToYmd(ord)
    return new(ymd.year, ymd.month, ymd.day)

  @staticmethod
  @immutable
  def today() -> Self:
    st: CTime = localTimeNow()
    return new(st.tmYear, st.tmMon, st.tmMday)

  def __init__(self, year: int, month: int, day: int):
    _checkDate(year, month, day)
    self._year: int = year
    self._month: int = month
    self._day: int = day
    self._ord: int = _ymdToOrd(year, month, day)

  @immutable
  def __str__(self) -> str:
    return self.isoFormat()

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
    return new.fromOrdinal(self._ord + int(other._us // _UsPerDayI))

  @immutable
  def __sub__(self, other: Self) -> timedelta:
    return new(self._ord - other._ord, 0, 0)

  @immutable
  def isoFormat(self) -> str:
    return f"{_zfillInt(self.year, 4)}-{_two(self.month)}-{_two(self.day)}"

  @immutable
  def strftime(self, fmt: str) -> str:
    return strftime(fmt, CTime(self.year, self.month, self.day, 0, 0, 0))

  @immutable
  def toOrdinal(self) -> int:
    return self._ord


@copyable
class time:
  """日内时间（无时区）。"""

  def __init__(
    self,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
  ):
    _checkTime(hour, minute, second, microsecond)
    self.hour: int = hour
    self.minute: int = minute
    self.second: int = second
    self.microsecond: int = microsecond

  @immutable
  def __str__(self) -> str:
    return self.isoFormat()

  @immutable
  def __repr__(self) -> str:
    return f"datetime.time({self.hour}, {self.minute}, {self.second})"

  @immutable
  def __cmp__(self, other: Self) -> int:
    return __cmp__(self.hour, other.hour) or __cmp__(self.minute, other.minute) or __cmp__(self.second, other.second) or __cmp__(self.microsecond, other.microsecond)

  @immutable
  def isoFormat(self) -> str:
    base: str = f"{_two(self.hour)}:{_two(self.minute)}:{_two(self.second)}"
    if self.microsecond != 0:
      return f"{base}.{_zfillInt(self.microsecond, 6)}"
    return base

  @immutable
  def strftime(self, fmt: str) -> str:
    return strftime(fmt, CTime(1900, 1, 1, self.hour, self.minute, self.second))


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
  def fromTimestamp(ts: float64) -> Self:
    st: CTime = localTime(ts)
    us: int = _usFromTimestamp(ts)
    return new._fromParts(
      st.tmYear,
      st.tmMon,
      st.tmMday,
      st.tmHour,
      st.tmMin,
      st.tmSec,
      us,
    )

  @staticmethod
  @immutable
  def now() -> Self:
    ts: float64 = wall_time()
    st: CTime = localTime(ts)
    us: int = _usFromTimestamp(ts)
    return new._fromParts(
      st.tmYear,
      st.tmMon,
      st.tmMday,
      st.tmHour,
      st.tmMin,
      st.tmSec,
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
    st: CTime = gmTime(ts)
    us: int = _usFromTimestamp(ts)
    return new._fromParts(
      st.tmYear,
      st.tmMon,
      st.tmMday,
      st.tmHour,
      st.tmMin,
      st.tmSec,
      us,
    )

  @staticmethod
  @immutable
  def _fromParts(
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
  def _fromYmdUs(ymd: _YMD, us: int64) -> Self:
    p: _HMSUS = _splitUs(us)
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
    _checkDate(year, month, day)
    _checkTime(hour, minute, second, microsecond)
    self._year: int = year
    self._month: int = month
    self._day: int = day
    self._hour: int = hour
    self._minute: int = minute
    self._second: int = second
    self._microsecond: int = microsecond
    self._ord: int = _ymdToOrd(year, month, day)
    self._us: int64 = microsecond
    self._us += second * _UsPerSecI
    self._us += minute * _MinuteUsI
    self._us += hour * _HourUsI

  @immutable
  def __str__(self) -> str:
    return self.isoFormat(" ")

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
    newUs: int64 = self._us + other._us
    extra: int64 = newUs // _UsPerDayI
    newUs %= _UsPerDayI
    p: _HMSUS = _splitUs(newUs)
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
    ymd: _YMD = _ordToYmd(self._ord + int(extra))
    return new(ymd.year, ymd.month, ymd.day, p.hour, p.minute, p.second, p.us)

  @immutable
  def __sub__(self, other: Self) -> timedelta:
    days: int = self._ord - other._ord
    us: int64 = self._us - other._us
    us += days * _UsPerDayI
    return new(0, 0, int(us))

  @immutable
  def date(self) -> date:
    return new.fromOrdinal(self._ord)

  @immutable
  def isoFormat(self, sep: str = "T") -> str:
    return self.date().isoFormat() + sep + self.time().isoFormat()

  @immutable
  def strftime(self, fmt: str) -> str:
    return strftime(
      fmt,
      CTime(self.year, self.month, self.day, self.hour, self.minute, self.second),
    )

  @immutable
  def time(self) -> time:
    return new(self.hour, self.minute, self.second, self.microsecond)

  @immutable
  def timestamp(self) -> float64:
    base: float64 = mkTime(
      CTime(self.year, self.month, self.day, self.hour, self.minute, self.second),
    )
    frac: float64 = self.microsecond * 1.0
    base += frac / 1000000.0
    return base
