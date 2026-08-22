"""``generated/runtime`` 与各模块 ``.h`` / ``.inl`` 写盘（自 ``translator.py`` 拆出）。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..analysis.ir import ModuleAnalysis, codegen_file_header_lines
from ..analysis.module_namespace import (
  merge_consecutive_namespace_blocks,
  namespace_qualifier_for_module,
  splice_before_innermost_namespace_close,
  using_namespace_line,
  using_symbol_line,
)
from ..codegen.expand_py2cpp_template import expand_template
from ..codegen.stdlib_mirror_codegen import expand_whole_file_template
from ..codegen.umbrella_gen import build_py2cpp_umbrella_header
from ..codegen.write_if_changed import write_text_if_changed
from ..constant.ffi_layout import ffi_runtime_module_path, ffi_source_note
from ..constant.stdlib_layout import RUNTIME_PKG, RUNTIME_BUILTINS_MODULE, stdlib_header_include, stdlib_module_path
from ..codegen.stdlib_mirror_codegen import write_stdlib_codegen_header, write_stdlib_codegen_inl
from ..constant.runtime_libs import (
  LIBRARY_TU_MACRO,
  header_only_mode,
  is_library_module,
  library_module_paths,
  wrap_inl_include_for_header,
)
from ..constant.stdlib_discovery import STDLIB_REL_PATHS
from .layout_config_emit import (
  _HEADER_INL_BEFORE_NS_CLOSE,
  _HEADER_SKIP_INL_IN_MODULE_H,
  _HEADER_SKIP_OPERATORS_BEFORE_INL,
  _HEADER_TAIL_SKIP_UMBRELLA,
  _INL_EXTRA_OPERATORS_INL,
  _INL_SKIP_OPERATORS_H,
  _INL_SKIP_UMBRELLA,
  _JSON_API_EXTRA_HEADER_INCLUDES,
  _JSON_API_MODULE,
  _PROTOCOL_TRAITS_MODULE,
  PROTOCOL_TRAITS_GUARD,
  PROTOCOL_TRAITS_HEADER,
  PROTOCOL_TRAITS_SOURCE_MODULES,
  PROTOCOL_TRAITS_SOURCE_MODULE_PATHS,
  RUNTIME_CPP,
  RUNTIME_PREFIX,
  UMBRELLA_HEADER,
  module_inl_extra_include_lines,
)

if TYPE_CHECKING:
  from ..translator import Translator

_ITER_RESULT_MODULE = stdlib_module_path("core/iter_result")


def module_path_to_guard(module_path: str) -> str:
  parts: list[str] = []
  for seg in module_path.replace("\\", "/").strip("/").split("/"):
    if not seg:
      continue
    name = seg.removesuffix(".py")
    if name.startswith("_"):
      name = name[1:]
    parts.append(name.upper())
  return "_".join(parts) + "_H" if parts else "PY2CPP_H"


def include_line_to_header_path(line: str) -> str | None:
  s = line.strip()
  if s.startswith('#include "') and s.endswith('"'):
    return s[len('#include "') : -1]
  return None


def format_include_line(inc: str) -> str:
  if len(inc) >= 2 and inc[0] == "<" and inc[-1] == ">":
    return f"#include {inc}"
  return f'#include "{inc}"'


def insert_inl_before_namespace_close(
  body: list[str], module_path: str, insert_lines: list[str]
) -> list[str]:
  if not insert_lines:
    return body
  q = namespace_qualifier_for_module(module_path)
  segs = q.split("::") if q else module_path_namespace_segments(module_path)
  if not segs:
    return [*body, *insert_lines]
  target = f"}} // namespace {segs[-1]}"
  for i in range(len(body) - 1, -1, -1):
    if body[i].strip() == target:
      return [*body[:i], *insert_lines, "", *body[i:]]
  return [*body, *insert_lines]


def split_protocol_header_lines(lines: list[str]) -> tuple[list[str], list[str]]:
  """traits（``#include <type_traits>`` … SFINAE）与模块 doc/namespace 分界。"""
  for i, line in enumerate(lines):
    if line.startswith("/// "):
      return lines[:i], lines[i:]
  return lines, []


