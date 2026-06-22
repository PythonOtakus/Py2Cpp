PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#define ctx_EnumGetter get___enum__
#define ctx_IsInstanceBody
#define ctx_AppendImpls
#define ctx_FromSingleImpls
PY2CPP_END

PY2CPP_BEGIN_SCOPE
bool exc_slot_enum_is_instance(ExcSlot::Enum slot, ExcSlot::Enum match)
{
PY2CPP_ECHO(ctx_IsInstanceBody)
}

void ExceptionGroup::split_for_except_star(
    const ExcSlot::Enum* kinds,
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
      if (exc_slot_enum_is_instance(slot.PY2CPP_ECHO(ctx_EnumGetter)(), kinds[k]))
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
    slots_[i].__copy__(other.slots_[i]);
  }
}

PY2CPP_ECHO(ctx_AppendImpls)

PyBool ExceptionGroup::__bool__() const
{
  return slots_len_ != 0;
}

void exception_group_split_except_star(
    const ExceptionGroup& src,
    const ExcSlot::Enum* kinds,
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

PY2CPP_ECHO(ctx_FromSingleImpls)
PY2CPP_END_SCOPE
