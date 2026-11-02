PY2CPP_IGNORE
#include "py2cpp/util/tuple.h"
PY2CPP_END

// MSVC 会在 switch 各分支实例化模板；仅构建长度 sizeof...(Args) 的函数表，避免越界索引被实例化。
template<int I, typename... Args>
typename _PyTupleElem<I, _PyTupleHolder<Args...>>::elem_t&
_py_tuple_elem_ref(_PyTupleHolder<Args...>& h)
{
  return _PyTupleElem<I, _PyTupleHolder<Args...>>::get(h);
}

template<int I, int N, typename... Args>
struct _PyTupleGetterInit
{
  typedef typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t Elem;
  typedef Elem& (*Fn)(_PyTupleHolder<Args...>&);
  static void fill(Fn* table)
  {
    table[I] = &_py_tuple_elem_ref<I, Args...>;
    _PyTupleGetterInit<I + 1, N, Args...>::fill(table);
  }
};

template<int N, typename... Args>
struct _PyTupleGetterInit<N, N, Args...>
{
  typedef typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t Elem;
  typedef Elem& (*Fn)(_PyTupleHolder<Args...>&);
  static void fill(Fn*)
  {
  }
};

template<typename... Args>
typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t&
_py_tuple_get_runtime(int index, _PyTupleHolder<Args...>& h)
{
  typedef typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t Elem;
  typedef Elem& (*Fn)(_PyTupleHolder<Args...>&);
  static Fn table[sizeof...(Args)];
  static bool ready = false;
  if (!ready)
  {
    _PyTupleGetterInit<0, (int)sizeof...(Args), Args...>::fill(table);
    ready = true;
  }
  return table[index](h);
}

template<typename... Args>
typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t& PyTuple<Args...>::__getitem__(int index)
{
  if (index < 0 || index >= (int)sizeof...(Args))
  {
    throw PY2CPP_TYPE(PyIndexError)();
  }
  return _py_tuple_get_runtime(index, this->_h);
}

template<typename... Args>
const typename _PyTupleElem<0, _PyTupleHolder<Args...>>::elem_t& PyTuple<Args...>::__getitem__(int index) const
{
  if (index < 0 || index >= (int)sizeof...(Args))
  {
    throw PY2CPP_TYPE(PyIndexError)();
  }
  return _py_tuple_get_runtime(index, const_cast<_PyTupleHolder<Args...>&>(this->_h));
}
