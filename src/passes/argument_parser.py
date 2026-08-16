"""``ArgumentParserMixin.parse[T]`` → ``T.parse``；带 ``*ArgMeta`` 的 dataclass 注入 ``parse``。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, has_named_decorator, is_optional_type_annotation
from ..translation_error import raise_translation_error

if TYPE_CHECKING:
  from ..translator import Translator

_POS = "PosArgMeta"
_OPT = "OptArgMeta"
_FLAG = "FlagArgMeta"
_SKIP_NAMES = frozenset({_POS, _OPT, _FLAG, "ArgumentParserMixin", "ArgParserIO"})


@dataclass
class _ArgField:
  name: str
  kind: str
  type_name: str
  default: ast.expr | None
  meta: ast.expr
  node: ast.AST


def _meta_name(expr: ast.expr) -> str | None:
  if isinstance(expr, ast.Name):
    return expr.id
  if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
    return expr.func.id
  return None


def _ann_base_and_metas(ann: ast.expr) -> tuple[ast.expr, list[ast.expr]]:
  metas: list[ast.expr] = []
  cur = ann
  while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.MatMult):
    metas.append(cur.right)
    cur = cur.left
  return cur, metas


def _meta_for(metas: list[ast.expr], want: str) -> ast.expr | None:
  for m in metas:
    if _meta_name(m) == want:
      return m
  return None


def _meta_kw(meta: ast.expr, key: str) -> ast.expr | None:
  if not isinstance(meta, ast.Call):
    return None
  for kw in meta.keywords:
    if kw.arg == key:
      return kw.value
  return None


def _const_str(expr: ast.expr | None) -> str:
  if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
    return expr.value
  return ""


def _const_bool(expr: ast.expr | None) -> bool:
  return isinstance(expr, ast.Constant) and expr.value is True


def _snake_to_kebab(name: str) -> str:
  return name.replace("_", "-")


def _type_name(ann: ast.expr) -> str:
  if isinstance(ann, ast.Name):
    return ann.id
  return ast.unparse(ann)


def _default_lit(type_name: str) -> str:
  if type_name in ("int", "int64"):
    return "0"
  if type_name in ("float", "float64"):
    return "0.0"
  if type_name == "bool":
    return "False"
  return '""'


def _convert_expr(type_name: str, raw_var: str) -> str:
  if type_name in ("int", "int64"):
    return f"int({raw_var})"
  if type_name in ("float", "float64"):
    return f"float({raw_var})"
  if type_name == "bool":
    return f'({raw_var} == "1" or {raw_var} == "true" or {raw_var} == "True")'
  return raw_var


def _choices_list(meta: ast.expr) -> list[str]:
  expr = _meta_kw(meta, "choices")
  if expr is None:
    return []
  elts: list[ast.expr] = []
  if isinstance(expr, ast.List):
    elts = list(expr.elts)
  elif isinstance(expr, ast.Tuple):
    elts = list(expr.elts)
  out: list[str] = []
  for elt in elts:
    if isinstance(elt, ast.Constant):
      out.append(str(elt.value))
  return out


def _parse_method(src: str) -> ast.FunctionDef:
  mod = ast.parse(src)
  if len(mod.body) != 1 or not isinstance(mod.body[0], ast.FunctionDef):
    raise ValueError("argument_parser: 期望单个 FunctionDef")
  return mod.body[0]


def _register_method(info: ClassInfo, fn: ast.FunctionDef) -> None:
  fn.decorator_list = [ast.Name(id="staticmethod", ctx=ast.Load())]
  ast.fix_missing_locations(fn)
  info.methods[fn.name] = fn
  info.node.body = [
    stmt
    for stmt in info.node.body
    if not (
      isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == fn.name
    )
  ]
  info.node.body.append(fn)
  info._collect_fields(fn)


def _error(
  tr: Translator,
  node: ast.AST | None,
  message: str,
  *,
  module_path: str | None = None,
) -> None:
  raise_translation_error(tr, node, message, module_path=module_path)


def _collect_arg_fields(tr: Translator, info: ClassInfo) -> list[_ArgField]:
  out: list[_ArgField] = []
  longs: dict[str, str] = {}
  shorts: dict[str, str] = {}
  for stmt in info.node.body:
    if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
      continue
    name = stmt.target.id
    if name.startswith("_"):
      continue
    base, metas = _ann_base_and_metas(stmt.annotation)
    kinds = [k for k in (_POS, _OPT, _FLAG) if _meta_for(metas, k) is not None]
    if not kinds:
      continue
    if len(kinds) > 1:
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: 同一字段至多一个 PosArgMeta/OptArgMeta/FlagArgMeta",
        module_path=info.module_path,
      )
    kind = kinds[0]
    meta = _meta_for(metas, kind)
    assert meta is not None
    tip = _type_name(base)
    if kind == _FLAG and tip != "bool":
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: FlagArgMeta 仅允许 bool，得到 {tip}",
        module_path=info.module_path,
      )
    if kind == _OPT and tip == "bool":
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: OptArgMeta 不能标在 bool（请用 FlagArgMeta）",
        module_path=info.module_path,
      )
    default = stmt.value
    if kind == _POS and default is not None:
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: 首版 PosArgMeta 不支持默认值",
        module_path=info.module_path,
      )
    if kind == _OPT and default is None:
      if not is_optional_type_annotation(stmt.annotation):
        _error(
          tr,
          stmt,
          f"{info.name}.{name}: OptArgMeta 须有默认值或 @optional",
          module_path=info.module_path,
        )
    long_name = "--" + _snake_to_kebab(name)
    if kind == _FLAG and _const_bool(_meta_kw(meta, "negated")):
      long_name = "--no-" + _snake_to_kebab(name)
    if long_name in longs:
      _error(
        tr,
        stmt,
        f"{info.name}.{name}: 长选项 {long_name} 与 {longs[long_name]} 冲突",
        module_path=info.module_path,
      )
    longs[long_name] = name
    short = _const_str(_meta_kw(meta, "short"))
    if short:
      if not (len(short) == 2 and short[0] == "-"):
        _error(
          tr,
          stmt,
          f"{info.name}.{name}: short 须形如 -x，得到 {short!r}",
          module_path=info.module_path,
        )
      if short in shorts:
        _error(
          tr,
          stmt,
          f"{info.name}.{name}: 短选项 {short} 与 {shorts[short]} 冲突",
          module_path=info.module_path,
        )
      shorts[short] = name
    out.append(
      _ArgField(
        name=name,
        kind=kind,
        type_name=tip,
        default=default,
        meta=meta,
        node=stmt,
      )
    )
  return out


def _ensure_mixin_base(info: ClassInfo) -> None:
  if "ArgumentParserMixin" in info.bases:
    return
  info.bases.insert(0, "ArgumentParserMixin")
  info.node.bases.insert(0, ast.Name(id="ArgumentParserMixin", ctx=ast.Load()))


def _usage_text(info: ClassInfo, fields: list[_ArgField]) -> str:
  parts: list[str] = [f"usage: {info.name}"]
  for f in fields:
    kebab = _snake_to_kebab(f.name)
    if f.kind == _POS:
      parts.append(f"<{f.name}>")
    elif f.kind == _OPT:
      parts.append(f"[--{kebab} VALUE]")
    elif _const_bool(_meta_kw(f.meta, "negated")):
      parts.append(f"[--no-{kebab}]")
    else:
      parts.append(f"[--{kebab}]")
  return " ".join(parts)


def _emit_help_text_method(info: ClassInfo, fields: list[_ArgField]) -> None:
  """注入常量 ``helpText``，避免 mixin 反射版在宿主上展开失败。"""
  usage = _usage_text(info, fields).replace("\\", "\\\\").replace('"', '\\"')
  src = f'''
@staticmethod
def helpText() -> str:
  return "{usage}"
'''
  _register_method(info, _parse_method(src))


def _emit_parse_method(info: ClassInfo, fields: list[_ArgField]) -> None:
  usage = _usage_text(info, fields).replace("\\", "\\\\").replace('"', '\\"')
  cls = info.name
  init_lines: list[str] = []
  new_args: list[str] = []
  for f in fields:
    if f.default is not None:
      init_lines.append(f"  {f.name}_v: {f.type_name} = {ast.unparse(f.default)}")
    elif f.kind == _FLAG:
      init_lines.append(f"  {f.name}_v: bool = False")
    else:
      init_lines.append(f"  {f.name}_v: {f.type_name} = {_default_lit(f.type_name)}")
    new_args.append(f"{f.name}={f.name}_v")

  flag_shorts: list[tuple[str, str, bool]] = []
  opt_branches: list[str] = []
  for f in fields:
    kebab = _snake_to_kebab(f.name)
    short = _const_str(_meta_kw(f.meta, "short"))
    if f.kind == _FLAG:
      negated = _const_bool(_meta_kw(f.meta, "negated"))
      tok = f"--no-{kebab}" if negated else f"--{kebab}"
      val = "False" if negated else "True"
      opt_branches.append(
        f'      if key == "{tok}":\n'
        f"        {f.name}_v = {val}\n"
        f"        matched = True\n"
        f"        consume = False"
      )
      if short:
        opt_branches.append(
          f'      if key == "{short}":\n'
          f"        {f.name}_v = {val}\n"
          f"        matched = True\n"
          f"        consume = False"
        )
        flag_shorts.append((short[1:], f.name, negated))
    elif f.kind == _OPT:
      conv = _convert_expr(f.type_name, "raw")
      choices = _choices_list(f.meta)
      choice_check = ""
      if choices:
        lit = ", ".join(f'"{c}"' for c in choices)
        choice_check = (
          f"        if raw not in [{lit}]:\n"
          f'          ArgParserIO.fail("invalid choice for --{kebab}: " + raw, "{usage}")\n'
        )
      body = (
        f"        if (not has_raw):\n"
        f'          ArgParserIO.fail("missing value for --{kebab}", "{usage}")\n'
        f"{choice_check}"
        f"        {f.name}_v = {conv}\n"
        f"        matched = True\n"
        f"        consume = not from_eq"
      )
      opt_branches.append(f'      if key == "--{kebab}":\n{body}')
      if short:
        opt_branches.append(f'      if key == "{short}":\n{body}')

  combo_lines: list[str] = []
  for ch, fname, negated in flag_shorts:
    val = "False" if negated else "True"
    combo_lines.append(
      f'          if ch == "{ch}":\n'
      f"            {fname}_v = {val}\n"
      f"            found_ch = True"
    )
  combo_block = "\n".join(combo_lines) if combo_lines else "          pass"

  pos_names = [f.name for f in fields if f.kind == _POS]
  pos_assign: list[str] = []
  for idx, pname in enumerate(pos_names):
    f = next(x for x in fields if x.name == pname)
    conv = _convert_expr(f.type_name, "tok")
    pos_assign.append(
      f"    if _pos == {idx}:\n"
      f"      {pname}_v = {conv}\n"
      f"      _pos += 1\n"
      f"      used_pos = True"
    )
  pos_block = "\n".join(pos_assign) if pos_assign else "    pass"
  opt_block = "\n".join(opt_branches) if opt_branches else "      pass"

  src = f"""
