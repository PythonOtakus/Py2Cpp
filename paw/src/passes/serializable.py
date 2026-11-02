"""``@serializable``：为 ``@dataclass`` / ``@union`` 生成 ``serialize`` / ``deserialize``。"""
from __future__ import annotations

import ast
import copy
import textwrap
from typing import TYPE_CHECKING

from ..analysis.ir import ClassInfo, UnionVariantInfo, has_named_decorator
from ..analysis.module_namespace import (
  inl_namespace_segments,
  qualify_symbol_in_module,
)
from .dataclass_expand import DataclassFieldSpec, _collect_dataclass_fields

if TYPE_CHECKING:
  from ..translator import Translator

SERIALIZABLE_DECORATOR = "serializable"
_STATICMETHOD_DEC = ast.Name(id="staticmethod", ctx=ast.Load())


def _is_serializable_decorator(dec: ast.expr) -> bool:
  if isinstance(dec, ast.Name) and dec.id == SERIALIZABLE_DECORATOR:
    return True
  return (
    isinstance(dec, ast.Call)
    and isinstance(dec.func, ast.Name)
    and dec.func.id == SERIALIZABLE_DECORATOR
  )


def _json_key_const_name(
  class_name: str, field: str, *, variant: str | None = None,
) -> str:
  if variant is not None:
    return f"__json_key_{class_name}_{variant}_{field}"
  return f"__json_key_{class_name}_{field}"


def _ensure_json_key_const(
  tr: Translator,
  info: ClassInfo,
  field: str,
  *,
  variant: str | None = None,
) -> str:
  """模块级 ``str`` 常量，避免 ``serialize`` 热路径反复构造 ``PyStr("field")``。"""
  const_name = _json_key_const_name(info.name, field, variant=variant)
  for mp, node in tr.module_constants:
    if mp == info.module_path and isinstance(node.target, ast.Name):
      if node.target.id == const_name:
        return const_name
  tree = tr.module_asts.get(info.module_path)
  if tree is None:
    return repr(field)
  ann = ast.AnnAssign(
    target=ast.Name(id=const_name, ctx=ast.Store()),
    annotation=ast.Name(id="str", ctx=ast.Load()),
    value=ast.Constant(value=field),
    simple=1,
  )
  ast.fix_missing_locations(ann)
  if tree is not None:
    tree.body.insert(0, ann)
  tr.module_constants.append((info.module_path, ann))
  return const_name


def _strip_serializable_decorators(node: ast.ClassDef) -> None:
  node.decorator_list = [
    dec for dec in node.decorator_list if not _is_serializable_decorator(dec)
  ]


def _parse_method(src: str) -> ast.FunctionDef:
  dedented = textwrap.dedent(src)
  mod = ast.parse(dedented)
  if len(mod.body) != 1 or not isinstance(mod.body[0], ast.FunctionDef):
    raise SyntaxError(
      f"@serializable generated invalid method AST ({len(mod.body)} top-level nodes):\n"
      f"{dedented}"
    )
  fn = mod.body[0]
  ast.fix_missing_locations(fn)
  return fn


def _register_method(info: ClassInfo, method: ast.FunctionDef) -> None:
  info.methods[method.name] = method
  info.node.body.append(method)
  info._collect_fields(method)


def _ann_name(ann: ast.expr) -> str | None:
  if isinstance(ann, ast.Name):
    return ann.id
  return None


def _ann_list_elem(ann: ast.expr) -> str | None:
  if not isinstance(ann, ast.Subscript) or not isinstance(ann.value, ast.Name):
    return None
  if ann.value.id != "list":
    return None
  sl = ann.slice
  if isinstance(sl, ast.Name):
    return sl.id
  if isinstance(sl, ast.Tuple) and sl.elts:
    first = sl.elts[0]
    if isinstance(first, ast.Name):
      return first.id
  return None


def _ann_dict_value(ann: ast.expr) -> str | None:
  if not isinstance(ann, ast.Subscript) or not isinstance(ann.value, ast.Name):
    return None
  if ann.value.id != "dict":
    return None
  sl = ann.slice
  if isinstance(sl, ast.Name):
    return sl.id
  if isinstance(sl, ast.Tuple) and len(sl.elts) >= 2:
    val = sl.elts[1]
    if isinstance(val, ast.Name):
      return val.id
  return None


def _serializable_class(tr: Translator, name: str) -> str | None:
  info = tr.classes.get(name)
  if info is None:
    return None
  if info.is_serializable or has_named_decorator(info.node, SERIALIZABLE_DECORATOR):
    return name
  return None


def _load_fast_field_body(
  decoder: str, ann: ast.expr, target: str, prefix: str,
) -> str | None:
  """``load_key`` 之后：一次 ``skipSpaces`` + 原位解析（避免 ``load_bool`` 等 list 缓冲）。"""
  if isinstance(ann, ast.Name):
    if ann.id == "bool":
      return (
        f"{prefix}{decoder}.skipSpaces()\n"
        f"{prefix}{target} = {decoder}.parseBoolAt()"
      )
    if ann.id == "int":
      return (
        f"{prefix}{decoder}.skipSpaces()\n"
        f"{prefix}{target} = {decoder}.parseIntAt()"
      )
    if ann.id == "long":
      return (
        f"{prefix}{decoder}.skipSpaces()\n"
        f"{prefix}{target} = {decoder}.parseLongAt()"
      )
    if ann.id == "str":
      return f"{prefix}{target} = {decoder}.loadStr()"
  elem = _ann_list_elem(ann)
  if elem == "int":
    return (
      f"{prefix}{decoder}.skipSpaces()\n"
      f"{prefix}{target} = {decoder}.loadListIntValue()"
    )
  if elem == "long":
    return (
      f"{prefix}{decoder}.skipSpaces()\n"
      f"{prefix}{target} = {decoder}.loadListLongValue()"
    )
  if elem == "str":
    return (
      f"{prefix}{decoder}.skipSpaces()\n"
      f"{prefix}{target} = {decoder}.loadListStrValue()"
    )
  if elem == "float":
    return (
      f"{prefix}{decoder}.skipSpaces()\n"
      f"{prefix}{target} = {decoder}.loadListFloatValue()"
    )
  return None


def _dump_fast_field_line(
  tr: Translator, ann: ast.expr, key: str, access: str, encoder: str,
) -> str | None:
  if isinstance(ann, ast.Name):
    if ann.id == "bool":
      return f"{encoder}.dumpFieldBool({key}, {access})"
    if ann.id == "int":
      return f"{encoder}.dumpFieldInt({key}, {access})"
    if ann.id == "long":
      return f"{encoder}.dumpFieldLong({key}, {access})"
    if ann.id in ("float", "float64"):
      return None
    if ann.id == "str":
      return f"{encoder}.dumpFieldStr({key}, {access})"
  elem = _ann_list_elem(ann)
  if elem == "int":
    return f"{encoder}.dumpFieldListInt({key}, {access})"
  if elem == "long":
    return f"{encoder}.dumpFieldListLong({key}, {access})"
  if elem == "str":
    return f"{encoder}.dumpFieldListStr({key}, {access})"
  if elem == "float":
    return f"{encoder}.dumpFieldListFloat({key}, {access})"
  return None


