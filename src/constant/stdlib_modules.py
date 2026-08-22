"""标准库模块路径字面量表（相对 ``py2cpp/``）。"""

STDLIB_SKIP_REL_PATHS: frozenset[str] = frozenset({
  "reflect",
  "reflect/mixin",
})

STDLIB_SKIP_PREFIXES: frozenset[str] = frozenset({
  "test/",
})

STDLIB_SKIP_DOMAIN_PACKAGE_INITS: frozenset[str] = frozenset({
  "alg",
  "design",
  "core",
  "numeric",
  "serde",
  "spatial",
  "text",
  "util",
  "weak",
  "ui/flow",
})

UMBRELLA_PREFIX_TIERS: tuple[str, ...] = (
  "system/",
  "core/",
  "util/",
  "text/",
  "io/",
  "math/",
  "numeric/",
  "spatial/",
  "weak/",
  "alg/",
  "design/",
  "serde/",
  "concur/",
  "ui/",
)

UMBRELLA_PRIORITY_MODULES: tuple[str, ...] = (
  "io/path",
  "serde/json",
  "serde/yaml",
  "alg/protocols",
  "console/exceptions",
  "console/parse",
  "console/render",
  "console/popen",
  "console/task",
  "ui/meta",
  "ui/style",
  "ui/events",
  "ui/app",
  "ui/widget",
  "ui/window",
  "ui/canvas",
  "ui/menu",
  "ui/input",
  "ui/file_dialog",
  "ui/tooltip",
  "ui/layout",
  "ui/panel",
  "ui/flow/meta",
  "ui/flow/model",
  "ui/flow/serialize",
  "ui/flow/history",
  "ui/flow/catalog",
  "ui/flow/builtins",
  "ui/flow/runtime",
  "ui/flow/layout",
  "ui/flow/style",
  "ui/flow/canvas",
  "ui/flow/palette",
  "ui/flow/shell",
  "ui/flow/panel",
)

UMBRELLA_MSVC_COMPAT_BEFORE_MODULE = "system/datetime"

# Win32 宏与 Py2Cpp 符号冲突；万能头 ``minimal.h`` 在 include 前 / ``datetime`` 前 /
# ``io`` late（path 等，UI 之后）前 / 末尾各 ``#undef`` 一轮。
UMBRELLA_MSVC_UNDEF_MACROS_EARLY: tuple[str, ...] = (
  "Yield",
  "Return",
)

UMBRELLA_MSVC_UNDEF_MACROS: tuple[str, ...] = (
  "isascii",
  "parent",
  "suffix",
  "environ",
  "date",
  "time",
  "hour",
  "minute",
  "second",
  "min",
  "max",
  "unlink",
  "remove",
  "rename",
  "replace",
  # rpcndr.h：#define small char（变量名 small 会被展开）；勿 undef far/near（会弄坏 Win 头）
  "small",
  # sys/stat.h / crt：Path.stat() 方法名与宏冲突（UI 拉入 windows.h 后）
  "stat",
  # sys/stat.h：``S_IFCHR`` 等为 ``0x2000`` 一类宏，``file::S_IFCHR`` 会变成 ``file::0x2000``（C2589）
  "S_IFMT",
  "S_IFDIR",
  "S_IFCHR",
  "S_IFBLK",
  "S_IFREG",
  "S_IFIFO",
  "S_IFLNK",
  "S_IFSOCK",
  # stdio.h：``stdin``/``stdout``/``stderr`` 为宏（MSVC → ``__acrt_iob_func``）
  "stdin",
  "stdout",
  "stderr",
  # stdio.h：``popen`` → ``_popen``，会弄坏 ``console::popen`` 命名空间与 ``Console.popen``
  "popen",
  "Yield",
  "Return",
)

UMBRELLA_IO_LATE_IF_PRESENT: tuple[str, ...] = ()

STR_POST_CLASS_MODULES: frozenset[str] = frozenset({
  "text/bytes",
  "util/list",
  "util/dict",
  "util/tuple",
})

BYTES_POST_CLASS_MODULES: frozenset[str] = frozenset({
  "util/dict",
})

PYSTR_FORWARD_ONLY_MODULES: frozenset[str] = frozenset({
  "util/list",
  "util/dict",
  "util/deque",
  "text/bytes",
  "util/tuple",
  "util/set",
  "core/iter_result",
  "core/optional",
  "core/exceptions",
})

HEADER_SKIP_OPERATORS_BEFORE_INL_REL: frozenset[str] = frozenset({
  "util/tuple",
  "text/str",
  "core/protocols",
  "util/protocols",
  "numeric/protocols",
  "core/delegate",
  "core/refcount",
  "weak/ref",
  "builtins",
})

HEADER_INL_BEFORE_NS_CLOSE_PKG: frozenset[str] = frozenset({"py2cpp"})

JSON_API_MODULE_REL = "serde/json"
JSON_API_EXTRA_HEADER_INCLUDE_RELS: tuple[str, ...] = ("io", "io/path")

IO_PATH_MODULE_REL = "io/path"
SYSTEM_DATETIME_MODULE_REL = "system/datetime"
PROTOCOL_TRAITS_MODULE_REL = "core/protocols"

PROTOCOL_TRAITS_SOURCE_MODULES: tuple[str, ...] = (
  "util/protocols",
  "numeric/protocols",
  "core/protocols",
)

HEADER_TAIL_SKIP_UMBRELLA_REL: frozenset[str] = frozenset({
  "core/protocols",
  "util/protocols",
  "numeric/protocols",
  "core/iter_result",
  "text/str",
})

INL_SKIP_UMBRELLA_REL: frozenset[str] = frozenset({
  "text/str",
  "builtins",
  "core/iter_result",
})

INL_SKIP_OPERATORS_H_REL: frozenset[str] = frozenset({
  "core/protocols",
  "util/protocols",
  "numeric/protocols",
  "text/str",
})

INL_EXTRA_OPERATORS_INL_REL: frozenset[str] = frozenset({
  "util/list",
  "util/dict",
  "util/set",
  "util/deque",
})

INL_EXTRA_STDINCLUDES_REL: dict[str, tuple[str, ...]] = {
  "concur/task": ("core/exceptions",),
  "core/exceptions": ("text/str",),
}

MODULE_INL_PY_STR_TO_CBUF_REL = "text/str"

PKG_ROOT_FRONT_SKIP_RELS: frozenset[str] = frozenset({
  "text/str",
  "core/protocols",
  "util/protocols",
  "numeric/protocols",
})

SLICE_FRONT_MODULES_REL: frozenset[str] = frozenset({
  "util/span",
  "text/str",
})

STDLIB_CODEGEN_MODULES: dict[str, str] = {
  "util/tuple": "tuple",
  "util/stack_array": "StackArray",
  "core/delegate": "delegate",
  "core/generator": "generator",
  "core/coroutine": "coroutine",
  "core/refcount": "refcount",
  "core/proxy": "proxy",
  "weak/ref": "weakref",
}
