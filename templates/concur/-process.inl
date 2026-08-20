#include "ffi/crt/stdio.h"
#include "ffi/crt/stdlib.h"
#include "ffi/crt/string.h"
#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#else
#include "ffi/crt/errno.h"
#include "ffi/crt/fcntl.h"
#include "ffi/crt/signal.h"
#include "ffi/posix/sys/types.h"
#include "ffi/posix/sys/wait.h"
#include "ffi/posix/unistd.h"
#endif

PY2CPP_IGNORE
#include "py2cpp/concur/process.h"
#include "py2cpp/core/exceptions.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/array.h"
#include "py2cpp/util/list.h"
#include "py2cpp/util/dict.h"
PY2CPP_END

struct PyProcessState
{
#if defined(_WIN32)
  PROCESS_INFORMATION pi;
  HANDLE out_rd;
  HANDLE out_wr;
  HANDLE err_rd;
  HANDLE err_wr;
  HANDLE in_rd;
  HANDLE in_wr;
  DWORD exit_code;
  BOOL started;
  BOOL done;
#else
  pid_t pid;
  int out_rd;
  int err_rd;
  int in_wr;
  int exit_code;
  int started;
  int done;
#endif
  PyList<PyStr> args;
  PyStr cwd;
  PyDict<PyStr, PyStr> env;
  PyInt stdin_mode;
  PyInt stdout_mode;
  PyInt stderr_mode;
};

static void _process_append_bytes(PyArray<PyChar>& codes, const char* p, int n)
{
  if ((!p) || n <= 0)
  {
    return;
  }
  int old = codes.__len__();
  codes.reshape(old + n, old);
  for (int i = 0; i < n; i++)
  {
    codes.__setitem__(old + i, (PyChar)(unsigned char)p[i]);
  }
}

static PyStr _process_codes_to_str(PyArray<PyChar>& codes)
{
  if (codes.__len__() <= 0)
  {
    return PyStr("");
  }
  return PyStr(codes);
}

#if defined(_WIN32)
static wchar_t* _process_utf8_to_wide(const PyStr& s)
{
  char buf[32768];
  s.copyToSpanUtf8(PySpan<PyByte>((PyByte*)buf, (PyInt)sizeof(buf), 1));
  int n = MultiByteToWideChar(CP_UTF8, 0, buf, -1, nullptr, 0);
  if (n <= 0)
  {
    return nullptr;
  }
  wchar_t* w = reinterpret_cast<wchar_t*>(static_cast<uintptr_t>(::ffi::crt::stdlib::pyiMalloc((PyUInt64)n * sizeof(wchar_t))));
  if (!w)
  {
    return nullptr;
  }
  MultiByteToWideChar(CP_UTF8, 0, buf, -1, w, n);
  return w;
}

static void _process_close_handle(HANDLE& h)
{
  if (h && h != INVALID_HANDLE_VALUE)
  {
    CloseHandle(h);
  }
  h = nullptr;
}

static HANDLE _process_nul_handle(DWORD access)
{
  SECURITY_ATTRIBUTES sa;
  sa.nLength = sizeof(sa);
  sa.bInheritHandle = TRUE;
  sa.lpSecurityDescriptor = nullptr;
  return CreateFileW(L"NUL", access, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, nullptr);
}

static void _process_append_quoted(wchar_t* dst, int& at, const wchar_t* src, int cap)
{
  int need_quote = 0;
  for (int i = 0; src[i]; i++)
  {
    if (src[i] == L' ' || src[i] == L'\t' || src[i] == L'"')
    {
      need_quote = 1;
      break;
    }
  }
  if (!need_quote)
  {
    for (int i = 0; src[i] && at + 1 < cap; i++)
    {
      dst[at++] = src[i];
    }
    return;
  }
  if (at + 1 < cap)
  {
    dst[at++] = L'"';
  }
  for (int i = 0; src[i] && at + 2 < cap; i++)
  {
    if (src[i] == L'"')
    {
      dst[at++] = L'\\';
    }
    dst[at++] = src[i];
  }
  if (at + 1 < cap)
  {
    dst[at++] = L'"';
  }
}

