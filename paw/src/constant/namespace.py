"""C++ 命名空间路径段映射。"""

INIT_SEGMENT = "__init__"

MODULES_WITHOUT_CPP_NAMESPACE_REL: frozenset[str] = frozenset({
  "util/tuple",
  "util/stack_array",
  "core/delegate",
  "core/generator",
  "core/coroutine",
  "core/refcount",
  "core/proxy",
  "weak/ref",
  "util/span",
})

BUILTIN_NAMESPACE_SEGMENT_OVERRIDES: dict[str, str] = {
  "long": "py_long",
  "set": "py_set",
  "environ": "py_environ",
  "popen": "py_popen",
}