def _strip_leading_protocol_traits_preamble(lines: list[str]) -> list[str]:
  """合并多模块 traits 时去掉重复的 ``#include`` / ``_Compare_ops_no_pybool_only``。"""
  i = 0
  n = len(lines)
  while i < n:
    s = lines[i].strip()
    if s in ("#include <type_traits>", "#include <utility>"):
      i += 1
      continue
    if s == "":
      i += 1
      continue
    if s.startswith("template<typename U") and i + 1 < n and "_Compare_ops_no_pybool_only" in lines[i + 1]:
      while i < n and not lines[i].startswith("/* @protocol"):
        i += 1
      continue
    break
  return lines[i:]


def _split_core_protocol_traits_for_traits_header(lines: list[str]) -> tuple[list[str], list[str]]:
  """``StringFormatType`` 探测 ``PyStr``，留 ``core/protocols.h`` 避免 ``protocol_traits.h`` MSVC ICE。"""
  for i, line in enumerate(lines):
    if line.startswith("/* @protocol StringFormatType"):
      return lines[:i], lines[i:]
  return lines, []


def runtime_cpp_using_lines(tr: Translator) -> list[str]:
  out: list[str] = []
  for name in tr.stdlib_modules_for_umbrella:
    mp = stdlib_module_path(name)
    q = namespace_qualifier_for_module(mp)
    if q:
      out.append(using_namespace_line(q))
  return out


def stdlib_header_global_using_line(module_path: str) -> str | None:
  """``.h`` 在 namespace 闭合后导出模块短名。

  库 TU 定义 ``PY2CPP_LIBRARY_TU`` 时跳过 header-only ``.inl``，而短名
  ``using namespace py2cpp::util::dict`` 原先只写在 ``.inl``，会导致
  ``PyDict`` / ``PyList`` 在 ``types.h``、``protocol_erase_domain.h`` 中不可见。
  """
  if module_path.replace("\\", "/").strip("/") == RUNTIME_PKG:
    return None
  q = namespace_qualifier_for_module(module_path)
  if not q:
    return None
  return using_namespace_line(q)


def _module_has_non_template_inl_entities(tr: Translator, module_path: str) -> bool:
  """模块级函数会进 ``.inl`` 且非 ``inline``，多 TU 包含即 LNK2005（如 ``math.random.seed``）。"""
  for mp, _func in getattr(tr, "module_functions", ()):
    if mp == module_path:
      return True
  return False


def _module_template_inl_ok_in_library_tu(tr: Translator, module_path: str) -> bool:
  """仅当模块内**顶层**类全是模板、且无模块级函数时，库 TU 才拉 ``.inl``。

  含非模板顶层类的模块（如 ``Queue[T]`` + ``Thread``）整份 ``.inl`` 仍须跳过。
  嵌套 ``@variant``（``Optional.None_``）不算顶层，以免把纯模板 ADT 误标为混模块。
  ``Random[T]`` + 模块级 ``seed`` 同理：模板方法可多 TU，自由函数不行。
  """
  if _module_has_non_template_inl_entities(tr, module_path):
    return False
  seen = False
  for info in tr.classes.values():
    if info.module_path != module_path:
      continue
    if info.outer_class is not None:
      continue
    if info.is_protocol or info.is_mixin or info.is_annotation or info.is_descriptor:
      continue
    seen = True
    if not info.is_template():
      return False
  return seen


_BYTES_MODULE = stdlib_module_path("text/bytes")
# ``bytes_from_literal`` 被其它模块 ``.h`` 的静态初始化调用；库 TU 跳过 ``bytes.inl``，须在头内可见。
_BYTES_FROM_LITERAL_LINES = [
  "      inline PyBytes bytes_from_literal(const unsigned char* data, PyInt n)",
  "      {",
  "        if (n <= 0)",
  "        {",
  "          PyArray<PyByte> empty(0);",
  "          return PyBytes(empty);",
  "        }",
  "        PyArray<PyByte> buf(n);",
  "        for (PyInt i = 0; i < n; ++i)",
  "        {",
  "          buf.__setitem__(i, PyByte(data[i]));",
  "        }",
  "        return PyBytes(buf);",
  "      }",
  "",
]