def _dump_scalar(ann: ast.expr, access: str, encoder: str) -> str | None:
  if isinstance(ann, ast.Name):
    if ann.id == "bool":
      return f"{encoder}.dumpBool({access})"
    if ann.id == "int":
      return f"{encoder}.dumpInt({access})"
    if ann.id == "long":
      return f"{encoder}.dumpLong({access})"
    if ann.id in ("float", "float64"):
      return f"{encoder}.dumpFloat({access})"
    if ann.id == "str":
      return f"{encoder}.dumpStr({access})"
    if ann.id == "PyNone":
      return f"{encoder}.dumpStr({access})"
  return None


def _dump_field_lines(
  tr: Translator, ann: ast.expr, access: str, encoder: str,
) -> list[str]:
  scalar = _dump_scalar(ann, access, encoder)
  if scalar is not None:
    return [scalar]

  if isinstance(ann, ast.Name):
    cls = _serializable_class(tr, ann.id)
    if cls is not None:
      return [f"{access}.serialize({encoder})"]

  elem = _ann_list_elem(ann)
  if elem is not None:
    if elem == "int":
      return [f"{encoder}.dumpListInt({access})"]
    if elem == "long":
      return [f"{encoder}.dumpListLong({access})"]
    if elem == "str":
      return [f"{encoder}.dumpListStr({access})"]
    if elem == "float":
      return [f"{encoder}.dumpListFloat({access})"]
    if elem == "bool":
      raise NotImplementedError("list[bool] serialize")
    cls = _serializable_class(tr, elem)
    if cls is not None:
      return [
        f"{encoder}.push({encoder}.sep)",
        f"{encoder}.beginArray()",
        f"_n = len({access})",
        f"for _i in range(_n):",
        f"  {access}[_i].serialize({encoder})",
        f"{encoder}.endArray()",
        f"{encoder}.sep = {encoder}.commaSep()",
      ]

  val_t = _ann_dict_value(ann)
  if val_t is not None:
    if val_t == "int":
      return [f"{encoder}.dumpDictStrInt({access})"]
    if val_t == "long":
      return [f"{encoder}.dumpDictStrLong({access})"]
    if val_t == "str":
      return [f"{encoder}.dumpDictStrStr({access})"]
    if val_t == "float":
      return [f"{encoder}.dumpDictStrFloat({access})"]
    if val_t == "bool":
      raise NotImplementedError("dict[str, bool] serialize")
    cls = _serializable_class(tr, val_t)
    if cls is not None:
      return [
        f"{encoder}.push({encoder}.sep)",
        f'{encoder}.push("{{")',
        f'{encoder}.sep = ""',
        f"_n = len({access})",
        f"for _i in range(_n):",
        f"  if _i > 0:",
        f'    {encoder}.push(",")',
        f"  {encoder}.push(JsonEncoder.encodeStr({access}.keyAt(_i)))",
        f'  {encoder}.push(":")',
        f'  {encoder}.sep = ""',
        f"  {access}.valueAt(_i).serialize({encoder})",
        f"  {encoder}.sep = {encoder}.commaSep()",
        f'{encoder}.push("}}")',
        f"{encoder}.sep = {encoder}.commaSep()",
      ]

  raise NotImplementedError(f"@serializable: 不支持的字段类型 {ast.dump(ann)}")


def _load_scalar_branch(
  tr: Translator,
  info: ClassInfo,
  field_name: str,
  ann: ast.expr,
  target: str,
  decoder: str,
  *,
  elif_: bool,
  indent: str,
  variant: str | None = None,
) -> str | None:
  key = _ensure_json_key_const(tr, info, field_name, variant=variant)
  kw = "elif" if elif_ else "if"
  body = indent + "  "
  fast_body = _load_fast_field_body(decoder, ann, target, body)
  if isinstance(ann, ast.Name):
    if ann.id in ("float", "float64"):
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        f"{body}{target} = {decoder}.loadFloat()"
      )
    if fast_body is not None:
      return f"{indent}{kw} {decoder}.tryMatchKey({key}):\n{fast_body}"
  return None


def _load_list_serializable_body(
  cls: str, target: str, decoder: str, body: str,
) -> str:
  return (
    f"{body}{target}: list[{cls}] = []\n"
    f"{body}{decoder}.beginArray()\n"
    f"{body}{decoder}.skipSpaces()\n"
    f"{body}if not {decoder}.atArrayEnd():\n"
    f"{body}  while True:\n"
    f"{body}    {target}.append({cls}.deserialize({decoder}))\n"
    f"{body}    {decoder}.skipSpaces()\n"
    f"{body}    if {decoder}.atArrayEnd():\n"
    f"{body}      break\n"
    f"{body}    {decoder}.expectChar(',')\n"
    f"{body}    {decoder}.skipSpaces()"
  )


def _load_dict_serializable_body(
  cls: str, target: str, decoder: str, body: str,
) -> str:
  inner = body + "  "
  return (
    f"{body}{target} = dict()\n"
    f"{body}{decoder}.skipSpaces()\n"
    f"{body}{decoder}.expectChar('{{')\n"
    f"{body}{decoder}.skipSpaces()\n"
    f"{body}while not {decoder}.atObjectEnd():\n"
    f"{inner}_k: str = {decoder}.readQuoted()\n"
    f"{inner}{decoder}.skipSpaces()\n"
    f"{inner}{decoder}.expectChar(':')\n"
    f"{inner}{target}[_k] = {cls}.deserialize({decoder})\n"
    f"{inner}{decoder}.skipSpaces()\n"
    f"{inner}if not {decoder}.atObjectEnd():\n"
    f"{inner}  {decoder}.expectChar(',')\n"
    f"{inner}  {decoder}.skipSpaces()"
  )


