"""MidIR → ``ast.Module`` 直构（生产路径；无 span / 全文 rewrite）。"""
from __future__ import annotations

import ast

from compiler.py.frontend.syntax_nodes import ObjectModel

from .nodes import (
  MidClass,
  MidEnum,
  MidFunction,
  MidImport,
  MidModule,
  MidModuleConst,
  MidOpaque,
)


def ast_module_from_mid(mid: MidModule, *, filename: str = "<paw>") -> ast.Module:
  """逐项直构整模块 AST（不读源码 Span、不 ``rewrite_paw_to_legacy``）。"""
  body: list[ast.stmt] = []
  for item in mid.items:
    if isinstance(item, MidImport):
      body.extend(_parse_stmts(item.source, filename))
    elif isinstance(item, MidOpaque):
      body.extend(_parse_stmts(item.source, filename))
    elif isinstance(item, MidEnum):
      body.append(_enum_class(item))
    elif isinstance(item, MidClass):
      body.append(_class_def(_class_for_ast(item), filename))
    elif isinstance(item, MidModuleConst):
      body.append(_module_const_stmt(item))
    elif isinstance(item, MidFunction):
      body.extend(_function_stmts(item, filename))
    else:
      raise TypeError(f"unknown MidIR item: {type(item)!r}")
  return ast.Module(body=body, type_ignores=[])


def classdef_from_mid_enum(item: MidEnum) -> ast.ClassDef:
  """MidEnum → ``ast.ClassDef``（供 Mid→ClassInfo）。"""
  return _enum_class(item)


def classdef_from_mid_class(
  item: MidClass, filename: str = "<paw>"
) -> ast.ClassDef:
  """MidClass → ``ast.ClassDef``（供 Mid→ClassInfo）。"""
  return _class_def(item, filename)


def stmts_from_mid_function(
  item: MidFunction, filename: str = "<paw>"
) -> list[ast.stmt]:
  """MidFunction → AST 语句列表。"""
  return _function_stmts(item, filename)


def stmt_from_mid_module_const(item: MidModuleConst) -> ast.stmt:
  """MidModuleConst → ``ast.AnnAssign``。"""
  return _module_const_stmt(item)


def _rewrite_optional_field_line(line: str) -> str:
  """``optional name: T = v`` → ``name: T @optional = v``。"""
  stripped = line.lstrip()
  indent = line[: len(line) - len(stripped)]
  if not stripped.startswith("optional "):
    return line
  rest = stripped[len("optional ") :]
  eq = rest.find("=")
  if eq < 0:
    return f"{indent}{rest}"
  left = rest[:eq].rstrip()
  right = rest[eq + 1 :].lstrip()
  return f"{indent}{left} @optional = {right}"


def _class_for_ast(item: MidClass) -> MidClass:
  return MidClass(
    decl_id=item.decl_id,
    name=item.name,
    object_model=item.object_model,
    is_final=item.is_final,
    is_record=item.is_record,
    is_frozen=item.is_frozen,
    is_ordered=item.is_ordered,
    is_lazy=item.is_lazy,
    is_protocol=item.is_protocol,
    is_mixin=item.is_mixin,
    is_union=item.is_union,
    is_variant=item.is_variant,
    bases_source=item.bases_source,
    const_fields=item.const_fields,
    fields=list(item.fields),
    opaque_members=[_rewrite_optional_field_line(m) for m in item.opaque_members],
    span=item.span,
    decorators_source=item.decorators_source,
    is_native=item.is_native,
    methods=list(item.methods),
    type_params_source=item.type_params_source,
  )


def _parse_class_header(
  name: str, type_params_source: str, bases_source: str | None
) -> tuple[list, list[ast.expr], list[ast.keyword]]:
  """解析 PEP695 / bases / friends= 等类头。"""
  tp = type_params_source or ""
  bases = bases_source or ""
  stub = f"class {name}{tp}{bases}:\n  pass\n"
  try:
    mod = ast.parse(stub, mode="exec")
  except SyntaxError:
    return [], [], []
  if not mod.body or not isinstance(mod.body[0], ast.ClassDef):
    return [], [], []
  node = mod.body[0]
  return list(getattr(node, "type_params", None) or []), list(node.bases), list(
    node.keywords
  )


