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

DUNDER_METHODS = frozenset({
  "__init__", "__del__", "__len__", "__getitem__", "__setitem__",
  "__iter__", "__next__", "__contains__", "__bool__", "__str__",
  "__add__", "__sub__", "__mul__", "__rmul__", "__truediv__", "__floordiv__",
  "__mod__", "__neg__", "__pos__", "__copy__", "__move__", "__cmp__",
})