def _load_field_branch(
  tr: Translator,
  info: ClassInfo,
  ann: ast.expr,
  field_name: str,
  target: str,
  decoder: str,
  *,
  elif_: bool,
  indent: str = "    ",
  variant: str | None = None,
) -> str:
  scalar = _load_scalar_branch(
    tr, info, field_name, ann, target, decoder,
    elif_=elif_, indent=indent, variant=variant,
  )
  if scalar is not None:
    return scalar

  key = _ensure_json_key_const(tr, info, field_name, variant=variant)
  kw = "elif" if elif_ else "if"
  body = indent + "  "

  if isinstance(ann, ast.Name):
    cls = _serializable_class(tr, ann.id)
    if cls is not None:
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        f"{body}{target} = {cls}.deserialize({decoder})"
      )

  elem = _ann_list_elem(ann)
  if elem is not None:
    fast_list = _load_fast_field_body(decoder, ann, target, body)
    if elem == "int" and fast_list is not None:
      return f"{indent}{kw} {decoder}.tryMatchKey({key}):\n{fast_list}"
    if elem == "long" and fast_list is not None:
      return f"{indent}{kw} {decoder}.tryMatchKey({key}):\n{fast_list}"
    if elem == "str" and fast_list is not None:
      return f"{indent}{kw} {decoder}.tryMatchKey({key}):\n{fast_list}"
    if elem == "float" and fast_list is not None:
      return f"{indent}{kw} {decoder}.tryMatchKey({key}):\n{fast_list}"
    cls = _serializable_class(tr, elem)
    if cls is not None:
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        + _load_list_serializable_body(cls, target, decoder, body)
      )

  val_t = _ann_dict_value(ann)
  if val_t is not None:
    if val_t == "int":
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        f"{body}{target} = {decoder}.loadDictStrInt()"
      )
    if val_t == "long":
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        f"{body}{target} = {decoder}.loadDictStrLong()"
      )
    if val_t == "str":
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        f"{body}{target} = {decoder}.loadDictStrStr()"
      )
    if val_t == "float":
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        f"{body}{target} = {decoder}.loadDictStrFloat()"
      )
    cls = _serializable_class(tr, val_t)
    if cls is not None:
      return (
        f"{indent}{kw} {decoder}.tryMatchKey({key}):\n"
        + _load_dict_serializable_body(cls, target, decoder, body)
      )

  raise NotImplementedError(f"@serializable: 不支持的字段类型 {ast.dump(ann)}")


def _type_hint(ann: ast.expr) -> str:
  if isinstance(ann, ast.Name):
    return ann.id
  if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
    if isinstance(ann.slice, ast.Name):
      return f"{ann.value.id}[{ann.slice.id}]"
    if isinstance(ann.slice, ast.Tuple):
      parts: list[str] = []
      for el in ann.slice.elts:
        if isinstance(el, ast.Name):
          parts.append(el.id)
      return f"{ann.value.id}[{', '.join(parts)}]"
  return "int"


def _default_init(spec: DataclassFieldSpec, tr: Translator) -> str:
  return _default_for_ann(spec.annotation, tr)


def _default_for_ann(ann: ast.expr, tr: Translator | None = None) -> str:
  if isinstance(ann, ast.Name):
    if ann.id == "bool":
      return "False"
    if ann.id == "int":
      return "0"
    if ann.id == "long":
      return 'long("")'
    if ann.id == "str":
      return '""'
    if ann.id in ("float", "float64"):
      return "0.0"
    if tr is not None:
      cls = _serializable_class(tr, ann.id)
      if cls is not None:
        return _default_ctor_call(tr, cls)
  if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
    if ann.value.id == "list":
      return "[]"
    if ann.value.id == "dict":
      return "{}"
  return "0"


def _dataclass_specs(tr: Translator, info: ClassInfo) -> list[DataclassFieldSpec]:
  stored = getattr(info, "dataclass_field_specs", None)
  if stored is not None:
    return stored
  return _collect_dataclass_fields(info.node)


def _schema_deserialize_eligible(tr: Translator, specs: list[DataclassFieldSpec]) -> bool:
  """仅标量快字段、无嵌套 serializable / dict / float 时生成有序反序列化。"""
  for spec in specs:
    ann = spec.annotation
    if isinstance(ann, ast.Name):
      if ann.id in ("int", "str", "bool", "long"):
        continue
      if ann.id in ("float", "float64"):
        return False
      if _serializable_class(tr, ann.id) is not None:
        return False
      return False
    if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
      if ann.value.id == "list":
        elem = _ann_list_elem(ann)
        if elem in ("int", "str"):
          continue
        return False
      if ann.value.id == "dict":
        return False
    return False
  return True


def _ordered_field_parse_lines(
  ann: ast.expr, target: str, decoder: str, indent: str,
) -> list[str]:
  """``tryMatchKey`` 成功后、下一键前的解析语句。"""
  body = indent
  if isinstance(ann, ast.Name):
    if ann.id == "int":
      return [
        f"{body}{decoder}.skipSpaces()",
        f"{body}{target} = {decoder}.parseIntAt()",
      ]
    if ann.id == "long":
      return [
        f"{body}{decoder}.skipSpaces()",
        f"{body}{target} = {decoder}.parseLongAt()",
      ]
    if ann.id == "str":
      return [
        f"{body}{target} = str.fromSpan({decoder}.loadStrSpan())",
      ]
    if ann.id == "bool":
      return [
        f"{body}{decoder}.skipSpaces()",
        f"{body}{target} = {decoder}.parseBoolAt()",
      ]
  elem = _ann_list_elem(ann)
  if elem == "str":
    return [
      f"{body}{decoder}.skipSpaces()",
      f"{body}if {decoder}.pos < len({decoder}.s) and {decoder}.s[{decoder}.pos] in '[':",
      f"{body}  if {decoder}.pos + 1 < len({decoder}.s) and {decoder}.s[{decoder}.pos + 1] in ']':",
      f"{body}    {decoder}.skipEmptyArray()",
      f"{body}    {target} = new()",
      f"{body}  else:",
      f"{body}    {target} = {decoder}.loadListStrValue()",
      f"{body}else:",
      f"{body}  {target} = {decoder}.loadListStrValue()",
    ]
  if elem == "int":
    return [
      f"{body}{decoder}.skipSpaces()",
      f"{body}{target} = {decoder}.loadListIntValue()",
    ]
  if elem == "long":
    return [
      f"{body}{decoder}.skipSpaces()",
      f"{body}{target} = {decoder}.loadListLongValue()",
    ]
  return [f"{body}{target} = {decoder}.loadStringSlow()"]


def _make_return_args(specs: list[DataclassFieldSpec], suffix: str = "_v") -> str:
  return ", ".join(f"{spec.name}={spec.name}{suffix}" for spec in specs)


