"""``Proxy[T]`` / ``super`` / ``Super`` 分析辅助。"""
from __future__ import annotations

import ast
import copy
from typing import TYPE_CHECKING

from .ir import ClassInfo, class_base_name, cpp_template_inner_args, strip_cpp_ref

if TYPE_CHECKING:
  from ..translator import Translator

PROXY_CLASS_NAME = "Proxy"
PROXY_TARGET_FIELD = "_target"
CPP_PROXY_PREFIX = "PyProxy"


def unwrap_super_receiver(node: ast.expr) -> bool:
  """``super`` / 无参 ``super()`` / 无参 ``super.__call__()``（可嵌套 ``__call__``）。"""
  if isinstance(node, ast.Name) and node.id == "super":
    return True
  if not isinstance(node, ast.Call) or node.args or node.keywords:
    return False
  match node.func:
    case ast.Name(id="super"):
      return True
    case ast.Attribute(value=v, attr="__call__"):
      return unwrap_super_receiver(v)
    case _:
      return False


def is_super_call_form(node: ast.expr) -> bool:
  """无参 ``super()`` / ``super.__call__()`` 链（**不含** bare ``super`` Name）。"""
  if isinstance(node, ast.Name):
    return False
  if not isinstance(node, ast.Call) or node.args or node.keywords:
    return False
  match node.func:
    case ast.Name(id="super"):
      return True
    case ast.Attribute(value=v, attr="__call__"):
      if isinstance(v, ast.Name) and v.id == "super":
        return True
      return is_super_call_form(v)
    case _:
      return False


def is_super_method_call(node: ast.Call) -> bool:
  """``super.method(...)`` / ``super().method(...)`` / ``super.__call__().method(...)``。"""
  if not isinstance(node.func, ast.Attribute):
    return False
  if node.func.attr == "__call__":
    return False
  return unwrap_super_receiver(node.func.value)


def is_super_dunder_call(node: ast.Call) -> bool:
  """``super.__call__()`` / ``super().__call__()`` / ``super.__init__(...)``（S01 豁免；不含 ``super().__init__``）。"""
  if not isinstance(node.func, ast.Attribute):
    return False
  if node.func.attr not in ("__call__", "__init__"):
    return False
  if not unwrap_super_receiver(node.func.value):
    return False
  if node.func.attr == "__init__" and is_super_call_form(node.func.value):
    return False
  return True


def is_s01_init_forward_call(node: ast.Call, *, in_class_init: bool) -> bool:
  """``__init__`` 内 ``super.__init__(...)`` / ``self.__init__(...)`` 参数转发（S01 豁免）。"""
  if not in_class_init:
    return False
  if not isinstance(node.func, ast.Attribute) or node.func.attr != "__init__":
    return False
  val = node.func.value
  return isinstance(val, ast.Name) and val.id in ("self", "super")


def reject_super_call_with_args(node: ast.Call) -> None:
  """``super(type, obj)`` / 带参 ``super.__call__(...)`` → ``NotImplementedError``。"""
  match node.func:
    case ast.Name(id="super"):
      if node.args or node.keywords:
        raise NotImplementedError(
          "super(...) 不支持 CPython 两参形式；请写无参 super() 或 super.method(...)"
        )
    case ast.Attribute(value=v, attr="__call__") if unwrap_super_receiver(v):
      if node.args or node.keywords:
        raise NotImplementedError(
          "super.__call__(...) / super().__call__(...) 不支持实参；请写无参 super.__call__()"
        )
    case _:
      return


def super_standalone_call_message() -> str:
  return (
    "super() / super.__call__() 须用于 super().method(...) 或 super.method(...)，"
    "不可单独作表达式"
  )


def super_missing_base_call_message() -> str:
  return (
    "super() / super.__call__() 要求 __base__ 类定义 __call__ 方法；"
    "请改用 super.method(...) 或于基类实现 __call__"
  )


def super_call_form_init_message() -> str:
  return "super().__init__(...) 不允许；``super()`` 在任何上下文中均等价 ``super.__call__()``，请写 super.__init__(...)"


def entity_base_has_call(tr: Translator, host: ClassInfo | None = None) -> bool:
  inner = entity_base_class_info(tr, host if host is not None else tr.class_info)
  if inner is None:
    return False
  return "__call__" in inner.methods or "__call__" in inner.method_overloads


def require_entity_base_call(tr: Translator, host: ClassInfo | None = None) -> None:
  if entity_base_has_call(tr, host):
    return
  raise NotImplementedError(super_missing_base_call_message())


def is_proxy_class_info(info: ClassInfo | None) -> bool:
  if info is None:
    return False
  if getattr(info, "is_proxy", False):
    return True
  return (
    info.name == PROXY_CLASS_NAME
    and info.module_path.replace("\\", "/").endswith("core/proxy")
  )


