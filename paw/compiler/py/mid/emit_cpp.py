"""MidIR → C++ 竖切发射（P3+）：结构化 seed 子集，绕过 materialize/ast。

能力边界：无 MidOpaque 残留 Paw 头；函数体无 ``OpaqueStmtSyntax``；
类型名为简单标识或已知映射。复杂 stdlib 仍走 materialize 回退。
"""
from __future__ import annotations

from pathlib import Path

from compiler.py.frontend.syntax_nodes import (
  AnnAssignStmt,
  AssertStmt,
  AssignStmt,
  AttributeExpr,
  AugAssignStmt,
  BinOpExpr,
  BoolOpExpr,
  BreakStmt,
  CallExpr,
  CompareExpr,
  ContinueStmt,
  DictExpr,
  ExprStmt,
  ExprSyntax,
  ForStmt,
  GlobalStmt,
  IfExp,
  IfStmt,
  ListExpr,
  LiteralExpr,
  MatchStmt,
  MatMultExpr,
  NameExpr,  # AnnAssign 局部 vs self.x
  NonlocalStmt,
  ObjectModel,
  OpaqueStmtSyntax,
  PassStmt,
  RaiseStmt,
  ReturnStmt,
  SliceExpr,
  StmtSyntax,
  SubscriptExpr,
  TryStmt,
  TupleExpr,
  UnaryOpExpr,
  WhileStmt,
  WithStmt,
)
from compiler.py.frontend.type_parse import type_syntax_to_source
from compiler.py.mid.structure import module_fully_structured as _module_fully_structured
from compiler.py.mid.nodes import (
  MidClass,
  MidEnum,
  MidFunction,
  MidImport,
  MidModule,
  MidModuleConst,
  MidOpaque,
)


def _opaque_ok(source: str) -> bool:
  s = source.strip()
  if not s:
    return True
  if s.startswith("#"):
    return True
  if s.startswith('"""') or s.startswith("'''"):
    return True
  if s.startswith("from ") or s.startswith("import "):
    return True
  # 模块导出表不影响 Mid emit 结构判定
  if s.startswith("__all__"):
    return True
  # 孤立 ``...`` 存根（模块/类残留）
  core = s.strip()
  if core in ("...", "pass") or core.startswith("...\n") or core == "...":
    return True
  # 仅省略号/注释拼段
  if all(
    ln.strip() in ("", "...", "pass") or ln.strip().startswith("#")
    for ln in core.splitlines()
  ):
    return True
  # ``type Alias[...] = ...`` 别名（emit 可跳过；完整结构化另议）
  if core.startswith("type ") and "=" in core:
    return True
  # 模块级注解/赋值常量（可跨行括号字符串）；emit 可跳过
  # 去掉尾部纯注释行再判
  lines = [ln for ln in core.splitlines() if ln.strip() and not ln.strip().startswith("#")]
  joined = "\n".join(lines).strip()
  if joined and ("=" in joined or ":" in joined):
    head = joined.split(":", 1)[0].split("=", 1)[0].strip()
    if head.isidentifier() and len(joined) < 800:
      return True
  # 测例入口：``if __name__ == "__main__":``（emit 跳过；不挡 mid_ok）
  head0 = lines[0].strip() if lines else ""
  if head0.startswith("if __name__") and "==" in head0 and "__main__" in head0:
    return True
  return False


def can_emit_mid(mid: MidModule) -> bool:
  if not _module_fully_structured(mid):
    return False
  for item in mid.items:
    if isinstance(item, MidOpaque) and not _opaque_ok(item.source):
      return False
    if isinstance(item, MidFunction) and not _body_structured(item.body):
      return False
    if isinstance(item, MidClass):
      for m in item.methods:
        if not _body_structured(m.body):
          return False
  return True


def _body_structured(body: list[StmtSyntax]) -> bool:
  for s in body:
    if isinstance(s, OpaqueStmtSyntax):
      # 嵌套 ``def`` / ``class`` / 装饰器暂不结构化，但不挡 mid-emit 门闩（物化仍走 AST）
      raw = s.source.strip()
      head = raw.split(None, 1)[0] if raw else ""
      if head in ("def", "async", "class", "return", "yield"):
        continue
      if raw.startswith("@") or raw.startswith("*"):
        continue
      if raw in ("...", "pass", ":"):
        continue
      return False
    if isinstance(s, IfStmt):
      if not _body_structured(s.body) or not _body_structured(s.orelse):
        return False
    elif isinstance(s, (WhileStmt, ForStmt, WithStmt)):
      if not _body_structured(s.body):
        return False
    elif isinstance(s, MatchStmt):
      for c in s.cases:
        if not _body_structured(c.body):
          return False
    elif isinstance(s, TryStmt):
      if not _body_structured(s.body):
        return False
      for h in s.handlers:
        if not _body_structured(h.body):
          return False
      if not _body_structured(s.orelse) or not _body_structured(s.finalbody):
        return False
  return True


def _module_path_of(mid: MidModule, override: str | None = None) -> str:
  if override:
    return override.replace("\\", "/").strip("/")
  p = (mid.path or "module").replace("\\", "/")
  if p.endswith(".paw") or p.endswith(".py"):
    p = p.rsplit(".", 1)[0]
  return p.strip("/")


def _ns_segments(module_path: str, module_ns: str | None = None) -> list[str]:
  """``compiler/paw/frontend/lexer`` → ``[compiler, seed, lexer]``；``module_ns='a::b'`` 优先。"""
  if module_ns:
    if "::" in module_ns:
      return [s for s in module_ns.split("::") if s]
    return [module_ns]
  return [s for s in module_path.split("/") if s]


def _open_namespaces(segs: list[str]) -> list[str]:
  lines: list[str] = []
  for s in segs:
    lines.append(f"namespace {s}")
    lines.append("{")
  return lines


def _close_namespaces(segs: list[str]) -> list[str]:
  return [f"}} // namespace {s}" for s in reversed(segs)]


