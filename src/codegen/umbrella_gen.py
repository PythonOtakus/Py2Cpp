"""``py2cpp/minimal.h`` 万能头聚合（``templates/minimal.h`` + include 列表 ctx）。"""

from collections.abc import Sequence

from ..constant.stdlib_layout import stdlib_header_include
from ..constant.runtime_libs import LIBRARY_TU_MACRO
from ..constant.stdlib_modules import (
  UMBRELLA_IO_LATE_IF_PRESENT,
  UMBRELLA_MSVC_COMPAT_BEFORE_MODULE,
  UMBRELLA_MSVC_UNDEF_MACROS,
  UMBRELLA_MSVC_UNDEF_MACROS_EARLY,
)
from ..constant.umbrella import expand_umbrella_include_paths
from .expand_py2cpp_template import expand_template
from .stdlib_mirror_codegen import expand_whole_file_template


def build_py2cpp_umbrella_header(
  guard: str,
  generated_at: str,
  runtime_prefix: str,
  stdlib_modules: Sequence[str],
  *,
  debug: bool = False,
) -> str:
  paths = expand_umbrella_include_paths(runtime_prefix, stdlib_modules)
  includes: list[str] = []
  for p in paths:
    if p.startswith("__py2cpp_guard_inl__:"):
      inl = p.split(":", 1)[1]
      includes.append(f"#ifndef {LIBRARY_TU_MACRO}")
      includes.append(f'#include "{inl}"')
      includes.append("#endif")
    elif p == "__py2cpp_using_pynone__":
      includes.append("using ::py2cpp::core::none::PyNone;")
    else:
      includes.append(f'#include "{p}"')
  datetime_hdr = f'#include "{stdlib_header_include(UMBRELLA_MSVC_COMPAT_BEFORE_MODULE)}"'
  io_late_hdrs = {
    f'#include "{stdlib_header_include(m)}"' for m in UMBRELLA_IO_LATE_IF_PRESENT
  }
  split_datetime = len(includes)
  for i, line in enumerate(includes):
    if line == datetime_hdr:
      split_datetime = i
      break
  split_io_late = len(includes)
  for i, line in enumerate(includes):
    if line in io_late_hdrs:
      split_io_late = i
      break
  debug_block = ""
  if debug:
    debug_block = (
      "// --debug：函数调用跟踪（仅 umbrella 头一份，勿在 .cpp 重复）\n"
      + expand_template("debug.inl", apply_allman=True).strip()
      + "\n"
    )
  return expand_whole_file_template(
    "minimal.h",
    generated_at,
    {
      "guard": guard,
      "source_note": f"templates/minimal.h（运行时万能头，聚合 {runtime_prefix}/*.h）",
      "runtime_prefix": runtime_prefix,
      "ctx_DebugBlock": debug_block,
      "ctx_UmbrellaBodyBefore": "\n".join(includes[:split_datetime]),
      "ctx_UmbrellaBodyMid": "\n".join(includes[split_datetime:split_io_late]),
      "ctx_UmbrellaBodyIoLate": "\n".join(includes[split_io_late:]),
      "msvc_undef_macros_early": UMBRELLA_MSVC_UNDEF_MACROS_EARLY,
      "msvc_undef_macros": UMBRELLA_MSVC_UNDEF_MACROS,
    },
    apply_allman=False,
  ).strip() + "\n"
