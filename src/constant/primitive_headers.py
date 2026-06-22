"""标量 / 标记 C++ 类型 → ``#include`` 路径（相对 ``generated/runtime``）。"""

PRIMITIVE_HEADER_MAP: dict[str, str] = {
  "PyInt": "py2cpp/py_types.h",
  "PyInt64": "py2cpp/py_types.h",
  "PyUInt": "py2cpp/py_types.h",
  "PyUInt64": "py2cpp/py_types.h",
  "PyUPtr": "py2cpp/py_types.h",
  "PyFloat": "py2cpp/py_types.h",
  "PyFloat64": "py2cpp/py_types.h",
  "PyBool": "py2cpp/py_types.h",
  "PyChar": "py2cpp/char.h",
  "PyByte": "py2cpp/byte.h",
  "c_str": "py2cpp/c_str.h",
}