def emit_mid_module(
  mid: MidModule,
  *,
  out_dir: Path,
  module_ns: str | None = None,
  module_path: str | None = None,
  stdlib_layout: bool = False,
) -> tuple[Path, Path]:
  """写出 ``{stem}.h`` / ``{stem}.cpp``，返回路径。

  ``module_path``（如 ``compiler/paw/frontend/lexer``）决定嵌套命名空间与相对 ``#include``；
  未传时从 ``mid.path`` 推导。``module_ns`` 可覆盖命名空间（含 ``a::b``）。

  ``stdlib_layout=True``：对齐 AST stdlib 产物——``.h`` 尾部 ``#include`` 本模块
  ``.inl``，实现写入 ``.inl``，``.cpp`` 为 ``PY2CPP_LIBRARY_TU`` + umbrella + inl。
  """
  mp = _module_path_of(mid, module_path)
  stem = Path(mp).name or "module"
  package_dir = "/".join(mp.split("/")[:-1])
  segs = _ns_segments(mp, module_ns)
  inl_rel = f"{mp}.inl" if stdlib_layout and mp else (f"{stem}.inl" if stdlib_layout else None)
  header = _emit_header(
    mid,
    segs,
    stem,
    module_path=mp,
    package_dir=package_dir,
    inl_include=inl_rel,
  )
  out_dir.mkdir(parents=True, exist_ok=True)
  h_path = out_dir / f"{stem}.h"
  c_path = out_dir / f"{stem}.cpp"
  h_path.write_text(header, encoding="utf-8", newline="\n")
  if stdlib_layout:
    inl_path = out_dir / f"{stem}.inl"
    inl_path.write_text(
      _emit_inl(mid, segs, stem, module_path=mp),
      encoding="utf-8",
      newline="\n",
    )
    c_path.write_text(
      _emit_stdlib_library_cpp(mp or stem),
      encoding="utf-8",
      newline="\n",
    )
  else:
    c_path.write_text(
      _emit_cpp(mid, segs, stem, module_path=mp),
      encoding="utf-8",
      newline="\n",
    )
  return h_path, c_path


_SCALAR_CPP = frozenset(
  {
    "void",
    "bool",
    "PyInt",
    "PyInt16",
    "PyInt64",
    "PyFloat",
    "PyFloat64",
    "float64",
    "PyChar",
    "PyByte",
    "PyBool",
  }
)


def _cpp_type(name: str | None) -> str:
  if not name:
    return "void"
  n = name.strip()
  if n.startswith("ref "):
    n = n[4:].strip()
  if n.startswith("lazy "):
    n = n[5:].strip()
  simple = {
    "str": "PyStr",
    "int": "PyInt",
    "bool": "bool",
    "float": "PyFloat",
    "float64": "float64",
    "None": "void",
  }
  if n in simple:
    return simple[n]
  if "[" in n:
    head, _, rest = n.partition("[")
    inner = rest.rstrip("]").strip()
    if head == "list":
      # ``list[T]`` / ``list[T, 0]`` → ``PyList<PyT, 0>``
      parts = [p.strip() for p in inner.split(",")]
      elem = _cpp_type(parts[0]) if parts and parts[0] else "PyObj"
      cap = parts[1] if len(parts) > 1 else "0"
      return f"PyList<{elem}, {cap}>"
    if head == "dict":
      parts = [p.strip() for p in inner.split(",")]
      if len(parts) >= 2:
        return f"PyDict<{_cpp_type(parts[0])}, {_cpp_type(parts[1])}>"
      return "PyDict"
  if "." in n:
    return "Py" + n.split(".")[-1]
  return "Py" + n[0].upper() + n[1:] if n else "void"


# 就地突变的类形参（Python 对象引用）；其余非标量用 ``const&`` 以绑定临时量。
_MUTABLE_REF_CPP = frozenset(
  {
    "PySyntaxModule",
    "PyEnumBundle",
    "PyClassBundle",
    "PyLexer",
    "PySourceManager",
  }
)


def _param_sig(ty: str, name: str) -> str:
  """对齐 Python 对象语义：标量按值；可变类 ``T&``；其它非标量 ``const T&``。"""
  if ty in _SCALAR_CPP or (ty.startswith("Py") and ty.endswith("Enum")):
    return f"{ty} {name}"
  if ty in _MUTABLE_REF_CPP:
    return f"{ty}& {name}"
  if ty.startswith("Py") or "<" in ty:
    return f"const {ty}& {name}"
  return f"{ty} {name}"


def _relative_import_include(
  source: str, *, package_dir: str = ""
) -> tuple[str, str, str] | None:
  """相对 import → ``(include, cpp_ns, names)``。

  - ``from .mod import Name``（同包单段）
  - ``from ..frontend.syntax_nodes import Name``（上溯 + 多段）

  ``package_dir=compiler/paw/mid`` + ``from ..frontend.syntax_nodes`` →
  include ``compiler/paw/frontend/syntax_nodes.h``，
  ns ``compiler::paw::frontend::syntax_nodes``。
  """
  s = source.strip()
  if not s.startswith("from "):
    return None
  rest = s[len("from ") :].strip()
  if not rest.startswith("."):
    return None
  dots = 0
  while dots < len(rest) and rest[dots] == ".":
    dots += 1
  rem = rest[dots:]
  if " import " not in rem:
    return None
  mod, _, names = rem.partition(" import ")
  mod_toks = mod.strip().split()
  # ``from . import Name`` / ``from .. import Name`` → 非本竖切
  if not mod_toks:
    return None
  mod = mod_toks[0]
  if not mod:
    return None
  pkg_parts = [p for p in package_dir.split("/") if p] if package_dir else []
  up = dots - 1
  if up < 0 or up > len(pkg_parts):
    return None
  base = pkg_parts[:-up] if up else list(pkg_parts)
  mod_parts = [p for p in mod.replace("\\", "/").replace(".", "/").split("/") if p]
  full_parts = base + mod_parts
  if not full_parts:
    return None
  inc = "/".join(full_parts) + ".h"
  cpp_ns = "::".join(full_parts)
  return inc, cpp_ns, names.strip()


def _import_names(names: str) -> list[str]:
  """解析 ``import`` 名表（含括号换行）。"""
  s = names.replace("(", " ").replace(")", " ").replace("\n", " ")
  out: list[str] = []
  for part in s.split(","):
    nm = part.strip()
    if not nm or nm == "*":
      continue
    # ``Name as Alias`` → 取原名（竖切不发别名）
    nm = nm.split()[0]
    if nm.isidentifier():
      out.append(nm)
  return out


def _is_type_attr_receiver(name: str) -> bool:
  """``ModeEnum.On`` / ``PermFlag.Read`` / ``Seal.MAX`` → 类型侧静态成员。"""
  if not name or not name[:1].isupper():
    return False
  return True


