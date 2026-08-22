#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#include "ffi/crt/stdio.h"
#include "ffi/crt/stdlib.h"
#include "ffi/crt/string.h"
#include <atomic>
#else
#include "ffi/crt/errno.h"
#include "ffi/crt/signal.h"
#include "ffi/crt/stdlib.h"
#include "ffi/crt/string.h"
#include "ffi/posix/sys/types.h"
#include "ffi/posix/sys/wait.h"
#include "ffi/posix/unistd.h"
#endif

PY2CPP_IGNORE
#include "py2cpp/concur/process.h"
#include "py2cpp/core/delegate.h"
#include "py2cpp/core/exceptions.h"
#include "py2cpp/text/str.h"
PY2CPP_END

namespace py2cpp_concur_process_detail
{
  typedef PyCallable<void> ProcessTarget;

  static const char* k_exec_flag = "--py2cpp-process-exec=";
  static const char* k_invoke_flag = "--py2cpp-process-invoke=";

  struct ProcessState
  {
    std::atomic<int> refs;
#if defined(_WIN32)
    PROCESS_INFORMATION pi;
    DWORD exit_code;
    BOOL started;
    BOOL done;
    BOOL closed;
#else
    pid_t pid;
    int exit_code;
    int started;
    int done;
    int closed;
#endif
    ProcessTarget target;
    PY2CPP_TYPE(PyStr) name;

    ProcessState()
      : refs(1),
#if defined(_WIN32)
        exit_code(0),
        started(FALSE),
        done(FALSE),
        closed(FALSE),
#else
        pid(0),
        exit_code(0),
        started(0),
        done(0),
        closed(0),
#endif
        target(),
        name(PY2CPP_TYPE(PyStr)(""))
    {
#if defined(_WIN32)
      memset(&pi, 0, sizeof(pi));
#endif
    }
  };

  static ProcessState* alloc_state()
  {
    ProcessState* st = reinterpret_cast<ProcessState*>(
      static_cast<uintptr_t>(::ffi::crt::stdlib::pyiCalloc(1, sizeof(ProcessState)))
    );
    if (!st)
    {
      throw PY2CPP_TYPE(PyOSError)();
    }
    new (st) ProcessState();
    return st;
  }

  static void free_state(ProcessState* st)
  {
    if (!st)
    {
      return;
    }
    st->~ProcessState();
    ::ffi::crt::stdlib::pyiFree(reinterpret_cast<uintptr_t>(st));
  }

