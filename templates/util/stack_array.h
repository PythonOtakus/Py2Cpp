#include "py2cpp/core/exceptions.h"
#include "py2cpp/core/iter_result.h"
#include "py2cpp/util/slice.h"
#include "py2cpp/util/span.h"
#include "py2cpp/util/tuple.h"
#include "py2cpp/minimal.h"
#include "py2cpp/py_types.h"

namespace py2cpp
{
  namespace util
  {
    namespace array
    {
      template<typename U, PyInt _StackLength>
      class PyArray;
      template<typename U>
      class PyArray2D;
      template<typename U>
      class PyArray3D;
    }
  }
}

template<typename T, PyInt Length, PyInt Offset>
class PyStackArrayIterator;

/// ``T[:N]`` / ``stack_array<T, Length, Offset>``：``s[k]`` 为 ``k∈[Offset,Offset+Length)``。
template<typename T, PyInt Length, PyInt Offset>
class PyStackArray
{
  T _data[Length];

  PyBool _index_in_range(PyInt index) const
  {
    return ((index >= Offset) && (index < (Offset + Length)));
  }

public:
  T* PY2CPP_GETTER(_buf)() const
  {
    return const_cast<T*>(_data);
  }

  explicit PyStackArray()
  {
    for (PyInt i = 0; i < Length; i += 1)
    {
      _data[i] = T();
    }
  }

  PyInt __len__() const
  {
    return Length;
  }

  PySpan<T> PY2CPP_GETTER(view)() const;

  PyStackArrayIterator<T, Length, Offset> __iter__();

  T& __getitem__(PyInt index)
  {
    if (!_index_in_range(index))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    return _data[(index - Offset)];
  }

  const T& __getitem__(PyInt index) const
  {
    if (!_index_in_range(index))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    return _data[(index - Offset)];
  }

  void __setitem__(PyInt index, T value)
  {
    if (!_index_in_range(index))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    _data[(index - Offset)] = value;
  }

  PY2CPP_TYPE(PyArray)<T, 0> _getslice(PySlice<PyInt, PyInt> sl) const;

  void __copy__(const PyStackArray<T, Length, Offset>& other)
  {
    for (PyInt i = 0; i < Length; i += 1)
    {
      _data[i] = other._data[i];
    }
  }

  void fill(T value)
  {
    for (PyInt i = 0; i < Length; i += 1)
    {
      _data[i] = value;
    }
  }

  T& unsafe_get(PyInt index)
  {
    return _data[(index - Offset)];
  }

  const T& unsafe_get(PyInt index) const
  {
    return _data[(index - Offset)];
  }

  void unsafe_set(PyInt index, T value)
  {
    _data[(index - Offset)] = value;
  }

  PyBool __bool__() const
  {
    return (Length > 0);
  }

  explicit operator PyBool() const
  {
    return __bool__();
  }
};

/// ``Length=0``：纯堆路径占位，无 ``T`` 默认构造（``PyArray<T,0>`` 等）。
template<typename T, PyInt Offset>
class PyStackArray<T, 0, Offset>
{
public:
  T* PY2CPP_GETTER(_buf)() const
  {
    return nullptr;
  }

  explicit PyStackArray()
  {
  }

  PyInt __len__() const
  {
    return 0;
  }

  PySpan<T> PY2CPP_GETTER(view)() const;

  PyStackArrayIterator<T, 0, Offset> __iter__();

  T& __getitem__(PyInt index)
  {
    throw PY2CPP_TYPE(IndexError)();
  }

  const T& __getitem__(PyInt index) const
  {
    throw PY2CPP_TYPE(IndexError)();
  }

  void __setitem__(PyInt index, T value)
  {
    throw PY2CPP_TYPE(IndexError)();
  }

  PY2CPP_TYPE(PyArray)<T, 0> _getslice(PySlice<PyInt, PyInt> sl) const;

  void __copy__(const PyStackArray<T, 0, Offset>& other)
  {
  }

  void fill(T value)
  {
  }

