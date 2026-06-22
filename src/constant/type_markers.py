"""包根类型标记类名（``py2cpp/__init__.py`` 中声明、非普通用户类）。"""

TYPE_MARKER_CLASSES: frozenset[str] = frozenset({
  "char", "byte", "c_str", "Pointer", "Function", "Callable", "Generator", "Coroutine", "Self", "Super",
  "staticproperty", "const", "optional", "ref", "lazy",
  "int64", "uint", "uint64", "uintptr", "float64",
})
