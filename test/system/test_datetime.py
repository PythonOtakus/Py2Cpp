"""``datetime`` / 扩展 ``time`` 回归（Phase C 子集，无时区）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

from py2cpp.system.datetime import date, datetime, time, timedelta
from py2cpp.system.time import (
  asctime,
  gmtime,
  gmtime_now,
  localtime,
  mktime,
  strftime,
  strptime,
  c_time,
  time as wall_time,
)


class TimedeltaTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    d: timedelta = new(1, 7200, 0)
    self.assertTrue(d.total_seconds() > 86400.0)
    neg: timedelta = new(0, -30, 0)
    self.assertTrue(neg.total_seconds() < 0.0)


class DateTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    d: date = new(2020, 1, 15)
    self.assertEqual(d.year, 2020)
    self.assertEqual(d.month, 1)
    self.assertEqual(d.day, 15)
    self.assertEqual(d.isoformat(), "2020-01-15")
    d2: date = d + timedelta(10, 0, 0)
    self.assertEqual(d2.day, 25)
    diff: timedelta = d2 - d
    self.assertEqual(diff, timedelta(10, 0, 0))


class DateTimeTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    dt: datetime = new(2020, 6, 1, 12, 30, 45, 123456)
    self.assertEqual(dt.year, 2020)
    self.assertEqual(dt.hour, 12)
    self.assertEqual(dt.microsecond, 123456)
    self.assertEqual(dt.isoformat(), "2020-06-01T12:30:45.123456")
    dt2: datetime = dt + timedelta(0, 3600, 0)
    self.assertEqual(dt2.hour, 13)
    comb: datetime = new.combine(date(2021, 1, 1), time(8, 0, 0))
    self.assertEqual(comb.hour, 8)


class DateTimeNowTests(TestCaseMixin):
  _test_tag = 21

  @override
  def test(self):
    n: datetime = new.now()
    self.assertTrue(n.year >= 2020)
    u: datetime = new.utcnow()
    self.assertTrue(u.year >= 2020)
    ts: float64 = wall_time()
    f: datetime = new.fromtimestamp(ts)
    self.assertTrue(f.year >= 2020)


class TimeStructTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    st: c_time = strptime("2020-01-15", "%Y-%m-%d")
    self.assertEqual(st.tm_year, 2020)
    self.assertEqual(st.tm_mon, 1)
    self.assertEqual(st.tm_mday, 15)
    out: str = strftime("%Y-%m-%d", st)
    self.assertEqual(out, "2020-01-15")
    st2: c_time = gmtime_now()
    self.assertTrue(st2.tm_year >= 2020)
    txt: str = asctime(st)
    self.assertTrue(len(txt) > 10)


class MktimeTests(TestCaseMixin):
  _test_tag = 31

  @override
  def test(self):
    st: c_time = new(2020, 1, 1, 0, 0, 0)
    sec: float64 = mktime(st)
    self.assertTrue(sec > 0.0)
    dt: datetime = new.fromtimestamp(sec)
    self.assertEqual(dt.year, 2020)


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)
