#include "py2cpp/core/iter_result.h"
#include <utility>


// 擦除协程句柄：``Coroutine[Y,S,R]`` 形参/字段/``@virtual`` 返回；具体 ``*_coroutine`` 经 ``makeCoroutine`` 装箱。
namespace py2cpp_coroutine_detail
{
  template<typename ST>
  ST default_send_value()
  {
    return ST();
  }

  struct model_hdr
  {
    int refcount;

    model_hdr() : refcount(1)
    {
    }

    void add_ref()
    {
      refcount += 1;
    }

    void release()
    {
      refcount -= 1;
      if (refcount <= 0)
      {
        delete this;
      }
    }
  };

  template<typename G>
  struct has_async_iter
  {
    template<typename U>
    static auto test(int) -> decltype(
      std::declval<U>().__aiter__(),
      std::declval<U>().__anext__(),
      std::true_type());
    template<typename U>
    static std::false_type test(...);
    static const bool value = decltype(test<G>(0))::value;
  };

  template<typename YT, typename ST, typename RT, typename G, bool B>
  struct async_bind;
}

template<typename YT, typename ST, typename RT>
class PyCoroutine
{
public:
  typedef YT Element;
  typedef ST SendType;
  typedef RT ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<YT, RT> Result;

  explicit PyCoroutine()
    : _ctx(0), _send_fn(0), _destroy_fn(0), _aiter_fn(0), _anext_fn(0)
  {
  }

  PyCoroutine(const PyCoroutine& other)
    : _ctx(other._ctx),
      _send_fn(other._send_fn),
      _destroy_fn(other._destroy_fn),
      _aiter_fn(other._aiter_fn),
      _anext_fn(other._anext_fn)
  {
    if (_ctx != 0)
    {
      static_cast<py2cpp_coroutine_detail::model_hdr*>(_ctx)->add_ref();
    }
  }

  PyCoroutine& operator=(const PyCoroutine& other)
  {
    if (this != &other)
    {
      reset();
      _ctx = other._ctx;
      _send_fn = other._send_fn;
      _destroy_fn = other._destroy_fn;
      _aiter_fn = other._aiter_fn;
      _anext_fn = other._anext_fn;
      if (_ctx != 0)
      {
        static_cast<py2cpp_coroutine_detail::model_hdr*>(_ctx)->add_ref();
      }
    }
    return *this;
  }

  ~PyCoroutine();

  void reset();
  bool empty() const
  {
    return _ctx == 0;
  }

  PyCoroutine& __iter__()
  {
    return *this;
  }

  Result __next__()
  {
    return send(py2cpp_coroutine_detail::default_send_value<ST>());
  }

  Result send(ST value)
  {
    if (_ctx == 0 || _send_fn == 0)
    {
      return Result::Return(RT());
    }
    return _send_fn(_ctx, value);
  }

  PyCoroutine __await__()
  {
    return *this;
  }

  PyCoroutine __aiter__()
  {
    if (_ctx != 0 && _aiter_fn != 0)
    {
      return _aiter_fn(_ctx);
    }
    return *this;
  }

  Result __anext__()
  {
    if (_ctx != 0 && _anext_fn != 0)
    {
      return _anext_fn(_ctx);
    }
    return Result::Return(RT());
  }

  PyCoroutine(PyCoroutine&& other);
  PyCoroutine& operator=(PyCoroutine&& other);

private:
  void* _ctx;
  Result (*_send_fn)(void* ctx, ST value);
  void (*_destroy_fn)(void* ctx);
  PyCoroutine (*_aiter_fn)(void* ctx);
  Result (*_anext_fn)(void* ctx);

  friend struct py2cpp_coroutine_access;
  template<typename YT2, typename ST2, typename RT2, typename G2, bool B2>
  friend struct py2cpp_coroutine_detail::async_bind;
};

struct py2cpp_coroutine_access
{
  template<typename YT, typename ST, typename RT, typename G>
  static PyCoroutine<YT, ST, RT> make(G gen);
};

template<typename YT, typename ST, typename RT>
PyCoroutine<YT, ST, RT>::~PyCoroutine()
{
  reset();
}

