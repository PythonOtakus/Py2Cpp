#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows/winsock2.h"
#include "ffi/windows/ws2tcpip.h"
#pragma comment(lib, "ws2_32.lib")
#else
#include "ffi/posix/sys/types.h"
#include "ffi/posix/sys/socket.h"
#include "ffi/posix/netinet/in.h"
#include "ffi/posix/arpa/inet.h"
#include "ffi/posix/unistd.h"
#include "ffi/crt/fcntl.h"
#include "ffi/crt/errno.h"
#endif
#include <atomic>
#include "ffi/crt/string.h"

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
    throw PY2CPP_TYPE(PyOSError)();
  }
  _web_wsa_ready = true;
#endif
}

static void _web_throw_oserror()
{
  throw PY2CPP_TYPE(PyOSError)();
}

static int _web_last_error()
{
#ifdef _WIN32
  return WSAGetLastError();
#else
  return errno;
#endif
}

static bool _web_is_would_block(int err)
{
#ifdef _WIN32
  return err == WSAEWOULDBLOCK || err == WSAEINPROGRESS || err == WSAEALREADY;
#else
  return err == EWOULDBLOCK || err == EAGAIN || err == EINPROGRESS || err == EALREADY;
#endif
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

struct PyTcpSocketState
{
  std::atomic<int> refs;
  _web_sock_t sock;
  bool closed;
  bool nonblocking;
  bool has_timeout;
  double timeout_sec;

  PyTcpSocketState()
    : refs(1), sock(_web_invalid), closed(true),
      nonblocking(false), has_timeout(false), timeout_sec(0.0)
  {
  }
};

static PyTcpSocketState* _web_socket_state(PyUIntPtr handle)
{
  return (PyTcpSocketState*)(uintptr_t)handle;
}

static void _web_close_state(PyTcpSocketState* st)
{
  if (!st)
  {
    return;
  }
  if ((!st->closed) && (st->sock != _web_invalid))
  {
    _web_close_sock(st->sock);
  }
  st->sock = _web_invalid;
  st->closed = true;
}

static void _web_retain_state(PyTcpSocketState* st)
{
  if (st)
  {
    st->refs.fetch_add(1, std::memory_order_relaxed);
  }
}

static void _web_release_state(PyTcpSocketState* st)
{
  if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
  {
    _web_close_state(st);
    delete st;
  }
}

static _web_sock_t _web_require_open(PyTcpSocketState* st)
{
  if ((!st) || st->closed || st->sock == _web_invalid)
  {
    _web_throw_oserror();
  }
  return st->sock;
}

static void _web_apply_timeout(_web_sock_t sock, double sec)
{
#ifdef _WIN32
  int ms = (int)(sec * 1000.0);
  if (ms < 0)
  {
    ms = 0;
  }
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&ms, (int)sizeof(ms));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&ms, (int)sizeof(ms));
#else
  struct timeval tv;
  tv.tv_sec = (long)sec;
  tv.tv_usec = (long)((sec - (double)tv.tv_sec) * 1000000.0);
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif
}

static bool _web_set_sock_nonblocking(_web_sock_t sock, bool enabled)
{
#ifdef _WIN32
  u_long mode = enabled ? 1UL : 0UL;
  return ioctlsocket(sock, FIONBIO, &mode) == 0;
#else
  int flags = fcntl(sock, F_GETFL, 0);
  if (flags < 0)
  {
    return false;
  }
  if (enabled)
  {
    flags |= O_NONBLOCK;
  }
  else
  {
    flags &= ~O_NONBLOCK;
  }
  return fcntl(sock, F_SETFL, flags) == 0;
#endif
}

