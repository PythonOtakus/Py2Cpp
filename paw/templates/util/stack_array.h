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

  PyBool _indexInRange(PyInt index) const
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
    if (!_indexInRange(index))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    return _data[(index - Offset)];
  }

  const T& __getitem__(PyInt index) const
  {
    if (!_indexInRange(index))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    return _data[(index - Offset)];
  }

  void __setitem__(PyInt index, T value)
  {
    if (!_indexInRange(index))
    {
      throw PY2CPP_TYPE(PyIndexError)();
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

  T& unsafeGet(PyInt index)
  {
    return _data[(index - Offset)];
  }

  const T& unsafeGet(PyInt index) const
  {
    return _data[(index - Offset)];
  }

  void unsafeSet(PyInt index, T value)
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
    throw PY2CPP_TYPE(PyIndexError)();
  }

  const T& __getitem__(PyInt index) const
  {
    throw PY2CPP_TYPE(PyIndexError)();
  }

  void __setitem__(PyInt index, T value)
  {
    throw PY2CPP_TYPE(PyIndexError)();
  }

  PY2CPP_TYPE(PyArray)<T, 0> _getslice(PySlice<PyInt, PyInt> sl) const;

  void __copy__(const PyStackArray<T, 0, Offset>& other)
  {
  }

  void fill(T value)
  {
  }

  T& unsafeGet(PyInt index)
  {
    throw PY2CPP_TYPE(PyIndexError)();
  }

  const T& unsafeGet(PyInt index) const
  {
    throw PY2CPP_TYPE(PyIndexError)();
  }

  void unsafeSet(PyInt index, T value)
  {
    throw PY2CPP_TYPE(PyIndexError)();
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

  PyBool _rowInRange(PyInt row) const
  {
    return ((row >= RowOff) && (row < (RowOff + Rows)));
  }

  PyBool _colInRange(PyInt col) const
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
    if (!_rowInRange(row) || !_colInRange(col))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    return _data[_linear(row, col)];
  }

  const T& __getitem__(PyTuple<PyInt, PyInt> index) const
  {
    PyInt row = index.template get<0>();
    PyInt col = index.template get<1>();
    if (!_rowInRange(row) || !_colInRange(col))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    return _data[_linear(row, col)];
  }

  void __setitem__(PyTuple<PyInt, PyInt> index, T value)
  {
    PyInt row = index.template get<0>();
    PyInt col = index.template get<1>();
    if (!_rowInRange(row) || !_colInRange(col))
    {
      throw PY2CPP_TYPE(PyIndexError)();
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

  T& unsafeGet(PyInt row, PyInt col)
  {
    return _data[_linear(row, col)];
  }

  const T& unsafeGet(PyInt row, PyInt col) const
  {
    return _data[_linear(row, col)];
  }

  void unsafeSet(PyInt row, PyInt col, T value)
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

template<typename T, PyInt Dim0, PyInt Dim1, PyInt Dim2, PyInt Off0, PyInt Off1, PyInt Off2>
class PyStackArray3D
{
  T _data[Dim0 * Dim1 * Dim2];

  PyBool _inRange(PyInt i, PyInt off, PyInt dim) const
  {
    return ((i >= off) && (i < (off + dim)));
  }

  PyInt _linear(PyInt i, PyInt j, PyInt k) const
  {
    return (((i - Off0) * Dim1) + (j - Off1)) * Dim2 + (k - Off2);
  }

public:
  T* PY2CPP_GETTER(_buf)() const
  {
    return const_cast<T*>(_data);
  }

  explicit PyStackArray3D()
  {
    for (PyInt n = 0; n < (Dim0 * Dim1 * Dim2); n += 1)
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
    if (!_inRange(i, Off0, Dim0) || !_inRange(j, Off1, Dim1) || !_inRange(k, Off2, Dim2))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    return _data[_linear(i, j, k)];
  }

  const T& __getitem__(PyTuple<PyInt, PyInt, PyInt> index) const
  {
    PyInt i = index.template get<0>();
    PyInt j = index.template get<1>();
    PyInt k = index.template get<2>();
    if (!_inRange(i, Off0, Dim0) || !_inRange(j, Off1, Dim1) || !_inRange(k, Off2, Dim2))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    return _data[_linear(i, j, k)];
  }

  void __setitem__(PyTuple<PyInt, PyInt, PyInt> index, T value)
  {
    PyInt i = index.template get<0>();
    PyInt j = index.template get<1>();
    PyInt k = index.template get<2>();
    if (!_inRange(i, Off0, Dim0) || !_inRange(j, Off1, Dim1) || !_inRange(k, Off2, Dim2))
    {
      throw PY2CPP_TYPE(PyIndexError)();
    }
    _data[_linear(i, j, k)] = value;
  }

  PY2CPP_TYPE(PyArray3D)<T> _getslice3d(
    PySlice<PyInt, PyInt> sl0,
    PySlice<PyInt, PyInt> sl1,
    PySlice<PyInt, PyInt> sl2) const;

  void __copy__(const PyStackArray3D<T, Dim0, Dim1, Dim2, Off0, Off1, Off2>& other)
  {
    for (PyInt n = 0; n < (Dim0 * Dim1 * Dim2); n += 1)
    {
      _data[n] = other._data[n];
    }
  }

  void fill(T value)
  {
    for (PyInt n = 0; n < (Dim0 * Dim1 * Dim2); n += 1)
    {
      _data[n] = value;
    }
  }

  T& unsafeGet(PyInt i, PyInt j, PyInt k)
  {
    return _data[_linear(i, j, k)];
  }

  const T& unsafeGet(PyInt i, PyInt j, PyInt k) const
  {
    return _data[_linear(i, j, k)];
  }

  void unsafeSet(PyInt i, PyInt j, PyInt k, T value)
  {
    _data[_linear(i, j, k)] = value;
  }

  PyBool __bool__() const
  {
    return (Dim0 > 0) && (Dim1 > 0) && (Dim2 > 0);
  }

  explicit operator PyBool() const
  {
    return __bool__();
  }
};