  static void retain_state(ProcessState* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  static void release_state(ProcessState* st)
  {
    if (!st)
    {
      return;
    }
    if (st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      free_state(st);
    }
  }

  struct ExecSlot
  {
    uintptr_t rva;
  };

  struct InvokeHdr
  {
    uintptr_t tramp_rva;
    uintptr_t fn_rva;
    int status;
  };

  static ProcessState* from_handle(PyUIntPtr handle)
  {
    return reinterpret_cast<ProcessState*>((uintptr_t)handle);
  }

  static bool is_free_void(const ProcessTarget& target)
  {
    return target._self == nullptr &&
      target._func == &py_callable_free_invoke<void>::call &&
      target._closure != nullptr;
  }

  static void (*free_void_fn(const ProcessTarget& target))()
  {
    return reinterpret_cast<void (*)()>((uintptr_t)target._closure);
  }

  template<typename Value>
  static bool is_free_value(const PyCallable<Value>& target)
  {
    return target._self == nullptr &&
      target._func == &py_callable_free_invoke<Value>::call &&
      target._closure != nullptr;
  }

  template<typename Value>
  static Value (*free_value_fn(const PyCallable<Value>& target))()
  {
    return reinterpret_cast<Value (*)()>((uintptr_t)target._closure);
  }

  static const char* match_flag(const char* arg, const char* flag)
  {
    size_t n = strlen(flag);
    if (strncmp(arg, flag, n) == 0)
    {
      return arg + n;
    }
    return nullptr;
  }

#if defined(_WIN32)
  static HMODULE module_base()
  {
    return GetModuleHandleW(nullptr);
  }

  static uintptr_t to_rva(void* fn)
  {
    return (uintptr_t)fn - (uintptr_t)module_base();
  }

  static void* from_rva(uintptr_t rva)
  {
    return reinterpret_cast<void*>((uintptr_t)module_base() + rva);
  }

  static void make_slot_name(char* out, int cap, const char* prefix)
  {
    DWORD pid = GetCurrentProcessId();
    DWORD tick = GetTickCount();
    static volatile LONG seq = 0;
    LONG n = InterlockedIncrement(&seq);
    _snprintf_s(
      out, (size_t)cap, _TRUNCATE, "Local\\%s-%lu-%lu-%ld", prefix, (unsigned long)pid, (unsigned long)tick, (long)n
    );
  }

  static HANDLE open_slot(const char* name, DWORD size, void** view)
  {
    HANDLE h = CreateFileMappingA(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, size, name);
    if (!h)
    {
      return nullptr;
    }
    void* p = MapViewOfFile(h, FILE_MAP_WRITE, 0, 0, size);
    if (!p)
    {
      CloseHandle(h);
      return nullptr;
    }
    *view = p;
    return h;
  }

  static int run_exec_slot(const char* name)
  {
    HANDLE h = OpenFileMappingA(FILE_MAP_READ, FALSE, name);
    if (!h)
    {
      return 1;
    }
    void* view = MapViewOfFile(h, FILE_MAP_READ, 0, 0, sizeof(ExecSlot));
    if (!view)
    {
      CloseHandle(h);
      return 1;
    }
    ExecSlot slot;
    memcpy(&slot, view, sizeof(slot));
    UnmapViewOfFile(view);
    CloseHandle(h);
    void (*fn)() = reinterpret_cast<void (*)()>(from_rva(slot.rva));
    if (!fn)
    {
      return 1;
    }
    fn();
    return 0;
  }

  template<typename Value>
  struct InvokeLayout
  {
    InvokeHdr hdr;
    Value value;
  };

  template<typename Value>
  static void invoke_tramp(void* view)
  {
    InvokeLayout<Value>* layout = reinterpret_cast<InvokeLayout<Value>*>(view);
    Value (*fn)() = reinterpret_cast<Value (*)()>(from_rva(layout->hdr.fn_rva));
    layout->value = fn();
    layout->hdr.status = 1;
  }

  static bool spawn_self(const char* flag, const char* slot_name, PROCESS_INFORMATION* pi)
  {
    wchar_t exe[MAX_PATH];
    DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH)
    {
      return false;
    }
    char cmdline_utf8[1024];
    _snprintf_s(cmdline_utf8, sizeof(cmdline_utf8), _TRUNCATE, "\"ignored\" %s%s", flag, slot_name);
    int wlen = MultiByteToWideChar(CP_UTF8, 0, cmdline_utf8, -1, nullptr, 0);
    if (wlen <= 0)
    {
      return false;
    }
    wchar_t* cmdline = reinterpret_cast<wchar_t*>(
      static_cast<uintptr_t>(::ffi::crt::stdlib::pyiMalloc((PyUInt64)wlen * sizeof(wchar_t)))
    );
    if (!cmdline)
    {
      return false;
    }
    MultiByteToWideChar(CP_UTF8, 0, cmdline_utf8, -1, cmdline, wlen);
    STARTUPINFOW si;
    memset(&si, 0, sizeof(si));
    si.cb = sizeof(si);
    memset(pi, 0, sizeof(*pi));
    BOOL ok = CreateProcessW(exe, cmdline, nullptr, nullptr, FALSE, 0, nullptr, nullptr, &si, pi);
    ::ffi::crt::stdlib::pyiFree(reinterpret_cast<uintptr_t>(cmdline));
    return ok != 0;
  }