def write_primitive_type_headers(tr: Translator) -> None:
  note = f"{RUNTIME_PREFIX}/__init__.py"
  for rel, template_rel in (
    (f"{RUNTIME_PREFIX}/char", "char.h"),
    (f"{RUNTIME_PREFIX}/byte", "byte.h"),
    (f"{RUNTIME_PREFIX}/c_str", "c_str.h"),
    (f"{RUNTIME_PREFIX}/py_types", "py_types.h"),
    (f"{RUNTIME_PREFIX}/member_access", "member_access.h"),
  ):
    hpath = tr._stdlib_artifact_path(rel, ".h")
    write_text_if_changed(
      hpath,
      expand_whole_file_template(
        template_rel,
        tr.generated_at,
        {"source_note": note},
        apply_allman=template_rel != "member_access.h",
      ).strip(),
    )
  ops_rel = f"{RUNTIME_PREFIX}/operators"
  ops_h = tr._stdlib_artifact_path(ops_rel, ".h")
  write_text_if_changed(
    ops_h,
    expand_whole_file_template(
      "operators.h",
      tr.generated_at,
      {"source_note": note},
      apply_allman=True,
    ).strip(),
  )
  op_inl = tr._stdlib_artifact_path(ops_rel, ".inl")
  write_text_if_changed(
    op_inl,
    expand_whole_file_template(
      "operators.inl",
      tr.generated_at,
      {},
      apply_allman=True,
    ).strip(),
  )


def build_stdlib_cpp_lines(tr: Translator, *, merge_entry_runtime: bool) -> list[str]:
  lines = [
    *codegen_file_header_lines("标准库非模板实现汇总", tr.generated_at),
    "#include <stdio.h>",
    "#include <string.h>",
    "#include <math.h>",
    "#include <new>",
    "",
  ]
  lines.append(f'#include "{UMBRELLA_HEADER}"')
  lines.append("")
  for name in tr.stdlib_modules_for_umbrella or STDLIB_REL_PATHS:
    mp = stdlib_module_path(name)
    q = namespace_qualifier_for_module(mp)
    if q:
      lines.append(using_namespace_line(q))
  if tr.stdlib_modules_for_umbrella:
    lines.append("")
  for mp in tr.module_order:
    if not tr._is_stdlib_module(mp):
      continue
    chunk = tr.per_module_source_lines.get(mp, [])
    if chunk:
      lines.extend(merge_consecutive_namespace_blocks(chunk))
      lines.append("")
  if merge_entry_runtime and tr.source_lines:
    lines.extend(tr.source_lines)
  return lines


def write_protocol_traits_header(tr: Translator) -> None:
  # 仅 bootstrap 写共享 ``protocol_traits.h``；并行测例同时写会 Permission denied。
  if not tr._is_runtime_bootstrap():
    return
  traits: list[str] = []
  for idx, mod_rel in enumerate(PROTOCOL_TRAITS_SOURCE_MODULES):
    mod = stdlib_module_path(mod_rel)
    lines = tr.per_module_header_lines.get(mod, [])
    mod_traits, rest = split_protocol_header_lines(lines)
    if mod_rel == "core/protocols":
      mod_traits, core_tail = _split_core_protocol_traits_for_traits_header(mod_traits)
      if core_tail:
        rest = [
          "#include <type_traits>",
          "#include <utility>",
          "",
          *core_tail,
          *rest,
        ]
    if idx > 0:
      mod_traits = _strip_leading_protocol_traits_preamble(mod_traits)
    traits.extend(mod_traits)
    tr.per_module_header_lines[mod] = rest
  guard = PROTOCOL_TRAITS_GUARD
  hpath = tr._stdlib_artifact_path(_PROTOCOL_TRAITS_MODULE, ".h")
  traits_path = hpath.parent / "protocol_traits.h"
  write_text_if_changed(
    traits_path,
    "\n".join([
      *codegen_file_header_lines(
        ", ".join(f"{RUNTIME_PREFIX}/{m}.py" for m in PROTOCOL_TRAITS_SOURCE_MODULES),
        tr.generated_at,
      ),
      f"#ifndef {guard}",
      f"#define {guard}",
      "",
      *traits,
      f"#endif // {guard}",
      "",
    ]),
  )