# ``_emit_stmt`` 嵌套期间的局部声明名（避免 ``Class()`` 被当成类型构）
_DECL_STACK: list[set[str]] = []


def _declared_names() -> set[str]:
  return _DECL_STACK[-1] if _DECL_STACK else set()


def _rewrite_match_pat(pat: str) -> str:
  """``TokenKindEnum.At`` / ``PermFlag.Read`` → ``Py…::…``；其余原样。"""
  p = pat.strip()
  if "." in p and not (p.startswith('"') or p.startswith("'")):
    head, _, tail = p.partition(".")
    if head.isidentifier() and tail.isidentifier() and _is_type_attr_receiver(head):
      return f"{_cpp_type(head)}::{tail}"
  return p


def _emit_header(
  mid: MidModule,
  segs: list[str],
  stem: str,
  *,
  module_path: str,
  package_dir: str,
  inl_include: str | None = None,
) -> str:
  guard = "_".join(s.upper() for s in segs) + "_H" if segs else f"{stem.upper()}_H"
  lines = [
    f"// MidIR emit (no CPython AST) — {module_path}",
    f"#ifndef {guard}",
    f"#define {guard}",
    "",
    '#include "py2cpp/minimal.h"',
  ]
  usings: list[str] = []
  for item in mid.items:
    if isinstance(item, MidImport):
      rel = _relative_import_include(item.source, package_dir=package_dir)
      if rel is not None:
        hdr, cpp_ns, names = rel
        lines.append(f'#include "{hdr}"')
        for nm in _import_names(names):
          cpp = f"Py{nm}" if nm[:1].isupper() else nm
          usings.append(f"  using ::{cpp_ns}::{cpp};")
      else:
        lines.append(f"// import: {item.source.strip()}")
  lines.append("")
  lines.extend(_open_namespaces(segs))
  indent = "  " * len(segs) if segs else ""
  body_indent = indent + ("  " if segs else "")
  # 兼容：无段时仍缩进一层
  if not segs:
    body_indent = "  "
  lines.append(f"{body_indent}using namespace py2cpp;")
  lines.append(
    f"{body_indent}using ::py2cpp::core::exceptions::PyValueError;"
  )
  lines.append(
    f"{body_indent}using ::py2cpp::core::exceptions::PyRuntimeError;"
  )
  lines.append(
    f"{body_indent}using ::py2cpp::core::exceptions::PyAssertionError;"
  )
  for u in usings:
    # usings 形如 ``  using ::ns::PyX;`` → 换成 body_indent
    core = u.lstrip()
    lines.append(f"{body_indent}{core}")
  for item in mid.items:
    if isinstance(item, MidImport):
      continue
    elif isinstance(item, MidEnum):
      from compiler.py.passes.apply_mid_decls import _parse_mid_enum_base

      scalar, _parent = _parse_mid_enum_base(item.base_source)
      underlying = "long long" if scalar == "int64" else "int"
      lines.append(f"{body_indent}enum class Py{item.name} : {underlying} {{")
      for name, val in item.members:
        if val is not None and val.strip() not in ("...", "Ellipsis"):
          lines.append(f"{body_indent}  {name} = {val},")
        else:
          lines.append(f"{body_indent}  {name},")
      lines.append(f"{body_indent}}};")
    elif isinstance(item, MidClass):
      lines.append(f"{body_indent}class Py{item.name};")
  for item in mid.items:
    if isinstance(item, MidFunction):
      lines.append(f"{body_indent}{_fn_decl(item)};")
  for item in mid.items:
    if isinstance(item, MidClass):
      for raw in _class_decl(item):
        # _class_decl 行以两个空格开头
        if raw.startswith("  "):
          lines.append(body_indent + raw[2:])
        else:
          lines.append(body_indent + raw)
  lines.extend(_close_namespaces(segs))
  if inl_include:
    lines += ["", f'#include "{inl_include}"']
  lines += ["", f"#endif // {guard}", ""]
  return "\n".join(lines)


def _enum_member_cpp(default_source: str) -> str | None:
  """``TokenKindEnum.End`` / ``ItemKindEnum.Opaque`` → ``PyTokenKindEnum::End``。"""
  d = default_source.strip()
  if "." not in d or d.startswith(".") or "(" in d or "[" in d:
    return None
  left, _, right = d.partition(".")
  if not left.isidentifier() or not right.isidentifier():
    return None
  if not left.endswith("Enum") and not left[0].isupper():
    return None
  return f"Py{left}::{right}"


def _default_cpp(default_source: str | None, ty: str) -> str:
  """形参/字段默认值 → C++ 初始化子（NSDMI 或形参默认）。"""
  if default_source is None:
    return ""
  d = default_source.strip()
  if not d:
    return ""
  if d in ("None", "none"):
    return ""
  if d in ("True", "False"):
    return f" = {'true' if d == 'True' else 'false'}"
  if d == "[]" or d == "{}":
    return f" = {ty}{{}}" if ty and ty != "void" else ""
  if (d.startswith('"') or d.startswith("'")) and (
    ty == "PyStr" or ty.startswith("Py")
  ):
    return f" = PyStr({d})"
  if d.startswith("new(") or d == "new()":
    return f" = {ty}{{}}" if ty and ty != "void" else ""
  enum_d = _enum_member_cpp(d)
  if enum_d is not None:
    return f" = {enum_d}"
  return f" = {d}"


def _fn_decl(fn: MidFunction, *, method: bool = False) -> str:
  ret = _cpp_type(fn.return_source)
  params = []
  for p in fn.params:
    if p.name == "self":
      continue
    ty = _cpp_type(type_syntax_to_source(p.type_syntax) if p.type_syntax else None)
    head = _param_sig(ty, p.name) + _default_cpp(p.default_source, ty)
    params.append(head)
  ps = ", ".join(params)
  return f"{ret} {fn.name}({ps})"