  static void boot_worker()
  {
    const wchar_t* cmd = GetCommandLineW();
    if (!cmd)
    {
      return;
    }
    char buf[4096];
    int n = WideCharToMultiByte(CP_UTF8, 0, cmd, -1, buf, (int)sizeof(buf), nullptr, nullptr);
    if (n <= 0)
    {
      return;
    }
    const char* p = strstr(buf, k_exec_flag);
    if (p)
    {
      const char* slot = p + strlen(k_exec_flag);
      char name[256];
      int i = 0;
      while (slot[i] && slot[i] != ' ' && slot[i] != '"' && i < (int)sizeof(name) - 1)
      {
        name[i] = slot[i];
        i++;
      }
      name[i] = 0;
      int code = run_exec_slot(name);
      ExitProcess((UINT)code);
    }
    p = strstr(buf, k_invoke_flag);
    if (p)
    {
      const char* slot = p + strlen(k_invoke_flag);
      char name[256];
      int i = 0;
      while (slot[i] && slot[i] != ' ' && slot[i] != '"' && i < (int)sizeof(name) - 1)
      {
        name[i] = slot[i];
        i++;
      }
      name[i] = 0;
      HANDLE h = OpenFileMappingA(FILE_MAP_ALL_ACCESS, FALSE, name);
      if (!h)
      {
        ExitProcess(1);
      }
      void* view = MapViewOfFile(h, FILE_MAP_ALL_ACCESS, 0, 0, 0);
      if (!view)
      {
        CloseHandle(h);
        ExitProcess(1);
      }
      InvokeHdr* hdr = reinterpret_cast<InvokeHdr*>(view);
      typedef void (*Tramp)(void*);
      Tramp tramp = reinterpret_cast<Tramp>(from_rva(hdr->tramp_rva));
      if (tramp)
      {
        tramp(view);
      }
      UnmapViewOfFile(view);
      CloseHandle(h);
      ExitProcess(0);
    }
  }

  struct ProcessBoot
  {
    ProcessBoot()
    {
      boot_worker();
    }
  };
  static ProcessBoot g_process_boot;
#endif
}

namespace py2cpp {
namespace concur {
namespace process {

PyInt tryWorker(PyInt argc, PyUIntPtr argv_addr)
{
  char** argv = reinterpret_cast<char**>((uintptr_t)argv_addr);
  if (argc < 2 || !argv)
  {
    return -1;
  }
  for (PyInt i = 1; i < argc; i++)
  {
    char* arg = argv[i];
    if (!arg)
    {
      continue;
    }
    const char* slot = py2cpp_concur_process_detail::match_flag(
      arg, py2cpp_concur_process_detail::k_exec_flag
    );
    if (slot)
    {
#if defined(_WIN32)
      return (PyInt)py2cpp_concur_process_detail::run_exec_slot(slot);
#else
      (void)slot;
      return 1;
#endif
    }
  }
  return -1;
}

_PyProcessHandle::_PyProcessHandle()
{
  _state = (PyUIntPtr)(uintptr_t)py2cpp_concur_process_detail::alloc_state();
}

void _PyProcessHandle::__copy__(const _PyProcessHandle& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_process_detail::ProcessState* next =
    py2cpp_concur_process_detail::from_handle(other._state);
  py2cpp_concur_process_detail::retain_state(next);
  py2cpp_concur_process_detail::ProcessState* old =
    py2cpp_concur_process_detail::from_handle(_state);
  py2cpp_concur_process_detail::release_state(old);
  _state = other._state;
}

_PyProcessHandle::~_PyProcessHandle()
{
  py2cpp_concur_process_detail::ProcessState* st =
    py2cpp_concur_process_detail::from_handle(_state);
  if (st)
  {
    close();
    py2cpp_concur_process_detail::release_state(st);
  }
  _state = 0;
}

void _PyProcessHandle::start(py2cpp_concur_process_detail::ProcessTarget target, PY2CPP_TYPE(PyStr) name)
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || st->started || st->closed)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  st->target = target;
  st->name = name;
#if defined(_WIN32)
  if (!py2cpp_concur_process_detail::is_free_void(target))
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  char slot_name[256];
  py2cpp_concur_process_detail::make_slot_name(slot_name, (int)sizeof(slot_name), "py2cpp-exec");
  void* view = nullptr;
  HANDLE map = py2cpp_concur_process_detail::open_slot(
    slot_name, (DWORD)sizeof(py2cpp_concur_process_detail::ExecSlot), &view
  );
  if ((!map) || (!view))
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  py2cpp_concur_process_detail::ExecSlot slot;
  slot.rva = py2cpp_concur_process_detail::to_rva(
    reinterpret_cast<void*>(py2cpp_concur_process_detail::free_void_fn(target))
  );
  memcpy(view, &slot, sizeof(slot));
  UnmapViewOfFile(view);
  if (!py2cpp_concur_process_detail::spawn_self(
        py2cpp_concur_process_detail::k_exec_flag, slot_name, &st->pi
      ))
  {
    CloseHandle(map);
    throw PY2CPP_TYPE(PyOSError)();
  }
  CloseHandle(map);
  st->started = TRUE;
  st->done = FALSE;
#else
  pid_t pid = fork();
  if (pid < 0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  if (pid == 0)
  {
    try
    {
      st->target();
    }
    catch (...)
    {
    }
    _exit(0);
  }
  st->pid = pid;
  st->started = 1;
  st->done = 0;
#endif
}

PyBool _PyProcessHandle::join(PyFloat64 timeout)
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || (!st->started))
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  if (st->done)
  {
    return true;
  }
  if (timeout < 0.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
#if defined(_WIN32)
  DWORD millis = (timeout == PY2CPP_FLOAT64_INF) ? INFINITE : (DWORD)(timeout * 1000.0);
  DWORD wr = WaitForSingleObject(st->pi.hProcess, millis);
  if (wr == WAIT_TIMEOUT)
  {
    return false;
  }
  if (wr != WAIT_OBJECT_0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  DWORD code = 0;
  if (!GetExitCodeProcess(st->pi.hProcess, &code))
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  st->exit_code = code;
  st->done = TRUE;
  return true;
#else
  if (timeout == PY2CPP_FLOAT64_INF)
  {
    int status = 0;
    if (waitpid(st->pid, &status, 0) < 0)
    {
      throw PY2CPP_TYPE(PyOSError)();
    }
    st->exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
    st->done = 1;
    return true;
  }
  double remain = (double)timeout;
  while (remain > 0.0)
  {
    int status = 0;
    pid_t r = waitpid(st->pid, &status, WNOHANG);
    if (r == st->pid)
    {
      st->exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
      st->done = 1;
      return true;
    }
    if (r < 0)
    {
      throw PY2CPP_TYPE(PyOSError)();
    }
    usleep(10000);
    remain -= 0.01;
  }
  return false;
#endif
}

void _PyProcessHandle::terminate()
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || (!st->started) || st->done)
  {
    return;
  }
#if defined(_WIN32)
  TerminateProcess(st->pi.hProcess, 1);
#else
  ::kill(st->pid, SIGTERM);
#endif
}