def write_protocol_erase_header(tr: Translator) -> None:
  from ..codegen.protocol_erase_gen import (
    protocol_erase_domain_header_lines,
    protocol_erase_header_lines,
  )
  from ..constant.stdlib_layout import CORE_PKG

  hpath = tr.runtime_output_dir / CORE_PKG / "protocol_erase.h"
  write_text_if_changed(
    hpath,
    "\n".join(protocol_erase_header_lines(generated_at=tr.generated_at)),
  )
  domain_lines = protocol_erase_domain_header_lines(generated_at=tr.generated_at)
  if domain_lines:
    dpath = tr.runtime_output_dir / CORE_PKG / "protocol_erase_domain.h"
    write_text_if_changed(dpath, "\n".join(domain_lines))


def write_umbrella_header(tr: Translator) -> None:
  if not tr._is_runtime_bootstrap():
    return
  if not any(tr._is_stdlib_module(mp) for mp in tr.module_order):
    return
  write_primitive_type_headers(tr)
  write_protocol_erase_header(tr)
  rel = f"{RUNTIME_PREFIX}/minimal"
  guard = module_path_to_guard(rel)
  hpath = tr.runtime_output_dir / UMBRELLA_HEADER
  new_text = build_py2cpp_umbrella_header(
    guard,
    tr.generated_at,
    RUNTIME_PREFIX,
    tr.stdlib_modules_for_umbrella or STDLIB_REL_PATHS,
    debug=tr.debug,
  )
  write_text_if_changed(hpath, new_text)
  sync_runtime_cpp_usings(tr)


def sync_runtime_cpp_usings(tr: Translator) -> None:
  path = tr.runtime_output_dir / RUNTIME_CPP
  if not path.is_file() or not tr.stdlib_modules_for_umbrella:
    return
  lines = path.read_text(encoding="utf-8").splitlines()
  start = None
  end = None
  for i, line in enumerate(lines):
    if line.startswith("using namespace py2cpp::"):
      if start is None:
        start = i
      end = i + 1
    elif start is not None and not line.startswith("using namespace py2cpp::"):
      break
  if start is None:
    insert_at = None
    for i, line in enumerate(lines):
      if line == f'#include "{RUNTIME_PREFIX}/operators.inl"':
        insert_at = i + 1
        break
    if insert_at is None:
      return
    new_usings = runtime_cpp_using_lines(tr)
    lines[insert_at:insert_at] = [""] + new_usings + [""]
  else:
    lines[start:end] = runtime_cpp_using_lines(tr)
  write_text_if_changed(path, "\n".join(lines) + "\n")


