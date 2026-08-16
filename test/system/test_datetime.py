"""``datetime`` / 扩展 ``time`` 回归（Phase C 子集，无时区）。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.system.datetime import date, datetime, time, timedelta
from py2cpp.system.time import ascTime, gmTime, gmTimeNow, localTime, mkTime, strftime, strptime, CTime, time as wall_time

class TimedeltaTests(TestCaseMixin):
    _testTag = 1

    @override
    def test(self):
        d: timedelta = new(1, 7200, 0)
        self.assertTrue(d.totalSeconds() > 86400.0)
        neg: timedelta = new(0, -30, 0)
        self.assertTrue(neg.totalSeconds() < 0.0)

class DateTests(TestCaseMixin):
    _testTag = 10

    @override
    def test(self):
        d: date = new(2020, 1, 15)
        self.assertEqual(d.year, 2020)
        self.assertEqual(d.month, 1)
        self.assertEqual(d.day, 15)
        self.assertEqual(d.isoFormat(), '2020-01-15')
        d2: date = d + timedelta(10, 0, 0)
        self.assertEqual(d2.day, 25)
        diff: timedelta = d2 - d
        self.assertEqual(diff, timedelta(10, 0, 0))

class DateTimeTests(TestCaseMixin):
    _testTag = 20

    @override
    def test(self):
        dt: datetime = new(2020, 6, 1, 12, 30, 45, 123456)
        self.assertEqual(dt.year, 2020)
        self.assertEqual(dt.hour, 12)
        self.assertEqual(dt.microsecond, 123456)
        self.assertEqual(dt.isoFormat(), '2020-06-01T12:30:45.123456')
        dt2: datetime = dt + timedelta(0, 3600, 0)
        self.assertEqual(dt2.hour, 13)
        comb: datetime = new.combine(date(2021, 1, 1), time(8, 0, 0))
        self.assertEqual(comb.hour, 8)

class DateTimeNowTests(TestCaseMixin):
    _testTag = 21

    @override
    def test(self):
        n: datetime = new.now()
        self.assertTrue(n.year >= 2020)
        u: datetime = new.utcnow()
        self.assertTrue(u.year >= 2020)
        ts: float64 = wall_time()
        f: datetime = new.fromTimestamp(ts)
        self.assertTrue(f.year >= 2020)

class TimeStructTests(TestCaseMixin):
    _testTag = 30

    @override
    def test(self):
        st: CTime = strptime('2020-01-15', '%Y-%m-%d')
        self.assertEqual(st.tmYear, 2020)
        self.assertEqual(st.tmMon, 1)
        self.assertEqual(st.tmMday, 15)
        out: str = strftime('%Y-%m-%d', st)
        self.assertEqual(out, '2020-01-15')
        st2: CTime = gmTimeNow()
        self.assertTrue(st2.tmYear >= 2020)
        txt: str = ascTime(st)
        self.assertTrue(len(txt) > 10)

class MktimeTests(TestCaseMixin):
    _testTag = 31

    @override
    def test(self):
        sec: float64 = mkTime(CTime(2020, 1, 1, 0, 0, 0))
        self.assertTrue(sec > 0.0)
        dt: datetime = new.fromTimestamp(sec)
        self.assertEqual(dt.year, 2020)

def main():
    suite: TestSuite = new()
    for Class in TestCaseMixin.iterSubclasses(sortConst='_testTag'):
        suite.addTest(Class())
    return TextTestRunner().run(suite)