def _parse_stmts(source: str, filename: str) -> list[ast.stmt]:
  text = source.strip("\n")
  if not text.strip():
    return []
  if not text.endswith("\n"):
    text = text + "\n"
  lines = text.splitlines()
  indents = [
    len(ln) - len(ln.lstrip(" \t"))
    for ln in lines
    if ln.strip() and not ln.lstrip().startswith("#")
  ]
  if indents:
    m = min(indents)
    if m > 0:
      text = "\n".join(ln[m:] if len(ln) >= m else ln for ln in lines) + "\n"
  try:
    tree = ast.parse(text, filename=filename, mode="exec")
  except SyntaxError as e:
    raise SyntaxError(f"{filename}: MidOpaque fragment: {e}") from e
  return list(tree.body)


def _decorator(name: str, *keywords: ast.keyword) -> ast.expr:
  if not keywords:
    return ast.Name(id=name, ctx=ast.Load())
  return ast.Call(
    func=ast.Name(id=name, ctx=ast.Load()),
    args=[],
    keywords=list(keywords),
  )


def _enum_bases_and_keywords(
  base_source: str | None,
) -> tuple[list[ast.expr], list[ast.keyword]]:
  """``(int64)`` / ``(ModeEnum)`` / ``(base=Animal)`` / ``(flag=True, PermFlag)``。"""
  if not base_source:
    return [], []
  inner = base_source.strip()
  if inner.startswith("(") and inner.endswith(")"):
    inner = inner[1:-1].strip()
  if not inner:
    return [], []
  bases: list[ast.expr] = []
  keywords: list[ast.keyword] = []
  for part in inner.split(","):
    part = part.strip()
    if not part:
      continue
    if "=" in part:
      key, _, raw = part.partition("=")
      key = key.strip()
      raw = raw.strip()
      if not key.isidentifier():
        continue
      try:
        value: ast.expr = ast.parse(raw, mode="eval").body
      except SyntaxError:
        value = ast.Constant(value=raw)
      keywords.append(ast.keyword(arg=key, value=value))
      continue
    if part.isidentifier():
      bases.append(ast.Name(id=part, ctx=ast.Load()))
  return bases, keywords


def _enum_bases_from_source(base_source: str | None) -> list[ast.expr]:
  """``(int64)`` / ``(ModeEnum)`` / ``(flag=True, PermFlag)`` → ClassDef.bases。"""
  bases, _ = _enum_bases_and_keywords(base_source)
  return bases


def _enum_class(item: MidEnum) -> ast.ClassDef:
  decos: list[ast.expr] = []
  if item.is_type_enum:
    # ``@enum.mro``（Attribute），勿写成 ``@enum(mro=True)``
    decos.append(
      ast.Attribute(
        value=ast.Name(id="enum", ctx=ast.Load()),
        attr="mro",
        ctx=ast.Load(),
      )
    )
  elif item.flag:
    decos.append(_decorator("enum", ast.keyword("flag", ast.Constant(True))))
  else:
    decos.append(_decorator("enum"))
  body: list[ast.stmt] = []
  for name, val in item.members:
    if val is None:
      continue
    target = ast.Name(id=name, ctx=ast.Store())
    if val.strip() == "...":
      value: ast.expr = ast.Constant(value=Ellipsis)
    else:
      try:
        value = ast.parse(val, mode="eval").body
      except SyntaxError:
        value = ast.Constant(value=val)
    body.append(ast.Assign(targets=[target], value=value))
  if not body:
    body = [ast.Pass()]
  bases, keywords = _enum_bases_and_keywords(item.base_source)
  return ast.ClassDef(
    name=item.name,
    bases=bases,
    keywords=keywords,
    body=body,
    decorator_list=decos,
    type_params=[],
  )


def _module_const_stmt(item: MidModuleConst) -> ast.stmt:
  return _const_field(item.name, item.type_name, item.value_source)


def _const_field(name: str, typ: str | None, value: str) -> ast.stmt:
  target = ast.Name(id=name, ctx=ast.Store())
  if typ:
    legacy = _type_to_legacy_annotation(typ) or typ
    try:
      inner = ast.parse(legacy, mode="eval").body
    except SyntaxError:
      inner = ast.Name(id=typ, ctx=ast.Load())
  else:
    inner = ast.Name(id="object", ctx=ast.Load())
  annotation = ast.BinOp(
    left=inner,
    op=ast.MatMult(),
    right=ast.Name(id="const", ctx=ast.Load()),
  )
  try:
    val_expr = ast.parse(value if value else "None", mode="eval").body
  except SyntaxError:
    val_expr = ast.Constant(value=None)
  return ast.AnnAssign(
    target=target,
    annotation=annotation,
    value=val_expr,
    simple=1,
  )


