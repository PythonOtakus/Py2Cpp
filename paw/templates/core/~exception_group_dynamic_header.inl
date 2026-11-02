PY2CPP_IGNORE
#include "py2cpp/core/exceptions.h"
#define ctx_AppendDecls
class PyExceptionGroup {
public:
PY2CPP_END

explicit PyExceptionGroup() : slots_len_(0) { }
void split_for_except_star(
    const PyExcTypeUnion::Enum* kinds,
    PyInt kind_count,
    PyExceptionGroup& matched,
    PyExceptionGroup& rest) const;

PY2CPP_ECHO(ctx_AppendDecls)

private:
static const PyInt kMaxSlots = 8;
PyExcTypeUnion slots_[8];
PyInt slots_len_;
void push_slot_impl(const PyExcTypeUnion& slot);

PY2CPP_IGNORE
};
PY2CPP_END