  T& unsafe_get(PyInt index)
  {
    throw PY2CPP_TYPE(IndexError)();
  }

  const T& unsafe_get(PyInt index) const
  {
    throw PY2CPP_TYPE(IndexError)();
  }

  void unsafe_set(PyInt index, T value)
  {
    throw PY2CPP_TYPE(IndexError)();
  }

  PyBool __bool__() const
  {
    return false;
  }

  explicit operator PyBool() const
  {
    return __bool__();
  }
};

/// ``PyStackArray`` 正向迭代；``__next__`` 使用 ``Offset + _index`` 绝对下标。
template<typename T, PyInt Length, PyInt Offset>
class PyStackArrayIterator
{
  PyStackArray<T, Length, Offset>* _host;
  PyInt _index;

public:
  explicit PyStackArrayIterator()
  {
    _host = nullptr;
    _index = 0;
  }

  PyStackArrayIterator(PyStackArray<T, Length, Offset>* host)
  {
    _host = host;
    _index = 0;
  }

  PyStackArrayIterator<T, Length, Offset> __iter__()
  {
    return *this;
  }

  PY2CPP_TYPE(PyIterResult)<T, T> __next__()
  {
    if (_index >= _host->__len__())
    {
      return (PY2CPP_TYPE(PyIterResult)<T, T>::Return)(T());
    }
    T value = _host->__getitem__(Offset + _index);
    _index += 1;
    return (PY2CPP_TYPE(PyIterResult)<T, T>::Yield)(value);
  }

  void assign(PyStackArrayIterator<T, Length, Offset> other)
  {
    _host = other._host;
    _index = other._index;
  }
};

/// ``T[:R, :C]`` / 子矩形 ``T[r0:r1, c0:c1]``：行主序栈存储。
template<typename T, PyInt Rows, PyInt Cols, PyInt RowOff, PyInt ColOff>
class PyStackArray2D
{
  T _data[Rows * Cols];

  PyBool _row_in_range(PyInt row) const
  {
    return ((row >= RowOff) && (row < (RowOff + Rows)));
  }

  PyBool _col_in_range(PyInt col) const
  {
    return ((col >= ColOff) && (col < (ColOff + Cols)));
  }

  PyInt _linear(PyInt row, PyInt col) const
  {
    return ((row - RowOff) * Cols) + (col - ColOff);
  }

public:
  T* PY2CPP_GETTER(_buf)() const
  {
    return const_cast<T*>(_data);
  }

  explicit PyStackArray2D()
  {
    for (PyInt i = 0; i < (Rows * Cols); i += 1)
    {
      _data[i] = T();
    }
  }

  PySpan2D<T> PY2CPP_GETTER(view)() const;

  T& __getitem__(PyTuple<PyInt, PyInt> index)
  {
    PyInt row = index.template get<0>();
    PyInt col = index.template get<1>();
    if (!_row_in_range(row) || !_col_in_range(col))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    return _data[_linear(row, col)];
  }

  const T& __getitem__(PyTuple<PyInt, PyInt> index) const
  {
    PyInt row = index.template get<0>();
    PyInt col = index.template get<1>();
    if (!_row_in_range(row) || !_col_in_range(col))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    return _data[_linear(row, col)];
  }

  void __setitem__(PyTuple<PyInt, PyInt> index, T value)
  {
    PyInt row = index.template get<0>();
    PyInt col = index.template get<1>();
    if (!_row_in_range(row) || !_col_in_range(col))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    _data[_linear(row, col)] = value;
  }

  PY2CPP_TYPE(PyArray2D)<T> _getslice2d(
    PySlice<PyInt, PyInt> row_sl,
    PySlice<PyInt, PyInt> col_sl) const;

  void __copy__(const PyStackArray2D<T, Rows, Cols, RowOff, ColOff>& other)
  {
    for (PyInt i = 0; i < (Rows * Cols); i += 1)
    {
      _data[i] = other._data[i];
    }
  }