def _build_ordered_deserialize_body(
  tr: Translator,
  info: ClassInfo,
  specs: list[DataclassFieldSpec],
) -> list[str]:
  """生成 ``deserialize`` 内有序快路径（嵌套 ``elif``）+ ``_use_generic`` 回退。"""
  ret = _make_return_args(specs)
  lines: list[str] = [
    "  _use_generic: bool = False",
    "  _mark: int = decoder.mark()",
    "  decoder.beginRootObject()",
    "  decoder.skipSpaces()",
    "  if decoder.atObjectEnd():",
    f"    return new({ret})",
  ]

  def _emit_field_chain(depth: int, start: int) -> None:
    if start >= len(specs):
      return
    spec = specs[start]
    key = _ensure_json_key_const(tr, info, spec.name)
    ind = "  " + "  " * depth
    bi = ind + "  "
    lines.append(f"{ind}elif decoder.tryMatchKey({key}):")
    lines.extend(_ordered_field_parse_lines(spec.annotation, f"{spec.name}_v", "decoder", bi))
    lines.append(f"{bi}decoder.skipSpaces()")
    lines.append(f"{bi}if decoder.atObjectEnd():")
    lines.append(f"{bi}  return new({ret})")
    if start + 1 < len(specs):
      _emit_field_chain(depth + 1, start + 1)
      fail_ind = bi
      lines.append(f"{fail_ind}else:")
      lines.append(f"{fail_ind}  decoder.restore(_mark)")
      lines.append(f"{fail_ind}  _use_generic = True")
    else:
      lines.append(f"{bi}else:")
      lines.append(f"{bi}  decoder.restore(_mark)")
      lines.append(f"{bi}  _use_generic = True")

  _emit_field_chain(0, 0)
  lines.append("  else:")
  lines.append("    decoder.restore(_mark)")
  lines.append("    _use_generic = True")
  lines.append("  if _use_generic:")
  lines.append("    decoder.beginRootObject()")
  return lines


def _cpp_dec_at_char(dec: str, code: int, off: int = 0) -> str:
  """``dec.pos``（及可选偏移）处是否为 ASCII ``code``（经 ``srcChar``，勿 ``PyStr.__getitem__``）。"""
  idx = f"{dec}.pos + {off}" if off else f"{dec}.pos"
  return f"(({idx} < {dec}.srcLen()) && ({dec}.srcChar({idx}) == PyChar({code})))"


def _cpp_parseIntAt_expr(dec: str) -> str:
  """``asciiOk`` 时用 ``parseIntAtAscii``，否则 ``parseIntAt``。"""
  return (
    f"({dec}.asciiOk ? {dec}.parseIntAtAscii()"
    f" : {dec}.parseIntAt())"
  )


def _cpp_inline_expect_key(
  dec: str, field: str, first: bool, fail_return: str,
) -> list[str]:
  """``dumps`` 紧凑形态：首字段 ``"k":``，后续 ``,\"k\":``（无空白）。"""
  checks: list[tuple[int, int]] = []
  off = 0
  if not first:
    checks.append((off, 44))
    off += 1
  checks.append((off, 34))
  off += 1
  for i, c in enumerate(field):
    checks.append((off + i, ord(c)))
  off += len(field)
  checks.append((off, 34))
  off += 1
  checks.append((off, 58))
  off += 1
  total = off
  cond = " && ".join(
    f"({dec}.srcChar({dec}.pos + {o}) == PyChar({code}))" for o, code in checks
  )
  return [
    f"  if (({dec}.pos + {total} > {dec}.srcLen()) || !({cond}))",
    "  {",
    f"    {dec}.fail(PyStr(\"expected field {field}\"));",
    f"    return {fail_return};",
    "  }",
    f"  {dec}.pos += {total};",
  ]


def _cpp_inline_object_open(dec: str, fail_return: str) -> list[str]:
  """游标在 ``{``；消费 ``{`` 或空对象 ``{}``。"""
  return [
    f"  if (!{_cpp_dec_at_char(dec, 123)})",
    "  {",
    f"    {dec}.fail(PyStr(\"expected {{\"));",
    f"    return {fail_return};",
    "  }",
    "  dec.pos += 1;",
    f"  if ({_cpp_dec_at_char(dec, 125)})",
    "  {",
    "    dec.pos += 1;",
    f"    return {fail_return};",
    "  }",
  ]


def _cpp_inline_object_close(dec: str) -> list[str]:
  """严格 ``dumps`` 形态下应为 ``}``；否则跳过未知字段。"""
  return [
    f"  if ({_cpp_dec_at_char(dec, 125)})",
    "  {",
    "    dec.pos += 1;",
    "  }",
    "  else",
    "  {",
    "    dec.skipField();",
    "    while (!dec.atObjectEnd())",
    "    {",
    "      dec.skipField();",
    "    }",
    "  }",
  ]


def _cpp_ordered_field_lines(
  ann: ast.expr,
  target_cpp: str,
  dec: str,
  fail_return: str,
  *,
  str_as_span: bool = False,
) -> list[str]:
  if isinstance(ann, ast.Name):
    if ann.id == "int":
      return [f"  {target_cpp} = {_cpp_parseIntAt_expr(dec)};"]
    if ann.id == "long":
      return [f"  {target_cpp} = {dec}.parseLongAt();"]
    if ann.id == "str":
      if str_as_span:
        return [f"  {target_cpp} = {dec}.loadStrSpan();"]
      return [f"  {target_cpp} = PyStr::fromSpan({dec}.loadStrSpan());"]
    if ann.id == "bool":
      return [
        "  if ((dec.pos + 4 <= dec.srcLen())"
        " && (dec.srcChar(dec.pos) == PyChar(116))"
        " && (dec.srcChar(dec.pos + 1) == PyChar(114))"
        " && (dec.srcChar(dec.pos + 2) == PyChar(117))"
        " && (dec.srcChar(dec.pos + 3) == PyChar(101)))",
        "  {",
        f"    {target_cpp} = true;",
        "    dec.pos += 4;",
        "  }",
        "  else if ((dec.pos + 5 <= dec.srcLen())"
        " && (dec.srcChar(dec.pos) == PyChar(102))"
        " && (dec.srcChar(dec.pos + 1) == PyChar(97))"
        " && (dec.srcChar(dec.pos + 2) == PyChar(108))"
        " && (dec.srcChar(dec.pos + 3) == PyChar(115))"
        " && (dec.srcChar(dec.pos + 4) == PyChar(101)))",
        "  {",
        f"    {target_cpp} = false;",
        "    dec.pos += 5;",
        "  }",
        "  else",
        "  {",
        f"    {dec}.fail(PyStr(\"expected bool\"));",
        f"    return {fail_return};",
        "  }",
      ]
  elem = _ann_list_elem(ann)
  if elem == "str":
    field = target_cpp.removesuffix("_v")
    return [
      f"  if ({_cpp_dec_at_char(dec, 91)})",
      "  {",
      f"    if ({_cpp_dec_at_char(dec, 93, 1)})",
      "    {",
      "      dec.pos += 2;",
      "    }",
      "    else",
      "    {",
      f"      {field}_nonempty = true;",
      f"      {target_cpp} = {dec}.loadListStrValue();",
      "    }",
      "  }",
      "  else",
      "  {",
      f"    {dec}.fail(PyStr(\"expected [\"));",
      f"    return {fail_return};",
      "  }",
    ]
  if elem == "int":
    return [f"  {target_cpp} = {dec}.loadListIntValue();"]
  return []


