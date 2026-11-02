#include "py2cpp/core/iter_result.h"


// 擦除生成器句柄：``Generator[Y,S,R]`` 形参/字段/``@virtual`` 返回；具体 ``*_generator`` 经 ``makeGenerator`` 装箱。
namespace py2cpp_generator_detail
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

template<typename YT, typename ST, typename RT>
class PyGenerator
{
public:
  typedef YT Element;
  typedef ST SendType;
  typedef RT ReturnType;
  typedef PY2CPP_TYPE(PyIterResult)<YT, RT> Result;

  explicit PyGenerator() : _ctx(0), _send_fn(0), _destroy_fn(0)
  {
  }

  PyGenerator(const PyGenerator& other)
    : _ctx(other._ctx), _send_fn(other._send_fn), _destroy_fn(other._destroy_fn)
  {
    if (_ctx != 0)
    {
      static_cast<py2cpp_generator_detail::model_hdr*>(_ctx)->add_ref();
    }
  }

  PyGenerator& operator=(const PyGenerator& other)
  {
    if (this != &other)
    {
      reset();
      _ctx = other._ctx;
      _send_fn = other._send_fn;
      _destroy_fn = other._destroy_fn;
      if (_ctx != 0)
      {
        static_cast<py2cpp_generator_detail::model_hdr*>(_ctx)->add_ref();
      }
    }
    return *this;
  }

  ~PyGenerator();

  void reset();
  bool empty() const
  {
    return _ctx == 0;
  }

  PyGenerator& __iter__()
  {
    return *this;
  }

  Result __next__()
  {
    return send(py2cpp_generator_detail::default_send_value<ST>());
  }

  Result send(ST value)
  {
    if (_ctx == 0 || _send_fn == 0)
    {
      return Result::Return(RT());
    }
    return _send_fn(_ctx, value);
  }

  PyGenerator(PyGenerator&& other);
  PyGenerator& operator=(PyGenerator&& other);

private:
  void* _ctx;
  Result (*_send_fn)(void* ctx, ST value);
  void (*_destroy_fn)(void* ctx);

  friend struct py2cpp_generator_access;
};

struct py2cpp_generator_access
{
  template<typename YT, typename ST, typename RT, typename G>
  static PyGenerator<YT, ST, RT> make(G gen);
};

template<typename YT, typename ST, typename RT>
PyGenerator<YT, ST, RT>::~PyGenerator()
{
  reset();
}

template<typename YT, typename ST, typename RT>
PyGenerator<YT, ST, RT>::PyGenerator(PyGenerator&& other)
  : _ctx(other._ctx), _send_fn(other._send_fn), _destroy_fn(other._destroy_fn)
{
  other._ctx = 0;
  other._send_fn = 0;
  other._destroy_fn = 0;
}

template<typename YT, typename ST, typename RT>
PyGenerator<YT, ST, RT>& PyGenerator<YT, ST, RT>::operator=(PyGenerator&& other)
{
  if (this != &other)
  {
    reset();
    _ctx = other._ctx;
    _send_fn = other._send_fn;
    _destroy_fn = other._destroy_fn;
    other._ctx = 0;
    other._send_fn = 0;
    other._destroy_fn = 0;
  }
  return *this;
}

template<typename YT, typename ST, typename RT>
void PyGenerator<YT, ST, RT>::reset()
{
  if (_ctx != 0 && _destroy_fn != 0)
  {
    _destroy_fn(_ctx);
  }
  _ctx = 0;
  _send_fn = 0;
  _destroy_fn = 0;
}

template<typename YT, typename ST, typename RT, typename G>
struct py2cpp_generator_model : py2cpp_generator_detail::model_hdr
{
  G gen;

  static PY2CPP_TYPE(PyIterResult)<YT, RT> send(void* ctx, ST value)
  {
    py2cpp_generator_model* self = static_cast<py2cpp_generator_model*>(ctx);
    return self->gen.send(value);
  }

  static void destroy(void* ctx)
  {
    static_cast<py2cpp_generator_model*>(ctx)->release();
  }
};

template<typename YT, typename ST, typename RT, typename G>
PyGenerator<YT, ST, RT> py2cpp_generator_access::make(G gen)
{
  py2cpp_generator_model<YT, ST, RT, G>* model =
    new py2cpp_generator_model<YT, ST, RT, G>();
  model->gen = gen;
  PyGenerator<YT, ST, RT> out;
  out._ctx = model;
  out._send_fn = &py2cpp_generator_model<YT, ST, RT, G>::send;
  out._destroy_fn = &py2cpp_generator_model<YT, ST, RT, G>::destroy;
  return out;
}

template<typename YT, typename ST, typename RT, typename G>
PyGenerator<YT, ST, RT> makeGenerator(G gen)
{
  return py2cpp_generator_access::make<YT, ST, RT, G>(gen);
}
