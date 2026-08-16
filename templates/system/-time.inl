PY2CPP_IGNORE
#include "py2cpp/system/time.h"
#include "py2cpp/py_types.h"
PY2CPP_END

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <unistd.h>
#endif

static double _py_time_seconds_nonneg(double s)
{
  if (s < 0.0)
  {
    return 0.0;
  }
  return s;
}

static void _py_time_sleep_seconds(double secs)
{
  secs = _py_time_seconds_nonneg(secs);
  if (secs <= 0.0)
  {
    return;
  }
#ifdef _WIN32
  {
    double ms = (secs * 1000.0);
    if (ms > 4294967294.0)
    {
      ms = 4294967294.0;
    }
    DWORD dw = (DWORD)(ms + 0.5);
    if (dw == 0)
    {
      dw = 1;
    }
    ::Sleep(dw);
  }
#else
  {
    struct timespec req;
    struct timespec rem;
    double whole = 0.0;
    double frac = modf(secs, &whole);
    req.tv_sec = (time_t)whole;
    req.tv_nsec = (long)((frac * 1000000000.0) + 0.5);
    while ((nanosleep(&req, &rem) != 0))
    {
      req = rem;
    }
  }
#endif
}

PY2CPP_BEGIN_SCOPE

PyFloat64 py_time()
{
  time_t t = (::time)((time_t*)0);
  return (PyFloat64)((double)t);
}

void py_sleep(PyFloat64 seconds)
{
  _py_time_sleep_seconds((double)seconds);
}

PyFloat64 monotonic()
{
#ifdef _WIN32
  return (PyFloat64)((double)::GetTickCount64() / 1000.0);
#else
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
  {
    return (PyFloat64)0.0;
  }
  return (PyFloat64)((double)ts.tv_sec + ((double)ts.tv_nsec / 1000000000.0));
#endif
}

PyFloat64 perfCounter()
{
#ifdef _WIN32
  LARGE_INTEGER freq;
  LARGE_INTEGER ctr;
  if ((!::QueryPerformanceFrequency(&freq)) || (!::QueryPerformanceCounter(&ctr)))
  {
    return monotonic();
  }
  if (freq.QuadPart == 0)
  {
    return (PyFloat64)0.0;
  }
  return (PyFloat64)((double)ctr.QuadPart / (double)freq.QuadPart);
#else
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
  {
    return (PyFloat64)0.0;
  }
  return (PyFloat64)((double)ts.tv_sec + ((double)ts.tv_nsec / 1000000000.0));
#endif
}

PyFloat64 processTime()
{
#ifdef _WIN32
  FILETIME create;
  FILETIME exit_ft;
  FILETIME kernel;
  FILETIME user;
  ULARGE_INTEGER k;
  ULARGE_INTEGER u;
  if (!::GetProcessTimes(::GetCurrentProcess(), &create, &exit_ft, &kernel, &user))
  {
    return (PyFloat64)0.0;
  }
  k.LowPart = kernel.dwLowDateTime;
  k.HighPart = kernel.dwHighDateTime;
  u.LowPart = user.dwLowDateTime;
  u.HighPart = user.dwHighDateTime;
  return (PyFloat64)((double)(k.QuadPart + u.QuadPart) / 10000000.0);
#else
  return (PyFloat64)((double)::clock() / (double)CLOCKS_PER_SEC);
#endif
}

static CTime _py_tm_to_struct(const struct tm* pt, int is_dst)
{
  if (!pt)
  {
    return CTime(1970, 1, 1, 0, 0, 0);
  }
CTime st(
    pt->tm_year + 1900,
    pt->tm_mon + 1,
    pt->tm_mday,
    pt->tm_hour,
    pt->tm_min,
    pt->tm_sec);
  st.tmWday = pt->tm_wday;
  st.tmYday = pt->tm_yday + 1;
  st.tmIsdst = is_dst;
  return st;
}

static int _py_day_of_week(int y, int m, int d)
{
  static const int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  if (m < 3)
  {
    y -= 1;
  }
  return (y + y / 4 - y / 100 + y / 400 + t[m - 1] + d) % 7;
}

static void _py_struct_to_tm(const CTime& st, struct tm* pt)
{
  if (!pt)
  {
    return;
  }
  memset(pt, 0, sizeof(struct tm));
  pt->tm_year = st.tmYear - 1900;
  pt->tm_mon = st.tmMon - 1;
  pt->tm_mday = st.tmMday;
  pt->tm_hour = st.tmHour;
  pt->tm_min = st.tmMin;
  pt->tm_sec = st.tmSec;
  pt->tm_wday = _py_day_of_week(st.tmYear, st.tmMon, st.tmMday);
  pt->tm_isdst = st.tmIsdst;
}

PyStr pyStrftime(const PyStr& format, CTime st)
{
  struct tm t;
  _py_struct_to_tm(st, &t);
  char buf[256];
  buf[0] = '\0';
  char fmt[128];
  format.copyToSpan(PySpan<PyByte>((PyByte*)fmt, (PyInt)sizeof(fmt), 1));
  size_t n = ::strftime(buf, sizeof(buf), fmt, &t);
  if (n == 0)
  {
    return PyStr("");
  }
  return PyStr(buf);
}

CTime gmTime(PyFloat64 secs)
{
  time_t t = (time_t)((double)secs);
  struct tm buf;
  struct tm* pt = NULL;
#ifdef _WIN32
  if (gmtime_s(&buf, &t) == 0)
  {
    pt = &buf;
  }
#else
  pt = gmtime_r(&t, &buf);
#endif
  return _py_tm_to_struct(pt, -1);
}

CTime localTime(PyFloat64 secs)
{
  time_t t = (time_t)((double)secs);
  struct tm buf;
  struct tm* pt = NULL;
#ifdef _WIN32
  if (localtime_s(&buf, &t) == 0)
  {
    pt = &buf;
  }
#else
  pt = localtime_r(&t, &buf);
#endif
  int is_dst = -1;
  if (pt)
  {
    is_dst = pt->tm_isdst;
  }
  return _py_tm_to_struct(pt, is_dst);
}

PyFloat64 py_mkTime(CTime st)
{
  struct tm t;
  _py_struct_to_tm(st, &t);
  time_t out = ::mktime(&t);
  if (out == (time_t)-1)
  {
    return (PyFloat64)-1.0;
  }
  return (PyFloat64)((double)out);
}

CTime gmTimeNow()
{
  return gmTime(py_time());
}

CTime localTimeNow()
{
  return localTime(py_time());
}

PY2CPP_END_SCOPE
