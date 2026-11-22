PY2CPP_IGNORE
namespace paw { namespace concur { namespace task {
template<typename _Value>
class PyTask
{
PY2CPP_END

PY2CPP_INJECT_CLASS(PyTask)
public:
  template<typename Coro>
  static PyTask<typename Coro::ReturnType> create(Coro coro);
PY2CPP_END

PY2CPP_IGNORE
};
} } }
PY2CPP_END

/// 薄 emit runtime helpers（runtime 再生成后需随模板保留）。
template<typename T>
struct py2cpp_thin_task_run_traits
{
  template<typename U>
  static auto test_coro(int) -> decltype(
    typename U::ReturnType(),
    typename U::Element(),
    std::declval<U>().__next__(),
    std::true_type());
  template<typename U>
  static std::false_type test_coro(...);
  static const bool is_coro = decltype(test_coro<T>(0))::value;
};

template<typename V>
V py2cpp_thin_task_run(paw::concur::task::PyTask<V> task)
{
  if (paw::concur::task::_sched.haveScheduler)
  {
    while (!task.done__get())
    {
      paw::concur::task::_sched.scheduler.pump();
    }
  }
  return task.result();
}

template<typename T>
typename std::enable_if<!py2cpp_thin_task_run_traits<T>::is_coro, T>::type
py2cpp_thin_task_run(T value)
{
  return value;
}

template<typename Coro>
typename std::enable_if<py2cpp_thin_task_run_traits<Coro>::is_coro, typename Coro::ReturnType>::type
py2cpp_thin_task_run(Coro main)
{
  typedef typename Coro::ReturnType R;
  if (paw::concur::task::_sched.haveScheduler)
  {
    paw::concur::task::PyTask<R> child = paw::concur::task::PyTask<R>::create(main);
    while (!child.done__get())
    {
      paw::concur::task::_sched.scheduler.pump();
    }
    return child.result();
  }
  return paw::concur::task::PyTask<R>::run(main);
}

inline void py2cpp_thin_task_sleep(PyFloat64 /*secs*/ = 0)
{
  if (paw::concur::task::_sched.haveScheduler)
  {
    paw::concur::task::_sched.scheduler.pump();
  }
}

template<typename RT>
struct py2cpp_thunk0_coroutine
{
  typedef paw::concur::task::PyLoopHandle Element;
  typedef PY2CPP_TYPE(PyNone) SendType;
  typedef RT ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<paw::concur::task::PyLoopHandle, RT> Result;

  RT (*fn)();
  bool done;
  RT value;

  explicit py2cpp_thunk0_coroutine(RT (*f)()) : fn(f), done(false), value() {}
  py2cpp_thunk0_coroutine& __iter__() { return *this; }
  Result __next__() { return send(PY2CPP_TYPE(PyNone)()); }
  Result send(PY2CPP_TYPE(PyNone))
  {
    if (!done) { done = true; value = fn(); }
    return Result::Return(value);
  }
};

template<typename RT>
PyCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>
makeThunkCoroutine0(RT (*fn)())
{
  return makeCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>(
    py2cpp_thunk0_coroutine<RT>(fn));
}

template<typename RT, typename A0>
struct py2cpp_thunk1_ref_coroutine
{
  typedef paw::concur::task::PyLoopHandle Element;
  typedef PY2CPP_TYPE(PyNone) SendType;
  typedef RT ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<paw::concur::task::PyLoopHandle, RT> Result;

  RT (*fn)(A0&);
  A0* a0;
  bool done;
  RT value;

  explicit py2cpp_thunk1_ref_coroutine(RT (*f)(A0&), A0& arg) : fn(f), a0(&arg), done(false), value() {}
  py2cpp_thunk1_ref_coroutine& __iter__() { return *this; }
  Result __next__() { return send(PY2CPP_TYPE(PyNone)()); }
  Result send(PY2CPP_TYPE(PyNone))
  {
    if (!done) { done = true; value = fn(*a0); }
    return Result::Return(value);
  }
};

template<typename RT, typename A0>
PyCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>
makeThunkCoroutine1Ref(RT (*fn)(A0&), A0& arg)
{
  return makeCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>(
    py2cpp_thunk1_ref_coroutine<RT, A0>(fn, arg));
}

template<typename RT, typename A0>
struct py2cpp_thunk1_val_coroutine
{
  typedef paw::concur::task::PyLoopHandle Element;
  typedef PY2CPP_TYPE(PyNone) SendType;
  typedef RT ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<paw::concur::task::PyLoopHandle, RT> Result;

  RT (*fn)(A0&);
  A0 a0;
  bool done;
  RT value;

  explicit py2cpp_thunk1_val_coroutine(RT (*f)(A0&), const A0& arg) : fn(f), a0(arg), done(false), value() {}
  py2cpp_thunk1_val_coroutine& __iter__() { return *this; }
  Result __next__() { return send(PY2CPP_TYPE(PyNone)()); }
  Result send(PY2CPP_TYPE(PyNone))
  {
    if (!done) { done = true; value = fn(a0); }
    return Result::Return(value);
  }
};

template<typename RT, typename A0>
PyCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>
makeThunkCoroutine1Val(RT (*fn)(A0&), const A0& arg)
{
  return makeCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>(
    py2cpp_thunk1_val_coroutine<RT, A0>(fn, arg));
}


/// 薄 emit：Task.gather(a, b) → PyTask::gather(PyArray)
template<typename I>
PyList<I, 0> py2cpp_thin_task_gather(PyTask<I> a, PyTask<I> b)
{
  PyArray<PyTask<I>, 0> tasks(2);
  tasks.__setitem__(0, a);
  tasks.__setitem__(1, b);
  return py2cpp_thin_task_run(PyTask<I>::gather(tasks));
}

/// 薄 emit：已求值返回值装箱为 ``PyCoroutine<LoopHandle, None, RT>``。
template<typename RT>
struct py2cpp_value_coroutine
{
  typedef paw::concur::task::PyLoopHandle Element;
  typedef PY2CPP_TYPE(PyNone) SendType;
  typedef RT ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<paw::concur::task::PyLoopHandle, RT> Result;

  RT value;
  bool done;

  explicit py2cpp_value_coroutine(RT v = RT()) : value(v), done(false) {}
  py2cpp_value_coroutine& __iter__() { return *this; }
  Result __next__() { return send(PY2CPP_TYPE(PyNone)()); }
  Result send(PY2CPP_TYPE(PyNone))
  {
    if (!done) { done = true; return Result::Return(value); }
    return Result::Return(value);
  }
};

template<typename RT>
PyCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>
makeValueCoroutine(RT value)
{
  return makeCoroutine<paw::concur::task::PyLoopHandle, PY2CPP_TYPE(PyNone), RT>(
    py2cpp_value_coroutine<RT>(value));
}

