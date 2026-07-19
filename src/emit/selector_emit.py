"""``obj.select("path")`` 译期内联；返回类型由导航 + 后处理推断。"""
from __future__ import annotations
import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..analysis.type_emit import field_ann_ast, field_storage_cpp, bind_scope_var
from ..analysis.type_pred import is_dict_type, is_list_type, is_optional_type
from ..analysis.type_extract import dict_type_args, list_elem_type, optional_inner_type
from ..analysis.ir import ClassInfo, cpp_ident, cpp_template_type, option_is_not_none_expr, str_cpp_from_literal, strip_cpp_ref
from .iife_emit import emit_iife
from ..analysis.selector_types import _collect_descendant_relative_paths, _collect_nav_env, _dict_value_ctx, _infer_elem_expr_cpp, select_result_cpp_type, walk_selector_plan
from ..passes.selector_parse import FILTER_BIND_PREFIX, FILTER_ELEM_PLACEHOLDER, BindStep, CountStep, DescendantStep, FieldStep, FilterStep, GroupStep, IndexStep, MultiBracketStep, ProjectionStep, RefStep, SelectorChainPlan, SelectorParseError, SliceStep, SortStep, StrIndexStep, parse_selector_literal
from ..translation_error import raise_translation_error
from ..translator import temp_name
from .builtin_call_emit import emit_cmp_call
from .call_emit import class_info_from_receiver
if TYPE_CHECKING:
    from ..translator import Translator
_SELECT_NAME = 'select'

@dataclass
class _EmitCtx:
    cpp: str
    cpp_t: str
    info: ClassInfo | None

def _is_select_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (node.func.attr == _SELECT_NAME) and (len(node.args) == 1) and (not node.keywords) and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)

def _parse_type_ann(tr: Translator, ann: ast.expr | None) -> str:
    if ann is None:
        return ''
    return tr._parse_type(ann, tr._active_type_params()).strip()

def _check_result_ann(tr: Translator, result_ann: str, expected_cpp: str, *, node: ast.AST | None) -> None:
    from ..analysis.ir import cpp_inferred_type_matches_ann
    ann = result_ann.strip()
    if not ann:
        return
    if not cpp_inferred_type_matches_ann(expected_cpp, ann):
        raise_translation_error(tr, node, f'select 返回类型须为 {expected_cpp}，实为 {ann}')

def _access_sep(tr: Translator, cpp_type: str) -> str:
    return '->' if tr._uses_ptr_access(cpp_type) else '.'

def _list_getitem(tr: Translator, base_cpp: str, base_type: str, index: str) -> str:
    sep = _access_sep(tr, base_type)
    if tr._is_ptr_type(base_type):
        return f'{base_cpp}{sep}__getitem__({index})'
    return f'{base_cpp}.__getitem__({index})'

def _dict_getitem(tr: Translator, base_cpp: str, base_type: str, key: str) -> str:
    key_cpp = str_cpp_from_literal(key)
    sep = _access_sep(tr, base_type)
    if tr._is_ptr_type(base_type):
        return f'{base_cpp}{sep}__getitem__({key_cpp})'
    return f'{base_cpp}.__getitem__({key_cpp})'

def _wrap_guard(cond: str, stmts: list[str]) -> list[str]:
    if not stmts:
        return []
    return [f'if ({cond}) {{', *stmts, '}']

def _list_index_guard(tr: Translator, base_cpp: str, base_type: str, index: int) -> str:
    hi = _list_len(tr, base_cpp, base_type)
    if index >= 0:
        return f'({index} >= 0 && {index} < {hi})'
    return f'(({hi} + ({index})) >= 0 && ({hi} + ({index})) < ({hi}))'

def _dict_key_guard(base_cpp: str, base_type: str, tr: Translator, key: str) -> str:
    key_cpp = str_cpp_from_literal(key)
    sep = _access_sep(tr, base_type)
    if tr._is_ptr_type(base_type):
        return f'{base_cpp}{sep}__contains__({key_cpp})'
    return f'{base_cpp}.__contains__({key_cpp})'

