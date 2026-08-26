"""容器/数组字面量与 new() 构造 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
from collections.abc import Callable
from typing import TYPE_CHECKING
from ..constant.stdlib_layout import RUNTIME_PKG
from ..analysis.type_emit import field_storage_cpp, scope_storage_cpp, bind_scope_var
from ..analysis.module_namespace import qualify_symbol_in_module
from ..analysis.type_pred import is_array_type, is_byte_heap_array_type, is_char_heap_array_type, is_char_stack_array_type, is_dict_type, is_frozenlist_type, is_frozendict_type, is_frozenset_type, is_bytes_type, is_deque_type, is_list_type, is_set_type, is_stack_array_type, is_str_type
from ..analysis.type_extract import deque_elem_type, dict_type_args, frozenlist_elem_type, frozendict_type_args, frozenset_elem_type, list_elem_type, set_elem_type
from ..analysis.ir import ClassInfo, class_info_for_cpp_type, default_new_ctor_cpp, cpp_array_ndim, cpp_ident, cpp_param, cpp_stack_array_offset, cpp_stack_array_size, cpp_stack_array_ndim, cpp_stack_array_var_decl, parse_cpp_stack_array2d_type, parse_cpp_stack_array3d_type, cpp_template_type, strip_cpp_type_qualifiers
from .builtin_call_emit import emit_construct
from .comprehensions_emit import emit_dict_comprehension, emit_dict_literal, emit_frozenlist_comprehension, emit_frozenlist_literal, emit_frozendict_comprehension, emit_frozenset_comprehension, emit_frozenset_literal, emit_frozendict_literal, emit_list_comprehension, emit_sequence_literal, emit_set_comprehension, emit_set_literal
from ..analysis.stubs.class_stubs import load_host_bound_iterator_view_cpp_bases
if TYPE_CHECKING:
    from ..translator import Translator

def _emit_new_ctor_arg_expr(tr: 'Translator', expr: ast.expr, param_cpp_type: str = '') -> str:
    """``new(self)`` 按目标形参传引用或指针。"""
    pt = param_cpp_type.strip()
    if isinstance(expr, ast.Name) and expr.id == 'self' and pt.endswith('&') and (not pt.endswith('&&')):
        return '*this'
    if isinstance(expr, ast.Name) and expr.id == 'self' and pt.endswith('*'):
        return 'this'
    if pt:
        return tr._visit_value_for_type(expr, pt)
    return tr._visit_value_expr(expr)

def _emit_new_iterator_view_ctor(tr: 'Translator', cpp_type: str, call: ast.Call) -> str | None:
    bare = strip_cpp_type_qualifiers(cpp_type).strip()
    for base in load_host_bound_iterator_view_cpp_bases():
        if bare.startswith(f'{base}<') or bare == base:
            inner = tr._emit_list_iterator_ctor_inner(call)
            info = class_info_for_cpp_type(cpp_type, tr.classes)
            cpp_emit = tr._rewrite_template_args_to_cpp_params(cpp_type, info) if info is not None and info.is_template() else cpp_type
            return f'{cpp_emit}({inner})'
    return None

def _frozendict_new_from_arg_expr(tr: 'Translator', inner: str, arg: ast.expr) -> str:
    spec = cpp_template_type('frozendict', inner)
    arg_cpp = tr._visit_value_expr(arg)
    arg_t = tr._infer_expr_cpp_type(arg)
    if is_dict_type(arg_t):
        init = f'out.initFromDict({arg_cpp})'
    elif is_frozendict_type(arg_t):
        init = f'out.initFromFrozendict({arg_cpp})'
    else:
        raise NotImplementedError('frozendict new(mapping) 仅支持 dict、frozendict 实参（需可推断类型）')
    return f'[&]() {{ {spec} out; {init}; return out; }}()'

def _mark_scope_variable(tr: 'Translator', name: str) -> None:
    from ..translator import NameContext
    tr.scope.vars[name] = NameContext.Variable

def _emit_same_class_ctor(tr: 'Translator', cpp_type: str, args: str, *, str_inner: str='') -> str:
    """同类 ``new`` / ``Self()`` → 全名 C++ 构造（C++ 无 ``Self`` 类型别名）。"""
    from .builtin_call_emit import emit_user_ctor
    info = tr.class_info or tr._self_type_class
    if info is not None:
        bare = cpp_type.strip()
        if bare.startswith('const '):
            bare = bare[6:].strip()
        base = info.cpp_name()
        if bare == base or bare.startswith(f'{base}<'):
            if info.module_path != RUNTIME_PKG and tr._is_stdlib_module(info.module_path):
                q_base, _, tail = bare.partition('<')
                q = qualify_symbol_in_module(info.module_path, q_base)
                cpp = f'{q}<{tail}' if tail else q
            else:
                cpp = bare
            if info.is_template():
                cpp = tr._rewrite_template_args_to_cpp_params(cpp, info)
            return f'{cpp}({args})' if args else f'{cpp}()'
    if info is None:
        if cpp_type.strip() == cpp_ident('str'):
            inner = str_inner if str_inner else args
            return f"{cpp_ident('str')}({inner})" if inner else f"{cpp_ident('str')}()"
        return f'{cpp_type}({args})' if args else f'{cpp_type}()'
    if info.name == 'str':
        inner = str_inner if str_inner else args
        return emit_user_ctor(tr, info.name, inner)
    return emit_user_ctor(tr, info.name, args)

def new_call_default_ctor_cpp(call: ast.Call, cpp_type: str, *, classes: dict[str, ClassInfo], emit_default_arg: Callable[[ast.expr, str | None], str], parse_param_type: Callable[[ast.arg], str | None] | None=None) -> str:
    """``new(...)`` 作 C++ 默认实参：无参/有参/关键字对齐目标 ``__init__`` 形参表。"""
    ctor_t = strip_cpp_type_qualifiers(cpp_type)
    if not call.args and (not call.keywords):
        return default_new_ctor_cpp(cpp_type)
    info = class_info_for_cpp_type(cpp_type, classes)
    if info is not None and info.inits:
        from ..passes.kwargs_options import new_ctor_arg_exprs_from_init
        init = info.inits[0]
        params = list(init.args.args)
        if params and params[0].arg == 'self':
            params = params[1:]
        resolved = new_ctor_arg_exprs_from_init(call, init)
        parts: list[str] = []
        for param, expr in zip(params, resolved):
            pt = parse_param_type(param) if parse_param_type is not None else None
            parts.append(emit_default_arg(expr, pt))
        inner = ', '.join(parts)
        return f'{ctor_t}({inner})' if inner else f'{ctor_t}()'
    if call.keywords:
        raise NotImplementedError('new(kw=…) 默认实参须能解析目标类 __init__（注解为该类且已 expand_dataclass）')
    args = ', '.join((emit_default_arg(a, None) for a in call.args))
    return f'{ctor_t}({args})' if args else f'{ctor_t}()'

def _emit_boxing_new_ctor(tr: 'Translator', cpp_type: str, call: ast.Call) -> str | None:
    """``node: BoxingNode[T] = new()`` → ``new BoxingNode<T>(...)``。"""
    from ..analysis.ir import class_info_for_cpp_type, strip_cpp_ref
    t = strip_cpp_ref(cpp_type.strip())
    if t.endswith('*'):
        t = t[:-1].strip()
    info = class_info_for_cpp_type(t, tr.classes)
    if info is None or not info.is_boxing:
        return None
    inner = ', '.join((tr._visit_value_expr(a) for a in call.args))
    args_t = ', '.join(info.type_params) if info.type_params else ''
    return emit_construct(tr, info.cpp_name(), args_t, inner, info.name)

def _ctor_init_for_call(tr: 'Translator', info: ClassInfo, call: ast.Call) -> ast.FunctionDef | None:
    if info.method_overloads.get('__init__'):
        picked = tr._method_def_for_call(info, '__init__', call)
        if picked is not None:
            return picked
    if info.inits:
        return info.inits[0]
    return None

def _init_param_cpp_type(tr: 'Translator', info: ClassInfo, init: ast.FunctionDef, param: ast.arg) -> str:
    sig = info.method_sig_for(init)
    if sig is not None:
        from ..analysis.type_emit import method_param_storage_cpp
        pt = method_param_storage_cpp(sig, param.arg, fallback='')
        if pt:
            return pt
    if param.annotation is not None:
        tparams = list(info.type_params) if info.type_params else tr._active_type_params()
        self_class = info.template_cpp_type() if info.is_template() else info.cpp_name()
        return tr.type_parser.parse_storage_type(
            param.annotation,
            tparams,
            self_class=self_class,
        )
    return ''

def _new_ctor_emit_params(tr: 'Translator', info: ClassInfo, init: ast.FunctionDef, call: ast.Call) -> tuple[list[ast.arg], list[ast.expr]]:
    params = [a for a in init.args.args if a.arg not in ('self', 'cls')]
    if call.keywords:
        from ..passes.kwargs_options import new_ctor_arg_exprs_from_init
        return params, list(new_ctor_arg_exprs_from_init(call, init))
    return params[:len(call.args)], list(call.args)

def new_ctor_param_cpp_types(tr: 'Translator', cpp_type: str, call: ast.Call) -> list[str] | None:
    """``new(...)`` 在已知目标 C++ 类型时的形参类型表（与 ``_emit_new_class_ctor_expr`` 对齐）。"""
    info = class_info_for_cpp_type(cpp_type, tr.classes)
    if info is None or not info.inits:
        return None
    init = _ctor_init_for_call(tr, info, call)
    if init is None:
        return None
    emit_params, _ = _new_ctor_emit_params(tr, info, init, call)
    return [_init_param_cpp_type(tr, info, init, param) for param in emit_params]

def _emit_new_class_ctor_expr(tr: 'Translator', cpp_type: str, call: ast.Call) -> str | None:
    info = class_info_for_cpp_type(cpp_type, tr.classes)
    if info is None or not info.inits:
        return None
    init = _ctor_init_for_call(tr, info, call)
    if init is None:
        return None
    emit_params, exprs = _new_ctor_emit_params(tr, info, init, call)
    parts: list[str] = []
    for i, expr in enumerate(exprs):
        pt = ''
        if i < len(emit_params):
            pt = _init_param_cpp_type(tr, info, init, emit_params[i])
        parts.append(_emit_new_ctor_arg_expr(tr, expr, pt))
    args = ', '.join(parts)
    # A rewritten class template parameter is only valid while emitting that
    # class's own out-of-line member. Other generic constructors retain the
    # active function type parameter unchanged.
    cpp_emit = (
        tr._rewrite_template_args_to_cpp_params(cpp_type, info)
        if info.is_template() and tr._is_self_class_cpp_type(cpp_type)
        else cpp_type
    )
    return f'{cpp_emit}({args})' if args else f'{cpp_emit}()'

def _emit_new_ctor_expr(tr: 'Translator', cpp_type: str, call: ast.Call) -> str:
    """``new(args...)`` + 已知 C++ 类型 → ``Type(args...)``；与所在类相同时 → ``Self(...)``。"""
    from ..passes.new_type_args import validate_new_call_args
    validate_new_call_args(tr, call)
    # ``Optional[T]`` 字段上的 ``new(...)`` 构造内层 ``T``，赋值时再 ``Some`` 装箱
    from ..analysis.type_extract import optional_inner_type
    opt_inner = optional_inner_type(cpp_type.strip(), classes=tr.classes)
    if opt_inner is not None:
        return _emit_new_ctor_expr(tr, opt_inner, call)
    iter_ctor = _emit_new_iterator_view_ctor(tr, cpp_type, call)
    if iter_ctor is not None:
        return iter_ctor
    from ..analysis.type_extract import refcount_inner_type
    from ..analysis.type_pred import is_refcount_type
    rc_inner = refcount_inner_type(cpp_type.strip(), classes=tr.classes)
    if rc_inner is not None and is_refcount_type(cpp_type.strip(), classes=tr.classes):
        if not call.args and (not call.keywords):
            return f'makeRefCount<{rc_inner}>()'
        args = ', '.join((tr._visit_value_expr(a) for a in call.args))
        return f'makeRefCount<{rc_inner}>({args})'
    boxing_ctor = _emit_boxing_new_ctor(tr, cpp_type, call)
    if boxing_ctor is not None:
        return boxing_ctor
    bare = cpp_type.strip()
    if bare.startswith(f"{cpp_ident('ECSComponentTableQuery')}<") and call.args:
        inner = tr._emit_ecs_query_ctor_inner(call)
        return f'{bare}({inner})'
    class_ctor = _emit_new_class_ctor_expr(tr, cpp_type, call)
    if class_ctor is not None:
        return class_ctor
    if tr._is_self_class_cpp_type(cpp_type):
        args = ', '.join((tr._visit_value_expr(a) for a in call.args))
        if cpp_type.strip() == cpp_ident('str'):
            inner = ', '.join((tr._cpp_str_ctor_arg(a) for a in call.args))
            return _emit_same_class_ctor(tr, cpp_type, args, str_inner=inner)
        return _emit_same_class_ctor(tr, cpp_type, args)
    elem_t = list_elem_type(cpp_type)
    if elem_t is not None:
        spec = f"{cpp_ident('list')}<{elem_t}>"
        if not call.args:
            return f'{spec}()'
        if len(call.args) == 1:
            return f'{spec}()'
        raise NotImplementedError('list new() 仅支持 new() 或配合 _reserve；元素请用 []')
    elem_t = deque_elem_type(cpp_type)
    if elem_t is not None:
        if not call.args:
            raise NotImplementedError('deque 空表请用 []（如 q: deque[T] = []）；有界队列用 new(maxlen)，元素仍用 []')
        if len(call.args) == 1 and (not call.keywords):
            maxlen = tr._visit_value_expr(call.args[0])
            return f"{cpp_ident('deque')}<{elem_t}>({maxlen})"
        raise NotImplementedError('deque new() 仅支持 new(maxlen)；空表与元素请用 []')
    if is_dict_type(cpp_type):
        inner = dict_type_args(cpp_type) or ''
        if call.args:
            raise NotImplementedError('dict new() 仅支持无参 new()')
        return f"{cpp_template_type('dict', inner)}()"
    elem_t = set_elem_type(cpp_type)
    if elem_t is not None:
        if call.args:
            raise NotImplementedError('set new() 仅支持无参 new()')
        return f"{cpp_template_type('set', elem_t)}()"
    elem_t = frozenset_elem_type(cpp_type)
    if elem_t is not None:
        if call.args:
            raise NotImplementedError('frozenset new() 仅支持无参 new()')
        return f"{cpp_template_type('frozenset', elem_t)}()"
    elem_t = frozenlist_elem_type(cpp_type)
    if elem_t is not None:
        if call.args:
            raise NotImplementedError('frozenlist new() 仅支持无参 new()')
        return f"{cpp_template_type('frozenlist', elem_t)}()"
    fd_inner = frozendict_type_args(cpp_type)
    if fd_inner is not None:
        if not call.args:
            return f"{cpp_template_type('frozendict', fd_inner)}()"
        if len(call.args) == 1 and (not call.keywords):
            return _frozendict_new_from_arg_expr(tr, fd_inner, call.args[0])
        raise NotImplementedError('frozendict new() 仅支持 new()、new(dict) 或 new(frozendict)')
    if is_stack_array_type(cpp_type):
        if call.args:
            raise NotImplementedError('T[:N] 栈定长数组不支持 new(大小)；请写 ``buf: T[:N]`` 或 ``new()``')
        return f'{cpp_type}()'
    if cpp_type.strip() == cpp_ident('str'):
        inner = ', '.join((tr._cpp_str_ctor_arg(a) for a in call.args))
        return f"{cpp_ident('str')}({inner})" if inner else f"{cpp_ident('str')}()"
    args = ', '.join((tr._visit_value_expr(a) for a in call.args))
    return f'{cpp_type}({args})' if args else f'{cpp_type}()'

def _try_emit_new_ann_assign(tr: 'Translator', node: ast.AnnAssign) -> bool:
    from .call_emit import is_new_receiver_attr_call, specialize_typed_storage_from_rhs_call
    if not node.annotation or not (tr._is_new_call(node.value) or is_new_receiver_attr_call(node.value)):
        return False
    tparams = tr._active_type_params()
    call = node.value
    match node.target:
        case ast.Name(id=name):
            # ``new.factory(...)`` 可由实参收窄左侧默认模板实参，例如
            # ``x: NormalDist = new.fromSamples(list[float64])``。
            if is_new_receiver_attr_call(call):
                t = tr._parse_storage_type(node.annotation, tparams)
                if isinstance(node.annotation, ast.Name):
                    t = specialize_typed_storage_from_rhs_call(tr, t, call)
                val = tr.visit(call)
                pname = cpp_param(name)
                if tr._try_declare(name):
                    if tr.scope:
                        bind_scope_var(tr.scope, name, t, classes=tr.classes)
                    tr.write_line(f'{t} {pname} = {val};')
                else:
                    tr.write_line(f'{pname} = {val};')
                return True
            appendable = tr._appendable_init_from_ann(node.annotation)
            if appendable is not None:
                container, elem_t = appendable
                if container == 'list' and (not call.args):
                    _declare_appendable_var(tr, container, name, elem_t, declare=tr._try_declare(name))
                    return True
                if container == 'list' and len(call.args) == 1:
                    decl = tr._try_declare(name)
                    _declare_appendable_var(tr, container, name, elem_t, declare=decl)
                    tr.write_line(f'{cpp_param(name)}._reserve({tr.visit(call.args[0])});')
                    return True
                if container == 'deque' and (not call.args):
                    _declare_appendable_var(tr, container, name, elem_t, declare=tr._try_declare(name))
                    return True
                if container == 'deque' and len(call.args) == 1:
                    decl = tr._try_declare(name)
                    if decl:
                        tr.write_line(f"{cpp_template_type('deque', elem_t)} {cpp_param(name)}({tr.visit(call.args[0])});")
                    else:
                        tr.write_line(f"{cpp_param(name)} = {cpp_template_type('deque', elem_t)}({tr.visit(call.args[0])});")
                    if tr.scope:
                        bind_scope_var(tr.scope, name, cpp_template_type('deque', elem_t), classes=tr.classes)
                    return True
            t = tr._parse_storage_type(node.annotation, tparams)
            fd_inner = frozendict_type_args(t) if is_frozendict_type(t) else None
            if fd_inner is not None and len(call.args) == 1 and (not call.keywords):
                _emit_frozendict_from_arg(tr, name, fd_inner, call.args[0], declare=tr._try_declare(name))
                return True
            if is_stack_array_type(t):
                if call.args:
                    raise NotImplementedError('T[:N] 栈定长数组不支持 new(大小)；请写 ``buf: int[:N]`` 或 ``new()``')
                pname = cpp_param(name)
                decl = cpp_stack_array_var_decl(t, pname)
                if tr._try_declare(name):
                    if tr.scope:
                        bind_scope_var(tr.scope, name, t, classes=tr.classes)
                    tr.write_line(f'{decl};')
                else:
                    tr.write_line(f'{pname} = {t}();')
                return True
            val = _emit_new_ctor_expr(tr, t, call)
            pname = cpp_param(name)
            if tr._try_declare(name):
                if tr.scope:
                    bind_scope_var(tr.scope, name, t, classes=tr.classes)
                tr.write_line(f'{t} {pname} = {val};')
            else:
                tr.write_line(f'{pname} = {val};')
            return True
        case ast.Attribute(value=ast.Name(id='self'), attr=attr):
            if _emit_self_member_typed_container_init(tr, attr, node):
                return True
            t = tr._parse_storage_type(node.annotation, tparams)
            if is_stack_array_type(t):
                if call.args:
                    raise NotImplementedError('T[:N] 栈数组成员不支持 new(大小)；字段在类体默认构造')
                return True
            val = _emit_new_ctor_expr(tr, t, call)
            tr.write_line(f'this->{tr._attr_cpp_name(node.target, attr)} = {val};')
            return True
        case _:
            return False

def _analyze_list_ctor_call(tr: 'Translator', node: ast.Call) -> tuple[str, str, list[ast.expr]] | None:
    match node.func:
        case ast.Subscript(value=ast.Name(id='list'), slice=sl):
            elem_t = tr._parse_storage_type(sl, tr._active_type_params())
            if len(node.args) > 1:
                raise NotImplementedError('已废除 list[T](a, b, c)；请使用 x: list[T] = [a, b, c] 或 x = [a, b, c]')
            if not node.args:
                return (elem_t, 'empty', [])
            return (elem_t, 'capacity', list(node.args))
        case ast.Name(id='list'):
            if node.args:
                return None
            return (None, 'empty_untyped', [])
    return None

def _emit_empty_container_ctor(tr: 'Translator', name: str, container: str, elem_spec: str, *, declare: bool) -> None:
    spec = cpp_template_type(container, elem_spec)
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{spec} {pname};')
    else:
        tr.write_line(f'{pname} = {spec}();')

def _emit_typed_container_init(tr: 'Translator', name: str, container: str, elem_spec: str, value: ast.expr, *, declare: bool) -> bool:
    if not isinstance(value, ast.Call) or value.args:
        return False
    if isinstance(value.func, ast.Name) and value.func.id == container:
        _emit_empty_container_ctor(tr, name, container, elem_spec, declare=declare)
        return True
    if container == 'list':
        analyzed = _analyze_list_ctor_call(tr, value)
        if analyzed and analyzed[1] == 'empty_untyped':
            _emit_empty_container_ctor(tr, name, container, elem_spec, declare=declare)
            return True
    return False

def _empty_container_rhs(tr: 'Translator', container: str, elem_spec: str) -> str | None:
    if container in ('list', 'deque', 'dict', 'set', 'frozenset', 'frozenlist', 'frozendict'):
        return f'{cpp_ident(container)}<{elem_spec}>()'
    return None

def _is_empty_container_call(tr: 'Translator', container: str, value: ast.expr) -> bool:
    if not isinstance(value, ast.Call) or value.args:
        return False
    if isinstance(value.func, ast.Name) and value.func.id == container:
        return True
    if container == 'list':
        analyzed = _analyze_list_ctor_call(tr, value)
        return bool(analyzed and analyzed[1] == 'empty_untyped')
    return False

def _emit_self_member_typed_container_init(tr: 'Translator', attr: str, node: ast.AnnAssign) -> bool:
    """tr.x: list[T] = list() / dict[K,V] = dict() → this->x = list<T>() / dict<...>()"""
    if not node.annotation or not node.value:
        return False
    tparams = tr._active_type_params()
    appendable = tr._appendable_init_from_ann(node.annotation) if node.annotation else None
    if appendable is not None:
        container, elem_t = appendable
        if isinstance(node.value, ast.List) and (not node.value.elts):
            return True
        if isinstance(node.value, ast.Dict) and (not node.value.keys):
            return True
        if tr._is_new_call(node.value) and (not node.value.args):
            return True
        if _is_empty_container_call(tr, container, node.value):
            return True
        if container == 'list' and isinstance(node.value, ast.Call):
            analyzed = _analyze_list_ctor_call(tr, node.value)
            if analyzed and analyzed[1] != 'empty_untyped':
                et, mode, args = analyzed
                tr.write_line(f"this->{attr} = {cpp_ident('list')}<{et}>();")
                if mode == 'capacity':
                    tr.write_line(f'this->{attr}._reserve({tr.visit(args[0])});')
                return True
    t = tr._parse_type(node.annotation, tparams)
    if is_stack_array_type(t):
        if tr._is_new_call(node.value) and (not node.value.args):
            return True
        return False
    if is_dict_type(t) and _is_empty_container_call(tr, 'dict', node.value):
        return True
    if is_dict_type(t) and isinstance(node.value, ast.Dict) and (not node.value.keys):
        return True
    return False

def _declare_appendable_var(tr: 'Translator', container: str, name: str, elem_t: str, *, declare: bool) -> None:
    spec = cpp_template_type(container, elem_t)
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{spec} {pname};')
    else:
        tr.write_line(f'{pname} = {spec}();')

def _declare_list_var(tr: 'Translator', name: str, elem_t: str, *, declare: bool) -> None:
    _declare_appendable_var(tr, 'list', name, elem_t, declare=declare)

def _emit_list_ctor_init(tr: 'Translator', name: str, elem_t: str, mode: str, args: list[ast.expr], *, declare: bool):
    _declare_appendable_var(tr, 'list', name, elem_t, declare=declare)
    if mode == 'capacity':
        tr.write_line(f'{cpp_param(name)}._reserve({tr.visit(args[0])});')

def _emit_appendable_literal_init(tr: 'Translator', cpp_spec: str, name: str, elem_t: str, elts: list[ast.expr], *, declare: bool) -> None:
    emit_sequence_literal(tr, cpp_spec=cpp_spec, name=name, elem_t=elem_t, elts=elts, declare=declare)

def _emit_list_literal_init(tr: 'Translator', name: str, elem_t: str, elts: list[ast.expr], *, declare: bool):
    _emit_appendable_literal_init(tr, cpp_template_type('list', elem_t), name, elem_t, elts, declare=declare)

def _str_literal_codepoints(text: str) -> list[int]:
    return [ord(c) for c in text]

def _resolve_typed_field_assign_target(tr: 'Translator', target: ast.expr, *, cpp_type: str | None=None) -> tuple[str, str] | None:
    """``self/other._f`` 或带注解局部变量 → ``(lhs, field_cpp_type)``。"""
    match target:
        case ast.Name(id=name):
            t = cpp_type
            if t is None:
                if not tr.scope:
                    return None
                t = scope_storage_cpp(tr, name)
            if not t:
                return None
            return (cpp_param(name), t)
        case ast.Attribute(value=ast.Name(id='self'), attr=attr):
            if not tr.class_info:
                return None
            t = cpp_type or field_storage_cpp(tr.class_info, attr)
            if not t:
                return None
            return (f'this->{tr._attr_cpp_name(target, attr)}', t)
        case ast.Attribute(value=receiver, attr=attr):
            t = cpp_type or tr._field_cpp_type_for_attribute(receiver, attr) or ''
            if not t:
                return None
            recv, sep = tr._receiver_access(receiver)
            lhs = f'{recv}{sep}{tr._attr_cpp_name(target, attr)}'
            return (lhs, t)
        case _:
            return None

def _empty_literal_rhs_for_cpp_type(tr: 'Translator', value: ast.expr, cpp_type: str) -> str | None:
    """空 ``[]`` / ``{}`` / ``""`` / ``b""`` / ``set()`` → 与字段类型一致的默认构造。"""
    t = strip_cpp_type_qualifiers(cpp_type.strip())
    if isinstance(value, ast.List) and (not value.elts):
        if is_list_type(t) or is_deque_type(t) or is_frozenlist_type(t):
            return f'{t}()'
        return None
    if isinstance(value, ast.Dict) and (not (value.keys or value.values)):
        if is_dict_type(t) or is_frozendict_type(t):
            return f'{t}()'
        return None
    if isinstance(value, ast.Constant) and value.value == '':
        if is_str_type(t):
            return f"{cpp_ident('str')}()"
        if is_char_heap_array_type(t) or is_byte_heap_array_type(t):
            return f'{t}()'
        return None
    if isinstance(value, ast.Constant) and value.value == b'':
        if is_bytes_type(t):
            return f"{cpp_ident('bytes')}()"
        if is_byte_heap_array_type(t):
            return f'{t}()'
        return None
    if isinstance(value, ast.Call) and (not value.args) and (not value.keywords):
        if isinstance(value.func, ast.Name) and value.func.id == 'set':
            if is_set_type(t) or is_frozenset_type(t):
                return f'{t}()'
    return None

def _try_emit_field_typed_empty_literal_assign(tr: 'Translator', target: ast.expr, value: ast.expr) -> bool:
    """``self/other._f = []`` 等：按字段注解生成 ``PyList<…>()`` 等，勿误推 ``list[int]``。"""
    resolved = _resolve_typed_field_assign_target(tr, target)
    if resolved is None:
        return False
    lhs, ft = resolved
    rhs = _empty_literal_rhs_for_cpp_type(tr, value, ft)
    if rhs is None:
        return False
    tr.write_line(f'{lhs} = {rhs};')
    return True

def _heap_array_literal_lhs(tr: 'Translator', target: ast.expr, *, cpp_type: str | None=None) -> tuple[str, str, bool, str | None] | None:
    """``T[:] = […]`` 赋值目标 → ``(lhs, cpp_type, declare, name?)``。"""
    match target:
        case ast.Name(id=name):
            resolved = _resolve_typed_field_assign_target(tr, target, cpp_type=cpp_type)
            if resolved is None:
                return None
            lhs, t = resolved
            if not is_array_type(t) or cpp_array_ndim(t) != 1:
                return None
            return (lhs, t, tr._try_declare(name), name)
        case ast.Attribute():
            resolved = _resolve_typed_field_assign_target(tr, target, cpp_type=cpp_type)
            if resolved is None:
                return None
            lhs, t = resolved
            if not is_array_type(t) or cpp_array_ndim(t) != 1:
                return None
            return (lhs, t, False, None)
        case _:
            return None

def _emit_heap_array_literal_init(tr: 'Translator', lhs: str, cpp_type: str, elts: list[ast.expr], *, declare: bool, name: str | None=None, node: ast.AST | None=None) -> None:
    n = len(elts)
    ctor = f'{cpp_type}({n})'
    if declare and name is not None:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
            _mark_scope_variable(tr, name)
        pname = cpp_param(name)
        tr.write_line(f'{cpp_type} {pname} = {ctor};')
        store = pname
    else:
        tr.write_line(f'{lhs} = {ctor};')
        store = lhs
    for i, elt in enumerate(elts):
        tr.write_line(f'{store}.__setitem__({i}, {tr._visit_value_expr(elt)});')

def _try_emit_heap_array_literal_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr, *, cpp_type: str | None=None, node: ast.AST | None=None) -> bool:
    if len(targets) != 1 or not isinstance(value, ast.List):
        return False
    resolved = _heap_array_literal_lhs(tr, targets[0], cpp_type=cpp_type)
    if resolved is None:
        return False
    lhs, t, declare, name = resolved
    _emit_heap_array_literal_init(tr, lhs, t, value.elts, declare=declare, name=name, node=node or value)
    return True

def _emit_char_heap_array_from_str_literal(tr: 'Translator', name: str, text: str, cpp_type: str, *, declare: bool, target_expr: str | None=None) -> None:
    cps = _str_literal_codepoints(text)
    ctor = f'{cpp_type}({len(cps)})'
    if target_expr is not None:
        tr.write_line(f'{target_expr} = {ctor};')
        expr = target_expr
    else:
        pname = cpp_param(name)
        if declare:
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
            tr.write_line(f'{cpp_type} {pname} = {ctor};')
        else:
            tr.write_line(f'{pname} = {ctor};')
        expr = pname
    for i, cp in enumerate(cps):
        tr.write_line(f'{expr}.__setitem__({i}, PyChar({cp}));')

def _emit_char_stack_array_from_str_literal(tr: 'Translator', name: str, cpp_type: str, text: str, *, declare: bool, node: ast.AST) -> None:
    expected = cpp_stack_array_size(cpp_type)
    if expected is None:
        raise NotImplementedError(f'{tr._debug_loc(node)}: 栈数组 {cpp_type} 的长度须为编译期字面量才能用字符串字面量初始化')
    got = len(text)
    if got != expected:
        _raise_stack_array_literal_length_mismatch(tr, cpp_type, expected, got, node)
    cps = _str_literal_codepoints(text)
    offset = cpp_stack_array_offset(cpp_type) or 0
    pname = cpp_param(name)
    decl = cpp_stack_array_var_decl(cpp_type, pname)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
        tr.write_line(f'{decl};')
    for i, cp in enumerate(cps):
        tr.write_line(f'{pname}.__setitem__({offset + i}, PyChar({cp}));')

def _emit_byte_heap_array_from_bytes_literal(tr: 'Translator', name: str, data: bytes, cpp_type: str, *, declare: bool, target_expr: str | None=None) -> None:
    raw = list(data)
    ctor = f'{cpp_type}({len(raw)})'
    if target_expr is not None:
        tr.write_line(f'{target_expr} = {ctor};')
        expr = target_expr
    else:
        pname = cpp_param(name)
        if declare:
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
            tr.write_line(f'{cpp_type} {pname} = {ctor};')
        else:
            tr.write_line(f'{pname} = {ctor};')
        expr = pname
    for i, b in enumerate(raw):
        tr.write_line(f'{expr}.__setitem__({i}, PyByte({b}));')

def _try_emit_byte_array_bytes_literal(tr: 'Translator', target: ast.expr, value: ast.expr, *, cpp_type: str | None=None, node: ast.AST | None=None) -> bool:
    if not isinstance(value, ast.Constant) or not isinstance(value.value, bytes):
        return False
    data = value.value
    match target:
        case ast.Name(id=name):
            t = cpp_type
            if t is None:
                if not tr.scope:
                    return False
                t = scope_storage_cpp(tr, name)
            if is_byte_heap_array_type(t):
                _emit_byte_heap_array_from_bytes_literal(tr, name, data, t, declare=tr._try_declare(name))
                return True
            return False
        case _:
            return False

def _try_emit_char_array_str_literal(tr: 'Translator', target: ast.expr, value: ast.expr, *, cpp_type: str | None=None, node: ast.AST | None=None) -> bool:
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return False
    text = value.value
    if text == '':
        return _try_emit_field_typed_empty_literal_assign(tr, target, value)
    match target:
        case ast.Name(id=name):
            t = cpp_type
            if t is None:
                if not tr.scope:
                    return False
                t = scope_storage_cpp(tr, name)
            if is_char_heap_array_type(t):
                _emit_char_heap_array_from_str_literal(tr, name, text, t, declare=tr._try_declare(name))
                return True
            if is_char_stack_array_type(t):
                _emit_char_stack_array_from_str_literal(tr, name, t, text, declare=tr._try_declare(name), node=node or value)
                return True
            return False
        case ast.Attribute():
            resolved = _resolve_typed_field_assign_target(tr, target, cpp_type=cpp_type)
            if resolved is None:
                return False
            lhs, t = resolved
            if is_char_heap_array_type(t):
                _emit_char_heap_array_from_str_literal(tr, '', text, t, declare=False, target_expr=lhs)
                return True
            if is_str_type(t):
                tr.write_line(f"{lhs} = {cpp_ident('str')}({tr._literal(text, cpp_type=t)});")
                return True
            return False
        case _:
            return False

def _raise_stack_array_literal_length_mismatch(tr: 'Translator', cpp_type: str, expected: int, got: int, node: ast.AST) -> None:
    loc = tr._debug_loc(node)
    raise ValueError(f'{loc}: 栈数组 {cpp_type} 初始化列表长度为 {got}，需要 {expected} 个元素')

def _emit_stack_array_literal_init(tr: 'Translator', name: str, cpp_type: str, elts: list[ast.expr], *, declare: bool, node: ast.AST) -> None:
    nd = cpp_stack_array_ndim(cpp_type)
    if nd == 2:
        _emit_stack_array2d_literal_init(tr, name, cpp_type, elts, declare=declare, node=node)
        return
    if nd == 3:
        _emit_stack_array3d_literal_init(tr, name, cpp_type, elts, declare=declare, node=node)
        return
    expected = cpp_stack_array_size(cpp_type)
    if expected is None:
        raise NotImplementedError(f'{tr._debug_loc(node)}: 栈数组 {cpp_type} 的长度须为编译期字面量才能用列表字面量初始化')
    if len(elts) != expected:
        _raise_stack_array_literal_length_mismatch(tr, cpp_type, expected, len(elts), node)
    offset = cpp_stack_array_offset(cpp_type) or 0
    pname = cpp_param(name)
    decl = cpp_stack_array_var_decl(cpp_type, pname)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{decl};')
    for i, elt in enumerate(elts):
        idx = offset + i
        tr.write_line(f'{pname}.__setitem__({idx}, {tr._visit_value_expr(elt)});')

def _emit_stack_array2d_literal_init(tr: 'Translator', name: str, cpp_type: str, elts: list[ast.expr], *, declare: bool, node: ast.AST) -> None:
    parsed = parse_cpp_stack_array2d_type(cpp_type)
    if parsed is None:
        raise NotImplementedError(f'栈二维数组类型 {cpp_type}')
    _elem, rows, cols, row_off, col_off = parsed
    if len(elts) != rows:
        _raise_stack_array_literal_length_mismatch(tr, cpp_type, rows, len(elts), node)
    pname = cpp_param(name)
    decl = cpp_stack_array_var_decl(cpp_type, pname)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{decl};')
    pi = cpp_ident('int')
    for r, row_node in enumerate(elts):
        if not isinstance(row_node, ast.List):
            raise ValueError(f'{tr._debug_loc(node)}: 栈二维数组 {cpp_type} 初始化须为嵌套列表')
        if len(row_node.elts) != cols:
            _raise_stack_array_literal_length_mismatch(tr, cpp_type, cols, len(row_node.elts), node)
        for c, elt in enumerate(row_node.elts):
            idx = f'PyTuple<{pi}, {pi}>({row_off + r}, {col_off + c})'
            tr.write_line(f'{pname}.__setitem__({idx}, {tr._visit_value_expr(elt)});')

def _emit_stack_array3d_literal_init(tr: 'Translator', name: str, cpp_type: str, elts: list[ast.expr], *, declare: bool, node: ast.AST) -> None:
    parsed = parse_cpp_stack_array3d_type(cpp_type)
    if parsed is None:
        raise NotImplementedError(f'栈三维数组类型 {cpp_type}')
    _elem, d0, d1, d2, o0, o1, o2 = parsed
    if len(elts) != d0:
        _raise_stack_array_literal_length_mismatch(tr, cpp_type, d0, len(elts), node)
    pname = cpp_param(name)
    decl = cpp_stack_array_var_decl(cpp_type, pname)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_type, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{decl};')
    pi = cpp_ident('int')
    for i, plane in enumerate(elts):
        if not isinstance(plane, ast.List):
            raise ValueError(f'{tr._debug_loc(node)}: 栈三维数组 {cpp_type} 初始化须为三层嵌套列表')
        if len(plane.elts) != d1:
            _raise_stack_array_literal_length_mismatch(tr, cpp_type, d1, len(plane.elts), node)
        for j, row_node in enumerate(plane.elts):
            if not isinstance(row_node, ast.List):
                raise ValueError(f'{tr._debug_loc(node)}: 栈三维数组 {cpp_type} 初始化须为三层嵌套列表')
            if len(row_node.elts) != d2:
                _raise_stack_array_literal_length_mismatch(tr, cpp_type, d2, len(row_node.elts), node)
            for k, elt in enumerate(row_node.elts):
                idx = f'PyTuple<{pi}, {pi}, {pi}>({o0 + i}, {o1 + j}, {o2 + k})'
                tr.write_line(f'{pname}.__setitem__({idx}, {tr._visit_value_expr(elt)});')

def _try_emit_stack_array_literal_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr, *, cpp_type: str | None=None, node: ast.AST | None=None) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    if not isinstance(value, ast.List):
        return False
    name = targets[0].id
    t = cpp_type
    if t is None:
        if not tr.scope:
            return False
        t = scope_storage_cpp(tr, name)
    if not is_stack_array_type(t):
        return False
    _emit_stack_array_literal_init(tr, name, t, value.elts, declare=tr._try_declare(name), node=node or value)
    return True

def _emit_appendable_rvalue_expr(tr: 'Translator', node: ast.List, cpp_spec: str, elem_t: str) -> str:
    """``-> Self`` / 宿主 ``list``/``deque`` 等：``return […]`` / ``return [*a, …]`` 右值。"""
    from ..translator import temp_name
    tmp = temp_name('seq_val')
    _emit_appendable_literal_init(tr, cpp_spec, tmp, elem_t, node.elts, declare=True)
    return cpp_param(tmp)

def _emit_list_comp_rvalue_expr(tr: 'Translator', comp: ast.ListComp, cpp_spec: str, elem_t: str) -> str:
    from ..translator import temp_name
    tmp = temp_name('list_comp')
    emit_list_comprehension(tr, name=tmp, cpp_spec=cpp_spec, elem_t=elem_t, comp=comp, declare=True)
    return cpp_param(tmp)

def _emit_list_value_expr(tr: 'Translator', node: ast.List) -> str:
    """嵌套/右值列表字面量 → 临时 ``PyList`` 再返回名（供 ``__setitem__`` 等）。"""
    from ..translator import temp_name
    tmp = temp_name('list_val')
    elem_t = tr._infer_list_elem_type(node.elts)
    _emit_list_literal_init(tr, tmp, elem_t, node.elts, declare=True)
    return cpp_param(tmp)

def _try_emit_self_field_empty_list_assign(tr: 'Translator', target: ast.expr, value: ast.List) -> bool:
    """兼容旧名：``self._field = []`` → :func:`_try_emit_field_typed_empty_literal_assign`。"""
    return _try_emit_field_typed_empty_literal_assign(tr, target, value)

def _try_emit_list_init_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr) -> bool:
    if len(targets) != 1:
        return False
    target = targets[0]
    if not isinstance(target, ast.Name):
        return False
    name = target.id
    decl = tr._try_declare(name)
    if isinstance(value, ast.ListComp):
        return _try_emit_list_comp_assign(tr, targets, value)
    if isinstance(value, ast.Call):
        analyzed = _analyze_list_ctor_call(tr, value)
        if analyzed:
            elem_t, mode, args = analyzed
            _emit_list_ctor_init(tr, name, elem_t, mode, args, declare=decl)
            return True
    if isinstance(value, ast.List):
        if tr.scope:
            vt = scope_storage_cpp(tr, name)
            if is_array_type(vt) and cpp_array_ndim(vt) == 1:
                return False
            from ..analysis.ir import cpp_type_supports_list_literal_append
            pair = cpp_type_supports_list_literal_append(vt, tr.classes)
            if pair is not None:
                cpp_spec, elem_t = pair
                _emit_appendable_literal_init(tr, cpp_spec, name, elem_t, value.elts, declare=decl)
                return True
        elem_t = tr._infer_list_elem_type(value.elts)
        _emit_list_literal_init(tr, name, elem_t, value.elts, declare=decl)
        return True
    return False

def _declare_mapping_var(tr: 'Translator', name: str, cpp_spec: str, *, declare: bool) -> None:
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{cpp_spec} {pname};')
    else:
        tr.write_line(f'{pname} = {cpp_spec}();')

def _declare_dict_var(tr: 'Translator', name: str, inner: str, *, declare: bool) -> None:
    _declare_mapping_var(tr, name, cpp_template_type('dict', inner), declare=declare)

def _infer_dict_inner_from_literal(tr: 'Translator', node: ast.Dict) -> str:
    keys = node.keys or []
    values = node.values or []
    kt = cpp_ident('int')
    vt = cpp_ident('int')
    for key, val in zip(keys, values):
        if key is not None:
            kt = tr._infer_expr_cpp_type(key)
        if val is not None:
            vt = tr._infer_expr_cpp_type(val)
            break
    return f'{kt}, {vt}'

def _emit_dict_literal_init(tr: 'Translator', name: str, cpp_spec: str, node: ast.Dict, *, declare: bool) -> None:
    emit_dict_literal(tr, name=name, cpp_spec=cpp_spec, node=node, declare=declare)

def _emit_dict_value_expr(tr: 'Translator', node: ast.Dict, *, param_cpp_type: str | None=None) -> str:
    """右值 ``{…}`` → 临时 ``PyDict``（或注解给出的映射类型）。"""
    from ..translator import temp_name
    if param_cpp_type and is_dict_type(param_cpp_type):
        inner = dict_type_args(param_cpp_type) or _infer_dict_inner_from_literal(tr, node)
        cpp_spec = cpp_template_type('dict', inner)
    else:
        inner = _infer_dict_inner_from_literal(tr, node)
        cpp_spec = cpp_template_type('dict', inner)
    tmp = temp_name('dict_lit')
    _emit_dict_literal_init(tr, tmp, cpp_spec, node, declare=True)
    return cpp_param(tmp)

def _list_cpp_type(tr: 'Translator', elem_t: str) -> str:
    return cpp_template_type('list', elem_t)

def _resolve_list_comp_spec(tr: 'Translator', name: str, comp: ast.ListComp, *, elem_t: str | None=None, cpp_spec: str | None=None) -> tuple[str, str]:
    from ..analysis.ir import cpp_type_supports_list_literal_append
    if cpp_spec is not None:
        et = elem_t or list_elem_type(cpp_spec) or tr._infer_expr_cpp_type(comp.elt)
        return (cpp_spec, et)
    if tr.scope:
        t = scope_storage_cpp(tr, name)
        pair = cpp_type_supports_list_literal_append(t, tr.classes)
        if pair is not None:
            spec, et_from_t = pair
            return (spec, elem_t or et_from_t)
    et = elem_t or tr._infer_expr_cpp_type(comp.elt)
    return (_list_cpp_type(tr, et), et)

def _try_emit_list_comp_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr, *, elem_t: str | None=None, cpp_spec: str | None=None) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    if not isinstance(value, ast.ListComp):
        return False
    name = targets[0].id
    spec, et = _resolve_list_comp_spec(tr, name, value, elem_t=elem_t, cpp_spec=cpp_spec)
    emit_list_comprehension(tr, name=name, cpp_spec=spec, elem_t=et, comp=value, declare=tr._try_declare(name))
    if tr.scope:
        bind_scope_var(tr.scope, name, spec, classes=tr.classes)
        _mark_scope_variable(tr, name)
    return True

def _try_emit_dict_comp_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr, *, cpp_spec: str | None=None) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    if not isinstance(value, ast.DictComp):
        return False
    name = targets[0].id
    if cpp_spec is None:
        if not tr.scope:
            return False
        t = scope_storage_cpp(tr, name)
        from ..analysis.ir import cpp_type_supports_dict_literal_setitem
        cpp_spec = cpp_type_supports_dict_literal_setitem(t, tr.classes)
        if cpp_spec is None:
            return False
    emit_dict_comprehension(tr, name=name, cpp_spec=cpp_spec, comp=value, declare=tr._try_declare(name))
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_spec, classes=tr.classes)
        _mark_scope_variable(tr, name)
    return True

def _try_emit_dict_init_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    if isinstance(value, ast.DictComp):
        return _try_emit_dict_comp_assign(tr, targets, value)
    if not isinstance(value, ast.Dict):
        return False
    name = targets[0].id
    if not tr.scope:
        return False
    t = scope_storage_cpp(tr, name)
    from ..analysis.ir import cpp_type_supports_dict_literal_setitem
    cpp_spec = cpp_type_supports_dict_literal_setitem(t, tr.classes)
    if cpp_spec is None:
        return False
    _emit_dict_literal_init(tr, name, cpp_spec, value, declare=tr._try_declare(name))
    return True

def _declare_addable_var(tr: 'Translator', cpp_spec: str, name: str, elem_t: str, *, declare: bool) -> None:
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{cpp_spec} {pname};')
    else:
        tr.write_line(f'{pname} = {cpp_spec}();')

def _declare_set_var(tr: 'Translator', name: str, elem_t: str, *, declare: bool) -> None:
    _declare_addable_var(tr, cpp_template_type('set', elem_t), name, elem_t, declare=declare)

def _emit_set_literal_init(tr: 'Translator', name: str, elem_t: str, node: ast.Set, *, declare: bool, cpp_spec: str | None=None) -> None:
    spec = cpp_spec or cpp_template_type('set', elem_t)
    emit_set_literal(tr, name=name, cpp_spec=spec, elem_t=elem_t, node=node, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, spec, classes=tr.classes)
        _mark_scope_variable(tr, name)

def _resolve_set_comp_spec(tr: 'Translator', name: str, comp: ast.SetComp, *, elem_t: str | None=None, cpp_spec: str | None=None) -> tuple[str, str]:
    from ..analysis.ir import cpp_type_supports_set_literal_add
    if cpp_spec is not None:
        et = elem_t or set_elem_type(cpp_spec) or tr._infer_expr_cpp_type(comp.elt)
        if et is None:
            et = tr._infer_expr_cpp_type(comp.elt)
        return (cpp_spec, et)
    if tr.scope:
        t = scope_storage_cpp(tr, name)
        et_from_t = cpp_type_supports_set_literal_add(t, tr.classes)
        if et_from_t is not None:
            spec = t if not is_set_type(t) else cpp_template_type('set', et_from_t)
            return (spec, elem_t or et_from_t)
    et = elem_t or tr._infer_expr_cpp_type(comp.elt)
    return (cpp_template_type('set', et), et)

def _try_emit_set_comp_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr, *, elem_t: str | None=None, cpp_spec: str | None=None) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    if not isinstance(value, ast.SetComp):
        return False
    name = targets[0].id
    spec, et = _resolve_set_comp_spec(tr, name, value, elem_t=elem_t, cpp_spec=cpp_spec)
    emit_set_comprehension(tr, name=name, cpp_spec=spec, elem_t=et, comp=value, declare=tr._try_declare(name))
    if tr.scope:
        bind_scope_var(tr.scope, name, spec, classes=tr.classes)
        _mark_scope_variable(tr, name)
    return True

def _try_emit_set_init_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    name = targets[0].id
    decl = tr._try_declare(name)
    if isinstance(value, ast.SetComp):
        return _try_emit_set_comp_assign(tr, targets, value)
    if isinstance(value, ast.Set):
        elem_t: str | None = None
        cpp_spec: str | None = None
        if tr.scope:
            t = scope_storage_cpp(tr, name)
            from ..analysis.ir import cpp_type_supports_set_literal_add
            elem_t = cpp_type_supports_set_literal_add(t, tr.classes)
            if elem_t is not None:
                cpp_spec = t if not is_set_type(t) else cpp_template_type('set', elem_t)
        if elem_t is None:
            elem_t = _infer_set_elem_type(tr, value.elts)
            cpp_spec = cpp_template_type('set', elem_t)
        _emit_set_literal_init(tr, name, elem_t, value, declare=decl, cpp_spec=cpp_spec)
        return True
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and (value.func.id == 'set') and (not value.args) and tr.scope:
        t = scope_storage_cpp(tr, name)
        elem_t = set_elem_type(t) if is_set_type(t) else None
        if elem_t is not None:
            _emit_empty_container_ctor(tr, name, 'set', elem_t, declare=decl)
            return True
    return False

def _infer_set_elem_type(tr: 'Translator', elts: list[ast.expr]) -> str:
    if not elts:
        return cpp_ident('int')
    return tr._infer_expr_cpp_type(elts[0])

def _emit_frozenset_from_arg(tr: 'Translator', name: str, elem_t: str, arg: ast.expr, *, declare: bool) -> None:
    if isinstance(arg, ast.Set):
        _emit_frozenset_from_set_literal(tr, name, elem_t, arg, declare=declare)
        return
    spec = cpp_template_type('frozenset', elem_t)
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{spec} {pname};')
    else:
        tr.write_line(f'{pname} = {spec}();')
    arg_cpp = tr.visit(arg)
    arg_t = tr._infer_expr_cpp_type(arg)
    if is_set_type(arg_t):
        tr.write_line(f'{pname}.initFromSet({arg_cpp});')
    elif is_frozenset_type(arg_t):
        tr.write_line(f'{pname}.initFromFrozenset({arg_cpp});')
    elif is_list_type(arg_t):
        tr.write_line(f'{pname}.initFromList({arg_cpp});')
    else:
        raise NotImplementedError('frozenset(iterable) 仅支持 set、frozenset、list 实参（需可推断类型）')

def _emit_frozenset_from_set_literal(tr: 'Translator', name: str, elem_t: str, node: ast.Set, *, declare: bool) -> None:
    emit_frozenset_literal(tr, name=name, elem_t=elem_t, node=node, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_template_type('frozenset', elem_t), classes=tr.classes)

def _emit_frozenlist_from_list_comp(tr: 'Translator', name: str, elem_t: str, comp: ast.ListComp, *, declare: bool) -> None:
    emit_frozenlist_comprehension(tr, name=name, elem_t=elem_t, comp=comp, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_template_type('frozenlist', elem_t), classes=tr.classes)
        _mark_scope_variable(tr, name)

def _emit_frozenset_from_set_comp(tr: 'Translator', name: str, elem_t: str, comp: ast.SetComp, *, declare: bool) -> None:
    emit_frozenset_comprehension(tr, name=name, elem_t=elem_t, comp=comp, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_template_type('frozenset', elem_t), classes=tr.classes)
        _mark_scope_variable(tr, name)

def _emit_frozendict_from_dict_comp(tr: 'Translator', name: str, inner: str, comp: ast.DictComp, *, declare: bool) -> None:
    emit_frozendict_comprehension(tr, name=name, inner=inner, comp=comp, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_template_type('frozendict', inner), classes=tr.classes)
        _mark_scope_variable(tr, name)

def _emit_frozenlist_from_list_literal(tr: 'Translator', name: str, elem_t: str, elts: list[ast.expr], *, declare: bool) -> None:
    emit_frozenlist_literal(tr, name=name, elem_t=elem_t, elts=elts, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_template_type('frozenlist', elem_t), classes=tr.classes)

def _emit_frozendict_from_dict_literal(tr: 'Translator', name: str, inner: str, node: ast.Dict, *, declare: bool) -> None:
    emit_frozendict_literal(tr, name=name, inner=inner, node=node, declare=declare)
    if tr.scope:
        bind_scope_var(tr.scope, name, cpp_template_type('frozendict', inner), classes=tr.classes)
        _mark_scope_variable(tr, name)

def _try_emit_frozenset_init_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    name = targets[0].id
    decl = tr._try_declare(name)
    elem_t: str | None = None
    if tr.scope:
        t = scope_storage_cpp(tr, name)
        elem_t = frozenset_elem_type(t) if is_frozenset_type(t) else None
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        if value.func.id == 'frozenset' and (not value.args):
            if elem_t is None:
                return False
            _emit_empty_container_ctor(tr, name, 'frozenset', elem_t, declare=decl)
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_template_type('frozenset', elem_t), classes=tr.classes)
            return True
        if value.func.id == 'frozenset' and len(value.args) == 1:
            if elem_t is None:
                arg_t = tr._infer_expr_cpp_type(value.args[0])
                if is_set_type(arg_t):
                    elem_t = set_elem_type(arg_t)
                elif is_frozenset_type(arg_t):
                    elem_t = frozenset_elem_type(arg_t)
                elif is_list_type(arg_t):
                    elem_t = list_elem_type(arg_t)
            if elem_t is None:
                return False
            _emit_frozenset_from_arg(tr, name, elem_t, value.args[0], declare=decl)
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_template_type('frozenset', elem_t), classes=tr.classes)
            return True
    if isinstance(value, ast.Set):
        if elem_t is None:
            elem_t = _infer_set_elem_type(tr, value.elts)
        _emit_frozenset_from_set_literal(tr, name, elem_t, value, declare=decl)
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_template_type('frozenset', elem_t), classes=tr.classes)
        return True
    return False

def _frozenlist_elem_type_from_ann(tr: 'Translator', annotation: ast.expr) -> str | None:
    t = tr._parse_type(annotation, tr._active_type_params())
    if is_frozenlist_type(t):
        return frozenlist_elem_type(t)
    if tr.class_info and tr.class_info.name == 'frozenlist' and (len(tr.class_info.type_params) >= 1) and isinstance(annotation, ast.Name) and (annotation.id in ('Self', tr.class_info.cpp_name())):
        return tr.class_info.type_params[0]
    return None

def _frozendict_inner_from_ann(tr: 'Translator', annotation: ast.expr) -> str | None:
    t = tr._parse_type(annotation, tr._active_type_params())
    if is_frozendict_type(t):
        return frozendict_type_args(t)
    if tr.class_info and tr.class_info.name == 'frozendict' and (len(tr.class_info.type_params) >= 2) and isinstance(annotation, ast.Name) and (annotation.id in ('Self', tr.class_info.cpp_name())):
        return f'{tr.class_info.type_params[0]}, {tr.class_info.type_params[1]}'
    return None

def _emit_frozenlist_from_arg(tr: 'Translator', name: str, elem_t: str, arg: ast.expr, *, declare: bool) -> None:
    spec = cpp_template_type('frozenlist', elem_t)
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{spec} {pname};')
    else:
        tr.write_line(f'{pname} = {spec}();')
    arg_cpp = tr.visit(arg)
    arg_t = tr._infer_expr_cpp_type(arg)
    if is_list_type(arg_t):
        tr.write_line(f'{pname}.initFromList({arg_cpp});')
    elif is_frozenlist_type(arg_t):
        tr.write_line(f'{pname}.initFromFrozenlist({arg_cpp});')
    else:
        raise NotImplementedError('frozenlist(iterable) 仅支持 list、frozenlist 实参（需可推断类型）')

def _try_emit_frozenlist_init_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    name = targets[0].id
    decl = tr._try_declare(name)
    elem_t: str | None = None
    if tr.scope:
        t = scope_storage_cpp(tr, name)
        elem_t = frozenlist_elem_type(t) if is_frozenlist_type(t) else None
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        if value.func.id == 'frozenlist' and (not value.args):
            if elem_t is None:
                return False
            _emit_empty_container_ctor(tr, name, 'frozenlist', elem_t, declare=decl)
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_template_type('frozenlist', elem_t), classes=tr.classes)
            return True
        if value.func.id == 'frozenlist' and len(value.args) == 1:
            if elem_t is None:
                arg_t = tr._infer_expr_cpp_type(value.args[0])
                if is_list_type(arg_t):
                    elem_t = list_elem_type(arg_t)
                elif is_frozenlist_type(arg_t):
                    elem_t = frozenlist_elem_type(arg_t)
            if elem_t is None:
                return False
            _emit_frozenlist_from_arg(tr, name, elem_t, value.args[0], declare=decl)
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_template_type('frozenlist', elem_t), classes=tr.classes)
            return True
    if isinstance(value, ast.List):
        if elem_t is None:
            elem_t = tr._infer_list_elem_type(value.elts)
        if elem_t is None:
            return False
        _emit_frozenlist_from_list_literal(tr, name, elem_t, value.elts, declare=decl)
        return True
    return False

def _emit_frozendict_from_arg(tr: 'Translator', name: str, inner: str, arg: ast.expr, *, declare: bool) -> None:
    spec = cpp_template_type('frozendict', inner)
    pname = cpp_param(name)
    if declare:
        if tr.scope:
            bind_scope_var(tr.scope, name, spec, classes=tr.classes)
            _mark_scope_variable(tr, name)
        tr.write_line(f'{spec} {pname};')
    else:
        tr.write_line(f'{pname} = {spec}();')
    arg_cpp = tr.visit(arg)
    arg_t = tr._infer_expr_cpp_type(arg)
    if is_dict_type(arg_t):
        tr.write_line(f'{pname}.initFromDict({arg_cpp});')
    elif is_frozendict_type(arg_t):
        tr.write_line(f'{pname}.initFromFrozendict({arg_cpp});')
    else:
        raise NotImplementedError('frozendict(mapping) 仅支持 dict、frozendict 实参（需可推断类型）')

def _try_emit_frozendict_init_assign(tr: 'Translator', targets: list[ast.expr], value: ast.expr) -> bool:
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return False
    name = targets[0].id
    decl = tr._try_declare(name)
    inner: str | None = None
    if tr.scope:
        t = scope_storage_cpp(tr, name)
        inner = frozendict_type_args(t) if is_frozendict_type(t) else None
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        if value.func.id == 'frozendict' and (not value.args):
            if inner is None:
                return False
            _emit_empty_container_ctor(tr, name, 'frozendict', inner, declare=decl)
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_template_type('frozendict', inner), classes=tr.classes)
            return True
        if value.func.id == 'frozendict' and len(value.args) == 1:
            if inner is None:
                arg_t = tr._infer_expr_cpp_type(value.args[0])
                if is_dict_type(arg_t):
                    inner = dict_type_args(arg_t)
                elif is_frozendict_type(arg_t):
                    inner = frozendict_type_args(arg_t)
            if inner is None:
                return False
            _emit_frozendict_from_arg(tr, name, inner, value.args[0], declare=decl)
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_template_type('frozendict', inner), classes=tr.classes)
            return True
    if isinstance(value, ast.Dict):
        if inner is None and value.keys and value.values:
            kt = tr._infer_expr_cpp_type(value.keys[0])
            vt = tr._infer_expr_cpp_type(value.values[0])
            if kt and vt:
                inner = f'{kt}, {vt}'
        if inner is None:
            return False
        _emit_frozendict_from_dict_literal(tr, name, inner, value, declare=decl)
        if tr.scope:
            bind_scope_var(tr.scope, name, cpp_template_type('frozendict', inner), classes=tr.classes)
        return True
    return False
