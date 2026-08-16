"""标准库逻辑模块路径（``py2cpp/util/list`` → ``#include`` / ``::`` 命名空间）。"""
from __future__ import annotations

from .paths import PY2CPP_ROOT
from .stdlib_discovery import STDLIB_REL_PATHS, STDLIB_REL_PATH_SET
from .stdlib_modules import STDLIB_SKIP_PREFIXES, STDLIB_SKIP_REL_PATHS

RUNTIME_PKG = "py2cpp"
RUNTIME_BUILTINS_MODULE = f"{RUNTIME_PKG}/builtins"
# ``operators.h`` 全局 ``len``/``iter``/…；``builtins`` 勿再生成 ``py2cpp::`` 同名桩
BUILTINS_OPERATORS_FUNCS: frozenset[str] = frozenset({
  "len",
  "iter",
  "next",
  "aiter",
  "anext",
  "reversed",
  "repr",
  "hash",
})
CORE_PKG = f"{RUNTIME_PKG}/core"
UTIL_PKG = f"{RUNTIME_PKG}/util"
TEXT_PKG = f"{RUNTIME_PKG}/text"
IO_PKG = f"{RUNTIME_PKG}/io"
IO_FILE_PKG = f"{RUNTIME_PKG}/io/file"
SYSTEM_PKG = f"{RUNTIME_PKG}/system"
CONCUR_PKG = f"{RUNTIME_PKG}/concur"
TEST_PKG = f"{RUNTIME_PKG}/test"
SERDE_PKG = f"{RUNTIME_PKG}/serde"
REFLECT_PKG = f"{RUNTIME_PKG}/reflect"

_STDLIB_REL_PATHS = STDLIB_REL_PATH_SET


def _on_demand_stdlib_py_exists(rel: str) -> bool:
  mod_py = PY2CPP_ROOT / f"{rel}.py"
  if mod_py.is_file():
    return True
  return (PY2CPP_ROOT / rel / "__init__.py").is_file()


def is_on_demand_stdlib_rel(rel: str) -> bool:
  """跳过 bootstrap 发现、但 ``py2cpp/`` 下仍有源文件的标准库路径。"""
  if rel in STDLIB_SKIP_REL_PATHS:
    return False
  if not any(rel.startswith(p) for p in STDLIB_SKIP_PREFIXES):
    return False
  return _on_demand_stdlib_py_exists(rel)


def list_on_demand_stdlib_rels() -> list[str]:
  """``STDLIB_SKIP_PREFIXES`` 下须 bootstrap 预生成的 on-demand 模块（如 ``test/unittest``）。"""
  found: set[str] = set()
  for prefix in STDLIB_SKIP_PREFIXES:
    root = PY2CPP_ROOT / prefix.rstrip("/")
    if not root.is_dir():
      continue
    for path in sorted(root.rglob("*.py")):
      if path.name == "__init__.py":
        rel = path.parent.relative_to(PY2CPP_ROOT).as_posix()
      else:
        rel = path.with_suffix("").relative_to(PY2CPP_ROOT).as_posix()
      if is_on_demand_stdlib_rel(rel):
        found.add(rel)
  return sorted(found)


def stdlib_rel_path(name: str) -> str:
  """``util/list`` 或 ``py2cpp/util/list`` → 相对 ``py2cpp/`` 的路径。"""
  rel = name
  if rel.startswith(f"{RUNTIME_PKG}/"):
    rel = rel[len(f"{RUNTIME_PKG}/") :]
  if rel not in _STDLIB_REL_PATHS:
    if is_on_demand_stdlib_rel(rel):
      return rel
    raise ValueError(
      f"stdlib module {name!r}: expected a path under py2cpp/ "
      f"(e.g. util/list)"
    )
  return rel


def stdlib_module_path(name: str) -> str:
  """→ ``py2cpp/util/list`` 等翻译模块路径。"""
  if name == RUNTIME_PKG:
    return RUNTIME_PKG
  rel = stdlib_rel_path(name)
  return f"{RUNTIME_PKG}/{rel}"


def stdlib_header_include(name: str, *, suffix: str = ".h") -> str:
  """``#include`` 路径（相对 ``generated/runtime`` 的 ``-I`` 根）。"""
  if name == RUNTIME_PKG:
    return f"{RUNTIME_PKG}{suffix}"
  return f"{stdlib_module_path(name)}{suffix}"


def stdlib_cpp_namespace(name: str) -> str:
  """``util/list`` → ``py2cpp::util::list``。"""
  return stdlib_module_path(name).replace("/", "::")


EXCEPTIONS_NS = f"{stdlib_cpp_namespace('core/exceptions')}"
STR_PYSTR = f"{stdlib_cpp_namespace('text/str')}::PyStr"


def cpp_exception_type(name: str = "Exception") -> str:
  """``Exception`` → ``…::PyException``。"""
  from .language import default_py_class_cpp_name

  return f"{EXCEPTIONS_NS}::{default_py_class_cpp_name(name)}"


def cpp_stdlib_class(mod_path: str, class_name: str) -> str:
  from .language import default_py_class_cpp_name

  # 异常等类名走默认 Py 前缀
  cpp = default_py_class_cpp_name(class_name)
  return f"{stdlib_cpp_namespace(mod_path)}::{cpp}"


def cpp_exception_ctor(name: str) -> str:
  return f"{cpp_exception_type(name)}()"


def stdlib_rel_from_import_segment(name: str) -> str | None:
  """``from py2cpp import io`` 等单段名 → 标准库相对路径；歧义或未知名返回 ``None``。"""
  if name in _STDLIB_REL_PATHS:
    return name
  matches = [p for p in STDLIB_REL_PATHS if p == name or p.endswith(f"/{name}")]
  if len(matches) == 1:
    return matches[0]
  return None


def resolve_stdlib_import_parts(parts: list[str]) -> str | None:
  """``['collections', 'list']`` / ``['list']`` → ``py2cpp/…``；域包 ``util`` 等返回 ``None``（由调用方拼路径）。"""
  if not parts:
    return RUNTIME_PKG
  if parts[0] == RUNTIME_PKG:
    parts = parts[1:]
  if not parts:
    return RUNTIME_PKG
  slash = "/".join(parts)
  if slash in _STDLIB_REL_PATHS:
    return stdlib_module_path(slash)
  if len(parts) == 1:
    rel = stdlib_rel_from_import_segment(parts[0])
    if rel is not None:
      return stdlib_module_path(rel)
  return None
