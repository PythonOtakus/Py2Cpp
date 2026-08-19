#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#else
#include "ffi/posix/pthread.h"
#if defined(__linux__)
#include "ffi/posix/sys/syscall.h"
#include "ffi/posix/unistd.h"
#endif
#endif

PY2CPP_IGNORE
#include "py2cpp/concur/thread.h"
#include "py2cpp/core/delegate.h"
#include "py2cpp/core/exceptions.h"
#include "py2cpp/util/deque.h"
#include "py2cpp/util/list.h"
PY2CPP_END

namespace py2cpp_concur_thread_detail
{
  typedef PyCallable<void> ThreadTarget;
  struct ThreadState;

  static std::atomic<PyInt64> next_ident(1);
  static thread_local PyInt64 tls_ident = 0;
  static thread_local ThreadState* tls_thread_state = nullptr;

  static PyInt64 ensure_ident()
  {
    if (tls_ident == 0)
    {
      tls_ident = next_ident.fetch_add(1, std::memory_order_relaxed);
      if (tls_ident == 0)
      {
        tls_ident = next_ident.fetch_add(1, std::memory_order_relaxed);
      }
    }
    return tls_ident;
  }

  static PyInt64 current_native_id()
  {
#ifdef _WIN32
    return (PyInt64)::GetCurrentThreadId();
#elif defined(__linux__)
    return (PyInt64)::syscall(SYS_gettid);
#elif defined(__APPLE__)
    uint64_t tid = 0;
    pthread_threadid_np(NULL, &tid);
    return (PyInt64)tid;
#else
    return (PyInt64)(uintptr_t)pthread_self();
#endif
  }

  static bool timed_wait_cv(
    std::condition_variable& cv,
    std::unique_lock<std::mutex>& lock,
    double timeout)
  {
    if (timeout < 0.0)
    {
      cv.wait(lock);
      return true;
    }
    if (timeout <= 0.0)
    {
      return false;
    }
    std::chrono::duration<double> dur(timeout);
    return cv.wait_for(lock, dur) != std::cv_status::timeout;
  }

  template<typename T>
  struct AtomicState
  {
    std::atomic<int> refs;
    std::atomic<T> value;

    explicit AtomicState(T init) : refs(1), value(init)
    {
    }
  };

  template<typename T>
  struct QueueState
  {
    std::atomic<int> refs;
    std::mutex mutex;
    std::condition_variable not_empty;
    std::condition_variable not_full;
    std::condition_variable all_tasks_done;
    PY2CPP_TYPE(PyDeque)<T> items;
    PyInt maxsize;
    PyInt unfinished_tasks;
    bool shutdown;
    bool immediate;

    explicit QueueState(PyInt maxsize_)
      : refs(1), maxsize(maxsize_), unfinished_tasks(0),
        shutdown(false), immediate(false)
    {
    }
  };

  struct LockState
  {
    std::atomic<int> refs;
    std::mutex mutex;
    std::condition_variable cv;
    bool locked;

    LockState() : refs(1), locked(false)
    {
    }
  };

  struct RLockState
  {
    std::atomic<int> refs;
    std::mutex mutex;
    std::condition_variable cv;
    PyInt64 owner;
    PyInt recursion;

    RLockState() : refs(1), owner(0), recursion(0)
    {
    }
  };

  enum ConditionLockKind
  {
    CONDITION_LOCK,
    CONDITION_RLOCK
  };

  struct ConditionState
  {
    std::atomic<int> refs;
    std::mutex mutex;
    std::condition_variable cv;
    ConditionLockKind lock_kind;
    void* lock_state;
    PyInt waiters;
    bool closing;

    ConditionState(ConditionLockKind kind, void* lock)
      : refs(1), lock_kind(kind), lock_state(lock), waiters(0), closing(false)
    {
    }
  };

  struct ThreadState
  {
    std::atomic<int> refs;
    std::mutex mutex;
    std::condition_variable cv;
    std::thread worker;
    ThreadTarget target;
    bool started;
    bool running;
    bool finished;
    bool joined;
    PyInt64 ident;
    PyInt64 nativeId;
    PY2CPP_TYPE(PyStr) name;
    bool daemon;
    bool registered;
    ThreadState* registry_prev;
    ThreadState* registry_next;

    ThreadState()
      : refs(1), target(), started(false), running(false), finished(false),
        joined(false), ident(0), nativeId(0), name(PY2CPP_TYPE(PyStr)("")),
        daemon(false), registered(false), registry_prev(NULL), registry_next(NULL)
    {
    }

    ~ThreadState()
    {
      if (worker.joinable())
      {
        if (worker.get_id() == std::this_thread::get_id())
        {
          worker.detach();
        }
        else
        {
          worker.join();
        }
      }
    }
  };

  static std::mutex registry_mutex;
  static ThreadState* registry_head = NULL;
  static ThreadState* main_thread_state = NULL;

  static void retain_thread(ThreadState* st);
  static void release_thread(ThreadState* st);

  static LockState* lock_from_handle(PyUPtr handle)
  {
    return reinterpret_cast<LockState*>((uintptr_t)handle);
  }