@staticmethod
def parse(argv: list[str] | None = None) -> Self:
{chr(10).join(init_lines)}
  args: list[str] = ArgParserIO.resolveArgv(argv)
  n: int = len(args)
  _pos: int = 0
  _opts_done: bool = False
  skip_next: bool = False
  for i in range(n):
    if skip_next:
      skip_next = False
      continue
    tok: str = args[i]
    if (not _opts_done) and tok == "--":
      _opts_done = True
      continue
    if (not _opts_done) and tok in {{"--help", "-h"}}:
      ArgParserIO.showHelp("{usage}")
    if (not _opts_done) and tok.startsWith("-") and tok != "-":
      key: str = tok
      raw: str = ""
      has_raw: bool = False
      from_eq: bool = False
      before, sep, after = tok.partition("=")
      if sep == "=":
        key = before
        raw = after
        has_raw = True
        from_eq = True
      elif (i + 1) < n:
        nxt: str = args[i + 1]
        take_val: bool = (not nxt.startsWith("-")) or nxt == "-"
        if (not take_val) and len(nxt) >= 2:
          dch: str = nxt[1:2]
          if dch >= "0" and dch <= "9":
            take_val = True
        if take_val:
          raw = nxt
          has_raw = True
      matched: bool = False
      consume: bool = False
{opt_block}
      if matched:
        if consume:
          skip_next = True
        continue
      if (not tok.startsWith("--")) and len(tok) > 2 and (not from_eq):
        combo_ok: bool = True
        for k in range(1, len(tok)):
          ch: str = tok[k:k + 1]
          found_ch: bool = False
{combo_block}
          if not found_ch:
            combo_ok = False
        if combo_ok:
          continue
      ArgParserIO.fail("unknown option " + tok, "{usage}")
    used_pos: bool = False
{pos_block}
    if not used_pos:
      ArgParserIO.fail("unexpected positional " + tok, "{usage}")
  if _pos < {len(pos_names)}:
    ArgParserIO.fail("missing positional argument", "{usage}")
  return new({", ".join(new_args)})