def _instance_field(name: str, typ: str | None, value: str) -> ast.stmt:
  target = ast.Name(id=name, ctx=ast.Store())
  if typ:
    legacy = _type_to_legacy_annotation(typ) or typ
    try:
      annotation = ast.parse(legacy, mode="eval").body
    except SyntaxError:
      annotation = ast.Name(id=typ, ctx=ast.Load())
  else:
    annotation = ast.Name(id="object", ctx=ast.Load())
  val_expr = None
  if value.strip():
    try:
      val_expr = ast.parse(value, mode="eval").body
    except SyntaxError:
      val_expr = ast.Constant(value=None)
  return ast.AnnAssign(
    target=target,
    annotation=annotation,
    value=val_expr,
    simple=1,
  )


def _parse_decorator_lines(text: str) -> list[ast.expr]:
  out: list[ast.expr] = []
  lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("@")]
  if not lines:
    return out
  stub = "\n".join(lines) + "\ndef __paw_deco_stub():\n  pass\n"
  try:
    mod = ast.parse(stub, mode="exec")
  except SyntaxError:
    return out
  for stmt in mod.body:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
      out.extend(stmt.decorator_list)
  return out


def _opaque_looks_like_type_if(mem: str) -> bool:
  """类体首条 type_if 链：去缩进后以 ``if `` 开头。"""
  for ln in mem.splitlines():
    s = ln.strip()
    if not s or s.startswith("#"):
      continue
    return s.startswith("if ") or s == "if"
  return False


def _opaque_member_stmts(mem: str, filename: str) -> list[ast.stmt]:
  """类体 opaque → AST；含 ``static def`` 等 Paw 前缀时先 ``rewrite_paw_to_legacy``。"""
  raw = mem.strip("\n")
  if not raw.strip():
    return []
  text = raw if raw.endswith("\n") else raw + "\n"
  candidates = [text]
  if any(
    tok in text
    for tok in (
      "static ",
      "native ",
      "override ",
      "abstract ",
      "virtual ",
      "final ",
      "property ",
      "lazy ",
    )
  ):
    try:
      from compiler.py.frontend.diagnostic import FrontendError
      from compiler.py.frontend.surface_rewrite import rewrite_paw_to_legacy

      rewritten = rewrite_paw_to_legacy(text)
      if rewritten != text:
        candidates.insert(0, rewritten)
    except FrontendError:
      pass
  for cand in candidates:
    try:
      return _parse_stmts(cand, filename)
    except SyntaxError:
      continue
  return [ast.Pass()]


def _class_def(item: MidClass, filename: str = "<paw>") -> ast.ClassDef:
  decos: list[ast.expr] = []
  if item.decorators_source.strip():
    decos.extend(_parse_decorator_lines(item.decorators_source))
  if item.is_union:
    # ``type union Name(base=T)`` → ``@union.mro``；普通 ``union`` 仍 ``@union``
    bases_src = item.bases_source or ""
    if "base=" in bases_src:
      decos.append(
        ast.Attribute(
          value=ast.Name(id="union", ctx=ast.Load()),
          attr="mro",
          ctx=ast.Load(),
        )
      )
    else:
      decos.append(_decorator("union"))
  if item.is_variant:
    decos.append(_decorator("variant"))
  if item.is_protocol:
    decos.append(_decorator("protocol"))
  if item.is_mixin:
    decos.append(_decorator("mixin"))
  if item.is_record:
    dc_kw: list[ast.keyword] = []
    if item.is_frozen:
      dc_kw.append(ast.keyword("frozen", ast.Constant(True)))
    if item.is_ordered:
      # ``ordered record`` 须同时 ``eq=True``：``ComparableType``/Heap 探测 ``__eq__``；
      # 仅 ``order=True`` 时 ``_parse_dataclass_options`` 会默认 ``eq=False``。
      dc_kw.append(ast.keyword("order", ast.Constant(True)))
      dc_kw.append(ast.keyword("eq", ast.Constant(True)))
    decos.append(_decorator("dataclass", *dc_kw))
  elif item.is_frozen:
    decos.append(_decorator("frozen"))
  if item.object_model is ObjectModel.REF_COUNT:
    decos.append(_decorator("refcount"))
  if item.is_final:
    decos.append(_decorator("final"))
  if item.is_native:
    decos.append(_decorator("native"))
  if item.is_lazy and item.object_model is not ObjectModel.REF_COUNT:
    decos.append(_decorator("refcount"))

  # MidClass 拆成 fields/opaque/methods 会丢交错顺序；class_type_if 要求体首为 If 链
  type_if_opaques: list[str] = []
  other_opaques: list[str] = []
  for mem in item.opaque_members:
    if _opaque_looks_like_type_if(mem):
      type_if_opaques.append(mem)
    else:
      other_opaques.append(mem)

  body: list[ast.stmt] = []
  for mem in type_if_opaques:
    body.extend(_opaque_member_stmts(mem, filename))
  for name, typ, val in item.const_fields:
    body.append(_const_field(name, typ, val))
  for name, typ, val in item.fields:
    body.append(_instance_field(name, typ, val))
  for mem in other_opaques:
    body.extend(_opaque_member_stmts(mem, filename))
  for meth in item.methods:
    body.extend(_function_stmts(meth, filename))
  if not body:
    body = [ast.Pass()]

  type_params, bases, keywords = _parse_class_header(
    item.name, item.type_params_source, item.bases_source
  )

  return ast.ClassDef(
    name=item.name,
    bases=bases,
    keywords=keywords,
    body=body,
    decorator_list=decos,
    type_params=type_params,
  )


