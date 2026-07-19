"""``Type.build("…")`` / ``list[T].build("…")`` 译期内联。"""
from __future__ import annotations
import ast
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from .iife_emit import emit_iife
from ..analysis.build_types import build_result_cpp_type, walk_build_plan
from ..analysis.type_emit import field_ann_ast, field_storage_cpp, bind_scope_var
from ..analysis.type_pred import is_list_type
from ..analysis.type_extract import list_elem_type
from ..analysis.ir import ClassInfo, cpp_inferred_type_matches_ann, cpp_ident, cpp_template_type, strip_cpp_ref
from ..analysis.module_namespace import qualify_symbol_in_module
from ..passes.build_parse import BUILD_INDEX_PREFIX, AssignSegment, BuildBody, BuildPlan, BuildValue, BuildParseError, ExprValue, IndexRefValue, ListDescentSegment, ListRootPlan, LiteralValue, StructDescentSegment, StructRootPlan, parse_build_literal
from ..translation_error import raise_translation_error
from ..translator import temp_name
from .call_emit import class_info_from_receiver
if TYPE_CHECKING:
    from ..translator import Translator
_BUILD_NAME = 'build'

@dataclass
class _EmitCtx:
    cpp: str
    cpp_t: str
    info: ClassInfo | None

def _is_build_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (node.func.attr == _BUILD_NAME) and (len(node.args) == 1) and (not node.keywords) and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)

def _access_sep(tr: Translator, cpp_type: str) -> str:
    return '->' if tr._uses_ptr_access(cpp_type) else '.'

def _field_member(tr: Translator, info: ClassInfo, field: str) -> str:
    return tr._member_cpp_name(info, field)

def _field_access(tr: Translator, ctx: _EmitCtx, field: str) -> _EmitCtx:
    if ctx.info is None:
        raise BuildParseError(f'字段 {field!r} 无 struct 上下文')
    member = _field_member(tr, ctx.info, field)
    sep = _access_sep(tr, ctx.cpp_t)
    cpp = f'{ctx.cpp}{sep}{member}'
    cpp_t = field_storage_cpp(ctx.info, field)
    if not cpp_t:
        ann = field_ann_ast(ctx.info, field)
        cpp_t = tr._parse_type(ann, ctx.info.type_params) if ann else ''
    info = tr._class_info_for_type(strip_cpp_ref(cpp_t))
    return _EmitCtx(cpp, cpp_t, info)

def _resolve_build_target(tr: Translator, recv: ast.expr, *, node: ast.AST | None=None) -> tuple[str, ClassInfo | None, bool] | None:
    """返回 ``(result_cpp, struct_info|None, list_root)``。"""
    match recv:
        case ast.Name(id=name):
            info = tr._class_info_for_ref(name)
            if info is None:
                return None
            cpp = info.cpp_name()
            if info.module_path and tr._is_stdlib_module(info.module_path):
                cpp = qualify_symbol_in_module(info.module_path, cpp)
            return (cpp, info, False)
        case ast.Subscript(value=ast.Name(id='list'), slice=sl):
            elem_t = tr._parse_type_args(sl, tr._active_type_params())
            if not elem_t:
                raise_translation_error(tr, node, 'list[T].build 须显式元素类型')
            return (cpp_template_type('list', elem_t), None, True)
        case _:
            info = class_info_from_receiver(tr, recv)
            if info is not None:
                cpp = info.cpp_name()
                if info.module_path and tr._is_stdlib_module(info.module_path):
                    cpp = qualify_symbol_in_module(info.module_path, cpp)
                return (cpp, info, False)
    return None

def _make_default_expr(tr: Translator, cpp_t: str, info: ClassInfo | None=None) -> str:
    from ..emit.builtin_call_emit import emit_user_ctor
    from ..passes.kwargs_options import _default_ctor_args
    elem = list_elem_type(cpp_t)
    if elem is not None:
        return f"{cpp_template_type('list', elem)}()"
    if info is not None:
        args = _default_ctor_args(tr, info.name)
        if args:
            arg_str = ', '.join((tr._visit_value_expr(a) for a in args))
            return emit_user_ctor(tr, info.name, arg_str)
        return emit_user_ctor(tr, info.name, '')
    bare = strip_cpp_ref(cpp_t)
    if bare == cpp_ident('str'):
        return f"{cpp_ident('str')}()"
    return f'{bare}()'