static wchar_t* _process_env_block(const PyDict<PyStr, PyStr>& env)
{
  PyInt n = env.__len__();
  if (n <= 0)
  {
    return nullptr;
  }
  wchar_t* block = reinterpret_cast<wchar_t*>(static_cast<uintptr_t>(::ffi::crt::stdlib::pyiMalloc(65536 * sizeof(wchar_t))));
  if (!block)
  {
    return nullptr;
  }
  int at = 0;
  for (PyInt i = 0; i < n && at + 4 < 65536; i++)
  {
    PyStr key = env.keyAt(i);
    PyStr val = env.valueAt(i);
    wchar_t* wk = _process_utf8_to_wide(key);
    wchar_t* wv = _process_utf8_to_wide(val);
    if ((!wk) || (!wv))
    {
      ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(wk));
      ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(wv));
      ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(block));
      return nullptr;
    }
    for (int j = 0; wk[j] && at + 3 < 65536; j++)
    {
      block[at++] = wk[j];
    }
    block[at++] = L'=';
    for (int j = 0; wv[j] && at + 2 < 65536; j++)
    {
      block[at++] = wv[j];
    }
    block[at++] = 0;
    ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(wk));
    ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(wv));
  }
  block[at++] = 0;
  return block;
}

static void _process_drain_avail(HANDLE h, PyArray<PyChar>& codes)
{
  if (!h)
  {
    return;
  }
  for (;;)
  {
    DWORD avail = 0;
    if (!PeekNamedPipe(h, nullptr, 0, nullptr, &avail, nullptr) || avail == 0)
    {
      return;
    }
    char stack[4096];
    DWORD n = 0;
    DWORD want = avail > (DWORD)sizeof(stack) ? (DWORD)sizeof(stack) : avail;
    if (!ReadFile(h, stack, want, &n, nullptr) || n == 0)
    {
      return;
    }
    _process_append_bytes(codes, stack, (int)n);
  }
}

static PyStr _process_read_rest(HANDLE h)
{
  PyArray<PyChar> codes;
  if (!h)
  {
    return PyStr("");
  }
  char stack[4096];
  for (;;)
  {
    DWORD n = 0;
    if (!ReadFile(h, stack, (DWORD)sizeof(stack), &n, nullptr) || n == 0)
    {
      break;
    }
    _process_append_bytes(codes, stack, (int)n);
  }
  return _process_codes_to_str(codes);
}
#endif

PyProcess::PyProcess(
  const PyList<PyStr, 0>& args,
  PyStr cwd,
  PyOptional<PyDict<PyStr, PyStr>> env_opt,
  PyInt stdin_mode,
  PyInt stdout_mode,
  PyInt stderr_mode
)
{
  PyDict<PyStr, PyStr> env;
  if (!(env_opt.__enum____get() == PyOptional<PyDict<PyStr, PyStr>>::Enum::None_))
  {
    env = env_opt.value__get();
  }
  PyProcessState* st = reinterpret_cast<PyProcessState*>(static_cast<uintptr_t>(::ffi::crt::stdlib::pyiCalloc(1, sizeof(PyProcessState))));
  if (!st)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  st->args = args;
  st->cwd = cwd;
  st->env = env;
  st->stdin_mode = stdin_mode;
  st->stdout_mode = stdout_mode;
  st->stderr_mode = stderr_mode;
#if defined(_WIN32)
  st->out_rd = nullptr;
  st->out_wr = nullptr;
  st->err_rd = nullptr;
  st->err_wr = nullptr;
  st->in_rd = nullptr;
  st->in_wr = nullptr;
  st->exit_code = 0;
  st->started = FALSE;
  st->done = FALSE;
  ZeroMemory(&st->pi, sizeof(st->pi));
  SECURITY_ATTRIBUTES sa;
  sa.nLength = sizeof(sa);
  sa.bInheritHandle = TRUE;
  sa.lpSecurityDescriptor = nullptr;
  if (stdout_mode == -1)
  {
    if (!CreatePipe(&st->out_rd, &st->out_wr, &sa, 0))
    {
      ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(st));
      throw PY2CPP_TYPE(PyOSError)();
    }
    SetHandleInformation(st->out_rd, HANDLE_FLAG_INHERIT, 0);
  }
  if (stderr_mode == -1)
  {
    if (!CreatePipe(&st->err_rd, &st->err_wr, &sa, 0))
    {
      ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(st));
      throw PY2CPP_TYPE(PyOSError)();
    }
    SetHandleInformation(st->err_rd, HANDLE_FLAG_INHERIT, 0);
  }
  if (stdin_mode == -1)
  {
    if (!CreatePipe(&st->in_rd, &st->in_wr, &sa, 0))
    {
      ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(st));
      throw PY2CPP_TYPE(PyOSError)();
    }
    SetHandleInformation(st->in_wr, HANDLE_FLAG_INHERIT, 0);
  }
