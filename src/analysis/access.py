"""按 Python 命名约定推断 C++ 访问级别（``_`` → protected，``__`` → private）。"""
from __future__ import annotations

import ast

from .ir import ClassInfo, strip_type_annotation_markers
from .type_emit import field_ann_ast

Access = str  # "public" | "protected" | "private"


def is_dunder(name: str) -> bool:
  return (
    len(name) > 4
    and name.startswith("__")
    and name.endswith("__")
    and name != "__"
  )


def default_member_access(name: str, _class_name: str = "") -> tuple[Access, str]:
  """返回 (访问级别, C++ 成员名)；C++ 与 Python 标识符一致。"""
  if is_dunder(name):
    return "public", name
  if name.startswith("__"):
    return "private", name
  if name.startswith("_"):
    return "protected", name
  return "public", name


def class_grants_friend_access(
  accessor: str,
  host: str,
  classes: dict[str, ClassInfo],
) -> bool:
  """``host`` 在类头声明 ``friends=(accessor, …)`` 时，``accessor`` 可访问 ``host`` 的 protected/private。"""
  host_info = classes.get(host)
  if host_info is None:
    return False
  return accessor in host_info.friend_classes


def class_extends(child: str, ancestor: str, classes: dict[str, ClassInfo]) -> bool:
  if child == ancestor:
    return True
  info = classes.get(child)
  if not info:
    return False
  for base in info.bases:
    if class_extends(base, ancestor, classes):
      return True
  return False


def _class_by_python_or_cpp_name(
  name: str,
  classes: dict[str, ClassInfo],
  import_bindings: dict,
  *,
  context: ClassInfo | None = None,
) -> str | None:
  if name == "Self":
    return context.name if context else None
  if name in classes:
    return name
  binding = import_bindings.get(name)
  if binding is not None and getattr(binding, "kind", None) == "class":
    return binding.symbol
  for info in classes.values():
    if info.cpp_name() == name:
      return info.name
  return None


def _class_from_annotation(
  ann: ast.expr | None,
  classes: dict[str, ClassInfo],
  import_bindings: dict,
  *,
  context: ClassInfo | None = None,
) -> str | None:
  if ann is None:
    return None
  ann = strip_type_annotation_markers(ann)
  if ann is None:
    return None
  match ann:
    case ast.Name(id=name):
      return _class_by_python_or_cpp_name(
        name, classes, import_bindings, context=context,
      )
    case ast.Subscript(value=ast.Name(id=name)):
      if name in classes:
        return name
      binding = import_bindings.get(name)
      if binding is not None and getattr(binding, "kind", None) == "class":
        return binding.symbol
    case _:
      return None


def _infer_receiver_class(
  recv: ast.expr,
  *,
  context: ClassInfo | None,
  func: ast.FunctionDef | None,
  classes: dict[str, ClassInfo],
  import_bindings: dict,
) -> str | None:
  match recv:
    case ast.Name(id="self") | ast.Name(id="Self") | ast.Name(id="new"):
      return context.name if context else None
    case ast.Name(id=name):
      if name in classes:
        return name
      binding = import_bindings.get(name)
      if binding is not None and getattr(binding, "kind", None) == "class":
        return binding.symbol
      if context and func and name == "other" and func.name in (
        "__init__",
        "__copy__",
        "__move__",
      ):
        return context.name
      if func and context:
        for arg in func.args.args:
          if arg.arg == name:
            cls = _class_from_annotation(
              arg.annotation, classes, import_bindings, context=context,
            )
            if cls:
              return cls
        for node in ast.walk(func):
          if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
          ):
            cls = _class_from_annotation(
              node.annotation, classes, import_bindings, context=context,
            )
            if cls:
              return cls
      resolved = _class_by_python_or_cpp_name(
        name, classes, import_bindings, context=context,
      )
      if resolved:
        return resolved
      return None
    case ast.Call(func=ast.Name(id="abs"), args=[arg, *_rest]) if len(_rest) == 0:
      return _infer_receiver_class(
        arg,
        context=context,
        func=func,
        classes=classes,
        import_bindings=import_bindings,
      )
    case ast.Call(func=ast.Name(id=cls_name)):
      return _class_by_python_or_cpp_name(
        cls_name, classes, import_bindings, context=context,
      )
    case ast.Attribute(value=val, attr=field_name):
      if (
        isinstance(val, ast.Name)
        and val.id == "self"
        and context is not None
      ):
        ann_node = field_ann_ast(context, field_name)
        if ann_node is not None:
          cls = _class_from_annotation(
            ann_node, classes, import_bindings, context=context,
          )
          if cls is not None:
            return cls
      host = _infer_receiver_class(
        val,
        context=context,
        func=func,
        classes=classes,
        import_bindings=import_bindings,
      )
      if host is not None:
        host_info = classes.get(host)
        if host_info is not None and field_name in host_info.fields:
          ann_node = field_ann_ast(host_info, field_name)
          if ann_node is not None:
            cls = _class_from_annotation(
              ann_node, classes, import_bindings, context=context,
            )
            if cls is not None:
              return cls
      return host
    case _:
      return None


