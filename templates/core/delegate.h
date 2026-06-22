#include "py2cpp/util/list.h"


// 可绑定槽位：ctx + invoke(ctx, args...)；用于委托 += 与 Callable[[...], R] 注解。
template<typename Ret, typename... Args>
struct PyCallable
{
  void* ctx;
  Ret (*invoke)(void* ctx, Args... args);

  explicit PyCallable() : ctx(nullptr), invoke(nullptr)
  {
  }

  explicit PyCallable(void* c, Ret (*fn)(void* ctx, Args... args)) : ctx(c), invoke(fn)
  {
  }

  Ret __call__(Args... args) const
  {
    return invoke(ctx, args...);
  }

  Ret operator()(Args... args) const
  {
    return __call__(args...);
  }

  bool operator==(const PyCallable& o) const
  {
    return ctx == o.ctx && invoke == o.invoke;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

template<typename Ret>
struct PyCallable<Ret>
{
  void* ctx;
  Ret (*invoke)(void* ctx);

  explicit PyCallable() : ctx(nullptr), invoke(nullptr)
  {
  }

  explicit PyCallable(void* c, Ret (*fn)(void* ctx)) : ctx(c), invoke(fn)
  {
  }

  Ret __call__() const
  {
    return invoke(ctx);
  }

  Ret operator()() const
  {
    return __call__();
  }

  bool operator==(const PyCallable& o) const
  {
    return ctx == o.ctx && invoke == o.invoke;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

template<>
struct PyCallable<void>
{
  void* ctx;
  void (*invoke)(void* ctx);

  explicit PyCallable() : ctx(nullptr), invoke(nullptr)
  {
  }

  explicit PyCallable(void* c, void (*fn)(void* ctx)) : ctx(c), invoke(fn)
  {
  }

  void __call__() const
  {
    invoke(ctx);
  }

  void operator()() const
  {
    __call__();
  }

  bool operator==(const PyCallable& o) const
  {
    return ctx == o.ctx && invoke == o.invoke;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

template<typename... Args>
struct PyCallable<void, Args...>
{
  void* ctx;
  void (*invoke)(void* ctx, Args... args);

  explicit PyCallable() : ctx(nullptr), invoke(nullptr)
  {
  }

  explicit PyCallable(void* c, void (*fn)(void* ctx, Args... args)) : ctx(c), invoke(fn)
  {
  }

  void __call__(Args... args) const
  {
    invoke(ctx, args...);
  }

  void operator()(Args... args) const
  {
    __call__(args...);
  }

  bool operator==(const PyCallable& o) const
  {
    return ctx == o.ctx && invoke == o.invoke;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

// 自由函数槽位：ctx 存 ``Ret (*)(Args...)``，invoke 解引用调用。
template<typename Ret, typename... Args>
struct py_callable_free_invoke
{
  static Ret call(void* ctx, Args... args)
  {
    typedef Ret (*Fn)(Args...);
    return reinterpret_cast<Fn>(ctx)(args...);
  }
};

template<typename Ret>
struct py_callable_free_invoke<Ret>
{
  static Ret call(void* ctx)
  {
    typedef Ret (*Fn)();
    return reinterpret_cast<Fn>(ctx)();
  }
};

template<typename... Args>
struct py_callable_free_invoke<void, Args...>
{
  static void call(void* ctx, Args... args)
  {
    typedef void (*Fn)(Args...);
    reinterpret_cast<Fn>(ctx)(args...);
  }
};

template<>
struct py_callable_free_invoke<void>
{
  static void call(void* ctx)
  {
    typedef void (*Fn)();
    reinterpret_cast<Fn>(ctx)();
  }
};

// C++ lambda 闭包对象：ctx 指向 ``operator()`` 可调的匿名类实例。
template<typename Lam, typename Ret, typename... Args>
struct py_callable_lambda_invoke
{
  static Ret call(void* ctx, Args... args)
  {
    return (*static_cast<Lam*>(ctx))(args...);
  }
};

template<typename Lam, typename Ret>
struct py_callable_lambda_invoke<Lam, Ret>
{
  static Ret call(void* ctx)
  {
    return (*static_cast<Lam*>(ctx))();
  }
};

template<typename Lam, typename... Args>
struct py_callable_lambda_invoke<Lam, void, Args...>
{
  static void call(void* ctx, Args... args)
  {
    (*static_cast<Lam*>(ctx))(args...);
  }
};

template<typename Lam>
struct py_callable_lambda_invoke<Lam, void>
{
  static void call(void* ctx)
  {
    (*static_cast<Lam*>(ctx))();
  }
};

// 多播委托：Handler = PyCallable<Ret, Args...>；+= / -= / bool 在此实现。
template<typename Ret, typename... Args>
class PyDelegate
{
public:
  typedef PyCallable<Ret, Args...> Handler;

  explicit PyDelegate() : _handlers()
  {
  }

  PyDelegate& operator+=(const Handler& h)
  {
    _handlers.append(h);
    return *this;
  }

  PyDelegate& operator-=(const Handler& h)
  {
    _handlers.remove(h);
    return *this;
  }

  explicit operator bool() const
  {
    return _handlers.__len__() > 0;
  }

protected:
  Ret _invoke(Args... args) const
  {
    Ret __result{};
    int __n = _handlers.__len__();
    for (int __i = 0; __i < __n; ++__i)
    {
      const Handler& __h = _handlers.__getitem__(__i);
      __result = __h(args...);
    }
    return __result;
  }

private:
  PY2CPP_TYPE(PyList)<Handler> _handlers;
};

template<typename Ret>
class PyDelegate<Ret>
{
public:
  typedef PyCallable<Ret> Handler;

  explicit PyDelegate() : _handlers()
  {
  }

  PyDelegate& operator+=(const Handler& h)
  {
    _handlers.append(h);
    return *this;
  }

  PyDelegate& operator-=(const Handler& h)
  {
    _handlers.remove(h);
    return *this;
  }

  explicit operator bool() const
  {
    return _handlers.__len__() > 0;
  }

protected:
  Ret _invoke() const
  {
    Ret __result{};
    int __n = _handlers.__len__();
    for (int __i = 0; __i < __n; ++__i)
    {
      const Handler& __h = _handlers.__getitem__(__i);
      __result = __h();
    }
    return __result;
  }

private:
  PY2CPP_TYPE(PyList)<Handler> _handlers;
};

template<>
class PyDelegate<void>
{
public:
  typedef PyCallable<void> Handler;

  explicit PyDelegate() : _handlers()
  {
  }

  PyDelegate& operator+=(const Handler& h)
  {
    _handlers.append(h);
    return *this;
  }

  PyDelegate& operator-=(const Handler& h)
  {
    _handlers.remove(h);
    return *this;
  }

  explicit operator bool() const
  {
    return _handlers.__len__() > 0;
  }

protected:
  void _invoke() const
  {
    int __n = _handlers.__len__();
    for (int __i = 0; __i < __n; ++__i)
    {
      const Handler& __h = _handlers.__getitem__(__i);
      __h();
    }
  }

private:
  PY2CPP_TYPE(PyList)<Handler> _handlers;
};

template<typename... Args>
class PyDelegate<void, Args...>
{
public:
  typedef PyCallable<void, Args...> Handler;

  explicit PyDelegate() : _handlers()
  {
  }

  PyDelegate& operator+=(const Handler& h)
  {
    _handlers.append(h);
    return *this;
  }

  PyDelegate& operator-=(const Handler& h)
  {
    _handlers.remove(h);
    return *this;
  }

  explicit operator bool() const
  {
    return _handlers.__len__() > 0;
  }

protected:
  void _invoke(Args... args) const
  {
    int __n = _handlers.__len__();
    for (int __i = 0; __i < __n; ++__i)
    {
      const Handler& __h = _handlers.__getitem__(__i);
      __h(args...);
    }
  }

private:
  PY2CPP_TYPE(PyList)<Handler> _handlers;
};