  void fill(T value)
  {
    for (PyInt i = 0; i < (Rows * Cols); i += 1)
    {
      _data[i] = value;
    }
  }

  T& unsafe_get(PyInt row, PyInt col)
  {
    return _data[_linear(row, col)];
  }

  const T& unsafe_get(PyInt row, PyInt col) const
  {
    return _data[_linear(row, col)];
  }

  void unsafe_set(PyInt row, PyInt col, T value)
  {
    _data[_linear(row, col)] = value;
  }

  PyBool __bool__() const
  {
    return (Rows > 0) && (Cols > 0);
  }

  explicit operator PyBool() const
  {
    return __bool__();
  }
};

template<typename T, PyInt D0, PyInt D1, PyInt D2, PyInt O0, PyInt O1, PyInt O2>
class PyStackArray3D
{
  T _data[D0 * D1 * D2];

  PyBool _in_range(PyInt i, PyInt off, PyInt dim) const
  {
    return ((i >= off) && (i < (off + dim)));
  }

  PyInt _linear(PyInt i, PyInt j, PyInt k) const
  {
    return (((i - O0) * D1) + (j - O1)) * D2 + (k - O2);
  }

public:
  T* PY2CPP_GETTER(_buf)() const
  {
    return const_cast<T*>(_data);
  }

  explicit PyStackArray3D()
  {
    for (PyInt n = 0; n < (D0 * D1 * D2); n += 1)
    {
      _data[n] = T();
    }
  }

  PySpan3D<T> PY2CPP_GETTER(view)() const;

  T& __getitem__(PyTuple<PyInt, PyInt, PyInt> index)
  {
    PyInt i = index.template get<0>();
    PyInt j = index.template get<1>();
    PyInt k = index.template get<2>();
    if (!_in_range(i, O0, D0) || !_in_range(j, O1, D1) || !_in_range(k, O2, D2))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    return _data[_linear(i, j, k)];
  }

  const T& __getitem__(PyTuple<PyInt, PyInt, PyInt> index) const
  {
    PyInt i = index.template get<0>();
    PyInt j = index.template get<1>();
    PyInt k = index.template get<2>();
    if (!_in_range(i, O0, D0) || !_in_range(j, O1, D1) || !_in_range(k, O2, D2))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    return _data[_linear(i, j, k)];
  }

  void __setitem__(PyTuple<PyInt, PyInt, PyInt> index, T value)
  {
    PyInt i = index.template get<0>();
    PyInt j = index.template get<1>();
    PyInt k = index.template get<2>();
    if (!_in_range(i, O0, D0) || !_in_range(j, O1, D1) || !_in_range(k, O2, D2))
    {
      throw PY2CPP_TYPE(IndexError)();
    }
    _data[_linear(i, j, k)] = value;
  }

  PY2CPP_TYPE(PyArray3D)<T> _getslice3d(
    PySlice<PyInt, PyInt> sl0,
    PySlice<PyInt, PyInt> sl1,
    PySlice<PyInt, PyInt> sl2) const;

  void __copy__(const PyStackArray3D<T, D0, D1, D2, O0, O1, O2>& other)
  {
    for (PyInt n = 0; n < (D0 * D1 * D2); n += 1)
    {
      _data[n] = other._data[n];
    }
  }

  void fill(T value)
  {
    for (PyInt n = 0; n < (D0 * D1 * D2); n += 1)
    {
      _data[n] = value;
    }
  }

  T& unsafe_get(PyInt i, PyInt j, PyInt k)
  {
    return _data[_linear(i, j, k)];
  }

  const T& unsafe_get(PyInt i, PyInt j, PyInt k) const
  {
    return _data[_linear(i, j, k)];
  }

  void unsafe_set(PyInt i, PyInt j, PyInt k, T value)
  {
    _data[_linear(i, j, k)] = value;
  }

  PyBool __bool__() const
  {
    return (D0 > 0) && (D1 > 0) && (D2 > 0);
  }

  explicit operator PyBool() const
  {
    return __bool__();
  }
};