def _rewrite_expr_index(expr: ast.expr, index_env: dict[str, str]) -> ast.expr:

    class Rewriter(ast.NodeTransformer):

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id.startswith(BUILD_INDEX_PREFIX):
                bind_name = node.id[len(BUILD_INDEX_PREFIX):]
                if bind_name in index_env:
                    return ast.Name(id=index_env[bind_name], ctx=ast.Load())
            return node
    return ast.fix_missing_locations(Rewriter().visit(copy.deepcopy(expr)))

def _literal_to_ast(lit: LiteralValue) -> ast.expr:
    if lit.kind == 'str':
        return ast.Constant(value=lit.value)
    if lit.kind == 'int':
        return ast.Constant(value=lit.value)
    if lit.kind == 'bool':
        return ast.Constant(value=lit.value)
    if lit.kind == 'none':
        return ast.Constant(value=None)
    raise BuildParseError(f'未知字面量: {lit!r}')

def _emit_value(tr: Translator, value: BuildValue, target_t: str, index_env: dict[str, str]) -> str:
    if isinstance(value, IndexRefValue):
        if value.name not in index_env:
            raise BuildParseError(f'${value.name!r} 未绑定')
        return index_env[value.name]
    if isinstance(value, LiteralValue):
        raw = tr._visit_value_expr(_literal_to_ast(value))
        return tr._coerce_expr_to_cpp_type(raw, target_t) if target_t else raw
    if isinstance(value, ExprValue):
        expr = _rewrite_expr_index(value.expr, index_env)
        raw = tr._visit_value_expr(expr)
        if target_t:
            return tr._coerce_expr_to_cpp_type(raw, target_t, rhs_node=expr)
        return raw
    raise BuildParseError(f'未知 build 值: {value!r}')

def _emit_assign(tr: Translator, ctx: _EmitCtx, seg: AssignSegment, index_env: dict[str, str]) -> str:
    target = _field_access(tr, ctx, seg.field)
    val = _emit_value(tr, seg.value, strip_cpp_ref(target.cpp_t), index_env)
    return f'{target.cpp} = {val};'

def _emit_list_loop(tr: Translator, list_cpp: str, list_t: str, count: int, index_bind: str | None, body: BuildBody, index_env: dict[str, str]) -> list[str]:
    elem_t = list_elem_type(list_t) or ''
    elem_info = tr._class_info_for_type(strip_cpp_ref(elem_t))
    loop_var = temp_name('bi') if index_bind is None else cpp_ident(index_bind)
    elem_var = temp_name('be')
    loop_env = dict(index_env)
    if index_bind is not None:
        loop_env[index_bind] = loop_var
    elem_ctx = _EmitCtx(elem_var, elem_t, elem_info)
    inner: list[str] = []
    for seg in body.segments:
        inner.extend(_emit_segment_stmts(tr, elem_ctx, seg, loop_env))
    return [f'for (int {loop_var} = 0; {loop_var} < {count}; ++{loop_var}) {{', f'{elem_t} {elem_var} = {_make_default_expr(tr, elem_t, elem_info)};', *inner, f'{list_cpp}.append({elem_var});', '}']

def _emit_segment_stmts(tr: Translator, ctx: _EmitCtx, seg: AssignSegment | StructDescentSegment | ListDescentSegment, index_env: dict[str, str]) -> list[str]:
    if isinstance(seg, AssignSegment):
        return [_emit_assign(tr, ctx, seg, index_env)]
    if isinstance(seg, StructDescentSegment):
        child = _field_access(tr, ctx, seg.field)
        stmts: list[str] = []
        for sub in seg.body.segments:
            stmts.extend(_emit_segment_stmts(tr, child, sub, index_env))
        return stmts
    if isinstance(seg, ListDescentSegment):
        child = _field_access(tr, ctx, seg.field)
        if not is_list_type(child.cpp_t):
            raise BuildParseError(f'{seg.field!r} 不是 list')
        return _emit_list_loop(tr, child.cpp, child.cpp_t, seg.count, seg.index_bind, seg.body, index_env)
    raise BuildParseError(f'未知 build 段: {seg!r}')

