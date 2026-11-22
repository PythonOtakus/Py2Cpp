"""统一解析入口（原生 Syntax → HIR → MidIR；生产路径禁止 Paw→legacy / CPython ast.parse）。

用途登记（须经本 API）：
- 模块发现 / 入口装载
- stdlib / FFI stubs
- 子表达式（逐步迁入原生 parse_expression）
"""
from __future__ import annotations

import host.tree_nodes as ast
import os
from dataclasses import dataclass, field
from pathlib import Path

from compiler.py.frontend import SCHEMA_VERSION as NATIVE_SCHEMA_VERSION
from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.syntax_nodes import SyntaxModule
from compiler.py.hir.nodes import HirModule
from compiler.py.mid.emit_cpp import can_emit_mid
from compiler.py.mid.nodes import MidModule
from compiler.py.sema.bind import bind_module, lower_to_mid

from .dialect import Dialect, dialect_from_path
from .source import SourceManager, digest_text

SCHEMA_VERSION = NATIVE_SCHEMA_VERSION

_CACHE: dict[tuple[str, str, str], "ParsedModule"] = {}
_SOURCE_MANAGER = SourceManager()


@dataclass
class ParsedModule:
  dialect: Dialect
  path: str
  source: str
  tree: ast.Module
  syntax: SyntaxModule
  hir: HirModule | None
  mid: MidModule | None
  digest: str
  schema_version: str = SCHEMA_VERSION
  diagnostics: list[str] = field(default_factory=list)
  # 已废弃：不再保存 rewrite 后的源码
  legacy_source: str = ""
  # MidIR 可直 emit（无 opaque 体）；生产保持空 tree，ClassInfo 经 Mid 登记
  mid_emit_ok: bool = False


def clear_parse_cache() -> None:
  _CACHE.clear()


def parse_module(
  source: str,
  *,
  path: str = "<memory>",
  dialect: Dialect | None = None,
  use_cache: bool = True,
) -> ParsedModule:
  """Paw/Mid 解析。``tree`` 生产路径恒为空（``ClassInfo`` 靠 Mid 登记）。

  ``.py`` / ``.pyi`` 亦走本路径；语法不被 Paw 接受时抛出清晰 ``SyntaxError``，
  **绝不**回退 ``ast.parse``。
  """
  dial = dialect if dialect is not None else dialect_from_path(path)
  if dial is not Dialect.PAW:
    raise ValueError(f"生产仅支持 Dialect.PAW，得 {dial!r}（{path}）")
  digest = digest_text(source)
  # 缓存键保留 NO_MATERIALIZE 槽位，避免与旧结果串味（现恒空树）
  mat_flag = os.environ.get("PY2CPP_NO_MATERIALIZE", "").strip().lower() or "default"
  key = (digest, dial.value, SCHEMA_VERSION, mat_flag, path.replace("\\", "/"))
  if use_cache and key in _CACHE:
    return _CACHE[key]

  sf = _SOURCE_MANAGER.add(path, source, digest)
  diagnostics: list[str] = []

  _diagnose_paw_banned_decorators(source, path, diagnostics)
  bans = [d for d in diagnostics if "禁止" in d]
  if bans:
    raise SyntaxError("\n".join(bans))

  suf = Path(path).suffix.lower()
  if suf in (".py", ".pyi"):
    diagnostics.append(
      f"{path}: 兼容后缀 {suf} 按 Dialect.PAW 解析（无 LEGACY/ast.parse）"
    )

  try:
    # Lexer 归一 ``\r\n``/BOM 到 ``_text``；parse 切片必须用同一份（Win CRLF 否则 span 错位）。
    _lex = Lexer(source, sf.file_id)
    tokens = _lex.tokenize()
    syntax = parse_tokens(tokens, _lex._text)
  except Exception as e:
    raise SyntaxError(
      f"{path}: Paw 前端拒绝该源（已无 CPython ast.parse 回退）: {e}"
    ) from e

  diagnostics.extend(f"P3-pending: {u}" for u in syntax.unsupported)
  hir = bind_module(syntax, path=path)
  diagnostics.extend(hir.diagnostics)
  mid = lower_to_mid(hir)
  mid_ok = can_emit_mid(mid)
  # Zero-AST Phase 4：生产 tree 恒空；ClassInfo / import 发现走 Mid 桥
  tree = ast.Module(body=[], type_ignores=[])
  if mid_ok:
    diagnostics.append(f"{path}: mid-emit（空 tree；ClassInfo←Mid）")
  else:
    diagnostics.append(f"{path}: !mid_ok（空 tree；ClassInfo←Mid）")

  parsed = ParsedModule(
    dialect=dial,
    path=path,
    source=source,
    tree=tree,
    syntax=syntax,
    hir=hir,
    mid=mid,
    digest=digest,
    diagnostics=diagnostics,
    legacy_source="",
    mid_emit_ok=mid_ok,
  )
  if use_cache:
    _CACHE[key] = parsed
  return parsed