def is_proxy_derived_class_info(info: ClassInfo | None) -> bool:
  return info is not None and getattr(info, "is_proxy_derived", False)


def uses_proxy_storage(info: ClassInfo | None) -> bool:
  if info is None:
    return False
  if is_proxy_class_info(info) or is_proxy_derived_class_info(info):
    return True
  return inherits_from_proxy_class(info)


def inherits_from_proxy_class(info: ClassInfo) -> bool:
  return PROXY_CLASS_NAME in info.bases


def proxy_inner_from_base_ast(base_ast: ast.expr) -> ast.expr | None:
  if (
    isinstance(base_ast, ast.Subscript)
    and isinstance(base_ast.value, ast.Name)
    and base_ast.value.id == PROXY_CLASS_NAME
  ):
    return copy.deepcopy(base_ast.slice)
  return None


def is_nested_proxy_inner(inner: ast.expr) -> bool:
  if isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name):
    return inner.value.id == PROXY_CLASS_NAME
  return False


def is_cpp_proxy_type(cpp_type: str) -> bool:
  t = strip_cpp_ref(cpp_type.strip())
  return t.startswith(CPP_PROXY_PREFIX) and t.endswith(">")


def cpp_proxy_inner_type(cpp_type: str) -> str | None:
  return cpp_template_inner_args(strip_cpp_ref(cpp_type), f"{CPP_PROXY_PREFIX}<")


def entity_base_type_alias(info: ClassInfo):
  return info.type_aliases.get("__base__")


def entity_base_ast(info: ClassInfo) -> ast.expr | None:
  alias = entity_base_type_alias(info)
  return alias.value if alias is not None else None


def resolve_super_type_name(info: ClassInfo | None) -> str | None:
  """``Super`` → ``__base__`` 根名（``void`` 时 None）。"""
  if info is None:
    return None
  base_ast = entity_base_ast(info)
  if base_ast is None:
    return None
  if isinstance(base_ast, ast.Name):
    if base_ast.id == "void":
      return None
    return base_ast.id
  if isinstance(base_ast, ast.Subscript) and isinstance(base_ast.value, ast.Name):
    return base_ast.value.id
  return None


def class_info_for_type_ast(tr: Translator, ann: ast.expr) -> ClassInfo | None:
  if isinstance(ann, ast.Name):
    return tr.classes.get(ann.id)
  if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
    return tr.classes.get(ann.value.id)
  return None


def entity_base_class_info(tr: Translator, host: ClassInfo | None) -> ClassInfo | None:
  if host is None:
    return None
  base_ast = entity_base_ast(host)
  if base_ast is None:
    return None
  if isinstance(base_ast, ast.Name) and base_ast.id == "void":
    return None
  if isinstance(base_ast, ast.Name):
    if base_ast.id in host.type_params:
      return None
    return tr.classes.get(base_ast.id)
  return class_info_for_type_ast(tr, base_ast)


def host_super_uses_proxy_target(tr: Translator) -> bool:
  host = tr.class_info
  if host is None:
    return False
  if uses_proxy_storage(host):
    return True
  for base_name in host.bases:
    bi = tr.classes.get(base_name)
    if is_proxy_class_info(bi):
      return True
  return False


def proxy_target_member_sep(tr: Translator, inner_storage_cpp: str | None) -> str:
  if inner_storage_cpp and tr._uses_ptr_access(inner_storage_cpp):
    return "->"
  return "."


def proxy_class_info(tr: Translator) -> ClassInfo | None:
  for info in tr.classes.values():
    if is_proxy_class_info(info):
      return info
  return None


def receiver_proxy_peel_enabled(tr: Translator, receiver: ast.expr) -> bool:
  recv_t = strip_cpp_ref(
    tr._infer_expr_cpp_type(receiver) or tr._expr_cpp_type(receiver) or ""
  )
  if is_cpp_proxy_type(recv_t):
    return True
  info = tr._class_info_for_receiver(receiver)
  return info is not None and uses_proxy_storage(info)


def receiver_proxy_host_info(tr: Translator, receiver: ast.expr) -> ClassInfo | None:
  """剥壳时的宿主 ``ClassInfo``（可为 ``None``，``PyProxy<T>`` 仍可通过 C++ 类型剥壳）。"""
  info = tr._class_info_for_receiver(receiver)
  if info is not None and uses_proxy_storage(info):
    return info
  recv_t = strip_cpp_ref(
    tr._infer_expr_cpp_type(receiver) or tr._expr_cpp_type(receiver) or ""
  )
  if is_cpp_proxy_type(recv_t):
    return tr._class_info_for_type(recv_t) or proxy_class_info(tr)
  return None
