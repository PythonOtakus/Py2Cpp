PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#define ctx_AppendDecls
class ExceptionGroup {
public:
PY2CPP_END

explicit ExceptionGroup() : slots_len_(0) { }
void split_for_except_star(
    const ExcSlot::Enum* kinds,
    PyInt kind_count,
    ExceptionGroup& matched,
    ExceptionGroup& rest) const;

PY2CPP_ECHO(ctx_AppendDecls)

private:
static const PyInt kMaxSlots = 8;
ExcSlot slots_[8];
PyInt slots_len_;
void push_slot_impl(const ExcSlot& slot);

PY2CPP_IGNORE
};
PY2CPP_END