def parse_module_file(path: str | Path, *, use_cache: bool = True) -> ParsedModule:
  p = Path(path)
  text = p.read_text(encoding="utf-8").replace("\ufeff", "")
  return parse_module(
    text,
    path=str(p),
    dialect=dialect_from_path(p),
    use_cache=use_cache,
  )


def parse_expression(source: str, *, mode: str = "eval"):
  """子表达式 → ``ExprSyntax``（生产路径无 CPython AST 解析）。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.source import FileId
  from compiler.py.frontend.stmt_parse import parse_expr
  from compiler.py.frontend.tokens import TokenKind

  if mode != "eval":
    raise ValueError(f"parse_expression 仅支持 mode='eval'，得 {mode!r}")
  text = source.strip()
  if not text:
    raise SyntaxError("空表达式")
  toks = Lexer(text, FileId(0)).tokenize()
  expr, i = parse_expr(toks, 0, source=text)
  if expr is None:
    raise SyntaxError(f"无法解析表达式: {source!r}")
  while i < len(toks) and toks[i].kind in (TokenKind.NEWLINE, TokenKind.END):
    i += 1
  if i < len(toks) and toks[i].kind is not TokenKind.END:
    raise SyntaxError(f"表达式未完全消费: {source!r}")
  return expr


def parse_type(source: str):
  """类型子表达式 → ``TypeSyntax``（原生 ``type_parse``，无 CPython AST 解析）。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.source import FileId
  from compiler.py.frontend import type_parse as _type_parse
  from compiler.py.frontend.tokens import TokenKind

  text = source.strip()
  if not text:
    raise SyntaxError("空类型")
  toks = Lexer(text, FileId(0)).tokenize()
  ty, i = _type_parse.parse_type(toks, 0, source=text)
  if ty is None:
    raise SyntaxError(f"无法解析类型: {source!r}")
  while i < len(toks) and toks[i].kind in (TokenKind.NEWLINE, TokenKind.END):
    i += 1
  if i < len(toks) and toks[i].kind is not TokenKind.END:
    raise SyntaxError(f"类型未完全消费: {source!r}")
  return ty


def parse_expression_as_ast(source: str) -> ast.expr:
  """``parse_expression`` + Syntax→AST（供仍消费 ``ast.expr`` 的 emit 过渡）。"""
  from compiler.py.mid.tree_from_mid import expr_syntax_to_ast

  return expr_syntax_to_ast(parse_expression(source))


def parse_type_as_ast(source: str) -> ast.expr:
  """``parse_type`` + Syntax→AST。"""
  from compiler.py.mid.tree_from_mid import type_syntax_to_ast

  return type_syntax_to_ast(parse_type(source))


