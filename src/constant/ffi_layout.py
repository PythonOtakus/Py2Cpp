"""仓库根 ``ffi/**/*.pyi`` 与 Zeus 旁路 ``zeus/ffi/**/*.pyi`` 布局（第三方 C FFI 声明面）。

Python：``import ffi.windows`` / ``from ffi.sqlite.sqlite3 import …`` / ``from ffi.glfw.glfw3 import …``
内部 module_path：``ffi/windows``、``ffi/sqlite/sqlite3``、``ffi/glfw/glfw3``
生成物：``generated/runtime/ffi/…``（``#include "ffi/…"``；与 ``py2cpp/`` 并列）
C++ 命名空间：``ffi::…``（见 ``module_namespace``；不挂 ``py2cpp::``）

不进 ``STDLIB_REL_PATHS`` / ``minimal.h`` 默认 bulk；仅被 import 时参与翻译。
Zeus：``zeus\\ffi.bat`` 重生成 ``zeus/ffi/glfw``、``zeus/ffi/gl``（勿手改 AUTO-GENERATED）。
"""
from __future__ import annotations

from pathlib import Path

from .paths import _REPO_ROOT

FFI_PKG = "ffi"
FFI_ROOT = _REPO_ROOT / FFI_PKG
# Zeus 旁路：``zeus/ffi/**/*.pyi`` 与仓库根 ``ffi/`` 同 module_path（``ffi/glfw/glfw3``）
_ZEUS_FFI_ROOT = _REPO_ROOT / "zeus" / "ffi"

# module_path → 第三方 C 头（供 glue ``#include``；``None`` 表示暂不自动 glue）
_FFI_C_HEADER_BY_MODULE: dict[str, str] = {
  "ffi/sqlite/sqlite3": "sqlite3.h",
  "ffi/glfw/glfw3": "GLFW/glfw3.h",
  "ffi/gl/gl": "GL/gl.h",
}

# 生成 ``.inl`` 体的 C 符号白名单；缺省/``None`` = 该模块全部 ``@native``（慎用：回调签名易 C2664）
_FFI_GLUE_ALLOWLIST: dict[str, frozenset[str] | None] = {
  "ffi/sqlite/sqlite3": frozenset({
    "sqlite3_open",
    "sqlite3_close",
    "sqlite3_close_v2",
    "sqlite3_prepare_v2",
    "sqlite3_step",
    "sqlite3_finalize",
    "sqlite3_bind_int",
    "sqlite3_column_int",
    "sqlite3_get_autocommit",
    "sqlite3_exec",
    "sqlite3_free",
  }),
  # Zeus：.pyi 全量生成，glue 仅业务实际调用（回调/Pointer 签名勿全量转发）
  "ffi/glfw/glfw3": frozenset({
    "glfwInit",
    "glfwTerminate",
    "glfwWindowHint",
    "glfwCreateWindow",
    "glfwDestroyWindow",
    "glfwMakeContextCurrent",
    "glfwSwapBuffers",
    "glfwPollEvents",
    "glfwWindowShouldClose",
    "glfwGetKey",
    "glfwGetMouseButton",
    "glfwGetCursorPos",
    "glfwSetWindowPos",
    "glfwSetWindowSize",
    "glfwShowWindow",
    "glfwHideWindow",
  }),
  "ffi/gl/gl": frozenset({
    "glClearColor",
    "glClear",
    "glViewport",
    "glEnable",
    "glMatrixMode",
    "glLoadIdentity",
    "glFrustum",
    "glTranslatef",
    "glRotatef",
    "glPushMatrix",
    "glPopMatrix",
    "glBegin",
    "glEnd",
    "glColor3d",
    "glVertex3d",
  }),
}


def is_ffi_module_path(module_path: str) -> bool:
  norm = module_path.replace("\\", "/").strip("/")
  return norm == FFI_PKG or norm.startswith(f"{FFI_PKG}/")


def ffi_import_parts_to_module_path(parts: list[str]) -> str | None:
  """``['ffi','windows']`` → ``ffi/windows``；非 ``ffi`` 前缀返回 ``None``。"""
  if not parts or parts[0] != FFI_PKG:
    return None
  return "/".join(parts)


def find_ffi_source_file(module_path: str, *, project_root: Path | None = None) -> Path | None:
  """``ffi/windows`` → 仓库根 ``ffi/windows.pyi``；其次 ``zeus/ffi/…``。

  ``project_root`` 参数保留兼容调用方，忽略。
  """
  _ = project_root
  if not is_ffi_module_path(module_path):
    return None
  rel = module_path.replace("\\", "/").strip("/")
  for root in (FFI_ROOT, _ZEUS_FFI_ROOT):
    hit = _find_ffi_under_root(root, rel)
    if hit is not None:
      return hit
  return None