def _class_decl(cls: MidClass) -> list[str]:
  lines = [f"  class Py{cls.name}", "  {", "  public:"]
  for name, typ, val in cls.const_fields:
    ty = _cpp_type(typ)
    lines.append(f"    {ty} {name}{_default_cpp(val, ty)};")
  for name, typ, val in cls.fields:
    ty = _cpp_type(typ)
    lines.append(f"    {ty} {name}{_default_cpp(val, ty)};")
  # 兼容残留 opaque 字段行
  for raw in cls.opaque_members:
    s = raw.strip()
    if not s or s.startswith("#") or s.startswith("def ") or s.startswith("@"):
      continue
    if ":" in s:
      left, _, right = s.partition(":")
      fname = left.strip()
      ty_rhs = right.split("=", 1)
      ty_part = ty_rhs[0].strip()
      val_part = ty_rhs[1].strip() if len(ty_rhs) > 1 else None
      if fname.isidentifier():
        ty = _cpp_type(ty_part)
        lines.append(f"    {ty} {fname}{_default_cpp(val_part, ty)};")
  has_init = any(m.name == "__init__" for m in cls.methods)
  if has_init:
    init = next(m for m in cls.methods if m.name == "__init__")
    # 构造函数声明（跳过 self）
    iparams = []
    for p in init.params:
      if p.name == "self":
        continue
      ty = _cpp_type(type_syntax_to_source(p.type_syntax) if p.type_syntax else None)
      iparams.append(_param_sig(ty, p.name))
    lines.append(f"    explicit Py{cls.name}({', '.join(iparams)});")
  else:
    lines.append(f"    explicit Py{cls.name}() = default;")
  for m in cls.methods:
    if m.name in ("__init__", "__bool__", "__repr__", "__str__"):
      continue
    lines.append(f"    {_fn_decl(m, method=True)};")
  lines.append("  };")
  if cls.object_model == ObjectModel.REF_COUNT:
    lines.append(f"  // refcount model: Py{cls.name}")
  return lines


def _emit_impl_body(
  mid: MidModule, segs: list[str], *, module_path: str
) -> list[str]:
  """命名空间内实现体（无 ``#include``；供 ``.cpp`` / ``.inl`` 共用）。"""
  lines: list[str] = []
  lines.extend(_open_namespaces(segs))
  body_indent = "  " * len(segs) if segs else "  "
  for item in mid.items:
    if isinstance(item, MidModuleConst):
      lines.append(
        f"{body_indent}// const {item.name}: {item.type_name} = {item.value_source}"
      )
    elif isinstance(item, MidFunction):
      lines.extend(_fn_def(item, indent=body_indent))
    elif isinstance(item, MidClass):
      for m in item.methods:
        if m.name.startswith("__") and m.name not in ("__init__",):
          continue
        lines.extend(_method_def(item.name, m, indent=body_indent))
  lines.extend(_close_namespaces(segs))
  lines.append("")
  return lines


def _emit_cpp(
  mid: MidModule, segs: list[str], stem: str, *, module_path: str
) -> str:
  inc = f"{module_path}.h" if module_path else f"{stem}.h"
  lines = [
    f"// MidIR emit — {module_path}",
    f'#include "{inc}"',
    "",
  ]
  lines.extend(_emit_impl_body(mid, segs, module_path=module_path))
  return "\n".join(lines)


def _emit_inl(
  mid: MidModule, segs: list[str], stem: str, *, module_path: str
) -> str:
  """stdlib 布局：实现进 ``.inl``（由 ``.h`` / library ``.cpp`` include）。"""
  _ = stem
  lines = [
    f"// MidIR emit inl — {module_path}",
    "",
  ]
  lines.extend(_emit_impl_body(mid, segs, module_path=module_path))
  return "\n".join(lines)


def _emit_stdlib_library_cpp(module_path: str) -> str:
  """对齐 AST library TU：``PY2CPP_LIBRARY_TU`` + umbrella + ``.inl``。"""
  return "\n".join(
    [
      f"// MidIR emit library TU — {module_path}",
      "#define PY2CPP_LIBRARY_TU",
      '#include "py2cpp.h"',
      f'#include "{module_path}.inl"',
      "",
    ]
  )


def _fn_def(fn: MidFunction, *, indent: str) -> list[str]:
  ret = _cpp_type(fn.return_source)
  params = []
  for p in fn.params:
    if p.name == "self":
      continue
    ty = _cpp_type(type_syntax_to_source(p.type_syntax) if p.type_syntax else None)
    params.append(_param_sig(ty, p.name))
  sig = f"{indent}{ret} {fn.name}({', '.join(params)})"
  lines = [sig, indent + "{"]
  declared = {p.name for p in fn.params if p.name != "self"}
  lines.extend(
    _emit_stmts(fn.body, indent + "  ", ret, in_method=False, declared=declared)
  )
  lines.append(indent + "}")
  return lines


def _method_def(cls: str, fn: MidFunction, *, indent: str) -> list[str]:
  params = []
  for p in fn.params:
    if p.name == "self":
      continue
    ty = _cpp_type(type_syntax_to_source(p.type_syntax) if p.type_syntax else None)
    params.append(_param_sig(ty, p.name))
  ps = ", ".join(params)
  if fn.name == "__init__":
    # 构造函数：``PyCls::PyCls(...)``
    sig = f"{indent}Py{cls}::Py{cls}({ps})"
    ret = "void"
  else:
    ret = _cpp_type(fn.return_source)
    sig = f"{indent}{ret} Py{cls}::{fn.name}({ps})"
  lines = [sig, indent + "{"]
  declared = {p.name for p in fn.params if p.name != "self"}
  lines.extend(
    _emit_stmts(fn.body, indent + "  ", ret, in_method=True, declared=declared)
  )
  lines.append(indent + "}")
  return lines


def _emit_stmts(
  body: list[StmtSyntax],
  indent: str,
  ret_ty: str,
  *,
  in_method: bool = False,
  declared: set[str] | None = None,
) -> list[str]:
  out: list[str] = []
  decl = declared if declared is not None else set()
  for st in body:
    out.extend(
      _emit_stmt(st, indent, ret_ty, in_method=in_method, declared=decl)
    )
  return out


# 与 ``src/emit/layout_config_emit.py`` 一致
_SLICE_START_UNSET = -2000000001
_SLICE_STOP_UNSET = -2000000002


def _str_literal_value(text: str) -> str | None:
  """``\"a\"`` / ``'\\n'`` → 解码后的 Python str；失败返回 None。"""
  try:
    import ast as _ast

    v = _ast.literal_eval(text)
    return v if isinstance(v, str) else None
  except Exception:
    return None


def _emit_pychar_from_str_literal(text: str) -> str | None:
  v = _str_literal_value(text)
  if v is not None and len(v) == 1:
    return f"PyChar({ord(v)})"
  return None