def _diagnose_paw_banned_decorators(
  source: str, path: str, diagnostics: list[str]
) -> None:
  """``.paw`` 禁止旧装饰器 / 类型标记写法（``@native_name`` 除外）。

  ``paw/reflect/mixin.paw`` 为 CPython/IDE 桩，允许 ``@classmethod``。
  合成片段路径（``<…>``）跳过：pass 回写 Mid 的临时源，不是用户表面。
  """
  from compiler.py.frontend.source import FileId
  from compiler.py.frontend.tokens import TokenKind

  norm = path.replace("\\", "/")
  if "<" in norm:
    return
  allow_classmethod = norm.endswith("paw/reflect/mixin.paw")
  for i, line in enumerate(source.splitlines(), start=1):
    s = line.lstrip()
    if s.startswith("@native_name"):
      continue
    if s.startswith("@staticmethod"):
      diagnostics.append(f"{path}:{i}: 禁止 @staticmethod，改用 static def")
    elif s.startswith("@classmethod") and not allow_classmethod:
      diagnostics.append(f"{path}:{i}: 禁止 @classmethod（Paw 不支持）")
    elif s.startswith("@overload"):
      diagnostics.append(f"{path}:{i}: 禁止 @overload；同名定义即重载")
    elif s.startswith("@native") and not s.startswith("@native_name"):
      diagnostics.append(f"{path}:{i}: 禁止 @native，改用 native class / native def")
    elif s.startswith("@override"):
      diagnostics.append(f"{path}:{i}: 禁止 @override，改用 override def")
    elif s.startswith("@virtual"):
      diagnostics.append(f"{path}:{i}: 禁止 @virtual，改用 virtual def")
    elif s.startswith("@abstract"):
      diagnostics.append(f"{path}:{i}: 禁止 @abstract，改用 abstract def")
    elif s.startswith("@final"):
      diagnostics.append(
        f"{path}:{i}: 禁止 @final，改用 final class / final def / override final def"
      )
    elif s.startswith("@staticproperty"):
      diagnostics.append(
        f"{path}:{i}: 禁止 @staticproperty，改用 static property def / static property 块"
      )
    elif s.startswith("@property"):
      diagnostics.append(
        f"{path}:{i}: 禁止 @property，改用 property def / property 块"
      )
    elif s.startswith("@delegate"):
      diagnostics.append(
        f"{path}:{i}: 禁止 @delegate，改用 delegate Name(...) -> R"
      )
    elif s.startswith("@enum"):
      diagnostics.append(
        f"{path}:{i}: 禁止 @enum / @enum.mro，改用 enum Name: / type enum Name:"
      )
    elif s.startswith("@union"):
      diagnostics.append(
        f"{path}:{i}: 禁止 @union / @union.mro，改用 union Name: / type union Name:"
      )

  for i, line in enumerate(source.splitlines(), start=1):
    if "Function[[" in line:
      diagnostics.append(
        f"{path}:{i}: 禁止 Function[[…], R]，改用 (Args) -> R / T -> R"
      )
    if "Callable[[" in line:
      diagnostics.append(
        f"{path}:{i}: 禁止 Callable[[…], R]，改用 Callable[(Args) -> R]"
      )

  tokens = Lexer(source, FileId(0)).tokenize()
  n = len(tokens)
  line_starts = [0]
  for idx, ch in enumerate(source):
    if ch == "\n":
      line_starts.append(idx + 1)

  def _line_of(pos: int) -> int:
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
      mid = (lo + hi + 1) // 2
      if line_starts[mid] <= pos:
        lo = mid
      else:
        hi = mid - 1
    return lo + 1

  i = 0
  while i < n:
    if (
      tokens[i].kind is TokenKind.NAME
      and tokens[i].text == "async"
      and i + 1 < n
      and tokens[i + 1].kind is TokenKind.NAME
      and tokens[i + 1].text == "static"
    ):
      diagnostics.append(
        f"{path}:{_line_of(tokens[i].span.start)}: 禁止 async static，改用 static async"
      )
      i += 2
      continue
    tok = tokens[i]
    if tok.kind is TokenKind.END:
      break
    if tok.kind is TokenKind.NAME and tok.text == "import":
      j = i + 1
      while j < n and tokens[j].kind not in (
        TokenKind.NEWLINE,
        TokenKind.END,
        TokenKind.DEDENT,
      ):
        if tokens[j].kind in (TokenKind.KW_ENUM, TokenKind.KW_UNION):
          kw = tokens[j].text
          diagnostics.append(
            f"{path}:{_line_of(tokens[j].span.start)}: 禁止将硬关键字 `{kw}` 作导入名；声明写 `{kw} Name:`"
          )
        j += 1
      i = j
      continue
    if tok.kind is TokenKind.AT and i + 1 < n and tokens[i + 1].kind is TokenKind.NAME:
      name = tokens[i + 1].text
      ln = _line_of(tok.span.start)
      j = i - 1
      saw_nl = False
      while j >= 0 and tokens[j].kind in (
        TokenKind.NEWLINE,
        TokenKind.INDENT,
        TokenKind.DEDENT,
      ):
        if tokens[j].kind is TokenKind.NEWLINE:
          saw_nl = True
        j -= 1
      at_stmt_start = j < 0 or saw_nl
      if name in ("ref", "lazy"):
        if name == "ref":
          diagnostics.append(
            f"{path}:{ln}: 禁止类型标记 @ref，改用 ref T（组合写 lazy ref T）"
          )
        else:
          diagnostics.append(
            f"{path}:{ln}: 禁止类型标记 @lazy，改用 lazy T（组合写 lazy ref T）"
          )
      elif name in ("property", "staticproperty") and not at_stmt_start:
        if name == "staticproperty":
          diagnostics.append(
            f"{path}:{ln}: 禁止字段标记 @staticproperty，改用 static property 块"
          )
        else:
          diagnostics.append(
            f"{path}:{ln}: 禁止字段标记 @property，改用存储字段 + property 块"
          )
      i += 2
      continue
    i += 1