  static RLockState* rlock_from_handle(PyUPtr handle)
  {
    return reinterpret_cast<RLockState*>((uintptr_t)handle);
  }

  static ConditionState* condition_from_handle(PyUPtr handle)
  {
    return reinterpret_cast<ConditionState*>((uintptr_t)handle);
  }

  static ThreadState* thread_from_handle(PyUPtr handle)
  {
    return reinterpret_cast<ThreadState*>((uintptr_t)handle);
  }

  static void registry_link_locked(ThreadState* st)
  {
    if (!st || st->registered)
    {
      return;
    }
    st->registry_prev = NULL;
    st->registry_next = registry_head;
    if (registry_head)
    {
      registry_head->registry_prev = st;
    }
    registry_head = st;
    st->registered = true;
  }

  static void registry_unlink_locked(ThreadState* st)
  {
    if (!st || !st->registered)
    {
      return;
    }
    if (st->registry_prev)
    {
      st->registry_prev->registry_next = st->registry_next;
    }
    else
    {
      registry_head = st->registry_next;
    }
    if (st->registry_next)
    {
      st->registry_next->registry_prev = st->registry_prev;
    }
    st->registry_prev = NULL;
    st->registry_next = NULL;
    st->registered = false;
  }

  static void register_active_thread(ThreadState* st)
  {
    if (!st)
    {
      return;
    }
    std::lock_guard<std::mutex> lk(registry_mutex);
    if (!st->registered)
    {
      retain_thread(st);
      registry_link_locked(st);
    }
  }

  static void unregister_active_thread(ThreadState* st)
  {
    bool should_release = false;
    {
      std::lock_guard<std::mutex> lk(registry_mutex);
      if (st && st->registered)
      {
        registry_unlink_locked(st);
        should_release = true;
      }
    }
    if (should_release)
    {
      release_thread(st);
    }
  }

  static ThreadState* ensure_main_thread_registered()
  {
    PyInt64 ident = ensure_ident();
    std::lock_guard<std::mutex> lk(registry_mutex);
    if (!main_thread_state)
    {
      ThreadState* st = new ThreadState();
      st->started = true;
      st->running = true;
      st->finished = false;
      st->joined = true;
      st->ident = ident;
      st->nativeId = current_native_id();
      st->name = PY2CPP_TYPE(PyStr)("MainThread");
      st->daemon = false;
      main_thread_state = st;
      retain_thread(st);
      registry_link_locked(st);
    }
    if (main_thread_state->ident == ident && tls_thread_state == NULL)
    {
      tls_thread_state = main_thread_state;
    }
    return main_thread_state;
  }

  static ThreadState* current_thread_state()
  {
    if (tls_thread_state)
    {
      return tls_thread_state;
    }
    ensure_main_thread_registered();
    if (tls_thread_state)
    {
      return tls_thread_state;
    }
    return main_thread_state;
  }

  template<typename T>
  static AtomicState<T>* atomic_from_handle(PyUPtr handle)
  {
    return reinterpret_cast<AtomicState<T>*>((uintptr_t)handle);
  }

  template<typename T>
  static QueueState<T>* queue_from_handle(PyUPtr handle)
  {
    return reinterpret_cast<QueueState<T>*>((uintptr_t)handle);
  }

  static void retain_lock(LockState* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  static void release_lock(LockState* st)
  {
    if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      delete st;
    }
  }

  static void retain_rlock(RLockState* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  static void release_rlock(RLockState* st)
  {
    if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      delete st;
    }
  }

  static void retain_condition(ConditionState* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  static void release_condition(ConditionState* st)
  {
    if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      {
        std::unique_lock<std::mutex> lk(st->mutex);
        st->closing = true;
        lk.unlock();
        st->cv.notify_all();
        lk.lock();
        while (st->waiters > 0)
        {
          st->cv.wait(lk);
        }
      }
      if (st->lock_kind == CONDITION_LOCK)
      {
        release_lock(reinterpret_cast<LockState*>(st->lock_state));
      }
      else
      {
        release_rlock(reinterpret_cast<RLockState*>(st->lock_state));
      }
      delete st;
    }
  }

  static void validate_blocking_timeout(PyBool blocking, PyFloat64 timeout)
  {
    if (!blocking && timeout >= 0.0)
    {
      throw PY2CPP_TYPE(PyValueError)();
    }
    if (timeout < -1.0)
    {
      throw PY2CPP_TYPE(PyValueError)();
    }
  }

  static double timeout_deadline(PyFloat64 timeout)
  {
    return (double)py2cpp::system::time::monotonic() + (double)timeout;
  }

  static PyBool lock_locked_state(LockState* st)
  {
    if (!st)
    {
      return false;
    }
    std::lock_guard<std::mutex> lk(st->mutex);
    return st->locked;
  }

