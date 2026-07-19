"""``@mixin`` 装饰器参考实现（CPython / IDE）。

包根 ``py2cpp/__init__.py`` 中的 ``mixin`` 仅为翻译标记（``return cls``），**勿** ``from .mixin import mixin``，
以免 ``ast``/``inspect`` 进入翻译闭包。

翻译期辅助（由 ``passes/`` 展开，**非** CPython 运行时语义）：

- ``Self.iter_fields()`` / ``Self.iter_fields[Ann]()`` / ``enum_fields(public_only=…)`` / ``get_annotation(...)`` / ``get_annotations(...)``（``glob=`` 粗筛字段名）
- ``VarStack`` + ``s: VarStack = new()`` + ``s.push(…)`` / ``s.pop()`` / ``s.top()`` + ``new(*s)`` / ``fn(*s)`` / ``(*s,)``（译期展开为 ``__vs_{name}N``；``pop`` 不回收编号，``*s`` 仅含逻辑栈剩余项；``top()`` 可读栈顶且可跨内层作用域；声明与 ``push``/``pop``/``*s`` 须同块作用域，``Self.iter_fields`` / ``enum_fields`` 循环体除外）
- ``Self.iter_methods()`` / ``Self.iter_methods[Ann]()`` / ``get_method_annotation[AnnMeta](method)``（``glob=`` 粗筛方法名）
- ``Self.get_annotation[AnnMeta](field)`` → 字段上该 ``@`` 标记（无则 ``None``）；``.text`` / ``.lo`` 等译期折叠
- ``Mixin.iter_subclasses()`` / ``iter_subclasses(sort_const="_test_tag")`` → 入口 ``main`` 内 ``suite.addTest(Host())``（``expand_test_discovery``）
"""
from __future__ import annotations

from ..builtins import *
import ast
import inspect

from src.constant.mixin import ITER_SUBCLASSES

__all__ = (
  "ITER_SUBCLASSES",
  "MIXIN_METHODS_NOT_INLINED",
  "mixin",
)

from src.constant.mixin import MIXIN_METHODS_NOT_INLINED  # noqa: E402


def _discover_annotated_fields(cls: type, annotation_name: str) -> list[str]:
  try:
    src = inspect.getsource(cls.__init__)
    tree = ast.parse(src)
  except (OSError, TypeError, SyntaxError):
    return []
  fields: list[str] = []
  for node in ast.walk(tree):
    if not isinstance(node, ast.AnnAssign):
      continue
    if not isinstance(node.target, ast.Attribute):
      continue
    if not (isinstance(node.target.value, ast.Name) and node.target.value.id == "self"):
      continue
    ann = node.annotation
    if not isinstance(ann, ast.BinOp) or not isinstance(ann.op, ast.MatMult):
      continue
    right = ann.right
    rname: str | None = None
    if isinstance(right, ast.Name):
      rname = right.id
    elif isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
      rname = right.func.id
    if rname == annotation_name:
      fields.append(node.target.attr)
  return fields


def _discover_module_hosts(
  mixin_cls: type,
  *,
  require_method: str | None = None,
) -> list[type]:
  """CPython 下扫描定义本混入的模块内直接子类（仅供 IDE/调试；译器用 AST）。"""
  mod = inspect.getmodule(mixin_cls)
  if mod is None:
    return []
  out: list[type] = []
  for obj in vars(mod).values():
    if not isinstance(obj, type) or obj is mixin_cls:
      continue
    if not issubclass(obj, mixin_cls):
      continue
    if require_method is not None and require_method not in obj.__dict__:
      continue
    out.append(obj)
  return out


def mixin(cls):
  """类装饰器：混入类不生成 C++；``Self.iter_fields[…]`` 等在翻译期内联。"""

  @classmethod
  def iter_fields(cls, *, public_only: bool = False, mro: bool = False, glob: str | None = None):
    """翻译期：全部字段（声明序）；``Self.iter_fields[Ann]()`` 按 ``@Ann`` 过滤；``glob=`` 粗筛字段名。"""
    try:
      src = inspect.getsource(cls.__init__)
      tree = ast.parse(src)
    except (OSError, TypeError, SyntaxError):
      return
      yield  # pragma: no cover
    for node in ast.walk(tree):
      if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Attribute):
        if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
          name = node.target.attr
          if public_only and name.startswith("_"):
            continue
          yield name

  @classmethod
  def enum_fields(cls, *, public_only: bool = False, mro: bool = False):
    for idx, field in enumerate(cls.iter_fields(public_only=public_only, mro=mro)):
      yield idx, field

  @classmethod
  def get_annotation(cls, field: str):
    try:
      src = inspect.getsource(cls.__init__)
      tree = ast.parse(src)
    except (OSError, TypeError, SyntaxError):
      return None
    for node in ast.walk(tree):
      if not isinstance(node, ast.AnnAssign):
        continue
      if not isinstance(node.target, ast.Attribute) or node.target.attr != field:
        continue
      ann = node.annotation
      if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.MatMult):
        right = ann.right
        if isinstance(right, ast.Call):
          return right
        if isinstance(right, ast.Name):
          return right
    return None

  @classmethod
  def get_annotations(cls, field: str):
    """翻译期：字段 ``T @A @B`` 上各 ``@`` 标记（自外向内）；``for ann in Self.get_annotations(field):`` 由译器展开。"""
    return []

  @classmethod
  def iter_methods(cls, *, public_only: bool = False, mro: bool = False, glob: str | None = None):
    """翻译期：类体内方法名（声明序）；``Self.iter_methods[Ann]()`` 按 ``@Ann`` 过滤；``glob=`` 粗筛方法名。"""
    return []

  @classmethod
  def get_method_annotation(cls, method: str):
    """翻译期：方法 ``@Ann`` 标记（无则 ``None``）。"""
    return None

  @classmethod
  def iter_method_params(cls, method: str):
    """翻译期：方法形参名（跳过 ``self``）；``for p in Self.iter_method_params(m):`` 由译器展开。"""
    return []

  @classmethod
  def get_param_type(cls, method: str, param: str) -> str:
    """翻译期：形参 type_id（``"int"`` / ``"object"`` 等）。"""
    return "object"

  @classmethod
  def get_return_type(cls, method: str) -> str | None:
    """翻译期：返回 type_id；``-> None`` / 无注解 → ``None``。"""
    return None

  @classmethod
  def iter_subclasses(
    cls,
    *,
    sort_const: str | None = None,
    require_method: str = "test",
  ):
    """翻译期展开：入口模块内 ``class Host(cls)`` 子类。

    默认按**声明顺序**；``sort_const`` 非空时按同名 ``static const`` 字段**升序**
    （同键保持声明顺序）。``sort_const`` 须与宿主字段名一致（如 ``"_test_tag"``）。

    典型用法（``unittest``）::

      for Case in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
        suite.addTest(Case())

    译器在 ``main()`` 中展开为 ``suite.addTest(makeRefCount<Host>())``；勿在本混入类上生成 C++ 实现。
    CPython 下返回空列表。
    """
    return []

  cls.iter_fields = iter_fields
  cls.enum_fields = enum_fields
  cls.get_annotation = get_annotation
  cls.get_annotations = get_annotations
  cls.iter_methods = iter_methods
  cls.get_method_annotation = get_method_annotation
  cls.iter_method_params = iter_method_params
  cls.get_param_type = get_param_type
  cls.get_return_type = get_return_type
  cls.iter_subclasses = iter_subclasses
  return cls