def _emit_list_assign(
  target_cpp: str, elts: list[ExprSyntax], indent: str, *, in_method: bool
) -> list[str]:
  """``xs = [a, b]`` → decltype 默构 + append（PyList 无 init-list 构造）。"""
  lines = [indent + f"{target_cpp} = decltype({target_cpp}){{}};"]
  for el in elts:
    lines.append(
      indent
      + f"(void)({target_cpp}.append({_emit_expr(el, in_method=in_method)}));"
    )
  return lines


def _is_int_index_subscript(e: ExprSyntax) -> bool:
  return isinstance(e, SubscriptExpr) and not isinstance(e.slice, SliceExpr)


def _coerce_to_pystr(expr_cpp: str, value: ExprSyntax, dest_ty: str) -> str:
  """``str`` 目标且 RHS 为 ``s[i]``（得 ``PyChar``）→ ``PyStr(...)``。"""
  if dest_ty == "PyStr" and _is_int_index_subscript(value):
    return f"PyStr({expr_cpp})"
  return expr_cpp


def _emit_cmp_side(
  e: ExprSyntax, other: ExprSyntax, *, in_method: bool
) -> str:
  """比较两侧：``s[i]`` 对单字符字面量时发 ``PyChar``（避免 PyChar/PyStr C4805）。"""
  if (
    isinstance(e, LiteralExpr)
    and e.kind == "str"
    and _is_int_index_subscript(other)
  ):
    pc = _emit_pychar_from_str_literal(e.text)
    if pc is not None:
      return pc
  return _emit_expr(e, in_method=in_method)
def _emit_stmt(
  st: StmtSyntax,
  indent: str,
  ret_ty: str,
  *,
  in_method: bool = False,
  declared: set[str] | None = None,
) -> list[str]:
  decl = declared if declared is not None else set()
  _DECL_STACK.append(decl)
  try:
    return _emit_stmt_body(
      st, indent, ret_ty, in_method=in_method, declared=decl
    )
  finally:
    _DECL_STACK.pop()


