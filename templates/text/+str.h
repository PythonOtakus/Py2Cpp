PY2CPP_IGNORE
#include "py2cpp/text/str.h"
#include "py2cpp/util/tuple.h"

namespace py2cpp
{
namespace text
{
namespace str
{

class PyStr
{
PY2CPP_END

PY2CPP_INJECT_CLASS(PyStr)
  /// ``_sub`` 等临时 ``PyArray<PyChar>`` 按值接管（``str(char[:])`` 左值走 ``&`` 重载）。
  explicit PyStr(PY2CPP_TYPE(PyArray)<PyChar, 0>&& data);
PY2CPP_END

PY2CPP_INJECT_CLASS(PyStr)
private:
  static PY2CPP_TYPE(PyStr) _str_unescape_braces(utf8ptr fmt);
  static PY2CPP_TYPE(PyStr) _str_format_substitute(utf8ptr fmt, const PY2CPP_TYPE(PyStr)* parts, int n);
public:
  /// ``{{}}`` 占位（f-string / ``str.format``）；实参须为 ``PyStr``（可变参数模板，个数与 ``sizeof...(Args)`` 一致）。
  template<typename... Args>
  static PY2CPP_TYPE(PyStr) format(utf8ptr fmt, Args... args)
  {
    static_assert(sizeof...(Args) <= 32, "PyStr::format: at most 32 placeholders");
    if (sizeof...(Args) == 0)
    {
      return _str_unescape_braces(fmt);
    }
    const PY2CPP_TYPE(PyStr) parts[] = { args... };
    return _str_format_substitute(fmt, parts, (int)sizeof...(Args));
  }
  /// ``fprintf`` 变参：``PyStr`` → 栈上 C 缓冲（``.data`` 作 ``char*``）。
  struct PrintfArg
  {
    char data[512];
    explicit PrintfArg(const PY2CPP_TYPE(PyStr)& s);
  };
  static PY2CPP_TYPE(PyStr) percent_format(utf8ptr fmt, ...);
  /// 仅 ``PyTuple<...>``（``str %`` → ``::__mod__(fmt, makeTuple(...))``）；无 ``T0`` 非元组重载。
  template<typename... Args>
  PY2CPP_TYPE(PyStr) __mod__(const PyTuple<Args...>& other) const;
PY2CPP_END

PY2CPP_IGNORE
};

} // namespace str
} // namespace text
} // namespace py2cpp
PY2CPP_END
