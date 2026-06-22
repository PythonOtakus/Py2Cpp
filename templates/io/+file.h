PY2CPP_IGNORE
#include "py2cpp/io/file.h"

namespace py2cpp
{
namespace io
{
namespace file
{

class ScandirIterator
{
PY2CPP_END

PY2CPP_INJECT_CLASS(ScandirIterator)
public:
  ScandirIterator(const ScandirIterator&) = delete;
  ScandirIterator& operator=(const ScandirIterator&) = delete;
  ScandirIterator(ScandirIterator&& other) noexcept;
  ScandirIterator& operator=(ScandirIterator&& other) noexcept;
PY2CPP_END

PY2CPP_IGNORE
};

} // namespace file
} // namespace io
} // namespace py2cpp
PY2CPP_END