def _rewrite_body_type_prefixes(body: str) -> str:
  """函数体内 Paw 类型表面 → 可 ``ast.parse``（``ref``/``lazy``/裸箭头/``Callable[arrow]``）。

  包进探测 ``def`` 再 ``rewrite_paw_to_legacy``，避免 Lexer 吃 INDENT 后的残片。
  """
  if not (
    "ref" in body or "lazy" in body or "->" in body or "Callable[" in body
  ):
    return body
  from compiler.py.frontend.diagnostic import FrontendError
  from compiler.py.frontend.surface_rewrite import rewrite_paw_to_legacy

  wrapped = f"def __paw_body_probe():\n{body}"
  try:
    rewritten = rewrite_paw_to_legacy(wrapped)
  except FrontendError:
    return body
  nl = rewritten.find("\n")
  if nl < 0:
    return body
  out = rewritten[nl + 1 :]
  return out if out.endswith("\n") else out + "\n"


def _body_parses(body: str) -> bool:
  """缩进探测：允许先改写 Paw 类型表面再 ``ast.parse``。"""
  candidates = [body]
  rewritten = _rewrite_body_type_prefixes(body)
  if rewritten != body:
    candidates.insert(0, rewritten)
  if "ref" in body or "lazy" in body:
    soft = (
      body.replace(": ref ", ": ")
      .replace(": lazy ", ": ")
      .replace(":ref ", ": ")
      .replace(":lazy ", ": ")
    )
    if soft != body:
      candidates.append(soft)
  for text in candidates:
    try:
      ast.parse(f"def __paw_indent_probe():\n{text}", mode="exec")
      return True
    except SyntaxError:
      continue
  return False


def _dedent_and_indent(body: str, indent: str = "  ") -> str:
  """统一函数体缩进。Lexer 的 INDENT 令牌会吃掉首行物理空白，需补齐再 dedent。

  首行被吃空白后，后续行仍可能是文件绝对缩进；复合句块体 vs 兄弟句的
  ``pad`` 量不唯一，故对候选 pad 做 ``ast.parse`` 探测，取第一个合法结果。
  """
  lines = body.replace("\r\n", "\n").split("\n")
  while lines and not lines[-1].strip():
    lines.pop()
  nonempty_idx = [i for i, ln in enumerate(lines) if ln.strip()]
  if not nonempty_idx:
    return indent + "pass\n"
  base_indents = [len(lines[i]) - len(lines[i].lstrip(" \t")) for i in nonempty_idx]
  fi = nonempty_idx[0]
  pad_candidates: list[int] = [0]
  if base_indents[0] == 0 and any(x > 0 for x in base_indents[1:]):
    m = min(x for x in base_indents[1:] if x > 0)
    pad_candidates = [m, 0]
    first = lines[fi].rstrip()
    if first.endswith(":"):
      levels = sorted({x for x in base_indents[1:] if x > 0})
      if len(levels) >= 2:
        step = min(levels[i + 1] - levels[i] for i in range(len(levels) - 1))
        if step > 0:
          # 优先兄弟级 pad=m（``if``/``with`` 后还有同级句）；再试纯块体 m-step
          pad_candidates = [m, max(0, m - step), 0]
      else:
        pad_candidates = [0, m]

  def _render(pad: int) -> str:
    work = list(lines)
    indents = list(base_indents)
    if pad > 0 and indents[0] == 0:
      work[fi] = (" " * pad) + work[fi]
      indents[0] = pad
    min_i = min(indents)
    out: list[str] = []
    for ln in work:
      if not ln.strip():
        out.append("")
      else:
        raw_i = len(ln) - len(ln.lstrip(" \t"))
        cut = min(min_i, raw_i)
        out.append(indent + ln[cut:])
    return "\n".join(out) + "\n"

  seen: set[int] = set()
  for pad in pad_candidates:
    if pad in seen:
      continue
    seen.add(pad)
    text = _render(pad)
    if _body_parses(text):
      return text
  return _render(pad_candidates[0])


