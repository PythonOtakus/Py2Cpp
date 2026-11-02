"""标量 / 标记 C++ 类型 → ``#include`` 路径（相对 ``generated/runtime``）。"""

PRIMITIVE_HEADER_MAP: dict[str, str] = {
  "PyInt": "paw/py_types.h",
  "PyInt16": "paw/py_types.h",
  "PyInt64": "paw/py_types.h",
  "PyUInt16": "paw/py_types.h",
  "PyUInt": "paw/py_types.h",
  "PyUInt64": "paw/py_types.h",
  "PyUIntPtr": "paw/py_types.h",
  "PyFloat": "paw/py_types.h",
  "PyFloat64": "paw/py_types.h",
  "PyBool": "paw/py_types.h",
  "PyChar": "paw/char.h",
  "PyByte": "paw/byte.h",
  "PyUtf8Ptr": "paw/c_str.h",
  "PyUtf16Ptr": "paw/c_str.h",
}
