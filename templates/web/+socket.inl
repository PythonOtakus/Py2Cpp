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
#include <atomic>
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

struct PyTcpSocketState
{
  std::atomic<int> refs;
  _web_sock_t sock;
  bool closed;
  bool has_timeout;
  double timeout_sec;

  PyTcpSocketState()
    : refs(1), sock(_web_invalid), closed(true),
      has_timeout(false), timeout_sec(0.0)
  {
  }
};

static PyTcpSocketState* _web_socket_state(PyUPtr handle)
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

static void _web_apply_pending_timeout(PyTcpSocketState* st)
{
  if (st && st->has_timeout && (!st->closed) && st->sock != _web_invalid)
  {
    _web_apply_timeout(st->sock, st->timeout_sec);
  }
}

PyTcpSocket::PyTcpSocket()
{
  _state = (PyUPtr)(uintptr_t)(new PyTcpSocketState());
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
  _web_release_state(old);
  _state = other._state;
}

void PyTcpSocket::close()
{
  _web_close_state(_web_socket_state(_state));
}

PyBool PyTcpSocket::is_closed() const
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
  st->sock = s;
  st->closed = false;
  _web_apply_pending_timeout(st);
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
  st->sock = s;
  st->closed = false;
  _web_apply_pending_timeout(st);
#endif
}

void PyTcpSocket::bind(PyStr host, PyInt port)
{
  _web_ensure_wsa();
  PyTcpSocketState* st = _web_socket_state(_state);
  _web_close_state(st);
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
  st->sock = s;
  st->closed = false;
  _web_apply_pending_timeout(st);
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
  st->sock = s;
  st->closed = false;
  _web_apply_pending_timeout(st);
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

void PyTcpSocket::set_timeout(PyFloat sec)
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