void _PyProcessHandle::kill()
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || (!st->started) || st->done)
  {
    return;
  }
#if defined(_WIN32)
  TerminateProcess(st->pi.hProcess, 1);
#else
  ::kill(st->pid, SIGKILL);
#endif
}

void _PyProcessHandle::close()
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || st->closed)
  {
    return;
  }
#if defined(_WIN32)
  if (st->pi.hThread)
  {
    CloseHandle(st->pi.hThread);
    st->pi.hThread = nullptr;
  }
  if (st->pi.hProcess)
  {
    CloseHandle(st->pi.hProcess);
    st->pi.hProcess = nullptr;
  }
  st->closed = TRUE;
#else
  st->closed = 1;
#endif
}

PyBool _PyProcessHandle::PY2CPP_GETTER(alive)() const
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || (!st->started) || st->done)
  {
    return false;
  }
#if defined(_WIN32)
  DWORD wr = WaitForSingleObject(st->pi.hProcess, 0);
  if (wr == WAIT_TIMEOUT)
  {
    return true;
  }
  if (wr == WAIT_OBJECT_0)
  {
    DWORD code = 0;
    GetExitCodeProcess(st->pi.hProcess, &code);
    const_cast<py2cpp_concur_process_detail::ProcessState*>(st)->exit_code = code;
    const_cast<py2cpp_concur_process_detail::ProcessState*>(st)->done = TRUE;
  }
  return false;
#else
  int status = 0;
  pid_t r = waitpid(st->pid, &status, WNOHANG);
  if (r == 0)
  {
    return true;
  }
  if (r == st->pid)
  {
    const_cast<py2cpp_concur_process_detail::ProcessState*>(st)->exit_code =
      WIFEXITED(status) ? WEXITSTATUS(status) : -1;
    const_cast<py2cpp_concur_process_detail::ProcessState*>(st)->done = 1;
  }
  return false;
