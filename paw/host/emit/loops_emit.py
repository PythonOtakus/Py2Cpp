"""``for`` / ``while`` / ``range`` / ``enumerate`` / ``zip`` 语句 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING, Callable
from ..analysis.type_pred import is_array_type, is_bytes_type, is_char_heap_array_type, is_chunk_deque_type, is_dict_type, is_frozendict_type, is_frozenlist_type, is_list_type, is_py_iterable_type, is_span_type, is_stack_array_type, is_str_type
from ..analysis.type_extract import chunk_deque_elem_type, frozenlist_elem_type, list_elem_type, iterable_elem_type, dict_type_args, frozendict_type_args
from ..analysis.ir import cpp_array_elem_type, cpp_array_ndim, cpp_ident, cpp_iterator_type, cpp_result_type, cpp_slice_result_type, cpp_span_elem_type, cpp_stack_array_elem_type, cpp_stack_array_iterator_type, cpp_stack_array_offset, iter_result_done_cpp, iter_result_value_cpp, strip_cpp_ref
from ..analysis.type_emit import scope_storage_cpp, bind_scope_var
if TYPE_CHECKING:
    from ..translator import Translator

def _is_cpp_generator_type(tr: Translator, iter_ty: str) -> bool:
    from ..analysis.type_pred import is_py_async_generator_type, is_py_coroutine_type, is_py_generator_type
    from ..passes.generators import GENERATOR_SUFFIX
    t = strip_cpp_ref(iter_ty).strip()
    if is_py_generator_type(t):
        return True
    if is_py_coroutine_type(t):
        return True
    if is_py_async_generator_type(t):
        return True
    return bool(t.endswith(GENERATOR_SUFFIX) and t in tr.classes)

def _generator_element_cpp_type(tr: Translator, iter_ty: str) -> str | None:
    from ..analysis.type_extract import async_generator_type_args, coroutine_type_args, generator_type_args
    from ..analysis.type_pred import is_py_async_generator_type, is_py_coroutine_type, is_py_generator_type
    t = strip_cpp_ref(iter_ty).strip()
    if is_py_generator_type(t):
        args = generator_type_args(t)
        if args is not None:
            return args[0]
        return None
    if is_py_coroutine_type(t):
        args = coroutine_type_args(t)
        if args is not None:
            return args[0]
        return None
    if is_py_async_generator_type(t):
        args = async_generator_type_args(t)
        if args is not None:
            return args[0]
        return None
    info = tr.classes.get(t)
    if info is None:
        return None
    elem = info.type_aliases.get('Element')
    if elem is None:
        return None
    return tr._parse_storage_type(elem.value, tr._active_type_params())

def _generator_iter_result_cpp_type(tr: Translator, iter_ty: str) -> str | None:
    from ..analysis.type_extract import async_generator_type_args, coroutine_type_args, generator_type_args
    from ..analysis.type_pred import is_py_async_generator_type, is_py_coroutine_type, is_py_generator_type
    t = strip_cpp_ref(iter_ty).strip()
    if is_py_generator_type(t):
        args = generator_type_args(t)
        if args is not None:
            return cpp_result_type(args[0], args[2])
        return None
    if is_py_coroutine_type(t):
        args = coroutine_type_args(t)
        if args is not None:
            return cpp_result_type(args[0], args[2])
        return None
    if is_py_async_generator_type(t):
        args = async_generator_type_args(t)
        if args is not None:
            return cpp_result_type(args[0], cpp_ident('PyNone'))
        return None
    elem = _generator_element_cpp_type(tr, iter_ty)
    if not elem:
        return None
    t = strip_cpp_ref(iter_ty).strip()
    info = tr.classes.get(t)
    if info is None:
        return cpp_result_type(elem, cpp_ident('PyNone'))
    ret = info.type_aliases.get('ReturnType')
    ret_cpp = tr._parse_storage_type(ret.value, tr._active_type_params()) if ret is not None else cpp_ident('PyNone')
    return cpp_result_type(elem, ret_cpp)

def _is_slice_ctor_expr(node: ast.expr) -> bool:
    match node:
        case ast.Call(func=ast.Subscript(value=ast.Name(id='slice'), slice=_)):
            return True
        case ast.Call(func=ast.Name(id='slice')):
            return True
        case _:
            return False

def is_direct_inline_range_call(node: ast.expr) -> bool:
    from ..passes.inline_range import is_inline_range_call
    return is_inline_range_call(node)

def is_direct_range_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id == 'range')

def _try_parse_cpp_int_literal(cpp: str) -> int | None:
    s = cpp.strip()
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1].strip()
    if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
        return int(s)
    return None

def range_step_is_negative(step: str) -> bool | None:
    """编译期可解析的 ``step`` 符号；``None`` 表示运行时再分支。"""
    step_val = _try_parse_cpp_int_literal(step)
    if step_val is None:
        return None
    return step_val < 0

def cpp_range_loop_cond(name: str, stop: str, step: str, *, neg_step_flag: str | None=None) -> str:
    """``range(start, stop, step)`` 的循环条件（负步长 ``>``，正步长 ``<``）。

  运行期 ``step`` 须先物化符号（``neg_step_flag``），勿在条件里每轮求 ``step < 0``。
  """
    neg = range_step_is_negative(step)
    if neg is True:
        return f'{name} > {stop}'
    if neg is False:
        return f'{name} < {stop}'
    if neg_step_flag is not None:
        return f'({neg_step_flag} ? {name} > {stop} : {name} < {stop})'
    return f'(({step}) < 0 ? {name} > {stop} : {name} < {stop})'

def _native_range_for_header(name: str, start: str, stop: str, step: str, *, redeclare: bool, neg: bool) -> str:
    cond = f'{name} > {stop}' if neg else f'{name} < {stop}'
    inc = f'{name} += {step}'
    if redeclare:
        return f'for (int {name} = {start}; {cond}; {inc})'
    return f'for ({name} = {start}; {cond}; {inc})'

def cpp_native_for_range_header(name: str, start: str, stop: str, step: str, *, redeclare: bool=True) -> str:
    """原生 ``for`` 头；运行期 ``step`` 返回 ``if (step<0){for…>}else{for…}``（符号只判一次）。"""
    neg = range_step_is_negative(step)
    if neg is not None:
        return _native_range_for_header(name, start, stop, step, redeclare=redeclare, neg=neg)
    neg_hdr = _native_range_for_header(name, start, stop, step, redeclare=redeclare, neg=True)
    pos_hdr = _native_range_for_header(name, start, stop, step, redeclare=redeclare, neg=False)
    return f'if (({step}) < 0) {neg_hdr} else {pos_hdr}'

def emit_native_range_loop(tr: Translator, name: str, start: str, stop: str, step: str, body: Callable[[], None], *, redeclare: bool=True, before_header: Callable[[], None] | None=None) -> None:
    """``for name in range(start, stop, step)``：运行期 ``step`` 用 ``if/else`` 双 ``for``。"""
    from ..translator import NameContext
    neg = range_step_is_negative(step)
    if neg is not None:
        if before_header is not None:
            before_header()
        with tr._use_block(cpp_native_for_range_header(name, start, stop, step, redeclare=redeclare)):
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_ident('int'), classes=tr.classes)
                tr.scope.vars[name] = NameContext.Variable
            body()
        return
    neg_hdr = _native_range_for_header(name, start, stop, step, redeclare=redeclare, neg=True)
    pos_hdr = _native_range_for_header(name, start, stop, step, redeclare=redeclare, neg=False)

    def _emit_one(hdr: str) -> None:
        if before_header is not None:
            before_header()
        with tr._use_block(hdr):
            if tr.scope:
                bind_scope_var(tr.scope, name, cpp_ident('int'), classes=tr.classes)
                tr.scope.vars[name] = NameContext.Variable
            body()
    with tr._use_block(f'if (({step}) < 0)'):
        _emit_one(neg_hdr)
    with tr._use_block('else'):
        _emit_one(pos_hdr)

def _cpp_native_for_range_header(name: str, start: str, stop: str, step: str) -> str:
    return cpp_native_for_range_header(name, start, stop, step, redeclare=True)

def emit_range_len_expr(tr: Translator, iter_call: ast.Call) -> str:
    match iter_call.args:
        case [stop]:
            start_s, stop_s, step_s = ('0', tr._visit_value_expr(stop), '1')
        case [start, stop]:
            start_s, stop_s, step_s = (tr._visit_value_expr(start), tr._visit_value_expr(stop), '1')
        case [start, stop, step]:
            start_s, stop_s, step_s = (tr._visit_value_expr(start), tr._visit_value_expr(stop), tr._visit_value_expr(step))
        case _:
            raise NotImplementedError('len(range(...)) 仅支持 1～3 个位置参数')
    from .iife_emit import emit_iife
    return emit_iife(None, [f'PyInt start = ({start_s})', f'PyInt stop = ({stop_s})', f'PyInt step = ({step_s})', 'if (step > 0) { PyInt n = stop - start; if (n <= 0) return (PyInt)0; return ::__floordiv__((n + step - 1), step); }', 'PyInt n = start - stop', 'if (n <= 0) return (PyInt)0', 'return ::__floordiv__((n - step - 1), (-step))'])

def emit_native_range_loop_from_call(tr: Translator, name: str, iter_call: ast.Call, body: Callable[[], None]) -> None:
    from ..translator import NameContext
    match iter_call.args:
        case [stop]:
            start_s, stop_s, step_s = ('0', tr.visit(stop), '1')
        case [start, stop]:
            start_s, stop_s, step_s = (tr.visit(start), tr.visit(stop), '1')
        case [start, stop, step]:
            start_s, stop_s, step_s = (tr.visit(start), tr.visit(stop), tr.visit(step))
        case _:
            raise NotImplementedError('range for-loop pattern')
    redeclare = not (tr.scope is not None and tr.scope.vars.get(name) == NameContext.Variable)
    emit_native_range_loop(tr, name, start_s, stop_s, step_s, body, redeclare=redeclare)

def _emit_iter_next_unpack(tr: Translator, iter_expr: str, result_var: str, value_var: str, value_t: str, *, iter_suffix: str='.__next__()') -> None:
    tr.write_line(f'{cpp_result_type(value_t)} {result_var} = {iter_expr}{iter_suffix};')
    tr.write_line(f'if ({iter_result_done_cpp(result_var)}) break;')
    tr.write_line(f'{value_t} {value_var} = {iter_result_value_cpp(result_var)};')

def _enumerate_call_parts(tr: Translator, call: ast.Call) -> tuple[ast.expr, str] | None:
    if not (isinstance(call.func, ast.Name) and call.func.id == 'enumerate'):
        return None
    start_s = '0'
    for kw in call.keywords:
        if kw.arg == 'start':
            start_s = tr.visit(kw.value)
        else:
            return None
    match call.args:
        case [iterable]:
            return (iterable, start_s)
        case [iterable, start]:
            if call.keywords:
                return None
            return (iterable, tr.visit(start))
        case _:
            return None

def _uses_index_for_loop(iter_ty: str, elem_t: str | None) -> bool:
    if not elem_t or not iter_ty:
        return False
    t = strip_cpp_ref(iter_ty)
    return is_span_type(t) or is_stack_array_type(t) or is_list_type(t) or is_chunk_deque_type(t) or is_str_type(t) or is_bytes_type(t) or is_char_heap_array_type(t) or is_frozenlist_type(t) or (is_array_type(t) and cpp_array_ndim(t) == 1)

def index_for_getitem_at(iter_cpp: str, iter_ty: str, at_expr: str) -> str:
    """相对下标 ``0..len-1``（``reversed`` 时已折算）→ ``__getitem__`` 实参。"""
    t = strip_cpp_ref(iter_ty)
    if is_stack_array_type(t):
        off = cpp_stack_array_offset(t) or 0
        if off != 0:
            at_expr = f'({off}) + ({at_expr})'
    return f'{iter_cpp}.__getitem__({at_expr})'

def _is_stable_iterable_expr(iter_expr: ast.expr) -> bool:
    """左值/稳定引用：可安全多次求值；右值 ``Call`` 等须先物化到局部变量。"""
    match iter_expr:
        case ast.Name():
            return True
        case ast.Attribute(value=val, attr=_):
            return _is_stable_iterable_expr(val)
        case ast.Subscript(value=base, slice=_):
            return _is_stable_iterable_expr(base)
        case ast.Call(func=ast.Name(id='reversed'), args=[_arg], keywords=[]):
            return False
        case _:
            return False

def _materialize_for_iterable(tr: Translator, iter_expr: ast.expr) -> tuple[str, ast.expr]:
    """返回 ``(iter_cpp, iter_expr)``；不稳定可迭代物先绑定到临时 ``list``/容器变量。"""
    from ..translator import temp_name
    match iter_expr:
        case ast.Call(func=ast.Name(id='reversed'), args=[arg], keywords=[]):
            inner_cpp, _ = _materialize_for_iterable(tr, arg)
            return (inner_cpp, iter_expr)
    if _is_stable_iterable_expr(iter_expr):
        return (tr.visit(iter_expr), iter_expr)
    bind = temp_name('seq')
    iter_ty = _iterable_cpp_type(tr, iter_expr)
    if not iter_ty:
        iter_ty = strip_cpp_ref(tr._infer_expr_cpp_type(iter_expr)) or 'auto'
    storage_ty = _concrete_generator_call_cpp_type(tr, iter_expr, iter_ty) or iter_ty
    tr.write_line(f'{storage_ty} {bind} = {tr.visit(iter_expr)};')
    return (bind, iter_expr)


def _concrete_generator_call_cpp_type(
    tr: Translator, iter_expr: ast.expr, inferred_type: str,
) -> str | None:
    """生成器函数调用以其状态机类型落地，避免擦除为抽象生成器。"""
    from ..analysis.ir import cpp_ident
    from ..analysis.module_namespace import qualify_symbol_in_module
    from ..analysis.type_pred import is_py_generator_type
    from ..passes.generators import GENERATOR_SUFFIX

    if not is_py_generator_type(strip_cpp_ref(inferred_type)):
        return None
    if not isinstance(iter_expr, ast.Call) or not isinstance(iter_expr.func, ast.Name):
        return None
    binding = tr._effective_import_bindings().get(iter_expr.func.id)
    if binding is not None and binding.kind == 'function':
        module_path = binding.module_path
        func_name = binding.symbol
    else:
        module_path = tr._active_module_path()
        func_name = iter_expr.func.id
    if not module_path:
        return None
    return qualify_symbol_in_module(
        module_path, cpp_ident(f'{func_name}{GENERATOR_SUFFIX}'),
    )

def _list_iter_owner_ref(iter_cpp: str) -> str:
    """``PyListIterator`` 构造实参：宿主须为可存活的 ``list`` 左值。"""
    s = iter_cpp.strip()
    if not s:
        return f'&({iter_cpp})'
    if s[0] == '(' and s.endswith(')'):
        return f'&{s}'
    return f'&{s}'

def _elem_t_from_container_type(iter_ty: str) -> str | None:
    t = strip_cpp_ref(iter_ty)
    if is_span_type(t):
        return cpp_span_elem_type(t)
    if is_dict_type(t):
        inner = dict_type_args(t) or ''
        key = inner.split(',')[0].strip() if inner else ''
        if key:
            return key
    if is_frozendict_type(t):
        inner = frozendict_type_args(t) or ''
        key = inner.split(',')[0].strip() if inner else ''
        if key:
            return key
    if is_list_type(t):
        return list_elem_type(t)
    if is_chunk_deque_type(t):
        return chunk_deque_elem_type(t)
    if is_frozenlist_type(t):
        return frozenlist_elem_type(t)
    if is_bytes_type(t):
        return cpp_ident('byte')
    if is_str_type(t):
        return cpp_ident('char')
    if is_char_heap_array_type(t):
        return cpp_array_elem_type(t) or cpp_ident('char')
    if is_stack_array_type(t):
        return cpp_stack_array_elem_type(t)
    if is_array_type(t) and cpp_array_ndim(t) == 1:
        return cpp_array_elem_type(t)
    elem = iterable_elem_type(t)
    if elem:
        return elem
    if t.endswith('_generator'):
        return None
    return None

def _iterator_ctor_type(tr: Translator, iter_expr: ast.expr, elem_t: str) -> str:
    iter_ty = _iterable_cpp_type(tr, iter_expr)
    stack_it = cpp_stack_array_iterator_type(strip_cpp_ref(iter_ty))
    if stack_it:
        return stack_it
    if is_py_iterable_type(iter_ty):
        return f'PyIterator<{elem_t}>'
    return cpp_iterator_type('ListIterator', elem_t)

def _neighbors_call_list_cpp_type(tr: Translator, call: ast.Call) -> str | None:
    """``nav.neighbors(u)`` 且 ``nav`` 为协议模板形参时，由 ``Node`` 形参/返回值推 ``PyList<…>``。"""
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == 'neighbors' and (len(call.args) == 1) and (not call.keywords)):
        return None
    if not tr.current_method:
        return None
    tparams = tr._active_type_params()
    for ann in (tr.current_method.returns,):
        if ann is None:
            continue
        ret_cpp = tr._parse_storage_type(ann, tparams)
        if is_list_type(ret_cpp):
            return ret_cpp
    for arg in tr.current_method.args.args:
        if arg.arg in ('start', 'goal', 'u', 'v') and arg.annotation is not None:
            node_cpp = tr._parse_storage_type(arg.annotation, tparams)
            if node_cpp:
                return cpp_template_type('list', node_cpp)
    return None

def _iterable_cpp_type(tr: Translator, iter_expr: ast.expr) -> str:
    match iter_expr:
        case ast.Constant(value=v) if isinstance(v, str):
            return cpp_ident('str')
        case ast.Name(id=name):
            if tr.scope:
                return scope_storage_cpp(tr, name)
        case ast.Attribute(value=ast.Name(id='self'), attr=attr):
            if tr.class_info:
                from ..analysis.type_emit import field_storage_cpp
                return field_storage_cpp(tr.class_info, attr)
        case ast.Attribute(value=val, attr=attr) if isinstance(val, ast.Name):
            if tr.scope:
                return scope_storage_cpp(tr, val.id)
        case ast.Call(func=ast.Attribute(value=recv, attr=method)) as await_call:
            if method == '__await__' and (not await_call.args) and (not await_call.keywords):
                recv_t = strip_cpp_ref(tr._infer_expr_cpp_type(recv) or '')
                if recv_t and recv_t != cpp_ident('int'):
                    return recv_t
                from ..passes.generators import COROUTINE_SUFFIX, _infer_iter_type
                it_ann = _infer_iter_type(await_call, tr, [])
                if isinstance(it_ann, ast.Name) and it_ann.id.endswith(COROUTINE_SUFFIX):
                    return tr._parse_type(it_ann.id, tr._active_type_params())
            lt = _neighbors_call_list_cpp_type(tr, await_call)
            if lt:
                return lt
            inferred_raw = tr._infer_expr_cpp_type(await_call)
            inferred = inferred_raw.strip().rstrip('&') if inferred_raw else ''
            if inferred and inferred != cpp_ident('int'):
                return inferred
            return ''
        case ast.Call() as call:
            lt = _neighbors_call_list_cpp_type(tr, call)
            if lt:
                return lt
            inferred_raw = tr._infer_expr_cpp_type(call)
            inferred = inferred_raw.strip().rstrip('&') if inferred_raw else ''
            if inferred and inferred != cpp_ident('int'):
                return inferred
            return ''
        case _:
            inferred_raw = tr._infer_expr_cpp_type(iter_expr)
            inferred = inferred_raw.strip().rstrip('&') if inferred_raw else ''
            if inferred and inferred != cpp_ident('int'):
                return inferred
    return ''

def element_type_of_iterable(tr: Translator, iter_expr: ast.expr) -> str | None:
    match iter_expr:
        case ast.Call(func=ast.Name(id='reversed'), args=[arg], keywords=[]):
            return element_type_of_iterable(tr, arg)
        case ast.Subscript(value=base, slice=sl) if isinstance(sl, ast.Slice) or _is_slice_ctor_expr(sl):
            base_ty = _iterable_cpp_type(tr, base)
            if not base_ty:
                base_ty = strip_cpp_ref(tr._infer_expr_cpp_type(base))
            result_ty = cpp_slice_result_type(base_ty) if base_ty else None
            if result_ty is None:
                return None
            return _elem_t_from_container_type(result_ty)
        case ast.Constant(value=v) if isinstance(v, str):
            return cpp_ident('char')
        case ast.Name(id=name):
            if tr.scope:
                return _elem_t_from_container_type(scope_storage_cpp(tr, name))
        case ast.Attribute(value=ast.Name(id='self'), attr=attr):
            if tr.class_info:
                from ..analysis.type_emit import field_storage_cpp
                return _elem_t_from_container_type(field_storage_cpp(tr.class_info, attr))
        case ast.Attribute(value=val, attr=attr) if isinstance(val, ast.Name):
            if tr.scope:
                return _elem_t_from_container_type(scope_storage_cpp(tr, val.id))
        case _:
            iter_ty = _iterable_cpp_type(tr, iter_expr)
            if not iter_ty:
                iter_ty = strip_cpp_ref(tr._infer_expr_cpp_type(iter_expr))
            if iter_ty:
                gen_elem = _generator_element_cpp_type(tr, iter_ty)
                if gen_elem:
                    return gen_elem
                return _elem_t_from_container_type(iter_ty)
            return None
    return None

def _index_for_loop_plan(tr: Translator, iter_expr: ast.expr, *, iter_cpp_override: str | None=None) -> tuple[str, str, str, bool] | None:
    match iter_expr:
        case ast.Call(func=ast.Name(id='reversed'), args=[arg], keywords=[]):
            inner = _index_for_loop_plan(tr, arg, iter_cpp_override=None)
            if inner is None:
                return None
            iter_cpp, iter_ty, elem_t, _rev = inner
            if _is_stable_iterable_expr(arg):
                arg_cpp = tr.visit(arg)
            else:
                arg_cpp = iter_cpp
            return (arg_cpp, iter_ty, elem_t, True)
        case ast.Subscript(value=base, slice=sl) if isinstance(sl, ast.Slice) or _is_slice_ctor_expr(sl):
            base_ty = _iterable_cpp_type(tr, base)
            if not base_ty:
                base_ty = strip_cpp_ref(tr._infer_expr_cpp_type(base))
            result_ty = cpp_slice_result_type(base_ty) if base_ty else None
            if result_ty is None:
                return None
            elem_t = _elem_t_from_container_type(result_ty)
            if not _uses_index_for_loop(result_ty, elem_t):
                return None
            iter_cpp = iter_cpp_override if iter_cpp_override is not None else tr.visit(iter_expr)
            return (iter_cpp, result_ty, elem_t, False)
        case _:
            iter_ty = _iterable_cpp_type(tr, iter_expr)
            elem_t = element_type_of_iterable(tr, iter_expr)
            if not (elem_t and _uses_index_for_loop(iter_ty, elem_t)):
                return None
            iter_cpp = iter_cpp_override if iter_cpp_override is not None else tr.visit(iter_expr)
            return (iter_cpp, iter_ty, elem_t, False)

def _emit_index_enumerate_for_loop(tr: Translator, node: ast.For, iter_cpp: str, iter_ty: str, elem_t: str, idx_name: str, val_name: str, start_s: str, *, reversed: bool=False) -> None:
    from ..translator import NameContext, temp_name
    fi = temp_name('fi')
    with tr._loop_with_else(node.orelse):
        header = f'for (PyInt {fi} = 0; {fi} < {iter_cpp}.__len__(); {fi} += 1)'
        with tr._use_block(header):
            tr.write_line(f'int {idx_name} = ({start_s}) + {fi};')
            if reversed:
                at = f'({iter_cpp}.__len__() - 1 - {fi})'
            else:
                at = fi
            tr.write_line(f'{elem_t} {val_name} = {index_for_getitem_at(iter_cpp, iter_ty, at)};')
            if tr.scope:
                bind_scope_var(tr.scope, idx_name, cpp_ident('int'), classes=tr.classes)
                bind_scope_var(tr.scope, val_name, elem_t, classes=tr.classes)
                tr.scope.vars[idx_name] = NameContext.Variable
                tr.scope.vars[val_name] = NameContext.Variable
            tr._emit_body(node.body)

def emit_index_enumerate_for_from_iter(tr: Translator, target: ast.expr, iter_call: ast.Call, body: Callable[[], None], *, orelse: list[ast.stmt] | None=None) -> bool:
    from ..translator import NameContext, temp_name
    parts = _enumerate_call_parts(tr, iter_call)
    if parts is None:
        return False
    iterable, start_s = parts
    match target:
        case ast.Tuple(elts=[ast.Name(id=idx), ast.Name(id=val)]):
            pass
        case _:
            return False
    iter_cpp, iterable = _materialize_for_iterable(tr, iterable)
    plan = _index_for_loop_plan(tr, iterable, iter_cpp_override=iter_cpp)
    if plan is None:
        return False
    iter_cpp, iter_ty, elem_t, reversed_loop = plan
    fi = temp_name('fi')
    header = f'for (PyInt {fi} = 0; {fi} < {iter_cpp}.__len__(); {fi} += 1)'
    with tr._use_block(header):
        tr.write_line(f'int {idx} = ({start_s}) + {fi};')
        if reversed_loop:
            at = f'({iter_cpp}.__len__() - 1 - {fi})'
        else:
            at = fi
        tr.write_line(f'{elem_t} {val} = {index_for_getitem_at(iter_cpp, iter_ty, at)};')
        if tr.scope:
            bind_scope_var(tr.scope, idx, cpp_ident('int'), classes=tr.classes)
            bind_scope_var(tr.scope, val, elem_t, classes=tr.classes)
            tr.scope.vars[idx] = NameContext.Variable
            tr.scope.vars[val] = NameContext.Variable
        body()
    return True

def emit_index_for_from_iter(tr: Translator, target: ast.expr, iter_expr: ast.expr, body: Callable[[], None], *, orelse: list[ast.stmt] | None=None) -> bool:
    from ..translator import NameContext, temp_name
    if not isinstance(target, ast.Name):
        return False
    iter_cpp, iter_expr = _materialize_for_iterable(tr, iter_expr)
    plan = _index_for_loop_plan(tr, iter_expr, iter_cpp_override=iter_cpp)
    if plan is None:
        return False
    iter_cpp, iter_ty, elem_t, reversed_loop = plan
    name = target.id
    idx = temp_name('fi')
    if reversed_loop:
        header = f'for (PyInt {idx} = {iter_cpp}.__len__() - 1; {idx} >= 0; {idx} -= 1)'
        at = idx
    else:
        header = f'for (PyInt {idx} = 0; {idx} < {iter_cpp}.__len__(); {idx} += 1)'
        at = idx
    with tr._use_block(header):
        tr.write_line(f'{elem_t} {name} = {index_for_getitem_at(iter_cpp, iter_ty, at)};')
        if tr.scope:
            bind_scope_var(tr.scope, name, elem_t, classes=tr.classes)
            tr.scope.vars[name] = NameContext.Variable
        body()
    return True

def _emit_index_for_loop(tr: Translator, node: ast.For, iter_cpp: str, iter_ty: str, elem_t: str, name: str, *, reversed: bool=False) -> None:
    from ..translator import NameContext, temp_name
    idx = temp_name('fi')
    with tr._loop_with_else(node.orelse):
        if reversed:
            header = f'for (PyInt {idx} = {iter_cpp}.__len__() - 1; {idx} >= 0; {idx} -= 1)'
            at = idx
        else:
            header = f'for (PyInt {idx} = 0; {idx} < {iter_cpp}.__len__(); {idx} += 1)'
            at = idx
        with tr._use_block(header):
            tr.write_line(f'{elem_t} {name} = {index_for_getitem_at(iter_cpp, iter_ty, at)};')
            if tr.scope:
                bind_scope_var(tr.scope, name, elem_t, classes=tr.classes)
                tr.scope.vars[name] = NameContext.Variable
            tr._emit_body(node.body)

def _for_inline_range(tr: Translator, node: ast.For) -> None:
    from ..passes.inline_range import _INLINE_RANGE_ERR, _flatten_stmt, _is_inline_range_call
    if not _is_inline_range_call(node.iter) or tr.class_info is None:
        raise NotImplementedError('inline_range for-loop pattern')
    if node.orelse:
        raise NotImplementedError('inline_range 不支持 for-else')
    flat = _flatten_stmt(node, tr.class_info, {})
    if len(flat) == 1 and isinstance(flat[0], ast.For):
        lineno = getattr(node, 'lineno', 0) or 0
        raise NotImplementedError(f'{lineno}: {_INLINE_RANGE_ERR}')
    tr._emit_body(flat)

def _for_range(tr: Translator, node: ast.For) -> None:
    match node.target:
        case ast.Name(id=name):
            with tr._loop_with_else(node.orelse):
                emit_native_range_loop_from_call(tr, name, node.iter, lambda: tr._emit_body(node.body))
        case _:
            raise NotImplementedError('range for-loop pattern')

def _for_enumerate(tr: Translator, node: ast.For) -> None:
    from ..translator import NameContext, temp_name
    if not isinstance(node.iter, ast.Call):
        raise NotImplementedError('enumerate for-loop')
    parts = _enumerate_call_parts(tr, node.iter)
    if parts is None:
        raise NotImplementedError('enumerate for-loop')
    iterable, start_s = parts
    match node.target:
        case ast.Tuple(elts=[ast.Name(id=idx), ast.Name(id=val)]):
            iter_cpp, iterable = _materialize_for_iterable(tr, iterable)
            plan = _index_for_loop_plan(tr, iterable, iter_cpp_override=iter_cpp)
            if plan is not None:
                iter_cpp, iter_ty, elem_t, reversed_loop = plan
                _emit_index_enumerate_for_loop(tr, node, iter_cpp, iter_ty, elem_t, idx, val, start_s, reversed=reversed_loop)
                return
            elem_t = element_type_of_iterable(tr, iterable) or f"{cpp_ident('object')}*"
            tuple_t = f'PyTuple<int, {elem_t}>'
            it = temp_name('it')
            res = temp_name('en')
            tuple_var = temp_name('pr')
            tr.write_line(f"{cpp_ident('EnumerateIterator')}<{elem_t}> {it}({iter_cpp}, {start_s});")
            with tr._loop_with_else(node.orelse):
                with tr._use_block('while (true)'):
                    _emit_iter_next_unpack(tr, it, res, tuple_var, tuple_t)
                    tr.write_line(f'int {idx} = {tuple_var}.template get<0>();')
                    tr.write_line(f'{elem_t} {val} = {tuple_var}.template get<1>();')
                    if tr.scope:
                        bind_scope_var(tr.scope, idx, cpp_ident('int'), classes=tr.classes)
                        bind_scope_var(tr.scope, val, elem_t, classes=tr.classes)
                        tr.scope.vars[idx] = NameContext.Variable
                        tr.scope.vars[val] = NameContext.Variable
                    tr._emit_body(node.body)
        case _:
            raise NotImplementedError('enumerate for-loop')

def _for_zip(tr: Translator, node: ast.For) -> None:
    from ..translator import temp_name
    match (node.target, node.iter.args):
        case [ast.Tuple(elts=elts), args] if len(elts) == len(args):
            iters = [temp_name('zip') for _ in args]
            results = [temp_name('zr') for _ in args]
            for v, arg in zip(iters, args):
                arg_cpp, arg_expr = _materialize_for_iterable(tr, arg)
                elem_t = element_type_of_iterable(tr, arg_expr)
                if elem_t:
                    tr.write_line(f'{_iterator_ctor_type(tr, arg_expr, elem_t)} {v}({_list_iter_owner_ref(arg_cpp)});')
                else:
                    sep = tr._member_access(arg_cpp)
                    tr.write_line(f'auto& {v} = {arg_cpp}{sep}__iter__();')
            with tr._loop_with_else(node.orelse):
                with tr._use_block('while (true)'):
                    for elt, it, res, arg in zip(elts, iters, results, args):
                        elem_t = element_type_of_iterable(tr, arg) or 'auto'
                        if elem_t == 'auto':
                            tr.write_line(f'auto {res} = {it}.__next__();')
                            tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                            tr.write_line(f'auto {elt.id} = {iter_result_value_cpp(res)};')
                        else:
                            tr.write_line(f'{cpp_result_type(elem_t)} {res} = {it}.__next__();')
                            tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                            tr.write_line(f'{elem_t} {elt.id} = {iter_result_value_cpp(res)};')
                    tr._emit_body(node.body)
        case _:
            raise NotImplementedError('zip for-loop')

def _for_async_iter(tr: Translator, node: ast.For | ast.AsyncFor) -> None:
    from ..translator import temp_name
    iter_cpp, iter_expr = _materialize_for_iterable(tr, node.iter)
    elem_t = element_type_of_iterable(tr, iter_expr)
    match node.target:
        case ast.Name(id=name):
            it = temp_name('ait')
            sep = tr._member_access(iter_cpp)
            tr.write_line(f'auto {it} = {iter_cpp}{sep}__aiter__();')
            res = temp_name('ar')
            value_t = elem_t or 'auto'
            with tr._loop_with_else(node.orelse):
                with tr._use_block('while (true)'):
                    _emit_iter_next_unpack(tr, it, res, name, value_t, iter_suffix='.__anext__()')
                    tr._emit_body(node.body)
        case _:
            raise NotImplementedError('async for 目标仅支持简单变量名')

def _for_iter(tr: Translator, node: ast.For) -> None:
    from ..translator import temp_name
    iter_cpp, iter_expr = _materialize_for_iterable(tr, node.iter)
    match node.target:
        case ast.Name(id=name):
            plan = _index_for_loop_plan(tr, iter_expr, iter_cpp_override=iter_cpp)
            if plan is not None:
                iter_cpp, iter_ty, elem_t, reversed_loop = plan
                _emit_index_for_loop(tr, node, iter_cpp, iter_ty, elem_t, name, reversed=reversed_loop)
                return
    iter_ty = _iterable_cpp_type(tr, iter_expr)
    if not iter_ty:
        iter_ty = strip_cpp_ref(tr._infer_expr_cpp_type(iter_expr) or '')
    elem_t = element_type_of_iterable(tr, iter_expr)
    match node.target:
        case ast.Name(id=name):
            it = temp_name('it')
            if _is_cpp_generator_type(tr, iter_ty):
                sep = tr._member_access(iter_cpp)
                tr.write_line(f'auto& {it} = {iter_cpp}{sep}__iter__();')
                gen_elem = _generator_element_cpp_type(tr, iter_ty) or elem_t or 'auto'
                result_ty = _generator_iter_result_cpp_type(tr, iter_ty) or cpp_result_type(gen_elem, cpp_ident('PyNone'))
                res = temp_name('r')
                with tr._loop_with_else(node.orelse):
                    with tr._use_block('while (true)'):
                        if gen_elem == 'auto':
                            tr.write_line(f'auto {res} = {it}.__next__();')
                            tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                            tr.write_line(f'auto {name} = {iter_result_value_cpp(res)};')
                        else:
                            tr.write_line(f'{result_ty} {res} = {it}.__next__();')
                            tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                            tr.write_line(f'{gen_elem} {name} = {iter_result_value_cpp(res)};')
                        if tr.scope:
                            from ..translator import NameContext
                            bind_scope_var(tr.scope, name, gen_elem if gen_elem != 'auto' else '', classes=tr.classes)
                            tr.scope.vars[name] = NameContext.Variable
                        tr._emit_body(node.body)
                return
            if elem_t:
                iter_ty = _iterable_cpp_type(tr, iter_expr) or iter_ty
                iter_ty_stripped = strip_cpp_ref(iter_ty)
                if is_dict_type(iter_ty_stripped) or is_frozendict_type(iter_ty_stripped):
                    sep = tr._member_access(iter_cpp)
                    tr.write_line(f'auto& {it} = {iter_cpp}{sep}__iter__();')
                elif is_py_iterable_type(iter_ty):
                    tr.write_line(f'PyIterator<{elem_t}> {it} = ({iter_cpp}).__iter__();')
                else:
                    tr.write_line(f'{_iterator_ctor_type(tr, iter_expr, elem_t)} {it}({_list_iter_owner_ref(iter_cpp)});')
                if tr.scope:
                    bind_scope_var(tr.scope, name, elem_t, classes=tr.classes)
                    from ..translator import NameContext
                    tr.scope.vars[name] = NameContext.Variable
                res = temp_name('r')
                with tr._loop_with_else(node.orelse):
                    with tr._use_block('while (true)'):
                        _emit_iter_next_unpack(tr, it, res, name, elem_t)
                        tr._emit_body(node.body)
            else:
                sep = tr._member_access(iter_cpp)
                match node.iter:
                    case ast.Call(func=ast.Name(id='reversed'), args=[_arg], keywords=[]):
                        rev_bind = temp_name('rev')
                        tr.write_line(f'auto {rev_bind} = {tr.visit(node.iter)};')
                        tr.write_line(f'auto& {it} = {rev_bind}{sep}__iter__();')
                    case _:
                        tr.write_line(f'auto& {it} = {iter_cpp}{sep}__iter__();')
                res = temp_name('r')
                with tr._loop_with_else(node.orelse):
                    with tr._use_block('while (true)'):
                        tr.write_line(f'auto {res} = {it}.__next__();')
                        tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                        if elem_t:
                            tr.write_line(f'{elem_t} {name} = {iter_result_value_cpp(res)};')
                        else:
                            tr.write_line(f'auto {name} = {iter_result_value_cpp(res)};')
                        tr._emit_body(node.body)
        case _:
            raise NotImplementedError('for-loop target')

def visit_while(tr: Translator, node: ast.While) -> None:
    with tr._loop_with_else(node.orelse):
        with tr._use_block(f'while ({tr._bool_test_condition(node.test)})'):
            tr._emit_body(node.body)

def visit_for(tr: Translator, node: ast.For) -> None:
    from .enum_emit import try_emit_enum_for_loop
    from .prange_emit import is_prange_call, emit_prange_for
    from .variadic_template_emit import try_emit_variadic_pack_for
    if try_emit_variadic_pack_for(tr, node):
        return
    if getattr(node, 'is_async', False):
        _for_async_iter(tr, node)
        return
    if is_prange_call(tr, node.iter):
        emit_prange_for(tr, node)
        return
    if is_direct_inline_range_call(node.iter):
        _for_inline_range(tr, node)
        return
    if is_direct_range_call(node.iter):
        _for_range(tr, node)
        return
    if try_emit_enum_for_loop(tr, node):
        return
    match node.iter:
        case ast.Call(func=ast.Name(id='enumerate')):
            _for_enumerate(tr, node)
        case ast.Call(func=ast.Name(id='zip')):
            _for_zip(tr, node)
        case _:
            _for_iter(tr, node)

def visit_async_for(tr: Translator, node: ast.AsyncFor) -> None:
    _for_async_iter(tr, node)
