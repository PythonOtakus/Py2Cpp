#include "py2cpp/core/iter_result.h"
#include "py2cpp/core/none.h"
#include <utility>


// 擦除异步生成器句柄：``AsyncGenerator[Y,S]`` 形参/字段/``@virtual`` 返回；具体 ``*_coroutine`` 经 ``makeAsyncGenerator`` 装箱。
namespace py2cpp_async_generator_detail
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
}

template<typename YT, typename ST>
class PyAsyncGenerator
{
public:
  typedef YT Element;
  typedef ST SendType;
  typedef PY2CPP_TYPE(PyNone) ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<YT, PY2CPP_TYPE(PyNone)> Result;

  explicit PyAsyncGenerator()
    : _ctx(0), _aiter_fn(0), _anext_fn(0), _asend_fn(0), _destroy_fn(0)
  {
  }

  PyAsyncGenerator(const PyAsyncGenerator& other)
    : _ctx(other._ctx),
      _aiter_fn(other._aiter_fn),
      _anext_fn(other._anext_fn),
      _asend_fn(other._asend_fn),
      _destroy_fn(other._destroy_fn)
  {
    if (_ctx != 0)
    {
      static_cast<py2cpp_async_generator_detail::model_hdr*>(_ctx)->add_ref();
    }
  }

  PyAsyncGenerator& operator=(const PyAsyncGenerator& other)
  {
    if (this != &other)
    {
      reset();
      _ctx = other._ctx;
      _aiter_fn = other._aiter_fn;
      _anext_fn = other._anext_fn;
      _asend_fn = other._asend_fn;
      _destroy_fn = other._destroy_fn;
      if (_ctx != 0)
      {
        static_cast<py2cpp_async_generator_detail::model_hdr*>(_ctx)->add_ref();
      }
    }
    return *this;
  }

  ~PyAsyncGenerator();

  void reset();
  bool empty() const
  {
    return _ctx == 0;
  }

  PyAsyncGenerator __aiter__()
  {
    if (_ctx != 0 && _aiter_fn != 0)
    {
      return _aiter_fn(_ctx);
    }
    return *this;
  }

  Result __anext__()
  {
    return asend(py2cpp_async_generator_detail::default_send_value<ST>());
  }

  Result asend(ST value)
  {
    if (_ctx == 0 || _asend_fn == 0)
    {
      return Result::Return(PY2CPP_TYPE(PyNone)());
    }
    return _asend_fn(_ctx, value);
  }

  PyAsyncGenerator(PyAsyncGenerator&& other);
  PyAsyncGenerator& operator=(PyAsyncGenerator&& other);

private:
  void* _ctx;
  PyAsyncGenerator (*_aiter_fn)(void* ctx);
  Result (*_anext_fn)(void* ctx);
  Result (*_asend_fn)(void* ctx, ST value);
  void (*_destroy_fn)(void* ctx);

  friend struct py2cpp_async_generator_access;
};

struct py2cpp_async_generator_access
{
  template<typename YT, typename ST, typename G>
  static PyAsyncGenerator<YT, ST> make(G gen);
};

template<typename YT, typename ST>
PyAsyncGenerator<YT, ST>::~PyAsyncGenerator()
{
  reset();
}

template<typename YT, typename ST>
PyAsyncGenerator<YT, ST>::PyAsyncGenerator(PyAsyncGenerator&& other)
  : _ctx(other._ctx),
    _aiter_fn(other._aiter_fn),
    _anext_fn(other._anext_fn),
    _asend_fn(other._asend_fn),
    _destroy_fn(other._destroy_fn)
{
  other._ctx = 0;
  other._aiter_fn = 0;
  other._anext_fn = 0;
  other._asend_fn = 0;
  other._destroy_fn = 0;
}

template<typename YT, typename ST>
PyAsyncGenerator<YT, ST>& PyAsyncGenerator<YT, ST>::operator=(PyAsyncGenerator&& other)
{
  if (this != &other)
  {
    reset();
    _ctx = other._ctx;
    _aiter_fn = other._aiter_fn;
    _anext_fn = other._anext_fn;
    _asend_fn = other._asend_fn;
    _destroy_fn = other._destroy_fn;
    other._ctx = 0;
    other._aiter_fn = 0;
    other._anext_fn = 0;
    other._asend_fn = 0;
    other._destroy_fn = 0;
  }
  return *this;
}

template<typename YT, typename ST>
void PyAsyncGenerator<YT, ST>::reset()
{
  if (_ctx != 0 && _destroy_fn != 0)
  {
    _destroy_fn(_ctx);
  }
  _ctx = 0;
  _aiter_fn = 0;
  _anext_fn = 0;
  _asend_fn = 0;
  _destroy_fn = 0;
}

template<typename YT, typename ST, typename G>
struct py2cpp_async_generator_model : py2cpp_async_generator_detail::model_hdr
{
  G gen;

  static PyAsyncGenerator<YT, ST> aiter(void* ctx)
  {
    py2cpp_async_generator_model* self = static_cast<py2cpp_async_generator_model*>(ctx);
    return makeAsyncGenerator<YT, ST>(self->gen.__aiter__());
  }

  static PY2CPP_TYPE(PyIterResult)<YT, PY2CPP_TYPE(PyNone)> anext(void* ctx)
  {
    py2cpp_async_generator_model* self = static_cast<py2cpp_async_generator_model*>(ctx);
    return self->gen.__anext__();
  }

  static PY2CPP_TYPE(PyIterResult)<YT, PY2CPP_TYPE(PyNone)> asend(void* ctx, ST value)
  {
    py2cpp_async_generator_model* self = static_cast<py2cpp_async_generator_model*>(ctx);
    return self->gen.send(value);
  }

  static void destroy(void* ctx)
  {
    static_cast<py2cpp_async_generator_model*>(ctx)->release();
  }
};

template<typename YT, typename ST, typename G>
PyAsyncGenerator<YT, ST> py2cpp_async_generator_access::make(G gen)
{
  py2cpp_async_generator_model<YT, ST, G>* model =
    new py2cpp_async_generator_model<YT, ST, G>();
  model->gen = gen;
  PyAsyncGenerator<YT, ST> out;
  out._ctx = model;
  out._aiter_fn = &py2cpp_async_generator_model<YT, ST, G>::aiter;
  out._anext_fn = &py2cpp_async_generator_model<YT, ST, G>::anext;
  out._asend_fn = &py2cpp_async_generator_model<YT, ST, G>::asend;
  out._destroy_fn = &py2cpp_async_generator_model<YT, ST, G>::destroy;
  return out;
}

template<typename YT, typename ST, typename G>
PyAsyncGenerator<YT, ST> makeAsyncGenerator(G gen)
{
  return py2cpp_async_generator_access::make<YT, ST, G>(gen);
}
