"""从 ``py2cpp/**/protocols.py`` 推导运行时擦除协议（``Py{Name}`` / ``make{Name}``）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache

from ...constant.protocol_scan import PROTOCOL_SCAN_REL_PATHS
from ..ir import cpp_ident, has_named_decorator, is_stub_function_body
from .paths import PY2CPP
from .protocol_stubs import _scan_protocol_classes, _type_param_names


@dataclass(frozen=True)
class ProtocolEraseMethod:
  name: str
  params: tuple[tuple[str, str], ...]
  ret_cpp: str
  is_void: bool


@dataclass(frozen=True)
class ProtocolEraseSpec:
  name: str
  type_params: tuple[str, ...]
  methods: tuple[ProtocolEraseMethod, ...]
  module_rel: str


PROTOCOL_ERASE_ALWAYS: frozenset[str] = frozenset({
  "GeneratorType",
  "CoroutineType",
  "AsyncGeneratorType",
})
"""手写 ``templates/core/{generator,coroutine,async_generator}.h``；仍参与 ``make{Name}`` 与类型映射。"""

PROTOCOL_ERASE_FORCE: frozenset[str] = frozenset({"IteratorType", "AsyncIteratorType"})
"""协议体含 ``Self``，但被其它擦除协议返回类型依赖；仍生成 ``PyIterator`` / ``PyAsyncIterator``。"""

PROTOCOL_ERASE_AUTOGEN_MODULES: frozenset[str] = frozenset({
  "core/protocols",
  "util/protocols",
  "numeric/protocols",
  "io/protocols",
  "serde/protocols",
  "sql/protocols",
  "alg/protocols",
})
"""自动生成 ``protocol_erase.h`` 的 ``@protocol`` 模块（含域协议；``Self`` 体仍排除）。"""

_REF_ERASED_CPP: dict[str, str] = {
  "IteratorType": "PyIterator",
  "AsyncIteratorType": "PyAsyncIterator",
}

PROTOCOL_ERASE_SKIP: frozenset[str] = frozenset({
  "IterableIteratorType",
  "StringFormatType",
})
"""``Element``/``Key``/``Value`` 别名已映射；``Self`` 协议（``TextIOType``/``DocumentType`` 等）仍不生成 C++。"""

# ``protocol_erase.h`` 在全局命名空间；嵌套模块类型须 FQN（``minimal.h`` 中 ``long.h`` 在其后）。
_PROTOCOL_ERASE_TYPE_FQN: dict[str, str] = {
  "long": "py2cpp::numeric::py_long::PyLong",
  "PyLong": "py2cpp::numeric::py_long::PyLong",
}

PROTOCOL_ERASE_SPEC_ORDER: tuple[str, ...] = (
  "IteratorType",
  "AsyncIteratorType",
  "SizedType",
  "HashableType",
  "ContextManagerType",
  "ContainerType",
  "CollectionType",
  "AppendableType",
  "MutableMappingType",
  "IterableType",
  "ReversibleType",
  "AwaitableType",
  "AsyncIterableType",
  "AsyncContextManagerType",
  "NumberType",
  "CursorType",
  "DialectType",
  "ConnectionType",
  "TextWriterType",
  "TextReaderType",
  "EncoderType",
  "DecoderType",
  "NavigatableType",
)

PROTOCOL_ERASE_LATE_SPECS: frozenset[str] = frozenset({"EncoderType", "DecoderType"})
"""依赖 ``long`` 完整定义；在 ``numeric/long.h`` 之后生成 ``protocol_erase_domain.h``。"""


def annotation_uses_self(ann: ast.expr | None) -> bool:
  if ann is None:
    return False
  return any(isinstance(n, ast.Name) and n.id == "Self" for n in ast.walk(ann))


def _ordered_type_param_names(node: ast.ClassDef) -> tuple[str, ...]:
  names: list[str] = []
  for tp in getattr(node, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar):
      names.append(tp.name)
    elif isinstance(tp, ast.TypeVarTuple):
      names.append(tp.name)
    elif isinstance(tp, ast.ParamSpec):
      names.append(tp.name)
  return tuple(names)


def _protocol_module_rel(path) -> str:
  rel = path.relative_to(PY2CPP).as_posix()
  return rel[: -len(".py")]


def _alias_ellipsis_to_type_param(
  alias_name: str,
  type_param_names: tuple[str, ...],
) -> str | None:
  """``type Element = ...`` → 协议形参 ``T`` / ``K`` / ``V`` / ``N``。"""
  if alias_name == "Element" and type_param_names:
    return type_param_names[0]
  if alias_name == "Key" and type_param_names:
    return type_param_names[0]
  if alias_name == "Value" and len(type_param_names) >= 2:
    return type_param_names[1]
  if alias_name == "Node" and type_param_names:
    return type_param_names[0]
  return None


def _protocol_erase_scalar_cpp(py_name: str) -> str:
  if py_name in _PROTOCOL_ERASE_TYPE_FQN:
    return _PROTOCOL_ERASE_TYPE_FQN[py_name]
  if py_name in ("int", "str", "bool", "float", "bytes", "char", "byte", "object"):
    return cpp_ident(py_name)
  if py_name == "None":
    return cpp_ident("PyNone")
  cpp = cpp_ident(py_name)
  return _PROTOCOL_ERASE_TYPE_FQN.get(cpp, cpp)


def _resolve_protocol_type_alias(
  alias_name: str,
  alias_value: ast.expr,
  type_param_names: tuple[str, ...],
  type_aliases: dict[str, ast.expr],
  *,
  runtime_erase: frozenset[str],
) -> str | None:
  if isinstance(alias_value, ast.Constant) and alias_value.value is Ellipsis:
    mapped = _alias_ellipsis_to_type_param(alias_name, type_param_names)
    if mapped is not None:
      return mapped
  if isinstance(alias_value, ast.Name):
    if alias_value.id in type_param_names:
      return alias_value.id
    if alias_value.id in type_aliases:
      return _protocol_ann_to_cpp(
        ast.Name(id=alias_value.id),
        type_param_names,
        type_aliases,
        runtime_erase=runtime_erase,
      )
  return _protocol_ann_to_cpp(
    alias_value,
    type_param_names,
    type_aliases,
    runtime_erase=runtime_erase,
  )


def _map_protocol_ann(
  protocol_name: str,
  ann: ast.expr | None,
  type_param_names: tuple[str, ...],
  type_aliases: dict[str, ast.expr],
  *,
  runtime_erase: frozenset[str],
) -> str:
  if isinstance(ann, ast.Name) and ann.id == "Self":
    if protocol_name == "IteratorType" and len(type_param_names) == 1:
      tp = type_param_names[0]
      return f"PyIterator<{tp}>&"
    if protocol_name == "AsyncIteratorType" and len(type_param_names) == 1:
      tp = type_param_names[0]
      return f"PyAsyncIterator<{tp}>&"
  return _protocol_ann_to_cpp(
    ann, type_param_names, type_aliases, runtime_erase=runtime_erase,
  )


def _collect_protocol_methods(
  node: ast.ClassDef,
  *,
  module_rel: str,
  classes: dict[str, ast.ClassDef],
  runtime_erase: frozenset[str],
) -> tuple[ProtocolEraseMethod, ...]:
  tparams = _ordered_type_param_names(node)
  type_aliases: dict[str, ast.expr] = {}
  for item in node.body:
    if isinstance(item, ast.TypeAlias):
      alias_name = item.name.id if isinstance(item.name, ast.Name) else item.name.name
      type_aliases[alias_name] = item.value

  def ret_cpp(ann: ast.expr | None) -> str:
    return _map_protocol_ann(
      node.name, ann, tparams, type_aliases, runtime_erase=runtime_erase,
    )

  merged: dict[str, ProtocolEraseMethod] = {}

  def walk(cls: ast.ClassDef) -> None:
    for base in cls.bases:
      if isinstance(base, ast.Name):
        parent = classes.get(base.id)
        if parent is not None and has_named_decorator(parent, "protocol"):
          walk(parent)
    for item in cls.body:
      if not isinstance(item, ast.FunctionDef) or not is_stub_function_body(item.body):
        continue
      if any(
        isinstance(d, ast.Name) and d.id == "overload"
        for d in item.decorator_list
      ):
        continue
      if item.name.startswith("__") and item.name.endswith("__") and item.name != "__contains__":
        pass
      params: list[tuple[str, str]] = []
      for arg in item.args.args:
        if arg.arg == "self":
          continue
        if arg.annotation is None:
          params.append((arg.arg, "void*"))
        else:
          params.append(
            (arg.arg, _map_protocol_ann(
              node.name, arg.annotation, tparams, type_aliases,
              runtime_erase=runtime_erase,
            )),
          )
      r = ret_cpp(item.returns)
      if (
        node.name == "IteratorType"
        and item.name == "__next__"
        and len(tparams) == 1
      ):
        tp = tparams[0]
        if r == tp:
          from ..ir import cpp_result_type
          r = cpp_result_type(tp)
      is_void = not r or r == "void"
      merged[item.name] = ProtocolEraseMethod(
        item.name,
        tuple(params),
        r if not is_void else "void",
        is_void,
      )

  walk(node)
  return tuple(merged[name] for name in sorted(merged))


def _protocol_ann_to_cpp(
  ann: ast.expr | None,
  type_param_names: tuple[str, ...],
  type_aliases: dict[str, ast.expr],
  *,
  runtime_erase: frozenset[str],
) -> str:
  type_params = set(type_param_names)
  if ann is None:
    return "void"
  if isinstance(ann, ast.Constant):
    if ann.value is None:
      return cpp_ident("PyNone")
    if ann.value is Ellipsis:
      return "void*"
    if isinstance(ann.value, bool):
      return cpp_ident("bool")
    if isinstance(ann.value, int):
      return cpp_ident("int")
    if isinstance(ann.value, float):
      return cpp_ident("float")
  if isinstance(ann, ast.Name):
    if ann.id == "Self":
      return "Self"
    if ann.id in type_params:
      return ann.id
    if ann.id in type_aliases:
      resolved = _resolve_protocol_type_alias(
        ann.id,
        type_aliases[ann.id],
        type_param_names,
        type_aliases,
        runtime_erase=runtime_erase,
      )
      if resolved:
        return resolved
      return "void*"
    if ann.id in runtime_erase:
      return erased_protocol_cpp_name(ann.id)
    return _protocol_erase_scalar_cpp(ann.id)
  if isinstance(ann, ast.Subscript):
    if isinstance(ann.value, ast.Name):
      base = ann.value.id
      if base in runtime_erase:
        args = _protocol_slice_to_cpp_args(
          ann.slice, type_param_names, type_aliases, runtime_erase=runtime_erase,
        )
        if args:
          return f"{erased_protocol_cpp_name(base)}<{args}>"
        return erased_protocol_cpp_name(base)
      if base in _REF_ERASED_CPP:
        args = _protocol_slice_to_cpp_args(
          ann.slice, type_param_names, type_aliases, runtime_erase=runtime_erase,
        )
        prefix = _REF_ERASED_CPP[base]
        return f"{prefix}<{args}>" if args else prefix
      if base in ("list", "dict", "set", "tuple", "IterResult", "Optional", "AwaitableType"):
        args = _protocol_slice_to_cpp_args(
          ann.slice, type_param_names, type_aliases, runtime_erase=runtime_erase,
        )
        if base == "IterResult":
          return f"PyIterResult<{args}>"
        if base == "tuple":
          return f"PyTuple<{args}>" if args else "PyTuple"
        return f"{cpp_ident(base)}<{args}>"
      if base in type_aliases:
        return _protocol_ann_to_cpp(
          ann.slice if isinstance(ann.slice, ast.Name) else ann,
          type_param_names,
          type_aliases,
          runtime_erase=runtime_erase,
        )
    if isinstance(ann.value, ast.Attribute) and isinstance(ann.value.value, ast.Name):
      if ann.value.value.id == "char" and isinstance(ann.slice, ast.Slice):
        return cpp_ident("char") + "[:]"
  if isinstance(ann, ast.Tuple):
    args = ", ".join(
      _protocol_ann_to_cpp(e, type_param_names, type_aliases, runtime_erase=runtime_erase)
      for e in ann.elts
    )
    return args
  if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
    return _protocol_ann_to_cpp(
      ann.left, type_param_names, type_aliases, runtime_erase=runtime_erase,
    )
  return "void*"


def _protocol_slice_to_cpp_args(
  slice_node: ast.expr,
  type_param_names: tuple[str, ...],
  type_aliases: dict[str, ast.expr],
  *,
  runtime_erase: frozenset[str],
) -> str:
  if isinstance(slice_node, ast.Tuple):
    return ", ".join(
      _protocol_ann_to_cpp(e, type_param_names, type_aliases, runtime_erase=runtime_erase)
      for e in slice_node.elts
    )
  return _protocol_ann_to_cpp(
    slice_node, type_param_names, type_aliases, runtime_erase=runtime_erase,
  )


def _protocol_erase_stem(protocol: str) -> str:
  """``IteratorType`` → ``Iterator``（C++ ``PyIterator`` / ``makeIterator``）。"""
  if protocol.endswith("Type"):
    return protocol[: -len("Type")]
  if protocol.endswith("Protocol"):
    return protocol[: -len("Protocol")]
  return protocol


def erased_protocol_cpp_name(protocol: str) -> str:
  if protocol in _REF_ERASED_CPP:
    return _REF_ERASED_CPP[protocol]
  return cpp_ident(f"Py{_protocol_erase_stem(protocol)}")


def protocol_uses_self(node: ast.ClassDef, classes: dict[str, ast.ClassDef]) -> bool:
  def walk(cls: ast.ClassDef) -> bool:
    for base in cls.bases:
      if isinstance(base, ast.Name):
        parent = classes.get(base.id)
        if parent is not None and has_named_decorator(parent, "protocol"):
          if walk(parent):
            return True
    for item in cls.body:
      if isinstance(item, ast.FunctionDef):
        for arg in item.args.args:
          if arg.arg != "self" and annotation_uses_self(arg.annotation):
            return True
        if annotation_uses_self(item.returns):
          return True
      if isinstance(item, ast.TypeAlias) and annotation_uses_self(item.value):
        return True
    return False

  return walk(node)


@lru_cache(maxsize=1)
def load_protocol_runtime_erase() -> frozenset[str]:
  """运行时双轨擦除协议（具已生成或手写 ``Py*`` C++ 类型）。"""
  names = {s.name for s in load_protocol_erase_specs()}
  return frozenset(names | PROTOCOL_ERASE_ALWAYS)


@lru_cache(maxsize=1)
def load_protocol_runtime_erase_candidates() -> frozenset[str]:
  """扫描所得、协议体无 ``Self`` 的候选（含尚未生成 C++ 的域协议）。"""
  classes_list = _scan_protocol_classes()
  by_name = {c.name: c for c in classes_list}
  auto: set[str] = set()
  for node in classes_list:
    if node.name in PROTOCOL_ERASE_FORCE:
      auto.add(node.name)
      continue
    if protocol_uses_self(node, by_name):
      continue
    auto.add(node.name)
  return frozenset(auto | PROTOCOL_ERASE_ALWAYS)


@lru_cache(maxsize=1)
def load_protocol_erase_specs() -> tuple[ProtocolEraseSpec, ...]:
  """自动生成 C++ 擦除类的协议（``core/protocols``；排除 ``GeneratorType``/``CoroutineType``）。"""
  classes_list = _scan_protocol_classes()
  by_name = {c.name: c for c in classes_list}
  path_by_name: dict[str, str] = {}
  for rel in PROTOCOL_SCAN_REL_PATHS:
    path = PY2CPP.joinpath(*rel.split("/")).with_suffix(".py")
    if not path.is_file():
      continue
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mod_rel = _protocol_module_rel(path)
    for item in tree.body:
      if isinstance(item, ast.ClassDef) and has_named_decorator(item, "protocol"):
        path_by_name[item.name] = mod_rel

  candidates = load_protocol_runtime_erase_candidates()
  order = {name: i for i, name in enumerate(PROTOCOL_ERASE_SPEC_ORDER)}
  specs: list[ProtocolEraseSpec] = []
  for node in classes_list:
    if node.name not in candidates:
      continue
    if node.name in PROTOCOL_ERASE_ALWAYS:
      continue
    mod_rel = path_by_name.get(node.name, "core/protocols")
    if mod_rel not in PROTOCOL_ERASE_AUTOGEN_MODULES:
      continue
    if node.name in PROTOCOL_ERASE_SKIP:
      continue
    methods = _collect_protocol_methods(
      node, module_rel=mod_rel, classes=by_name, runtime_erase=candidates,
    )
    if not methods:
      continue
    specs.append(
      ProtocolEraseSpec(
        node.name,
        tuple(_ordered_type_param_names(node)),
        methods,
        mod_rel,
      ),
    )
  specs.sort(key=lambda s: (order.get(s.name, 999), s.name))
  return tuple(specs)


def protocol_erase_specs_for_header(*, late: bool) -> tuple[ProtocolEraseSpec, ...]:
  """``late=False`` → ``protocol_erase.h``；``late=True`` → ``protocol_erase_domain.h``。"""
  all_specs = load_protocol_erase_specs()
  if late:
    return tuple(s for s in all_specs if s.name in PROTOCOL_ERASE_LATE_SPECS)
  return tuple(s for s in all_specs if s.name not in PROTOCOL_ERASE_LATE_SPECS)


def erased_protocol_make_fn(protocol: str) -> str:
  return f"make{_protocol_erase_stem(protocol)}"


def cpp_make_erased_protocol_expr(erased_cpp_type: str, concrete_expr: str) -> str:
  """``PyContextManager<T>`` + 具体实现 → ``makeContextManager<T>(…)``。"""
  parsed = parse_erased_protocol_from_cpp(erased_cpp_type.strip())
  if parsed is None:
    return concrete_expr
  proto, args = parsed
  fn = erased_protocol_make_fn(proto)
  if args:
    return f"{fn}<{args}>({concrete_expr})"
  return f"{fn}({concrete_expr})"


def is_cpp_erased_protocol_type(cpp_type: str, protocol: str | None = None) -> bool:
  t = cpp_type.strip()
  if protocol is not None:
    prefix = erased_protocol_cpp_name(protocol)
    return t == prefix or t.startswith(f"{prefix}<")
  if not t.startswith("Py"):
    return False
  name = t[2:].split("<", 1)[0]
  erase = load_protocol_runtime_erase()
  if name in erase:
    return True
  return any(_protocol_erase_stem(p) == name for p in erase)


def parse_erased_protocol_from_cpp(cpp_type: str) -> tuple[str, str] | None:
  """``PySized`` / ``PyContextManager<T>`` → ``(protocol, args)``。"""
  t = cpp_type.strip()
  if not t.startswith("Py"):
    return None
  rest = t[2:]
  if "<" in rest and rest.endswith(">"):
    name, args = rest.split("<", 1)
    return name, args[:-1]
  return rest, ""
