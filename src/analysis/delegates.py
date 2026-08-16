"""``@delegate`` 函数定义解析（C# 风格多播委托）。"""
from __future__ import annotations

import ast
from dataclasses import dataclass

from .ir import FuncTypeParams, has_named_decorator


@dataclass(frozen=True)
class DelegateParam:
  name: str
  cpp_type: str


@dataclass(frozen=True)
class DelegateInfo:
  """``@delegate def Func[T](x: T) -> T: ...`` 的编译期描述。"""

  name: str
  module_path: str
  type_params: tuple[str, ...]
  func_template_names: tuple[str, ...]
  params: tuple[DelegateParam, ...]
  ret_cpp: str
  node: ast.FunctionDef

  @property
  def all_template_names(self) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for n in self.type_params + self.func_template_names:
      if n not in seen:
        seen.add(n)
        out.append(n)
    return tuple(out)

  def cpp_name(self) -> str:
    from ..constant.language import default_py_class_cpp_name

    return default_py_class_cpp_name(self.name)

  def is_template(self) -> bool:
    return bool(self.all_template_names)

  def cpp_specialization(self, arg_types: str) -> str:
    if not arg_types:
      return self.cpp_name()
    return f"{self.cpp_name()}<{arg_types}>"

  def call_param_decls(self) -> str:
    return ", ".join(f"{p.cpp_type} {p.name}" for p in self.params)

  def call_args(self) -> str:
    return ", ".join(p.name for p in self.params)


def is_delegate_definition(func: ast.FunctionDef) -> bool:
  return has_named_decorator(func, "delegate")


def parse_function_type_params(func: ast.FunctionDef) -> list[str]:
  names: list[str] = []
  for tp in getattr(func, "type_params", None) or ():
    if isinstance(tp, ast.TypeVar):
      names.append(tp.name)
  return names


def _is_delegate_stub_body(func: ast.FunctionDef) -> bool:
  if len(func.body) != 1:
    return False
  stmt = func.body[0]
  if isinstance(stmt, ast.Pass):
    return True
  return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and (
    stmt.value.value is ...
  )


def _parse_return_type(node: ast.FunctionDef, *, parse_type) -> str:
  if node.returns is None:
    return "void"
  match node.returns:
    case ast.Constant(value=None):
      return "void"
    case ast.Name(id="None"):
      return "void"
    case _:
      return parse_type(node.returns, set(parse_function_type_params(node)))


def collect_delegates(
  module_path: str,
  tree: ast.Module,
  *,
  parse_type,
) -> dict[str, DelegateInfo]:
  """从模块 AST 收集 ``@delegate`` 定义。"""
  out: dict[str, DelegateInfo] = {}
  for node in tree.body:
    if not isinstance(node, ast.FunctionDef):
      continue
    if not is_delegate_definition(node):
      continue
    if not _is_delegate_stub_body(node):
      raise NotImplementedError(
        f"@delegate {node.name} 仅支持 ``...`` / ``pass`` 存根体"
      )
    tparams = parse_function_type_params(node)
    func_ft = FuncTypeParams.collect(node, frozenset(tparams))
    all_tp = set(tparams) | set(func_ft.template_names)
    params: list[DelegateParam] = []
    for arg in node.args.args:
      if arg.annotation:
        pt = parse_type(arg.annotation, all_tp)
      elif arg.arg in func_ft.arg_types:
        pt = func_ft.arg_types[arg.arg]
      else:
        pt = "void*"
      params.append(DelegateParam(arg.arg, pt))
    ret_cpp = _parse_return_type(node, parse_type=parse_type)
    info = DelegateInfo(
      name=node.name,
      module_path=module_path,
      type_params=tuple(tparams),
      func_template_names=tuple(func_ft.template_names),
      params=tuple(params),
      ret_cpp=ret_cpp,
      node=node,
    )
    out[node.name] = info
  return out