static int _web_socket_so_error(_web_sock_t sock)
{
  int err = 0;
#ifdef _WIN32
  int len = (int)sizeof(err);
  if (getsockopt(sock, SOL_SOCKET, SO_ERROR, (char*)&err, &len) != 0)
  {
    return _web_last_error();
  }
#else
  socklen_t len = sizeof(err);
  if (getsockopt(sock, SOL_SOCKET, SO_ERROR, &err, &len) != 0)
  {
    return errno;
  }
#endif
  return err;
}

static void _web_apply_pending_timeout(PyTcpSocketState* st)
{
  if (st && st->has_timeout && (!st->closed) && st->sock != _web_invalid)
  {
    _web_apply_timeout(st->sock, st->timeout_sec);
  }
}

static void _web_assign_open_sock(PyTcpSocketState* st, _web_sock_t sock)
{
  st->sock = sock;
  st->closed = false;
  if (st->nonblocking && !_web_set_sock_nonblocking(sock, true))
  {
    _web_close_state(st);
    _web_throw_oserror();
  }
  _web_apply_pending_timeout(st);
}

PyTcpSocket::PyTcpSocket()
{
  _state = (PyUIntPtr)(uintptr_t)(new PyTcpSocketState());
}

PyTcpSocket::~PyTcpSocket()
{
  PyTcpSocketState* st = _web_socket_state(_state);
  _web_release_state(st);
  _state = 0;
}

void PyTcpSocket::__copy__(const PyTcpSocket& other)
{
  if (_state == other._state)
  {
    return;
  }
  PyTcpSocketState* next = _web_socket_state(other._state);
  _web_retain_state(next);
  PyTcpSocketState* old = _web_socket_state(_state);
  if (old)
  {
    _web_release_state(old);
  }
  _state = other._state;
}

void PyTcpSocket::close()
{
  _web_close_state(_web_socket_state(_state));
}

PyBool PyTcpSocket::isClosed() const
{
  PyTcpSocketState* st = _web_socket_state(_state);
  return (!st) || st->closed;
}

void PyTcpSocket::connect(PyStr host, PyInt port)
{
  _web_ensure_wsa();
  PyTcpSocketState* st = _web_socket_state(_state);
  _web_close_state(st);
  char hbuf[256];
  host.copyToSpanUtf8(PySpan<PyByte>((PyByte*)hbuf, (PyInt)sizeof(hbuf), 1));
#ifdef _WIN32
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (s == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
  struct sockaddr_in addr = {};
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
  _web_assign_open_sock(st, s);
#else
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
  {
    _web_throw_oserror();
  }
  struct sockaddr_in addr = {};
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
  _web_assign_open_sock(st, s);
#endif
}

void PyTcpSocket::bind(PyStr host, PyInt port)
{
  _web_ensure_wsa();
  PyTcpSocketState* st = _web_socket_state(_state);
  _web_close_state(st);
  char hbuf[256];
  host.copyToSpanUtf8(PySpan<PyByte>((PyByte*)hbuf, (PyInt)sizeof(hbuf), 1));
#ifdef _WIN32
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (s == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
  int yes = 1;
  setsockopt(s, SOL_SOCKET, SO_REUSEADDR, (const char*)&yes, (int)sizeof(yes));
  struct sockaddr_in addr = {};
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
  _web_assign_open_sock(st, s);
#else
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
  {
    _web_throw_oserror();
  }
  int yes = 1;
  setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  struct sockaddr_in addr = {};
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
  _web_assign_open_sock(st, s);
#endif
}

void PyTcpSocket::listen(PyInt backlog)
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
#ifdef _WIN32
  if (::listen(sock, backlog) != 0)
  {
    _web_throw_oserror();
  }
#else
  if (::listen(sock, backlog) != 0)
  {
    _web_throw_oserror();
  }
#endif
}

PyTcpSocket PyTcpSocket::accept()
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
#ifdef _WIN32
  struct sockaddr_in peer;
  int plen = (int)sizeof(peer);
  _web_sock_t c = ::accept(sock, (struct sockaddr*)&peer, &plen);
  if (c == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
#else
  struct sockaddr_in peer;
  socklen_t plen = sizeof(peer);
  _web_sock_t c = ::accept(sock, (struct sockaddr*)&peer, &plen);
  if (c < 0)
  {
    _web_throw_oserror();
  }
#endif
  PyTcpSocket out = PyTcpSocket();
  PyTcpSocketState* out_st = _web_socket_state(out._state);
  out_st->sock = c;
  out_st->closed = false;
  return out;
}

void PyTcpSocket::setBlocking(PyBool blocking)
{
  PyTcpSocketState* st = _web_socket_state(_state);
  if (!st)
  {
    _web_throw_oserror();
  }
  st->nonblocking = !blocking;
  if ((!st->closed) && st->sock != _web_invalid)
  {
    if (!_web_set_sock_nonblocking(st->sock, st->nonblocking))
    {
      _web_throw_oserror();
    }
  }
}

PyInt PyTcpSocket::connectEx(PyStr host, PyInt port)
{
  _web_ensure_wsa();
  PyTcpSocketState* st = _web_socket_state(_state);
  _web_close_state(st);
  char hbuf[256];
  host.copyToSpanUtf8(PySpan<PyByte>((PyByte*)hbuf, (PyInt)sizeof(hbuf), 1));
#ifdef _WIN32
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (s == INVALID_SOCKET)
  {
    _web_throw_oserror();
  }
  if (st->nonblocking && !_web_set_sock_nonblocking(s, true))
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  struct sockaddr_in addr = {};
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)port);
  if (InetPtonA(AF_INET, hbuf, &addr.sin_addr) != 1)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  int rc = ::connect(s, (struct sockaddr*)&addr, (int)sizeof(addr));
  if (rc != 0)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      st->sock = s;
      st->closed = false;
      _web_apply_pending_timeout(st);
      return SocketWouldBlock;
    }
    _web_close_sock(s);
    _web_throw_oserror();
  }
