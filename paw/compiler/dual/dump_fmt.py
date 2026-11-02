"""Shared dump formats for Py×Paw dual compare (tokenize / parse / MidIR)."""

from __future__ import annotations

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.source import FileId
from compiler.py.frontend.syntax_nodes import EnumDecl, FunctionDecl, SyntaxModule
from compiler.py.frontend.tokens import Token, TokenKind
from compiler.py.mid.nodes import MidClass, MidEnum, MidFunction, MidImport, MidModule, MidOpaque
from compiler.py.sema.bind import bind_module, lower_to_mid


def kind_name(kind: TokenKind) -> str:
  """TokenKind.END → End；KW_ENUM → KwEnum（对齐 Paw TokenKindEnum）。"""
  return "".join(p.capitalize() for p in kind.name.split("_"))


def escape_text(s: str) -> str:
  return (
    s.replace("\\", "\\\\")
    .replace("\n", "\\n")
    .replace("\r", "\\r")
    .replace("\t", "\\t")
  )


def dump_token(tok: Token) -> str:
  return (
    f"{kind_name(tok.kind)}\t{tok.span.start}\t{tok.span.end}\t"
    f"{escape_text(tok.text)}"
  )


def dump_tokenize(src: str, *, file_value: int = 0) -> str:
  toks = Lexer(src, FileId(file_value)).tokenize()
  return "\n".join(dump_token(t) for t in toks) + "\n"


def dump_parse(src: str, *, file_value: int = 0) -> str:
  toks = Lexer(src, FileId(file_value)).tokenize()
  mod: SyntaxModule = parse_tokens(toks, src)
  lines: list[str] = []
  for it in mod.items:
    if isinstance(it, EnumDecl):
      lines.append(f"enum:{it.name}")
      for m in it.members:
        vs = m.value_source if m.value_source is not None else ""
        lines.append(f"member:{m.name}={vs}")
    elif isinstance(it, FunctionDecl):
      lines.append(f"fn:{it.name}")
  return "\n".join(lines) + ("\n" if lines else "")


def _b01(v: bool) -> str:
  return "1" if v else "0"


def dump_mid_module(mid: MidModule) -> str:
  """Normalized MidIR text（省略 decl_id / span；供双轨对照）。"""
  lines: list[str] = []
  for it in mid.items:
    if isinstance(it, MidEnum):
      base = it.base_source if it.base_source is not None else ""
      lines.append(
        f"mid_enum name={it.name} is_type={_b01(it.is_type_enum)} "
        f"flag={_b01(it.flag)} base={base}"
      )
      for name, val in it.members:
        vs = val if val is not None else ""
        lines.append(f"  member name={name} value={vs}")
    elif isinstance(it, MidFunction):
      ret = it.return_source if it.return_source is not None else ""
      lines.append(
        f"mid_fn name={it.name} params={it.params_source} return={ret} "
        f"async={_b01(it.is_async)}"
      )
    elif isinstance(it, MidClass):
      lines.append(
        f"mid_class name={it.name} record={_b01(it.is_record)} "
        f"final={_b01(it.is_final)} model={it.object_model.name}"
      )
    elif isinstance(it, MidImport):
      lines.append(f"mid_import {it.source.strip()}")
    elif isinstance(it, MidOpaque):
      # opaque 源易抖，只记条数标记
      lines.append("mid_opaque")
  return "\n".join(lines) + ("\n" if lines else "")


def dump_mid(src: str, *, path: str = "<dual>", file_value: int = 0) -> str:
  toks = Lexer(src, FileId(file_value)).tokenize()
  syn = parse_tokens(toks, src)
  mid = lower_to_mid(bind_module(syn, path=path))
  return dump_mid_module(mid)


def extract_enum_class_blocks(cpp: str) -> list[str]:
  """抽出 ``enum class Py… { … };``（无嵌套括号；D4 子集）。"""
  text = cpp.replace("\r\n", "\n")
  out: list[str] = []
  i = 0
  key = "enum class Py"
  while True:
    a = text.find(key, i)
    if a < 0:
      break
    brace = text.find("{", a)
    if brace < 0:
      break
    depth = 0
    j = brace
    while j < len(text):
      ch = text[j]
      if ch == "{":
        depth += 1
      elif ch == "}":
        depth -= 1
        if depth == 0:
          end = j + 1
          if end < len(text) and text[end] == ";":
            end += 1
          out.append(text[a:end])
          i = end
          break
      j += 1
    else:
      break
  return out


def normalize_enum_cpp(block: str) -> str:
  """规范化枚举 C++：去缩进与成员尾逗号，统一为双空格成员缩进。"""
  raw_lines = [ln.strip() for ln in block.replace("\r\n", "\n").split("\n")]
  raw_lines = [ln for ln in raw_lines if ln]
  if not raw_lines:
    return ""
  lines: list[str] = []
  for idx, ln in enumerate(raw_lines):
    s = ln[:-1] if ln.endswith(",") else ln
    if idx == 0 or s.startswith("}") or s.startswith("enum "):
      lines.append(s)
    else:
      lines.append("  " + s)
  return "\n".join(lines) + "\n"


def normalize_emitted_enums(cpp: str) -> str:
  blocks = extract_enum_class_blocks(cpp)
  return "".join(normalize_enum_cpp(b) for b in blocks)


def dump_emit_enums_from_mid(
  src: str,
  *,
  path: str = "<dual>",
  module_path: str = "dual/fixtures/parse_enum_color",
  file_value: int = 0,
) -> str:
  """Py Mid ``emit_cpp`` → 规范化 enum 文本（D4）。"""
  import tempfile
  from pathlib import Path

  from compiler.py.mid.emit_cpp import can_emit_mid, emit_mid_module

  toks = Lexer(src, FileId(file_value)).tokenize()
  syn = parse_tokens(toks, src)
  mid = lower_to_mid(bind_module(syn, path=path))
  if not can_emit_mid(mid):
    raise ValueError("can_emit_mid failed for dual emit fixture")
  with tempfile.TemporaryDirectory(prefix="dual_emit_") as td:
    h_path, _ = emit_mid_module(
      mid, out_dir=Path(td), module_path=module_path
    )
    return normalize_emitted_enums(h_path.read_text(encoding="utf-8"))
