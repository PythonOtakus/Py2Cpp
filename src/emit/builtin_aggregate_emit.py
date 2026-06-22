"""内建聚合：``min`` / ``max`` / ``sum`` / ``any`` / ``all``（译期内联 IIFE）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_scalar_float_type, is_scalar_int_type, is_str_type, is_varint_type
from ..analysis.ir import cpp_ident, cpp_iterator_type, cpp_result_type, iter_result_done_cpp, iter_result_value_cpp
from ..analysis.type_emit import scope_storage_cpp, bind_scope_var
from ..constant.stdlib_layout import cpp_exception_ctor
from .builtin_call_emit import emit_scalar_cmp_ternary
from .iife_emit import emit_iife
from .comprehensions_emit import _temp_name, append_generator_exp_loops, infer_generator_exp_elem_type
from .loops_emit import _cpp_native_for_range_header, _index_for_loop_plan, _iterator_ctor_type, element_type_of_iterable, index_for_getitem_at, is_direct_range_call
if TYPE_CHECKING:
    from ..translator import Translator
_BUILTIN_AGG = frozenset({'min', 'max', 'sum', 'any', 'all'})

def try_emit_builtin_aggregate_call(tr: Translator, node: ast.Call) -> str | None:
    if not isinstance(node.func, ast.Name) or node.func.id not in _BUILTIN_AGG:
        return None
    name = node.func.id
    pos, key_kw, default_kw, start_kw = _parse_aggregate_keywords(node)
    if name in ('any', 'all'):
        if key_kw is not None or default_kw is not None or start_kw is not None:
            raise NotImplementedError(f'{name}() 不支持 key= / default= / start=')
    if name == 'sum' and (key_kw is not None or default_kw is not None):
        raise NotImplementedError('sum() 不支持 key= / default=')
    if name in ('min', 'max') and start_kw is not None:
        raise NotImplementedError(f'{name}() 不支持 start=')
    if name in ('any', 'all') and len(pos) != 1:
        raise NotImplementedError(f'{name}() 仅接受一个 iterable 参数')
    if name == 'sum' and len(pos) not in (1, 2):
        raise NotImplementedError('sum() 仅接受 iterable 与可选 start')
    if name in ('min', 'max'):
        return _emit_min_max(tr, name, pos, key_kw, default_kw)
    if name == 'sum':
        start = start_kw
        if start is None and len(pos) == 2:
            start = pos[1]
        return _emit_sum(tr, pos[0], start)
    return _emit_any_all(tr, name, pos[0])

def _parse_aggregate_keywords(node: ast.Call) -> tuple[list[ast.expr], ast.expr | None, ast.expr | None, ast.expr | None]:
    pos = list(node.args)
    key_kw: ast.expr | None = None
    default_kw: ast.expr | None = None
    start_kw: ast.expr | None = None
    for kw in node.keywords:
        if kw.arg is None:
            raise NotImplementedError('聚合内建不支持 **kwargs')
        if kw.arg == 'key':
            if key_kw is not None:
                raise NotImplementedError('重复的 key=')
            key_kw = kw.value
        elif kw.arg == 'default':
            if default_kw is not None:
                raise NotImplementedError('重复的 default=')
            default_kw = kw.value
        elif kw.arg == 'start':
            if start_kw is not None:
                raise NotImplementedError('重复的 start=')
            start_kw = kw.value
        else:
            raise NotImplementedError(f'未知关键字参数 {kw.arg!r}')
    return (pos, key_kw, default_kw, start_kw)

def _emit_cxx_lambda(tr: Translator, lam: ast.Lambda, param_t: str) -> str:
    if lam.args.defaults or lam.args.kwonlyargs or lam.args.kwarg or lam.args.vararg or (len(lam.args.args) != 1):
        raise NotImplementedError('key= lambda 仅支持单形参、无默认值')
    param = lam.args.args[0].arg
    saved_types = dict(tr.scope.var_types) if tr.scope else {}
    saved_vars = dict(tr.scope.vars) if tr.scope else {}
    try:
        if tr.scope:
            bind_scope_var(tr.scope, param, param_t, classes=tr.classes)
            from ..translator import NameContext
            tr.scope.vars[param] = NameContext.Variable
        body = tr._visit_value_expr(lam.body)
        return f'[&]({param_t} {param}) {{ return {body}; }}'
    finally:
        if tr.scope:
            tr.scope.var_types.clear()
            tr.scope.var_types.update(saved_types)
            tr.scope.vars.clear()
            tr.scope.vars.update(saved_vars)

def _key_fn_expr(tr: Translator, key_kw: ast.expr | None, elem_t: str) -> str | None:
    if key_kw is None:
        return None
    match key_kw:
        case ast.Lambda():
            return _emit_cxx_lambda(tr, key_kw, elem_t)
        case ast.Name(id=name):
            return name
        case _:
            fn = tr.visit(key_kw)
            return f'({fn})'

def _key_on_item(key_fn: str | None, item_cpp: str) -> str:
    if key_fn is None:
        return item_cpp
    return f'{key_fn}({item_cpp})'

def _values_cmp_expr(tr: Translator, left_cpp: str, right_cpp: str, elem_t: str) -> str:
    lk = left_cpp
    rk = right_cpp
    if is_scalar_int_type(elem_t) or is_scalar_float_type(elem_t):
        return emit_scalar_cmp_ternary(lk, rk)
    if is_varint_type(elem_t) or is_str_type(elem_t):
        return f'{lk}.__cmp__({rk})'
    return f'::py2cpp::py_cmp({lk}, {rk})'

def _emit_min_max_pick_cond(tr: Translator, left_cpp: str, right_cpp: str, elem_t: str, *, key_fn: str | None, pick_min: bool) -> str:
    """``min``/``max`` 选取条件：标量（含 ``key=`` 后的键）用 ``<``/``>``，其余 ``__cmp__``/``py_cmp``。"""
    lk = _key_on_item(key_fn, left_cpp) if key_fn else left_cpp
    rk = _key_on_item(key_fn, right_cpp) if key_fn else right_cpp
    order_t = elem_t
    if key_fn is not None and (not (is_scalar_int_type(elem_t) or is_scalar_float_type(elem_t))):
        order_t = cpp_ident('int')
    if is_scalar_int_type(order_t) or is_scalar_float_type(order_t):
        op = '<' if pick_min else '>'
        return f'({lk} {op} {rk})'
    cmp_expr = _values_cmp_expr(tr, lk, rk, order_t)
    return f'({cmp_expr}) < 0' if pick_min else f'({cmp_expr}) > 0'

def _infer_elem_type(tr: Translator, expr: ast.expr) -> str:
    if isinstance(expr, ast.GeneratorExp):
        return infer_generator_exp_elem_type(tr, expr)
    if is_direct_range_call(expr):
        return cpp_ident('int')
    et = element_type_of_iterable(tr, expr)
    if et:
        return et
    if isinstance(expr, ast.List) and expr.elts:
        return tr._infer_expr_cpp_type(expr.elts[0])
    t = tr._infer_expr_cpp_type(expr)
    return t or 'auto'

def _result_type_min_max(tr: Translator, exprs: list[ast.expr]) -> str:
    for e in exprs:
        t = tr._infer_expr_cpp_type(e)
        if t and t != 'auto':
            return t
    return 'auto'

def _throw_value_error() -> str:
    return f"throw {cpp_exception_ctor('ValueError')};"

def _append_index_loop(tr: Translator, stmts: list[str], iter_expr: ast.expr, loop_var: str, inner: list[str]) -> str:
    plan = _index_for_loop_plan(tr, iter_expr)
    if plan is None:
        raise RuntimeError('index plan expected')
    iter_cpp, iter_ty, elem_t, reversed_loop = plan
    fi = _temp_name('fi')
    if reversed_loop:
        header = f'for (PyInt {fi} = {iter_cpp}.__len__() - 1; {fi} >= 0; {fi} -= 1)'
        at = f'({iter_cpp}.__len__() - 1 - {fi})'
    else:
        header = f'for (PyInt {fi} = 0; {fi} < {iter_cpp}.__len__(); {fi} += 1)'
        at = fi
    getitem = index_for_getitem_at(iter_cpp, iter_ty, at)
    stmts.append(f"{header} {{ {elem_t} {loop_var} = {getitem}; {' '.join(inner)} }}")
    return elem_t

def _append_range_loop(tr: Translator, stmts: list[str], iter_call: ast.Call, loop_var: str, inner: list[str]) -> str:
    match iter_call.args:
        case [stop]:
            start_s, stop_s, step_s = ('0', tr.visit(stop), '1')
        case [start, stop]:
            start_s, stop_s, step_s = (tr.visit(start), tr.visit(stop), '1')
        case [start, stop, step]:
            start_s, stop_s, step_s = (tr.visit(start), tr.visit(stop), tr.visit(step))
        case _:
            raise NotImplementedError('range 仅支持 1～3 个位置参数')
    header = _cpp_native_for_range_header(loop_var, start_s, stop_s, step_s)
    stmts.append(f"{header} {{ {' '.join(inner)} }}")
    return cpp_ident('int')

def _append_iter_loop(tr: Translator, stmts: list[str], iter_expr: ast.expr, loop_var: str, inner: list[str]) -> str:
    elem_t = element_type_of_iterable(tr, iter_expr) or 'auto'
    iter_cpp = tr.visit(iter_expr)
    it = _temp_name('it')
    res = _temp_name('r')
    value_t = elem_t if elem_t != 'auto' else 'auto'
    sep = tr._member_access(iter_cpp)
    if elem_t and elem_t != 'auto':
        stmts.append(f'{_iterator_ctor_type(tr, iter_expr, elem_t)} {it}(&{iter_cpp});')
        loop = f"while (true) {{ {cpp_result_type(elem_t)} {res} = {it}.__next__(); if ({iter_result_done_cpp(res)}) break; {value_t} {loop_var} = {iter_result_value_cpp(res)}; {' '.join(inner)} }}"
    else:
        stmts.append(f'auto& {it} = {iter_cpp}{sep}__iter__();')
        loop = f"while (true) {{ auto {res} = {it}.__next__(); if ({iter_result_done_cpp(res)}) break; auto {loop_var} = {iter_result_value_cpp(res)}; {' '.join(inner)} }}"
    stmts.append(loop)
    return elem_t if elem_t != 'auto' else 'auto'

def _append_genexp_loops(tr: Translator, stmts: list[str], genexp: ast.GeneratorExp, inner: Callable[[], list[str]]) -> str:
    append_generator_exp_loops(tr, stmts, genexp, inner)
    return infer_generator_exp_elem_type(tr, genexp)

def _append_for_over_iterable(tr: Translator, stmts: list[str], iter_expr: ast.expr, loop_var: str, inner: list[str]) -> str:
    if isinstance(iter_expr, ast.GeneratorExp):
        raise RuntimeError('genexp 须经 _append_genexp_loops，勿传入 loop_var')
    if is_direct_range_call(iter_expr):
        return _append_range_loop(tr, stmts, iter_expr, loop_var, inner)
    if _index_for_loop_plan(tr, iter_expr) is not None:
        return _append_index_loop(tr, stmts, iter_expr, loop_var, inner)
    return _append_iter_loop(tr, stmts, iter_expr, loop_var, inner)

def _emit_min_max(tr: Translator, name: str, pos: list[ast.expr], key_kw: ast.expr | None, default_kw: ast.expr | None) -> str:
    pick_min = name == 'min'
    if not pos:
        raise NotImplementedError(f'{name}() 至少需要一个参数')
    if len(pos) >= 2:
        return _emit_min_max_multi(tr, name, pos, key_kw)
    return _emit_min_max_iterable(tr, name, pos[0], key_kw, default_kw, pick_min)

def _emit_min_max_multi(tr: Translator, name: str, args: list[ast.expr], key_kw: ast.expr | None) -> str:
    pick_min = name == 'min'
    ret_t = _result_type_min_max(tr, args)
    elem_t = ret_t if ret_t != 'auto' else cpp_ident('int')
    key_fn = _key_fn_expr(tr, key_kw, elem_t)
    best = _temp_name('agg')
    stmts = [f'{ret_t} {best} = {tr._visit_value_expr(args[0])};']
    for arg in args[1:]:
        cur = tr._visit_value_expr(arg)
        cond = _emit_min_max_pick_cond(tr, cur, best, elem_t, key_fn=key_fn, pick_min=pick_min)
        stmts.append(f'if ({cond}) {best} = {cur};')
    stmts.append(f'return {best};')
    return emit_iife(ret_t, stmts)

def _min_max_inner_stmts(tr: Translator, *, elt_cpp: str, best: str, have: str, ret_t: str, pick_min: bool, key_fn: str | None) -> list[str]:
    inner: list[str] = []
    cond = _emit_min_max_pick_cond(tr, elt_cpp, best, ret_t, key_fn=key_fn, pick_min=pick_min)
    inner.append(f'if (!{have}) {{ {best} = {elt_cpp}; {have} = true; }}')
    inner.append(f'else if ({cond}) {{ {best} = {elt_cpp}; }}')
    return inner

def _emit_min_max_iterable(tr: Translator, name: str, iterable: ast.expr, key_kw: ast.expr | None, default_kw: ast.expr | None, pick_min: bool) -> str:
    ret_t = _infer_elem_type(tr, iterable)
    if default_kw is not None:
        ret_t = tr._infer_expr_cpp_type(default_kw) or ret_t
    key_fn = _key_fn_expr(tr, key_kw, ret_t)
    best = _temp_name('agg')
    have = _temp_name('have')
    stmts: list[str] = []
    if ret_t == 'auto':
        stmts.append(f'auto {best};')
    else:
        stmts.append(f'{ret_t} {best};')
    stmts.append(f'bool {have} = false;')
    if isinstance(iterable, ast.GeneratorExp):

        def genexp_body() -> list[str]:
            elt_cpp = tr._visit_value_expr(iterable.elt)
            return _min_max_inner_stmts(tr, elt_cpp=elt_cpp, best=best, have=have, ret_t=ret_t, pick_min=pick_min, key_fn=key_fn)
        _append_genexp_loops(tr, stmts, iterable, genexp_body)
    else:
        loop_var = _temp_name('x')
        inner = _min_max_inner_stmts(tr, elt_cpp=loop_var, best=best, have=have, ret_t=ret_t, pick_min=pick_min, key_fn=key_fn)
        _append_for_over_iterable(tr, stmts, iterable, loop_var, inner)
    if default_kw is not None:
        d = tr._visit_value_expr(default_kw)
        stmts.append(f'if (!{have}) return {d};')
        stmts.append(f'return {best};')
        return emit_iife(ret_t, stmts)
    stmts.append(f'if (!{have}) {_throw_value_error()}')
    stmts.append(f'return {best};')
    return emit_iife(ret_t, stmts)

def _emit_add_expr(tr: Translator, acc_var: str, item_var: str) -> str:
    left = ast.Name(id=acc_var)
    right = ast.Name(id=item_var)
    if tr.scope:
        t_acc = scope_storage_cpp(tr, acc_var)
        t_item = scope_storage_cpp(tr, item_var)
        bind_scope_var(tr.scope, acc_var, t_acc, classes=tr.classes)
        bind_scope_var(tr.scope, item_var, t_item, classes=tr.classes)
    binop = ast.BinOp(left=left, op=ast.Add(), right=right)
    return tr.visit(binop)

def _emit_sum(tr: Translator, iterable: ast.expr, start_kw: ast.expr | None) -> str:
    if start_kw is None:
        start_expr = '0'
        ret_t = cpp_ident('int')
    else:
        start_expr = tr._visit_value_expr(start_kw)
        ret_t = tr._infer_expr_cpp_type(start_kw) or cpp_ident('int')
    acc = _temp_name('sum')
    stmts = [f'{ret_t} {acc} = {start_expr};']
    if tr.scope:
        bind_scope_var(tr.scope, acc, ret_t, classes=tr.classes)
    if isinstance(iterable, ast.GeneratorExp):
        elem_t = infer_generator_exp_elem_type(tr, iterable)

        def genexp_body() -> list[str]:
            elt_cpp = tr._visit_value_expr(iterable.elt)
            tmp = _temp_name('ge')
            if tr.scope:
                bind_scope_var(tr.scope, tmp, elem_t, classes=tr.classes)
                from ..translator import NameContext
                tr.scope.vars[tmp] = NameContext.Variable
            return [f'{elem_t} {tmp} = {elt_cpp};', f'{acc} = {_emit_add_expr(tr, acc, tmp)};']
        _append_genexp_loops(tr, stmts, iterable, genexp_body)
    else:
        loop_var = _temp_name('x')
        elem_t = _infer_elem_type(tr, iterable)
        inner = [f'{acc} = {_emit_add_expr(tr, acc, loop_var)};']
        if tr.scope:
            bind_scope_var(tr.scope, loop_var, elem_t, classes=tr.classes)
        _append_for_over_iterable(tr, stmts, iterable, loop_var, inner)
    stmts.append(f'return {acc};')
    return emit_iife(ret_t, stmts)

def _truth_stmts_for_elt(tr: Translator, elt_cpp: str, elem_t: str, *, want_any: bool) -> list[str]:
    tmp = _temp_name('ge')
    if tr.scope:
        from ..translator import NameContext
        bind_scope_var(tr.scope, tmp, elem_t, classes=tr.classes)
        tr.scope.vars[tmp] = NameContext.Variable
    truth = tr._truthiness_condition_from_cpp(ast.Name(id=tmp), tmp)
    inner = [f'{elem_t} {tmp} = {elt_cpp};']
    if want_any:
        inner.append(f'if ({truth}) return true;')
    else:
        inner.append(f'if (!({truth})) return false;')
    return inner

def _emit_any_all(tr: Translator, name: str, iterable: ast.expr) -> str:
    want_any = name == 'any'
    stmts: list[str] = []
    if isinstance(iterable, ast.GeneratorExp):
        elem_t = infer_generator_exp_elem_type(tr, iterable)

        def genexp_body() -> list[str]:
            elt_cpp = tr._visit_value_expr(iterable.elt)
            return _truth_stmts_for_elt(tr, elt_cpp, elem_t, want_any=want_any)
        _append_genexp_loops(tr, stmts, iterable, genexp_body)
    else:
        loop_var = _temp_name('x')
        elem_t = _infer_elem_type(tr, iterable)
        if tr.scope:
            bind_scope_var(tr.scope, loop_var, elem_t, classes=tr.classes)
        truth = tr._truthiness_condition_from_cpp(ast.Name(id=loop_var), loop_var)
        inner: list[str] = []
        if want_any:
            inner.append(f'if ({truth}) return true;')
        else:
            inner.append(f'if (!({truth})) return false;')
        _append_for_over_iterable(tr, stmts, iterable, loop_var, inner)
    stmts.append('return false;' if want_any else 'return true;')
    return emit_iife('bool', stmts)
