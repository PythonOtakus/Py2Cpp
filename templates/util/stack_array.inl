PY2CPP_IGNORE
#include "py2cpp/util/stack_array.h"
#include "py2cpp/util/array.h"
#include "py2cpp/util/span.h"
PY2CPP_END

template<typename T, PyInt Length, PyInt Offset>
PyStackArrayIterator<T, Length, Offset> PyStackArray<T, Length, Offset>::__iter__()
{
  return PyStackArrayIterator<T, Length, Offset>(this);
}

template<typename T, PyInt Length, PyInt Offset>
PySpan<T> PyStackArray<T, Length, Offset>::PY2CPP_GETTER(view)() const
{
  return PySpan<T>(PY2CPP_GETTER(_buf)(), __len__(), 1);
}

template<typename T, PyInt Offset>
PySpan<T> PyStackArray<T, 0, Offset>::PY2CPP_GETTER(view)() const
{
  return PySpan<T>(nullptr, 0, 1);
}

template<typename T, PyInt Length, PyInt Offset>
PY2CPP_TYPE(PyArray)<T, 0> PyStackArray<T, Length, Offset>::_getslice(PySlice<PyInt, PyInt> sl) const
{
  PyInt n = __len__();
  PyInt start;
  PyInt stop;
  PyInt step;
  {
    auto trip = sl.indices(n);
    start = trip.template get<0>();
    stop = trip.template get<1>();
    step = trip.template get<2>();
  }
  PyInt cnt = 0;
  if (step > 0)
  {
    for (PyInt i = start; i < stop; i += step)
    {
      cnt += 1;
    }
  }
  else
  {
    for (PyInt i = start; i > stop; i += step)
    {
      cnt += 1;
    }
  }
  PY2CPP_TYPE(PyArray)<T, 0> out(cnt);
  PyInt j = 0;
  if (step > 0)
  {
    for (PyInt i = start; i < stop; i += step)
    {
      out.__setitem__(j, __getitem__(i));
      j += 1;
    }
  }
  else
  {
    for (PyInt i = start; i > stop; i += step)
    {
      out.__setitem__(j, __getitem__(i));
      j += 1;
    }
  }
  return out;
}

static PyInt _slice_count2d(PyInt start, PyInt stop, PyInt step)
{
  if (step > 0)
  {
    if (start >= stop)
    {
      return 0;
    }
    return ((stop - start) + step - 1) / step;
  }
  if (start <= stop)
  {
    return 0;
  }
  return ((start - stop) - step - 1) / (-step);
}

template<typename T, PyInt Rows, PyInt Cols, PyInt RowOff, PyInt ColOff>
PySpan2D<T> PyStackArray2D<T, Rows, Cols, RowOff, ColOff>::PY2CPP_GETTER(view)() const
{
  return PySpan2D<T>(
    PY2CPP_GETTER(_buf)(),
    PyTuple<PyInt, PyInt>(Rows, Cols),
    Cols);
}

template<typename T, PyInt Rows, PyInt Cols, PyInt RowOff, PyInt ColOff>
PY2CPP_TYPE(PyArray2D)<T> PyStackArray2D<T, Rows, Cols, RowOff, ColOff>::_getslice2d(
  PySlice<PyInt, PyInt> row_sl,
  PySlice<PyInt, PyInt> col_sl) const
{
  PyInt row_start;
  PyInt row_stop;
  PyInt row_step;
  PyInt col_start;
  PyInt col_stop;
  PyInt col_step;
  {
    auto trip = row_sl.indices(Rows);
    row_start = trip.template get<0>();
    row_stop = trip.template get<1>();
    row_step = trip.template get<2>();
  }
  {
    auto trip = col_sl.indices(Cols);
    col_start = trip.template get<0>();
    col_stop = trip.template get<1>();
    col_step = trip.template get<2>();
  }
  PyInt out_rows = _slice_count2d(row_start, row_stop, row_step);
  PyInt out_cols = _slice_count2d(col_start, col_stop, col_step);
  PY2CPP_TYPE(PyArray2D)<T> out(out_rows, out_cols);
  PyInt orow = 0;
  if (row_step > 0)
  {
    for (PyInt ri = row_start; ri < row_stop; ri += row_step)
    {
      PyInt ocol = 0;
      if (col_step > 0)
      {
        for (PyInt ci = col_start; ci < col_stop; ci += col_step)
        {
          out.__setitem__(
            PyTuple<PyInt, PyInt>(orow, ocol),
            __getitem__(PyTuple<PyInt, PyInt>(RowOff + ri, ColOff + ci)));
          ocol += 1;
        }
      }
      else
      {
        for (PyInt ci = col_start; ci > col_stop; ci += col_step)
        {
          out.__setitem__(
            PyTuple<PyInt, PyInt>(orow, ocol),
            __getitem__(PyTuple<PyInt, PyInt>(RowOff + ri, ColOff + ci)));
          ocol += 1;
        }
      }
      orow += 1;
    }
  }
  else
  {
    for (PyInt ri = row_start; ri > row_stop; ri += row_step)
    {
      PyInt ocol = 0;
      if (col_step > 0)
      {
        for (PyInt ci = col_start; ci < col_stop; ci += col_step)
        {
          out.__setitem__(
            PyTuple<PyInt, PyInt>(orow, ocol),
            __getitem__(PyTuple<PyInt, PyInt>(RowOff + ri, ColOff + ci)));
          ocol += 1;
        }
      }
      else
      {
        for (PyInt ci = col_start; ci > col_stop; ci += col_step)
        {
          out.__setitem__(
            PyTuple<PyInt, PyInt>(orow, ocol),
            __getitem__(PyTuple<PyInt, PyInt>(RowOff + ri, ColOff + ci)));
          ocol += 1;
        }
      }
      orow += 1;
    }
  }
  return out;
}

