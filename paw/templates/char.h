
#include <cstdint>

/// Unicode 码点（与 Python ``char`` 注解对应；非 C++ 单字节 ``char``）。
/// 使用独立 struct，避免 MSVC 上 ``PyInt``（``int``）与 ``int32_t`` 别名导致 ``PyStr(PyInt)`` / ``repr`` / ``format`` 重载冲突。
struct PyChar {
  int32_t value;
  explicit PyChar() : value(0) {}
  explicit PyChar(int32_t v) : value(v) {}
  operator int32_t() const { return value; }
};

inline bool operator==(PyChar a, PyChar b) { return a.value == b.value; }
inline bool operator!=(PyChar a, PyChar b) { return a.value != b.value; }

/// 仅 ``int32_t`` 一侧重载：MSVC 上 ``int`` 与 ``int32_t`` 为同一类型，双重重载会 C2084。
inline PyChar operator+(PyChar c, int32_t d) { return PyChar(c.value + d); }
inline PyChar operator-(PyChar c, int32_t d) { return PyChar(c.value - d); }
inline PyChar operator<<(PyChar c, int32_t d) { return PyChar(c.value << d); }
inline PyChar operator>>(PyChar c, int32_t d) { return PyChar(c.value >> d); }
inline PyChar operator&(PyChar c, int32_t d) { return PyChar(c.value & d); }
inline PyChar operator|(PyChar c, int32_t d) { return PyChar(c.value | d); }

/// 将码点截断为单字节（供 C API / ``char*`` 缓冲；非 UTF-8 编码）
inline char pychar_to_byte(PyChar c) { return (char)(unsigned char)c.value; }
