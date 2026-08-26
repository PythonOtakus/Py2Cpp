"""``d += handler`` / ``d -= handler`` 的 ``PyCallable`` 字面量与成员 thunk 生成。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.delegates import DelegateInfo, DelegateParam
from ..analysis.imports import binding_cpp_name
from ..analysis.type_pred import is_py_callable_type
from ..analysis.ir import cpp_param, cpp_template_base_and_args, split_cpp_template_args, strip_cpp_type_qualifiers
from ..analysis.type_emit import scope_has_type_binding, scope_storage_cpp, bind_scope_var
from ..analysis.module_namespace import qualify_symbol_in_module
if TYPE_CHECKING:
    from ..analysis.ir import ClassInfo
    from ..translator import Translator

def py_callable_type_parts(cpp_type: str) -> tuple[str, tuple[str, ...]] | None:
    """``PyCallable<Ret, Args...>`` → ``(Ret, (Args...))``。"""
    t = strip_cpp_type_qualifiers(cpp_type)
    if not is_py_callable_type(t):
        return None
    inner = t[len('PyCallable<'):-1].strip()
    if not inner:
        return None
    parts = split_cpp_template_args(inner)
    if not parts:
        return None
    return (parts[0], tuple(parts[1:]))

def infer_py_callable_type_from_lambda(tr: 'Translator', lam: ast.Lambda) -> str:
    from ..analysis.ir import cpp_ident
    param_pairs = tr._delegate_lambda_param_types(lam)
    ret = cpp_ident('int')
    args = ', '.join((cpp_t for _, cpp_t in param_pairs))
    if args:
        return f'PyCallable<{ret}, {args}>'
    return f'PyCallable<{ret}>'

def py_callable_type_to_delegate_params(cpp_type: str) -> tuple[str, tuple[DelegateParam, ...]] | None:
    parts = py_callable_type_parts(cpp_type)
    if parts is None:
        return None
    ret, arg_types = parts
    params = tuple((DelegateParam(f'__arg{i}', arg_t) for i, arg_t in enumerate(arg_types)))
    return (ret, params)

def delegate_py_callable_type(info: DelegateInfo) -> str:
    base_args = ', '.join((p.cpp_type for p in info.params))
    ret = info.ret_cpp
    if base_args:
        return f'PyCallable<{ret}, {base_args}>'
    return f'PyCallable<{ret}>'

def py_callable_free_invoke_ref(ret: str, params: tuple[DelegateParam, ...]) -> str:
    if params:
        types = ', '.join([ret, *(p.cpp_type for p in params)])
        return f'py_callable_free_invoke<{types}>::call'
    return f'py_callable_free_invoke<{ret}>::call'

def resolve_delegate_for_type(vtype: str, delegates: dict[str, DelegateInfo]) -> DelegateInfo | None:
    """``vtype`` 可能是 ``PyFuncDelegate<PyInt>`` / ``FuncDelegate<…>`` / 带 ``::`` 限定名。

    ``delegates`` 以 Python 名（``FuncDelegate``）为键，须同时匹配 ``info.cpp_name()``。
    """
    base = strip_cpp_type_qualifiers(vtype).split('<', 1)[0].strip()
    if '::' in base:
        base = base.rsplit('::', 1)[-1]
    info = delegates.get(base)
    if info is None:
        for cand in delegates.values():
            if cand.cpp_name() == base or cand.name == base:
                info = cand
                break
    if info is None:
        return None
    return specialize_delegate_info(vtype, info)

def specialize_delegate_info(vtype: str, info: DelegateInfo) -> DelegateInfo:
    """``Func<PyInt>`` 等把委托形参/返回中的 ``T`` 换为具体 C++ 类型。"""
    parsed = cpp_template_base_and_args(vtype)
    if parsed is None:
        return info
    base, args = parsed
    if base != info.cpp_name():
        return info
    tnames = list(info.all_template_names)
    if not tnames or len(args) != len(tnames):
        return info
    subs = {name: arg for name, arg in zip(tnames, args)}

    def sub_type(cpp_type: str) -> str:
        key = cpp_type.strip()
        return subs.get(key, cpp_type)
    return DelegateInfo(name=info.name, module_path=info.module_path, type_params=info.type_params, func_template_names=info.func_template_names, params=tuple((DelegateParam(p.name, sub_type(p.cpp_type)) for p in info.params)), ret_cpp=sub_type(info.ret_cpp), node=info.node)

def _emit_callable_slot(info: DelegateInfo, ctx_expr: str, invoke_ref: str) -> str:
    slot_type = delegate_py_callable_type(info)
    return _emit_callable_slot_type(slot_type, ctx_expr, invoke_ref)

def _emit_callable_slot_type(slot_type: str, ctx_expr: str, invoke_ref: str) -> str:
    return f'{slot_type}{{ {ctx_expr}, {invoke_ref} }}'

def _module_function_cpp_name(tr: 'Translator', name: str) -> str:
    bound = binding_cpp_name(tr._effective_import_bindings(), name)
    if bound is not None:
        return bound
    return qualify_symbol_in_module(tr._active_module_path(), cpp_param(name))

def _emit_free_function_callable(tr: 'Translator', info: DelegateInfo, fn_cpp: str) -> str:
    slot_type = delegate_py_callable_type(info)
    return f'{slot_type}({fn_cpp})'

def _class_info_for_type_receiver(tr: 'Translator', node: ast.expr) -> 'ClassInfo | None':
    match node:
        case ast.Name(id=name):
            return tr._class_info_for_ref(name)
        case _:
            return tr._class_info_for_receiver(node)

def _is_static_method(class_info: 'ClassInfo', method: str, tr: 'Translator') -> bool:
    return tr._class_static_member_ref(class_info, method) is not None

def _emit_static_method_callable(tr: 'Translator', info: DelegateInfo, class_info: 'ClassInfo', method: str) -> str | None:
    static_ref = tr._class_static_member_ref(class_info, method)
    if static_ref is None:
        return None
    qual = qualify_symbol_in_module(class_info.module_path, class_info.cpp_name())
    method_cpp = tr._member_cpp_name(class_info, method)
    invoke = tr._ensure_py_callable_free_function_thunk(f'&{qual}::{method_cpp}', info)
    return _emit_callable_slot(info, 'nullptr', f'&{invoke}')

def _emit_self_method_callable(tr: 'Translator', info: DelegateInfo, method: str) -> str | None:
    if tr.class_info is None or method not in tr.class_info.methods:
        return None
    sig = tr.class_info.method_sigs.get(method)
    if sig is not None and sig.is_static:
        return _emit_static_method_callable(tr, info, tr.class_info, method)
    thunk = tr._ensure_py_callable_method_thunk(tr.class_info, method, info)
    slot_type = delegate_py_callable_type(info)
    return f'{slot_type}{{ (void*)this, &{thunk} }}'

def validate_delegate_lambda_shape(lam: ast.Lambda) -> None:
    if lam.args.defaults or lam.args.kwonlyargs or lam.args.kwarg or lam.args.vararg or lam.args.kw_defaults:
        raise NotImplementedError('委托 lambda 仅支持位置形参、无默认值')

def validate_delegate_lambda(lam: ast.Lambda, info: DelegateInfo) -> None:
    validate_delegate_lambda_shape(lam)
    if len(lam.args.args) != len(info.params):
        raise NotImplementedError(f'委托 lambda 形参个数须与委托一致（期望 {len(info.params)}，实际 {len(lam.args.args)}）')

def lambda_ast_uses_name(lam: ast.Lambda, name: str) -> bool:
    for node in ast.walk(lam):
        if isinstance(node, ast.Name) and node.id == name:
            return True
    return False

def py_callable_lambda_invoke_ref(lam_var: str, ret: str, params: tuple[DelegateParam, ...]) -> str:
    if params:
        types = ', '.join([f'decltype({lam_var})', ret, *(p.cpp_type for p in params)])
    else:
        types = f'decltype({lam_var}), {ret}'
    return f'py_callable_lambda_invoke<{types}>::call'

def py_callable_owned_lambda_expr(lam_var: str, ret: str, params: tuple[DelegateParam, ...]) -> str:
    if params:
        types = ', '.join([ret, f'decltype({lam_var})', *(p.cpp_type for p in params)])
    else:
        types = f'{ret}, decltype({lam_var})'
    return f'py_callable_make_owned_lambda<{types}>({lam_var})'

def _emit_lambda_callable(tr: 'Translator', info: DelegateInfo, lam: ast.Lambda) -> str:
    lam_var = tr._emit_delegate_cpp_lambda(lam, info)
    return py_callable_owned_lambda_expr(lam_var, info.ret_cpp, info.params)

def _scope_py_callable_var(tr: 'Translator', name: str) -> str | None:
    if tr.scope is None or not scope_has_type_binding(tr.scope, name):
        return None
    vtype = scope_storage_cpp(tr, name)
    if not is_py_callable_type(vtype):
        return None
    return cpp_param(name)

def _emit_py_callable_attribute(tr: 'Translator', node: ast.Attribute) -> str | None:
    ft = tr._field_cpp_type_for_attribute(node.value, node.attr)
    if ft is None or not is_py_callable_type(ft):
        return None
    return tr.visit(node)

def try_emit_delegate_lambda_assign(tr: 'Translator', target: ast.expr, lam: ast.Lambda, *, callable_type: str | None=None) -> bool:
    if not isinstance(target, ast.Name):
        return False
    name = target.id
    if not tr._try_declare(name):
        return False
    validate_delegate_lambda_shape(lam)
    cpp_var = cpp_param(name)
    slot_type = callable_type or infer_py_callable_type_from_lambda(tr, lam)
    parsed = py_callable_type_to_delegate_params(slot_type)
    if parsed is None:
        return False
    ret_cpp, params = parsed
    lam_var = tr._emit_delegate_cpp_lambda(lam, None, var_name=f'_{cpp_var}_lam')
    slot = py_callable_owned_lambda_expr(lam_var, ret_cpp, params)
    tr.write_line(f'{slot_type} {cpp_var} = {slot};')
    if tr.scope is not None:
        bind_scope_var(tr.scope, name, slot_type, classes=tr.classes)
    return True

def try_emit_delegate_handler(tr: 'Translator', info: DelegateInfo, node: ast.expr) -> str | None:
    """将 ``+=`` / ``-=`` 右侧译为 ``PyCallable{_closure, _func}`` 槽位。"""
    match node:
        case ast.Name(id=name):
            callable_var = _scope_py_callable_var(tr, name)
            if callable_var is not None:
                return callable_var
            fn_cpp = _module_function_cpp_name(tr, name)
            return _emit_free_function_callable(tr, info, fn_cpp)
        case ast.Lambda():
            return _emit_lambda_callable(tr, info, node)
        case ast.Attribute(value=val, attr=method):
            if isinstance(val, ast.Name) and val.id == 'self':
                return _emit_self_method_callable(tr, info, method)
            class_info = _class_info_for_type_receiver(tr, val)
            if class_info is not None and _is_static_method(class_info, method, tr):
                return _emit_static_method_callable(tr, info, class_info, method)
            callable_field = _emit_py_callable_attribute(tr, node)
            if callable_field is not None:
                return callable_field
            return None
        case _:
            return None
