"""统一解析入口（原生 Syntax → HIR → MidIR；生产路径禁止 Paw→legacy 全文改写）。

用途登记（须经本 API）：
- 模块发现 / 入口装载
- stdlib / FFI stubs
- 子表达式（逐步迁入原生 parse_expression）
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path

from compiler.py.frontend import SCHEMA_VERSION as NATIVE_SCHEMA_VERSION
from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.syntax_nodes import SyntaxModule
from compiler.py.hir.nodes import HirModule
from compiler.py.mid.ast_from_mid import ast_module_from_mid
from compiler.py.mid.emit_cpp import can_emit_mid
from compiler.py.mid.nodes import MidModule
from compiler.py.sema.bind import bind_module, lower_to_mid

from .cpython_adapter import from_cpython
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
  # P3：MidIR 可直 emit（无 opaque 体）；为 True 时走 ast_from_mid / 可空树
  mid_emit_ok: bool = False


def clear_parse_cache() -> None:
  _CACHE.clear()


def _no_materialize_mode(path: str, *, mid_ok: bool) -> bool:
  """是否空树（跳过 AST 直构；ClassInfo 靠回填 / ``register_module_from_mid``）。

  - ``PY2CPP_NO_MATERIALIZE=1`` / 未设置：全部 ``mid_emit_ok`` 空树（P6）
  - ``=0``：关闭（``mid_ok`` 仍走 ``ast_from_mid``，非 span materialize）
  """
  if not mid_ok:
    return False
  flag = os.environ.get("PY2CPP_NO_MATERIALIZE", "").strip().lower()
  if flag in ("0", "false", "no", "off"):
    return False
  # 未设置或 =1：mid_ok 一律空树（translator 再 ast_from_mid 回填）
  _ = path
  return True


def parse_module(
  source: str,
  *,
  path: str = "<memory>",
  dialect: Dialect | None = None,
  use_cache: bool = True,
) -> ParsedModule:
  dial = dialect if dialect is not None else dialect_from_path(path)
  digest = digest_text(source)
  # 物化模式进缓存键，避免 NO_MATERIALIZE 与物化结果串味
  mat_flag = os.environ.get("PY2CPP_NO_MATERIALIZE", "").strip().lower() or "default"
  key = (digest, dial.value, SCHEMA_VERSION, mat_flag, path.replace("\\", "/"))
  if use_cache and key in _CACHE:
    return _CACHE[key]

  sf = _SOURCE_MANAGER.add(path, source, digest)
  diagnostics: list[str] = []
  hir: HirModule | None = None
  mid: MidModule | None = None
  mid_ok = False

  if dial is Dialect.LEGACY:
    tree = ast.parse(source, filename=path)
    syntax = from_cpython(tree, source, file_id=sf.file_id)
    legacy_source = source
  else:
    _diagnose_paw_banned_decorators(source, path, diagnostics)
    bans = [d for d in diagnostics if "禁止" in d]
    if bans:
      raise SyntaxError("\n".join(bans))
    tokens = Lexer(source, sf.file_id).tokenize()
    syntax = parse_tokens(tokens, source)
    diagnostics.extend(f"P3-pending: {u}" for u in syntax.unsupported)
    hir = bind_module(syntax, path=path)
    diagnostics.extend(hir.diagnostics)
    mid = lower_to_mid(hir)
    mid_ok = can_emit_mid(mid)
    if _no_materialize_mode(path, mid_ok=mid_ok):
      tree = ast.Module(body=[], type_ignores=[])
      diagnostics.append(f"{path}: mid-emit（跳过 materialize_ast）")
    else:
      # P5：生产路径一律 MidIR 直构（已删 span ``materialize_ast``）
      tree = ast_module_from_mid(mid, filename=path)
      tag = "mid_ok" if mid_ok else "!mid_ok"
      diagnostics.append(f"{path}: {tag} → ast_from_mid")
    legacy_source = ""

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
    legacy_source=legacy_source,
    mid_emit_ok=mid_ok if dial is not Dialect.LEGACY else False,
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


def parse_expression(source: str, *, mode: str = "eval") -> ast.AST:
  """子表达式登记入口。

  N4：简单标识符走原生 Lexer 校验后仍物化为 ``ast``（C0）；
  复杂式暂用 ``ast.parse``。完整原生 Expr 节点见后续 schema。
  """
  text = source.strip()
  if mode == "eval" and text.isidentifier():
    from compiler.py.frontend.lexer import Lexer
    from compiler.py.frontend.source import FileId
    from compiler.py.frontend.tokens import TokenKind

    toks = Lexer(text, FileId(0)).tokenize()
    names = [t for t in toks if t.kind not in (TokenKind.NEWLINE, TokenKind.END)]
    if len(names) == 1 and names[0].kind is TokenKind.NAME:
      return ast.Name(id=names[0].text, ctx=ast.Load())
  tree = ast.parse(source, mode=mode)
  return tree.body if mode == "eval" else tree


def parse_type(source: str) -> ast.AST:
  """类型子表达式：与 ``parse_expression`` 同入口（N4 收口）。"""
  return parse_expression(source, mode="eval")


def _diagnose_paw_banned_decorators(
  source: str, path: str, diagnostics: list[str]
) -> None:
  """``.paw`` 禁止旧装饰器 / 类型标记写法（``@native_name`` 除外）。

  ``paw/reflect/mixin.paw`` 为 CPython/IDE 桩，允许 ``@classmethod``。
  """
  from compiler.py.frontend.source import FileId
  from compiler.py.frontend.tokens import TokenKind

  norm = path.replace("\\", "/")
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

  # 旧 Subscript 表面 Function[[…],R] / Callable[[…],R]
  for i, line in enumerate(source.splitlines(), start=1):
    if "Function[[" in line:
      diagnostics.append(
        f"{path}:{i}: 禁止 Function[[…], R]，改用 (Args) -> R / T -> R"
      )
    if "Callable[[" in line:
      diagnostics.append(
        f"{path}:{i}: 禁止 Callable[[…], R]，改用 Callable[(Args) -> R]"
      )

  # 类型位旧标记 ``T @ref`` / ``T @lazy``；以及 ``async static`` 序
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
    # ``enum``/``union`` 硬关键字不可作导入名（声明头除外）
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
      # 逻辑行首（含 class 体 INDENT 后）：行首装饰器已由文本扫描处理
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
        # 字段简写 ``T @property`` / ``T @property.postsetter``
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