#else
  _web_sock_t s = ::socket(AF_INET, SOCK_STREAM, 0);
  if (s < 0)
  {
    _web_throw_oserror();
  }
  if (st->nonblocking && !_web_set_sock_nonblocking(s, true))
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  struct sockaddr_in addr = {};
  addr.sin_family = AF_INET;
  addr.sin_port = htons((unsigned short)port);
  if (inet_pton(AF_INET, hbuf, &addr.sin_addr) <= 0)
  {
    _web_close_sock(s);
    _web_throw_oserror();
  }
  int rc = ::connect(s, (struct sockaddr*)&addr, sizeof(addr));
  if (rc != 0)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      st->sock = s;
      st->closed = false;
      _web_apply_pending_timeout(st);
      return SocketWouldBlock;
    }
    _web_close_sock(s);
    _web_throw_oserror();
  }
#endif
  st->sock = s;
  st->closed = false;
  _web_apply_pending_timeout(st);
  return SocketOk;
}

void PyTcpSocket::finishConnect()
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
  int err = _web_socket_so_error(sock);
  if (err != 0)
  {
    _web_throw_oserror();
  }
}

PyTcpSocket PyTcpSocket::acceptNonblocking()
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
  PyTcpSocket out = PyTcpSocket();
#ifdef _WIN32
  struct sockaddr_in peer;
  int plen = (int)sizeof(peer);
  _web_sock_t c = ::accept(sock, (struct sockaddr*)&peer, &plen);
  if (c == INVALID_SOCKET)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      return out;
    }
    _web_throw_oserror();
  }
#else
  struct sockaddr_in peer;
  socklen_t plen = sizeof(peer);
  _web_sock_t c = ::accept(sock, (struct sockaddr*)&peer, &plen);
  if (c < 0)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      return out;
    }
    _web_throw_oserror();
  }
#endif
  PyTcpSocketState* out_st = _web_socket_state(out._state);
  out_st->sock = c;
  out_st->closed = false;
  return out;
}