def _type_to_legacy_annotation(typ: str | None) -> str | None:
  """Paw 类型表面 → 物化用 ``Function``/``Callable`` Subscript。"""
  if typ is None or not typ.strip():
    return typ
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.source import FileId
  from compiler.py.frontend.surface_rewrite import rewrite_type_prefixes_fragment
  from compiler.py.frontend.type_parse import parse_type, type_syntax_to_legacy_annotation

  src = typ.strip()
  tokens = Lexer(src, FileId(0)).tokenize()
  ty, _ = parse_type(tokens, 0, source=src)
  if ty is not None:
    return rewrite_type_prefixes_fragment(type_syntax_to_legacy_annotation(ty))
  return rewrite_type_prefixes_fragment(src)


def _params_to_legacy_source(item: MidFunction) -> str:
  from compiler.py.frontend.surface_rewrite import rewrite_type_prefixes_fragment

  if item.params:
    parts: list[str] = []
    for p in item.params:
      if p.is_kwarg:
        s = f"**{p.name}"
      elif p.is_vararg:
        s = f"*{p.name}"
      else:
        s = p.name
      if p.type_syntax is not None:
        from compiler.py.frontend.type_parse import type_syntax_to_legacy_annotation
        from compiler.py.frontend.surface_rewrite import rewrite_type_prefixes_fragment as _r

        s += f": {_r(type_syntax_to_legacy_annotation(p.type_syntax))}"
      if p.default_source is not None:
        s += f" = {p.default_source}"
      parts.append(s)
    return ", ".join(parts)
  return rewrite_type_prefixes_fragment(item.params_source or "")


def _function_source(item: MidFunction) -> str:
  deco = item.decorators_source.strip()
  head = "async def" if item.is_async else "def"
  params = _params_to_legacy_source(item)
  if item.return_source:
    ret_src = _type_to_legacy_annotation(item.return_source) or item.return_source
  else:
    ret_src = ""
  ret = f" -> {ret_src}" if ret_src else ""
  tp = item.type_params_source or ""
  if item.is_delegate or item.is_native:
    body = "  ...\n"
  else:
    body = _rewrite_body_type_prefixes(
      _dedent_and_indent(item.body_source or "pass")
    )
    if not body.endswith("\n"):
      body += "\n"
  text = ""
  extra: list[str] = []
  if item.is_delegate:
    extra.append("@delegate")
  if item.is_property:
    extra.append("@staticproperty" if item.is_static else "@property")
  elif item.is_static:
    extra.append("@staticmethod")
  if item.is_native:
    extra.append("@native")
  if item.is_final:
    extra.append("@final")
  if item.is_override:
    extra.append("@override")
  if item.is_abstract:
    extra.append("@abstract")
  if item.is_virtual:
    extra.append("@virtual")
  for line in extra:
    text += line + "\n"
  if deco and not item.is_delegate:
    for dline in deco.splitlines():
      s = dline.strip()
      if s and s != "@delegate":
        text += s + "\n"
  text += f"{head} {item.name}{tp}({params}){ret}:\n"
  text += body
  if not text.endswith("\n"):
    text += "\n"
  return text


def _function_stmts(item: MidFunction, filename: str) -> list[ast.stmt]:
  return _parse_stmts(_function_source(item), filename)


def _unparse_stmt(node: ast.AST) -> str:
  ast.fix_missing_locations(node)
  text = ast.unparse(node)
  if not text.endswith("\n"):
    text += "\n"
  return text
