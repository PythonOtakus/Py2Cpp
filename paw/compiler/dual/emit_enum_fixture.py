"""Dual 门闩用 emitEnum（与 ``compiler/paw/mid/emit_cpp.paw::emitEnum`` 对齐）。

原 ``emit_enum_min`` 竖切已取消；此模块仅供 ``paw_dual_compare`` 对照 golden。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnumMember:
  name: str
  valueSource: str = ""


@dataclass
class EnumBundle:
  name: str
  members: list[EnumMember] = field(default_factory=list)


def emitEnum(en: EnumBundle) -> str:
  out: str = "enum class Py" + en.name + " : int {\n"
  n: int = len(en.members)
  i: int = 0
  while i < n:
    m: EnumMember = en.members[i]
    line: str = "  " + m.name
    vs: str = m.valueSource.strip()
    if vs != "" and vs != "..." and vs != "Ellipsis":
      line = line + " = " + vs
    if i + 1 < n:
      line = line + ","
    out = out + line + "\n"
    i += 1
  out = out + "};\n"
  return out