  static PyBool acquire_lock_state(LockState* st, PyBool blocking, PyFloat64 timeout)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    validate_blocking_timeout(blocking, timeout);
    std::unique_lock<std::mutex> lk(st->mutex);
    if (!st->locked)
    {
      st->locked = true;
      return true;
    }
    if (!blocking)
    {
      return false;
    }
    double end = 0.0;
    if (timeout >= 0.0)
    {
      end = timeout_deadline(timeout);
    }
    while (st->locked)
    {
      if (timeout < 0.0)
      {
        st->cv.wait(lk);
      }
      else
      {
        double now = (double)py2cpp::system::time::monotonic();
        double remaining = end - now;
        if (remaining <= 0.0)
        {
          return false;
        }
        timed_wait_cv(st->cv, lk, remaining);
      }
    }
    st->locked = true;
    return true;
  }

  static void release_lock_state(LockState* st)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    {
      std::lock_guard<std::mutex> lk(st->mutex);
      if (!st->locked)
      {
        throw PY2CPP_TYPE(PyRuntimeError)();
      }
      st->locked = false;
    }
    st->cv.notify_one();
  }

  static PyBool rlock_locked_state(RLockState* st)
  {
    if (!st)
    {
      return false;
    }
    std::lock_guard<std::mutex> lk(st->mutex);
    return st->owner != 0 && st->recursion > 0;
  }

  static PyBool rlock_is_owned_state(RLockState* st)
  {
    if (!st)
    {
      return false;
    }
    PyInt64 me = ensure_ident();
    std::lock_guard<std::mutex> lk(st->mutex);
    return st->owner == me && st->recursion > 0;
  }

  static PyBool acquire_rlock_state(RLockState* st, PyBool blocking, PyFloat64 timeout)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    validate_blocking_timeout(blocking, timeout);
    PyInt64 me = ensure_ident();
    std::unique_lock<std::mutex> lk(st->mutex);
    if (st->owner == me)
    {
      st->recursion += 1;
      return true;
    }
    if (st->owner == 0)
    {
      st->owner = me;
      st->recursion = 1;
      return true;
    }
    if (!blocking)
    {
      return false;
    }
    double end = 0.0;
    if (timeout >= 0.0)
    {
      end = timeout_deadline(timeout);
    }
    while (st->owner != 0)
    {
      if (timeout < 0.0)
      {
        st->cv.wait(lk);
      }
      else
      {
        double now = (double)py2cpp::system::time::monotonic();
        double remaining = end - now;
        if (remaining <= 0.0)
        {
          return false;
        }
        timed_wait_cv(st->cv, lk, remaining);
      }
    }
    st->owner = me;
    st->recursion = 1;
    return true;
  }

  static void release_rlock_state(RLockState* st)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    bool notify = false;
    PyInt64 me = ensure_ident();
    {
      std::lock_guard<std::mutex> lk(st->mutex);
      if (st->owner != me || st->recursion <= 0)
      {
        throw PY2CPP_TYPE(PyRuntimeError)();
      }
      st->recursion -= 1;
      if (st->recursion == 0)
      {
        st->owner = 0;
        notify = true;
      }
    }
    if (notify)
    {
      st->cv.notify_one();
    }
  }

  static PyInt rlock_release_save_state(RLockState* st)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    PyInt64 me = ensure_ident();
    PyInt count = 0;
    {
      std::lock_guard<std::mutex> lk(st->mutex);
      if (st->owner != me || st->recursion <= 0)
      {
        throw PY2CPP_TYPE(PyRuntimeError)();
      }
      count = st->recursion;
      st->recursion = 0;
      st->owner = 0;
    }
    st->cv.notify_one();
    return count;
  }

  static void rlock_acquire_restore_state(RLockState* st, PyInt count)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (count <= 0)
    {
      throw PY2CPP_TYPE(PyValueError)();
    }
    PyInt64 me = ensure_ident();
    std::unique_lock<std::mutex> lk(st->mutex);
    while (st->owner != 0 && st->owner != me)
    {
      st->cv.wait(lk);
    }
    st->owner = me;
    st->recursion += count;
  }

  static PyBool condition_locked_state(ConditionState* st)
  {
    if (!st)
    {
      return false;
    }
    if (st->lock_kind == CONDITION_LOCK)
    {
      return lock_locked_state(reinterpret_cast<LockState*>(st->lock_state));
    }
    return rlock_locked_state(reinterpret_cast<RLockState*>(st->lock_state));
  }

  static PyBool condition_is_owned_state(ConditionState* st)
  {
    if (!st)
    {
      return false;
    }
    if (st->lock_kind == CONDITION_LOCK)
    {
      return lock_locked_state(reinterpret_cast<LockState*>(st->lock_state));
    }
    return rlock_is_owned_state(reinterpret_cast<RLockState*>(st->lock_state));
  }

  static PyBool condition_acquire_state(ConditionState* st, PyBool blocking, PyFloat64 timeout)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (st->lock_kind == CONDITION_LOCK)
    {
      return acquire_lock_state(reinterpret_cast<LockState*>(st->lock_state), blocking, timeout);
    }
    return acquire_rlock_state(reinterpret_cast<RLockState*>(st->lock_state), blocking, timeout);
  }

  static void condition_release_state(ConditionState* st)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (st->lock_kind == CONDITION_LOCK)
    {
      release_lock_state(reinterpret_cast<LockState*>(st->lock_state));
    }
    else
    {
      release_rlock_state(reinterpret_cast<RLockState*>(st->lock_state));
    }
  }

  static PyInt condition_release_save_state(ConditionState* st)
  {
    if (st->lock_kind == CONDITION_LOCK)
    {
      release_lock_state(reinterpret_cast<LockState*>(st->lock_state));
      return 1;
    }
    return rlock_release_save_state(reinterpret_cast<RLockState*>(st->lock_state));
  }

  static void condition_acquire_restore_state(ConditionState* st, PyInt count)
  {
    if (st->lock_kind == CONDITION_LOCK)
    {
      acquire_lock_state(reinterpret_cast<LockState*>(st->lock_state), true, -1.0);
    }
    else
    {
      rlock_acquire_restore_state(reinterpret_cast<RLockState*>(st->lock_state), count);
    }
  }

  static PyBool condition_wait_state(ConditionState* st, PyFloat64 timeout)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (timeout < -1.0)
    {
      throw PY2CPP_TYPE(PyValueError)();
    }
    if (!condition_is_owned_state(st))
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    double end = 0.0;
    if (timeout >= 0.0)
    {
      end = timeout_deadline(timeout);
    }
    std::unique_lock<std::mutex> lk(st->mutex);
    if (st->closing)
    {
      return false;
    }
    st->waiters += 1;
    PyInt saved = 0;
    bool released = false;
    try
    {
      saved = condition_release_save_state(st);
      released = true;
      PyBool ok = true;
      if (timeout < 0.0)
      {
        st->cv.wait(lk);
      }
      else
      {
        double now = (double)py2cpp::system::time::monotonic();
        double remaining = end - now;
        if (remaining <= 0.0)
        {
          ok = false;
        }
        else
        {
          ok = timed_wait_cv(st->cv, lk, remaining);
        }
      }
      PyBool closing = st->closing;
      lk.unlock();
      condition_acquire_restore_state(st, saved);
      lk.lock();
      st->waiters -= 1;
      if (closing)
      {
        st->cv.notify_all();
      }
      return ok && !closing;
    }
    catch (...)
    {
      if (released)
      {
        if (lk.owns_lock())
        {
          lk.unlock();
        }
        condition_acquire_restore_state(st, saved);
        lk.lock();
      }
      if (lk.owns_lock())
      {
        if (st->waiters > 0)
        {
          st->waiters -= 1;
        }
        if (st->closing)
        {
          st->cv.notify_all();
        }
        lk.unlock();
      }
      throw;
    }
  }

  static void condition_notify_state(ConditionState* st, PyInt n)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (!condition_is_owned_state(st))
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (n <= 0)
    {
      return;
    }
    PyInt count = 0;
    {
      std::lock_guard<std::mutex> lk(st->mutex);
      PyInt available = st->waiters;
      if (available <= 0)
      {
        return;
      }
      count = n < available ? n : available;
    }
    for (PyInt i = 0; i < count; ++i)
    {
      st->cv.notify_one();
    }
  }

  static void condition_notify_all_state(ConditionState* st)
  {
    if (!st)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (!condition_is_owned_state(st))
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    PyInt count = 0;
    {
      std::lock_guard<std::mutex> lk(st->mutex);
      PyInt available = st->waiters;
      if (available <= 0)
      {
        return;
      }
      count = available;
    }
    st->cv.notify_all();
  }

  template<typename T>
  static void retain_atomic(AtomicState<T>* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  template<typename T>
  static void release_atomic(AtomicState<T>* st)
  {
    if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      delete st;
    }
  }

  template<typename T>
  static void retain_queue(QueueState<T>* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  template<typename T>
  static void release_queue(QueueState<T>* st)
  {
    if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      delete st;
    }
  }

  static void retain_thread(ThreadState* st)
  {
    if (st)
    {
      st->refs.fetch_add(1, std::memory_order_relaxed);
    }
  }

  static void release_thread(ThreadState* st)
  {
    if (st && st->refs.fetch_sub(1, std::memory_order_acq_rel) == 1)
    {
      delete st;
    }
  }
}