template<typename YT, typename ST, typename RT>
PyCoroutine<YT, ST, RT>::PyCoroutine(PyCoroutine&& other)
  : _ctx(other._ctx),
    _send_fn(other._send_fn),
    _destroy_fn(other._destroy_fn),
    _aiter_fn(other._aiter_fn),
    _anext_fn(other._anext_fn)
{
  other._ctx = 0;
  other._send_fn = 0;
  other._destroy_fn = 0;
  other._aiter_fn = 0;
  other._anext_fn = 0;
}

template<typename YT, typename ST, typename RT>
PyCoroutine<YT, ST, RT>& PyCoroutine<YT, ST, RT>::operator=(PyCoroutine&& other)
{
  if (this != &other)
  {
    reset();
    _ctx = other._ctx;
    _send_fn = other._send_fn;
    _destroy_fn = other._destroy_fn;
    _aiter_fn = other._aiter_fn;
    _anext_fn = other._anext_fn;
    other._ctx = 0;
    other._send_fn = 0;
    other._destroy_fn = 0;
    other._aiter_fn = 0;
    other._anext_fn = 0;
  }
  return *this;
}

template<typename YT, typename ST, typename RT>
void PyCoroutine<YT, ST, RT>::reset()
{
  if (_ctx != 0 && _destroy_fn != 0)
  {
    _destroy_fn(_ctx);
  }
  _ctx = 0;
  _send_fn = 0;
  _destroy_fn = 0;
  _aiter_fn = 0;
  _anext_fn = 0;
}

template<typename YT, typename ST, typename RT, typename G>
struct py2cpp_coroutine_model : py2cpp_coroutine_detail::model_hdr
{
  G gen;

  static PY2CPP_TYPE(PyIterResult)<YT, RT> send(void* ctx, ST value)
  {
    py2cpp_coroutine_model* self = static_cast<py2cpp_coroutine_model*>(ctx);
    return self->gen.send(value);
  }

  static void destroy(void* ctx)
  {
    static_cast<py2cpp_coroutine_model*>(ctx)->release();
  }
};

namespace py2cpp_coroutine_detail
{
  template<typename YT, typename ST, typename RT, typename G, bool = has_async_iter<G>::value>
  struct async_bind;

  template<typename YT, typename ST, typename RT, typename G>
  struct async_bind<YT, ST, RT, G, false>
  {
    static void apply(PyCoroutine<YT, ST, RT>&)
    {
    }
  };

  template<typename YT, typename ST, typename RT, typename G>
  struct async_bind<YT, ST, RT, G, true>
  {
    static PyCoroutine<YT, ST, RT> aiter(void* ctx)
    {
      py2cpp_coroutine_model<YT, ST, RT, G>* self =
        static_cast<py2cpp_coroutine_model<YT, ST, RT, G>*>(ctx);
      return makeCoroutine<YT, ST, RT>(self->gen.__aiter__());
    }

    static PY2CPP_TYPE(PyIterResult)<YT, RT> anext(void* ctx)
    {
      py2cpp_coroutine_model<YT, ST, RT, G>* self =
        static_cast<py2cpp_coroutine_model<YT, ST, RT, G>*>(ctx);
      return self->gen.__anext__();
    }

    static void apply(PyCoroutine<YT, ST, RT>& out)
    {
      out._aiter_fn = &async_bind::aiter;
      out._anext_fn = &async_bind::anext;
    }
  };
}

template<typename YT, typename ST, typename RT, typename G>
PyCoroutine<YT, ST, RT> py2cpp_coroutine_access::make(G gen)
{
  py2cpp_coroutine_model<YT, ST, RT, G>* model =
    new py2cpp_coroutine_model<YT, ST, RT, G>();
  model->gen = gen;
  PyCoroutine<YT, ST, RT> out;
  out._ctx = model;
  out._send_fn = &py2cpp_coroutine_model<YT, ST, RT, G>::send;
  out._destroy_fn = &py2cpp_coroutine_model<YT, ST, RT, G>::destroy;
  py2cpp_coroutine_detail::async_bind<YT, ST, RT, G>::apply(out);
  return out;
}

template<typename YT, typename ST, typename RT, typename G>
PyCoroutine<YT, ST, RT> makeCoroutine(G gen)
{
  return py2cpp_coroutine_access::make<YT, ST, RT, G>(gen);
}