def _emit_stmt_body(
  st: StmtSyntax,
  indent: str,
  ret_ty: str,
  *,
  in_method: bool = False,
  declared: set[str],
) -> list[str]:
  decl = declared
  match st:
    case PassStmt():
      return [indent + "(void)0;"]
    case BreakStmt():
      return [indent + "break;"]
    case ContinueStmt():
      return [indent + "continue;"]
    case GlobalStmt(names=ns):
      # Python 作用域声明；C++ 无对应语句（名称已在外层绑定）
      return [indent + f"/* global {', '.join(ns)} */"]
    case NonlocalStmt(names=ns):
      return [indent + f"/* nonlocal {', '.join(ns)} */"]
    case ReturnStmt(value=None):
      return [indent + "return;"] if ret_ty == "void" else [indent + f"return {ret_ty}();"]
    case ReturnStmt(value=v):
      if isinstance(v, CallExpr) and isinstance(v.func, NameExpr) and v.func.name == "new":
        return _emit_new_return(v, ret_ty, indent, in_method=in_method)
      rhs = _coerce_to_pystr(
        _emit_expr(v, in_method=in_method), v, ret_ty
      )
      return [indent + f"return {rhs};"]
    case RaiseStmt(exc=exc):
      if exc is None:
        return [indent + 'throw PyRuntimeError(PyStr("raise"));']
      return [indent + f"throw {_emit_expr(exc, in_method=in_method)};"]
    case AssignStmt(target=t, value=v):
      # 局部名首次赋值 → ``auto``；再赋值不带 auto
      if isinstance(t, NameExpr):
        if isinstance(v, ListExpr):
          if t.name not in decl:
            decl.add(t.name)
            # 无类型的 list 局部：先跳过（少见）；带注解走 AnnAssign
            return _emit_list_assign(t.name, v.elts, indent, in_method=in_method)
          return _emit_list_assign(t.name, v.elts, indent, in_method=in_method)
        if (
          isinstance(v, CallExpr)
          and isinstance(v.func, NameExpr)
          and v.func.name == "new"
          and t.name in decl
        ):
          rhs = _emit_new_expr(
            v.args, v.keywords, ty=f"decltype({t.name})", in_method=in_method
          )
          if "\n" in rhs:
            padded = rhs.replace("\n", "\n" + indent)
            return [indent + f"{t.name} = {padded};"]
          return [indent + f"{t.name} = {rhs};"]
        rhs = _emit_expr(v, in_method=in_method)
        if t.name not in decl:
          decl.add(t.name)
          return [indent + f"auto {t.name} = {rhs};"]
        return [indent + f"{t.name} = {rhs};"]
      lt = _emit_expr(t, in_method=in_method)
      if isinstance(v, ListExpr):
        return _emit_list_assign(lt, v.elts, indent, in_method=in_method)
      return [indent + f"{lt} = {_emit_expr(v, in_method=in_method)};"]
    case AugAssignStmt(target=t, op=op, value=v):
      # ``+=`` 等：展开为 ``t = (t + v)``。PyStr 等有 ``operator+`` / ``__add__``，无 ``operator+=``。
      lt = _emit_expr(t, in_method=in_method)
      rv = _emit_expr(v, in_method=in_method)
      if isinstance(op, str) and op.endswith("=") and len(op) > 1:
        bin_op = op[:-1]
        if bin_op == "//":
          return [indent + f"{lt} = __floordiv__({lt}, {rv});"]
        if bin_op == "/":
          return [indent + f"{lt} = __truediv__({lt}, {rv});"]
        if bin_op == "%":
          return [indent + f"{lt} = __mod__({lt}, {rv});"]
        if bin_op == "**":
          return [indent + f"{lt} = __pow__({lt}, {rv});"]
        return [indent + f"{lt} = ({lt} {bin_op} {rv});"]
      return [indent + f"{lt} {op} {rv};"]
    case AnnAssignStmt(target=t, annotation=ann, value=v):
      if v is None:
        return []
      # ``x: T = new(...)``：按注解类型展开 IIFE
      if (
        isinstance(v, CallExpr)
        and isinstance(v.func, NameExpr)
        and v.func.name == "new"
        and isinstance(t, NameExpr)
      ):
        decl.add(t.name)
        ty = _cpp_type(type_syntax_to_source(ann) if ann is not None else None)
        expr = _emit_new_expr(v.args, v.keywords, ty=ty, in_method=in_method)
        if "\n" in expr:
          padded = expr.replace("\n", "\n" + indent)
          return [indent + f"{ty} {t.name} = {padded};"]
        return [indent + f"{ty} {t.name} = {expr};"]
      # 局部 ``x: T = v`` 用类型名；``self.x: T = v`` 仅赋值
      if isinstance(t, NameExpr):
        decl.add(t.name)
        ty = _cpp_type(type_syntax_to_source(ann) if ann is not None else None)
        if isinstance(v, ListExpr) and ty and ty != "void":
          return [indent + f"{ty} {t.name}{{}};"] + [
            indent
            + f"(void)({t.name}.append({_emit_expr(el, in_method=in_method)}));"
            for el in v.elts
          ]
        if ty and ty != "void":
          rhs = _coerce_to_pystr(
            _emit_expr(v, in_method=in_method), v, ty
          )
          return [indent + f"{ty} {t.name} = {rhs};"]
        return [
          indent + f"auto {t.name} = {_emit_expr(v, in_method=in_method)};"
        ]
      lt = _emit_expr(t, in_method=in_method)
      if isinstance(v, ListExpr):
        return _emit_list_assign(lt, v.elts, indent, in_method=in_method)
      return [indent + f"{lt} = {_emit_expr(v, in_method=in_method)};"]
    case ExprStmt(value=v):
      return [indent + f"(void)({_emit_expr(v, in_method=in_method)});"]
    case IfStmt(test=test, body=body, orelse=orelse):
      lines = [indent + f"if ({_emit_expr(test, in_method=in_method)}) {{"]
      for s in body:
        lines.extend(
          _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
        )
      lines.append(indent + "}")
      if orelse:
        if len(orelse) == 1 and isinstance(orelse[0], IfStmt):
          nested = _emit_stmt(
            orelse[0], indent, ret_ty, in_method=in_method, declared=decl
          )
          if nested and nested[0].lstrip().startswith("if ("):
            nested[0] = indent + "else " + nested[0].lstrip()
          lines.extend(nested)
        else:
          lines.append(indent + "else {")
          for s in orelse:
            lines.extend(
              _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
            )
          lines.append(indent + "}")
      return lines
    case WhileStmt(test=test, body=body):
      lines = [indent + f"while ({_emit_expr(test, in_method=in_method)}) {{"]
      for s in body:
        lines.extend(
          _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
        )
      lines.append(indent + "}")
      return lines
    case ForStmt(target=t, iter=it, body=body):
      tgt = _emit_expr(t, in_method=in_method)
      if isinstance(t, NameExpr):
        decl.add(t.name)
      # ``for i in range(n):`` → C 风格计数循环（避免与命名空间 range 冲突）
      if (
        isinstance(it, CallExpr)
        and isinstance(it.func, NameExpr)
        and it.func.name == "range"
        and it.args
      ):
        if len(it.args) == 1:
          n = _emit_expr(it.args[0], in_method=in_method)
          lines = [indent + f"for (PyInt {tgt} = 0; {tgt} < {n}; ++{tgt}) {{"]
        elif len(it.args) >= 2:
          a0 = _emit_expr(it.args[0], in_method=in_method)
          a1 = _emit_expr(it.args[1], in_method=in_method)
          lines = [indent + f"for (PyInt {tgt} = {a0}; {tgt} < {a1}; ++{tgt}) {{"]
        else:
          lines = [
            indent
            + f"for (auto {tgt} : {_emit_expr(it, in_method=in_method)}) {{"
          ]
      else:
        # PyList 无 begin/end：下标循环
        it_cpp = _emit_expr(it, in_method=in_method)
        idx = f"__i_{tgt}" if isinstance(t, NameExpr) else "__i"
        lines = [
          indent
          + f"for (PyInt {idx} = 0; {idx} < ({it_cpp}).__len__(); ++{idx}) {{",
          indent + f"  auto {tgt} = ({it_cpp}).__getitem__({idx});",
        ]
        body_indent = indent + "  "
        for s in body:
          lines.extend(
            _emit_stmt(
              s, body_indent, ret_ty, in_method=in_method, declared=decl
            )
          )
        lines.append(indent + "}")
        return lines
      for s in body:
        lines.extend(
          _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
        )
      lines.append(indent + "}")
      return lines
    case MatchStmt(subject=subj, cases=cases):
      # 非整数主体用 if/else（PyStr 不能 switch）
      sub = _emit_expr(subj, in_method=in_method)
      lines: list[str] = []
      for i, c in enumerate(cases):
        pat = c.pattern_source.strip()
        is_else = pat == "_"
        if is_else:
          lines.append(indent + "else {")
        else:
          alts = [a.strip() for a in pat.split("|")]
          conds = []
          for a in alts:
            if len(a) >= 2 and a[0] in "\"'" and a[-1] == a[0]:
              conds.append(f"(({sub}) == PyStr({a}))")
            else:
              conds.append(f"(({sub}) == ({_rewrite_match_pat(a)}))")
          kw = "if" if i == 0 else "else if"
          lines.append(indent + f"{kw} ({' || '.join(conds)}) {{")
        for s in c.body:
          lines.extend(
            _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
          )
        lines.append(indent + "}")
      return lines
    case TryStmt(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody):
      lines = [indent + "try {"]
      for s in body:
        lines.extend(
          _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
        )
      lines.append(indent + "}")
      for h in handlers:
        tag = (
          _emit_expr(h.type_expr, in_method=in_method)
          if h.type_expr is not None
          else "..."
        )
        bind = f" {h.name}" if h.name else ""
        lines.append(indent + f"catch (/* {tag}{bind} */) {{")
        for s in h.body:
          lines.extend(
            _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
          )
        lines.append(indent + "}")
      if orelse:
        lines.append(indent + "// try-else")
        lines.append(indent + "{")
        for s in orelse:
          lines.extend(
            _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
          )
        lines.append(indent + "}")
      if finalbody:
        lines.append(indent + "// finally")
        lines.append(indent + "{")
        for s in finalbody:
          lines.extend(
            _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
          )
        lines.append(indent + "}")
      return lines
    case WithStmt(items=items, body=body):
      lines = [
        indent
        + "// with "
        + ", ".join(
          _emit_expr(it.context_expr, in_method=in_method)
          + (
            f" as {_emit_expr(it.optional_vars, in_method=in_method)}"
            if it.optional_vars
            else ""
          )
          for it in items
        )
      ]
      lines.append(indent + "{")
      for s in body:
        lines.extend(
          _emit_stmt(s, indent + "  ", ret_ty, in_method=in_method, declared=decl)
        )
      lines.append(indent + "}")
      return lines
    case AssertStmt(test=test, msg=msg):
      m = (
        _emit_expr(msg, in_method=in_method)
        if msg is not None
        else 'PyStr("assert")'
      )
      return [
        indent
        + f"if (!({_emit_expr(test, in_method=in_method)})) {{ throw PyAssertionError({m}); }}"
      ]
    case OpaqueStmtSyntax(source=src):
      return [indent + f"/* opaque: {src[:60]} */"]
    case _:
      return [indent + "/* unsupported stmt */"]