#else
  st->pid = -1;
  st->out_rd = -1;
  st->err_rd = -1;
  st->in_wr = -1;
  st->exit_code = 0;
  st->started = 0;
  st->done = 0;
#endif
  this->_state = (PyUIntPtr)(uintptr_t)st;
}

PyProcess::PyProcess(PyProcess&& other)
{
  this->_state = other._state;
  other._state = 0;
}

PyProcess& PyProcess::operator=(PyProcess&& other)
{
  if (this != &other)
  {
    this->~PyProcess();
    this->_state = other._state;
    other._state = 0;
  }
  return *this;
}

PyProcess::~PyProcess()
{
  if (!_state)
  {
    return;
  }
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
#if defined(_WIN32)
  if (st->pi.hProcess)
  {
    CloseHandle(st->pi.hProcess);
  }
  if (st->pi.hThread)
  {
    CloseHandle(st->pi.hThread);
  }
  _process_close_handle(st->out_rd);
  _process_close_handle(st->out_wr);
  _process_close_handle(st->err_rd);
  _process_close_handle(st->err_wr);
  _process_close_handle(st->in_rd);
  _process_close_handle(st->in_wr);
#else
  if (st->out_rd >= 0)
  {
    close(st->out_rd);
  }
  if (st->err_rd >= 0)
  {
    close(st->err_rd);
  }
  if (st->in_wr >= 0)
  {
    close(st->in_wr);
  }
#endif
  ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(st));
  _state = 0;
}

void PyProcess::start()
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || st->started)
  {
    return;
  }
  int n = st->args.__len__();
  if (n <= 0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
#if defined(_WIN32)
  wchar_t cmdline[32768];
  int at = 0;
  for (int i = 0; i < n; i++)
  {
    wchar_t* w = _process_utf8_to_wide(st->args.__getitem__(i));
    if (!w)
    {
      throw PY2CPP_TYPE(PyOSError)();
    }
    if (i > 0 && at + 1 < 32768)
    {
      cmdline[at++] = L' ';
    }
    _process_append_quoted(cmdline, at, w, 32768);
    ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(w));
  }
  cmdline[at] = 0;
  STARTUPINFOW si;
  ZeroMemory(&si, sizeof(si));
  si.cb = sizeof(si);
  si.dwFlags = STARTF_USESTDHANDLES;
  if (st->stdin_mode == -1)
  {
    si.hStdInput = st->in_rd;
  }
  else if (st->stdin_mode == -2)
  {
    si.hStdInput = _process_nul_handle(GENERIC_READ);
  }
  else
  {
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  }
  if (st->stdout_mode == -1)
  {
    si.hStdOutput = st->out_wr;
  }
  else if (st->stdout_mode == -2)
  {
    si.hStdOutput = _process_nul_handle(GENERIC_WRITE);
  }
  else
  {
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
  }
  if (st->stderr_mode == -1)
  {
    si.hStdError = st->err_wr;
  }
  else if (st->stderr_mode == -2)
  {
    si.hStdError = _process_nul_handle(GENERIC_WRITE);
  }
  else
  {
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
  }
  wchar_t* wcwd = nullptr;
  if (st->cwd.__len__() > 0)
  {
    wcwd = _process_utf8_to_wide(st->cwd);
  }
  wchar_t* wenv = _process_env_block(st->env);
  DWORD flags = 0;
  if (wenv)
  {
    flags |= CREATE_UNICODE_ENVIRONMENT;
  }
  BOOL ok = CreateProcessW(
    nullptr, cmdline, nullptr, nullptr, TRUE, flags, wenv, wcwd, &si, &st->pi
  );
  ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(wcwd));
  ::ffi::crt::stdlib::pyiFree((PyUIntPtr)reinterpret_cast<uintptr_t>(wenv));
  if (st->stdin_mode == -2 && si.hStdInput && si.hStdInput != INVALID_HANDLE_VALUE)
  {
    CloseHandle(si.hStdInput);
  }
  if (st->stdout_mode == -2 && si.hStdOutput && si.hStdOutput != INVALID_HANDLE_VALUE)
  {
    CloseHandle(si.hStdOutput);
  }
  if (st->stderr_mode == -2 && si.hStdError && si.hStdError != INVALID_HANDLE_VALUE)
  {
    CloseHandle(si.hStdError);
  }
  _process_close_handle(st->out_wr);
  _process_close_handle(st->err_wr);
  _process_close_handle(st->in_rd);
  if (!ok)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  st->started = TRUE;
