#include <atomic>
#include "py2cpp/util/list.h"

struct PyCallableOwnerBase
{
  std::atomic<int> ref_count;
  void (*destroy)(PyCallableOwnerBase*);

  explicit PyCallableOwnerBase(void (*destroy_fn)(PyCallableOwnerBase*))
    : ref_count(1), destroy(destroy_fn)
  {
  }
};

inline void py_callable_owner_retain(PyCallableOwnerBase* _self)
{
  if (_self)
  {
    _self->ref_count.fetch_add(1, std::memory_order_relaxed);
  }
}

inline void py_callable_owner_release(PyCallableOwnerBase* _self)
{
  if (_self && _self->ref_count.fetch_sub(1, std::memory_order_acq_rel) == 1)
  {
    _self->destroy(_self);
  }
}

template<typename Holder>
struct PyCallableOwnerBox : PyCallableOwnerBase
{
  Holder value;

  explicit PyCallableOwnerBox(const Holder& v)
    : PyCallableOwnerBase(&PyCallableOwnerBox::destroy_box), value(v)
  {
  }

  static void destroy_box(PyCallableOwnerBase* _self)
  {
    PyCallableOwnerBox* self = static_cast<PyCallableOwnerBox*>(_self);
    self->~PyCallableOwnerBox();
    ::operator delete(self);
  }
};

template<typename Holder>
PyCallableOwnerBox<Holder>* py_callable_owner_new_box(const Holder& value)
{
  void* mem = ::operator new(sizeof(PyCallableOwnerBox<Holder>));
  return new (mem) PyCallableOwnerBox<Holder>(value);
}

// 自由函数槽位：_closure 存 ``Ret (*)(Args...)``，_func 解引用调用。
template<typename Ret, typename... Args>
struct py_callable_free_invoke
{
  static Ret call(void* _closure, Args... args)
  {
    typedef Ret (*Fn)(Args...);
    return reinterpret_cast<Fn>(_closure)(args...);
  }
};

template<typename Ret>
struct py_callable_free_invoke<Ret>
{
  static Ret call(void* _closure)
  {
    typedef Ret (*Fn)();
    return reinterpret_cast<Fn>(_closure)();
  }
};

template<typename... Args>
struct py_callable_free_invoke<void, Args...>
{
  static void call(void* _closure, Args... args)
  {
    typedef void (*Fn)(Args...);
    reinterpret_cast<Fn>(_closure)(args...);
  }
};

template<>
struct py_callable_free_invoke<void>
{
  static void call(void* _closure)
  {
    typedef void (*Fn)();
    reinterpret_cast<Fn>(_closure)();
  }
};

// 可绑定槽位：_closure + _func(_closure, args...)；用于委托 += 与 Callable[[...], R] 注解。
template<typename Ret, typename... Args>
struct PyCallable
{
  void* _closure;
  Ret (*_func)(void* _closure, Args... args);
  PyCallableOwnerBase* _self;