def _guess_new_type(kws: list[tuple[str, ExprSyntax]]) -> str | None:
  """无注解 ``new(f=…)`` 时按字段名猜 seed 常用类型。"""
  keys = {k for k, _ in kws}
  if {"fileId", "start", "end"} <= keys:
    return "PySourceSpan"
  if {"ok", "endI"} <= keys:
    return "PyParseAdvance"
  if {"name", "bodyStart", "endSpan"} <= keys:
    return "PyDeclTail"
  if "kind" in keys and "sourceSpan" in keys:
    return "PyModuleItem"
  if "kind" in keys and "span" in keys and "text" in keys:
    return "PyToken"
  return None


def _emit_new_expr(
  args: list[ExprSyntax],
  kws: list[tuple[str, ExprSyntax]],
  *,
  ty: str | None,
  in_method: bool = False,
) -> str:
  """``new()`` / ``new(f=v, …)`` → 默构或立即调用 lambda 填字段。"""
  if not args and not kws:
    return f"{ty}{{}}" if ty and ty != "void" else "{}"
  if not kws and args:
    # 位置实参 ``new(a, b)``：按构造实参转发
    inner = ", ".join(_emit_expr(a, in_method=in_method) for a in args)
    return f"{ty}({inner})" if ty and ty != "void" else f"/*new*/({inner})"
  if not ty or ty == "void":
    ty = _guess_new_type(kws) or ty
  if not ty or ty == "void":
    if not kws:
      return "{}"
    parts = ", ".join(
      f"/*{k}*/ {_emit_expr(v, in_method=in_method)}" for k, v in kws
    )
    return f"({{ /*new fields*/ {parts} }})"
  lines = [f"([&]() -> {ty} {{", f"  {ty} __o{{}};"]
  for k, v in kws:
    if (
      isinstance(v, CallExpr)
      and isinstance(v.func, NameExpr)
      and v.func.name == "new"
      and not v.args
      and not v.keywords
    ):
      # 赋值右侧不能写裸 ``{}``（MSVC 拒 initializer_list）；用 decltype 默构
      lines.append(f"  __o.{k} = decltype(__o.{k}){{}};")
    else:
      lines.append(f"  __o.{k} = {_emit_expr(v, in_method=in_method)};")
  lines.append("  return __o;")
  lines.append("})()")
  return "\n".join(lines)

def _emit_new_return(
  call: CallExpr, ret_ty: str, indent: str, *, in_method: bool = False
) -> list[str]:
  """``return new(...)`` 展开为可编译语句（多行 IIFE）。"""
  expr = _emit_new_expr(call.args, call.keywords, ty=ret_ty, in_method=in_method)
  if "\n" not in expr:
    return [indent + f"return {expr};"]
  # 多行：整段作为 return 表达式
  padded = expr.replace("\n", "\n" + indent)
  return [indent + f"return {padded};"]