namespace py2cpp {
namespace concur {
namespace thread {

void _barrierNoAction()
{
}

template<typename _Value>
PyAtomic<_Value>::PyAtomic()
{
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::AtomicState<_Value>(_Value()));
}

template<typename _Value>
PyAtomic<_Value>::PyAtomic(_Value value)
{
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::AtomicState<_Value>(value));
}

template<typename _Value>
PyAtomic<_Value>::~PyAtomic()
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  py2cpp_concur_thread_detail::release_atomic(st);
  _state = 0;
}

template<typename _Value>
void PyAtomic<_Value>::__copy__(const PyAtomic<_Value>& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_thread_detail::AtomicState<_Value>* next =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(other._state);
  py2cpp_concur_thread_detail::retain_atomic(next);
  py2cpp_concur_thread_detail::AtomicState<_Value>* old =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  py2cpp_concur_thread_detail::release_atomic(old);
  _state = other._state;
}

template<typename _Value>
_Value PyAtomic<_Value>::load() const
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  return st->value.load(std::memory_order_seq_cst);
}

template<typename _Value>
void PyAtomic<_Value>::store(_Value value)
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  st->value.store(value, std::memory_order_seq_cst);
}

template<typename _Value>
_Value PyAtomic<_Value>::exchange(_Value value)
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  return st->value.exchange(value, std::memory_order_seq_cst);
}

