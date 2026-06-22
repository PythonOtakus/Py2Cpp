"""C++ 代码生成：Allman 风格（左大括号另起一行）。"""
from __future__ import annotations

import re


def kr_to_allman(text: str) -> str:
  """将 ``) {`` / ``const {`` / ``class X {`` 等转为 Allman（保留 ``= {`` 聚合初始化）。"""
  out: list[str] = []
  for line in text.splitlines():
    stripped = line.rstrip()
    if not stripped:
      out.append("")
      continue
    indent = line[: len(line) - len(stripped.lstrip())]

    m = re.match(
      r"^(\s*)(template<[^>]+>\s*)?(class|struct)\s+([^;{]+)\s*\{\s*$",
      stripped,
    )
    if m:
      tpl = m.group(2) or ""
      out.append(f"{m.group(1)}{tpl}{m.group(3)} {m.group(4).rstrip()}")
      out.append(f"{m.group(1)}{{")
      continue

    if re.search(r"\}\s*else\s*\{", stripped):
      parts = re.split(r"\}\s*else\s*\{", stripped, maxsplit=1)
      if len(parts) == 2:
        out.append(parts[0] + "}")
        out.append(f"{indent}else")
        rest = parts[1]
        if rest.strip() == "":
          out.append(f"{indent}{{")
        else:
          _split_brace_line(f"{indent}else {{ {rest}", out)
        continue

    if _split_brace_line(stripped, out):
      continue

    out.append(stripped)
  result = "\n".join(out)
  if text.endswith("\n"):
    result += "\n"
  return result


def _split_brace_line(stripped: str, out: list[str]) -> bool:
  """将含块起始 ``{`` 的行拆为 Allman（函数头、``for``/``if``、``const`` 方法体等）。"""
  if re.search(r"=\s*\{", stripped):
    return False

  brace_idx = stripped.rfind("{")
  if brace_idx < 0:
    return False

  before_brace = stripped[:brace_idx].rstrip()
  if not re.search(r"\)\s*(?:const\s*)?$", before_brace) and not re.search(
    r"\bconst\s*$", before_brace
  ):
    return False

  indent = stripped[: len(stripped) - len(stripped.lstrip())]
  after = stripped[brace_idx + 1 :].strip()

  out.append(before_brace)
  out.append(f"{indent}{{")

  if not after:
    return True

  if after == "}":
    out.append(f"{indent}}}")
    return True

  if after.endswith("}"):
    inner = after[:-1].strip()
    if inner:
      out.append(f"{indent}  {inner}")
    out.append(f"{indent}}}")
    return True

  return False