def write_per_module_headers(tr: Translator) -> None:
  if tr.emit_module_filter is None:
    write_protocol_traits_header(tr)
  for module_path in tr.module_order:
    if not tr._should_emit_module(module_path):
      continue
    if module_path == tr.entry_module_path and not (
      tr._is_runtime_bootstrap() and module_path == RUNTIME_PKG
    ):
      if tr._is_ffi_module(module_path) and tr._can_write_ffi_artifact(module_path):
        pass
      elif not (
        tr._is_stdlib_module(module_path)
        and tr._can_write_stdlib_artifact(module_path)
      ):
        continue
    if tr._is_stdlib_module(module_path) and not tr._can_write_stdlib_artifact(module_path):
      continue
    if tr._is_ffi_module(module_path) and not tr._can_write_ffi_artifact(module_path):
      continue
    if write_stdlib_codegen_header(tr, module_path):
      continue
    lines = tr.per_module_header_lines.get(module_path, [])
    deferred = tr.per_module_deferred_header_lines.get(module_path, [])
    if deferred:
      lines = splice_before_innermost_namespace_close(lines, deferred)
    if module_path == _BYTES_MODULE:
      lines = splice_before_innermost_namespace_close(lines, _BYTES_FROM_LITERAL_LINES)
    guard = module_path_to_guard(module_path)
    if tr._is_ffi_module(module_path):
      hpath = tr._ffi_artifact_path(module_path, ".h")
    elif tr._is_stdlib_module(module_path):
      hpath = tr._stdlib_artifact_path(module_path, ".h")
    else:
      rel_mp = tr._user_module_output_relpath(module_path)
      hpath = tr.entry_output_dir / f"{rel_mp}.h"
    hpath.parent.mkdir(parents=True, exist_ok=True)
    if tr._is_ffi_module(module_path):
      note = ffi_source_note(module_path)
    elif tr._is_stdlib_module(module_path):
      note = tr._stdlib_source_note(module_path)
    else:
      note = f"{module_path}.py"
    content = [
      *codegen_file_header_lines(note, tr.generated_at),
      f"#ifndef {guard}",
      f"#define {guard}",
      "",
    ]
    # UI 等可能先于万能头 io-late ``#undef`` 拉入本头；在头内再清一轮 Win 宏（如 ``stat``）
    if module_path in (
      "py2cpp/io/path",
      "py2cpp/console",
      "py2cpp/console/popen",
      "py2cpp/console/task",
    ):
      from ..constant.stdlib_modules import UMBRELLA_MSVC_UNDEF_MACROS

      content.append("#ifdef _MSC_VER")
      for macro in UMBRELLA_MSVC_UNDEF_MACROS:
        content.append(f"#ifdef {macro}")
        content.append(f"#undef {macro}")
        content.append("#endif")
      content.append("#endif")
      content.append("")
    ma = tr.module_analysis.get(module_path, ModuleAnalysis(module_path))
    extra_includes: list[str] = []
    if module_path == _JSON_API_MODULE:
      for inc in _JSON_API_EXTRA_HEADER_INCLUDES:
        if inc not in ma.includes:
          extra_includes.append(inc)
    if module_path == "py2cpp/console/task":
      popen_h = "py2cpp/console/popen.h"
      if popen_h not in ma.includes and popen_h not in extra_includes:
        extra_includes.append(popen_h)
    from ..constant.ffi_layout import ffi_c_header_include

    if tr._is_ffi_module(module_path):
      c_inc = ffi_c_header_include(module_path)
      if c_inc:
        norm = module_path.replace("\\", "/").strip("/")
        c_l = c_inc.replace("\\", "/").lower()
        if norm == "ffi/gl/gl":
          content.append("#ifdef _WIN32")
          content.append("#ifndef WIN32_LEAN_AND_MEAN")
          content.append("#define WIN32_LEAN_AND_MEAN")
          content.append("#endif")
          content.append("#include <windows.h>")
          content.append("#endif")
        # Win32：生成头自带 LEAN_AND_MEAN / winsock2 序，避免与模板其它 ``ffi/windows/*`` 冲突
        if c_l in {"windows.h", "commctrl.h", "commdlg.h", "shellapi.h", "objidl.h", "winhttp.h", "gdiplus.h"}:
          content.append("#ifndef WIN32_LEAN_AND_MEAN")
          content.append("#define WIN32_LEAN_AND_MEAN")
          content.append("#endif")
          content.append("#ifndef NOMINMAX")
          content.append("#define NOMINMAX")
          content.append("#endif")
        if c_l == "ws2tcpip.h":
          content.append("#ifndef WIN32_LEAN_AND_MEAN")
          content.append("#define WIN32_LEAN_AND_MEAN")
          content.append("#endif")
          content.append("#include <winsock2.h>")
        elif c_l == "winsock2.h":
          content.append("#ifndef WIN32_LEAN_AND_MEAN")
          content.append("#define WIN32_LEAN_AND_MEAN")
          content.append("#endif")
        content.append(f"#include <{c_inc}>")
        content.append("")
      from ..constant.ffi_layout import ffi_include_only_surface
      if ffi_include_only_surface(module_path):
        # 空 allowlist：只中转 C 头，不拉 py_types / 其它 ffi 依赖、不写 ``.inl``
        content.append(f"#endif // {guard}")
        content.append("")
        write_text_if_changed(hpath, "\n".join(content))
        continue
    for inc in list(extra_includes) + list(ma.includes):
      content.append(format_include_line(inc))
    if module_path in PROTOCOL_TRAITS_SOURCE_MODULE_PATHS:
      content.append(f'#include "{PROTOCOL_TRAITS_HEADER}"')
    if ma.includes:
      content.append("")
    # stdio 等会把 ``popen`` 重新定义为宏；须在 include 之后、命名空间/声明之前再清一轮
    if module_path in (
      "py2cpp/console/popen",
      "py2cpp/console/task",
    ):
      content.append("#ifdef _MSC_VER")
      content.append("#ifdef popen")
      content.append("#undef popen")
      content.append("#endif")
      content.append("#endif")
      content.append("")
    if ma.forward_decls:
      for decl in ma.forward_decls:
        content.append(decl)
      content.append("")
    content.extend(lines)
    if ma.post_class_includes:
      content.append("")
      for inc in ma.post_class_includes:
        content.append(format_include_line(inc))
    if tr.per_module_inl_lines.get(module_path):
      if module_path not in _HEADER_SKIP_INL_IN_MODULE_H:
        inl_tail: list[str] = []
        library = (
          tr._is_stdlib_module(module_path)
          and is_library_module(module_path)
          and not header_only_mode()
        )
        # library：``.h`` 仅声明 + traits；实现由模块 ``.cpp`` 单次 include ``.inl``
        if not library:
          if (
            tr._is_stdlib_module(module_path)
            and module_path not in (RUNTIME_PKG, RUNTIME_BUILTINS_MODULE)
            and module_path not in _HEADER_TAIL_SKIP_UMBRELLA
            and module_path != _ITER_RESULT_MODULE
          ):
            inl_tail.append(f'#include "{UMBRELLA_HEADER}"')
          if (
            tr._is_stdlib_module(module_path)
            and module_path not in _HEADER_SKIP_OPERATORS_BEFORE_INL
          ):
            inl_tail.append(f'#include "{RUNTIME_PREFIX}/operators.h"')
        global_traits = tr.per_module_global_traits_lines.get(module_path, [])
        if global_traits:
          inl_tail.extend([
            "",
            '#include "py2cpp/core/refcount.h"',
            "",
            *global_traits,
          ])
        inl_rel = (
          f"{ffi_runtime_module_path(module_path)}.inl"
          if tr._is_ffi_module(module_path)
          else f"{module_path}.inl"
        )
        thunk_decls = getattr(tr, "_py_callable_thunk_decls_by_module", {}).get(module_path, [])
        if thunk_decls:
          inl_tail.extend(["", *thunk_decls, ""])
        if not library:
          inl_line = f'#include "{inl_rel}"'
          # 非模板 header-only：库 TU 跳过，避免与测例重复定义。
          # 模板 ``.inl`` 必须在库 TU 可见，否则无法实例化。
          if (
            tr._is_stdlib_module(module_path)
            and not header_only_mode()
            and not _module_template_inl_ok_in_library_tu(tr, module_path)
          ):
            inl_tail.extend(["", *wrap_inl_include_for_header(inl_line), ""])
          else:
            inl_tail.extend(["", inl_line, ""])
        if inl_tail:
          if module_path in _HEADER_INL_BEFORE_NS_CLOSE:
            content = insert_inl_before_namespace_close(content, module_path, inl_tail)
          else:
            content.extend(inl_tail)
    if tr._is_stdlib_module(module_path):
      global_using = stdlib_header_global_using_line(module_path)
      if global_using:
        content.append(global_using)
    content.append(f"#endif // {guard}")
    content.append("")
    write_text_if_changed(hpath, "\n".join(content))