template<typename _Value>
PyBool PyAtomic<_Value>::compareExchange(_Value expected, _Value desired)
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  return st->value.compare_exchange_strong(
    expected, desired, std::memory_order_seq_cst, std::memory_order_seq_cst);
}

template<typename _Value>
_Value PyAtomic<_Value>::fetchAdd(_Value delta)
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  return st->value.fetch_add(delta, std::memory_order_seq_cst);
}

template<typename _Value>
_Value PyAtomic<_Value>::fetchSub(_Value delta)
{
  py2cpp_concur_thread_detail::AtomicState<_Value>* st =
    py2cpp_concur_thread_detail::atomic_from_handle<_Value>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  return st->value.fetch_sub(delta, std::memory_order_seq_cst);
}

PyLock::PyLock()
{
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::LockState());
}

PyLock::~PyLock()
{
  py2cpp_concur_thread_detail::LockState* st =
    py2cpp_concur_thread_detail::lock_from_handle(_state);
  py2cpp_concur_thread_detail::release_lock(st);
  _state = 0;
}

void PyLock::__copy__(const PyLock& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_thread_detail::LockState* next =
    py2cpp_concur_thread_detail::lock_from_handle(other._state);
  py2cpp_concur_thread_detail::retain_lock(next);
  py2cpp_concur_thread_detail::LockState* old =
    py2cpp_concur_thread_detail::lock_from_handle(_state);
  py2cpp_concur_thread_detail::release_lock(old);
  _state = other._state;
}

PyBool PyLock::acquire(PyBool blocking, PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::LockState* st =
    py2cpp_concur_thread_detail::lock_from_handle(_state);
  return py2cpp_concur_thread_detail::acquire_lock_state(st, blocking, timeout);
}

void PyLock::release()
{
  py2cpp_concur_thread_detail::LockState* st =
    py2cpp_concur_thread_detail::lock_from_handle(_state);
  py2cpp_concur_thread_detail::release_lock_state(st);
}

PyBool PyLock::locked() const
{
  py2cpp_concur_thread_detail::LockState* st =
    py2cpp_concur_thread_detail::lock_from_handle(_state);
  return py2cpp_concur_thread_detail::lock_locked_state(st);
}

PyLock& PyLock::__enter__()
{
  acquire(true, -1.0);
  return *this;
}

void PyLock::__exit__()
{
  release();
}

PyRLock::PyRLock()
{
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::RLockState());
}

PyRLock::~PyRLock()
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  py2cpp_concur_thread_detail::release_rlock(st);
  _state = 0;
}

void PyRLock::__copy__(const PyRLock& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_thread_detail::RLockState* next =
    py2cpp_concur_thread_detail::rlock_from_handle(other._state);
  py2cpp_concur_thread_detail::retain_rlock(next);
  py2cpp_concur_thread_detail::RLockState* old =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  py2cpp_concur_thread_detail::release_rlock(old);
  _state = other._state;
}

PyBool PyRLock::acquire(PyBool blocking, PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  return py2cpp_concur_thread_detail::acquire_rlock_state(st, blocking, timeout);
}

void PyRLock::release()
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  py2cpp_concur_thread_detail::release_rlock_state(st);
}

PyBool PyRLock::locked() const
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  return py2cpp_concur_thread_detail::rlock_locked_state(st);
}

PyBool PyRLock::_isOwned() const
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  return py2cpp_concur_thread_detail::rlock_is_owned_state(st);
}

PyInt PyRLock::_releaseSave()
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  return py2cpp_concur_thread_detail::rlock_release_save_state(st);
}

void PyRLock::_acquireRestore(PyInt count)
{
  py2cpp_concur_thread_detail::RLockState* st =
    py2cpp_concur_thread_detail::rlock_from_handle(_state);
  py2cpp_concur_thread_detail::rlock_acquire_restore_state(st, count);
}

PyRLock& PyRLock::__enter__()
{
  acquire(true, -1.0);
  return *this;
}

void PyRLock::__exit__()
{
  release();
}

PyCondition::PyCondition()
{
  py2cpp_concur_thread_detail::RLockState* lock =
    new py2cpp_concur_thread_detail::RLockState();
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::ConditionState(
    py2cpp_concur_thread_detail::CONDITION_RLOCK, lock));
}

PyCondition::PyCondition(PyLock lock)
{
  py2cpp_concur_thread_detail::LockState* lock_state =
    py2cpp_concur_thread_detail::lock_from_handle(lock._state);
  py2cpp_concur_thread_detail::retain_lock(lock_state);
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::ConditionState(
    py2cpp_concur_thread_detail::CONDITION_LOCK, lock_state));
}

