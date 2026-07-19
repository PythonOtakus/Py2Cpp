#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#endif
#include <string.h>

PY2CPP_IGNORE
#include "py2cpp/web/socket.h"
#include "py2cpp/text/str.h"
PY2CPP_END

static bool _web_wsa_ready = false;

static void _web_ensure_wsa()
{
#ifdef _WIN32
  if (_web_wsa_ready)
  {
    return;
  }
  WSADATA wsa;
  if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0)
  {
    throw PY2CPP_TYPE(OSError)();
  }
  _web_wsa_ready = true;
#endif
}

static void _web_throw_oserror()
{
  throw PY2CPP_TYPE(OSError)();
}

#ifdef _WIN32
typedef SOCKET _web_sock_t;
static const _web_sock_t _web_invalid = INVALID_SOCKET;
static void _web_close_sock(_web_sock_t s)
{
  if (s != INVALID_SOCKET)
  {
    closesocket(s);
  }
}
#else
typedef int _web_sock_t;
static const _web_sock_t _web_invalid = -1;
static void _web_close_sock(_web_sock_t s)
{
  if (s >= 0)
  {
    close(s);
  }
}
#endif

static _web_sock_t _web_sock_from_u64(unsigned long long v)
{
#ifdef _WIN32
  return (_web_sock_t)v;
#else
  return (_web_sock_t)v;
#endif
}

PyTcpSocket::PyTcpSocket()
{
  _sock = (unsigned long long)_web_invalid;
  _closed = true;
}

PyTcpSocket::~PyTcpSocket()
{
  close();
}

void PyTcpSocket::close()
{
  if ((!_closed) && (_sock != (unsigned long long)_web_invalid))
  {
    _web_close_sock(_web_sock_from_u64(_sock));
  }
  _sock = (unsigned long long)_web_invalid;
  _closed = true;
}

PyBool PyTcpSocket::is_closed() const
{
  return _closed;
}

void PyTcpSocket::connect(PyStr host, PyInt port)
{
  _web_ensure_wsa();
  close();
  char hbuf[256];
  host.copy_to_span(PySpan<PyByte>((PyByte*)hbuf, (PyInt)sizeof(hbuf), 1));
#ifdef _WIN32
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (s == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)port);
  if (InetPtonA(AF_INET, hbuf, &addr.sin_addr) != 1)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  if (::connect(s, (struct sockaddr*)&addr, (int)sizeof(addr)) != 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  _sock = (unsigned long long)s;
  _closed = false;
#else
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
  {
    _web_throw_oserror();
  }
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)port);
  if (inet_pton(AF_INET, hbuf, &addr.sin_addr) <= 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  if (::connect(s, (struct sockaddr*)&addr, sizeof(addr)) != 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  _sock = (unsigned long long)s;
  _closed = false;
#endif
}

void PyTcpSocket::bind(PyStr host, PyInt port)
{
  _web_ensure_wsa();
  close();
  char hbuf[256];
  host.copy_to_span(PySpan<PyByte>((PyByte*)hbuf, (PyInt)sizeof(hbuf), 1));
#ifdef _WIN32
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (s == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
  int yes = 1;
  setsockopt(s, SOL_SOCKET, SO_REUSEADDR, (const char*)&yes, (int)sizeof(yes));
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)port);
  if (InetPtonA(AF_INET, hbuf, &addr.sin_addr) != 1)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  if (::bind(s, (struct sockaddr*)&addr, (int)sizeof(addr)) != 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  _sock = (unsigned long long)s;
  _closed = false;
#else
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
  {
    _web_throw_oserror();
  }
  int yes = 1;
  setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)port);
  if (inet_pton(AF_INET, hbuf, &addr.sin_addr) <= 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  if (::bind(s, (struct sockaddr*)&addr, sizeof(addr)) != 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  _sock = (unsigned long long)s;
  _closed = false;
#endif
}

void PyTcpSocket::listen(PyInt backlog)
{
  if (_closed)
  {
    _web_throw_oserror();
  }
#ifdef _WIN32
  if (::listen(_web_sock_from_u64(_sock), backlog) != 0)
  {
    _web_throw_oserror();
  }
#else
  if (::listen(_web_sock_from_u64(_sock), backlog) != 0)
  {
    _web_throw_oserror();
  }
#endif
}

PyTcpSocket PyTcpSocket::accept()
{
  if (_closed)
  {
    _web_throw_oserror();
  }
#ifdef _WIN32
  struct sockaddr_in peer;
  int plen = (int)sizeof(peer);
  _web_sock_t c = ::accept(_web_sock_from_u64(_sock), (struct sockaddr*)&peer, &plen);
  if (c == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
#else
  struct sockaddr_in peer;
  socklen_t plen = sizeof(peer);
  _web_sock_t c = ::accept(_web_sock_from_u64(_sock), (struct sockaddr*)&peer, &plen);
  if (c < 0)
  {
    _web_throw_oserror();
  }
#endif
PyTcpSocket out = PyTcpSocket();
  out._sock = (unsigned long long)c;
  out._closed = false;
  return out;
}

PyInt PyTcpSocket::send(PyArray<PyByte>& buf, PyInt end)
{
  if (_closed)
  {
    _web_throw_oserror();
  }
  if (end <= 0)
  {
    return 0;
  }
  int n = buf.__len__();
  if (end > n)
  {
    end = n;
  }
  const char* p = (const char*)(buf.view__get()).at(0);
#ifdef _WIN32
  int sent = ::send(_web_sock_from_u64(_sock), p, end, 0);
  if (sent == SOCKET_ERROR)
  {
    _web_throw_oserror();
  }
#else
  ssize_t sent = ::send(_web_sock_from_u64(_sock), p, (size_t)end, 0);
  if (sent < 0)
  {
    _web_throw_oserror();
  }
#endif
  return (int)sent;
}

PyInt PyTcpSocket::recv(PyArray<PyByte>& buf, PyInt cap)
{
  if (_closed)
  {
    _web_throw_oserror();
  }
  if (cap <= 0)
  {
    return 0;
  }
  int n = buf.__len__();
  if (cap > n)
  {
    cap = n;
  }
  char* p = (char*)(buf.view__get()).at(0);
#ifdef _WIN32
  int got = ::recv(_web_sock_from_u64(_sock), p, cap, 0);
  if (got == SOCKET_ERROR)
  {
    _web_throw_oserror();
  }
#else
  ssize_t got = ::recv(_web_sock_from_u64(_sock), p, (size_t)cap, 0);
  if (got < 0)
  {
    _web_throw_oserror();
  }
#endif
  return (int)got;
}

void PyTcpSocket::set_timeout(PyFloat sec)
{
  if (_closed)
  {
    _web_throw_oserror();
  }
#ifdef _WIN32
  int ms = (int)(sec * 1000.0);
  if (ms < 0)
  {
    ms = 0;
  }
  setsockopt(_web_sock_from_u64(_sock), SOL_SOCKET, SO_RCVTIMEO, (const char*)&ms, (int)sizeof(ms));
  setsockopt(_web_sock_from_u64(_sock), SOL_SOCKET, SO_SNDTIMEO, (const char*)&ms, (int)sizeof(ms));
#else
  struct timeval tv;
  tv.tv_sec = (long)sec;
  tv.tv_usec = (long)((sec - (double)tv.tv_sec) * 1000000.0);
  setsockopt(_web_sock_from_u64(_sock), SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(_web_sock_from_u64(_sock), SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
}

