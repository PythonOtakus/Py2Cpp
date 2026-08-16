"""译器语言关键字、dunder、标量 Python 名 → C++ 类型。"""

RESERVED = frozenset({
  "class", "struct", "void", "int", "float", "double", "bool",
  "return", "new", "delete", "this", "true", "false", "nullptr",
})

CPP_KEYWORDS: frozenset[str] = frozenset({
  "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
  "bool", "break", "case", "catch", "char", "class", "compl", "const",
  "const_cast", "constexpr", "continue", "decltype", "default", "delete",
  "do", "double", "dynamic_cast", "else", "enum", "explicit", "export",
  "extern", "false", "float", "for", "friend", "goto", "if", "inline", "int",
  "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq",
  "nullptr", "operator", "or", "or_eq", "private", "protected", "public",
  "register", "reinterpret_cast", "return", "short", "signed", "sizeof",
  "static", "static_assert", "static_cast", "struct", "switch", "template",
  "this", "thread_local", "throw", "true", "try", "typedef", "typeid",
  "typename", "union", "unsigned", "using", "virtual", "void", "volatile",
  "wchar_t", "while", "xor", "xor_eq",
})

CPP_PARAM_RENAME: dict[str, str] = {
  "default": "default_value",
}

CPP_RENAME: dict[str, str] = {
  "int": "PyInt",
  "int64": "PyInt64",
  "uint": "PyUInt",
  "uint64": "PyUInt64",
  "uintptr": "PyUPtr",
  "float": "PyFloat",
  "float64": "PyFloat64",
  "bool": "PyBool",
  "char": "PyChar",
  "byte": "PyByte",
}


def default_py_class_cpp_name(name: str) -> str:
  """Python 类名 → 默认 C++ 名：``Py`` 前缀，前导 ``_`` 挪到 ``Py`` 前；小写首字母大写。

  - ``Handle`` → ``PyHandle``；``_Handle`` → ``_PyHandle``；``list`` → ``PyList``
  - 已是 ``Py``+大写 / ``Pyi…`` / ``pyi…`` 则不再加业务 ``Py``
  - ``Self`` 保持 ``Self``（协议探测 / typing，勿成 ``PySelf``）
  """
  if not name:
    return name
  if name == "Self":
    return "Self"
  n_us = 0
  while n_us < len(name) and name[n_us] == "_":
    n_us += 1
  body = name[n_us:]
  if not body:
    return name
  if body.startswith("Pyi") or body.startswith("pyi"):
    return name
  if body.startswith("Py") and len(body) > 2 and body[2].isupper():
    return ("_" * n_us) + body
  # 单字母形参（``T`` / ``U`` / ``E``）保持原样，勿成 ``PyT``
  if len(body) == 1:
    return ("_" * n_us) + body
  if body[0].islower():
    body = body[0].upper() + body[1:]
  return ("_" * n_us) + "Py" + body


DUNDER_METHODS = frozenset({
  "__init__", "__del__", "__len__", "__getitem__", "__setitem__",
  "__iter__", "__next__", "__contains__", "__bool__", "__str__",
  "__add__", "__sub__", "__mul__", "__rmul__", "__truediv__", "__floordiv__",
  "__mod__", "__neg__", "__pos__", "__copy__", "__move__", "__cmp__",
})