PyCondition::PyCondition(PyRLock lock)
{
  py2cpp_concur_thread_detail::RLockState* lock_state =
    py2cpp_concur_thread_detail::rlock_from_handle(lock._state);
  py2cpp_concur_thread_detail::retain_rlock(lock_state);
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::ConditionState(
    py2cpp_concur_thread_detail::CONDITION_RLOCK, lock_state));
}

PyCondition::~PyCondition()
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  py2cpp_concur_thread_detail::release_condition(st);
  _state = 0;
}

void PyCondition::__copy__(const PyCondition& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_thread_detail::ConditionState* next =
    py2cpp_concur_thread_detail::condition_from_handle(other._state);
  py2cpp_concur_thread_detail::retain_condition(next);
  py2cpp_concur_thread_detail::ConditionState* old =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  py2cpp_concur_thread_detail::release_condition(old);
  _state = other._state;
}

PyBool PyCondition::acquire(PyBool blocking, PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  return py2cpp_concur_thread_detail::condition_acquire_state(st, blocking, timeout);
}

void PyCondition::release()
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  py2cpp_concur_thread_detail::condition_release_state(st);
}

PyBool PyCondition::locked() const
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  return py2cpp_concur_thread_detail::condition_locked_state(st);
}

PyBool PyCondition::_isOwned() const
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  return py2cpp_concur_thread_detail::condition_is_owned_state(st);
}

PyBool PyCondition::wait(PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  return py2cpp_concur_thread_detail::condition_wait_state(st, timeout);
}

PyBool PyCondition::waitFor(PyCallable<PyBool> predicate, PyFloat64 timeout)
{
  if (!_isOwned())
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  if (predicate())
  {
    return true;
  }
  if (timeout < -1.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
  double end = 0.0;
  if (timeout >= 0.0)
  {
    end = py2cpp_concur_thread_detail::timeout_deadline(timeout);
  }
  while (true)
  {
    PyFloat64 wait_time = -1.0;
    if (timeout >= 0.0)
    {
      double now = (double)py2cpp::system::time::monotonic();
      double remaining = end - now;
      if (remaining <= 0.0)
      {
        return predicate();
      }
      wait_time = (PyFloat64)remaining;
    }
    if (!wait(wait_time))
    {
      return predicate();
    }
    if (predicate())
    {
      return true;
    }
  }
}

void PyCondition::notify(PyInt n)
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  py2cpp_concur_thread_detail::condition_notify_state(st, n);
}

void PyCondition::notifyAll()
{
  py2cpp_concur_thread_detail::ConditionState* st =
    py2cpp_concur_thread_detail::condition_from_handle(_state);
  py2cpp_concur_thread_detail::condition_notify_all_state(st);
}

PyCondition& PyCondition::__enter__()
{
  acquire(true, -1.0);
  return *this;
}

void PyCondition::__exit__()
{
  release();
}

template<typename _Element>
PyQueue<_Element>::PyQueue(PyInt maxsize)
{
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::QueueState<_Element>(maxsize));
}

template<typename _Element>
PyQueue<_Element>::~PyQueue()
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  py2cpp_concur_thread_detail::release_queue(st);
  _state = 0;
}

template<typename _Element>
void PyQueue<_Element>::__copy__(const PyQueue<_Element>& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_thread_detail::QueueState<_Element>* next =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(other._state);
  py2cpp_concur_thread_detail::retain_queue(next);
  py2cpp_concur_thread_detail::QueueState<_Element>* old =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  py2cpp_concur_thread_detail::release_queue(old);
  _state = other._state;
}

template<typename _Element>
PyInt PyQueue<_Element>::__len__() const
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    return 0;
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->items.__len__();
}

template<typename _Element>
PyBool PyQueue<_Element>::__bool__() const
{
  return __len__() > 0;
}

template<typename _Element>
PyBool PyQueue<_Element>::full() const
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    return false;
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->maxsize > 0 && st->items.__len__() >= st->maxsize;
}