PyInt PyTcpSocket::send(PyArray<PyByte>& buf, PyInt end)
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
  if (end <= 0)
  {
    return 0;
  }
  int n = buf.__len__();
  if (end > n)
  {
    end = n;
  }
  const char* p = (const char*)(buf.PY2CPP_GETTER(view)()).at(0);
#ifdef _WIN32
  int sent = ::send(sock, p, end, 0);
  if (sent == SOCKET_ERROR)
  {
    _web_throw_oserror();
  }
#else
  ssize_t sent = ::send(sock, p, (size_t)end, 0);
  if (sent < 0)
  {
    _web_throw_oserror();
  }
#endif
  return (int)sent;
}

PyInt PyTcpSocket::sendRangeNonblocking(PyArray<PyByte>& buf, PyInt start, PyInt end)
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
  int n = buf.__len__();
  if (start < 0)
  {
    start = 0;
  }
  if (end > n)
  {
    end = n;
  }
  if (end <= start)
  {
    return 0;
  }
  const char* p = (const char*)(buf.PY2CPP_GETTER(view)()).at(start);
  int count = end - start;
#ifdef _WIN32
  int sent = ::send(sock, p, count, 0);
  if (sent == SOCKET_ERROR)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      return SocketWouldBlock;
    }
    _web_throw_oserror();
  }
#else
  ssize_t sent = ::send(sock, p, (size_t)count, 0);
  if (sent < 0)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      return SocketWouldBlock;
    }
    _web_throw_oserror();
  }
#endif
  return (int)sent;
}

PyInt PyTcpSocket::recv(PyArray<PyByte>& buf, PyInt cap)
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
  if (cap <= 0)
  {
    return 0;
  }
  int n = buf.__len__();
  if (cap > n)
  {
    cap = n;
  }
  char* p = (char*)(buf.PY2CPP_GETTER(view)()).at(0);
#ifdef _WIN32
  int got = ::recv(sock, p, cap, 0);
  if (got == SOCKET_ERROR)
  {
    _web_throw_oserror();
  }
#else
  ssize_t got = ::recv(sock, p, (size_t)cap, 0);
  if (got < 0)
  {
    _web_throw_oserror();
  }
#endif
  return (int)got;
}

PyInt PyTcpSocket::recvNonblocking(PyArray<PyByte>& buf, PyInt cap)
{
  _web_sock_t sock = _web_require_open(_web_socket_state(_state));
  if (cap <= 0)
  {
    return 0;
  }
  int n = buf.__len__();
  if (cap > n)
  {
    cap = n;
  }
  char* p = (char*)(buf.PY2CPP_GETTER(view)()).at(0);
#ifdef _WIN32
  int got = ::recv(sock, p, cap, 0);
  if (got == SOCKET_ERROR)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      return SocketWouldBlock;
    }
    _web_throw_oserror();
  }
#else
  ssize_t got = ::recv(sock, p, (size_t)cap, 0);
  if (got < 0)
  {
    int err = _web_last_error();
    if (_web_is_would_block(err))
    {
      return SocketWouldBlock;
    }
    _web_throw_oserror();
  }
#endif
  return (int)got;
}

void PyTcpSocket::setTimeout(PyFloat sec)
{
  PyTcpSocketState* st = _web_socket_state(_state);
  if (!st)
  {
    _web_throw_oserror();
  }
  st->has_timeout = true;
  st->timeout_sec = (double)sec;
  _web_apply_pending_timeout(st);
}

PyInt64 PyTcpSocket::fileno() const
{
  PyTcpSocketState* st = _web_socket_state(_state);
  if ((!st) || st->closed || st->sock == _web_invalid)
  {
    return -1;
  }
  return (PyInt64)(uintptr_t)st->sock;
}

PyBool PyTcpSocket::wouldBlock(PyInt code)
{
  return code == SocketWouldBlock;
}