def _cpp_list_str_fields(specs: list[DataclassFieldSpec]) -> list[DataclassFieldSpec]:
  return [s for s in specs if _ann_list_elem(s.annotation) == "str"]


def _cpp_has_ctor_str_field(specs: list[DataclassFieldSpec]) -> bool:
  return any(
    isinstance(s.annotation, ast.Name) and s.annotation.id == "str"
    for s in specs
  )


def _cpp_fast_from_ordered_name(cpp_cls: str) -> str:
  return f"_{cpp_cls}_fast_from_ordered"


def _cpp_field_target(spec: DataclassFieldSpec, *, str_as_span: bool) -> str:
  if isinstance(spec.annotation, ast.Name) and spec.annotation.id == "str" and str_as_span:
    return f"{spec.name}_seg"
  return f"{spec.name}_v"


def _cpp_ctor_fast_args(specs: list[DataclassFieldSpec]) -> tuple[str, str]:
  """``Cls(id_v, PyStr(\"\"), active_v)`` 用于快路径 ``init``（``str`` 字段另赋）。"""
  id_arg = "0"
  active_arg = "true"
  for spec in specs:
    if not isinstance(spec.annotation, ast.Name):
      continue
    if spec.annotation.id == "int":
      id_arg = f"{spec.name}_v"
    elif spec.annotation.id == "long":
      id_arg = f"{spec.name}_v"
    elif spec.annotation.id == "bool":
      active_arg = f"{spec.name}_v"
  return id_arg, active_arg


def _cpp_str_field_ctor_default(spec: DataclassFieldSpec) -> str:
  if (
    spec.default is not None
    and isinstance(spec.default, ast.Constant)
    and isinstance(spec.default.value, str)
  ):
    return f'PyStr("{spec.default.value}")'
  return 'PyStr("")'


def _cpp_fast_ctor_placeholder_args(specs: list[DataclassFieldSpec]) -> str:
  """快路径 ``init``：标量用 ``_v``，``str`` 用占位（随后 ``strAssignFromSeg``）。"""
  parts: list[str] = []
  for spec in specs:
    if not isinstance(spec.annotation, ast.Name):
      continue
    ann = spec.annotation.id
    if ann in ("int", "long", "bool"):
      parts.append(f"{spec.name}_v")
    elif ann == "str":
      parts.append(_cpp_str_field_ctor_default(spec))
  return ", ".join(parts)


def _cpp_is_scalar_int_bool_only(specs: list[DataclassFieldSpec]) -> bool:
  """仅 ``int``/``bool`` 字段（无 ``str``/``list``/嵌套），可 ``serdePushSlot`` + ``init``。"""
  for spec in specs:
    if isinstance(spec.annotation, ast.Name):
      if spec.annotation.id in ("int", "bool", "long"):
        continue
      return False
    return False
  return bool(specs)


def _cpp_ctor_scalar_args(specs: list[DataclassFieldSpec]) -> str:
  parts: list[str] = []
  for spec in specs:
    if isinstance(spec.annotation, ast.Name) and spec.annotation.id in ("int", "bool", "long"):
      parts.append(f"{spec.name}_v")
  return ", ".join(parts)


def _cpp_emit_list_push_fast_scalar(
  cpp_cls: str,
  specs: list[DataclassFieldSpec],
  out_var: str,
  indent: str,
) -> list[str]:
  """纯标量 dataclass：尾槽 ``init``，避免 ``append`` 拷贝。"""
  args = _cpp_ctor_scalar_args(specs)
  return [
    f"{indent}{cpp_cls}* _slot = {out_var}.serdePushSlot();",
    f"{indent}init<{cpp_cls}>(_slot, {args});",
    f"{indent}{out_var}.serdeCommitPush();",
  ]


def _cpp_emit_list_push_fast_user(
  cpp_cls: str,
  specs: list[DataclassFieldSpec],
  out_var: str,
  indent: str,
) -> list[str]:
  """``list`` 尾槽 ``init`` + ``copy_from_span``，避免 ``append`` 再拷贝 ``User``。"""
  ctor_args = _cpp_fast_ctor_placeholder_args(specs)
  lines: list[str] = [
    f"{indent}{cpp_cls}* _slot = {out_var}.serdePushSlot();",
    f"{indent}init<{cpp_cls}>(_slot, {ctor_args});",
  ]
  for spec in specs:
    if isinstance(spec.annotation, ast.Name) and spec.annotation.id == "str":
      lines.append(
        f"{indent}_slot->{spec.name} = dec.strAssignFromSeg({spec.name}_seg);",
      )
  lines.append(f"{indent}{out_var}.serdeCommitPush();")
  return lines


def _cpp_emit_fast_from_ordered_helper(
  cpp_cls: str, specs: list[DataclassFieldSpec], lines_out: list[str],
) -> bool:
  """``copy_from_span`` 收尾：避免 ``fromSpan`` + ctor ``__copy__`` 双拷贝。"""
  if not _cpp_has_ctor_str_field(specs):
    return False
  helper = _cpp_fast_from_ordered_name(cpp_cls)
  params: list[str] = []
  ctor_args = _cpp_fast_ctor_placeholder_args(specs)
  for spec in specs:
    if not isinstance(spec.annotation, ast.Name):
      continue
    if spec.annotation.id == "int":
      params.append(f"PyInt {spec.name}_v")
    elif spec.annotation.id == "long":
      params.append(f"PyLong {spec.name}_v")
    elif spec.annotation.id == "str":
      params.append(f"PySpan<PyChar> {spec.name}_seg")
    elif spec.annotation.id == "bool":
      params.append(f"PyBool {spec.name}_v")
  params.append("::py2cpp::serde::json::PyJsonDecoder& dec")
  lines_out.append(
    f"static __forceinline {cpp_cls} {helper}({', '.join(params)})",
  )
  lines_out.append("{")
  lines_out.append(f"  {cpp_cls} u({ctor_args});")
  for spec in specs:
    if isinstance(spec.annotation, ast.Name) and spec.annotation.id == "str":
      lines_out.append(
        f"  u.{spec.name} = dec.strAssignFromSeg({spec.name}_seg);",
      )
  lines_out.append("  return u;")
  lines_out.append("}")
  lines_out.append("")
  return True


def _cpp_finish_value_expr(
  cpp_cls: str, specs: list[DataclassFieldSpec], *, use_fast_helper: bool,
) -> str:
  if use_fast_helper:
    args: list[str] = []
    for spec in specs:
      if not isinstance(spec.annotation, ast.Name):
        continue
      if spec.annotation.id in ("int", "bool", "long"):
        args.append(f"{spec.name}_v")
      elif spec.annotation.id == "str":
        args.append(f"{spec.name}_seg")
    args.append("dec")
    return f"{_cpp_fast_from_ordered_name(cpp_cls)}({', '.join(args)})"
  ctor_expr, _ = _cpp_user_ctor_expr(cpp_cls, specs)
  return ctor_expr