#else
  int out_pipe[2] = {-1, -1};
  int err_pipe[2] = {-1, -1};
  if (st->stdout_mode == -1 && pipe(out_pipe) != 0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  if (st->stderr_mode == -1 && pipe(err_pipe) != 0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  pid_t pid = fork();
  if (pid < 0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  if (pid == 0)
  {
    if (out_pipe[0] >= 0)
    {
      close(out_pipe[0]);
      dup2(out_pipe[1], STDOUT_FILENO);
      close(out_pipe[1]);
    }
    else if (st->stdout_mode == -2)
    {
      int nul = open("/dev/null", O_WRONLY);
      if (nul >= 0)
      {
        dup2(nul, STDOUT_FILENO);
        close(nul);
      }
    }
    if (err_pipe[0] >= 0)
    {
      close(err_pipe[0]);
      dup2(err_pipe[1], STDERR_FILENO);
      close(err_pipe[1]);
    }
    else if (st->stderr_mode == -2)
    {
      int nul = open("/dev/null", O_WRONLY);
      if (nul >= 0)
      {
        dup2(nul, STDERR_FILENO);
        close(nul);
      }
    }
    if (st->cwd.__len__() > 0)
    {
      char cbuf[4096];
      st->cwd.copyToSpanUtf8(PySpan<PyByte>((PyByte*)cbuf, (PyInt)sizeof(cbuf), 1));
      if (::ffi::posix::unistd::pyiChdir(cbuf) != 0)
      {
        _exit(127);
      }
    }
    char* argv[256];
    char storage[256][1024];
    int argc = n < 255 ? n : 255;
    for (int i = 0; i < argc; i++)
    {
      st->args.__getitem__(i).copyToSpanUtf8(
        PySpan<PyByte>((PyByte*)storage[i], (PyInt)sizeof(storage[i]), 1)
      );
      argv[i] = storage[i];
    }
    argv[argc] = nullptr;
    execvp(argv[0], argv);
    _exit(127);
  }
  if (out_pipe[1] >= 0)
  {
    close(out_pipe[1]);
  }
  if (err_pipe[1] >= 0)
  {
    close(err_pipe[1]);
  }
  st->pid = pid;
  st->out_rd = out_pipe[0];
  st->err_rd = err_pipe[0];
  st->started = 1;
#endif
}

PyProcess& PyProcess::__enter__()
{
  this->start();
  return *this;
}

void PyProcess::__exit__()
{
  if (this->running__get())
  {
    this->terminate();
  }
}
PyInt PyProcess::poll()
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started))
  {
    return -1;
  }
#if defined(_WIN32)
  DWORD code = 0;
  if (WaitForSingleObject(st->pi.hProcess, 0) == WAIT_OBJECT_0)
  {
    GetExitCodeProcess(st->pi.hProcess, &code);
    st->exit_code = code;
    st->done = TRUE;
    return (PyInt)code;
  }
  return -1;
#else
  int status = 0;
  pid_t r = waitpid(st->pid, &status, WNOHANG);
  if (r == st->pid)
  {
    st->exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
    st->done = 1;
    return (PyInt)st->exit_code;
  }
  return -1;
#endif
}

PyInt PyProcess::wait(PyFloat64 timeout)
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started))
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  if (timeout < 0.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
#if defined(_WIN32)
  DWORD ms = (timeout == PY2CPP_FLOAT64_INF) ? INFINITE : (DWORD)(timeout * 1000.0);
  DWORD r = WaitForSingleObject(st->pi.hProcess, ms);
  if (r == WAIT_TIMEOUT)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  DWORD code = 0;
  GetExitCodeProcess(st->pi.hProcess, &code);
  st->exit_code = code;
  st->done = TRUE;
  return (PyInt)code;
#else
  (void)timeout;
  int status = 0;
  if (waitpid(st->pid, &status, 0) != st->pid)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  st->exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
  st->done = 1;
  return (PyInt)st->exit_code;
#endif
}

void PyProcess::terminate()
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started))
  {
    return;
  }
#if defined(_WIN32)
  TerminateProcess(st->pi.hProcess, 1);
