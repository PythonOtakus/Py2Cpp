"""``@lazy`` 形参：call site 包壳、first-touch memo、supplier 透传。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_py_callable_type, is_dict_type, is_frozendict_type
from ..analysis.type_extract import dict_type_args, frozendict_type_args
from ..analysis.ir import cpp_param, strip_cpp_ref
from ..analysis.type_emit import scope_binding_storage_cpp, scope_has_type_binding, scope_storage_cpp
from ..analysis.lazy_param import LazyParamInfo, lazy_supplier_cpp_type, lazy_supplier_invoke_expr, lazy_supplier_is_none_expr
if TYPE_CHECKING:
    from ..translator import Translator

def lazy_param_memo_init_var(param_name: str) -> str:
    return f'__py2cpp_lazy_{param_name}_init'

def lazy_param_memo_var(param_name: str) -> str:
    return f'__py2cpp_lazy_{param_name}_val'

def emit_lazy_param_prologue(tr: 'Translator', lazy_params: dict[str, LazyParamInfo]) -> None:
    """函数体入口：默认 supplier 填充 + memo 变量声明。"""
    if not lazy_params:
        return
    for name, info in lazy_params.items():
        sup = cpp_param(name)
        if info.default_expr is not None:
            wrapped = emit_lazy_supplier_from_expr(tr, info.default_expr, info.value_cpp_type)
            tr.write_line(f'if ({lazy_supplier_is_none_expr(sup)}) {{')
            tr.write_line(f'  {sup} = {wrapped};')
            tr.write_line('}')
        init_v = lazy_param_memo_init_var(name)
        val_v = lazy_param_memo_var(name)
        tr.write_line(f'bool {init_v} = false;')
        stored = info.value_cpp_type.rstrip('&').strip()
        tr.write_line(f'{stored} {val_v};')

def resolve_lazy_value_cpp_type_at_call(tr: 'Translator', func: ast.expr | None, lazy_info: LazyParamInfo) -> str:
    """泛型方法 ``V @lazy`` 在实例化接收者上替换为具体 ``V``（如 ``PyInt``）。"""
    base = lazy_info.value_cpp_type
    if func is None or not base or base.startswith('Py') or ('<' in base):
        return base
    from ..analysis.ir import cpp_template_base_and_args
    from ..emit.call_emit import class_info_from_receiver
    match func:
        case ast.Attribute(value=recv):
            info = class_info_from_receiver(tr, recv)
            if info is None or not info.type_params or base not in info.type_params:
                return base
            recv_t = tr._infer_expr_cpp_type(recv) or ''
            if not recv_t and isinstance(recv, ast.Name) and tr.scope:
                recv_t = scope_storage_cpp(tr, recv.id)
            recv_t = recv_t.strip()
            if not recv_t:
                return base
            if is_dict_type(recv_t):
                inner = dict_type_args(recv_t) or ''
            elif is_frozendict_type(recv_t):
                inner = frozendict_type_args(recv_t) or ''
            else:
                parsed = cpp_template_base_and_args(recv_t)
                inner = parsed[1] if parsed else recv_t[recv_t.find('<') + 1:recv_t.rfind('>')]
            parts = [p.strip() for p in inner.split(',')]
            idx = info.type_params.index(base)
            if idx < len(parts):
                return parts[idx]
        case _:
            pass
    return base

def emit_lazy_supplier_from_expr(tr: 'Translator', expr: ast.expr, value_cpp_type: str) -> str:
    """实参表达式 → ``PyCallable<V>``（IIFE 内嵌零参 lambda）。"""
    from ..emit.delegate_emit import py_callable_owned_lambda_expr
    base = value_cpp_type.rstrip('&').strip()
    idx = tr._lazy_lambda_counter
    tr._lazy_lambda_counter += 1
    lam = f'_lazy_lam_{idx}'
    body = tr._visit_value_expr(expr)
    sup_t = lazy_supplier_cpp_type(base)
    slot = py_callable_owned_lambda_expr(lam, base, ())
    return f'([&]() {{ auto {lam} = [&]() {{ return {body}; }}; return {slot}; }})()'

def emit_lazy_param_materialize(tr: 'Translator', param_name: str, info: LazyParamInfo) -> str:
    """first-touch memo：读取惰性形参 materialized 值。"""
    sup = cpp_param(param_name)
    init_v = lazy_param_memo_init_var(param_name)
    val_v = lazy_param_memo_var(param_name)
    stored = info.value_cpp_type.rstrip('&').strip()
    invoke = lazy_supplier_invoke_expr(sup, stored)
    if info.materialized_ref:
        return f'([&]() -> {stored}& {{ if (!{init_v}) {{ {val_v} = {invoke}; {init_v} = true; }} return {val_v}; }})()'
    return f'([&]() -> {stored} {{ if (!{init_v}) {{ {val_v} = {invoke}; {init_v} = true; }} return {val_v}; }})()'

def try_emit_lazy_param_is_none(tr: 'Translator', name_node: ast.Name, *, is_not: bool) -> str | None:
    if tr.scope is None or name_node.id not in tr.scope.lazy_params:
        return None
    sup = cpp_param(name_node.id)
    cond = lazy_supplier_is_none_expr(sup)
    return f'(!({cond}))' if is_not else cond

def try_emit_lazy_call_arg(tr: 'Translator', arg_expr: ast.expr, lazy_info: LazyParamInfo, *, param_name: str, func: ast.expr | None=None) -> str | None:
    """call site：惰性实参包壳或透传。"""
    if isinstance(arg_expr, ast.Name) and tr.scope is not None:
        py = arg_expr.id
        cpp = cpp_param(py)
        pt = (
            scope_binding_storage_cpp(tr.scope, py)
            or scope_binding_storage_cpp(tr.scope, cpp)
        )
        if py in tr.scope.lazy_params or is_py_callable_type(strip_cpp_ref(pt)):
            if py == param_name or py in tr.scope.lazy_params:
                return cpp
    value_cpp = resolve_lazy_value_cpp_type_at_call(tr, func, lazy_info)
    return emit_lazy_supplier_from_expr(tr, arg_expr, value_cpp)

def callee_lazy_params_for_call(tr: 'Translator', func: ast.expr, *, call: ast.Call | None=None) -> dict[str, LazyParamInfo]:
    from ..emit.call_emit import call_param_names, class_info_from_receiver
    names = call_param_names(tr, func, call=call)
    if not names:
        return {}
    lazy: dict[str, LazyParamInfo] = {}
    match func:
        case ast.Attribute(value=val, attr=method):
            info = class_info_from_receiver(tr, val)
            if info is None:
                return {}
            method_def = tr._method_def_for_call(info, method, call)
            if method_def is None:
                return {}
            sig = info.method_sig_for(method_def)
            if sig is None:
                return {}
            for n in names:
                if n in sig.lazy_params:
                    lazy[n] = sig.lazy_params[n]
            return lazy
        case ast.Name(id=name):
            if tr.class_info and (name in tr.class_info.methods or name in tr.class_info.method_overloads):
                method_def = tr._method_def_for_call(tr.class_info, name, call)
                if method_def is not None:
                    sig = tr.class_info.method_sig_for(method_def)
                    if sig is not None:
                        for n in names:
                            if n in sig.lazy_params:
                                lazy[n] = sig.lazy_params[n]
                return lazy
            mp = tr._active_module_path()
            if mp:
                func_def = tr._module_function_def_for_call(mp, name, call=call)
                if func_def is not None:
                    fsig = tr.function_sigs.get((mp, func_def.name))
                    if fsig is not None:
                        for n in names:
                            if n in fsig.lazy_params:
                                lazy[n] = fsig.lazy_params[n]
            return lazy
        case _:
            return {}

def lazy_param_at_index(lazy: dict[str, LazyParamInfo], param_names: list[str], index: int) -> LazyParamInfo | None:
    if index >= len(param_names):
        return None
    return lazy.get(param_names[index])