#endif
}

PyInt _PyProcessHandle::PY2CPP_GETTER(pid)() const
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
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

PyInt _PyProcessHandle::PY2CPP_GETTER(exitCode)() const
{
  py2cpp_concur_process_detail::ProcessState* st = py2cpp_concur_process_detail::from_handle(_state);
  if ((!st) || (!st->done))
  {
    return -1;
  }
  return (PyInt)st->exit_code;
}

template<typename Value>
Value _processInvoke(PyCallable<Value> fn)
{
#if defined(_WIN32)
  if (!py2cpp_concur_process_detail::is_free_value(fn))
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  typedef py2cpp_concur_process_detail::InvokeLayout<Value> Layout;
  char slot_name[256];
  py2cpp_concur_process_detail::make_slot_name(slot_name, (int)sizeof(slot_name), "py2cpp-inv");
  void* view = nullptr;
  HANDLE map = py2cpp_concur_process_detail::open_slot(slot_name, (DWORD)sizeof(Layout), &view);
  if ((!map) || (!view))
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  Layout* layout = reinterpret_cast<Layout*>(view);
  layout->hdr.tramp_rva = py2cpp_concur_process_detail::to_rva(
    reinterpret_cast<void*>(&py2cpp_concur_process_detail::invoke_tramp<Value>)
  );
  layout->hdr.fn_rva = py2cpp_concur_process_detail::to_rva(
    reinterpret_cast<void*>(py2cpp_concur_process_detail::free_value_fn(fn))
  );
  layout->hdr.status = 0;
  UnmapViewOfFile(view);

  PROCESS_INFORMATION pi;
  if (!py2cpp_concur_process_detail::spawn_self(
        py2cpp_concur_process_detail::k_invoke_flag, slot_name, &pi
      ))
  {
    CloseHandle(map);
    throw PY2CPP_TYPE(PyOSError)();
  }
  WaitForSingleObject(pi.hProcess, INFINITE);
  CloseHandle(pi.hThread);
  CloseHandle(pi.hProcess);

  view = MapViewOfFile(map, FILE_MAP_READ, 0, 0, sizeof(Layout));
  if (!view)
  {
    CloseHandle(map);
    throw PY2CPP_TYPE(PyOSError)();
  }
  layout = reinterpret_cast<Layout*>(view);
  if (layout->hdr.status != 1)
  {
    UnmapViewOfFile(view);
    CloseHandle(map);
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  Value result = layout->value;
  UnmapViewOfFile(view);
  CloseHandle(map);
  return result;
#else
  int fds[2];
  if (pipe(fds) != 0)
  {
    throw PY2CPP_TYPE(PyOSError)();
  }
  pid_t child = fork();
  if (child < 0)
  {
    close(fds[0]);
    close(fds[1]);
    throw PY2CPP_TYPE(PyOSError)();
  }
  if (child == 0)
  {
    close(fds[0]);
    Value result = fn();
    const char* p = reinterpret_cast<const char*>(&result);
    size_t left = sizeof(Value);
    while (left > 0)
    {
      ssize_t n = write(fds[1], p, left);
      if (n <= 0)
      {
        _exit(1);
      }
      p += (size_t)n;
      left -= (size_t)n;
    }
    close(fds[1]);
    _exit(0);
  }
  close(fds[1]);
  Value result;
  char* p = reinterpret_cast<char*>(&result);
  size_t left = sizeof(Value);
  while (left > 0)
  {
    ssize_t n = read(fds[0], p, left);
    if (n <= 0)
    {
      close(fds[0]);
      waitpid(child, nullptr, 0);
      throw PY2CPP_TYPE(PyOSError)();
    }
    p += (size_t)n;
    left -= (size_t)n;
  }
  close(fds[0]);
  int status = 0;
  waitpid(child, &status, 0);
  if ((!WIFEXITED(status)) || WEXITSTATUS(status) != 0)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  return result;
#endif
}

} // namespace process
} // namespace concur
} // namespace py2cpp
