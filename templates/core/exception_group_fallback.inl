PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
using namespace py2cpp::core::exceptions;
PY2CPP_END

namespace py2cpp {
namespace core {
namespace exceptions {

using ExcKind = ExceptionGroup::ExcKind;
using ExcSlot = ExceptionGroup::ExcSlot;

bool exc_kind_is_instance(ExcKind slot, ExcKind match)
{
  if (slot == match)
  {
    return true;
  }
  if (match == ExcKind::ValueError)
  {
    return slot == ExcKind::StatisticsError
        || slot == ExcKind::LinAlgError;
  }
  if (match == ExcKind::OSError)
  {
    return slot == ExcKind::FileNotFoundError
        || slot == ExcKind::FileExistsError;
  }
  return false;
}

namespace {

ExcSlot make_slot(const StopIteration& e)
{
  ExcSlot s;
  s.kind = ExcKind::StopIteration;
  s.stop_iteration = e;
  return s;
}

ExcSlot make_slot(const TypeError& e)
{
  ExcSlot s;
  s.kind = ExcKind::TypeError;
  s.type_error = e;
  return s;
}

ExcSlot make_slot(const KeyError& e)
{
  ExcSlot s;
  s.kind = ExcKind::KeyError;
  s.key_error = e;
  return s;
}

ExcSlot make_slot(const IndexError& e)
{
  ExcSlot s;
  s.kind = ExcKind::IndexError;
  s.index_error = e;
  return s;
}

ExcSlot make_slot(const ValueError& e)
{
  ExcSlot s;
  s.kind = ExcKind::ValueError;
  s.value_error = e;
  return s;
}

ExcSlot make_slot(const StatisticsError& e)
{
  ExcSlot s;
  s.kind = ExcKind::StatisticsError;
  s.statistics_error = e;
  return s;
}

ExcSlot make_slot(const LinAlgError& e)
{
  ExcSlot s;
  s.kind = ExcKind::LinAlgError;
  s.linalg_error = e;
  return s;
}

ExcSlot make_slot(const RuntimeError& e)
{
  ExcSlot s;
  s.kind = ExcKind::RuntimeError;
  s.runtime_error = e;
  return s;
}

ExcSlot make_slot(const OSError& e)
{
  ExcSlot s;
  s.kind = ExcKind::OSError;
  s.os_error = e;
  return s;
}

ExcSlot make_slot(const FileNotFoundError& e)
{
  ExcSlot s;
  s.kind = ExcKind::FileNotFoundError;
  s.file_not_found_error = e;
  return s;
}

ExcSlot make_slot(const FileExistsError& e)
{
  ExcSlot s;
  s.kind = ExcKind::FileExistsError;
  s.file_exists_error = e;
  return s;
}

ExcSlot make_slot(const AssertionError& e)
{
  ExcSlot s;
  s.kind = ExcKind::AssertionError;
  s.assertion_error = e;
  return s;
}

} // namespace

void ExceptionGroup::split_for_except_star(
    const ExcKind* kinds,
    PyInt kind_count,
    ExceptionGroup& matched,
    ExceptionGroup& rest) const
{
  matched.clear();
  rest.clear();
  for (PyInt i = 0; i < slots_len_; ++i)
  {
    const ExcSlot& slot = slots_[i];
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

PyInt ExceptionGroup::__len__() const
{
  return slots_len_;
}

void ExceptionGroup::clear()
{
  slots_len_ = 0;
}

void ExceptionGroup::push_slot_impl(const ExcSlot& slot)
{
  if (slots_len_ < kMaxSlots)
  {
    slots_[slots_len_] = slot;
    slots_len_ += 1;
  }
}

void ExceptionGroup::copy_from(ExceptionGroup other)
{
  slots_len_ = other.slots_len_;
  for (PyInt i = 0; i < other.slots_len_; ++i)
  {
    slots_[i] = other.slots_[i];
  }
}

void ExceptionGroup::append(const StopIteration& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const TypeError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const KeyError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const IndexError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const ValueError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const StatisticsError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const LinAlgError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const RuntimeError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const OSError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const FileNotFoundError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const FileExistsError& e)
{
  push_slot_impl(make_slot(e));
}

void ExceptionGroup::append(const AssertionError& e)
{
  push_slot_impl(make_slot(e));
}

PyBool ExceptionGroup::__bool__() const
{
  return slots_len_ > 0;
}

void exception_group_split_except_star(
    const ExceptionGroup& src,
    const ExcKind* kinds,
    PyInt kind_count,
    ExceptionGroup& matched,
    ExceptionGroup& rest)
{
  src.split_for_except_star(kinds, kind_count, matched, rest);
}

void throw_exception_group_propagate(const ExceptionGroup& g)
{
  if (!static_cast<PyBool>(g))
  {
    return;
  }
  throw g;
}

ExceptionGroup exception_group_from_single(const StopIteration& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const TypeError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const KeyError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const IndexError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const ValueError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const StatisticsError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const LinAlgError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const RuntimeError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const OSError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const FileNotFoundError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const FileExistsError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

ExceptionGroup exception_group_from_single(const AssertionError& e)
{
  ExceptionGroup g;
  g.append(e);
  return g;
}

}}}