def _optional_value_cpp(base_cpp: str, base_type: str) -> str:
    del base_type
    return f'{base_cpp}.value__get()'

def _list_len(tr: Translator, base_cpp: str, base_type: str) -> str:
    sep = _access_sep(tr, base_type)
    if tr._is_ptr_type(base_type):
        return f'{base_cpp}{sep}__len__()'
    return f'{base_cpp}.__len__()'

def _emit_field(tr: Translator, ctx: _EmitCtx, step: FieldStep) -> _EmitCtx:
    if ctx.info is None:
        raise SelectorParseError(f'字段 {step.name!r} 无 struct 上下文')
    member = tr._member_cpp_name(ctx.info, step.name)
    sep = _access_sep(tr, ctx.cpp_t)
    cpp = f'{ctx.cpp}{sep}{member}'
    cpp_t = field_storage_cpp(ctx.info, step.name)
    if not cpp_t:
        ann = field_ann_ast(ctx.info, step.name)
        cpp_t = tr._parse_type(ann, ctx.info.type_params) if ann else ''
    info = tr._class_info_for_type(strip_cpp_ref(cpp_t))
    return _EmitCtx(cpp, cpp_t, info)

def _rewrite_filter_elem(expr: ast.expr, elem_var: str, bind_vars: dict[str, str] | None=None) -> ast.expr:
    bind_vars = bind_vars or {}

    class Rewriter(ast.NodeTransformer):

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load):
                if node.id == FILTER_ELEM_PLACEHOLDER:
                    return ast.Name(id=elem_var, ctx=ast.Load())
                if node.id.startswith(FILTER_BIND_PREFIX):
                    bind_name = node.id[len(FILTER_BIND_PREFIX):]
                    if bind_name in bind_vars:
                        return ast.Name(id=bind_vars[bind_name], ctx=ast.Load())
            return node

        def visit_Attribute(self, node: ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id.startswith(FILTER_BIND_PREFIX):
                bind_name = node.value.id[len(FILTER_BIND_PREFIX):]
                if bind_name in bind_vars:
                    return ast.Attribute(value=ast.Name(id=bind_vars[bind_name], ctx=ast.Load()), attr=node.attr, ctx=node.ctx)
            return self.generic_visit(node)
    return ast.fix_missing_locations(Rewriter().visit(copy.deepcopy(expr)))

def _bind_var_name(name: str) -> str:
    return f'sel_{name}'

def _emit_bind_decl(name: str, ctx: _EmitCtx) -> tuple[str, _EmitCtx]:
    var = _bind_var_name(name)
    return (f'auto& {var} = {ctx.cpp};', _EmitCtx(var, ctx.cpp_t, ctx.info))

def _emit_list_iife(tr: Translator, ret_cpp: str, body_stmts: list[str], *, out: str | None=None, list_elem_cpp: str | None=None) -> str:
    if list_elem_cpp is not None:
        out_var = out or temp_name('sel_out')
        list_t = cpp_template_type('list', list_elem_cpp)
        stmts = [f'{list_t} {out_var};', *body_stmts, f'return {out_var};']
    else:
        stmts = [*body_stmts]
    return emit_iife(ret_cpp, stmts)

def _emit_sort_stmts(tr: Translator, out: str, sort: SortStep, binds: dict[str, _EmitCtx]) -> list[str]:
    bind_vars = _bind_cpp_vars(binds)
    cmp_lines: list[str] = []
    for key in sort.keys:
        ea = _rewrite_filter_elem(key.expr, 'a', bind_vars)
        eb = _rewrite_filter_elem(key.expr, 'b', bind_vars)
        cmp_expr = emit_cmp_call(tr, ea, eb)
        if key.descending:
            cmp_lines.append(f'if ({cmp_expr} != 0) return {cmp_expr} > 0;')
        else:
            cmp_lines.append(f'if ({cmp_expr} != 0) return {cmp_expr} < 0;')
    cmp_lines.append('return false;')
    before = temp_name('sel_before')
    si = temp_name('si')
    sj = temp_name('sj')
    val = temp_name('sel_v')
    return [f"auto {before} = [&](const auto& a, const auto& b) -> bool {{ {' '.join(cmp_lines)} }};", f'for (int {si} = 1; {si} < {out}.__len__(); ++{si}) {{', f'auto {val} = {out}.__getitem__({si});', f'int {sj} = {si};', f'while ({sj} > 0 && {before}({val}, {out}.__getitem__({sj} - 1))) {{', f'{out}.__setitem__({sj}, {out}.__getitem__({sj} - 1));', f'--{sj};', '}', f'{out}.__setitem__({sj}, {val});', '}']

def _emit_group_stmts(tr: Translator, out: str, elem_cpp: str, group: GroupStep, binds: dict[str, _EmitCtx], *, struct_info: ClassInfo | None, nav_env: dict, node: ast.AST | None) -> tuple[str, str, list[str]]:
    key_cpp = _infer_elem_expr_cpp(tr, group.expr, struct_info, nav_env, node=node)
    list_t = cpp_template_type('list', elem_cpp)
    dict_t = cpp_template_type('dict', f'{key_cpp}, {list_t}')
    grouped = temp_name('sel_grp')
    si = temp_name('si')
    elem_var = temp_name('sel_elem')
    key_var = temp_name('sel_key')
    bind_vars = _bind_cpp_vars(binds)
    key_expr = tr.visit(_rewrite_filter_elem(group.expr, elem_var, bind_vars))
    bucket_new = temp_name('sel_bucket_new')
    bucket = temp_name('sel_bucket')
    stmts = [f'{dict_t} {grouped};', f'for (int {si} = 0; {si} < {out}.__len__(); ++{si}) {{', f'auto& {elem_var} = {out}.__getitem__({si});', f'auto {key_var} = {key_expr};', f'if (!{grouped}.__contains__({key_var})) {{', f'{list_t} {bucket_new};', f'{grouped}.__setitem__({key_var}, {bucket_new});', '}', f'{list_t} {bucket} = {grouped}.__getitem__({key_var});', f'{bucket}.append({elem_var});', f'{grouped}.__setitem__({key_var}, {bucket});', '}']
    return (grouped, dict_t, stmts)

def _emit_count_stmts(tr: Translator, cur: str, cur_t: str, count: CountStep, elem_cpp: str, binds: dict[str, _EmitCtx], *, struct_info: ClassInfo | None, nav_env: dict, node: ast.AST | None) -> tuple[list[str], str]:
    if is_dict_type(cur_t):
        raise SelectorParseError('@group 后不支持 @count；按字段频数请用 @count(.field)')
    if count.expr is None:
        return ([f'return {cur}.__len__();'], cpp_ident('int'))
    key_cpp = _infer_elem_expr_cpp(tr, count.expr, struct_info, nav_env, node=node)
    out_t = cpp_template_type('Counter', key_cpp)
    out = temp_name('sel_freq')
    si = temp_name('si')
    elem_var = temp_name('sel_elem')
    key_var = temp_name('sel_key')
    bind_vars = _bind_cpp_vars(binds)
    key_expr = tr.visit(_rewrite_filter_elem(count.expr, elem_var, bind_vars))
    one = cpp_ident('1')
    return ([f'{out_t} {out};', f'for (int {si} = 0; {si} < {cur}.__len__(); ++{si}) {{', f'auto& {elem_var} = {cur}.__getitem__({si});', f'auto {key_var} = {key_expr};', f'if ({out}.__contains__({key_var})) {{', f'{out}.__setitem__({key_var}, {out}.__getitem__({key_var}) + {one});', '} else {', f'{out}.__setitem__({key_var}, {one});', '}', '}', f'return {out};'], out_t)

def _emit_post_stmts(tr: Translator, out: str, elem_cpp: str, post_steps: tuple, binds: dict[str, _EmitCtx], *, struct_info: ClassInfo | None, nav_env: dict, node: ast.AST | None) -> tuple[list[str], str, str]:
    """返回 ``(stmts, 结果变量名, 结果 C++ 类型)``；``@count`` 末步在 ``stmts`` 内含 ``return``。"""
    stmts: list[str] = []
    cur = out
    cur_t = cpp_template_type('list', elem_cpp)
    for step in post_steps:
        if isinstance(step, SortStep):
            stmts.extend(_emit_sort_stmts(tr, cur, step, binds))
        elif isinstance(step, GroupStep):
            grouped, dict_t, grp_stmts = _emit_group_stmts(tr, cur, elem_cpp, step, binds, struct_info=struct_info, nav_env=nav_env, node=node)
            stmts.extend(grp_stmts)
            cur = grouped
            cur_t = dict_t
        elif isinstance(step, CountStep):
            cnt_stmts, ret_t = _emit_count_stmts(tr, cur, cur_t, step, elem_cpp, binds, struct_info=struct_info, nav_env=nav_env, node=node)
            stmts.extend(cnt_stmts)
            return (stmts, '', ret_t)
    return (stmts, cur, cur_t)

def _bind_cpp_vars(binds: dict[str, _EmitCtx]) -> dict[str, str]:
    return {name: ctx.cpp for name, ctx in binds.items()}

def _emit_slice_loop(tr: Translator, out: str, ctx: _EmitCtx, lo: int | None, hi: int | None, step: int | None, rest: tuple, binds: dict[str, _EmitCtx]) -> list[str]:
    if not is_list_type(ctx.cpp_t):
        raise SelectorParseError('切片要求 list')
    lo_v = lo if lo is not None else 0
    hi_s = str(hi) if hi is not None else _list_len(tr, ctx.cpp, ctx.cpp_t)
    step_v = step if step is not None else 1
    si = temp_name('si')
    elem_var = temp_name('sel_elem')
    get = _list_getitem(tr, ctx.cpp, ctx.cpp_t, si)
    elem = list_elem_type(ctx.cpp_t)
    elem_t = elem.strip() if elem else ''
    sub = _EmitCtx(elem_var, elem_t, tr._class_info_for_type(strip_cpp_ref(elem_t)))
    inner = _emit_append_stmts(tr, out, sub, rest, binds)
    return [f'for (int {si} = {lo_v}; {si} < {hi_s}; {si} += {step_v}) {{', f'auto& {elem_var} = {get};', *inner, '}']

def _emit_nav_step(tr: Translator, ctx: _EmitCtx, step: object, binds: dict[str, _EmitCtx]) -> tuple[_EmitCtx, list[str]]:
    if isinstance(step, BindStep):
        decl, bound = _emit_bind_decl(step.name, ctx)
        binds[step.name] = bound
        return (ctx, [decl])
    if isinstance(step, RefStep):
        if step.name not in binds:
            raise SelectorParseError(f'引用未绑定 ${step.name!r}')
        return (binds[step.name], [])
    if isinstance(step, FieldStep):
        if step.optional and is_optional_type(ctx.cpp_t):
            inner_t = optional_inner_type(ctx.cpp_t)
            if not inner_t:
                raise SelectorParseError('无法解析 Optional 内部类型')
            inner_t = inner_t.strip()
            val_cpp = _optional_value_cpp(ctx.cpp, ctx.cpp_t)
            sub = _EmitCtx(val_cpp, inner_t, tr._class_info_for_type(strip_cpp_ref(inner_t)))
            nxt = _emit_field(tr, sub, FieldStep(step.name))
            cond = option_is_not_none_expr(ctx.cpp, ctx.cpp_t)
            return (nxt, _wrap_guard(cond, []))
        return (_emit_field(tr, ctx, step), [])
    if isinstance(step, IndexStep):
        if not is_list_type(ctx.cpp_t):
            raise SelectorParseError(f'下标 [{step.index}] 要求 list')
        elem = list_elem_type(ctx.cpp_t)
        elem_t = elem.strip() if elem else ''
        get = _list_getitem(tr, ctx.cpp, ctx.cpp_t, str(step.index))
        sub = _EmitCtx(get, elem_t, tr._class_info_for_type(strip_cpp_ref(elem_t)))
        if step.optional:
            cond = _list_index_guard(tr, ctx.cpp, ctx.cpp_t, step.index)
            return (sub, _wrap_guard(cond, []))
        return (sub, [])
    if isinstance(step, StrIndexStep):
        val_cpp, info = _dict_value_ctx(tr, _EmitCtx(ctx.cpp, ctx.cpp_t, ctx.info), node=None, what=f'下标 [{step.key!r}]')
        get = _dict_getitem(tr, ctx.cpp, ctx.cpp_t, step.key)
        sub = _EmitCtx(get, val_cpp, info)
        if step.optional:
            cond = _dict_key_guard(ctx.cpp, ctx.cpp_t, tr, step.key)
            return (sub, _wrap_guard(cond, []))
        return (sub, [])
    if isinstance(step, SliceStep):
        raise SelectorParseError('bind 前缀不支持单独切片步')
    if isinstance(step, MultiBracketStep):
        raise SelectorParseError('bind 前缀不支持多下标步')
    if isinstance(step, FilterStep):
        raise SelectorParseError('bind 前缀不支持过滤步')
    if isinstance(step, ProjectionStep):
        raise SelectorParseError('bind 前缀不支持投影步')
    if isinstance(step, DescendantStep):
        raise SelectorParseError('bind 前缀不支持递归下降步')
    raise SelectorParseError(f'未知 select 步: {step!r}')

def _emit_nav_steps(tr: Translator, ctx: _EmitCtx, steps: tuple, binds: dict[str, _EmitCtx]) -> tuple[_EmitCtx, list[str]]:
    stmts: list[str] = []
    for step in steps:
        ctx, part = _emit_nav_step(tr, ctx, step, binds)
        stmts.extend(part)
    return (ctx, stmts)

def _emit_append_stmts(tr: Translator, out: str, ctx: _EmitCtx, steps: tuple, binds: dict[str, _EmitCtx] | None=None) -> list[str]:
    binds = binds if binds is not None else {}
    if not steps:
        if is_list_type(ctx.cpp_t):
            si = temp_name('si')
            hi = _list_len(tr, ctx.cpp, ctx.cpp_t)
            get = _list_getitem(tr, ctx.cpp, ctx.cpp_t, si)
            return [f'for (int {si} = 0; {si} < {hi}; ++{si}) {{', f'{out}.append({get});', '}']
        return [f'{out}.append({ctx.cpp});']
    step = steps[0]
    rest = steps[1:]
    if isinstance(step, BindStep):
        decl, bound = _emit_bind_decl(step.name, ctx)
        binds[step.name] = bound
        tail = _emit_append_stmts(tr, out, ctx, rest, binds)
        return [decl, *tail]
    if isinstance(step, RefStep):
        if step.name not in binds:
            raise SelectorParseError(f'引用未绑定 ${step.name!r}')
        return _emit_append_stmts(tr, out, binds[step.name], rest, binds)
    if isinstance(step, FieldStep):
        if step.optional and is_optional_type(ctx.cpp_t):
            inner_t = optional_inner_type(ctx.cpp_t)
            if not inner_t:
                raise SelectorParseError('无法解析 Optional 内部类型')
            inner_t = inner_t.strip()
            val_cpp = _optional_value_cpp(ctx.cpp, ctx.cpp_t)
            sub = _EmitCtx(val_cpp, inner_t, tr._class_info_for_type(strip_cpp_ref(inner_t)))
            inner = _emit_append_stmts(tr, out, _emit_field(tr, sub, FieldStep(step.name)), rest, binds)
            return _wrap_guard(option_is_not_none_expr(ctx.cpp, ctx.cpp_t), inner)
        return _emit_append_stmts(tr, out, _emit_field(tr, ctx, step), rest, binds)
    if isinstance(step, IndexStep):
        if not is_list_type(ctx.cpp_t):
            raise SelectorParseError(f'下标 [{step.index}] 要求 list')
        elem = list_elem_type(ctx.cpp_t)
        elem_t = elem.strip() if elem else ''
        get = _list_getitem(tr, ctx.cpp, ctx.cpp_t, str(step.index))
        sub = _EmitCtx(get, elem_t, tr._class_info_for_type(strip_cpp_ref(elem_t)))
        inner = _emit_append_stmts(tr, out, sub, rest, binds)
        if step.optional:
            cond = _list_index_guard(tr, ctx.cpp, ctx.cpp_t, step.index)
            return _wrap_guard(cond, inner)
        return inner
    if isinstance(step, StrIndexStep):
        val_cpp, info = _dict_value_ctx(tr, _EmitCtx(ctx.cpp, ctx.cpp_t, ctx.info), node=None, what=f'下标 [{step.key!r}]')
        get = _dict_getitem(tr, ctx.cpp, ctx.cpp_t, step.key)
        sub = _EmitCtx(get, val_cpp, info)
        inner = _emit_append_stmts(tr, out, sub, rest, binds)
        if step.optional:
            cond = _dict_key_guard(ctx.cpp, ctx.cpp_t, tr, step.key)
            return _wrap_guard(cond, inner)
        return inner
    if isinstance(step, SliceStep):
        return _emit_slice_loop(tr, out, ctx, step.lo, step.hi, step.step, rest, binds)
    if isinstance(step, MultiBracketStep):
        if step.items and isinstance(step.items[0], StrIndexStep):
            val_cpp, info = _dict_value_ctx(tr, _EmitCtx(ctx.cpp, ctx.cpp_t, ctx.info), node=None, what='多字符串下标')
            stmts: list[str] = []
            for item in step.items:
                if not isinstance(item, StrIndexStep):
                    raise SelectorParseError('多字符串下标项须为字符串键')
                get = _dict_getitem(tr, ctx.cpp, ctx.cpp_t, item.key)
                sub = _EmitCtx(get, val_cpp, info)
                inner = _emit_append_stmts(tr, out, sub, rest, binds)
                if item.optional:
                    inner = _wrap_guard(_dict_key_guard(ctx.cpp, ctx.cpp_t, tr, item.key), inner)
                stmts.extend(inner)
            return stmts
        if not is_list_type(ctx.cpp_t):
            raise SelectorParseError('多下标要求 list')
        elem = list_elem_type(ctx.cpp_t)
        elem_t = elem.strip() if elem else ''
        info = tr._class_info_for_type(strip_cpp_ref(elem_t))
        stmts: list[str] = []
        for item in step.items:
            if isinstance(item, IndexStep):
                get = _list_getitem(tr, ctx.cpp, ctx.cpp_t, str(item.index))
                sub = _EmitCtx(get, elem_t, info)
                inner = _emit_append_stmts(tr, out, sub, rest, binds)
                if item.optional:
                    inner = _wrap_guard(_list_index_guard(tr, ctx.cpp, ctx.cpp_t, item.index), inner)
                stmts.extend(inner)
            else:
                stmts.extend(_emit_slice_loop(tr, out, ctx, item.lo, item.hi, item.step, rest, binds))
        return stmts
    if isinstance(step, FilterStep):
        if not is_list_type(ctx.cpp_t):
            raise SelectorParseError('过滤要求 list')
        elem = list_elem_type(ctx.cpp_t)
        elem_t = elem.strip() if elem else ''
        si = temp_name('si')
        elem_var = temp_name('sel_elem')
        hi = _list_len(tr, ctx.cpp, ctx.cpp_t)
        get = _list_getitem(tr, ctx.cpp, ctx.cpp_t, si)
        sub = _EmitCtx(elem_var, elem_t, tr._class_info_for_type(strip_cpp_ref(elem_t)))
        inner = _emit_append_stmts(tr, out, sub, rest, binds)
        bind_vars = _bind_cpp_vars(binds)
        cond = tr.visit(_rewrite_filter_elem(step.expr, elem_var, bind_vars))
        return [f'for (int {si} = 0; {si} < {hi}; ++{si}) {{', f'auto& {elem_var} = {get};', f'if ({cond}) {{', *inner, '}', '}']
    if isinstance(step, ProjectionStep):
        if ctx.info is None:
            raise SelectorParseError('投影要求 struct 上下文')
        stmts: list[str] = []
        for arm in step.arms:
            stmts.extend(_emit_append_stmts(tr, out, ctx, arm.steps + rest, binds))
        return stmts
    if isinstance(step, DescendantStep):
        paths = _collect_descendant_relative_paths(tr, ctx, step.field)
        if not paths:
            raise SelectorParseError(f'递归下降 ..{step.field!r} 未找到任何匹配字段')
        stmts: list[str] = []
        for rel in paths:
            stmts.extend(_emit_append_stmts(tr, out, ctx, rel + rest, binds))
        return stmts
    raise SelectorParseError(f'未知 select 步: {step!r}')

def _emit_select_expr(tr: Translator, recv: ast.expr, plan, result_ann: str, *, node: ast.AST | None=None) -> str:
    recv_info = class_info_from_receiver(tr, recv)
    recv_type = strip_cpp_ref(tr._infer_expr_cpp_type(recv) or (recv_info.cpp_name() if recv_info else ''))
    if not recv_type and recv_info is None:
        raise_translation_error(tr, node, 'select 接收者须为 dataclass 或 list')
    if recv_info is None and (not is_list_type(recv_type)):
        raise_translation_error(tr, node, 'select 接收者须为 dataclass 或 list')
    recv_cpp = tr.visit(recv)
    walk = walk_selector_plan(tr, recv, recv_type, recv_info, plan, node=node)
    _check_result_ann(tr, result_ann, walk.result_cpp, node=node)
    nav_env = _collect_nav_env(tr, recv_type, recv_info, plan, node=node)
    ctx = _EmitCtx(recv_cpp, recv_type, recv_info)
    out = temp_name('sel_out')
    binds: dict[str, _EmitCtx] = {}
    body: list[str] = []
    if isinstance(plan, SelectorChainPlan):
        _, nav_stmts = _emit_nav_steps(tr, ctx, plan.bind_prefix, binds)
        body.extend(nav_stmts)
        body.extend(_emit_append_stmts(tr, out, ctx, plan.steps, binds))
    else:
        body = _emit_append_stmts(tr, out, ctx, plan.steps)
    post_steps = plan.post_steps
    if not post_steps:
        return _emit_list_iife(tr, walk.result_cpp, body, out=out, list_elem_cpp=walk.elem_cpp)
    list_t = cpp_template_type('list', walk.elem_cpp)
    post_stmts, ret_var, ret_t = _emit_post_stmts(tr, out, walk.elem_cpp, post_steps, binds, struct_info=walk.struct_info, nav_env=nav_env, node=node)
    if ret_var:
        stmts = [f'{list_t} {out};', *body, *post_stmts, f'return {ret_var};']
    else:
        stmts = [f'{list_t} {out};', *body, *post_stmts]
    return emit_iife(walk.result_cpp, stmts)

def try_emit_select_call(tr: Translator, node: ast.Call) -> str | None:
    if not _is_select_call(node):
        return None
    try:
        plan = parse_selector_literal(node.args[0].value)
    except SelectorParseError as e:
        raise_translation_error(tr, node, str(e))
    return _emit_select_expr(tr, node.func.value, plan, '', node=node)

def try_emit_select_ann_assign(tr: Translator, node: ast.AnnAssign) -> bool:
    if node.value is None or not _is_select_call(node.value):
        return False
    if not isinstance(node.target, ast.Name):
        raise_translation_error(tr, node, 'select 赋值目标首版仅支持简单变量名')
    try:
        plan = parse_selector_literal(node.value.args[0].value)
    except SelectorParseError as e:
        raise_translation_error(tr, node, str(e))
    result_ann = _parse_type_ann(tr, node.annotation)
    val = _emit_select_expr(tr, node.value.func.value, plan, result_ann, node=node)
    name = node.target.id
    if tr._try_declare(name):
        tr.write_line(f'{result_ann} {cpp_ident(name)} = {val};')
    else:
        tr.write_line(f'{cpp_ident(name)} = {val};')
    if tr.scope:
        bind_scope_var(tr.scope, name, result_ann, classes=tr.classes)
    return True