static PyInt _slice_count3d(PyInt start, PyInt stop, PyInt step)
{
  if (step > 0)
  {
    if (start >= stop)
    {
      return 0;
    }
    return ((stop - start) + step - 1) / step;
  }
  if (start <= stop)
  {
    return 0;
  }
  return ((start - stop) - step - 1) / (-step);
}

template<typename T, PyInt D0, PyInt D1, PyInt D2, PyInt O0, PyInt O1, PyInt O2>
PySpan3D<T> PyStackArray3D<T, D0, D1, D2, O0, O1, O2>::PY2CPP_GETTER(view)() const
{
  return PySpan3D<T>(
    PY2CPP_GETTER(_buf)(),
    PyTuple<PyInt, PyInt, PyInt>(D0, D1, D2),
    PyTuple<PyInt, PyInt>(D1 * D2, D2));
}

template<typename T, PyInt D0, PyInt D1, PyInt D2, PyInt O0, PyInt O1, PyInt O2>
PY2CPP_TYPE(PyArray3D)<T> PyStackArray3D<T, D0, D1, D2, O0, O1, O2>::_getslice3d(
  PySlice<PyInt, PyInt> sl0,
  PySlice<PyInt, PyInt> sl1,
  PySlice<PyInt, PyInt> sl2) const
{
  PyInt s0;
  PyInt e0;
  PyInt t0;
  PyInt s1;
  PyInt e1;
  PyInt t1;
  PyInt s2;
  PyInt e2;
  PyInt t2;
  {
    auto trip = sl0.indices(D0);
    s0 = trip.template get<0>();
    e0 = trip.template get<1>();
    t0 = trip.template get<2>();
  }
  {
    auto trip = sl1.indices(D1);
    s1 = trip.template get<0>();
    e1 = trip.template get<1>();
    t1 = trip.template get<2>();
  }
  {
    auto trip = sl2.indices(D2);
    s2 = trip.template get<0>();
    e2 = trip.template get<1>();
    t2 = trip.template get<2>();
  }
  PyInt n0 = _slice_count3d(s0, e0, t0);
  PyInt n1 = _slice_count3d(s1, e1, t1);
  PyInt n2 = _slice_count3d(s2, e2, t2);
  PY2CPP_TYPE(PyArray3D)<T> out(n0, n1, n2);
  PyInt o0 = 0;
  if (t0 > 0)
  {
    for (PyInt i = s0; i < e0; i += t0)
    {
      PyInt o1 = 0;
      if (t1 > 0)
      {
        for (PyInt j = s1; j < e1; j += t1)
        {
          PyInt o2 = 0;
          if (t2 > 0)
          {
            for (PyInt k = s2; k < e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          else
          {
            for (PyInt k = s2; k > e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          o1 += 1;
        }
      }
      else
      {
        for (PyInt j = s1; j > e1; j += t1)
        {
          PyInt o2 = 0;
          if (t2 > 0)
          {
            for (PyInt k = s2; k < e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          else
          {
            for (PyInt k = s2; k > e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          o1 += 1;
        }
      }
      o0 += 1;
    }
  }
  else
  {
    for (PyInt i = s0; i > e0; i += t0)
    {
      PyInt o1 = 0;
      if (t1 > 0)
      {
        for (PyInt j = s1; j < e1; j += t1)
        {
          PyInt o2 = 0;
          if (t2 > 0)
          {
            for (PyInt k = s2; k < e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          else
          {
            for (PyInt k = s2; k > e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          o1 += 1;
        }
      }
      else
      {
        for (PyInt j = s1; j > e1; j += t1)
        {
          PyInt o2 = 0;
          if (t2 > 0)
          {
            for (PyInt k = s2; k < e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          else
          {
            for (PyInt k = s2; k > e2; k += t2)
            {
              out.__setitem__(
                PyTuple<PyInt, PyInt, PyInt>(o0, o1, o2),
                __getitem__(PyTuple<PyInt, PyInt, PyInt>(O0 + i, O1 + j, O2 + k)));
              o2 += 1;
            }
          }
          o1 += 1;
        }
      }
      o0 += 1;
    }
  }
  return out;
}
