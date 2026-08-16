PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
using namespace py2cpp::core::exceptions;
PY2CPP_END

namespace py2cpp {
namespace core {
namespace exceptions {

using ExcKind = PyExceptionGroup::ExcKind;
using PyExcTypeUnion = PyExceptionGroup::PyExcTypeUnion;

bool exc_kind_is_instance(ExcKind slot, ExcKind match)
{
  if (slot == match)
  {
    return true;
  }
  if (match == ExcKind::PyValueError)
  {
    return slot == ExcKind::PyStatisticsError
        || slot == ExcKind::PyLinAlgError;
  }
  if (match == ExcKind::PyOSError)
  {
    return slot == ExcKind::PyFileNotFoundError
        || slot == ExcKind::PyFileExistsError;
  }
  return false;
}

namespace {

PyExcTypeUnion make_slot(const PyStopIteration& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyStopIteration;
  s.stop_iteration = e;
  return s;
}

PyExcTypeUnion make_slot(const PyTypeError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyTypeError;
  s.type_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyKeyError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyKeyError;
  s.key_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyIndexError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyIndexError;
  s.index_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyValueError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyValueError;
  s.value_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyStatisticsError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyStatisticsError;
  s.statistics_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyLinAlgError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyLinAlgError;
  s.linalg_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyRuntimeError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyRuntimeError;
  s.runtime_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyOSError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyOSError;
  s.os_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyFileNotFoundError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyFileNotFoundError;
  s.file_not_found_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyFileExistsError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyFileExistsError;
  s.file_exists_error = e;
  return s;
}

PyExcTypeUnion make_slot(const PyAssertionError& e)
{
  PyExcTypeUnion s;
  s.kind = ExcKind::PyAssertionError;
  s.assertion_error = e;
  return s;
}

} // namespace

void PyExceptionGroup::split_for_except_star(
    const ExcKind* kinds,
    PyInt kind_count,
    PyExceptionGroup& matched,
    PyExceptionGroup& rest) const
{
  matched.clear();
  rest.clear();
  for (PyInt i = 0; i < slots_len_; ++i)
  {
    const PyExcTypeUnion& slot = slots_[i];
    bool hit = false;
    for (PyInt k = 0; k < kind_count; ++k)
    {
      if (exc_kind_is_instance(slot.kind, kinds[k]))
      {
        hit = true;
        break;
      }
    }
    if (hit)
    {
      matched.slots_[matched.slots_len_] = slot;
      matched.slots_len_ += 1;
    }
    else
    {
      rest.slots_[rest.slots_len_] = slot;
      rest.slots_len_ += 1;
    }
  }
}

PyInt PyExceptionGroup::__len__() const
{
  return slots_len_;
}

void PyExceptionGroup::clear()
{
  slots_len_ = 0;
}

void PyExceptionGroup::push_slot_impl(const PyExcTypeUnion& slot)
{
  if (slots_len_ < kMaxSlots)
  {
    slots_[slots_len_] = slot;
    slots_len_ += 1;
  }
}

void PyExceptionGroup::copyFrom(PyExceptionGroup other)
{
  slots_len_ = other.slots_len_;
  for (PyInt i = 0; i < other.slots_len_; ++i)
  {
    slots_[i] = other.slots_[i];
  }
}

void PyExceptionGroup::append(const PyStopIteration& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyTypeError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyKeyError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyIndexError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyValueError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyStatisticsError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyLinAlgError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyRuntimeError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyOSError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyFileNotFoundError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyFileExistsError& e)
{
  push_slot_impl(make_slot(e));
}

void PyExceptionGroup::append(const PyAssertionError& e)
{
  push_slot_impl(make_slot(e));
}

PyBool PyExceptionGroup::__bool__() const
{
  return slots_len_ > 0;
}

void exception_group_split_except_star(
    const PyExceptionGroup& src,
    const ExcKind* kinds,
    PyInt kind_count,
    PyExceptionGroup& matched,
    PyExceptionGroup& rest)
{
  src.split_for_except_star(kinds, kind_count, matched, rest);
}

void throw_exception_group_propagate(const PyExceptionGroup& g)
{
  if (!static_cast<PyBool>(g))
  {
    return;
  }
  throw g;
}

PyExceptionGroup exception_group_from_single(const PyStopIteration& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyTypeError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyKeyError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyIndexError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyValueError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyStatisticsError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyLinAlgError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyRuntimeError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyOSError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyFileNotFoundError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyFileExistsError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

PyExceptionGroup exception_group_from_single(const PyAssertionError& e)
{
  PyExceptionGroup g;
  g.append(e);
  return g;
}

}}}