def _sanitize_core_iter_result_inl(
  content: list[str],
  *,
  str_inc: str,
  umbrella_inc: str,
) -> list[str]:
  """``iter_result.inl``：仅 ``str.h`` + ``operators.h``；注入必要 ``using``。"""
  header: list[str] = []
  includes: list[str] = []
  rest: list[str] = []
  phase = "header"
  for line in content:
    stripped = line.strip()
    if phase == "header":
      if stripped.startswith("#include"):
        phase = "includes"
        includes.append(line)
      else:
        header.append(line)
      continue
    if phase == "includes":
      if stripped.startswith("#include"):
        includes.append(line)
        continue
      phase = "rest"
    if stripped.startswith("using ::py2cpp::text::str::") and stripped != "using ::py2cpp::text::str::PyStr;":
      continue
    rest.append(line)
  ops_inc = next((ln for ln in includes if "operators.h" in ln), None)
  other_includes = [
    ln
    for ln in includes
    if ln not in (str_inc, umbrella_inc, ops_inc) and "minimal.h" not in ln
  ]
  ordered_includes = [str_inc]
  if ops_inc is not None:
    ordered_includes.append(ops_inc)
  ordered_includes.extend(other_includes)
  usings = [
    "using namespace py2cpp::core::iter_result;",
    "using ::py2cpp::text::str::PyStr;",
  ]
  rest = [
    ln
    for ln in rest
    if ln.strip()
    not in (
      "using namespace py2cpp::core::iter_result;",
      "using ::py2cpp::text::str::PyStr;",
    )
  ]
  if rest and rest[0].strip():
    ordered_includes.append("")
  return [*header, *ordered_includes, "", *usings, "", *rest]