#else
  kill(st->pid, SIGTERM);
#endif
}

void PyProcess::kill()
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started))
  {
    return;
  }
#if defined(_WIN32)
  TerminateProcess(st->pi.hProcess, 1);
#else
  kill(st->pid, SIGKILL);
#endif
}

PyCompletedProcess PyProcess::communicate(PyStr input, PyFloat64 timeout)
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started))
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  if (timeout < 0.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
#if defined(_WIN32)
  if (st->in_wr && input.__len__() > 0)
  {
    char buf[32768];
    input.copyToSpanUtf8(PySpan<PyByte>((PyByte*)buf, (PyInt)sizeof(buf), 1));
    DWORD n = 0;
    WriteFile(st->in_wr, buf, (DWORD)::ffi::crt::string::pyiStrlen(buf), &n, nullptr);
  }
  _process_close_handle(st->in_wr);
  PyArray<PyChar> out_codes;
  PyArray<PyChar> err_codes;
  ULONGLONG start = GetTickCount64();
  DWORD total_ms = (timeout == PY2CPP_FLOAT64_INF) ? INFINITE : (DWORD)(timeout * 1000.0);
  for (;;)
  {
    _process_drain_avail(st->out_rd, out_codes);
    _process_drain_avail(st->err_rd, err_codes);
    DWORD PySlice = 10;
    if (total_ms != INFINITE)
    {
      ULONGLONG elapsed = GetTickCount64() - start;
      if (elapsed >= (ULONGLONG)total_ms)
      {
        TerminateProcess(st->pi.hProcess, 1);
        throw PY2CPP_TYPE(PyRuntimeError)();
      }
    }
    DWORD r = WaitForSingleObject(st->pi.hProcess, PySlice);
    if (r == WAIT_OBJECT_0)
    {
      break;
    }
  }
  DWORD code = 0;
  GetExitCodeProcess(st->pi.hProcess, &code);
  st->exit_code = code;
  st->done = TRUE;
  PyStr out = _process_codes_to_str(out_codes);
  PyStr err = _process_codes_to_str(err_codes);
  if (st->out_rd)
  {
    PyStr rest = _process_read_rest(st->out_rd);
    if (rest.__len__() > 0)
    {
      out = out.__add__(rest);
    }
  }
  if (st->err_rd)
  {
    PyStr rest = _process_read_rest(st->err_rd);
    if (rest.__len__() > 0)
    {
      err = err.__add__(rest);
    }
  }
  return PyCompletedProcess(st->args, (PyInt)st->exit_code, out, err);
#else
  (void)input;
  (void)timeout;
  this->wait(PY2CPP_FLOAT64_INF);
  PyArray<PyChar> out_codes;
  PyArray<PyChar> err_codes;
  char stack[4096];
  if (st->out_rd >= 0)
  {
    for (;;)
    {
      int n = (int)read(st->out_rd, stack, sizeof(stack));
      if (n <= 0)
      {
        break;
      }
      _process_append_bytes(out_codes, stack, n);
    }
  }
  if (st->err_rd >= 0)
  {
    for (;;)
    {
      int n = (int)read(st->err_rd, stack, sizeof(stack));
      if (n <= 0)
      {
        break;
      }
      _process_append_bytes(err_codes, stack, n);
    }
  }
  return PyCompletedProcess(
    st->args, (PyInt)st->exit_code, _process_codes_to_str(out_codes), _process_codes_to_str(err_codes)
  );
#endif
}

PyInt PyProcess::returnCode__get() const
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->done))
  {
    return -1;
  }
  return (PyInt)st->exit_code;
}

PyBool PyProcess::running__get() const
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started) || st->done)
  {
    return false;
  }
#if defined(_WIN32)
  return WaitForSingleObject(st->pi.hProcess, 0) == WAIT_TIMEOUT;
#else
  int status = 0;
  pid_t r = waitpid(st->pid, &status, WNOHANG);
  if (r == st->pid)
  {
    st->exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
    st->done = 1;
    return false;
  }
  return r == 0;
#endif
}
PyInt PyProcess::pid__get() const
{
  PyProcessState* st = (PyProcessState*)(uintptr_t)_state;
  if ((!st) || (!st->started))
  {
    return -1;
  }
#if defined(_WIN32)
  return (PyInt)st->pi.dwProcessId;
#else
  return (PyInt)st->pid;
#endif
}