template<typename _Element>
void PyQueue<_Element>::put(_Element item, PyBool block, PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  if (!block && timeout >= 0.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
  if (timeout < -1.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
  std::unique_lock<std::mutex> lk(st->mutex);
  if (st->shutdown)
  {
    throw PyShutDownError();
  }
  double end = 0.0;
  if (timeout >= 0.0)
  {
    end = (double)py2cpp::system::time::monotonic() + (double)timeout;
  }
  while (st->maxsize > 0 && st->items.__len__() >= st->maxsize)
  {
    if (st->shutdown)
    {
      throw PyShutDownError();
    }
    if (!block)
    {
      throw PyFullError();
    }
    if (timeout < 0.0)
    {
      st->not_full.wait(lk);
    }
    else
    {
      double now = (double)py2cpp::system::time::monotonic();
      double remaining = end - now;
      if (remaining <= 0.0)
      {
        throw PyFullError();
      }
      py2cpp_concur_thread_detail::timed_wait_cv(st->not_full, lk, remaining);
    }
  }
  if (st->shutdown)
  {
    throw PyShutDownError();
  }
  st->items.append(item);
  st->unfinished_tasks += 1;
  lk.unlock();
  st->not_empty.notify_one();
}

template<typename _Element>
void PyQueue<_Element>::putNoWait(_Element item)
{
  put(item, false, -1.0);
}

template<typename _Element>
_Element PyQueue<_Element>::get(PyBool block, PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  if (!block && timeout >= 0.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
  if (timeout < -1.0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
  std::unique_lock<std::mutex> lk(st->mutex);
  double end = 0.0;
  if (timeout >= 0.0)
  {
    end = (double)py2cpp::system::time::monotonic() + (double)timeout;
  }
  while (st->items.__len__() == 0)
  {
    if (st->shutdown)
    {
      throw PyShutDownError();
    }
    if (!block)
    {
      throw PyEmptyError();
    }
    if (timeout < 0.0)
    {
      st->not_empty.wait(lk);
    }
    else
    {
      double now = (double)py2cpp::system::time::monotonic();
      double remaining = end - now;
      if (remaining <= 0.0)
      {
        throw PyEmptyError();
      }
      py2cpp_concur_thread_detail::timed_wait_cv(st->not_empty, lk, remaining);
    }
  }
  if (st->immediate)
  {
    throw PyShutDownError();
  }
  _Element item = st->items.popLeft();
  lk.unlock();
  st->not_full.notify_one();
  return item;
}

template<typename _Element>
_Element PyQueue<_Element>::getNoWait()
{
  return get(false, -1.0);
}

template<typename _Element>
void PyQueue<_Element>::taskDone()
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  if (st->unfinished_tasks <= 0)
  {
    throw PY2CPP_TYPE(PyValueError)();
  }
  st->unfinished_tasks -= 1;
  if (st->unfinished_tasks == 0)
  {
    st->all_tasks_done.notify_all();
  }
}

template<typename _Element>
void PyQueue<_Element>::join()
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  std::unique_lock<std::mutex> lk(st->mutex);
  while (st->unfinished_tasks > 0 && !st->immediate)
  {
    st->all_tasks_done.wait(lk);
  }
}

template<typename _Element>
void PyQueue<_Element>::shutdown(PyBool immediate)
{
  py2cpp_concur_thread_detail::QueueState<_Element>* st =
    py2cpp_concur_thread_detail::queue_from_handle<_Element>(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  {
    std::lock_guard<std::mutex> lk(st->mutex);
    st->shutdown = true;
    if (immediate)
    {
      st->immediate = true;
      st->items.clear();
      st->unfinished_tasks = 0;
    }
  }
  st->not_empty.notify_all();
  st->not_full.notify_all();
  st->all_tasks_done.notify_all();
}

_PyThreadHandle::_PyThreadHandle()
{
  _state = (PyUPtr)(uintptr_t)(new py2cpp_concur_thread_detail::ThreadState());
}

_PyThreadHandle::~_PyThreadHandle()
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  py2cpp_concur_thread_detail::release_thread(st);
  _state = 0;
}

void _PyThreadHandle::__copy__(const _PyThreadHandle& other)
{
  if (_state == other._state)
  {
    return;
  }
  py2cpp_concur_thread_detail::ThreadState* next =
    py2cpp_concur_thread_detail::thread_from_handle(other._state);
  py2cpp_concur_thread_detail::retain_thread(next);
  py2cpp_concur_thread_detail::ThreadState* old =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  py2cpp_concur_thread_detail::release_thread(old);
  _state = other._state;
}

_PyThreadHandle _PyThreadHandle::PY2CPP_GETTER(current)()
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::current_thread_state();
  _PyThreadHandle handle;
  py2cpp_concur_thread_detail::ThreadState* old =
    py2cpp_concur_thread_detail::thread_from_handle(handle._state);
  py2cpp_concur_thread_detail::release_thread(old);
  py2cpp_concur_thread_detail::retain_thread(st);
  handle._state = (PyUPtr)(uintptr_t)st;
  return handle;
}

_PyThreadHandle _PyThreadHandle::PY2CPP_GETTER(main)()
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::ensure_main_thread_registered();
  _PyThreadHandle handle;
  py2cpp_concur_thread_detail::ThreadState* old =
    py2cpp_concur_thread_detail::thread_from_handle(handle._state);
  py2cpp_concur_thread_detail::release_thread(old);
  py2cpp_concur_thread_detail::retain_thread(st);
  handle._state = (PyUPtr)(uintptr_t)st;
  return handle;
}

PyInt _PyThreadHandle::PY2CPP_GETTER(activeCount)()
{
  py2cpp_concur_thread_detail::ensure_main_thread_registered();
  PyInt count = 0;
  std::lock_guard<std::mutex> lk(py2cpp_concur_thread_detail::registry_mutex);
  py2cpp_concur_thread_detail::ThreadState* cur =
    py2cpp_concur_thread_detail::registry_head;
  while (cur)
  {
    count += 1;
    cur = cur->registry_next;
  }
  return count;
}