def write_per_module_inl(tr: Translator) -> None:
  for module_path in tr.module_order:
    if not tr._should_emit_module(module_path):
      continue
    if tr._is_stdlib_module(module_path) and not tr._can_write_stdlib_artifact(module_path):
      continue
    if tr._is_ffi_module(module_path) and not tr._can_write_ffi_artifact(module_path):
      continue
    if write_stdlib_codegen_inl(tr, module_path):
      continue
    lines = tr.per_module_inl_lines.get(module_path)
    if not lines:
      continue
    if tr._is_ffi_module(module_path):
      ipath = tr._ffi_artifact_path(module_path, ".inl")
    elif tr._is_stdlib_module(module_path):
      ipath = tr._stdlib_artifact_path(module_path, ".inl")
    else:
      rel_mp = tr._user_module_output_relpath(module_path)
      ipath = tr.entry_output_dir / f"{rel_mp}.inl"
    ipath.parent.mkdir(parents=True, exist_ok=True)
    inl_includes: list[str] = []
    ma = tr.module_analysis.get(module_path)
    library_tu = (
      tr._is_stdlib_module(module_path)
      and is_library_module(module_path)
      and not header_only_mode()
    )
    # 库 ``.cpp`` 已先 include ``minimal.h``；``.inl`` 勿再拉 umbrella（只留本模块体）。
    if (
      not library_tu
      and tr._is_stdlib_module(module_path)
      and module_path != RUNTIME_PKG
      and module_path not in _INL_SKIP_UMBRELLA
    ):
      inl_includes.append(f'#include "{UMBRELLA_HEADER}"')
    inl_includes.extend(module_inl_extra_include_lines(module_path))
    if (
      not library_tu
      and tr._is_stdlib_module(module_path)
      and module_path != RUNTIME_PKG
      and module_path not in _INL_SKIP_OPERATORS_H
    ):
      ops_h = f'#include "{RUNTIME_PREFIX}/operators.h"'
      if ops_h not in inl_includes:
        inl_includes.append(ops_h)
    if (
      ma
      and ma.forward_decls
      and stdlib_header_include("text/str") not in ma.includes
      and module_path not in _INL_SKIP_UMBRELLA
    ):
      str_inc = f'#include "{stdlib_header_include("text/str")}"'
      if str_inc not in inl_includes:
        inl_includes.append(str_inc)
    inl_preamble: list[str] = []
    if module_path in _INL_EXTRA_OPERATORS_INL:
      inl_includes.append(f'#include "{RUNTIME_PREFIX}/operators.inl"')
    if tr._is_ffi_module(module_path):
      note = f"{ffi_source_note(module_path)}（实现）"
    elif tr._is_stdlib_module(module_path):
      note = f"{tr._stdlib_source_note(module_path)}（模板实现）"
    else:
      note = f"{module_path}.py（实现）"
    preamble = tr._stdlib_inl_using_lines(module_path) if tr._is_stdlib_module(module_path) else []
    seen_pre = {ln.strip() for ln in preamble}
    idx = tr.header_usings_index
    umbrella_inc = f'#include "{UMBRELLA_HEADER}"'
    for inc in inl_includes:
      if inc == umbrella_inc:
        continue
      header = include_line_to_header_path(inc) or inc
      for ns, sym in idx.get(header, ()):
        if module_path == _ITER_RESULT_MODULE and ns == 'py2cpp::text::str' and sym != 'PyStr':
          continue
        line = using_symbol_line(ns, sym)
        if line not in seen_pre:
          seen_pre.add(line)
          preamble.append(line)
    if module_path == _ITER_RESULT_MODULE:
      str_inc = f'#include "{stdlib_header_include("text/str")}"'
      rest = [
        inc
        for inc in inl_includes
        if inc not in (str_inc, umbrella_inc) and "minimal.h" not in inc
      ]
      inl_includes = [str_inc, *rest]
    body = list(lines)
    if any("::new (" in ln for ln in body):
      new_inc = "#include <new>"
      if new_inc not in inl_includes:
        inl_includes.append(new_inc)
    if preamble:
      flat = [ln.strip() for ln in preamble]
      body = [*flat, ""] + body
    body = merge_consecutive_namespace_blocks(body)
    content = [
      *codegen_file_header_lines(note, tr.generated_at),
      "",
      *inl_includes,
      *(["",] if inl_includes else []),
      *inl_preamble,
      *body,
      "",
    ]
    if module_path == _ITER_RESULT_MODULE:
      content = _sanitize_core_iter_result_inl(
        content,
        str_inc=f'#include "{stdlib_header_include("text/str")}"',
        umbrella_inc=umbrella_inc,
      )
    write_text_if_changed(ipath, "\n".join(content))
  if tr.emit_module_filter is None:
    write_mirror_codegen_artifacts(tr)
  write_library_module_cpps(tr)