"""
  _register_method(info, _parse_method(src))


def _is_parse_subscript_call(node: ast.expr) -> tuple[str, ast.Call] | None:
  if not isinstance(node, ast.Call):
    return None
  func = node.func
  if not isinstance(func, ast.Subscript):
    return None
  if not isinstance(func.value, ast.Attribute) or func.value.attr != "parse":
    return None
  recv = func.value.value
  if isinstance(recv, ast.Name):
    if recv.id != "ArgumentParserMixin":
      return None
  elif isinstance(recv, ast.Attribute) and recv.attr == "ArgumentParserMixin":
    pass
  else:
    return None
  sl = func.slice
  if not isinstance(sl, ast.Name):
    return None
  return sl.id, node


class _RewriteParseCalls(ast.NodeTransformer):
  def visit_Call(self, node: ast.Call) -> ast.AST:
    self.generic_visit(node)
    parsed = _is_parse_subscript_call(node)
    if parsed is None:
      return node
    _type_name, call = parsed
    # 有类型上下文时 ``new.parse(...)``（S06b）；``ArgumentParserMixin.parse[T]`` 的 ``T`` 已由注解/返回类型给出。
    return ast.Call(
      func=ast.Attribute(
        value=ast.Name(id="new", ctx=ast.Load()),
        attr="parse",
        ctx=ast.Load(),
      ),
      args=list(call.args),
      keywords=list(call.keywords),
    )


def expand_argument_parser(tr: Translator) -> None:
  """为带 ``*ArgMeta`` 的 dataclass 注入 ``parse``；改写 ``ArgumentParserMixin.parse[T]``。"""
  for info in list(tr.classes.values()):
    if info.name in _SKIP_NAMES or info.is_mixin or info.is_annotation:
      continue
    if not has_named_decorator(info.node, "dataclass"):
      fields_any = _collect_arg_fields(tr, info)
      if fields_any:
        _error(
          tr,
          info.node,
          f"{info.name}: 带 PosArgMeta/OptArgMeta/FlagArgMeta 的类须为 @dataclass",
          module_path=info.module_path,
        )
      continue
    fields = _collect_arg_fields(tr, info)
    if not fields:
      continue
    _ensure_mixin_base(info)
    has_parse = any(
      isinstance(stmt, ast.FunctionDef) and stmt.name == "parse"
      for stmt in info.node.body
    )
    if not has_parse:
      _emit_parse_method(info, fields)
    has_help = any(
      isinstance(stmt, ast.FunctionDef) and stmt.name == "helpText"
      for stmt in info.node.body
    )
    if not has_help:
      _emit_help_text_method(info, fields)

  rewriter = _RewriteParseCalls()
  for tree in tr.module_asts.values():
    rewriter.visit(tree)
  for info in tr.classes.values():
    for method in list(info.methods.values()):
      rewriter.visit(method)
    for overloads in info.method_overloads.values():
      for method in overloads:
        rewriter.visit(method)
    for init in info.inits:
      rewriter.visit(init)
  for _mp, fn in tr.module_functions:
    rewriter.visit(fn)
