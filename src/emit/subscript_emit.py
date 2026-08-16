"""下标 / 切片 / ``.view`` emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..passes.descriptors import property_getter_method_for, storage_field_for
from ..analysis.type_emit import field_storage_cpp, scope_binding_storage_cpp, scope_storage_cpp
from ..analysis.type_pred import is_array_type, is_bytes_type, is_deque_type, is_frozenlist_type, is_frozendict_type, is_frozenset_type, is_list_type, is_set_type, is_span_type, is_stack_array_type, is_str_type
from ..analysis.type_extract import list_elem_type
from ..analysis.ir import cpp_array_elem_type, cpp_array_ndim, cpp_span_elem_type_any, cpp_span_ndim, cpp_stack_array_elem_type_any, cpp_stack_array_ndim, cpp_stack_array_offset, parse_subslice_bounds, parse_pytuple_slice_template_bounds, cpp_tuple_arity, strip_cpp_type_qualifiers, cpp_ident
from .literal_map_lookup_emit import try_emit_dict_literal_getitem
from .literal_sequence_lookup_emit import try_emit_list_literal_getitem, try_emit_str_literal_getitem
from ..emit.builtin_call_emit import emit_slice_call, emit_slice_ctor
from ..emit.call_emit import class_info_from_receiver
if TYPE_CHECKING:
    from ..translator import Translator

def _class_has_int_getitem(info) -> bool:
    if '__getitem__' in info.method_overloads:
        return True
    return '__getitem__' in info.methods

def _emit_ptr_subscript(tr: Translator, base: str, idx: str, ptr_type: str) -> str:
    """裸指针下标：始终发射 C 式 ``ptr[idx]``。"""
    return f'{base}[{idx}]'

def container_view_elem_cpp(tr: Translator, receiver: ast.expr) -> str | None:
    t = tr._infer_expr_cpp_type(receiver) or tr._expr_cpp_type(receiver)
    if is_stack_array_type(t):
        from ..analysis.ir import cpp_stack_array_elem_type_any
        return cpp_stack_array_elem_type_any(t)
    if is_list_type(t):
        inner = list_elem_type(t)
        return inner.strip() if inner else None
    if is_array_type(t):
        return cpp_array_elem_type(t)
    return None

def _view_span_cpp_cast(elem: str, ndim: int) -> str:
    if ndim == 2:
        return f'PySpan2D<{elem}>'
    if ndim == 3:
        return f'PySpan3D<{elem}>'
    return f'PySpan<{elem}>'

def read_span_view_property(tr: Translator, receiver: ast.expr) -> str | None:
    """``StackArray`` / ``PyArray`` / ``PyList`` / 2D·3D 数组的 ``.view`` → ``view__get()``。"""
    t = tr._infer_expr_cpp_type(receiver) or tr._expr_cpp_type(receiver)
    stack_nd = cpp_stack_array_ndim(t) if is_stack_array_type(t) else None
    arr_nd = cpp_array_ndim(t) if is_array_type(t) else None
    if not (stack_nd is not None or is_list_type(t) or arr_nd in (1, 2, 3)):
        return None
    recv, sep = tr._receiver_access(receiver)
    info = class_info_from_receiver(tr, receiver)
    if info and info.properties.get('view'):
        getter = tr._property_getter_cpp_name(info, 'view')
        return f'{recv}{sep}{getter}()'
    return f"{recv}{sep}{property_getter_method_for('view')}()"

def emit_container_view_as_span(tr: Translator, receiver: ast.expr) -> str | None:
    bare = read_span_view_property(tr, receiver)
    if bare is None:
        return None
    t = tr._infer_expr_cpp_type(receiver) or tr._expr_cpp_type(receiver)
    elem = container_view_elem_cpp(tr, receiver)
    if elem:
        stack_nd = cpp_stack_array_ndim(t) if is_stack_array_type(t) else None
        arr_nd = cpp_array_ndim(t) if is_array_type(t) else None
        nd = stack_nd if stack_nd is not None else arr_nd
        if nd is None:
            nd = 1
        return f'(({_view_span_cpp_cast(elem, nd)})({bare}))'
    return bare

def index_tuple_ctor(ndim: int, args: str) -> str:
    pi = cpp_ident('int')
    if ndim == 2:
        return f'PyTuple<{pi}, {pi}>({args})'
    if ndim == 3:
        return f'PyTuple<{pi}, {pi}, {pi}>({args})'
    return args

def array_subscript_get(tr: Translator, base_expr: ast.expr, slice_node: ast.expr, base_cpp: str | None=None) -> str | None:
    if not isinstance(slice_node, ast.Tuple):
        return None
    elts = slice_node.elts
    t = tr._expr_cpp_type(base_expr)
    ndim = tr._array_ndim_from_type(t)
    if ndim is None or len(elts) != ndim:
        return None
    base = base_cpp if base_cpp is not None else tr.visit(base_expr)
    sep = tr._member_access(base)
    args = ', '.join((tr.visit(e) for e in elts))
    idx = index_tuple_ctor(ndim, args)
    return f'{base}{sep}__getitem__({idx})'

def array_subscript_set(tr: Translator, base_expr: ast.expr, slice_node: ast.expr, value: str, base_cpp: str | None=None) -> bool:
    if not isinstance(slice_node, ast.Tuple):
        return False
    elts = slice_node.elts
    t = tr._expr_cpp_type(base_expr)
    ndim = tr._array_ndim_from_type(t)
    if ndim is None or len(elts) != ndim:
        return False
    base = base_cpp if base_cpp is not None else tr.visit(base_expr)
    sep = tr._member_access(base)
    args = ', '.join((tr.visit(e) for e in elts))
    idx = index_tuple_ctor(ndim, args)
    set_val = tr._coerce_subscript_assign_value(base_expr, value)
    tr.write_line(f'{base}{sep}__setitem__({idx}, {set_val});')
    return True

def is_slice_ctor_expr(node: ast.expr) -> bool:
    match node:
        case ast.Call(func=ast.Subscript(value=ast.Name(id='slice'), slice=_)):
            return True
        case ast.Call(func=ast.Name(id='slice')):
            return True
        case _:
            return False

def emit_str_slice_subscript(tr: Translator, base_expr: ast.expr, slice_expr: ast.expr) -> str:
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    if isinstance(slice_expr, ast.Slice):
        inner = emit_slice_ctor(tr, slice_expr)
    elif isinstance(slice_expr, ast.Call):
        inner = emit_slice_call(tr, slice_expr)
    else:
        inner = tr.visit(slice_expr)
    return f'{base}{sep}__getitem__({inner})'

def fold_constant_span_slice(base_cpp_type: str, slice_expr: ast.expr) -> tuple[int, int] | None:
    """常量 ``[lo:hi]`` → ``(绝对 offset, length)``，用于 ``PySpan<T>(base, length, offset)``。"""
    sub = parse_subslice_bounds(slice_expr) if isinstance(slice_expr, ast.Slice) else None
    if sub is None:
        return None
    rel_lo, length = sub
    base_off = cpp_stack_array_offset(base_cpp_type) or 0
    return (base_off + rel_lo, length)

def _span_slice_index_ctor(ndim: int, parts: list[str]) -> str:
    pi = cpp_ident('int')
    if ndim == 2:
        return f"PyTuple<PySlice<{pi}, {pi}>, PySlice<{pi}, {pi}>>({', '.join(parts)})"
    return f"PyTuple<PySlice<{pi}, {pi}>, PySlice<{pi}, {pi}>, PySlice<{pi}, {pi}>>({', '.join(parts)})"

def emit_stack_array2d_slice_subscript(tr: Translator, base_expr: ast.expr, row_sl: ast.expr, col_sl: ast.expr) -> str:
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    if isinstance(row_sl, ast.Slice):
        row_inner = emit_slice_ctor(tr, row_sl)
    elif isinstance(row_sl, ast.Call):
        row_inner = emit_slice_call(tr, row_sl)
    else:
        row_inner = tr.visit(row_sl)
    if isinstance(col_sl, ast.Slice):
        col_inner = emit_slice_ctor(tr, col_sl)
    elif isinstance(col_sl, ast.Call):
        col_inner = emit_slice_call(tr, col_sl)
    else:
        col_inner = tr.visit(col_sl)
    return f'{base}{sep}_getslice2d({row_inner}, {col_inner})'

def emit_stack_array3d_slice_subscript(tr: Translator, base_expr: ast.expr, sl0: ast.expr, sl1: ast.expr, sl2: ast.expr) -> str:
    base = tr.visit(base_expr)
    sep = tr._member_access(base)

    def _emit_sl(sl: ast.expr) -> str:
        if isinstance(sl, ast.Slice):
            return emit_slice_ctor(tr, sl)
        if isinstance(sl, ast.Call):
            return emit_slice_call(tr, sl)
        return tr.visit(sl)
    return f'{base}{sep}_getslice3d({_emit_sl(sl0)}, {_emit_sl(sl1)}, {_emit_sl(sl2)})'

def emit_span2d_slice_subscript(tr: Translator, base_expr: ast.expr, row_sl: ast.expr, col_sl: ast.expr) -> str:
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    pi = cpp_ident('int')
    if isinstance(row_sl, ast.Slice):
        row_inner = emit_slice_ctor(tr, row_sl)
    else:
        row_inner = tr.visit(row_sl)
    if isinstance(col_sl, ast.Slice):
        col_inner = emit_slice_ctor(tr, col_sl)
    else:
        col_inner = tr.visit(col_sl)
    idx = _span_slice_index_ctor(2, [row_inner, col_inner])
    return f'{base}{sep}__getitem__({idx})'

def emit_stack_array_slice_subscript(tr: Translator, base_expr: ast.expr, slice_expr: ast.expr) -> str:
    """``buf[a:b]`` → ``buf._getslice(PySlice<…>)`` → ``PyArray<T>``。"""
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    if isinstance(slice_expr, ast.Slice):
        inner = emit_slice_ctor(tr, slice_expr)
    elif isinstance(slice_expr, ast.Call):
        inner = emit_slice_call(tr, slice_expr)
    else:
        inner = tr.visit(slice_expr)
    return f'{base}{sep}_getslice({inner})'

def emit_span_slice_subscript(tr: Translator, base_expr: ast.expr, slice_expr: ast.expr) -> str:
    """``span[a:b]`` → ``__getitem__(PySlice)``（``_getslice`` 为 protected）。"""
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    if isinstance(slice_expr, ast.Slice):
        inner = emit_slice_ctor(tr, slice_expr)
    elif isinstance(slice_expr, ast.Call):
        inner = emit_slice_call(tr, slice_expr)
    else:
        inner = tr.visit(slice_expr)
    return f'{base}{sep}__getitem__({inner})'

def _ptr_subscript_base_type(tr: Translator, base_expr: ast.expr) -> str | None:
    """下标基表达式为 ``Pointer[T]`` / ``T*`` 时返回其 C++ 类型。"""
    ptr_t = tr._infer_expr_cpp_type(base_expr) or tr._expr_cpp_type(base_expr)
    if ptr_t and tr._is_ptr_type(ptr_t):
        return ptr_t
    return None

def try_emit_ptr_subscript_store(tr: Translator, base_expr: ast.expr, sl: ast.expr, set_val: str) -> bool:
    """``ptr[i] = v`` / ``obj.buf[i] = v``（``buf`` 为 ``@property`` 返回指针）→ C 式 ``[i]``。"""
    if _ptr_subscript_base_type(tr, base_expr) is None:
        return False
    base = tr.visit(base_expr)
    idx = tr._coerce_dict_key_expr(base_expr, sl)
    tr.write_line(f'{base}[{idx}] = {set_val};')
    return True

def subscript_augassign_native_candidate(tr: Translator, target: ast.Subscript) -> bool:
    """栈数组 / 裸指针下标且元素为原生标量 → ``visit_AugAssign`` 走 ``_try_emit_native_augassign``。"""
    vtype = tr._cpp_type_for_assign_target(target)
    if not vtype or not tr._is_primitive_cpp_type(vtype):
        return False
    base_expr = target.value
    if _ptr_subscript_base_type(tr, base_expr) is not None:
        return True
    if isinstance(base_expr, ast.Attribute) and isinstance(base_expr.value, ast.Name):
        if base_expr.value.id == 'self' and tr.class_info:
            ft = field_storage_cpp(tr.class_info, base_expr.attr) if tr.class_info else ''
            if is_stack_array_type(ft):
                return True
    if isinstance(base_expr, ast.Name) and tr.scope:
        vt = scope_storage_cpp(tr, base_expr.id)
        if is_stack_array_type(vt):
            return True
    return False

def emit_subscript_store(tr: Translator, base_expr: ast.expr, sl: ast.expr, set_val: str) -> None:
    """``base[idx] = value`` → ``__setitem__``（与 ``translator._emit_assign`` 下标分支一致）。"""
    if array_subscript_set(tr, base_expr, sl, set_val):
        return
    if try_emit_ptr_subscript_store(tr, base_expr, sl, set_val):
        return
    if isinstance(base_expr, ast.Attribute) and base_expr.attr == 'shape':
        recv = tr.visit(base_expr.value)
        sep = tr._member_access(recv)
        idx = tr.visit(sl)
        tr.write_line(f'{recv}{sep}shape.__getitem__({idx}) = {set_val};')
        return
    if isinstance(base_expr, ast.Attribute) and isinstance(base_expr.value, ast.Name):
        if base_expr.value.id == 'self':
            attr = base_expr.attr
            if tr.class_info and attr in tr.class_info.field_properties:
                attr = storage_field_for(attr)
            fcpp = tr._attr_cpp_name(base_expr.value, attr)
            idx = tr._coerce_dict_key_expr(base_expr, sl)
            ft = field_storage_cpp(tr.class_info, attr, fallback='') if tr.class_info else ''
            if is_stack_array_type(ft):
                tr.write_line(f'this->{fcpp}.__setitem__({idx}, {set_val});')
            elif tr._is_ptr_type(ft):
                tr.write_line(f'this->{fcpp}[{idx}] = {set_val};')
            else:
                sep = '->' if ft.endswith('*') else '.'
                tr.write_line(f'this->{fcpp}{sep}__setitem__({idx}, {set_val});')
            return
    if isinstance(base_expr, ast.Name):
        base_cpp = tr.visit(base_expr)
        idx = tr._coerce_dict_key_expr(base_expr, sl)
        pname = base_expr.id
        vt = scope_storage_cpp(tr, pname) if tr.scope else ''
        if base_cpp == 'this':
            tr.write_line(f'this->__setitem__({idx}, {set_val});')
        elif is_stack_array_type(vt):
            tr.write_line(f'{base_cpp}.__setitem__({idx}, {set_val});')
        elif tr._is_ptr_type(vt):
            tr.write_line(f'{base_cpp}[{idx}] = {set_val};')
        else:
            tr.write_line(f'{base_cpp}.__setitem__({idx}, {set_val});')
        return
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    idx = tr._coerce_dict_key_expr(base_expr, sl)
    tr.write_line(f'{base}{sep}__setitem__({idx}, {set_val});')

def try_emit_subscript_augassign(tr: Translator, node: ast.AugAssign) -> bool:
    """``d[k] += v`` → ``d.__setitem__(k, d.__getitem__(k) + v)``（映射 / 容器下标）。"""
    target = node.target
    if not isinstance(target, ast.Subscript):
        return False
    if isinstance(target.slice, ast.Slice):
        return False
    if tr._binop_dunder(node.op) is None:
        return False
    if subscript_augassign_native_candidate(tr, target):
        return False
    bin_node = ast.BinOp(left=target, op=node.op, right=node.value)
    new_val = tr.visit(bin_node)
    set_val = tr._coerce_subscript_assign_value(target.value, new_val)
    emit_subscript_store(tr, target.value, target.slice, set_val)
    return True

def emit_del_subscript_index(tr: Translator, base_expr: ast.expr, slice_expr: ast.expr) -> None:
    """``del base[i]`` / ``del base[a:b]`` → ``__delitem__``。"""
    if isinstance(slice_expr, ast.Slice) or is_slice_ctor_expr(slice_expr):
        base = tr.visit(base_expr)
        sep = tr._member_access(base)
        if isinstance(slice_expr, ast.Slice):
            inner = emit_slice_ctor(tr, slice_expr)
        elif isinstance(slice_expr, ast.Call):
            inner = emit_slice_call(tr, slice_expr)
        else:
            inner = tr.visit(slice_expr)
        tr.write_line(f'{base}{sep}__delitem__({inner});')
        return
    if isinstance(base_expr, ast.Attribute) and isinstance(base_expr.value, ast.Name):
        if base_expr.value.id == 'self':
            attr = base_expr.attr
            if tr.class_info and attr in tr.class_info.field_properties:
                attr = storage_field_for(attr)
            fcpp = tr._attr_cpp_name(base_expr.value, attr)
            idx = tr.visit(slice_expr)
            ft = field_storage_cpp(tr.class_info, attr, fallback='') if tr.class_info else ''
            if tr._is_ptr_type(ft):
                raise NotImplementedError('del 不支持指针字段裸下标删除')
            sep = '->' if ft.endswith('*') else '.'
            tr.write_line(f'this->{fcpp}{sep}__delitem__({idx});')
            return
    if isinstance(base_expr, ast.Name):
        base_cpp = tr.visit(base_expr)
        idx = tr.visit(slice_expr)
        pname = base_expr.id
        vt = scope_storage_cpp(tr, pname) if tr.scope else ''
        if base_cpp == 'this':
            tr.write_line(f'this->__delitem__({idx});')
        elif tr._is_ptr_type(vt):
            raise NotImplementedError('del 不支持指针变量裸下标删除')
        else:
            tr.write_line(f'{base_cpp}.__delitem__({idx});')
        return
    base = tr.visit(base_expr)
    sep = tr._member_access(base)
    tr.write_line(f'{base}{sep}__delitem__({tr.visit(slice_expr)});')

def visit_delete(tr: Translator, node: ast.Delete) -> None:
    if len(node.targets) != 1:
        raise NotImplementedError('del 仅支持单目标')
    target = node.targets[0]
    match target:
        case ast.Subscript(value=base_expr, slice=sl):
            emit_del_subscript_index(tr, base_expr, sl)
        case ast.Name(id=name):
            if tr.scope and name in tr.scope.vars:
                raise NotImplementedError('del 变量绑定尚未支持')
            raise NotImplementedError(f'del 不支持的目标: {type(target).__name__}')
        case _:
            raise NotImplementedError(f'del 不支持的目标: {type(target).__name__}')

def _tuple_all_slices(sl: ast.expr) -> list[ast.expr] | None:
    if not isinstance(sl, ast.Tuple) or not sl.elts:
        return None
    if not all((isinstance(e, (ast.Slice, ast.Call)) or is_slice_ctor_expr(e) for e in sl.elts)):
        return None
    return list(sl.elts)

def try_emit_pytuple_slice_subscript(tr: Translator, value_node: ast.expr, slice_node: ast.expr) -> str | None:
    """``PyTuple<…>[i:j]``（字面量界）→ ``template get_slice<i, j>()``（``j`` 可为负索引）。"""
    if not isinstance(slice_node, ast.Slice):
        return None
    vt = tr._expr_var_type(value_node)
    if not vt.startswith('PyTuple<'):
        return None
    arity = cpp_tuple_arity(vt)
    if arity is None:
        return None
    bounds = parse_pytuple_slice_template_bounds(slice_node, arity=arity)
    if bounds is None:
        return None
    start, stop = bounds
    base = tr.visit(value_node)
    sep = tr._member_access(base)
    return f'{base}{sep}template get_slice<{start}, {stop}>()'

def visit_subscript(tr: Translator, node: ast.Subscript) -> str:
    tuple_slices = _tuple_all_slices(node.slice)
    if isinstance(node.value, ast.Attribute) and node.value.attr == 'view' and (tuple_slices is not None):
        base = emit_container_view_as_span(tr, node.value.value)
        if base is not None:
            nd = len(tuple_slices)
            parts: list[str] = []
            for s in tuple_slices:
                if isinstance(s, ast.Slice):
                    parts.append(emit_slice_ctor(tr, s))
                elif isinstance(s, ast.Call):
                    parts.append(emit_slice_call(tr, s))
                else:
                    parts.append(tr.visit(s))
            recv_t = tr._infer_expr_cpp_type(node.value.value) or tr._expr_cpp_type(node.value.value)
            view_nd = 1
            if is_stack_array_type(recv_t):
                stack_nd = cpp_stack_array_ndim(recv_t)
                if stack_nd is not None:
                    view_nd = stack_nd
            elif is_array_type(recv_t):
                arr_nd = cpp_array_ndim(recv_t)
                if arr_nd is not None:
                    view_nd = arr_nd
            if view_nd == 1:
                inner = parts[0] if len(parts) == 1 else parts[0]
                return f'{base}.__getitem__({inner})'
            idx = _span_slice_index_ctor(view_nd, parts)
            return f'{base}.__getitem__({idx})'
    if isinstance(node.value, ast.Attribute) and node.value.attr == 'view' and (isinstance(node.slice, ast.Slice) or is_slice_ctor_expr(node.slice)):
        base = emit_container_view_as_span(tr, node.value.value)
        if base is not None:
            if isinstance(node.slice, ast.Slice):
                inner = emit_slice_ctor(tr, node.slice)
            elif isinstance(node.slice, ast.Call):
                inner = emit_slice_call(tr, node.slice)
            else:
                inner = tr.visit(node.slice)
            return f'{base}.__getitem__({inner})'
    expr_t = tr._infer_expr_cpp_type(node.value)
    if tuple_slices is not None:
        stack_nd = cpp_stack_array_ndim(expr_t) if is_stack_array_type(expr_t) else None
        if stack_nd == 2 and len(tuple_slices) == 2:
            return emit_stack_array2d_slice_subscript(tr, node.value, tuple_slices[0], tuple_slices[1])
        if stack_nd == 3 and len(tuple_slices) == 3:
            return emit_stack_array3d_slice_subscript(tr, node.value, tuple_slices[0], tuple_slices[1], tuple_slices[2])
        span_nd = cpp_span_ndim(expr_t) if is_span_type(expr_t) else None
        if span_nd == 2 and len(tuple_slices) == 2:
            return emit_span2d_slice_subscript(tr, node.value, tuple_slices[0], tuple_slices[1])
        if span_nd == 3 and len(tuple_slices) == 3:
            base = tr.visit(node.value)
            sep = tr._member_access(base)
            parts = []
            for s in tuple_slices:
                if isinstance(s, ast.Slice):
                    parts.append(emit_slice_ctor(tr, s))
                elif isinstance(s, ast.Call):
                    parts.append(emit_slice_call(tr, s))
                else:
                    parts.append(tr.visit(s))
            idx = _span_slice_index_ctor(3, parts)
            return f'{base}{sep}__getitem__({idx})'
    if isinstance(node.slice, ast.Slice) or is_slice_ctor_expr(node.slice):
        if is_str_type(expr_t) or is_list_type(expr_t) or is_bytes_type(expr_t):
            return emit_str_slice_subscript(tr, node.value, node.slice)
        if is_stack_array_type(expr_t) and cpp_stack_array_ndim(expr_t) == 1:
            return emit_stack_array_slice_subscript(tr, node.value, node.slice)
        if is_span_type(expr_t) and cpp_span_ndim(expr_t) == 1:
            return emit_span_slice_subscript(tr, node.value, node.slice)
    if isinstance(node.value, ast.Attribute) and node.value.attr == 'shape':
        recv = tr.visit(node.value.value)
        sep = tr._member_access(recv)
        idx = tr.visit(node.slice)
        return f'{recv}{sep}shape.__getitem__({idx})'
    multi = array_subscript_get(tr, node.value, node.slice)
    if multi is not None:
        return multi
    if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name):
        if node.value.value.id == 'self' and tr.class_info:
            attr = node.value.attr
            if attr in tr.class_info.field_properties:
                attr = storage_field_for(attr)
            ft = field_storage_cpp(tr.class_info, attr)
            idx = tr.visit(node.slice)
            fcpp = tr._attr_cpp_name(node.value, attr)
            if is_stack_array_type(ft) or is_span_type(ft):
                return f'this->{fcpp}.__getitem__({idx})'
            if is_list_type(ft) or is_deque_type(ft):
                sep = '->' if tr._is_ptr_type(ft) else '.'
                return f'this->{node.value.attr}{sep}__getitem__({idx})'
            if tr._is_ptr_type(ft):
                base_t = strip_cpp_type_qualifiers(ft).rstrip('*').strip()
                if is_list_type(base_t) or is_deque_type(base_t) or is_frozenlist_type(base_t) or is_frozendict_type(base_t) or is_set_type(base_t) or is_frozenset_type(base_t):
                    return f'this->{node.value.attr}->__getitem__({idx})'
                from ..analysis.ir import class_info_for_cpp_type

                base_info = class_info_for_cpp_type(base_t, tr.classes)
                if (
                    base_info is not None
                    and not (
                        is_array_type(base_t)
                        or is_stack_array_type(base_t)
                        or is_span_type(base_t)
                    )
                    and _class_has_int_getitem(base_info)
                ):
                    return f'this->{fcpp}->__getitem__({idx})'
                return _emit_ptr_subscript(tr, f'this->{node.value.attr}', idx, ft)
    if isinstance(node.value, ast.Name) and tr.scope:
        if scope_binding_storage_cpp(tr.scope, node.value.id) == 'CStr':
            return f'{node.value.id}[{tr.visit(node.slice)}]'
        vt = scope_storage_cpp(tr, node.value.id)
        if is_stack_array_type(vt) or is_span_type(vt):
            return f'{node.value.id}.__getitem__({tr.visit(node.slice)})'
        if tr._is_ptr_type(vt):
            return _emit_ptr_subscript(tr, node.value.id, tr.visit(node.slice), vt)
    if isinstance(node.value, ast.Dict):
        return try_emit_dict_literal_getitem(tr, node.value, node.slice)
    if isinstance(node.value, ast.List):
        return try_emit_list_literal_getitem(tr, node.value, node.slice)
    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        inline = try_emit_str_literal_getitem(tr, node.value.value, node.slice)
        if inline is not None:
            return inline
    tr._reject_tuple_literal_expr(node.value, context='下标')
    const_get = tr._try_pytuple_const_subscript(node.value, node.slice)
    if const_get is not None:
        return const_get
    if isinstance(node.slice, ast.Slice) or is_slice_ctor_expr(node.slice):
        pytuple_slice = try_emit_pytuple_slice_subscript(tr, node.value, node.slice)
        if pytuple_slice is not None:
            return pytuple_slice
        if isinstance(node.slice, ast.Slice):
            inner = emit_slice_ctor(tr, node.slice)
        elif isinstance(node.slice, ast.Call):
            inner = emit_slice_call(tr, node.slice)
        else:
            inner = tr.visit(node.slice)
        base = tr.visit(node.value)
        sep = tr._member_access(base)
        return f'{base}{sep}__getitem__({inner})'
    if not isinstance(node.slice, ast.Slice) and (not is_slice_ctor_expr(node.slice)):
        if tr._use_member_dispatch_macro(node.value):
            return tr._cpp_call_expr(node.value, '__getitem__', tr.visit(node.slice), site=node, arg_count=1)
        ptr_t = tr._infer_expr_cpp_type(node.value)
        if tr._is_ptr_type(ptr_t):
            return _emit_ptr_subscript(tr, tr.visit(node.value), tr.visit(node.slice), ptr_t)
    base = tr.visit(node.value)
    idx = tr.visit(node.slice)
    sep = tr._member_access(base)
    return f'{base}{sep}__getitem__({idx})'