PY2CPP_TYPE(PyList)<_PyThreadHandle> _PyThreadHandle::PY2CPP_GETTER(actives)()
{
  py2cpp_concur_thread_detail::ensure_main_thread_registered();
  PY2CPP_TYPE(PyList)<_PyThreadHandle> out;
  std::lock_guard<std::mutex> lk(py2cpp_concur_thread_detail::registry_mutex);
  py2cpp_concur_thread_detail::ThreadState* cur =
    py2cpp_concur_thread_detail::registry_head;
  while (cur)
  {
    _PyThreadHandle handle;
    py2cpp_concur_thread_detail::ThreadState* old =
      py2cpp_concur_thread_detail::thread_from_handle(handle._state);
    py2cpp_concur_thread_detail::release_thread(old);
    py2cpp_concur_thread_detail::retain_thread(cur);
    handle._state = (PyUPtr)(uintptr_t)cur;
    out.append(handle);
    cur = cur->registry_next;
  }
  return out;
}

void _PyThreadHandle::start(
  py2cpp_concur_thread_detail::ThreadTarget target,
  PY2CPP_TYPE(PyStr) name,
  PyBool daemon)
{
  py2cpp_concur_thread_detail::ensure_main_thread_registered();
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  {
    std::lock_guard<std::mutex> lk(st->mutex);
    if (st->started)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    st->target = target;
    st->name = name;
    st->daemon = daemon;
    st->started = true;
    st->running = true;
  }
  py2cpp_concur_thread_detail::retain_thread(st);
  try
  {
    st->worker = std::thread([st]() {
      py2cpp_concur_thread_detail::tls_thread_state = st;
      PyInt64 ident = py2cpp_concur_thread_detail::ensure_ident();
      PyInt64 nativeId = py2cpp_concur_thread_detail::current_native_id();
      {
        std::lock_guard<std::mutex> lk(st->mutex);
        st->ident = ident;
        st->nativeId = nativeId;
      }
      py2cpp_concur_thread_detail::register_active_thread(st);
      st->cv.notify_all();
      try
      {
        st->target();
      }
      catch (...)
      {
        // 首版不跨线程保存异常；确保异常不逃逸到 std::thread entry。
      }
      {
        std::lock_guard<std::mutex> lk(st->mutex);
        st->running = false;
        st->finished = true;
        st->target = py2cpp_concur_thread_detail::ThreadTarget();
      }
      st->cv.notify_all();
      py2cpp_concur_thread_detail::unregister_active_thread(st);
      py2cpp_concur_thread_detail::tls_thread_state = NULL;
      py2cpp_concur_thread_detail::release_thread(st);
    });
  }
  catch (...)
  {
    std::lock_guard<std::mutex> lk(st->mutex);
    st->started = false;
    st->running = false;
    st->finished = false;
    st->target = py2cpp_concur_thread_detail::ThreadTarget();
    py2cpp_concur_thread_detail::release_thread(st);
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  std::unique_lock<std::mutex> lk(st->mutex);
  while (st->ident == 0 && st->running)
  {
    st->cv.wait(lk);
  }
}

PyBool _PyThreadHandle::join(PyFloat64 timeout)
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    throw PY2CPP_TYPE(PyRuntimeError)();
  }
  bool should_join = false;
  {
    std::unique_lock<std::mutex> lk(st->mutex);
    if (!st->started)
    {
      throw PY2CPP_TYPE(PyRuntimeError)();
    }
    if (!st->finished)
    {
      double end = 0.0;
      if (timeout >= 0.0)
      {
        end = (double)py2cpp::system::time::monotonic() + (double)timeout;
      }
      while (!st->finished)
      {
        if (timeout < 0.0)
        {
          st->cv.wait(lk);
        }
        else
        {
          double now = (double)py2cpp::system::time::monotonic();
          double remaining = end - now;
          if (remaining <= 0.0)
          {
            return false;
          }
          py2cpp_concur_thread_detail::timed_wait_cv(st->cv, lk, remaining);
        }
      }
    }
    if (!st->joined)
    {
      st->joined = true;
      should_join = true;
    }
  }
  if (should_join && st->worker.joinable())
  {
    st->worker.join();
  }
  return true;
}

PyBool _PyThreadHandle::PY2CPP_GETTER(alive)() const
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    return false;
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->running && !st->finished;
}

PyInt64 _PyThreadHandle::PY2CPP_GETTER(ident)() const
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    return 0;
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->ident;
}

PyInt64 _PyThreadHandle::PY2CPP_GETTER(nativeId)() const
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    return 0;
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->nativeId;
}

PY2CPP_TYPE(PyStr) _PyThreadHandle::PY2CPP_GETTER(name)() const
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    return PY2CPP_TYPE(PyStr)("");
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->name;
}

PyBool _PyThreadHandle::PY2CPP_GETTER(daemon)() const
{
  py2cpp_concur_thread_detail::ThreadState* st =
    py2cpp_concur_thread_detail::thread_from_handle(_state);
  if (!st)
  {
    return false;
  }
  std::lock_guard<std::mutex> lk(st->mutex);
  return st->daemon;
}

} // namespace thread
} // namespace concur
} // namespace py2cpp