def _emit_body_stmts(tr: Translator, ctx: _EmitCtx, body: BuildBody, index_env: dict[str, str]) -> list[str]:
    stmts: list[str] = []
    for seg in body.segments:
        stmts.extend(_emit_segment_stmts(tr, ctx, seg, index_env))
    return stmts

def _emit_struct_iife(tr: Translator, cpp_t: str, body_stmts: list[str]) -> str:
    ret = temp_name('build_ret')
    new = _make_default_expr(tr, cpp_t)
    stmts = [f'{cpp_t} {ret} = {new};', *body_stmts, f'return {ret};']
    return emit_iife(cpp_t, stmts)

def _emit_list_root_iife(tr: Translator, list_t: str, plan: ListRootPlan) -> str:
    out = temp_name('build_out')
    elem_t = list_elem_type(list_t) or ''
    elem_info = tr._class_info_for_type(strip_cpp_ref(elem_t))
    env: dict[str, str] = {}
    if plan.index_bind is not None:
        env[plan.index_bind] = cpp_ident(plan.index_bind)
    elem_ctx = _EmitCtx('', elem_t, elem_info)
    body_stmts = _emit_list_loop(tr, out, list_t, plan.count, plan.index_bind, plan.body, env)
    stmts = [f'{list_t} {out};', *body_stmts, f'return {out};']
    return emit_iife(list_t, stmts)

def _emit_build_expr(tr: Translator, target_cpp: str, target_info: ClassInfo | None, list_root: bool, plan: BuildPlan, result_ann: str, *, node: ast.AST | None=None) -> str:
    walk_build_plan(tr, plan, target_cpp, target_info, node=node)
    expected = build_result_cpp_type(target_cpp)
    ann = result_ann.strip()
    if ann and not cpp_inferred_type_matches_ann(expected, ann):
        raise_translation_error(tr, node, f'build 返回 {expected}；期望注解 {ann}')
    if isinstance(plan, ListRootPlan):
        return _emit_list_root_iife(tr, target_cpp, plan)
    if isinstance(plan, StructRootPlan):
        ctx = _EmitCtx(temp_name('build_root'), target_cpp, target_info)
        new = _make_default_expr(tr, target_cpp, target_info)
        ret = temp_name('build_ret')
        stmts = [f'{target_cpp} {ret} = {new};', *_emit_body_stmts(tr, _EmitCtx(ret, target_cpp, target_info), plan.body, {}), f'return {ret};']
        return emit_iife(target_cpp, stmts)
    raise BuildParseError(f'未知 build plan: {plan!r}')

def try_emit_build_call(tr: Translator, node: ast.Call) -> str | None:
    if not _is_build_call(node):
        return None
    target = _resolve_build_target(tr, node.func.value, node=node)
    if target is None:
        return None
    target_cpp, target_info, list_root = target
    try:
        plan = parse_build_literal(node.args[0].value, list_root=list_root)
    except BuildParseError as e:
        raise_translation_error(tr, node, str(e))
    return _emit_build_expr(tr, target_cpp, target_info, list_root, plan, '', node=node)

def try_emit_build_ann_assign(tr: Translator, node: ast.AnnAssign) -> bool:
    if node.value is None or not _is_build_call(node.value):
        return False
    if not isinstance(node.target, ast.Name):
        raise_translation_error(tr, node, 'build 赋值目标首版仅支持简单变量名')
    target = _resolve_build_target(tr, node.value.func.value, node=node)
    if target is None:
        return False
    target_cpp, target_info, list_root = target
    try:
        plan = parse_build_literal(node.value.args[0].value, list_root=list_root)
    except BuildParseError as e:
        raise_translation_error(tr, node, str(e))
    result_ann = tr._parse_type(node.annotation, tr._active_type_params()).strip()
    val = _emit_build_expr(tr, target_cpp, target_info, list_root, plan, result_ann, node=node)
    name = node.target.id
    if tr._try_declare(name):
        tr.write_line(f'{result_ann} {cpp_ident(name)} = {val};')
    else:
        tr.write_line(f'{cpp_ident(name)} = {val};')
    if tr.scope:
        bind_scope_var(tr.scope, name, result_ann, classes=tr.classes)
    return True
