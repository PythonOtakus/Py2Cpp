"""函数调用表达式 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
import copy
from typing import TYPE_CHECKING
from ..analysis.imports import binding_cpp_name, resolve_class_ref_cpp, resolve_ctor_cpp_type, resolve_import_attribute_chain
from ..analysis.type_pred import is_array_type, is_concrete_coroutine_type, is_invokable_type, is_iter_result_type, is_py_coroutine_type, is_py_generator_type, is_refcount_type, is_stack_array_type, is_bytes_type, is_char_type, is_delegate_type, is_str_type
from ..analysis.type_extract import list_elem_type
from ..analysis.ir import ClassInfo, bytes_cpp_from_literal, cpp_ident, cpp_iter_result_return_expr, cpp_param, cpp_result_type, cpp_stack_array_size, cpp_array_ndim, cpp_stack_array_ndim, cpp_template_type, iter_result_value_cpp, strip_cpp_ref, str_cpp_from_literal
from ..analysis.module_namespace import namespace_qualifier_for_module, qualify_symbol_in_module
from ..analysis.type_emit import field_storage_cpp, scope_storage_cpp, sig_return_full_cpp, sig_return_storage_cpp
from ..constant.primitive_headers import PRIMITIVE_HEADER_MAP
from .fstring_emit import emit_format_expr, plan_format_literal
from .binop_emit import _identity_addr_expr
from .literal_map_lookup_emit import try_emit_dict_literal_get
from .numeric_cast_emit import try_emit_float_ctor, try_emit_int_ctor, try_emit_numeric_ctor, try_emit_primitive_ctor
from .literal_sequence_lookup_emit import try_emit_str_literal_find_call, try_emit_str_literal_stripLines_call
from ..passes.static_reflect import static_field_name
from ..passes.union_expand import union_variant_names, union_variant_param_cpp_types
from ..emit.layout_config_emit import _JSON_API_METHODS_NEED_TYPE_ARG
from ..analysis.stubs.builtin_stubs import DEDUCED_TEMPLATE_MEMORY_FUNCS as _DEDUCED_TEMPLATE_FUNCS, builtin_dunder_forward
from ..analysis.stubs.class_stubs import load_host_bound_iterator_view_cpp_bases
from ..constant.stdlib_layout import RUNTIME_PKG
from ..analysis.runtime_symbols import BUILTIN_EMIT_SPECIAL, runtime_make_range_expr
if TYPE_CHECKING:
    from ..translator import Translator

def _emit_id_call(tr: Translator, node: ast.Call) -> str:
    if len(node.args) != 1:
        raise NotImplementedError('id(x) 需要一个实参')
    arg = node.args[0]
    if isinstance(arg, ast.Constant):
        raise NotImplementedError('id(x) 的 x 须为变量/字段/下标等可寻址左值，不可为字面量')
    arg_t = tr._infer_expr_cpp_type(arg)
    return _identity_addr_expr(tr, arg, arg_t)

def _emit_cast_call(tr: Translator, target_cpp: str, node: ast.Call) -> str:
    if len(node.args) != 1:
        raise NotImplementedError('cast[T](obj) 仅一参')
    arg = node.args[0]
    inner = tr._visit_value_expr(arg)
    raw_t = tr._infer_expr_cpp_type(arg) or ''
    bare_target = target_cpp.strip()
    raw_stripped = raw_t.rstrip()
    if bare_target.endswith('*') and bare_target != raw_stripped:
        if raw_stripped in ('PyInt', 'PyInt16', 'PyInt64', 'PyUInt16', 'PyUInt', 'PyUInt64', 'PyUIntPtr', 'uintptr', 'utf8ptr', 'utf16ptr') or raw_stripped.endswith('*') or (
          isinstance(arg, ast.Call)
          and isinstance(arg.func, ast.Name)
          and arg.func.id == 'id'
        ):
            return f'reinterpret_cast<{target_cpp}>({inner})'
    if bare_target == 'utf16ptr' and (raw_stripped == 'PyUInt16*' or raw_stripped.endswith('*')):
        return f'reinterpret_cast<utf16ptr>({inner})'
    if bare_target in ('PyUIntPtr', 'uintptr'):
        if raw_stripped in ('utf8ptr', 'utf16ptr') or raw_stripped.endswith('*') or (
          isinstance(arg, ast.Call)
          and isinstance(arg.func, ast.Name)
          and arg.func.id == 'id'
        ):
            return f'reinterpret_cast<{bare_target}>({inner})'
    cast_t = target_cpp.rstrip()
    if not cast_t.endswith('&'):
        cast_t = f'{cast_t}&'
    if raw_t.rstrip().endswith('&'):
        return f'static_cast<{cast_t}>({inner})'
    if is_refcount_type(raw_t.strip()):
        return f'static_cast<{cast_t}>(*{inner})'
    return f'static_cast<{target_cpp}>({inner})'

def _emit_deduced_template_call(tr: Translator, name: str, node: ast.Call) -> str:
    if name == 'id':
        return _emit_id_call(tr, node)
    if name == 'init':
        if not node.args:
            raise NotImplementedError('init(ptr) 至少需要一个实参')
        ptr = tr.visit(node.args[0])
        if len(node.args) == 1:
            return f'init({ptr})'
        rest = ', '.join((tr.visit(a) for a in node.args[1:]))
        return f'init({ptr}, {rest})'
    if name == 'destroy':
        ptr = tr.visit(node.args[0])
        return f'destroy({ptr})'
    if name == 'free':
        buf = tr.visit(node.args[0])
        return f'free({buf})'
    if name == 'freeArray':
        buf = tr.visit(node.args[0])
        return f'freeArray({buf})'
    raise ValueError(name)


def _emit_input_typed_call(tr: Translator, elem_t: str, node: ast.Call) -> str:
    if node.keywords:
        raise NotImplementedError('input[T](...) 暂不支持关键字参数')
    if len(node.args) > 1:
        raise NotImplementedError('input[T](prompt) 至多一个位置参数')
    if not node.args:
        return f'::py_input_typed<{elem_t}>()'
    prompt = tr._visit_value_expr(node.args[0])
    return f'::py_input_typed<{elem_t}>({prompt})'

def receiver_cpp_type_for_call(tr: Translator, receiver: ast.expr) -> str:
    """方法调用接收者的 C++ 类型（``self._coro`` 等字段优先于 ``@refcount`` ``self`` 句柄）。"""
    if isinstance(receiver, ast.Attribute):
        ft = tr._field_cpp_type_for_attribute(receiver.value, receiver.attr)
        if ft:
            return strip_cpp_ref(ft)
    return strip_cpp_ref(tr._infer_expr_cpp_type(receiver) or '')

def class_info_from_receiver(tr: Translator, receiver: ast.expr) -> ClassInfo | None:
    if isinstance(receiver, ast.Name) and receiver.id == 'self' and tr.class_info:
        return tr.class_info
    if isinstance(receiver, ast.Name) and receiver.id == 'Self':
        return tr._active_class_info()
    from ..analysis.proxy import entity_base_class_info, unwrap_super_receiver
    if unwrap_super_receiver(receiver):
        return entity_base_class_info(tr, tr.class_info)
    if isinstance(receiver, ast.Name) and tr._name_refers_to_class(receiver.id):
        return tr._class_info_for_ref(receiver.id)
    if isinstance(receiver, ast.Subscript) and isinstance(receiver.value, ast.Name) and tr._name_refers_to_class(receiver.value.id):
        return tr._class_info_for_ref(receiver.value.id)
    t = receiver_cpp_type_for_call(tr, receiver)
    if is_str_type(t):
        return tr.classes.get('str')
    if is_bytes_type(t):
        return tr.classes.get('bytes')
    if t and is_py_coroutine_type(t):
        proto = tr.classes.get('CoroutineType')
        if proto is not None:
            return proto
    if t and is_py_generator_type(t):
        proto = tr.classes.get('GeneratorType')
        if proto is not None:
            return proto
    info = tr._class_info_for_type(t)
    if info is not None:
        return info
    if isinstance(receiver, ast.Constant) and isinstance(receiver.value, bytes):
        return tr.classes.get('bytes')
    if isinstance(receiver, ast.Call):
        recv_cpp = tr.visit(receiver)
        if 'bytes_from_literal' in recv_cpp:
            return tr.classes.get('bytes')
    if t:
        return tr._lookup_class_by_cpp_or_py_name(t)
    return None

def specialize_param_cpp_types_from_context(info: ClassInfo, param_cpp_types: list[str], context_cpp: str) -> list[str]:
    """用 ``PyIterResult<Y,R>`` / ``PyCoroutine<Y,S,R>`` 等实例化形参占位符。"""
    from ..analysis.ir import ClassInfo as _CI, cpp_template_base_and_args, specialize_cpp_template_placeholders
    if not context_cpp or not info.type_params:
        return param_cpp_types
    # ``@refcount`` 接收者是 ``PyRefCount<ThreadPool<PyInt>>``：须先 unwrap，否则会把 ``R`` 误替成 ``ThreadPool<PyInt>``。
    recv = _CI.unwrap_refcount_type(context_cpp.strip())
    parsed = cpp_template_base_and_args(recv)
    class_cpp = info.cpp_name()
    if parsed is not None:
        base = parsed[0]
        if base == class_cpp or base.endswith(f'::{class_cpp}'):
            class_cpp = base
    return [specialize_cpp_template_placeholders(pt, class_cpp_name=class_cpp, type_params=list(info.type_params), recv_cpp=recv) for pt in param_cpp_types]

def _specialize_call_param_cpp_types(tr: Translator, func: ast.expr, param_cpp_types: list[str] | None) -> list[str] | None:
    if not param_cpp_types:
        return param_cpp_types
    match func:
        case ast.Attribute(value=recv, attr=_):
            info = class_info_from_receiver(tr, recv)
            if info is None:
                return param_cpp_types
            recv_cpp = receiver_cpp_type_for_call(tr, recv)
            if not recv_cpp:
                return param_cpp_types
            return specialize_param_cpp_types_from_context(info, param_cpp_types, recv_cpp)
        case _:
            return param_cpp_types

def call_param_names(tr: Translator, func: ast.expr, *, call: ast.Call | None=None) -> list[str] | None:
    match func:
        case ast.Attribute(value=val, attr=method):
            info = class_info_from_receiver(tr, val)
            if info is not None and (method in info.methods or method in info.method_overloads):
                method_def = tr._method_def_for_call(info, method, call)
                if method_def is None:
                    return None
                names = [a.arg for a in method_def.args.args if a.arg not in ('self', 'cls')]
                sig = info.method_sig_for(method_def)
                if sig is not None and sig.variadic_template is not None:
                    names.append(sig.variadic_template.param_name)
                elif sig is not None and sig.vararg_pack is not None:
                    names.append(sig.vararg_pack.param_name)
                return names
        case ast.Name(id=name):
            if tr.class_info and (name in tr.class_info.methods or name in tr.class_info.method_overloads):
                method_def = tr._method_def_for_call(tr.class_info, name, call)
                if method_def is None:
                    return None
                names = [a.arg for a in method_def.args.args if a.arg not in ('self', 'cls')]
                sig = tr.class_info.method_sig_for(method_def)
                if sig is not None and sig.variadic_template is not None:
                    names.append(sig.variadic_template.param_name)
                elif sig is not None and sig.vararg_pack is not None:
                    names.append(sig.vararg_pack.param_name)
                return names
            mp = tr._active_module_path()
            fsig = tr.function_sigs.get((mp, name))
            if fsig is not None:
                func_def = next((f for f in tr._module_functions_for(mp) if f.name == name), None)
                if func_def is not None:
                    names = [a.arg for a in func_def.args.args]
                    if fsig.variadic_template is not None:
                        names.append(fsig.variadic_template.param_name)
                    elif fsig.vararg_pack is not None:
                        names.append(fsig.vararg_pack.param_name)
                    return names
        case _:
            pass
    return None

def _infer_func_template_subst_from_call(tr: 'Translator', func_def: ast.FunctionDef, func_ft: 'FuncTypeParams', call: ast.Call) -> dict[str, str]:
    """``astar[Node](nav, start, goal)`` 调用处用 ``start``/``goal`` 推断 ``Node`` 具体 C++ 类型。"""
    import ast
    from ..analysis.ir import strip_cpp_ref
    if not func_ft.template_names:
        return {}
    subst: dict[str, str] = {}
    params = [a for a in func_def.args.args if a.arg not in ('self', 'cls')]
    for param, arg_node in zip(params, call.args):
        ann = param.annotation
        if not isinstance(ann, ast.Name) or ann.id not in func_ft.template_names:
            continue
        concrete = strip_cpp_ref(tr._infer_expr_cpp_type(arg_node) or '')
        if concrete and concrete not in func_ft.template_names:
            subst.setdefault(ann.id, concrete)
    return subst

def _specialize_func_param_cpp_types(tr: 'Translator', func_def: ast.FunctionDef, param_types: list[str], call: ast.Call | None) -> list[str]:
    import re
    if call is None or not param_types:
        return param_types
    from ..analysis.ir import FuncTypeParams
    func_ft = FuncTypeParams.collect(func_def)
    subst = _infer_func_template_subst_from_call(tr, func_def, func_ft, call)
    if not subst:
        return param_types
    out: list[str] = []
    for pt in param_types:
        s = pt
        for name, concrete in sorted(subst.items(), key=lambda kv: len(kv[0]), reverse=True):
            s = re.sub(f'\\b{re.escape(name)}\\b', concrete, s)
        out.append(s)
    return out

def _module_function_param_cpp_types(tr: Translator, module_path: str, symbol: str, *, call: ast.Call | None=None) -> list[str] | None:
    func_def = tr._module_function_def_for_call(module_path, symbol, call)
    if func_def is None:
        return None
    key = (module_path, symbol)
    overload_sigs = tr.module_function_overload_sigs.get(key)
    if overload_sigs:
        overloads = tr.module_function_overloads.get(key, [])
        idx = next((i for i, ov in enumerate(overloads) if ov is func_def), -1)
        if idx < 0:
            return None
        fsig = overload_sigs[idx]
    else:
        fsig = tr.function_sigs.get(key)
    if fsig is None:
        return None
    from ..analysis.type_emit import function_param_cpp_types
    types = function_param_cpp_types(fsig, func_def)
    return _specialize_func_param_cpp_types(tr, func_def, types, call)

def _imported_function_param_cpp_types(tr: Translator, func: ast.expr, *, call: ast.Call | None=None) -> list[str] | None:
    attrs: list[str] = []
    cur: ast.expr = func
    while isinstance(cur, ast.Attribute):
        attrs.insert(0, cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    binding = resolve_import_attribute_chain(tr, cur.id, attrs)
    if binding is None or binding.kind != 'function':
        return None
    return _module_function_param_cpp_types(tr, binding.module_path, binding.symbol, call=call)

def call_param_cpp_types(tr: Translator, func: ast.expr, *, call: ast.Call | None=None) -> list[str] | None:
    match func:
        case ast.Attribute(value=val, attr=method):
            info = class_info_from_receiver(tr, val)
            if info is not None and (method in info.methods or method in info.method_overloads):
                return tr._ordered_method_param_cpp_types(info, method, call=call)
            imported = _imported_function_param_cpp_types(tr, func, call=call)
            if imported is not None:
                return imported
        case ast.Name(id=name):
            if tr.class_info and (name in tr.class_info.methods or name in tr.class_info.method_overloads):
                return tr._ordered_method_param_cpp_types(tr.class_info, name, call=call)
            mp = tr._active_module_path()
            binding = tr._effective_import_bindings().get(name)
            if binding is not None and binding.kind == 'function':
                imported = _module_function_param_cpp_types(tr, binding.module_path, binding.symbol, call=call)
                if imported is not None:
                    return imported
            imported = _module_function_param_cpp_types(tr, mp, name, call=call)
            if imported is not None:
                return imported
        case _:
            pass
    return None

def _call_default_nodes(tr: Translator, node: ast.Call, param_names: list[str]) -> dict[str, ast.expr]:
    """选中调用目标的形参默认值；供关键字实参补齐中间位置。"""
    method_def: ast.FunctionDef | None = None
    match node.func:
        case ast.Attribute(value=recv, attr=method):
            info = class_info_from_receiver(tr, recv)
            if info is not None and (method in info.methods or method in info.method_overloads):
                method_def = tr._method_def_for_call(info, method, node)
        case ast.Name(id=name):
            if tr.class_info and (name in tr.class_info.methods or name in tr.class_info.method_overloads):
                method_def = tr._method_def_for_call(tr.class_info, name, node)
    if method_def is None:
        return {}
    args = [a for a in method_def.args.args if a.arg not in ('self', 'cls')]
    defaults = method_def.args.defaults
    first_default = len(args) - len(defaults)
    out: dict[str, ast.expr] = {}
    for i, value in enumerate(defaults):
        out[args[first_default + i].arg] = value
    return {name: value for name, value in out.items() if name in param_names}


def emit_named_call_args(tr: Translator, node: ast.Call, param_names: list[str], param_cpp_types: list[str], *, lazy_params: dict | None=None) -> str:
    lazy_params = lazy_params or {}
    bound: dict[str, str] = {}
    for i, arg in enumerate(node.args):
        if i >= len(param_names):
            raise NotImplementedError('位置参数过多')
        name = param_names[i]
        lazy_info = lazy_params.get(name)
        if lazy_info is not None:
            from .lazy_param_emit import try_emit_lazy_call_arg
            v = try_emit_lazy_call_arg(tr, arg, lazy_info, param_name=name, func=node.func)
        elif i < len(param_cpp_types) and param_cpp_types[i]:
            v = tr._visit_value_for_type(arg, param_cpp_types[i])
        else:
            v = tr._visit_value_expr(arg)
        bound[name] = v
    for kw in node.keywords:
        if kw.arg is None:
            raise NotImplementedError('变体构造不支持 **kwargs')
        if kw.arg not in param_names:
            raise NotImplementedError(f'未知关键字参数: {kw.arg}')
        idx = param_names.index(kw.arg)
        lazy_info = lazy_params.get(kw.arg)
        if lazy_info is not None:
            from .lazy_param_emit import try_emit_lazy_call_arg
            v = try_emit_lazy_call_arg(tr, kw.value, lazy_info, param_name=kw.arg, func=node.func)
        elif idx < len(param_cpp_types) and param_cpp_types[idx]:
            v = tr._visit_value_for_type(kw.value, param_cpp_types[idx])
        else:
            v = tr._visit_value_expr(kw.value)
        bound[kw.arg] = v
    last = -1
    for i, name in enumerate(param_names):
        if name in bound:
            last = i
    defaults = _call_default_nodes(tr, node, param_names)
    out: list[str] = []
    for i in range(last + 1):
        name = param_names[i]
        if name in bound:
            out.append(bound[name])
            continue
        default = defaults.get(name)
        if default is None:
            raise NotImplementedError(f'关键字参数前缺少必填参数: {name}')
        if i < len(param_cpp_types) and param_cpp_types[i]:
            out.append(tr._visit_value_for_type(default, param_cpp_types[i]))
        else:
            out.append(tr._visit_value_expr(default))
    return ', '.join(out)

def _vararg_pack_for_call(tr: Translator, func: ast.expr, *, call: ast.Call | None=None) -> 'VarargPackInfo | None':
    from ..analysis.vararg_pack import VarargPackInfo
    match func:
        case ast.Attribute(value=val, attr=method):
            info = class_info_from_receiver(tr, val)
            if info is not None and (method in info.methods or method in info.method_overloads):
                method_def = tr._method_def_for_call(info, method, call)
                if method_def is None:
                    return None
                sig = info.method_sig_for(method_def)
                return sig.vararg_pack if sig is not None else None
        case ast.Name(id=name):
            if tr.class_info and (name in tr.class_info.methods or name in tr.class_info.method_overloads):
                method_def = tr._method_def_for_call(tr.class_info, name, call)
                if method_def is None:
                    return None
                sig = tr.class_info.method_sig_for(method_def)
                return sig.vararg_pack if sig is not None else None
            mp = tr._active_module_path()
            fsig = tr.function_sigs.get((mp, name))
            return fsig.vararg_pack if fsig is not None else None
        case _:
            return None

def _try_emit_pynone_call_arg(tr: Translator, func: ast.expr, arg: ast.expr) -> str | None:
    """``coro.send(None)`` / ``agen.asend(None)`` → ``PyNone()``（S37 禁止源码写 ``PyNone``）。"""
    if not tr._is_none_constant(arg):
        return None
    match func:
        case ast.Attribute(attr=method) if method in ('send', 'asend'):
            return f"{cpp_ident('PyNone')}()"
        case _:
            return None

def emit_call_args(tr: Translator, node: ast.Call, *, param_cpp_types: list[str] | None=None, param_names: list[str] | None=None, vararg_pack: 'VarargPackInfo | None'=None) -> str:
    from .lazy_param_emit import callee_lazy_params_for_call, try_emit_lazy_call_arg
    from .vararg_emit import _starred_arg_indices, emit_call_args_with_vararg_starred, emit_named_call_args_with_vararg, emit_vararg_pack_expr, fixed_param_count
    from .variadic_template_emit import _variadic_template_for_call, emit_call_args_variadic_template, fixed_param_count_vt
    lazy_params = callee_lazy_params_for_call(tr, node.func, call=node)
    vt = _variadic_template_for_call(tr, node.func, call=node)
    if vt is not None:
        if param_names is None:
            param_names = call_param_names(tr, node.func, call=node)
        if param_cpp_types is None:
            param_cpp_types = call_param_cpp_types(tr, node.func, call=node)
        param_cpp_types = _specialize_call_param_cpp_types(tr, node.func, param_cpp_types)
        return emit_call_args_variadic_template(tr, node, param_cpp_types=param_cpp_types, param_names=param_names, vt=vt)
    if vararg_pack is None:
        vararg_pack = _vararg_pack_for_call(tr, node.func, call=node)
    if lazy_params and param_names is None:
        param_names = call_param_names(tr, node.func, call=node)
    starred = _starred_arg_indices(node)
    if starred:
        if vt is None and vararg_pack is None:
            from .vararg_emit import current_vararg_pack
            if current_vararg_pack(tr) is not None:
                raise NotImplementedError('不能把可变参数整包 *args 转发给仅有普通形参的 callee（位置须与 *args: T[:] 形参一致）')
            raise NotImplementedError('目标函数无 *args: T[:] 形参，不能使用 *args 转发/展开')
        if param_names is None:
            param_names = call_param_names(tr, node.func, call=node)
        return emit_call_args_with_vararg_starred(tr, node, param_cpp_types=param_cpp_types, param_names=param_names, vararg_pack=vararg_pack)
    if param_cpp_types is None:
        param_cpp_types = call_param_cpp_types(tr, node.func, call=node)
    param_cpp_types = _specialize_call_param_cpp_types(tr, node.func, param_cpp_types)
    if param_names is None and (node.keywords or vararg_pack is not None):
        param_names = call_param_names(tr, node.func, call=node)
    if lazy_params and param_names is None:
        param_names = call_param_names(tr, node.func, call=node)
    if param_names:
        num_fixed = fixed_param_count(param_names, vararg_pack)
    elif param_cpp_types and vararg_pack is not None:
        num_fixed = len(param_cpp_types) - 1
    elif param_cpp_types:
        num_fixed = len(param_cpp_types)
    else:
        num_fixed = len(node.args)
    if param_names and vararg_pack is not None and (node.keywords or len(node.args) > num_fixed):
        return emit_named_call_args_with_vararg(tr, node, param_names, param_cpp_types or [], vararg_pack)
    if param_names and vararg_pack is None and (node.keywords or len(node.args) > len(param_names) or lazy_params):
        return emit_named_call_args(tr, node, param_names, param_cpp_types or [], lazy_params=lazy_params)
    parts: list[str] = []
    if vararg_pack is not None:
        for i in range(num_fixed):
            if i >= len(node.args):
                break
            arg = node.args[i]
            pname = param_names[i] if param_names and i < len(param_names) else None
            lazy_info = lazy_params.get(pname) if pname else None
            if lazy_info is not None:
                v = try_emit_lazy_call_arg(tr, arg, lazy_info, param_name=pname or '', func=node.func)
            elif (none_v := _try_emit_pynone_call_arg(tr, node.func, arg)):
                v = none_v
            elif param_cpp_types and i < len(param_cpp_types) and param_cpp_types[i]:
                v = tr._visit_value_for_type(arg, param_cpp_types[i])
            else:
                v = tr._visit_value_expr(arg)
            parts.append(v)
        extra = node.args[num_fixed:]
        parts.append(emit_vararg_pack_expr(tr, vararg_pack.cpp_type, extra, elem_cpp_type=vararg_pack.elem_cpp_type))
        return ', '.join(parts)
    for i, arg in enumerate(node.args):
        pname = param_names[i] if param_names and i < len(param_names) else None
        lazy_info = lazy_params.get(pname) if pname else None
        if lazy_info is not None:
            v = try_emit_lazy_call_arg(tr, arg, lazy_info, param_name=pname or '', func=node.func)
        elif (none_v := _try_emit_pynone_call_arg(tr, node.func, arg)):
            v = none_v
        elif param_cpp_types and i < len(param_cpp_types) and param_cpp_types[i]:
            v = tr._visit_value_for_type(arg, param_cpp_types[i])
        else:
            v = tr._visit_value_expr(arg)
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('__add__', '__radd__') and len(node.args) == 1 and i == 0:
                recv_ty = tr._infer_expr_cpp_type(node.func.value)
                arg_ty = tr._infer_expr_cpp_type(arg)
                from ..analysis.type_pred import is_char_type, is_str_type
                from ..analysis.ir import cpp_ident
                if node.func.attr == '__add__' and is_str_type(recv_ty, classes=tr.classes) and is_char_type(arg_ty, classes=tr.classes):
                    v = f'{cpp_ident("str")}({v})'
                elif node.func.attr == '__radd__' and is_str_type(arg_ty, classes=tr.classes) and is_char_type(recv_ty, classes=tr.classes):
                    v = f'{cpp_ident("str")}({v})'
        parts.append(v)
    if isinstance(node.func, ast.Attribute) and node.func.attr == '__add__' and len(node.args) == 1 and parts:
        from ..analysis.type_pred import is_char_type, is_str_type
        from ..analysis.ir import cpp_ident
        recv_ty = tr._infer_expr_cpp_type(node.func.value)
        ps = cpp_ident('str')
        if is_str_type(recv_ty, classes=tr.classes) or recv_ty == ps:
            arg_ty = strip_cpp_ref(tr._infer_expr_cpp_type(node.args[0]) or '')
            if is_char_type(arg_ty, classes=tr.classes) or arg_ty in ('PyChar', 'char') or not arg_ty:
                parts[0] = f'{ps}({parts[0]})'
    return ', '.join(parts)

def _single_char_str_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        s = node.value
        if len(s) == 1:
            return s
    return None

def emit_assert_equal_args(tr: Translator, node: ast.Call) -> str:
    parts: list[str] = []
    for i, arg in enumerate(node.args):
        v = tr._visit_value_expr(arg)
        peer = node.args[1 - i]
        peer_t = tr._infer_expr_cpp_type(peer)
        if is_str_type(peer_t) or tr._expr_is_str_value(peer):
            peer_t = cpp_ident('str')
        ch_lit = _single_char_str_literal(arg)
        peer_ch_lit = _single_char_str_literal(peer)
        if ch_lit is not None and is_char_type(peer_t):
            v = f'PyChar({ord(ch_lit[0])})'
        elif peer_ch_lit is not None and is_char_type(tr._infer_expr_cpp_type(arg)):
            v = tr._visit_value_expr(arg)
        else:
            cursor_read = tr._coerce_json_doc_cursor_read(v, peer_t, rhs_node=arg)
            if cursor_read is not None:
                v = cursor_read
            else:
                arg_t = strip_cpp_ref(tr._infer_expr_cpp_type(arg) or '')
                if is_iter_result_type(arg_t) and peer_t and (not is_iter_result_type(peer_t)):
                    v = iter_result_value_cpp(v)
                elif (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and (arg.func.attr == '__next__') and (not arg.args) or (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and (arg.func.id == 'next') and (len(arg.args) == 1) and (not arg.keywords))) and peer_t and (not is_iter_result_type(peer_t)):
                    v = iter_result_value_cpp(v)
                elif peer_t:
                    v = tr._coerce_expr_to_cpp_type(v, peer_t, rhs_node=arg)
        parts.append(v)
    return ', '.join(parts)

def try_emit_scalar_type_static_call(tr: Translator, node: ast.Call) -> str | None:
    """``float64.isInf(x)`` / ``float.isfinite(x)`` → ``py_types.h`` 宏。"""
    from ..analysis.ir import scalar_type_static_method_cpp
    match node.func:
        case ast.Attribute(value=ast.Name(id=type_name), attr=method):
            if node.keywords or len(node.args) != 1:
                return None
            arg_cpp = tr._visit_value_expr(node.args[0])
            return scalar_type_static_method_cpp(type_name, method, arg_cpp)
    return None

def _qualified_class_template_cpp(tr: Translator, info: ClassInfo, type_arg: str) -> str:
    callee = f'{info.cpp_name()}<{type_arg}>'
    if info.module_path != RUNTIME_PKG and tr._is_stdlib_module(info.module_path):
        base, _, tail = callee.partition('<')
        if tail:
            return f'{qualify_symbol_in_module(info.module_path, base)}<{tail}>'
        return qualify_symbol_in_module(info.module_path, callee)
    return qualify_symbol_in_module(info.module_path, callee)

def _reject_method_subscript_on_generic_class(tr: Translator, cls_name: str, method: str, info: ClassInfo) -> None:
    if not info.type_params:
        return
    raise NotImplementedError(f'{cls_name}.{method}[…](…) 非法：泛型类请写 {cls_name}[T].{method}(…)（谁泛型谁传参）')

def _recv_is_instantiated_generic(tr: Translator, recv: ast.expr, info: ClassInfo) -> bool:
    recv_t = strip_cpp_ref(tr._infer_expr_cpp_type(recv) or '')
    if not recv_t or '<' not in recv_t:
        return False
    base, _, _ = recv_t.partition('<')
    cpp = info.cpp_name()
    return base == cpp or base.endswith(f'::{cpp}')

def class_subscript_static_call_return_type(tr: Translator, info: ClassInfo, method: str, slice_node: ast.expr) -> str | None:
    sig = info.method_sigs.get(method)
    if sig is None or not sig.is_static:
        return None
    type_arg = tr._parse_type_args(slice_node, tr._active_type_params())
    if not type_arg:
        return None
    ret_lead = sig_return_storage_cpp(sig)
    ret_trail = sig.ret_trail or ''
    if not ret_lead:
        if info.type_params:
            return _qualified_class_template_cpp(tr, info, type_arg)
        return None
    ret = (ret_lead + ret_trail).strip()
    if not ret:
        return None
    # 类形参名保持原样（勿 ``cpp_ident`` → ``PyElement``）
    if len(info.type_params) == 1 and ret == info.type_params[0]:
        return _qualified_class_template_cpp(tr, info, type_arg)
    tp = info.type_params[0] if info.type_params else ''
    if tp and ret.endswith(tp) and (ret != tp):
        ret = ret[:-len(tp)] + type_arg
    return ret

def type_context_ann_from_stack(tr: 'Translator') -> ast.expr | None:
    """``AnnAssign`` / ``return`` / 字段赋值目标注解，供 ``new.方法(...)`` 解析目标类。"""
    forced = getattr(tr, '_type_context_ann_stack', None)
    if forced:
        return forced[-1]
    ret_ann: ast.expr | None = None
    for node in reversed(tr._ast_node_stack):
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            return node.annotation
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            ann = tr._annotation_expr_for_assign_target(node.targets[0])
            if ann is not None:
                return ann
        if isinstance(node, ast.Return) and ret_ann is None:
            if tr.current_method is not None and tr.current_method.returns is not None:
                ret_ann = tr.current_method.returns
    return ret_ann

def is_new_receiver_attr_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and (node.func.value.id == 'new')

def is_new_staticproperty_ref(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and (node.value.id == 'new')

def _delegate_names(tr: 'Translator') -> frozenset[str]:
    return frozenset(tr.delegates.keys())

def _is_static_method(info: ClassInfo, attr: str) -> bool:
    sig = info.method_sigs.get(attr)
    if sig is not None and sig.is_static:
        return True
    ov_sigs = info.method_overload_sigs.get(attr)
    return ov_sigs is not None and ov_sigs[0].is_static

def _is_instance_method(info: ClassInfo, attr: str) -> bool:
    if attr not in info.methods and attr not in info.method_overload_sigs:
        return False
    return not _is_static_method(info, attr)

def _static_property_return_cpp_type(info: ClassInfo, attr: str) -> str | None:
    prop = info.static_properties.get(attr)
    if prop is None or prop.getter_sig is None:
        return None
    gs = prop.getter_sig
    return sig_return_full_cpp(gs)

def _instance_property_return_cpp_type(info: ClassInfo, attr: str) -> str | None:
    prop = info.properties.get(attr)
    if prop is None or prop.getter_sig is None:
        return None
    gs = prop.getter_sig
    return sig_return_full_cpp(gs)

def _static_class_field_cpp_type(tr: 'Translator', info: ClassInfo, attr: str) -> str | None:
    stmt = info.static_class_fields.get(attr)
    if stmt is not None and stmt.annotation is not None:
        return tr._parse_storage_type(stmt.annotation, list(info.type_params))
    ft = field_storage_cpp(info, attr)
    return ft or None

def _member_call_receiver_label(tr: 'Translator', receiver: ast.expr) -> str:
    if isinstance(receiver, ast.Name):
        return receiver.id
    if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name):
        return f'{receiver.value.id}.{receiver.attr}'
    return tr.visit(receiver)

def _non_invokable_member_call_message(receiver: str, attr: str, *, kind: str) -> str:
    return f'{receiver}.{attr}() 不可调用：{kind} 须写 {receiver}.{attr}；仅方法或 Function/Callable/Delegate 等可调用类型成员可写 (...)'

def _raise_if_non_invokable_class_member(tr: 'Translator', info: ClassInfo, receiver: str, attr: str) -> None:
    if _is_static_method(info, attr):
        return
    if attr in info.static_properties:
        ret_t = _static_property_return_cpp_type(info, attr)
        if ret_t and is_invokable_type(ret_t, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return
        raise NotImplementedError(_non_invokable_member_call_message(receiver, attr, kind='@staticproperty'))
    if attr in info.static_class_fields:
        ft = _static_class_field_cpp_type(tr, info, attr)
        if ft and is_invokable_type(ft, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return
        raise NotImplementedError(_non_invokable_member_call_message(receiver, attr, kind='静态字段'))

def _raise_if_non_invokable_instance_property(tr: 'Translator', info: ClassInfo, receiver: ast.expr, attr: str) -> None:
    if _is_instance_method(info, attr) or _is_static_method(info, attr):
        return
    label = _member_call_receiver_label(tr, receiver)
    if attr in info.properties or attr in info.field_properties:
        ret_t = _instance_property_return_cpp_type(info, attr)
        if not ret_t:
            ret_t = field_storage_cpp(info, attr) or None
        if ret_t and is_invokable_type(ret_t, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return
        raise NotImplementedError(_non_invokable_member_call_message(label, attr, kind='@property'))
    if attr in info.fields:
        ft = field_storage_cpp(info, attr)
        if ft and is_invokable_type(ft, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return
        raise NotImplementedError(_non_invokable_member_call_message(label, attr, kind='字段'))

def _emit_class_invokable_member_call(tr: 'Translator', info: ClassInfo, attr: str, node: ast.Call) -> str | None:
    """类级 ``Cls.attr(...)``：可调用 ``@staticproperty`` / 静态字段 → getter/成员再 ``()``。"""
    if attr in info.static_properties:
        ret_t = _static_property_return_cpp_type(info, attr)
        if not ret_t or not is_invokable_type(ret_t, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return None
        base = tr._static_property_read(info.name, attr)
        if base is None:
            return None
        arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
        if arg_str:
            return f'{base}({arg_str})'
        return f'{base}()'
    if attr in info.static_class_fields:
        ft = _static_class_field_cpp_type(tr, info, attr)
        if not ft or not is_invokable_type(ft, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return None
        ref = f'{info.cpp_name()}::{info.cpp_member_name(attr)}'
        arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
        if arg_str:
            return f'{ref}({arg_str})'
        return f'{ref}()'
    return None

def _emit_instance_invokable_member_call(tr: 'Translator', receiver: ast.expr, attr: str, node: ast.Call) -> str | None:
    info = tr._class_info_for_receiver(receiver)
    if info is None:
        return None
    if _is_instance_method(info, attr) or _is_static_method(info, attr):
        return None
    if attr in info.properties or attr in info.field_properties:
        ret_t = _instance_property_return_cpp_type(info, attr)
        if not ret_t:
            ret_t = field_storage_cpp(info, attr) or None
        if not ret_t or not is_invokable_type(ret_t, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return None
        read = tr._property_read(receiver, attr)
        if read is None:
            return None
        arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
        if arg_str:
            return f'{read}({arg_str})'
        return f'{read}()'
    if attr in info.fields:
        ft = field_storage_cpp(info, attr)
        if not ft or not is_invokable_type(ft, classes=tr.classes, delegate_names=_delegate_names(tr)):
            return None
        recv = tr._paren_expr(tr.visit(receiver))
        sep = tr._member_access_sep(receiver, recv)
        mcpp = tr._attr_cpp_name(receiver, attr)
        arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
        if arg_str:
            return f'{recv}{sep}{mcpp}({arg_str})'
        return f'{recv}{sep}{mcpp}()'
    return None

def try_emit_new_staticproperty_ref(tr: 'Translator', node: ast.Attribute, *, field_cpp_type: str | None=None) -> str | None:
    """``x: Vector2 = new.zero`` / ``self._p = new.zero``（按注解或字段 C++ 类型）。"""
    if not is_new_staticproperty_ref(node):
        return None
    attr = node.attr
    cpp_type = field_cpp_type
    if not cpp_type:
        ann = type_context_ann_from_stack(tr)
        if ann is None:
            return None
        if isinstance(ann, ast.Name) and ann.id == 'Self':
            info_ctx = tr._active_class_info()
            if info_ctx is None:
                return None
            cpp_type = info_ctx.template_cpp_type() if info_ctx.type_params else info_ctx.storage_cpp_type()
        else:
            cpp_type = tr._parse_storage_type(ann, tr._active_type_params())
    if not cpp_type:
        return None
    info = tr._class_info_for_type(cpp_type)
    if info is None or attr not in info.static_properties:
        return None
    if info.type_params:
        from ..analysis.ir import cpp_template_base_and_args
        parsed = cpp_template_base_and_args(ClassInfo.unwrap_refcount_type(strip_cpp_ref(cpp_type)))
        if parsed is not None:
            _base, args = parsed
            getter = tr._property_getter_cpp_name(info, attr)
            qbase = qualify_symbol_in_module(info.module_path, info.cpp_name())
            return f'{qbase}<{", ".join(args)}>::{getter}()'
    return tr._static_property_read(info.name, attr)

def _coroutine_class_name_for_call(tr: 'Translator', func_name: str) -> str | None:
    from ..passes.generators import COROUTINE_SUFFIX
    coro_name = f'{func_name}{COROUTINE_SUFFIX}'
    if coro_name in tr.classes:
        return coro_name
    mp = tr._active_module_path()
    if mp:
        for f_mp, func in tr.module_functions:
            if f_mp == mp and func.name == func_name:
                if isinstance(func, ast.AsyncFunctionDef) or coro_name in tr.classes:
                    return coro_name
                break
    return None

def _concrete_coroutine_cpp_type(tr: 'Translator', arg: ast.expr) -> str | None:
    from ..analysis.ir import strip_cpp_type_qualifiers
    from ..analysis.module_namespace import qualify_symbol_in_module
    t = strip_cpp_ref(tr._infer_expr_cpp_type(arg) or '')
    if t and is_concrete_coroutine_type(t):
        return strip_cpp_type_qualifiers(t)
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
        coro_name = _coroutine_class_name_for_call(tr, arg.func.id)
        if coro_name is None:
            return None
        mp = tr._active_module_path()
        if mp:
            return qualify_symbol_in_module(mp, coro_name)
        return coro_name
    return None

def _emit_make_coroutine_from_arg(tr: 'Translator', arg: ast.expr) -> str:
    coro_t = _concrete_coroutine_cpp_type(tr, arg)
    inner = tr._visit_value_expr(arg)
    if coro_t:
        return f'makeCoroutine<typename {coro_t}::Element, typename {coro_t}::SendType, typename {coro_t}::ReturnType>({inner})'
    return inner

def _task_elem_type_from_expr(tr: 'Translator', arg: ast.expr) -> str | None:
    from ..analysis.ir import split_cpp_template_args, strip_cpp_type_qualifiers
    t = strip_cpp_type_qualifiers(strip_cpp_ref(tr._infer_expr_cpp_type(arg) or ''))
    marker = 'Task<'
    idx = t.rfind(marker)
    if idx < 0:
        return None
    inner = t[idx + len(marker):]
    if not inner.endswith('>'):
        return None
    args = split_cpp_template_args(inner[:-1])
    return args[0].strip() if args else None

def _module_function_return_cpp_type(tr: 'Translator', module_path: str | None, name: str) -> str | None:
    if module_path is None:
        return None
    for f_mp, func in tr.module_functions:
        if f_mp != module_path or func.name != name or func.returns is None:
            continue
        from ..analysis.variadic_template import parse_function_type_params
        regular, _capture, _header_tuple = parse_function_type_params(func)
        return tr._parse_storage_type(func.returns, set(regular))
    return None

def _callable_return_type_from_expr(tr: 'Translator', arg: ast.expr) -> str | None:
    from .delegate_emit import py_callable_type_parts
    t = strip_cpp_ref(tr._infer_expr_cpp_type(arg) or '')
    parts = py_callable_type_parts(t)
    if parts is not None and not parts[1]:
        return parts[0]
    if isinstance(arg, ast.Lambda):
        ret = strip_cpp_ref(tr._infer_expr_cpp_type(arg.body) or '')
        return ret or cpp_ident('int')
    if isinstance(arg, ast.Name):
        binding = tr._effective_import_bindings().get(arg.id)
        if binding is not None and binding.kind == 'function':
            hit = _module_function_return_cpp_type(tr, binding.module_path, binding.symbol)
            if hit is not None:
                return hit
        hit = _module_function_return_cpp_type(tr, tr._active_module_path(), arg.id)
        if hit is not None:
            return hit
    return None

def _static_method_template_angle(tr: 'Translator', info: ClassInfo, method: str, node: ast.Call) -> str:
    sig = info.method_sigs.get(method)
    if sig is None or not sig.func_ft.template_names:
        return ''
    tnames = sig.func_ft.template_names
    if method == 'create' and node.args and (len(tnames) >= 3):
        coro_t = _concrete_coroutine_cpp_type(tr, node.args[0])
        if coro_t:
            return ''
    if method == 'gather' and node.args and (len(tnames) == 1):
        elem = _task_elem_type_from_expr(tr, node.args[0])
        if elem:
            return f'<{elem}>'
    if len(tnames) == 1 and node.args:
        coro_t = _concrete_coroutine_cpp_type(tr, node.args[0])
        if coro_t:
            return f'<{coro_t}>'
    return ''

def _emit_task_gather_pack(tr: 'Translator', info: ClassInfo, node: ast.Call, elem_cpp: str) -> str:
    from ..analysis.module_namespace import qualify_symbol_in_module
    from .vararg_emit import emit_vararg_pack_expr
    task_t = f'{qualify_symbol_in_module(info.module_path, info.cpp_name())}<{elem_cpp}>'
    pack_t = f'PyArray<{task_t}>'
    return emit_vararg_pack_expr(tr, pack_t, list(node.args), elem_cpp_type=task_t)

def static_method_call_type_receiver(func: ast.expr) -> tuple[ast.expr, str] | None:
    """``Cls[T].method`` / ``Cls.method`` → ``(类型 AST, 方法名)``。"""
    match func:
        case ast.Attribute(value=recv, attr=method) if isinstance(recv, (ast.Subscript, ast.Name)):
            return (recv, method)
    return None

def emit_class_static_method_call(tr: 'Translator', info: ClassInfo, method: str, slice_node: ast.expr | None, node: ast.Call) -> str | None:
    sig = info.method_sigs.get(method)
    if sig is None:
        from ..passes.class_type_if import class_type_if_method_sig
        sig = class_type_if_method_sig(info, method)
    if sig is None or not sig.is_static:
        return None
    type_arg = ''
    if info.type_params:
        if slice_node is None:
            defaults = info.type_param_defaults
            if not defaults or len(defaults) != len(info.type_params):
                return None
            args = [copy.deepcopy(defaults[p]) for p in info.type_params]
            slice_node = args[0] if len(args) == 1 else ast.Tuple(elts=args, ctx=ast.Load())
        type_arg = tr._parse_type_args(slice_node, tr._active_type_params())
        if not type_arg:
            return None
    arg_str = emit_call_args(tr, node, param_cpp_types=tr._ordered_method_param_cpp_types(info, method, call=node))
    # ``new.factory(...)`` bypasses the ordinary ``Cls.factory(...)`` emitter;
    # keep its cross-module callee globally qualified inside nested namespaces.
    base = "::" + qualify_symbol_in_module(info.module_path, info.cpp_name())
    member = info.cpp_member_name(method)
    if type_arg:
        callee = f'{base}<{type_arg}>::{member}'
    else:
        callee = f'{base}::{member}'
    if arg_str:
        return f'{callee}({arg_str})'
    return f'{callee}()'

def try_emit_class_subscript_static_call(tr: Translator, node: ast.Call) -> str | None:
    """``JsonDocument[Org].open(…)`` → ``JsonDocument<Org>::open(…)``（谁泛型谁传参）。"""
    match node.func:
        case ast.Attribute(value=ast.Subscript(value=ast.Name(id=cls_name), slice=sl), attr=method):
            if not tr._name_refers_to_class(cls_name):
                return None
            info = tr._class_info_for_ref(cls_name)
            if info is None or not info.type_params:
                return None
            return emit_class_static_method_call(tr, info, method, sl, node)
    return None

def try_emit_new_receiver_static_call(tr: Translator, node: ast.Call) -> str | None:
    """``x: JsonDocument[Org] = new.open(…)`` / ``x: Message = new.Quit()``。"""
    from ..passes.union_expand import union_variant_names
    if not is_new_receiver_attr_call(node):
        return None
    ann = type_context_ann_from_stack(tr)
    method = node.func.attr
    if ann is None:
        raise NotImplementedError(
            f'new.{method}(...) 需类型上下文：有字段/返回注解时对目标写 ``… = new.{method}(...)``；'
            f'无法推断时写 ``Cls.{method}(...)``（勿仅为 ``new`` 造 ``x: T = new.{method}(...)`` 临时变量）'
        )
    match ann:
        case ast.Subscript(value=ast.Name(id=cls_name), slice=sl):
            slice_node: ast.expr | None = sl
        case ast.Name(id=cls_name):
            slice_node = None
        case _:
            raise NotImplementedError('new.方法(...) 的类型上下文须为具体类或 ``Cls[T]`` 注解')
    context_cpp = tr._parse_storage_type(ann, tr._active_type_params())
    self_context = cls_name == 'Self'
    if cls_name in tr._active_type_params():
        mcpp = tr._attr_cpp_name(ast.Name(id=cls_name, ctx=ast.Load()), method)
        arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
        if arg_str:
            return f'{cls_name}::{mcpp}({arg_str})'
        return f'{cls_name}::{mcpp}()'
    if self_context:
        info = tr._active_class_info()
        if info is None:
            raise NotImplementedError(f'new.{method}(...) 的 ``Self`` 须处于类方法体内')
        cls_name = info.name
    elif not tr._name_refers_to_class(cls_name):
        info = tr._class_info_for_type(context_cpp)
        if info is None:
            raise NotImplementedError(f'new.{method}(...) 的注解类 {cls_name!r} 不可解析')
        cls_name = info.name
    else:
        info = tr._class_info_for_ref(cls_name)
    if info is None:
        raise NotImplementedError(f'new.{method}(...) 的注解类 {cls_name!r} 不可解析')
    if info.is_union and method in union_variant_names(info):
        out = tr._emit_union_variant_ctor(cls_name, method, node, context_cpp=context_cpp, type_args_slice=slice_node)
        if out is not None:
            return out
        raise NotImplementedError(f'new.{method}(...) 须对应 {cls_name} 的 ``@union`` 变体')
    if self_context and slice_node is None and info.type_params:
        args = [ast.Name(id=p, ctx=ast.Load()) for p in info.type_params]
        slice_node = args[0] if len(args) == 1 else ast.Tuple(elts=args, ctx=ast.Load())
    out = emit_class_static_method_call(tr, info, method, slice_node, node)
    if out is None:
        raise NotImplementedError(f'new.{method}(...) 须对应 {cls_name} 的 ``@staticmethod`` 方法或 ``@union`` 变体')
    return out

_ALLOCATOR_STATIC_METHODS = frozenset({'alloc_array', 'alloc_raw_array', 'free_array'})

def try_emit_templated_static_call(tr: Translator, node: ast.Call) -> str | None:
    match node.func:
        case ast.Subscript(value=ast.Attribute(value=ast.Name(id=cls_name), attr=method), slice=sl):
            from ..emit.builtin_call_emit import is_json_class_ref
            if cls_name in tr._active_type_params() and method in _ALLOCATOR_STATIC_METHODS:
                from ..analysis.ir import cpp_type_param_template_name, escape_cpp_param
                type_arg = tr._parse_type(sl, tr._active_type_params())
                if not type_arg:
                    return None
                arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
                callee = f'{cpp_type_param_template_name(cls_name)}::{escape_cpp_param(method)}<{type_arg}>'
                if arg_str:
                    return f'{callee}({arg_str})'
                return f'{callee}()'
            if is_json_class_ref(tr, cls_name):
                return None
            info = tr._class_info_for_ref(cls_name)
            if info is None:
                return None
            sig = info.method_sigs.get(method)
            if sig is None or not sig.is_static:
                return None
            _reject_method_subscript_on_generic_class(tr, cls_name, method, info)
            type_arg = tr._parse_type(sl, tr._active_type_params())
            if not type_arg:
                return None
            arg_str = emit_call_args(tr, node, param_cpp_types=tr._ordered_method_param_cpp_types(info, method, call=node))
            base = qualify_symbol_in_module(info.module_path, info.cpp_name())
            member = info.cpp_member_name(method)
            if not info.type_params:
                callee = f'{base}::{member}<{type_arg}>'
            else:
                callee = f'{base}<{type_arg}>::{member}'
            if arg_str:
                return f'{callee}({arg_str})'
            return f'{callee}()'
    return None

def templated_instance_call_return_type(tr: Translator, info: ClassInfo, method: str, slice_node: ast.expr) -> str | None:
    sig = info.method_sigs.get(method)
    if sig is None or not sig.func_ft.template_names:
        return None
    type_arg = tr._parse_type_args(slice_node, tr._active_type_params())
    if not type_arg:
        return None
    ret = sig_return_storage_cpp(sig)
    if len(sig.func_ft.template_names) == 1:
        tp = sig.func_ft.template_names[0]
        if ret == tp:
            return type_arg
        ret = ret.replace(f'<{tp}>', f'<{type_arg}>')
        if ret.endswith(tp) and ret != tp:
            ret = ret[:-len(tp)] + type_arg
    if info.module_path != RUNTIME_PKG and tr._is_stdlib_module(info.module_path):
        base, _, tail = ret.partition('<')
        if tail:
            return f'{qualify_symbol_in_module(info.module_path, base)}<{tail}'
        return qualify_symbol_in_module(info.module_path, ret)
    return ret

def try_emit_templated_instance_call(tr: Translator, node: ast.Call) -> str | None:
    match node.func:
        case ast.Subscript(value=ast.Attribute(value=recv, attr=method), slice=sl):
            info = tr._class_info_for_expr(recv)
            if info is None:
                return None
            if info.type_params and _recv_is_instantiated_generic(tr, recv, info):
                recv_label = recv.id if isinstance(recv, ast.Name) else info.name
                raise NotImplementedError(f'已类型化的 {info.name}[…].{method}[…](…) 非法：请写 {recv_label}.{method}(…)（谁泛型谁传参）')
            sig = info.method_sigs.get(method)
            if sig is None or not sig.func_ft.template_names:
                return None
            type_arg = tr._parse_type_args(sl, tr._active_type_params())
            if not type_arg:
                return None
            recv_cpp = tr._paren_expr(tr.visit(recv))
            sep = tr._member_access_sep(recv, recv_cpp)
            mcpp = info.cpp_member_name(method)
            arg_str = emit_call_args(tr, node, param_cpp_types=tr._ordered_method_param_cpp_types(info, method, call=node))
            callee = f'{recv_cpp}{sep}{mcpp}<{type_arg}>'
            if arg_str:
                return f'{callee}({arg_str})'
            return f'{callee}()'
    return None

def try_emit_json_document_load_call(tr: Translator, node: ast.Call) -> str | None:
    match node.func:
        case ast.Subscript(value=ast.Attribute(value=ast.Name(id=root), attr='load'), slice=_):
            if not tr.scope:
                return None
            t = scope_storage_cpp(tr, root)
            if 'JsonDocument' not in t:
                return None
            return f'{cpp_param(root)}.load()'
    return None

def _template_deduction_param_indices(func_def: ast.FunctionDef, func_ft: 'FuncTypeParams') -> set[int]:
    """形参注解为同名 ``TypeVar`` 时仅用于 C++ 模板推导，不传实参。"""
    tnames = set(func_ft.template_names)
    if not tnames:
        return set()
    out: set[int] = set()
    for i, arg in enumerate(func_def.args.args):
        if isinstance(arg.annotation, ast.Name) and arg.annotation.id in tnames:
            out.add(i)
    return out

def _module_function_template_angle(tr: 'Translator', func_def: ast.FunctionDef, func_ft: 'FuncTypeParams', node: ast.Call, *, explicit_type_arg: str | None) -> str:
    if explicit_type_arg:
        return f'<{explicit_type_arg}>'
    deduction = _template_deduction_param_indices(func_def, func_ft)
    if len(func_ft.template_names) != 1 or not deduction:
        return ''
    for idx in sorted(deduction):
        if idx >= len(node.args):
            continue
        arg = node.args[idx]
        coro_t = _concrete_coroutine_cpp_type(tr, arg)
        if coro_t:
            return f'<{coro_t}>'
        arg_t = strip_cpp_ref(tr._infer_expr_cpp_type(arg) or '')
        if arg_t and arg_t not in func_ft.template_names:
            return f'<{arg_t}>'
    for tp in getattr(func_def, 'type_params', None) or ():
        if isinstance(tp, ast.TypeVar) and tp.name in func_ft.template_names:
            default = getattr(tp, 'default_value', None)
            if default is not None:
                return f'<{tr._parse_type(default, tr._active_type_params())}>'
    return ''

def _emit_module_function_call(tr: 'Translator', mp: str, func_def: ast.FunctionDef, node: ast.Call, *, explicit_type_arg: str | None=None) -> str:
    from ..analysis.ir import FuncTypeParams, has_named_decorator, is_native_function_body
    func_ft = FuncTypeParams.collect(func_def)
    deduction = _template_deduction_param_indices(func_def, func_ft)
    cpp = tr._module_function_cpp_name(mp, func_def)
    if '::' not in cpp and cpp not in PRIMITIVE_HEADER_MAP:
        ns = namespace_qualifier_for_module(mp)
        if ns:
            cpp = f'::{ns}::{cpp}'
    callee = tr._qualify_import_call(cpp, func_def.name, module_path=mp)
    angle = _module_function_template_angle(tr, func_def, func_ft, node, explicit_type_arg=explicit_type_arg)
    native_deduction_only: set[int] = set()
    if has_named_decorator(func_def, 'native') or is_native_function_body(func_def.body):
        native_deduction_only = {
            i for i in deduction
            if i < len(func_def.args.args) and func_def.args.args[i].arg.startswith('_')
        }
    if native_deduction_only:
        kept = [a for i, a in enumerate(node.args) if i not in native_deduction_only]
    else:
        kept = list(node.args)
    fsig = tr.function_sigs.get((mp, func_def.name))
    param_types: list[str] | None = None
    if fsig is not None:
        from ..analysis.type_emit import function_param_cpp_types
        param_types = function_param_cpp_types(fsig, func_def)
        param_types = _specialize_func_param_cpp_types(tr, func_def, param_types, node)
        if native_deduction_only:
            param_types = [t for i, t in enumerate(param_types) if i not in native_deduction_only]
    if param_types:
        parts: list[str] = []
        for i, arg in enumerate(kept):
            if i < len(param_types) and param_types[i]:
                v = tr._visit_value_for_type(arg, param_types[i])
            else:
                v = tr._visit_value_expr(arg)
            parts.append(v)
        arg_str = ', '.join(parts)
    else:
        arg_str = ', '.join((tr._visit_value_expr(a) for a in kept))
    if arg_str:
        return f'{callee}{angle}({arg_str})'
    return f'{callee}{angle}()'

def _try_emit_imported_templated_function_subscript_call(tr: 'Translator', name: str, sl: ast.expr, node: ast.Call) -> str | None:
    """``from module import f`` 后的 ``f[T](...)`` 按模块函数模板调用。"""
    binding = tr._effective_import_bindings().get(name)
    if binding is None or binding.kind != 'function':
        return None
    func_def = tr._module_function_def_for_call(binding.module_path, binding.symbol, call=node)
    if func_def is None:
        return None
    from ..analysis.ir import FuncTypeParams
    func_ft = FuncTypeParams.collect(func_def)
    if not func_ft.template_names:
        return None
    from ..passes.type_if import validate_function_type_args
    validate_function_type_args(func_def, sl)
    type_arg = tr._parse_type_args(sl, tr._active_type_params())
    if not type_arg:
        return None
    return _emit_module_function_call(tr, binding.module_path, func_def, node, explicit_type_arg=type_arg)

def _try_emit_module_templated_function_subscript_call(tr: 'Translator', name: str, sl: ast.expr, node: ast.Call) -> str | None:
    """``_slot_result[T](slot)`` 等同模块模板 ``@native`` 函数，勿走构造路径。"""
    mp = tr._active_module_path()
    if not mp:
        return None
    func_def = tr._module_function_def_for_call(mp, name, call=node)
    if func_def is None:
        return None
    from ..analysis.ir import FuncTypeParams
    func_ft = FuncTypeParams.collect(func_def)
    if not func_ft.template_names:
        return None
    from ..passes.type_if import validate_function_type_args
    validate_function_type_args(func_def, sl)
    type_arg = tr._parse_type_args(sl, tr._active_type_params())
    if not type_arg:
        return None
    return _emit_module_function_call(tr, mp, func_def, node, explicit_type_arg=type_arg)

def _try_emit_imported_function_call(tr: Translator, name: str, node: ast.Call, args: str) -> str | None:
    """``from … import time`` 等：优先于全局同名 ``classes['time']`` 构造。"""
    binding = tr._effective_import_bindings().get(name)
    if binding is None or binding.kind != 'function':
        return None
    func_def = tr._module_function_def_for_call(binding.module_path, binding.symbol, call=node)
    if func_def is None:
        return None
    from ..analysis.ir import FuncTypeParams
    func_ft = FuncTypeParams.collect(func_def)
    if func_ft.template_names or _template_deduction_param_indices(func_def, func_ft):
        return _emit_module_function_call(tr, binding.module_path, func_def, node)
    cpp = tr._module_function_cpp_name(binding.module_path, func_def)
    if '::' not in cpp and cpp not in PRIMITIVE_HEADER_MAP:
        ns = namespace_qualifier_for_module(binding.module_path)
        if ns:
            cpp = f'::{ns}::{cpp}'
    callee = tr._qualify_import_call(cpp, name, module_path=binding.module_path)
    if args:
        return f'{callee}({args})'
    return f'{callee}()'

def _try_emit_active_module_function_call(tr: Translator, name: str, node: ast.Call, args: str) -> str | None:
    """同模块 ``def``（含 ``@native`` + ``@native_name``）须先于 ``resolve_ctor_cpp_type``。"""
    mp = tr._active_module_path()
    if not mp:
        return None
    func_def = tr._module_function_def_for_call(mp, name, call=node)
    if func_def is None:
        return None
    from ..analysis.ir import FuncTypeParams
    func_ft = FuncTypeParams.collect(func_def)
    if func_ft.template_names or _template_deduction_param_indices(func_def, func_ft):
        return _emit_module_function_call(tr, mp, func_def, node)
    cpp = tr._module_function_cpp_name(mp, func_def)
    if '::' not in cpp and cpp not in PRIMITIVE_HEADER_MAP:
        ns = namespace_qualifier_for_module(mp)
        if ns:
            cpp = f'::{ns}::{cpp}'
    callee = tr._qualify_import_call(cpp, name, module_path=mp)
    if args:
        return f'{callee}({args})'
    return f'{callee}()'

def emit_call_expr(tr: Translator, node: ast.Call):
    from ..emit.builtin_call_emit import emit_abs_call, emit_cmp_call, emit_construct, emit_format_call, emit_instance_dunder_call, try_emit_builtin_dunder_forward, try_emit_global_builtin_call, try_emit_scandir_ctor_call, emit_json_class_api_call, emit_slice_call, emit_str_format_call, emit_user_ctor
    from ..emit.builtin_call_emit import is_json_class_ref
    from ..emit.loops_emit import emit_range_len_expr
    from .build_emit import try_emit_build_call
    from .builtin_aggregate_emit import try_emit_builtin_aggregate_call
    from .genexp_call_emit import try_emit_iterable_genexp_call
    from .selector_emit import try_emit_select_call
    if isinstance(node.func, ast.Name) and node.func.id == '__macro__':
        raise NotImplementedError('"NAME" in __macro__ 仅可用于 if/elif 条件（译为 #ifdef / #elif），不可作普通表达式')
    agg_expr = try_emit_builtin_aggregate_call(tr, node)
    if agg_expr is not None:
        return agg_expr
    genexp_expr = try_emit_iterable_genexp_call(tr, node)
    if genexp_expr is not None:
        return genexp_expr
    build_expr = try_emit_build_call(tr, node)
    if build_expr is not None:
        return build_expr
    select_expr = try_emit_select_call(tr, node)
    if select_expr is not None:
        return select_expr
    doc_load = try_emit_json_document_load_call(tr, node)
    if doc_load is not None:
        return doc_load
    from .enum_mro_emit import try_emit_enum_mro_static_call
    from .union_mro_emit import try_emit_union_mro_enum_call
    enum_mro = try_emit_enum_mro_static_call(tr, node)
    if enum_mro is not None:
        return enum_mro
    union_mro = try_emit_union_mro_enum_call(tr, node)
    if union_mro is not None:
        return union_mro
    scalar_static = try_emit_scalar_type_static_call(tr, node)
    if scalar_static is not None:
        return scalar_static
    class_sub_static = try_emit_class_subscript_static_call(tr, node)
    if class_sub_static is not None:
        return class_sub_static
    new_recv_static = try_emit_new_receiver_static_call(tr, node)
    if new_recv_static is not None:
        return new_recv_static
    templ_static = try_emit_templated_static_call(tr, node)
    if templ_static is not None:
        return templ_static
    templ_inst = try_emit_templated_instance_call(tr, node)
    if templ_inst is not None:
        return templ_inst
    match node.func:
        case ast.Subscript(value=ast.Attribute(value=ast.Name(id=cls), attr=attr), slice=sl) if is_json_class_ref(tr, cls) and attr in _JSON_API_METHODS_NEED_TYPE_ARG:
            elem_t = tr._parse_type_args(sl, tr._active_type_params())
            out = emit_json_class_api_call(tr, attr, elem_t, node)
            if out is not None:
                return out
        case ast.Subscript(value=ast.Name(id='result_done'), slice=sl):
            tparams = tr._active_type_params()
            if isinstance(sl, ast.Tuple) and len(sl.elts) >= 2:
                y = tr._parse_type(sl.elts[0], tparams)
                r = tr._parse_type(sl.elts[1], tparams)
                rt = cpp_result_type(y, r)
                return cpp_iter_result_return_expr(rt, f'{r}()')
            t = tr._parse_type_args(sl, tparams)
            rt = cpp_result_type(t)
            return cpp_iter_result_return_expr(rt, f'{t}()')
        case ast.Subscript(value=ast.Name(id=name), slice=sl):
            tparams = tr._active_type_params()
            imported_tpl = _try_emit_imported_templated_function_subscript_call(tr, name, sl, node)
            if imported_tpl is not None:
                return imported_tpl
            mod_tpl = _try_emit_module_templated_function_subscript_call(tr, name, sl, node)
            if mod_tpl is not None:
                return mod_tpl
            if name == 'list':
                elem_t = tr._parse_storage_type(sl, tparams)
            elif name == 'WeakRef':
                # 与字段 ``WeakRef[T]`` 存储一致：内层 ``T: refcount`` 用 unwrap，勿 ``PyWeakRef<T>``。
                wr_ann = ast.Subscript(
                    value=ast.Name(id='WeakRef', ctx=ast.Load()),
                    slice=sl,
                    ctx=ast.Load(),
                )
                full = tr._parse_storage_type(wr_ann, tparams)
                wr_base = cpp_ident('WeakRef')
                prefix = f'{wr_base}<'
                if full.startswith(prefix) and full.endswith('>'):
                    elem_t = full[len(prefix):-1]
                else:
                    elem_t = tr._parse_type_args(sl, tparams)
            else:
                elem_t = tr._parse_type_args(sl, tparams)
            if name in _DEDUCED_TEMPLATE_FUNCS:
                return _emit_deduced_template_call(tr, name, node)
            if name == 'input':
                return _emit_input_typed_call(tr, elem_t, node)
            if name == 'alloc':
                if node.args:
                    raise NotImplementedError('alloc[T]() 仅分配单个对象；数组请用 allocArray[T](count)')
                return f'alloc<{elem_t}>()'
            if name == 'cast':
                if not node.args:
                    raise NotImplementedError('cast[T](obj) 需要一个实参')
                return _emit_cast_call(tr, elem_t, node)
            if name == 'allocArray':
                count = tr.visit(node.args[0]) if node.args else '1'
                return f'allocArray<{elem_t}>({count})'
            if name == 'allocRawArray':
                count = tr.visit(node.args[0]) if node.args else '1'
                return f'allocRawArray<{elem_t}>({count})'
            base = cpp_ident(name)
            if base == 'PyList':
                if not node.args:
                    return f"{cpp_ident('list')}<{elem_t}>()"
                raise NotImplementedError('list[T](...) 仅支持 list[T]() 或 list[T](capacity)；元素请用 x: list[T] = [a,b,...] 或 x = [a,b,...]')
            args_t = elem_t
            if base in load_host_bound_iterator_view_cpp_bases():
                inner = tr._emit_list_iterator_ctor_inner(node)
            elif base == cpp_ident('ECSComponentTableQuery'):
                inner = tr._emit_ecs_query_ctor_inner(node)
            elif base == cpp_ident('deque'):
                if not node.args:
                    inner = ''
                elif len(node.args) == 1:
                    inner = tr._visit_value_expr(node.args[0])
                else:
                    raise NotImplementedError('deque[T](...) 仅支持 deque[T]() 或 deque[T](maxLen)；元素请用 []')
            else:
                inner = ', '.join((tr._visit_value_expr(a) for a in node.args))
            return emit_construct(tr, base, args_t, inner, name)
        case ast.Subscript(value=value, slice=sl):
            py_class = value.id if isinstance(value, ast.Name) else None
            base = cpp_ident(py_class) if py_class else tr.visit(value)
            args_t = tr._parse_type_args(sl, tr._active_type_params())
            if base in load_host_bound_iterator_view_cpp_bases():
                inner = tr._emit_list_iterator_ctor_inner(node)
            elif base == cpp_ident('ECSComponentTableQuery'):
                inner = tr._emit_ecs_query_ctor_inner(node)
            elif base == cpp_ident('deque'):
                if not node.args:
                    inner = ''
                elif len(node.args) == 1:
                    inner = tr._visit_value_expr(node.args[0])
                else:
                    raise NotImplementedError('deque[T](...) 仅支持 deque[T]() 或 deque[T](maxLen)；元素请用 []')
            else:
                inner = ', '.join((tr._visit_value_expr(a) for a in node.args))
            return emit_construct(tr, base, args_t, inner, py_class)
        case ast.Name(id=name):
            args = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
            if name == 'super':
                from .proxy_emit import try_emit_super_call_expr
                try_emit_super_call_expr(tr, node)
            if name == 'Self' and tr._self_type_class:
                if tr._self_type_class.name == 'str' and node.args:
                    inner = ', '.join((tr._cpp_str_ctor_arg(a) for a in node.args))
                    return emit_user_ctor(tr, tr._self_type_class.name, inner)
                return emit_user_ctor(tr, tr._self_type_class.name, args)
            if tr._self_type_class and name == tr._self_type_class.cpp_name():
                if tr._self_type_class.name == 'str' and node.args:
                    inner = ', '.join((tr._cpp_str_ctor_arg(a) for a in node.args))
                    return emit_user_ctor(tr, tr._self_type_class.name, inner)
                return emit_user_ctor(tr, tr._self_type_class.name, args)
            if name == 'cast':
                if not node.args:
                    raise NotImplementedError('cast(obj) 需要一个实参')
                ann = type_context_ann_from_stack(tr)
                if ann is None:
                    raise NotImplementedError('cast(obj) 需类型上下文：使用 x: T = cast(obj) 或 return cast(obj)')
                target_cpp = tr._parse_storage_type(ann, tr._active_type_params())
                return _emit_cast_call(tr, target_cpp, node)
            if name == 'new':
                raise NotImplementedError(
                    'new() 需类型上下文：有字段/返回注解时对目标写 ``… = new(...)`` / ``return new(...)``；'
                    '无法推断时写 ``Cls(...)``（勿仅为 ``new`` 造 ``x: T = new(...)`` 临时变量）'
                )
            if name in _DEDUCED_TEMPLATE_FUNCS:
                return _emit_deduced_template_call(tr, name, node)
            # 类/方法形参默认构造：``YieldValue()`` / ``T()``，勿走 ``cpp_ident`` → ``Py…``
            if name in tr._active_type_params():
                return f'{name}({args})'
            if name == 'len':
                arg = node.args[0]
                from ..analysis.type_emit import scope_binding_storage_cpp
                if isinstance(arg, ast.Name) and tr.scope and scope_binding_storage_cpp(tr.scope, arg.id) == 'utf8ptr':
                    return f'(int)strlen({arg.id})'
                from .variadic_template_emit import try_emit_variadic_pack_len
                vt_len = try_emit_variadic_pack_len(tr, arg)
                if vt_len is not None:
                    return vt_len
                from .enum_emit import try_emit_enum_len
                enum_len = try_emit_enum_len(tr, arg)
                if enum_len is not None:
                    return enum_len
                if tr._is_direct_range_call(arg):
                    return emit_range_len_expr(tr, arg)
                arg_t = tr._infer_expr_cpp_type(arg)
                if is_array_type(arg_t):
                    arr_nd = cpp_array_ndim(arg_t)
                    if arr_nd in (2, 3):
                        raise NotImplementedError('len() 不支持 2D/3D 堆数组')
                if is_stack_array_type(arg_t):
                    stack_nd = cpp_stack_array_ndim(arg_t)
                    if stack_nd in (2, 3):
                        raise NotImplementedError('len() 不支持 2D/3D 栈数组')
                stack_n = cpp_stack_array_size(arg_t)
                if stack_n is not None:
                    return str(stack_n)
                if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
                    if arg.value.id == 'self' and tr.class_info:
                        ft = field_storage_cpp(tr.class_info, arg.attr)
                        if is_array_type(ft):
                            arr_nd = cpp_array_ndim(ft)
                            if arr_nd in (2, 3):
                                raise NotImplementedError('len() 不支持 2D/3D 堆数组')
                        if is_stack_array_type(ft):
                            stack_nd = cpp_stack_array_ndim(ft)
                            if stack_nd in (2, 3):
                                raise NotImplementedError('len() 不支持 2D/3D 栈数组')
                        stack_n = cpp_stack_array_size(ft)
                        if stack_n is not None:
                            return str(stack_n)
                len_fwd = builtin_dunder_forward('len')
                if len_fwd is not None:
                    return emit_instance_dunder_call(tr, len_fwd.dunder, arg)
                return emit_instance_dunder_call(tr, '__len__', arg)
            if name == 'abs' and len(node.args) == 1:
                return emit_abs_call(tr, node.args[0])
            if name == '__cmp__' and len(node.args) == 2:
                return emit_cmp_call(tr, node.args[0], node.args[1])
            if name == 'format':
                if len(node.args) == 1:
                    return emit_format_call(tr, tr._visit_value_expr(node.args[0]))
                if len(node.args) == 2:
                    return emit_format_call(tr, tr._visit_value_expr(node.args[0]), node.args[1])
                raise NotImplementedError('format() 仅支持 1～2 个位置参数')
            if name == 'print':
                return ''
            if name not in BUILTIN_EMIT_SPECIAL:
                dunder_expr = try_emit_builtin_dunder_forward(tr, name, node)
                if dunder_expr is not None:
                    return dunder_expr
            if name == 'chr' and len(node.args) == 1:
                arg_node = node.args[0]
                if isinstance(arg_node, ast.Constant) and isinstance(arg_node.value, int):
                    return str_cpp_from_literal(chr(arg_node.value))
                return f'::chr({tr._visit_value_expr(arg_node)})'
            if name == 'ord' and len(node.args) == 1:
                arg_node = node.args[0]
                if isinstance(arg_node, ast.Constant) and isinstance(arg_node.value, str) and (len(arg_node.value) == 1):
                    return f'PyChar({ord(arg_node.value)})'
                raise NotImplementedError('ord() 仅支持单字符 str 字面量')
            if name == 'repr' and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Name) and arg.id == 'self':
                    return 'this->__repr__()'
                from .union_mro_emit import try_emit_union_mro_enum_member
                umem = try_emit_union_mro_enum_member(tr, arg) if isinstance(arg, ast.Attribute) else None
                if umem is not None:
                    return f'repr({umem})'
                arg_expr = tr.visit(arg)
                einfo = tr._class_info_for_expr(arg) or tr._class_info_for_type(tr._infer_expr_cpp_type(arg))
                if einfo and einfo.is_enum:
                    return f'repr({arg_expr})'
                return f'::repr({arg_expr})'
            scandir_expr = try_emit_scandir_ctor_call(tr, name, node)
            if scandir_expr is not None:
                return scandir_expr
            global_expr = try_emit_global_builtin_call(tr, name, node)
            if global_expr is not None:
                return global_expr
            if name == 'slice':
                return emit_slice_call(tr, node)
            if name == 'getattr' and len(node.args) == 2:
                field = static_field_name(node.args[1])
                if field is not None:
                    return tr._emit_static_field_read(node.args[0], field)
                raise NotImplementedError('getattr 仅支持编译期已知字段名（字面量或 str 常量）')
            if name == 'setattr' and len(node.args) == 3:
                field = static_field_name(node.args[1])
                if field is not None:
                    val = tr._visit_value_expr(node.args[2])
                    recv = node.args[0]
                    if isinstance(recv, ast.Name) and recv.id == 'self':
                        return f'(this->{field} = {val})'
                    r, sep = tr._receiver_access(recv)
                    return f'({r}{sep}{field} = {val})'
                raise NotImplementedError('setattr 仅支持编译期已知字段名（字面量或 str 常量）')
            mod_fn = _try_emit_active_module_function_call(tr, name, node, args)
            if mod_fn is not None:
                return mod_fn
            mod_fn = _try_emit_imported_function_call(tr, name, node, args)
            if mod_fn is not None:
                return mod_fn
            ctor_cpp = resolve_ctor_cpp_type(tr, name)
            if ctor_cpp == cpp_ident('str'):
                ps = cpp_ident('str')
                if len(node.args) == 1:
                    arg = node.args[0]
                    einfo = tr._class_info_for_expr(arg) or tr._class_info_for_type(tr._infer_expr_cpp_type(arg))
                    if einfo and einfo.is_enum:
                        from .enum_emit import enum_pystr_cast_expr
                        return enum_pystr_cast_expr(tr, einfo, tr.visit(arg))
                    inner = tr._cpp_str_ctor_arg(arg)
                    if inner.startswith(f'static_cast<{ps}>'):
                        return inner
                    return f'{ps}({inner})'
                inner = ', '.join((tr._cpp_str_ctor_arg(a) for a in node.args))
                return f'{ps}({inner})'
            if ctor_cpp == cpp_ident('bytes') and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, bytes):
                    return bytes_cpp_from_literal(arg.value)
            if ctor_cpp == cpp_ident('int') and len(node.args) == 1:
                cast_expr = try_emit_int_ctor(tr, node)
                if cast_expr is not None:
                    return cast_expr
            if ctor_cpp == cpp_ident('float') and len(node.args) == 1:
                cast_expr = try_emit_float_ctor(tr, node)
                if cast_expr is not None:
                    return cast_expr
            numeric_ctor = try_emit_numeric_ctor(tr, name, node)
            if numeric_ctor is not None:
                return numeric_ctor
            primitive_ctor = try_emit_primitive_ctor(tr, name, node)
            if primitive_ctor is not None:
                return primitive_ctor
            from .enum_emit import try_emit_enum_ctor
            enum_ctor = try_emit_enum_ctor(tr, node)
            if enum_ctor is not None:
                return enum_ctor
            if name in tr.classes:
                info = tr.classes[name]
                ctor_param_types = tr._ordered_method_param_cpp_types(
                    info, "__init__", call=node,
                )
                if not ctor_param_types and node.args:
                    host_storage = field_storage_cpp(info, "g_self", fallback="")
                    if host_storage:
                        ctor_param_types = [host_storage]
                ctor_args = (
                    emit_call_args(tr, node, param_cpp_types=ctor_param_types)
                    if ctor_param_types else args
                )
                return emit_user_ctor(tr, name, ctor_args)
            if ctor_cpp is not None:
                return f'{ctor_cpp}({args})'
            if name == 'range':
                return runtime_make_range_expr(args)
            bound = binding_cpp_name(tr._effective_import_bindings(), name)
            if bound is not None:
                binding = tr._effective_import_bindings().get(name)
                cpp = bound
                if binding and '::' not in cpp and binding.module_path and (cpp not in PRIMITIVE_HEADER_MAP):
                    ns = namespace_qualifier_for_module(binding.module_path)
                    if ns:
                        cpp = f'::{ns}::{cpp}'
                callee = tr._qualify_import_call(cpp, name, module_path=binding.module_path if binding else None)
                return f'{callee}({args})'
            import_callee = tr._import_attr_chain_cpp(node.func)
            if import_callee is not None:
                arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
                if arg_str:
                    return f'{import_callee}({arg_str})'
                return f'{import_callee}()'
            mod_fn = _try_emit_active_module_function_call(tr, name, node, args)
            if mod_fn is not None:
                return mod_fn
            # 导入绑定缺失时仍按 ``@global_call``/``@native_name`` 解析（如模块常量 emit）
            hit = tr._module_function_info_for_name(name)
            if hit is not None:
                mp, func_def = hit
                from ..analysis.ir import FuncTypeParams
                func_ft = FuncTypeParams.collect(func_def)
                if func_ft.template_names or _template_deduction_param_indices(func_def, func_ft):
                    return _emit_module_function_call(tr, mp, func_def, node)
                cpp = tr._module_function_cpp_name(mp, func_def)
                if '::' not in cpp and cpp not in PRIMITIVE_HEADER_MAP:
                    ns = namespace_qualifier_for_module(mp)
                    if ns:
                        cpp = f'::{ns}::{cpp}'
                callee = tr._qualify_import_call(cpp, name, module_path=mp)
                if args:
                    return f'{callee}({args})'
                return f'{callee}()'
            return f'{name}({args})'
        case ast.Attribute(value=ast.Name(id=recv), attr=attr) if tr._recv_is_host_class(recv):
            if recv == 'Self':
                info = tr._class_info_for_receiver(node.func.value)
            else:
                static_host = tr._static_generator_host_class_info()
                if static_host is not None and recv in (static_host.cpp_name(), static_host.name):
                    info = static_host
                else:
                    info = tr._generator_host_class_info() or tr._active_class_info()
            if info is not None:
                ref = tr._class_static_member_ref(info, attr)
                if ref is not None:
                    if info.is_union and attr in union_variant_names(info):
                        variant = next((v for v in info.union_variants if v.name == attr))
                        arg_str = emit_call_args(tr, node, param_cpp_types=union_variant_param_cpp_types(info, attr), param_names=list(variant.fields))
                    else:
                        arg_str = emit_call_args(tr, node, param_cpp_types=tr._ordered_method_param_cpp_types(info, attr))
                    if arg_str:
                        return f'{ref}({arg_str})'
                    return f'{ref}()'
                _raise_if_non_invokable_class_member(tr, info, recv, attr)
                invokable = _emit_class_invokable_member_call(tr, info, attr, node)
                if invokable is not None:
                    return invokable
        case ast.Attribute(value=ast.Subscript(value=ast.Name(id=cls), slice=sl), attr=attr) if cls != 'self' and tr._name_refers_to_class(cls):
            info = tr._class_info_for_ref(cls)
            if info is not None and info.is_variant_mixin:
                raise NotImplementedError(f'{cls} 为 @variant 字段模板，不可 {cls}.{attr}(...) 构造')
            if info is not None and info.is_union and (attr in union_variant_names(info)):
                out = tr._emit_union_variant_ctor(cls, attr, node, context_cpp=None, type_args_slice=sl)
                if out is not None:
                    return out
        case ast.Attribute(value=ast.Name(id=tp), attr=attr) if tp in tr._active_type_params():
            tp_cpp = tp  # 形参别名（``using YieldValue = _YieldValue``），勿加 ``Py``
            mcpp = tr._attr_cpp_name(ast.Name(id=tp), attr)
            arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
            if arg_str:
                return f'{tp_cpp}::{mcpp}({arg_str})'
            return f'{tp_cpp}::{mcpp}()'
        case ast.Attribute(value=ast.Name(id=cls), attr=attr) if cls != 'self' and (not (cls == 'Self' and tr._active_class_info())) and tr._name_refers_to_class(cls):
            info = tr._class_info_for_ref(cls)
            if info is not None and info.is_variant_mixin:
                raise NotImplementedError(f'{cls} 为 @variant 字段模板，不可 {cls}.{attr}(...) 构造')
            if info is not None and info.is_union and (attr in union_variant_names(info)):
                out = tr._emit_union_variant_ctor(cls, attr, node, context_cpp=None)
                if out is not None:
                    return out
            if info is not None:
                if not _is_static_method(info, attr):
                    _raise_if_non_invokable_class_member(tr, info, cls, attr)
                    invokable = _emit_class_invokable_member_call(tr, info, attr, node)
                    if invokable is not None:
                        return invokable
            cls_cpp = resolve_class_ref_cpp(tr, cls)
            if info is not None:
                ov_sigs = info.method_overload_sigs.get(attr)
                sig = info.method_sigs.get(attr)
                is_static = sig is not None and sig.is_static or (ov_sigs is not None and ov_sigs[0].is_static)
                if is_static and (sig is not None or ov_sigs is not None):
                    mcpp = info.cpp_member_name(attr)
                    if info.name == 'dict' and attr == 'fromKeys' and (len(node.args) >= 2):
                        keys_t = tr._infer_expr_cpp_type(node.args[0])
                        val_t = tr._infer_expr_cpp_type(node.args[1])
                        k_t = list_elem_type(keys_t) or cpp_ident('int')
                        v_t = val_t or cpp_ident('int')
                        callee = f"{cpp_template_type('dict', f'{k_t}, {v_t}')}::{mcpp}"
                        arg_str = emit_call_args(tr, node, param_cpp_types=tr._ordered_method_param_cpp_types(info, attr))
                    else:
                        from ..analysis.ir import qualified_class_static_callee
                        arg_t = tr._infer_expr_cpp_type(node.args[0]) if node.args else None
                        run_thread_ret: str | None = None
                        if (
                            info.name == 'Task'
                            and info.module_path.endswith('concur/task')
                            and attr == 'runThread'
                            and node.args
                        ):
                            run_thread_ret = _callable_return_type_from_expr(tr, node.args[0])
                        if run_thread_ret:
                            base = qualify_symbol_in_module(info.module_path, info.cpp_name())
                            callee = f'{base}<{run_thread_ret}>::{mcpp}'
                            tpl = ''
                        else:
                            callee = qualified_class_static_callee(info, mcpp, arg_cpp_type=arg_t)
                            tpl = _static_method_template_angle(tr, info, attr, node)
                        if tpl:
                            callee = f'{callee}{tpl}'
                        if attr == 'create' and node.args and _concrete_coroutine_cpp_type(tr, node.args[0]):
                            arg_str = tr._visit_value_expr(node.args[0])
                        elif attr == 'create' and node.args:
                            arg_str = _emit_make_coroutine_from_arg(tr, node.args[0])
                        elif attr == 'gather' and tpl and node.args:
                            elem = tpl.strip('<>')
                            arg_str = _emit_task_gather_pack(tr, info, node, elem)
                        elif run_thread_ret and node.args:
                            arg_str = emit_call_args(tr, node, param_cpp_types=[f'PyCallable<{run_thread_ret}>'])
                        else:
                            arg_str = emit_call_args(tr, node, param_cpp_types=tr._ordered_method_param_cpp_types(info, attr))
                    if arg_str:
                        return f'{callee}({arg_str})'
                    return f'{callee}()'
            recv = tr.visit(ast.Name(id=cls))
            sep = tr._member_access(recv)
            mcpp = tr._attr_cpp_name(ast.Name(id=cls), attr)
            arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
            if arg_str:
                return f'{recv}{sep}{mcpp}({arg_str})'
            return f'{recv}{sep}{mcpp}()'
        case ast.Attribute() as attr_node:
            import_callee = tr._import_attr_chain_cpp(attr_node)
            if import_callee is not None:
                arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
                if arg_str:
                    return f'{import_callee}({arg_str})'
                return f'{import_callee}()'
            val = attr_node.value
            attr = attr_node.attr
            from .proxy_emit import try_emit_super_method_call_from_receiver
            out = try_emit_super_method_call_from_receiver(tr, val, attr, node)
            if out is not None:
                return out
            from .proxy_emit import try_proxy_peel_method_call
            peeled = try_proxy_peel_method_call(tr, val, attr, node)
            if peeled is not None:
                return peeled
            info = tr._class_info_for_receiver(val)
            if info is not None and (not _is_instance_method(info, attr)) and (not _is_static_method(info, attr)):
                if attr in info.properties or attr in info.field_properties or attr in info.fields:
                    _raise_if_non_invokable_instance_property(tr, info, val, attr)
                    invokable = _emit_instance_invokable_member_call(tr, val, attr, node)
                    if invokable is not None:
                        return invokable
            if isinstance(val, ast.Dict) and attr == 'get' and (len(node.args) == 2):
                return try_emit_dict_literal_get(tr, val, node.args[0], node.args[1])
            if isinstance(val, ast.Constant) and isinstance(val.value, str) and (attr in ('find', 'index', 'rfind', 'rindex')):
                return try_emit_str_literal_find_call(tr, val.value, attr, node)
            if isinstance(val, ast.Constant) and isinstance(val.value, str) and attr == 'stripLines':
                inline = try_emit_str_literal_stripLines_call(val.value, node)
                if inline is not None:
                    return inline
            if attr == '__getitem__' and len(node.args) == 1:
                const_get = tr._try_pytuple_const_subscript(val, node.args[0])
                if const_get is not None:
                    return const_get
            if attr == 'format':
                if isinstance(val, ast.Name) and resolve_class_ref_cpp(tr, val.id) == cpp_ident('str'):
                    return emit_str_format_call(tr, node)
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    return emit_format_expr(tr, plan_format_literal(tr, val.value, list(node.args)))
            arg_str = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
            if tr._use_member_dispatch_macro(val):
                mcpp = tr._attr_cpp_name(val, attr)
                if attr in ('assertTrue', 'assertFalse') and len(node.args) == 1:
                    arg = node.args[0]
                    if tr._expr_is_str_value(arg):
                        a0 = tr._emit_str_bool(arg)
                    else:
                        a0 = tr._truthiness_condition(arg)
                    return tr._cpp_call_expr(val, mcpp, a0, site=node, arg_count=1)
                if attr == 'assertEqual' and len(node.args) == 2:
                    return tr._cpp_call_expr(val, mcpp, emit_assert_equal_args(tr, node), site=node, arg_count=2)
                if arg_str:
                    return tr._cpp_call_expr(val, mcpp, arg_str, site=node)
                return tr._cpp_call_expr(val, mcpp, site=node)
            recv = tr._paren_expr(tr.visit(val))
            sep = tr._member_access_sep(val, recv)
            if sep == '.' and isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and (val.value.id == 'self') and tr.class_info:
                ft = field_storage_cpp(tr.class_info, val.attr)
                if ft.rstrip().endswith('*'):
                    sep = '->'
            mcpp = tr._attr_cpp_name(val, attr)
            if attr == 'assertEqual' and len(node.args) == 2:
                return f'{recv}{sep}{mcpp}({emit_assert_equal_args(tr, node)})'
            if attr in ('assertTrue', 'assertFalse') and len(node.args) == 1:
                arg = node.args[0]
                if tr._expr_is_str_value(arg):
                    a0 = tr._emit_str_bool(arg)
                else:
                    a0 = tr._truthiness_condition(arg)
                return f'{recv}{sep}{mcpp}({a0})'
            if arg_str:
                return f'{recv}{sep}{mcpp}({arg_str})'
            return f'{recv}{sep}{mcpp}()'
        case _:
            return f'{tr.visit(node.func)}({emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))})'