def _remove_stale_library_cpps(tr: Translator) -> None:
  """删除不再属于 ``library`` 白名单的模块 ``.cpp``（旧 bootstrap 残留）。"""
  root = tr.runtime_output_dir / RUNTIME_PREFIX
  if not root.is_dir():
    return
  keep: set[Path] = set()
  if not header_only_mode():
    keep = {
      tr._stdlib_artifact_path(mp, ".cpp").resolve()
      for mp in library_module_paths()
    }
  for cpp in root.rglob("*.cpp"):
    if cpp.resolve() in keep:
      continue
    try:
      cpp.unlink()
    except OSError:
      pass


def write_library_module_cpps(tr: Translator) -> None:
  """为 ``library`` 模块写 ``.cpp``：``PY2CPP_LIBRARY_TU`` + ``minimal.h`` + ``.inl``。"""
  if not tr._is_runtime_bootstrap():
    return
  if header_only_mode():
    _remove_stale_library_cpps(tr)
    return
  for module_path in tr.module_order:
    if not tr._is_stdlib_module(module_path) or not is_library_module(module_path):
      continue
    if not tr._can_write_stdlib_artifact(module_path):
      continue
    if not tr.per_module_inl_lines.get(module_path):
      continue
    if write_stdlib_codegen_inl(tr, module_path):
      continue
    inl_path = tr._stdlib_artifact_path(module_path, ".inl")
    if not inl_path.is_file():
      continue
    cpp_path = tr._stdlib_artifact_path(module_path, ".cpp")
    note = f"{tr._stdlib_source_note(module_path)}（库 TU）"
    inl_rel = f"{module_path}.inl"
    content = [
      *codegen_file_header_lines(note, tr.generated_at),
      "",
      f"#define {LIBRARY_TU_MACRO}",
      f'#include "{UMBRELLA_HEADER}"',
      f'#include "{inl_rel}"',
      "",
    ]
    write_text_if_changed(cpp_path, "\n".join(content))
  _remove_stale_library_cpps(tr)


def write_mirror_codegen_artifacts(tr: Translator) -> None:
  if not tr._is_runtime_bootstrap():
    return
  from ..codegen.stdlib_mirror_codegen import write_mirror_codegen_artifacts as _write

  _write(tr.runtime_output_dir / "py2cpp", tr.generated_at)