def _cpp_emit_ordered_locals(
  specs: list[DataclassFieldSpec], *, str_as_span: bool,
) -> list[str]:
  lines: list[str] = []
  for spec in specs:
    if isinstance(spec.annotation, ast.Name) and spec.annotation.id == "int":
      lines.append(f"  PyInt {spec.name}_v = 0;")
    elif isinstance(spec.annotation, ast.Name) and spec.annotation.id == "long":
      lines.append(f'  PyLong {spec.name}_v = PyLong(PyStr(""));')
    elif isinstance(spec.annotation, ast.Name) and spec.annotation.id == "str":
      if str_as_span:
        lines.append(f"  PySpan<PyChar> {spec.name}_seg(nullptr, 0);")
      else:
        lines.append(f"  PyStr {spec.name}_v;")
    elif isinstance(spec.annotation, ast.Name) and spec.annotation.id == "bool":
      lines.append(f"  PyBool {spec.name}_v = true;")
    elif _ann_list_elem(spec.annotation) == "str":
      lines.append(f"  PyList<PyStr> {spec.name}_v;")
      lines.append(f"  PyBool {spec.name}_nonempty = false;")
    elif _ann_list_elem(spec.annotation) == "int":
      lines.append(f"  PyList<PyInt> {spec.name}_v;")
  return lines


def _cpp_emit_ordered_parse_core(
  dec: str,
  specs: list[DataclassFieldSpec],
  fail_return: str,
  *,
  str_as_span: bool,
) -> list[str]:
  lines: list[str] = []
  lines.extend(_cpp_inline_object_open(dec, fail_return))
  for i, spec in enumerate(specs):
    tgt = _cpp_field_target(spec, str_as_span=str_as_span)
    lines.extend(_cpp_inline_expect_key(dec, spec.name, i == 0, fail_return))
    lines.extend(
      _cpp_ordered_field_lines(
        spec.annotation, tgt, dec, fail_return, str_as_span=str_as_span,
      ),
    )
  return lines


def _cpp_emit_ordered_finish(
  cpp_cls: str,
  specs: list[DataclassFieldSpec],
  *,
  use_fast_helper: bool,
  append_to: str | None = None,
) -> list[str]:
  """有序快路径收尾：``}`` 消费 + ``return`` 或 ``out.append``。"""
  finish_expr = _cpp_finish_value_expr(cpp_cls, specs, use_fast_helper=use_fast_helper)
  list_specs = _cpp_list_str_fields(specs)
  lines: list[str] = []

  def _sink(expr: str, indent: str = "  ") -> None:
    if append_to and use_fast_helper:
      lines.extend(_cpp_emit_list_push_fast_user(cpp_cls, specs, append_to, indent))
    elif append_to and _cpp_is_scalar_int_bool_only(specs):
      lines.extend(
        _cpp_emit_list_push_fast_scalar(cpp_cls, specs, append_to, indent),
      )
    elif append_to:
      lines.append(f"{indent}{append_to}.append({expr});")
    else:
      lines.append(f"{indent}return {expr};")

  if not list_specs:
    lines.extend(_cpp_inline_object_close("dec"))
    if append_to and use_fast_helper:
      _sink(finish_expr)
    else:
      _sink(finish_expr)
    return lines
  any_nonempty = " || ".join(f"{s.name}_nonempty" for s in list_specs)
  lines.append(f"  if (!({any_nonempty}))")
  lines.append("  {")
  lines.extend(_cpp_inline_object_close("dec"))
  _sink(finish_expr, "    ")
  lines.append("  }")
  lines.append("  else")
  lines.append("  {")
  lines.append(f"    {cpp_cls} _u = {finish_expr};")
  for spec in list_specs:
    lines.append(f"    if ({spec.name}_nonempty)")
    lines.append(f"      _u.{spec.name} = {spec.name}_v;")
  lines.extend(_cpp_inline_object_close("dec"))
  _sink("_u", "    ")
  lines.append("  }")
  return lines


def _cpp_emit_ordered_return(
  cpp_cls: str,
  specs: list[DataclassFieldSpec],
  def_ctor: str,
  *,
  use_fast_helper: bool = False,
) -> list[str]:
  return _cpp_emit_ordered_finish(
    cpp_cls, specs, use_fast_helper=use_fast_helper, append_to=None,
  )


def _cpp_user_ctor_expr(cpp_cls: str, specs: list[DataclassFieldSpec]) -> tuple[str, list[str]]:
  """``User(id_v, name_v, active_v)`` + 列表字段赋值行。"""
  ctor_params: list[str] = []
  post: list[str] = []
  for spec in specs:
    tgt = f"{spec.name}_v"
    if isinstance(spec.annotation, ast.Name):
      if spec.annotation.id in ("int", "str", "bool", "long"):
        ctor_params.append(tgt)
    elif _ann_list_elem(spec.annotation) == "str":
      post.append(f"  _u.{spec.name} = {tgt};")
    elif _ann_list_elem(spec.annotation) == "int":
      post.append(f"  _u.{spec.name} = {tgt};")
  expr = f"{cpp_cls}({', '.join(ctor_params)})"
  return expr, post


def _cpp_default_ctor_expr(cpp_cls: str, specs: list[DataclassFieldSpec]) -> str:
  """无参 ``User()`` 不可用时用 dataclass 必填字段默认值构造。"""
  parts: list[str] = []
  for spec in specs:
    if isinstance(spec.annotation, ast.Name):
      if spec.annotation.id == "int":
        parts.append("0")
      elif spec.annotation.id == "long":
        parts.append('PyLong(PyStr(""))')
      elif spec.annotation.id == "str":
        parts.append("PyStr(\"\")")
      elif spec.annotation.id == "bool":
        parts.append("true")
  if not parts:
    return f"{cpp_cls}(0)"
  return f"{cpp_cls}({', '.join(parts)})"


