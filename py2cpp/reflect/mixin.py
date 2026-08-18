"""``@mixin`` 装饰器参考实现（CPython / IDE）。

包根 ``py2cpp/__init__.py`` 中的 ``mixin`` 仅为翻译标记（``return cls``），**勿** ``from .mixin import mixin``，
以免 ``ast``/``inspect`` 进入翻译闭包。

翻译期辅助（由 ``passes/`` 展开，**非** CPython 运行时语义）：

- ``Self.iterFields()`` / ``Self.iterFields[Ann]()`` / ``enumFields(publicOnly=…)`` / ``getFieldAnnotation(...)`` / ``getFieldAnnotations(...)`` / ``getFieldType(...)`` / ``getFieldDefault(...)``（``glob=`` 粗筛字段名）
- ``VarStack`` + ``s: VarStack = new()`` + ``s.push(…)`` / ``s.pop()`` / ``s.top()`` + ``new(*s)`` / ``fn(*s)`` / ``(*s,)``（译期展开为 ``__vs_{name}N``；``pop`` 不回收编号，``*s`` 仅含逻辑栈剩余项；``top()`` 可读栈顶且可跨内层作用域；声明与 ``push``/``pop``/``*s`` 须同块作用域，``Self.iterFields`` / ``enumFields`` 循环体除外）
- ``Self.iterMethods()`` / ``Self.iterMethods[Ann]()`` / ``getMethodAnnotation[AnnMeta](method)``（``glob=`` 粗筛方法名）
- ``Self.getFieldAnnotation[AnnMeta](field)`` → 字段上该 ``@`` 标记（无则 ``None``）；``.text`` / ``.lo`` 等译期折叠
- ``Mixin.iterSubclasses()`` / ``iterSubclasses(sortConst="_testTag")`` → 入口 ``main`` 内 ``suite.addTest(Host())``（``expand_test_discovery``）
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


def _discoverAnnotatedFields(cls: type, annotationName: str) -> list[str]:
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
    if rname == annotationName:
      fields.append(node.target.attr)
  return fields


def _discoverModuleHosts(
  mixinCls: type,
  *,
  requireMethod: str | None = None,
) -> list[type]:
  """CPython 下扫描定义本混入的模块内直接子类（仅供 IDE/调试；译器用 AST）。"""
  mod = inspect.getmodule(mixinCls)
  if mod is None:
    return []
  out: list[type] = []
  for obj in vars(mod).values():
    if not isinstance(obj, type) or obj is mixinCls:
      continue
    if not issubclass(obj, mixinCls):
      continue
    if requireMethod is not None and requireMethod not in obj.__dict__:
      continue
    out.append(obj)
  return out


def mixin(cls):
  """类装饰器：混入类不生成 C++；``Self.iterFields[…]`` 等在翻译期内联。"""

  @classmethod
  def iterFields(cls, *, publicOnly: bool = False, mro: bool = False, glob: str | None = None):
    """翻译期：全部字段（声明序）；``Self.iterFields[Ann]()`` 按 ``@Ann`` 过滤；``glob=`` 粗筛字段名。"""
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
          if publicOnly and name.startsWith("_"):
            continue
          yield name

  @classmethod
  def enumFields(cls, *, publicOnly: bool = False, mro: bool = False):
    for idx, field in enumerate(cls.iterFields(publicOnly=publicOnly, mro=mro)):
      yield idx, field

  @classmethod
  def getFieldDefault(cls, field: str):
    """翻译期：字段默认值（无则 ``None``）；``Self.getFieldDefault(field)`` 由译器折叠。"""
    return None

  @classmethod
  def getFieldAnnotation(cls, field: str):
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
  def getFieldAnnotations(cls, field: str):
    """翻译期：字段 ``T @A @B`` 上各 ``@`` 标记（自外向内）；``for ann in Self.getFieldAnnotations(field):`` 由译器展开。"""
    return []

  @classmethod
  def iterMethods(cls, *, publicOnly: bool = False, mro: bool = False, glob: str | None = None):
    """翻译期：类体内方法名（声明序）；``Self.iterMethods[Ann]()`` 按 ``@Ann`` 过滤；``glob=`` 粗筛方法名。"""
    return []

  @classmethod
  def getMethodAnnotation(cls, method: str):
    """翻译期：方法 ``@Ann`` 标记（无则 ``None``）。"""
    return None

  @classmethod
  def iterMethodParams(cls, method: str):
    """翻译期：方法形参名（跳过 ``self``）；``for p in Self.iterMethodParams(m):`` 由译器展开。"""
    return []

  @classmethod
  def getMethodParamType(cls, method: str, param: str):
    """翻译期：形参基础类型；可写 ``Self.getMethodParamType(m, p) is int``。"""
    pass

  @classmethod
  def getMethodReturnType(cls, method: str):
    """翻译期：返回基础类型；无返回注解或 ``-> None`` 时为 ``None``。"""
    return None

  @classmethod
  def iterSubclasses(
    cls,
    *,
    sortConst: str | None = None,
    requireMethod: str = "test",
  ):
    """翻译期展开：入口模块内 ``class Host(cls)`` 子类。

    默认按**声明顺序**；``sortConst`` 非空时按同名 ``static const`` 字段**升序**
    （同键保持声明顺序）。``sortConst`` 须与宿主字段名一致（如 ``"_testTag"``）。

    典型用法（``unittest``）::

      for Case in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
        suite.addTest(Case())

    译器在 ``main()`` 中展开为 ``suite.addTest(makeRefCount<Host>())``；勿在本混入类上生成 C++ 实现。
    CPython 下返回空列表。
    """
    return []

  cls.iterFields = iterFields
  cls.enumFields = enumFields
  cls.getFieldAnnotation = getFieldAnnotation
  cls.getFieldAnnotations = getFieldAnnotations
  cls.getFieldDefault = getFieldDefault
  cls.iterMethods = iterMethods
  cls.getMethodAnnotation = getMethodAnnotation
  cls.iterMethodParams = iterMethodParams
  cls.getMethodParamType = getMethodParamType
  cls.getMethodReturnType = getMethodReturnType
  cls.iterSubclasses = iterSubclasses
  return cls