def _access_is_internal(
  recv: ast.expr,
  recv_class: str,
  attr: str,
  *,
  context: ClassInfo | None,
  func: ast.FunctionDef | None,
  classes: dict[str, ClassInfo],
  import_bindings: dict,
) -> bool:
  if is_dunder(attr):
    return True
  if not attr.startswith("_"):
    return True
  cls_name = recv_class
  if cls_name not in classes:
    cls_name = _class_by_python_or_cpp_name(
      recv_class, classes, import_bindings, context=context,
    )
  if cls_name and cls_name in classes and (
    attr in classes[cls_name].static_class_fields
    or attr in getattr(classes[cls_name], "thread_local_fields", {})
  ):
    return True
  if isinstance(recv, ast.Name) and recv.id in ("self", "Self", "new"):
    if context and class_extends(context.name, recv_class, classes):
      return True
    return context is not None and context.name == recv_class
  if (
    context
    and isinstance(recv, ast.Name)
    and recv.id == recv_class
    and class_extends(context.name, recv_class, classes)
  ):
    return True
  if context and isinstance(recv, ast.Name) and recv_class:
    owner = _class_by_python_or_cpp_name(
      recv.id, classes, import_bindings, context=context,
    )
    if owner == context.name:
      return True
  if (
    context
    and func
    and isinstance(recv, ast.Name)
    and recv_class
    and class_extends(context.name, recv_class, classes)
  ):
    if recv.id in ("Self", "other", "new"):
      return True
    for arg in func.args.args:
      if arg.arg == recv.id:
        ann_cls = _class_from_annotation(
          arg.annotation,
          classes,
          import_bindings,
          context=context,
        )
        if ann_cls == recv_class:
          return True
    inferred = _infer_receiver_class(
      recv,
      context=context,
      func=func,
      classes=classes,
      import_bindings=import_bindings,
    )
    if inferred == recv_class:
      return True
  if (
    context
    and recv_class
    and class_grants_friend_access(context.name, recv_class, classes)
  ):
    return True
  if context and recv_class and context.name == recv_class:
    inferred = _infer_receiver_class(
      recv,
      context=context,
      func=func,
      classes=classes,
      import_bindings=import_bindings,
    )
    if inferred == recv_class:
      return True
  return False


def collect_external_protected_accesses(
  classes: dict[str, ClassInfo],
  module_functions: list[tuple[str, ast.FunctionDef]],
  module_asts: dict[str, ast.Module],
  import_bindings: dict,
) -> set[tuple[str, str, str]]:
  """跨类 / 模块级访问的 ``(访问方, 宿主类, 成员名)``。"""
  external: set[tuple[str, str, str]] = set()

  def walk(
    node: ast.AST,
    *,
    context: ClassInfo | None,
    func: ast.FunctionDef | None,
  ) -> None:
    for child in ast.walk(node):
      if not isinstance(child, ast.Attribute):
        continue
      attr = child.attr
      if not attr.startswith("_") or is_dunder(attr):
        continue
      recv_class = _infer_receiver_class(
        child.value,
        context=context,
        func=func,
        classes=classes,
        import_bindings=import_bindings,
      )
      if recv_class is None:
        for cls_info in classes.values():
          if (
            cls_info.is_mixin
            or cls_info.is_annotation
            or cls_info.is_protocol
          ):
            continue
          if (
            attr in cls_info.fields
            or attr in cls_info.methods
          ):
            accessor = context.name if context else "<module>"
            external.add((accessor, cls_info.name, attr))
        continue
      if not _access_is_internal(
        child.value,
        recv_class,
        attr,
        context=context,
        func=func,
        classes=classes,
        import_bindings=import_bindings,
      ):
        accessor = context.name if context else "<module>"
        external.add((accessor, recv_class, attr))

  for info in classes.values():
    if info.is_descriptor or info.is_mixin or info.is_annotation:
      continue
    for init in info.inits:
      walk(init, context=info, func=init)
    for method in info.iter_methods():
      walk(method, context=info, func=method)
    for prop in info.properties.values():
      if prop.getter:
        walk(prop.getter, context=info, func=prop.getter)
      if prop.setter:
        walk(prop.setter, context=info, func=prop.setter)
      if prop.postsetter:
        walk(prop.postsetter, context=info, func=prop.postsetter)
    for prop in info.static_properties.values():
      if prop.getter:
        walk(prop.getter, context=info, func=prop.getter)
      if prop.setter:
        walk(prop.setter, context=info, func=prop.setter)
      if prop.postsetter:
        walk(prop.postsetter, context=info, func=prop.postsetter)

  for _path, func in module_functions:
    walk(func, context=None, func=func)

  for _path, mod in module_asts.items():
    for node in mod.body:
      if isinstance(node, ast.FunctionDef):
        walk(node, context=None, func=node)

  return external