def _emit_cpp_list_load_fast(
  tr: Translator, info: ClassInfo, specs: list[DataclassFieldSpec],
) -> None:
  """``loads[list[Cls]]``：严格键序（``dumps`` 形态）数组快路径 + ``_json_loads_list_element`` 特化。"""
  cpp_cls = info.cpp_name()
  mp = info.module_path
  fq_cls = qualify_symbol_in_module(mp, cpp_cls)
  parse_fn = f"_json_parse_{cpp_cls}_ordered"
  load_fn = f"_fast_load_list_{cpp_cls}_dec"
  inl_ns = inl_namespace_segments(mp)
  lines_out: list[str] = tr.per_module_inl_lines.setdefault(mp, [])
  for seg in inl_ns:
    lines_out.append(f"namespace {seg} {{")
  use_fast_helper = _cpp_emit_fast_from_ordered_helper(cpp_cls, specs, lines_out)
  str_as_span = use_fast_helper
  def_ctor = _cpp_default_ctor_expr(cpp_cls, specs)
  fail_out = f"PyList<{cpp_cls}>()"
  lines_out.append(
    f"static __forceinline {cpp_cls} {parse_fn}(::py2cpp::serde::json::PyJsonDecoder& dec)",
  )
  lines_out.append("{")
  lines_out.extend(_cpp_emit_ordered_locals(specs, str_as_span=str_as_span))
  lines_out.extend(
    _cpp_emit_ordered_parse_core("dec", specs, def_ctor, str_as_span=str_as_span),
  )
  lines_out.extend(
    _cpp_emit_ordered_return(cpp_cls, specs, def_ctor, use_fast_helper=use_fast_helper),
  )
  lines_out.append("}")
  lines_out.append("")
  lines_out.append(
    f"static __forceinline PyList<{cpp_cls}> {load_fn}"
    "(::py2cpp::serde::json::PyJsonDecoder& dec)",
  )
  lines_out.append("{")
  lines_out.append("  dec.skipSpaces();")
  lines_out.append(f"  if (!{_cpp_dec_at_char('dec', 91)})")
  lines_out.append("  {")
  lines_out.append("    dec.fail(PyStr(\"expected [\"));")
  lines_out.append(f"    return {fail_out};")
  lines_out.append("  }")
  lines_out.append("  dec.pos += 1;")
  lines_out.append("  dec.skipSpaces();")
  lines_out.append(f"  PyList<{cpp_cls}> out;")
  lines_out.append(f"  if ({_cpp_dec_at_char('dec', 93)})")
  lines_out.append("  {")
  lines_out.append("    dec.pos += 1;")
  lines_out.append("    return out;")
  lines_out.append("  }")
  lines_out.append("  {")
  _bytes_per = 48 if _cpp_has_ctor_str_field(specs) else 22
  lines_out.append(
    f"    int _est = (int)((dec.srcLen() - dec.pos) / {_bytes_per});",
  )
  lines_out.append("    if (_est > 0)")
  lines_out.append("    {")
  lines_out.append("      out.setCapacity(_est);")
  lines_out.append("    }")
  lines_out.append("  }")
  lines_out.extend(_cpp_emit_ordered_locals(specs, str_as_span=str_as_span))
  lines_out.append("  while (true)")
  lines_out.append("  {")
  for spec in _cpp_list_str_fields(specs):
    lines_out.append(f"    {spec.name}_nonempty = false;")
  mega_fail = "out"
  mega_body: list[str] = []
  mega_body.extend(
    _cpp_emit_ordered_parse_core("dec", specs, mega_fail, str_as_span=str_as_span),
  )
  mega_body.extend(
    _cpp_emit_ordered_finish(
      cpp_cls, specs, use_fast_helper=use_fast_helper, append_to="out",
    ),
  )
  for line in mega_body:
    lines_out.append(f"  {line}" if line else line)
  lines_out.append("    dec.skipSpaces();")
  lines_out.append(f"    if ({_cpp_dec_at_char('dec', 93)})")
  lines_out.append("    {")
  lines_out.append("      dec.pos += 1;")
  lines_out.append("      return out;")
  lines_out.append("    }")
  lines_out.append(
    "    if ((dec.pos >= dec.srcLen()) || (dec.srcChar(dec.pos) != PyChar(44)))",
  )
  lines_out.append("    {")
  lines_out.append("      dec.fail(PyStr(\"expected , or ]\"));")
  lines_out.append("      return out;")
  lines_out.append("    }")
  lines_out.append("    dec.pos += 1;")
  lines_out.append("    dec.skipSpaces();")
  lines_out.append("  }")
  lines_out.append("}")
  for seg in reversed(inl_ns):
    lines_out.append(f"}} // namespace {seg}")
  lines_out.append("")
  lines_out.append("namespace py2cpp {")
  lines_out.append("namespace serde {")
  lines_out.append("namespace json {")
  lines_out.append("")
  # helper 在用户模块 namespace（runtime .inl 则为全局）；特化在 py2cpp::serde::json，须限定调用。
  call_load = f"::{'::'.join(inl_ns)}::{load_fn}" if inl_ns else load_fn
  lines_out.append(f"template<>")
  lines_out.append(
    f"PyList<{fq_cls}> PyJsonDecoder::loadListElement<{fq_cls}>()",
  )
  lines_out.append("{")
  lines_out.append(f"  return {call_load}(*this);")
  lines_out.append("}")
  lines_out.append("")
  lines_out.append("} // json")
  lines_out.append("} // serde")
  lines_out.append("} // py2cpp")
  lines_out.append("")


def _default_ctor_call(tr: Translator, class_name: str) -> str:
  info = tr.classes.get(class_name)
  if info is None or not info.is_dataclass:
    return f"{class_name}()"
  specs = _dataclass_specs(tr, info)
  parts: list[str] = []
  for spec in specs:
    if spec.optional or spec.body_init is not None:
      continue
    parts.append(_default_for_ann(spec.annotation, tr))
  return f"{class_name}({', '.join(parts)})"


