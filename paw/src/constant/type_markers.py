"""包根类型标记类名（``py2cpp/__init__.py`` 中声明、非普通用户类）。"""

TYPE_MARKER_CLASSES: frozenset[str] = frozenset({
  "char", "byte", "utf8ptr", "utf16ptr", "Pointer", "Function", "Callable", "GeneratorType", "CoroutineType", "Self", "Super",
  "staticproperty", "const", "optional", "ref", "lazy", "thread_local",
  "int16", "int64", "uint16", "uint", "uint64", "uintptr", "float64",
})
