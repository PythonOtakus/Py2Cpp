"""``py2cpp/minimal.h`` 万能头聚合（``templates/minimal.h`` + include 列表 ctx）。"""

from collections.abc import Sequence

from ..constant.stdlib_layout import stdlib_header_include
from ..constant.stdlib_modules import (
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
  includes = [f'#include "{p}"' for p in paths]
  datetime_hdr = f'#include "{stdlib_header_include(UMBRELLA_MSVC_COMPAT_BEFORE_MODULE)}"'
  split_at = len(includes)
  for i, line in enumerate(includes):
    if line == datetime_hdr:
      split_at = i
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
      "ctx_UmbrellaBodyBefore": "\n".join(includes[:split_at]),
      "ctx_UmbrellaBodyAfter": "\n".join(includes[split_at:]),
      "msvc_undef_macros_early": UMBRELLA_MSVC_UNDEF_MACROS_EARLY,
      "msvc_undef_macros": UMBRELLA_MSVC_UNDEF_MACROS,
    },
    apply_allman=False,
  ).strip() + "\n"