def _emit_expr(e: ExprSyntax, *, in_method: bool = False) -> str:
  match e:
    case NameExpr(name="self") if in_method:
      return "(*this)"
    case NameExpr(name=name):
      return name
    case LiteralExpr(kind=kind, text=text):
      if kind == "str":
        return f"PyStr({text})"
      if kind == "bool":
        return "true" if text == "True" else "false"
      if kind == "none":
        return "/* None */ nullptr"
      return text
    case AttributeExpr(value=NameExpr(name="self"), attr=a) if in_method:
      return f"this->{a}"
    case AttributeExpr(value=v, attr=a):
      # ``TokenKindEnum.Name`` / ``PermFlag.Read`` / ``Seal.MAX`` → ``Py…::…``
      # 局部变量（如 for 的 ``Class``）仍用 ``.``
      if (
        isinstance(v, NameExpr)
        and _is_type_attr_receiver(v.name)
        and v.name not in _declared_names()
      ):
        return f"{_cpp_type(v.name)}::{a}"
      return f"{_emit_expr(v, in_method=in_method)}.{a}"
    case ListExpr(elts=elts):
      inner = ", ".join(_emit_expr(x, in_method=in_method) for x in elts)
      return f"PyList({{{inner}}})"
    case TupleExpr(elts=elts):
      inner = ", ".join(_emit_expr(x, in_method=in_method) for x in elts)
      return f"PyTuple({{{inner}}})"
    case DictExpr(keys=keys, values=values):
      parts = []
      for k, v in zip(keys, values):
        if k is None:
          parts.append(_emit_expr(v, in_method=in_method))
        else:
          parts.append(
            f"{{{_emit_expr(k, in_method=in_method)}, {_emit_expr(v, in_method=in_method)}}}"
          )
      return f"PyDict({{{', '.join(parts)}}})"
    case SliceExpr(lower=lo, upper=up, step=st):
      a = (
        _emit_expr(lo, in_method=in_method)
        if lo is not None
        else str(_SLICE_START_UNSET)
      )
      b = (
        _emit_expr(up, in_method=in_method)
        if up is not None
        else str(_SLICE_STOP_UNSET)
      )
      step = (
        _emit_expr(st, in_method=in_method) if st is not None else "1"
      )
      return f"PySlice<PyInt, PyInt>({a}, {b}, {step})"
    case CallExpr(func=f, args=args, keywords=kws):
      if isinstance(f, NameExpr) and f.name == "new":
        return _emit_new_expr(args, kws, ty=None, in_method=in_method)
      # 已声明局部（``for Class in …: Class()``）勿当类型构造
      if isinstance(f, NameExpr) and f.name in _declared_names():
        ap = ", ".join(_emit_expr(a, in_method=in_method) for a in args)
        if kws:
          ap += (", " if ap else "") + ", ".join(
            f"/*{k}*/ {_emit_expr(v, in_method=in_method)}" for k, v in kws
          )
        return f"{f.name}({ap})"
      # ``SourceSpan(...)`` / ``ModuleItem(...)`` 等类型名构造 → 同 new IIFE
      if isinstance(f, NameExpr) and f.name[:1].isupper() and kws:
        return _emit_new_expr(
          args, kws, ty=_cpp_type(f.name), in_method=in_method
        )
      if isinstance(f, NameExpr) and f.name[:1].isupper() and not kws:
        # 位置构造 ``Lexer(text, fileId)`` / 空 ``FunctionBundle()``
        cal = _cpp_type(f.name)
        if not args:
          return f"{cal}{{}}"
        ap = ", ".join(_emit_expr(a, in_method=in_method) for a in args)
        return f"{cal}({ap})"
      if isinstance(f, NameExpr) and f.name == "str":
        return (
          f"PyStr({_emit_expr(args[0], in_method=in_method)})" if args else "PyStr()"
        )
      if isinstance(f, NameExpr) and f.name == "len" and args:
        return f"({_emit_expr(args[0], in_method=in_method)}).__len__()"
      if isinstance(f, NameExpr) and f.name in ("min", "max") and len(args) == 2:
        # 避免 Windows.h ``min``/``max`` 宏；用三目
        a0 = _emit_expr(args[0], in_method=in_method)
        a1 = _emit_expr(args[1], in_method=in_method)
        if f.name == "min":
          return f"(({a0}) < ({a1}) ? ({a0}) : ({a1}))"
        return f"(({a0}) > ({a1}) ? ({a0}) : ({a1}))"
      if isinstance(f, NameExpr) and f.name.endswith("Error"):
        ap = ", ".join(_emit_expr(a, in_method=in_method) for a in args)
        return f"Py{f.name}({ap})"
      cal = _emit_expr(f, in_method=in_method)
      ap = ", ".join(_emit_expr(a, in_method=in_method) for a in args)
      if kws:
        ap += (", " if ap else "") + ", ".join(
          f"/*{k}*/ {_emit_expr(v, in_method=in_method)}" for k, v in kws
        )
      return f"{cal}({ap})"
    case BinOpExpr(left=l, op=op, right=r):
      # ``+`` 用运算符：PyInt 无 ``__add__`` 成员，PyStr 有 ``operator+``
      if op == "+":
        return (
          f"({_emit_expr(l, in_method=in_method)} + "
          f"{_emit_expr(r, in_method=in_method)})"
        )
      if op == "//":
        return (
          f"__floordiv__({_emit_expr(l, in_method=in_method)}, "
          f"{_emit_expr(r, in_method=in_method)})"
        )
      if op == "/":
        return (
          f"__truediv__({_emit_expr(l, in_method=in_method)}, "
          f"{_emit_expr(r, in_method=in_method)})"
        )
      if op == "%":
        return (
          f"__mod__({_emit_expr(l, in_method=in_method)}, "
          f"{_emit_expr(r, in_method=in_method)})"
        )
      if op == "**":
        return (
          f"__pow__({_emit_expr(l, in_method=in_method)}, "
          f"{_emit_expr(r, in_method=in_method)})"
        )
      return f"({_emit_expr(l, in_method=in_method)} {op} {_emit_expr(r, in_method=in_method)})"
    case MatMultExpr(left=l, right=r):
      return f"({_emit_expr(l, in_method=in_method)}).__matmul__({_emit_expr(r, in_method=in_method)})"
    case UnaryOpExpr(op=op, operand=o):
      if op == "not":
        return f"!({_emit_expr(o, in_method=in_method)})"
      return f"({op}{_emit_expr(o, in_method=in_method)})"
    case CompareExpr(left=l, ops=ops, comparators=cs):
      parts = []
      prev: ExprSyntax = l
      cur = _emit_cmp_side(l, cs[0] if cs else l, in_method=in_method)
      for op, c in zip(ops, cs):
        # ``x in [a, b]`` / set→ListExpr：展开为相等链（免 PyList init-list）
        if op in ("in", "not in") and isinstance(c, (ListExpr, TupleExpr)):
          eqs = [
            f"(({cur}) == ({_emit_expr(el, in_method=in_method)}))"
            for el in c.elts
          ]
          joined = " || ".join(eqs) if eqs else "false"
          parts.append(joined if op == "in" else f"!({joined})")
          prev = c
          cur = _emit_expr(c, in_method=in_method)
          continue
        rhs = _emit_cmp_side(c, prev, in_method=in_method)
        if op == "is":
          parts.append(f"(({cur}) == ({rhs}))")
        elif op == "is not":
          parts.append(f"(({cur}) != ({rhs}))")
        elif op == "in":
          parts.append(f"({rhs}).__contains__({cur})")
        elif op == "not in":
          parts.append(f"!({rhs}).__contains__({cur})")
        else:
          # 再按对侧重算（``s[i] == 'x'``）
          left_cpp = _emit_cmp_side(prev, c, in_method=in_method)
          parts.append(f"({left_cpp} {op} {rhs})")
        prev = c
        cur = rhs
      return " && ".join(parts) if parts else "true"
    case BoolOpExpr(op=op, values=vs):
      join = " && " if op == "and" else " || "
      return "(" + join.join(_emit_expr(v, in_method=in_method) for v in vs) + ")"
    case SubscriptExpr(value=v, slice=s):
      # PyList 等无 ``operator[]``，走 ``__getitem__``
      if isinstance(s, SliceExpr):
        return (
          f"{_emit_expr(v, in_method=in_method)}"
          f".__getitem__({_emit_expr(s, in_method=in_method)})"
        )
      return (
        f"{_emit_expr(v, in_method=in_method)}"
        f".__getitem__({_emit_expr(s, in_method=in_method)})"
      )
    case IfExp(body=b, test=t, orelse=o):
      return (
        f"(({_emit_expr(t, in_method=in_method)})"
        f" ? ({_emit_expr(b, in_method=in_method)})"
        f" : ({_emit_expr(o, in_method=in_method)}))"
      )
    case _:
      return "/*expr*/"