def _emit_dataclass_serializable(tr: Translator, info: ClassInfo) -> None:
  specs = _dataclass_specs(tr, info)
  class_name = info.name
  field_lines: list[str] = []
  for spec in specs:
    acc = f"self.{spec.name}"
    key = _ensure_json_key_const(tr, info, spec.name)
    fast = _dump_fast_field_line(tr, spec.annotation, key, acc, "encoder")
    if fast is not None:
      field_lines.append(f"  {fast}")
      continue
    field_lines.append(f"  encoder.dumpKey({key})")
    for line in _dump_field_lines(tr, spec.annotation, acc, "encoder"):
      field_lines.append(f"  {line}")
  fields_joined = "\n".join(field_lines)
  serialize_src = f"""
def serialize(self, encoder: JsonEncoder) -> None:
  encoder.beginObject()
{fields_joined}
  encoder.endObject()
"""
  ser_fn = _parse_method(serialize_src)
  _register_method(info, ser_fn)

  init_lines: list[str] = []
  parse_branches: list[str] = []
  new_args: list[str] = []
  for i, spec in enumerate(specs):
    init_lines.append(
      f"  {spec.name}_v: {_type_hint(spec.annotation)} = {_default_init(spec, tr)}",
    )
    parse_branches.append(
      _load_field_branch(
        tr, info, spec.annotation, spec.name, f"{spec.name}_v", "decoder", elif_=i > 0,
      ),
    )
    new_args.append(f"{spec.name}={spec.name}_v")

  ret_lines = [f"  return new({', '.join(new_args)})"]
  ordered_lines: list[str] = []
  if _schema_deserialize_eligible(tr, specs):
    ordered_lines = _build_ordered_deserialize_body(tr, info, specs)
    _emit_cpp_list_load_fast(tr, info, specs)
  if ordered_lines:
    generic_loop: list[str] = [
      "    while True:",
      "      if decoder.atObjectEnd():",
      "        break",
    ]
    for branch in parse_branches:
      for line in branch.splitlines():
        generic_loop.append("  " + line)
    generic_loop.extend(
      [
        "      else:",
        "        decoder.skipField()",
      ],
    )
    deserialize_src = f"""
@staticmethod
def deserialize(decoder: JsonDecoder) -> {class_name}:
{chr(10).join(init_lines)}
{chr(10).join(ordered_lines)}
{chr(10).join(generic_loop)}
{chr(10).join(ret_lines)}
"""
  else:
    deserialize_src = f"""
@staticmethod
def deserialize(decoder: JsonDecoder) -> {class_name}:
{chr(10).join(init_lines)}
  decoder.beginRootObject()
  while True:
    if decoder.atObjectEnd():
      break
{chr(10).join(parse_branches)}
    else:
      decoder.skipField()
{chr(10).join(ret_lines)}
"""
  des_fn = _parse_method(deserialize_src)
  des_fn.decorator_list = [copy.deepcopy(_STATICMETHOD_DEC)]
  _register_method(info, des_fn)


def _union_case_serialize(
  tr: Translator, info: ClassInfo, variant: UnionVariantInfo,
) -> str:
  vname = variant.name
  if not variant.fields:
    binds = ""
    body = [
      f"    case new.{vname}():",
      f'      encoder.beginVariant("{vname}")',
      "      encoder.endVariant()",
    ]
    return "\n".join(body)
  binds = ", ".join(f"{f}={f}" for f in variant.fields)
  lines = [f"    case new.{vname}({binds}):"]
  lines.append(f'      encoder.beginVariant("{vname}")')
  for fname in variant.fields:
    ann = variant.field_annotations[fname]
    key = _ensure_json_key_const(tr, info, fname, variant=vname)
    fast = _dump_fast_field_line(tr, ann, key, fname, "encoder")
    if fast is not None:
      lines.append(f"      {fast}")
      continue
    lines.append(f"      encoder.dumpKey({key})")
    for line in _dump_field_lines(tr, ann, fname, "encoder"):
      lines.append(f"      {line}")
  lines.append("      encoder.endVariant()")
  return "\n".join(lines)


def _union_unreachable_return(
  class_name: str, variant: UnionVariantInfo, tr: Translator,
) -> str:
  vname = variant.name
  if not variant.fields:
    return f"  return new.{vname}()"
  pre: list[str] = []
  parts: list[str] = []
  for fname in variant.fields:
    ann = variant.field_annotations[fname]
    hint = _type_hint(ann)
    pre.append(f"  _fb_{fname}: {hint} = {_default_for_ann(ann, tr)}")
    parts.append(f"{fname}=_fb_{fname}")
  return "\n".join(pre) + f"\n  return new.{vname}({', '.join(parts)})"


def _union_parse_payload(
  tr: Translator, info: ClassInfo, variant: UnionVariantInfo, decoder: str,
) -> tuple[str, str]:
  inits: list[str] = []
  branches: list[str] = []
  args: list[str] = []
  vname = variant.name
  for fname in variant.fields:
    ann = variant.field_annotations[fname]
    inits.append(f"    {fname}_v: {_type_hint(ann)} = {_default_for_ann(ann, tr)}")
    args.append(f"{fname}={fname}_v")
  first = True
  for fname in variant.fields:
    ann = variant.field_annotations[fname]
    branches.append(
      _load_field_branch(
        tr, info, ann, fname, f"{fname}_v", decoder,
        elif_=not first, indent="      ", variant=vname,
      ),
    )
    first = False
  loop = [
    "    while not decoder.atObjectEnd():",
    *branches,
    "      else:",
    "        decoder.skipField()",
  ]
  return "\n".join(inits + loop), ", ".join(args)


def _emit_union_serializable(tr: Translator, info: ClassInfo) -> None:
  class_name = info.name
  cases_ser = "\n".join(
    _union_case_serialize(tr, info, v) for v in info.union_variants
  )
  serialize_src = f"""
def serialize(self, encoder: JsonEncoder) -> None:
  match self:
{cases_ser}
"""
  ser_fn = _parse_method(serialize_src)
  _register_method(info, ser_fn)

  fallback_variant_info = info.union_variants[0]
  for variant in info.union_variants:
    if not variant.fields:
      fallback_variant_info = variant
      break
  branches: list[str] = []
  for variant in info.union_variants:
    vname = variant.name
    if not variant.fields:
      branches.append(
        f'  if tag == "{vname}":\n'
        f"    if not decoder.atObjectEnd():\n"
        f"      decoder.skipValue()\n"
        f"    return new.{vname}()",
      )
      continue
    body, args = _union_parse_payload(tr, info, variant, "decoder")
    branches.append(
      f'  if tag == "{vname}":\n{body}\n    return new.{vname}({args})',
    )

  unreachable = _union_unreachable_return(class_name, fallback_variant_info, tr)
  deserialize_src = f"""
@staticmethod
def deserialize(decoder: JsonDecoder) -> {class_name}:
  decoder.beginRootObject()
  tag: str = decoder.loadTagField()
  decoder.beginPayloadObject()
{chr(10).join(branches)}
  decoder.fail("unknown tag")
{unreachable}
"""
  des_fn = _parse_method(deserialize_src)
  des_fn.decorator_list = [copy.deepcopy(_STATICMETHOD_DEC)]
  _register_method(info, des_fn)


def expand_serializable(tr: Translator) -> None:
  """``@serializable`` → ``serialize`` / ``deserialize``。"""
  targets: list[ClassInfo] = []
  for info in tr.classes.values():
    skip = getattr(tr, "skip_cached_analysis_module", None)
    if skip is not None and skip(info.module_path):
      continue
    if not has_named_decorator(info.node, SERIALIZABLE_DECORATOR):
      continue
    if info.is_descriptor or info.is_mixin or info.is_protocol:
      continue
    _strip_serializable_decorators(info.node)
    info.is_serializable = True
    targets.append(info)
  for info in targets:
    if info.is_union:
      _emit_union_serializable(tr, info)
    elif info.is_dataclass:
      _emit_dataclass_serializable(tr, info)
    else:
      raise NotImplementedError(
        f"{info.name}: @serializable 仅支持 @dataclass 或 @union",
      )
    ast.fix_missing_locations(info.node)
