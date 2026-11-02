"""``__setitem__`` 值参数：自动生成 ``const T&`` / 按值 ``T`` 重载（可绑定临时量）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..analysis.ir import format_fn_sig


@dataclass(frozen=True)
class SetitemValueParam:
  prefix: str
  val_type: str
  name: str
  ref: Literal["value", "const_lref", "mutable_lref"]


_PARAM_RE = re.compile(
  r"^(?:(const)\s+)?(.+?)(?:(\&))\s+(\w+)\s*$",
)


def parse_setitem_value_param(params: str) -> SetitemValueParam | None:
  if not params or not params.strip():
    return None
  prefix, last = _split_last_param(params)
  m = _PARAM_RE.match(last.strip())
  if not m:
    sp = last.strip().rsplit(None, 1)
    if len(sp) != 2:
      return None
    val_type, name = sp[0].strip(), sp[1].strip()
    if val_type.endswith("&") or val_type.endswith("*"):
      return None
    return SetitemValueParam(prefix=prefix, val_type=val_type, name=name, ref="value")
  is_const, val_type, _, name = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
  ref: Literal["value", "const_lref", "mutable_lref"] = (
    "const_lref" if is_const else "mutable_lref"
  )
  return SetitemValueParam(prefix=prefix, val_type=val_type, name=name, ref=ref)


def canonical_const_lref_param(parsed: SetitemValueParam) -> str:
  return f"const {parsed.val_type}& {parsed.name}"


def by_value_param(parsed: SetitemValueParam) -> str:
  return f"{parsed.val_type} {parsed.name}"


def mutable_lref_param(parsed: SetitemValueParam) -> str:
  return f"{parsed.val_type}& {parsed.name}"


def params_with_last(prefix: str, last_param: str) -> str:
  if prefix:
    return f"{prefix}{last_param}"
  return last_param


def extra_setitem_decl_params(parsed: SetitemValueParam) -> list[str]:
  if parsed.ref == "value":
    return []
  if parsed.ref == "const_lref":
    return [params_with_last(parsed.prefix, by_value_param(parsed))]
  return [
    params_with_last(parsed.prefix, canonical_const_lref_param(parsed)),
    params_with_last(parsed.prefix, by_value_param(parsed)),
  ]


def emit_setitem_extra_decls(
  write_line,
  *,
  ret_lead: str,
  ret_trail: str,
  mcpp: str,
  parsed: SetitemValueParam,
  static_prefix: str = "",
  virtual_prefix: str = "",
  const_suffix: str = "",
  override_suffix: str = "",
) -> None:
  for extra_params in extra_setitem_decl_params(parsed):
    decl = format_fn_sig(ret_lead, ret_trail, mcpp, extra_params)
    write_line(f"{static_prefix}{virtual_prefix}{decl}{const_suffix}{override_suffix};")


def emit_setitem_forwarders(
  write_line,
  *,
  qual: str,
  ret_lead: str,
  ret_trail: str,
  mcpp: str,
  parsed: SetitemValueParam,
  const_suffix: str = "",
) -> None:
  canonical = params_with_last(parsed.prefix, canonical_const_lref_param(parsed))
  call_args = _call_args_from_params(canonical)
  if parsed.ref == "mutable_lref":
    orig = params_with_last(parsed.prefix, mutable_lref_param(parsed))
    sig = format_fn_sig(ret_lead, ret_trail, f"{qual}::{mcpp}", orig) + const_suffix
    write_line(f"{sig} {{ {mcpp}({call_args}); }}")
    write_line()
  if parsed.ref in ("mutable_lref", "const_lref"):
    bv = params_with_last(parsed.prefix, by_value_param(parsed))
    sig = format_fn_sig(ret_lead, ret_trail, f"{qual}::{mcpp}", bv) + const_suffix
    write_line(f"{sig} {{ {mcpp}({call_args}); }}")
    write_line()


def _split_last_param(params: str) -> tuple[str, str]:
  idx = params.rfind(",")
  if idx < 0:
    return "", params.strip()
  return params[: idx + 1] + " ", params[idx + 1 :].strip()


def _call_args_from_params(params: str) -> str:
  names: list[str] = []
  for part in params.split(","):
    part = part.strip()
    if not part:
      continue
    names.append(part.rsplit(None, 1)[-1])
  return ", ".join(names)