class ExternalProtectedAccessError(SyntaxError):
  """在其它类或模块级函数中访问 ``obj._member``。"""


def _external_protected_access_hint(accessor: str, host: str, member: str) -> str:
  if accessor == "<module>":
    return (
      f"  {host}.{member}  （模块级）"
      f" → 将逻辑移入 ``{host}`` 的方法，或提供非 ``_`` 公开 API"
    )
  if accessor != host:
    return (
      f"  {accessor} 访问 {host}.{member}  "
      f"→ 在 ``class {host}(friends=({accessor}, …))`` 声明友元"
      f"（被访问类声明，非访问方；见 ``test/lang/test_friends.py``）"
    )
  pub = member[1:] if member.startswith("_") else member
  return (
    f"  {host}.{member}  → 同类内 ``self.{member}`` / ``other.{member}``"
    f"（勿改为公开 ``{pub}``，优先友元）"
  )


def validate_module_friend_names(classes: dict[str, ClassInfo]) -> None:
  """``friends=(A,)`` 中的 ``A`` 须为已解析类名（同模块可前向，勿用字符串）。"""
  errors: list[str] = []
  for info in classes.values():
    if info.is_mixin or info.is_annotation or info.is_descriptor:
      continue
    for friend in info.friend_classes:
      fi = classes.get(friend)
      if fi is None:
        errors.append(
          f"  {info.name}.friends 含未定义类 ``{friend}``"
          f" → 确认同模块有 ``class {friend}``，且类名拼写一致"
        )
        continue
      if fi.module_path != info.module_path:
        errors.append(
          f"  {info.name}.friends 含 ``{friend}``（定义于 {fi.module_path}）"
          f" → 跨模块友元尚未支持，友元类须与宿主同文件模块"
        )
  if not errors:
    return
  lines = [
    "friends= 中的类名无法绑定到本翻译单元内的 class 定义。",
    "请写 ``friends=(Accessor, …)``（类名，非字符串）；同模块内友元类可在宿主之后定义（译器前向解析）。",
    "若需 CPython ``import`` 该模块，友元类须在宿主类执行前已绑定（通常写在宿主类之前）。",
  ]
  lines.extend(errors)
  raise SyntaxError("\n".join(lines))


def validate_no_external_protected_access(
  classes: dict[str, ClassInfo],
  module_functions: list[tuple[str, ast.FunctionDef]],
  module_asts: dict[str, ast.Module],
  import_bindings: dict,
  *,
  module_debug_files: dict[str, str] | None = None,
) -> None:
  external = collect_external_protected_accesses(
    classes, module_functions, module_asts, import_bindings
  )
  if not external:
    return
  lines: list[str] = [
    "受保护成员（单前导 ``_``）不能在无关类或模块级函数中访问。",
    "可选：同类内 ``self._x`` / ``other._x``；或在**被访问的类**上 "
    "``friends=(访问方, …)`` 声明友元（C++ ``friend class``，见编码规范 §2）。",
  ]
  for accessor, host, member in sorted(external):
    lines.append(_external_protected_access_hint(accessor, host, member))
  raise ExternalProtectedAccessError("\n".join(lines))


def resolve_member_access(
  classes: dict[str, ClassInfo],
  module_functions: list[tuple[str, ast.FunctionDef]],
  module_asts: dict[str, ast.Module],
  import_bindings: dict,
) -> None:
  for info in classes.values():
    if info.is_descriptor or info.is_mixin or info.is_annotation:
      continue
    info.member_access = {}
    info.member_cpp_names = {}
    names: set[str] = set(info.fields)
    names.update(info.methods)
    for overloads in info.method_overloads.values():
      names.update(ov.name for ov in overloads)
    names.update(info.static_class_fields)
    names.update(getattr(info, "thread_local_fields", {}))
    for prop in info.properties.values():
      names.add(prop.name)
    for name in names:
      acc, cpp = default_member_access(name, info.name)
      info.member_access[name] = acc
      if cpp != name:
        info.member_cpp_names[name] = cpp