  explicit PyCallable() : _closure(nullptr), _func(nullptr), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, Ret (*fn)(void* _closure, Args... args))
    : _closure(c), _func(fn), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, Ret (*fn)(void* _closure, Args... args), PyCallableOwnerBase* o)
    : _closure(c), _func(fn), _self(o)
  {
  }

  PyCallable(Ret (*fn)(Args...))
    : _closure(reinterpret_cast<void*>(fn)),
      _func(&py_callable_free_invoke<Ret, Args...>::call),
      _self(nullptr)
  {
  }

  PyCallable(const PyCallable& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    py_callable_owner_retain(_self);
  }

  PyCallable& operator=(const PyCallable& other)
  {
    if (this != &other)
    {
      py_callable_owner_retain(other._self);
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
    }
    return *this;
  }

  PyCallable(PyCallable&& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    other._closure = nullptr;
    other._func = nullptr;
    other._self = nullptr;
  }

  PyCallable& operator=(PyCallable&& other)
  {
    if (this != &other)
    {
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
      other._closure = nullptr;
      other._func = nullptr;
      other._self = nullptr;
    }
    return *this;
  }

  ~PyCallable()
  {
    py_callable_owner_release(_self);
  }

  Ret __call__(Args... args) const
  {
    return _func(_closure, args...);
  }

  Ret operator()(Args... args) const
  {
    return __call__(args...);
  }

  bool operator==(const PyCallable& o) const
  {
    return _closure == o._closure && _func == o._func;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

template<typename Ret>
struct PyCallable<Ret>
{
  void* _closure;
  Ret (*_func)(void* _closure);
  PyCallableOwnerBase* _self;

  explicit PyCallable() : _closure(nullptr), _func(nullptr), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, Ret (*fn)(void* _closure))
    : _closure(c), _func(fn), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, Ret (*fn)(void* _closure), PyCallableOwnerBase* o)
    : _closure(c), _func(fn), _self(o)
  {
  }

  PyCallable(Ret (*fn)())
    : _closure(reinterpret_cast<void*>(fn)),
      _func(&py_callable_free_invoke<Ret>::call),
      _self(nullptr)
  {
  }

  PyCallable(const PyCallable& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    py_callable_owner_retain(_self);
  }

  PyCallable& operator=(const PyCallable& other)
  {
    if (this != &other)
    {
      py_callable_owner_retain(other._self);
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
    }
    return *this;
  }

  PyCallable(PyCallable&& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    other._closure = nullptr;
    other._func = nullptr;
    other._self = nullptr;
  }

  PyCallable& operator=(PyCallable&& other)
  {
    if (this != &other)
    {
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
      other._closure = nullptr;
      other._func = nullptr;
      other._self = nullptr;
    }
    return *this;
  }

  ~PyCallable()
  {
    py_callable_owner_release(_self);
  }

  Ret __call__() const
  {
    return _func(_closure);
  }

  Ret operator()() const
  {
    return __call__();
  }

  bool operator==(const PyCallable& o) const
  {
    return _closure == o._closure && _func == o._func;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

template<>
struct PyCallable<void>
{
  void* _closure;
  void (*_func)(void* _closure);
  PyCallableOwnerBase* _self;

  explicit PyCallable() : _closure(nullptr), _func(nullptr), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, void (*fn)(void* _closure))
    : _closure(c), _func(fn), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, void (*fn)(void* _closure), PyCallableOwnerBase* o)
    : _closure(c), _func(fn), _self(o)
  {
  }

  PyCallable(void (*fn)())
    : _closure(reinterpret_cast<void*>(fn)),
      _func(&py_callable_free_invoke<void>::call),
      _self(nullptr)
  {
  }

  PyCallable(const PyCallable& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    py_callable_owner_retain(_self);
  }

  PyCallable& operator=(const PyCallable& other)
  {
    if (this != &other)
    {
      py_callable_owner_retain(other._self);
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
    }
    return *this;
  }

  PyCallable(PyCallable&& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    other._closure = nullptr;
    other._func = nullptr;
    other._self = nullptr;
  }

  PyCallable& operator=(PyCallable&& other)
  {
    if (this != &other)
    {
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
      other._closure = nullptr;
      other._func = nullptr;
      other._self = nullptr;
    }
    return *this;
  }

  ~PyCallable()
  {
    py_callable_owner_release(_self);
  }

  void __call__() const
  {
    _func(_closure);
  }

  void operator()() const
  {
    __call__();
  }

  bool operator==(const PyCallable& o) const
  {
    return _closure == o._closure && _func == o._func;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

template<typename... Args>
struct PyCallable<void, Args...>
{
  void* _closure;
  void (*_func)(void* _closure, Args... args);
  PyCallableOwnerBase* _self;

  explicit PyCallable() : _closure(nullptr), _func(nullptr), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, void (*fn)(void* _closure, Args... args))
    : _closure(c), _func(fn), _self(nullptr)
  {
  }

  explicit PyCallable(void* c, void (*fn)(void* _closure, Args... args), PyCallableOwnerBase* o)
    : _closure(c), _func(fn), _self(o)
  {
  }

  PyCallable(void (*fn)(Args...))
    : _closure(reinterpret_cast<void*>(fn)),
      _func(&py_callable_free_invoke<void, Args...>::call),
      _self(nullptr)
  {
  }

  PyCallable(const PyCallable& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    py_callable_owner_retain(_self);
  }

  PyCallable& operator=(const PyCallable& other)
  {
    if (this != &other)
    {
      py_callable_owner_retain(other._self);
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
    }
    return *this;
  }

  PyCallable(PyCallable&& other)
    : _closure(other._closure), _func(other._func), _self(other._self)
  {
    other._closure = nullptr;
    other._func = nullptr;
    other._self = nullptr;
  }

  PyCallable& operator=(PyCallable&& other)
  {
    if (this != &other)
    {
      py_callable_owner_release(_self);
      _closure = other._closure;
      _func = other._func;
      _self = other._self;
      other._closure = nullptr;
      other._func = nullptr;
      other._self = nullptr;
    }
    return *this;
  }

  ~PyCallable()
  {
    py_callable_owner_release(_self);
  }

  void __call__(Args... args) const
  {
    _func(_closure, args...);
  }

  void operator()(Args... args) const
  {
    __call__(args...);
  }

  bool operator==(const PyCallable& o) const
  {
    return _closure == o._closure && _func == o._func;
  }

  bool operator!=(const PyCallable& o) const
  {
    return !(*this == o);
  }
};

// C++ lambda 闭包对象：_closure 指向 ``operator()`` 可调的匿名类实例。
template<typename Lam, typename Ret, typename... Args>
struct py_callable_lambda_invoke
{
  static Ret call(void* _closure, Args... args)
  {
    return (*static_cast<Lam*>(_closure))(args...);
  }
};

template<typename Lam, typename Ret>
struct py_callable_lambda_invoke<Lam, Ret>
{
  static Ret call(void* _closure)
  {
    return (*static_cast<Lam*>(_closure))();
  }
};

template<typename Lam, typename... Args>
struct py_callable_lambda_invoke<Lam, void, Args...>
{
  static void call(void* _closure, Args... args)
  {
    (*static_cast<Lam*>(_closure))(args...);
  }
};

template<typename Lam>
struct py_callable_lambda_invoke<Lam, void>
{
  static void call(void* _closure)
  {
    (*static_cast<Lam*>(_closure))();
  }
};

template<typename Ret, typename Lam, typename... Args>
PyCallable<Ret, Args...> py_callable_make_owned_lambda(const Lam& lam)
{
  PyCallableOwnerBox<Lam>* box = py_callable_owner_new_box(lam);
  return PyCallable<Ret, Args...>(
    (void*)&box->value,
    &py_callable_lambda_invoke<Lam, Ret, Args...>::call,
    box);
}

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