def _find_ffi_under_root(root: Path, rel: str) -> Path | None:
  if rel == FFI_PKG:
    for suf in (".pyi", ".py"):
      cand = root / f"__init__{suf}"
      if cand.is_file():
        return cand
    return None
  rest = rel[len(FFI_PKG) + 1 :]
  for suf in (".pyi", ".py"):
    cand = root / f"{rest}{suf}"
    if cand.is_file():
      return cand
  init_pyi = root / rest / "__init__.pyi"
  if init_pyi.is_file():
    return init_pyi
  init_py = root / rest / "__init__.py"
  if init_py.is_file():
    return init_py
  return None


def ffi_runtime_module_path(module_path: str) -> str:
  """``ffi/windows`` → ``ffi/windows``（生成物相对 ``generated/runtime``，与 ``py2cpp/`` 并列）。"""
  return module_path.replace("\\", "/").strip("/")


def ffi_header_include(module_path: str) -> str:
  """``#include`` 路径（相对 ``-I generated/runtime``）。"""
  return f"{ffi_runtime_module_path(module_path)}.h"


def ffi_c_header_include(module_path: str) -> str | None:
  """自动 glue 时 ``#include`` 的 C 头名；无映射则不生成 glue。

  glue 须用 ``#include <sqlite3.h>``（尖括号），避免与同目录生成的
  ``ffi/sqlite/sqlite3.h`` 在引号 include 下自包含（guard 已定义则 C API 被跳过）。
  """
  norm = module_path.replace("\\", "/").strip("/")
  return _FFI_C_HEADER_BY_MODULE.get(norm)


def ffi_glue_allowlist(module_path: str) -> frozenset[str] | None:
  """``None`` = 全部 ``@native``；否则仅集合内 C 名生成 ``.inl`` 体。"""
  norm = module_path.replace("\\", "/").strip("/")
  if norm not in _FFI_GLUE_ALLOWLIST:
    return frozenset()
  return _FFI_GLUE_ALLOWLIST[norm]


def ffi_cpp_namespace_segment(segment: str) -> str:
  """FFI 路径段 → C++ 命名空间标识（与路径段一致）。"""
  return segment


def ffi_pyi_prefix() -> str:
  return "Pyi"


def ffi_c_struct_using_target(info: object) -> str:
  """``using PyiSqlite3 = ::sqlite3`` 右侧：全局 C typedef/标签名。"""
  tag = getattr(info, "cpp_rename", None) or ""
  if not tag:
    name = getattr(info, "name", "") or ""
    pref = ffi_pyi_prefix()
    legacy = "Pyi_"
    if name.startswith(legacy):
      tag = name[len(legacy):]
    elif name.startswith(pref) and len(name) > len(pref) and name[len(pref)].isupper():
      # 无 @native_name 时无法可靠还原；保留启发式剥前缀
      tag = name[len(pref):]
    else:
      tag = name
  return f"::{tag}"


def is_ffi_c_struct_class(info: object) -> bool:
  """``ClassInfo``：FFI 模块内 ``@native`` 类视为 C struct/enum 声明面（``using`` 别名，无新定义）。"""
  module_path = getattr(info, "module_path", "") or ""
  return bool(getattr(info, "is_native", False) and is_ffi_module_path(module_path))


# 兼容旧名（已废弃 *_h 句柄模型）
_OPAQUE_PY_SUFFIX = "_h"


def ffi_opaque_py_name(c_tag: str) -> str:
  """已废弃：历史 ``*_h`` 句柄名。新代码直接用结构体类名。"""
  if c_tag.endswith(_OPAQUE_PY_SUFFIX):
    return c_tag
  return f"{c_tag}{_OPAQUE_PY_SUFFIX}"


def ffi_opaque_c_tag(py_name: str) -> str:
  """``ffi_opaque_py_name`` 的逆；亦接受无后缀的结构体类名。"""
  if py_name.endswith(_OPAQUE_PY_SUFFIX) and len(py_name) > len(_OPAQUE_PY_SUFFIX):
    return py_name[: -len(_OPAQUE_PY_SUFFIX)]
  return py_name


def ffi_source_note(module_path: str, source_path: Path | None = None) -> str:
  if source_path is not None:
    try:
      return source_path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except ValueError:
      return str(source_path)
  p = find_ffi_source_file(module_path)
  if p is not None:
    try:
      return p.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except ValueError:
      return str(p)
  return f"{module_path}.pyi"
