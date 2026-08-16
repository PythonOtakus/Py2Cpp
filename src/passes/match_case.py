"""``match`` / ``case`` 翻译（字面量、``_``、捕获、静态类模式、字段注解模式）。"""
from __future__ import annotations
import ast
import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from ..analysis.type_emit import field_ann_ast, bind_scope_var
from ..analysis.type_pred import is_char_type, is_int_type, is_optional_type, is_str_type
from ..analysis.ir import ClassInfo, class_info_for_cpp_type, cpp_ident, cpp_template_inner_args, format_cpp_int, is_const_type_annotation, is_optional_type_annotation, is_ref_type_annotation, primary_field_annotation_class, quote_cpp_string, split_cpp_template_args, str_cpp_from_literal, _TYPE_ANNOTATION_METADATA_MARKERS
from ..analysis.patterns import property_getter_method_for
from .kwargs_options import _matchable_member_names, _skip_class, _validate_match_field_names
from .static_reflect import StaticReflectFolder, static_field_name
from .union_expand import parse_union_case_pattern, union_info_from_subject_cpp
from .optional_match import check_optional_match_exhaustive, is_optional_union_info, optional_pattern_to_match
from .union_match import UnionMatchArm, _pattern_for_union_case, check_union_match_exhaustive, partition_union_match_cases
if TYPE_CHECKING:
    from ..translator import Translator

@dataclass
class PatternMatch:
    condition: str | None
    bindings: list[ast.stmt] = field(default_factory=list)
    prelude_lines: list[str] = field(default_factory=list)
    is_wildcard: bool = False

def iter_field_annotation_calls(ann: ast.expr | None) -> list[tuple[str, ast.Call | None]]:
    """``T @A(...) @B`` / ``T @B`` → 自外向内 ``[(B, call|None), ...]``。"""
    out: list[tuple[str, ast.Call | None]] = []
    cur = ann
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.MatMult):
        right = cur.right
        if isinstance(right, ast.Call) and isinstance(right.func, ast.Name):
            out.append((right.func.id, right))
        elif isinstance(right, ast.Name):
            out.append((right.id, None))
        cur = cur.left
    return out

def field_annotation_markers_from_ann(ann: ast.expr | None) -> list[str]:
    return [name for name, _call in iter_field_annotation_calls(ann) if name not in _TYPE_ANNOTATION_METADATA_MARKERS]

def field_base_type_from_ann(ann: ast.expr | None) -> ast.expr | None:
    """``T @Meta(...) @optional`` → ``T``。

    ``Self.get_field_type`` 返回字段的基础类型，不暴露 ``@annotation`` 或内建存储
    标记；字段类型仍由后续分析器按通常规则解析。
    """
    if ann is None:
        return None
    out = copy.deepcopy(ann)
    while isinstance(out, ast.BinOp) and isinstance(out.op, ast.MatMult):
        out = out.left
    return out

def fold_self_get_field_type_calls(
    stmts: list[ast.stmt],
    ann_for_field,
    *,
    known_fields: frozenset[str],
) -> list[ast.stmt]:
    """折叠 ``Self.get_field_type('field')`` 为字段基础类型 AST。"""
    class _GetTypeFolder(ast.NodeTransformer):
        def _query(self, node: ast.expr) -> ast.expr | None:
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'Self'
                and node.func.attr == 'get_field_type'
                and len(node.args) == 1
                and not node.keywords
            ):
                return None
            field = static_field_name(node.args[0])
            if field is None or field not in known_fields:
                raise ValueError('Self.get_field_type 的字段须属于当前类且在翻译期可确定')
            base = field_base_type_from_ann(ann_for_field(field))
            if base is None:
                raise ValueError(f'Self.get_field_type 无法取得字段类型: {field}')
            return base

        def visit_Compare(self, node: ast.Compare) -> ast.expr:
            if len(node.ops) == 1 and len(node.comparators) == 1:
                left = self._query(node.left)
                right = self._query(node.comparators[0])
                if left is not None or right is not None:
                    lhs = left if left is not None else node.left
                    rhs = right if right is not None else node.comparators[0]
                    same = ast.dump(lhs, include_attributes=False) == ast.dump(rhs, include_attributes=False)
                    if isinstance(node.ops[0], (ast.Is, ast.Eq)):
                        return ast.Constant(value=same)
                    if isinstance(node.ops[0], (ast.IsNot, ast.NotEq)):
                        return ast.Constant(value=not same)
            return self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> ast.expr:
            base = self._query(node)
            if base is not None:
                return ast.copy_location(base, node)
            return self.generic_visit(node)

    folder = _GetTypeFolder()
    return [folder.visit(copy.deepcopy(stmt)) for stmt in stmts]

def _annotation_kwargs_from_call(class_name: str, call: ast.Call) -> dict[str, str]:
    out: dict[str, str] = {}
    if class_name == 'UILabelMeta' and call.args:
        arg0 = call.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            out['label'] = arg0.value
    if class_name == 'UISliderMeta':
        if len(call.args) >= 1:
            lo = call.args[0]
            if isinstance(lo, ast.Constant) and isinstance(lo.value, int):
                out['slider_lo'] = str(lo.value)
        if len(call.args) >= 2:
            hi = call.args[1]
            if isinstance(hi, ast.Constant) and isinstance(hi.value, int):
                out['slider_hi'] = str(hi.value)
    for kw in call.keywords:
        if not kw.arg or not isinstance(kw.value, ast.Constant):
            continue
        val = kw.value.value
        if isinstance(val, str):
            out[kw.arg] = val
        elif isinstance(val, int):
            out[kw.arg] = str(val)
    return out

def merged_field_annotation_kwargs(ann: ast.expr | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for class_name, call in iter_field_annotation_calls(ann):
        if call is not None:
            merged.update(_annotation_kwargs_from_call(class_name, call))
    return merged

def _annotation_rename_expr(key: str, value: str) -> ast.expr:
    if key in ('slider_lo', 'slider_hi'):
        return ast.Constant(value=int(value))
    return ast.Constant(value=value)

def annotation_kwargs_from_expr(ann_expr: ast.expr | None) -> dict[str, str]:
    return merged_field_annotation_kwargs(ann_expr)
_ANNOTATION_MATCH_PRIORITY: tuple[str, ...] = ('UIInvisibleMeta', 'UISliderMeta')

def resolve_field_annotation_match(markers: list[str], ann_cases: dict[str, list[ast.stmt]]) -> str | None:
    for name in _ANNOTATION_MATCH_PRIORITY:
        if name in markers and name in ann_cases:
            return name
    return None

def extract_field_annotation_meta(info: ClassInfo) -> None:
    for field_name in list(info.fields):
        ann = field_ann_ast(info, field_name)
        if is_const_type_annotation(ann) or is_optional_type_annotation(ann) or is_ref_type_annotation(ann):
            continue
        markers = field_annotation_markers_from_ann(ann)
        if not markers:
            continue
        info.field_annotation_markers[field_name] = markers
        ann_class = primary_field_annotation_class(ann)
        if ann_class:
            info.field_annotations[field_name] = ann_class
        info.field_annotation_kwargs[field_name] = merged_field_annotation_kwargs(ann)

def _fields_loop_call(node: ast.expr) -> tuple[str, str] | None:
    """``Self/Vec.iter_fields(…)`` / ``enum_fields(…)`` → ``(接收者名, 方法名)``。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and (node.func.attr in ('iter_fields', 'iterFields', 'enum_fields', 'enumFields')):
        return (node.func.value.id, node.func.attr)
    return None

def _iter_fields_receiver(node: ast.expr) -> str | None:
    info = _fields_loop_call(node)
    if info is not None and info[1] in ('iter_fields', 'iterFields'):
        return info[0]
    return None

def _enum_fields_receiver(node: ast.expr) -> str | None:
    info = _fields_loop_call(node)
    if info is not None and info[1] == 'enum_fields':
        return info[0]
    return None

def _is_iter_fields_call(node: ast.expr) -> bool:
    return _iter_fields_receiver(node) == 'Self'

def _is_any_iter_fields_call(node: ast.expr) -> bool:
    return _iter_fields_receiver(node) is not None

def _is_any_enum_fields_call(node: ast.expr) -> bool:
    return _enum_fields_receiver(node) is not None

def _is_any_fields_loop_call(node: ast.expr) -> bool:
    return _fields_loop_call(node) is not None

def _parse_fields_loop_options(node: ast.expr):
    """``*.iter_fields|enum_fields([public_only=…, mro=…])`` → 选项。"""
    from .annotation_options import IterReflectOptions, parse_self_iter_call_options
    if _fields_loop_call(node) is None:
        return None
    return parse_self_iter_call_options(node, allowed=frozenset({'public_only', 'publicOnly', 'mro', 'glob'}), label='iter_fields / enum_fields')

def _parse_fields_loop_public_only(node: ast.expr) -> bool | None:
    """``*.iter_fields|enum_fields([public_only=…])`` → 是否仅公有字段。"""
    opts = _parse_fields_loop_options(node)
    if opts is None:
        return None
    return opts.public_only

def _parse_iter_fields_public_only(node: ast.expr) -> bool | None:
    if _iter_fields_receiver(node) is None:
        return None
    return _parse_fields_loop_public_only(node)

def _host_iter_field_names(host: ClassInfo, *, public_only: bool) -> list[str]:
    if not public_only:
        return list(host.fields)
    skip = frozenset(host.properties) | host.field_properties | host.postsetter_properties
    return [name for name in host.fields if not name.startswith('_') and name not in skip]

def _iter_fields_class_info(receiver: str, host: ClassInfo, type_hosts: dict[str, ClassInfo]) -> ClassInfo:
    if receiver == 'Self':
        return host
    ci = type_hosts.get(receiver)
    if ci is None:
        raise NotImplementedError(f'iter_fields 接收者 {receiver!r} 未绑定 ClassInfo')
    return ci

def _resolve_iter_fields_names(receiver: str, host: ClassInfo, type_hosts: dict[str, ClassInfo], *, public_only: bool, mro: bool=False, glob: str | None=None, all_classes: dict[str, ClassInfo] | None=None) -> list[str]:
    from .annotation_options import collect_iter_field_names
    ci = _iter_fields_class_info(receiver, host, type_hosts)
    classes = all_classes if all_classes is not None else type_hosts
    return collect_iter_field_names(ci, classes, public_only=public_only, mro=mro, glob=glob, host_iter_field_names=_host_iter_field_names)

def _field_index_increment_var(body: list[ast.stmt]) -> str | None:
    """循环体末尾 ``idx += 1`` → ``idx`` 名（与 ``Vec.iter_fields`` 列/行下标联用）。"""
    if not body:
        return None
    last = body[-1]
    if isinstance(last, ast.AugAssign) and isinstance(last.target, ast.Name) and isinstance(last.op, ast.Add) and isinstance(last.value, ast.Constant) and (last.value.value == 1):
        return last.target.id
    return None

def _strip_field_index_increment(body: list[ast.stmt], idx_var: str | None) -> list[ast.stmt]:
    if idx_var is None or not body:
        return body
    last = body[-1]
    if isinstance(last, ast.AugAssign) and isinstance(last.target, ast.Name) and (last.target.id == idx_var):
        return body[:-1]
    return body

def _guard_continue_for_unroll(stmts: list[ast.stmt]) -> list[ast.stmt]:
    """``iter_fields`` 展开前：``if c: continue`` + 后续 → ``if not c: …``。"""
    out: list[ast.stmt] = []
    i = 0
    while i < len(stmts):
        stmt = stmts[i]
        if isinstance(stmt, ast.If) and len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Continue) and (not stmt.orelse):
            rest = _guard_continue_for_unroll(stmts[i + 1:])
            if rest:
                out.append(ast.If(test=ast.UnaryOp(op=ast.Not(), operand=copy.deepcopy(stmt.test)), body=rest, orelse=[]))
            break
        stmt_copy = copy.deepcopy(stmt)
        if isinstance(stmt_copy, ast.If):
            stmt_copy.body = _guard_continue_for_unroll(stmt_copy.body)
            stmt_copy.orelse = _guard_continue_for_unroll(stmt_copy.orelse)
        elif isinstance(stmt_copy, (ast.For, ast.While)):
            stmt_copy.body = _guard_continue_for_unroll(stmt_copy.body)
            stmt_copy.orelse = _guard_continue_for_unroll(stmt_copy.orelse)
        out.append(stmt_copy)
        i += 1
    return out

def _expand_iter_fields_in_stmts(stmts: list[ast.stmt], host: ClassInfo, type_hosts: dict[str, ClassInfo], *, all_classes: dict[str, ClassInfo] | None=None) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for stmt in stmts:
        if isinstance(stmt, ast.For):
            loop = _fields_loop_call(stmt.iter)
            if loop is not None:
                receiver, kind = loop
                loop_opts = _parse_fields_loop_options(stmt.iter)
                assert loop_opts is not None
                field_names = _resolve_iter_fields_names(receiver, host, type_hosts, public_only=loop_opts.public_only, mro=loop_opts.mro, glob=loop_opts.glob, all_classes=all_classes)
                fields_ci = _iter_fields_class_info(receiver, host, type_hosts)
                known = frozenset(fields_ci.fields)
                if kind == 'enum_fields':
                    if not isinstance(stmt.target, ast.Tuple) or len(stmt.target.elts) != 2:
                        raise NotImplementedError('enum_fields 循环目标须为 ``for i, f in …``')
                    idx_node, field_node = stmt.target.elts
                    if not isinstance(idx_node, ast.Name) or not isinstance(field_node, ast.Name):
                        raise NotImplementedError('enum_fields 循环变量须为简单名')
                    idx_var = idx_node.id
                    field_var = field_node.id
                    for field_idx, field_name in enumerate(field_names):
                        renames: dict[str, ast.expr] = {field_var: ast.Constant(value=field_name), idx_var: ast.Constant(value=field_idx)}
                        cloned = _clone_body_replace_names(stmt.body, renames, known_fields=known)
                        cloned = fold_self_get_field_type_calls(
                            cloned,
                            lambda name: field_ann_ast(fields_ci, name),
                            known_fields=known,
                        )
                        out.extend(_expand_iter_fields_in_stmts(cloned, host, type_hosts, all_classes=all_classes))
                    continue
                if not isinstance(stmt.target, ast.Name):
                    raise NotImplementedError('iter_fields 循环变量须为简单名')
                field_var = stmt.target.id
                idx_var = _field_index_increment_var(stmt.body)
                body_wo_inc = _strip_field_index_increment(stmt.body, idx_var)
                body_wo_inc = _guard_continue_for_unroll(body_wo_inc)
                for field_idx, field_name in enumerate(field_names):
                    renames = {field_var: ast.Constant(value=field_name)}
                    if idx_var is not None:
                        renames[idx_var] = ast.Constant(value=field_idx)
                    cloned = _clone_body_replace_names(body_wo_inc, renames, known_fields=known)
                    cloned = fold_self_get_field_type_calls(
                        cloned,
                        lambda name: field_ann_ast(fields_ci, name),
                        known_fields=known,
                    )
                    out.extend(_expand_iter_fields_in_stmts(cloned, host, type_hosts, all_classes=all_classes))
                continue
            stmt = copy.deepcopy(stmt)
            stmt.body = _expand_iter_fields_in_stmts(stmt.body, host, type_hosts, all_classes=all_classes)
            stmt.orelse = _expand_iter_fields_in_stmts(stmt.orelse, host, type_hosts, all_classes=all_classes)
            out.append(stmt)
            continue
        if isinstance(stmt, ast.While):
            stmt = copy.deepcopy(stmt)
            stmt.body = _expand_iter_fields_in_stmts(stmt.body, host, type_hosts, all_classes=all_classes)
            stmt.orelse = _expand_iter_fields_in_stmts(stmt.orelse, host, type_hosts, all_classes=all_classes)
            out.append(stmt)
            continue
        if isinstance(stmt, ast.If):
            stmt = copy.deepcopy(stmt)
            stmt.body = _expand_iter_fields_in_stmts(stmt.body, host, type_hosts, all_classes=all_classes)
            stmt.orelse = _expand_iter_fields_in_stmts(stmt.orelse, host, type_hosts, all_classes=all_classes)
            out.append(stmt)
            continue
        if isinstance(stmt, ast.With):
            stmt = copy.deepcopy(stmt)
            for item in stmt.body:
                item.body = _expand_iter_fields_in_stmts(item.body, host, type_hosts, all_classes=all_classes)
            out.append(stmt)
            continue
        if isinstance(stmt, ast.Try):
            stmt = copy.deepcopy(stmt)
            stmt.body = _expand_iter_fields_in_stmts(stmt.body, host, type_hosts, all_classes=all_classes)
            for handler in stmt.handlers:
                handler.body = _expand_iter_fields_in_stmts(handler.body, host, type_hosts, all_classes=all_classes)
            stmt.orelse = _expand_iter_fields_in_stmts(stmt.orelse, host, type_hosts, all_classes=all_classes)
            stmt.finalbody = _expand_iter_fields_in_stmts(stmt.finalbody, host, type_hosts, all_classes=all_classes)
            out.append(stmt)
            continue
        if isinstance(stmt, ast.Match):
            stmt = copy.deepcopy(stmt)
            for case in stmt.cases:
                case.body = _expand_iter_fields_in_stmts(case.body, host, type_hosts, all_classes=all_classes)
            out.append(stmt)
            continue
        out.append(copy.deepcopy(stmt))
    return out

def expand_iter_fields_loops(method: ast.FunctionDef, host: ClassInfo, *, type_hosts: dict[str, ClassInfo] | None=None, all_classes: dict[str, ClassInfo] | None=None) -> ast.FunctionDef | None:
    """``for f in Self/TypeParam.iter_fields(…):`` / ``for i, f in …enum_fields(…):`` 递归译期展开。"""
    type_hosts = type_hosts or {}
    has_iter = any((isinstance(node, ast.For) and _is_any_fields_loop_call(node.iter) for node in ast.walk(method)))
    if not has_iter:
        return None
    new_body = _expand_iter_fields_in_stmts(method.body, host, type_hosts, all_classes=all_classes)
    out = copy.deepcopy(method)
    out.body = new_body
    ast.fix_missing_locations(out)
    return out

def _parse_get_field_annotation_assign(stmt: ast.stmt) -> str | None:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Name):
        return None
    val = stmt.value
    if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute) and isinstance(val.func.value, ast.Name) and (val.func.value.id == 'Self') and (val.func.attr in ('get_field_annotation', 'getFieldAnnotation')) and (len(val.args) == 1) and isinstance(val.args[0], ast.Name)):
        return None
    return val.args[0].id

def _clone_body_replace_names(body: list[ast.stmt], renames: dict[str, ast.expr], *, known_fields: frozenset[str] | None=None) -> list[ast.stmt]:

    class _Renamer(ast.NodeTransformer):

        def visit_Name(self, node: ast.Name) -> ast.expr:
            if isinstance(node.ctx, ast.Load) and node.id in renames:
                return copy.deepcopy(renames[node.id])
            return node
    out = [_Renamer().visit(copy.deepcopy(s)) for s in body]
    folder = StaticReflectFolder(known_fields)
    return [folder.visit(s) for s in out]

def _annotation_case_body(match_node: ast.Match) -> tuple[dict[str, list[ast.stmt]], list[ast.stmt] | None]:
    ann_cases: dict[str, list[ast.stmt]] = {}
    default_body: list[ast.stmt] | None = None
    for case in match_node.cases:
        if case.guard is not None:
            raise NotImplementedError('注解 match 暂不支持 case guard')
        if is_wildcard_pattern(case.pattern):
            default_body = case.body
            continue
        if not isinstance(case.pattern, ast.MatchClass) or not isinstance(case.pattern.cls, ast.Name):
            raise NotImplementedError('注解 match 仅支持 ``case AnnClass(...)`` 与 ``case _``')
        ann_cases[case.pattern.cls.id] = case.body
    if default_body is None:
        raise ValueError('match 缺少 ``case _`` 默认分支')
    return (ann_cases, default_body)

def expand_str_annotation_match(method: ast.FunctionDef, host: ClassInfo) -> ast.FunctionDef | None:
    for_idx: int | None = None
    for i, stmt in enumerate(method.body):
        if isinstance(stmt, ast.For) and _is_iter_fields_call(stmt.iter):
            for_idx = i
            break
    if for_idx is None:
        return None
    for_node = method.body[for_idx]
    if len(for_node.body) < 2:
        return None
    field_var = _parse_get_field_annotation_assign(for_node.body[0])
    if field_var is None:
        return None
    if not isinstance(for_node.body[1], ast.Match):
        return None
    ann_cases, default_body = _annotation_case_body(for_node.body[1])
    extract_field_annotation_meta(host)
    loop_opts = _parse_fields_loop_options(for_node.iter)
    assert loop_opts is not None
    field_names = _resolve_iter_fields_names('Self', host, {}, public_only=loop_opts.public_only, mro=False, glob=loop_opts.glob)
    fields = frozenset(host.fields)
    unrolled: list[ast.stmt] = []
    for field_name in field_names:
        ann_ast = field_ann_ast(host, field_name)
        markers = field_annotation_markers_from_ann(ann_ast)
        kwargs = dict(host.field_annotation_kwargs.get(field_name, {}))
        if not kwargs:
            kwargs = merged_field_annotation_kwargs(ann_ast)
        if 'alias' not in kwargs:
            kwargs['alias'] = field_name
        renames: dict[str, ast.expr] = {field_var: ast.Constant(value=field_name), **{k: _annotation_rename_expr(k, v) for k, v in kwargs.items()}}
        matched = resolve_field_annotation_match(markers, ann_cases)
        if matched is not None:
            unrolled.extend(_clone_body_replace_names(ann_cases[matched], renames, known_fields=fields))
        else:
            unrolled.extend(_clone_body_replace_names(default_body, renames, known_fields=fields))
    out = copy.deepcopy(method)
    out.body = method.body[:for_idx] + unrolled + method.body[for_idx + 1:]
    return out

def _meta_name_from_subscript(sl: ast.expr) -> str | None:
    if isinstance(sl, ast.Name):
        return sl.id
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    return None

def parse_self_get_field_annotation_meta(node: ast.expr) -> tuple[str, ast.expr] | None:
    """``Self.get_field_annotation[Meta](field)`` → ``(Meta, field)``。"""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not isinstance(func, ast.Subscript):
        return None
    if not (isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name) and (func.value.value.id == 'Self') and (func.value.attr in ('get_field_annotation', 'getFieldAnnotation'))):
        return None
    meta_name = _meta_name_from_subscript(func.slice)
    if meta_name is None or len(node.args) != 1:
        return None
    return (meta_name, node.args[0])

def _field_meta_call(ann_ast: ast.expr | None, meta_name: str) -> ast.Call | None:
    for name, call in iter_field_annotation_calls(ann_ast):
        if name == meta_name:
            return call
    return None

def _field_has_meta(ann_ast: ast.expr | None, meta_name: str) -> bool:
    return meta_name in field_annotation_markers_from_ann(ann_ast)

def _meta_attr_constant(meta_name: str, call: ast.Call | None, attr: str) -> ast.expr:
    if meta_name == 'UILabelMeta' and attr == 'text':
        if call is not None and call.args:
            arg0 = call.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                return ast.Constant(value=arg0.value)
    if meta_name == 'UISliderMeta':
        if call is None:
            raise ValueError('UISliderMeta 须带 (lo, hi) 实参')
        if attr == 'lo' and call.args:
            lo = call.args[0]
            if isinstance(lo, ast.Constant) and isinstance(lo.value, int):
                return ast.Constant(value=lo.value)
        if attr == 'hi' and len(call.args) >= 2:
            hi = call.args[1]
            if isinstance(hi, ast.Constant) and isinstance(hi.value, int):
                return ast.Constant(value=hi.value)
    raise ValueError(f'字段注解 {meta_name}.{attr} 无法在编译期解析')

def _const_bool(value: bool) -> ast.Constant:
    return ast.Constant(value=value)

def _const_test_value(test: ast.expr) -> bool | None:
    if isinstance(test, ast.Constant) and isinstance(test.value, bool):
        return test.value
    return None

def _is_not_none_compare(node: ast.expr) -> ast.expr | None:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None
    if not isinstance(node.ops[0], ast.IsNot):
        return None
    if len(node.comparators) != 1:
        return None
    cmp = node.comparators[0]
    if isinstance(cmp, ast.Constant) and cmp.value is None:
        return node.left
    return None

def _is_none_compare(node: ast.expr) -> ast.expr | None:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None
    if not isinstance(node.ops[0], ast.Is):
        return None
    if len(node.comparators) != 1:
        return None
    cmp = node.comparators[0]
    if isinstance(cmp, ast.Constant) and cmp.value is None:
        return node.left
    return None

def _fold_meta_presence_test(subject: ast.expr, *, meta_temps: dict[str, tuple[str, ast.Call | None]], field_name: str, ann_ast: ast.expr | None, negate: bool) -> ast.expr | None:
    """``meta is [not] None`` → 编译期 bool（``negate`` 为 ``is None``）。"""
    if isinstance(subject, ast.Name) and subject.id in meta_temps:
        meta_name, _call = meta_temps[subject.id]
        present = bool(meta_name)
        return _const_bool(not present if negate else present)
    parsed = parse_self_get_field_annotation_meta(subject)
    if parsed is None:
        return None
    meta_name, arg = parsed
    if isinstance(arg, ast.Constant) and arg.value == field_name:
        present = _field_has_meta(ann_ast, meta_name)
        return _const_bool(not present if negate else present)
    return None

def _simplify_const_ifs(stmts: list[ast.stmt]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            cv = _const_test_value(stmt.test)
            if cv is True:
                out.extend(_simplify_const_ifs(stmt.body))
                continue
            if cv is False:
                out.extend(_simplify_const_ifs(stmt.orelse))
                continue
            stmt = copy.deepcopy(stmt)
            stmt.body = _simplify_const_ifs(stmt.body)
            stmt.orelse = _simplify_const_ifs(stmt.orelse)
        out.append(stmt)
    return out

def _remove_meta_temp_assigns(stmts: list[ast.stmt], temp_names: frozenset[str]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for stmt in stmts:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            tgt = stmt.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id in temp_names:
                parsed = parse_self_get_field_annotation_meta(stmt.value)
                if parsed is not None:
                    continue
        out.append(stmt)
    return out

def _collect_meta_temp_assigns(body: list[ast.stmt], field_name: str, ann_ast: ast.expr | None) -> dict[str, tuple[str, ast.Call | None]]:
    temps: dict[str, tuple[str, ast.Call | None]] = {}
    for stmt in body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        tgt = stmt.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        parsed = parse_self_get_field_annotation_meta(stmt.value)
        if parsed is None:
            continue
        meta_name, arg = parsed
        if not (isinstance(arg, ast.Constant) and arg.value == field_name):
            continue
        if _field_has_meta(ann_ast, meta_name):
            temps[tgt.id] = (meta_name, _field_meta_call(ann_ast, meta_name))
        else:
            temps[tgt.id] = ('', None)
    return temps

def _fold_field_meta_body(body: list[ast.stmt], field_var: str, field_name: str, ann_ast: ast.expr | None, *, known_fields: frozenset[str]) -> list[ast.stmt]:
    renames: dict[str, ast.expr] = {field_var: ast.Constant(value=field_name)}
    body = _clone_body_replace_names(body, renames, known_fields=known_fields)
    meta_temps = _collect_meta_temp_assigns(body, field_name, ann_ast)

    class _MetaCompareFolder(ast.NodeTransformer):

        def visit_Compare(self, node: ast.Compare) -> ast.expr:
            self.generic_visit(node)
            subject = _is_not_none_compare(node)
            if subject is not None:
                folded = _fold_meta_presence_test(subject, meta_temps=meta_temps, field_name=field_name, ann_ast=ann_ast, negate=False)
                if folded is not None:
                    return folded
                return node
            subject = _is_none_compare(node)
            if subject is not None:
                folded = _fold_meta_presence_test(subject, meta_temps=meta_temps, field_name=field_name, ann_ast=ann_ast, negate=True)
                if folded is not None:
                    return folded
            return node

    class _MetaAttrFolder(ast.NodeTransformer):

        def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
            self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id in meta_temps:
                meta_name, call = meta_temps[node.value.id]
                if not meta_name:
                    return node
                return _meta_attr_constant(meta_name, call, node.attr)
            return node
    body = fold_self_get_field_type_calls(
        body,
        lambda name: ann_ast if name == field_name else None,
        known_fields=frozenset({field_name}),
    )
    body = [_MetaCompareFolder().visit(copy.deepcopy(s)) for s in body]
    body = _simplify_const_ifs(body)
    body = [_MetaAttrFolder().visit(s) for s in body]
    body = _remove_meta_temp_assigns(body, frozenset(meta_temps))
    folder = StaticReflectFolder(known_fields)
    return [folder.visit(s) for s in body]

def expand_iter_fields_meta(method: ast.FunctionDef, host: ClassInfo, *, all_classes: dict[str, ClassInfo] | None=None) -> ast.FunctionDef | None:
    """``for field in Self.iter_fields([public_only=…, mro=…]):`` + ``Self.get_field_annotation[Meta](field)`` 译期展开。"""
    from .annotation_options import walk_entity_bases
    for_idx: int | None = None
    for i, stmt in enumerate(method.body):
        if isinstance(stmt, ast.For) and _is_iter_fields_call(stmt.iter):
            for_idx = i
            break
    if for_idx is None:
        return None
    for_node = method.body[for_idx]
    if not isinstance(for_node.target, ast.Name):
        return None
    if len(for_node.body) >= 2 and _parse_get_field_annotation_assign(for_node.body[0]) is not None and isinstance(for_node.body[1], ast.Match):
        return None
    field_var = for_node.target.id
    extract_field_annotation_meta(host)
    loop_opts = _parse_fields_loop_options(for_node.iter)
    assert loop_opts is not None
    classes = all_classes or {}
    field_names = _resolve_iter_fields_names('Self', host, {}, public_only=loop_opts.public_only, mro=loop_opts.mro, glob=loop_opts.glob, all_classes=classes if classes else None)
    if loop_opts.mro and classes:
        known: set[str] = set(host.fields)
        for bi in walk_entity_bases(host, classes):
            known.update(bi.fields)
        fields = frozenset(known)
    else:
        fields = frozenset(host.fields)

    def _ann_ast(field_name: str) -> ast.expr | None:
        if field_name in host.fields:
            return field_ann_ast(host, field_name)
        if loop_opts.mro and classes:
            for bi in walk_entity_bases(host, classes):
                extract_field_annotation_meta(bi)
                if field_name in bi.fields:
                    return field_ann_ast(bi, field_name)
        return None
    unrolled: list[ast.stmt] = []
    for field_name in field_names:
        unrolled.extend(_fold_field_meta_body(for_node.body, field_var, field_name, _ann_ast(field_name), known_fields=fields))
    out = copy.deepcopy(method)
    out.body = method.body[:for_idx] + unrolled + method.body[for_idx + 1:]
    return out

def is_wildcard_pattern(pattern: ast.pattern) -> bool:
    if isinstance(pattern, ast.MatchAs):
        if pattern.pattern is not None:
            return False
        return pattern.name in (None, '_')
    return False

def _subject_ref(subject: ast.expr, subject_expr: str) -> ast.expr:
    if isinstance(subject, ast.Name):
        return copy.deepcopy(subject)
    return ast.Name(id=subject_expr, ctx=ast.Load())

def _is_cpp_expr_subject(subject_expr: str) -> bool:
    return not subject_expr.isidentifier()

def _is_new_match_class(pattern: ast.pattern) -> bool:
    if isinstance(pattern, ast.MatchOr):
        return all((_is_new_match_class(p) for p in pattern.patterns))
    return isinstance(pattern, ast.MatchClass) and isinstance(pattern.cls, ast.Name) and (pattern.cls.id == 'new')

def _new_pattern_field_attr_expr(recv: ast.expr, attr: str) -> ast.Attribute:
    return ast.Attribute(value=copy.deepcopy(recv), attr=attr, ctx=ast.Load())

def _new_pattern_field_literal_cond(tr: Translator, recv: ast.expr, attr: str, pat: ast.pattern) -> str | None:
    lit_pat: ast.pattern | None = None
    if isinstance(pat, ast.MatchValue) and isinstance(pat.value, ast.Constant):
        lit_pat = pat
    elif isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        if isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant):
            lit_pat = pat.pattern
    if lit_pat is None:
        return None
    field_expr = tr.visit(_new_pattern_field_attr_expr(recv, attr))
    return f'(({field_expr}) == ({tr.visit(lit_pat.value)}))'

def _new_pattern_field_binding(recv: ast.expr, attr: str, pat: ast.pattern) -> ast.stmt | None:
    if not isinstance(pat, ast.MatchAs) or not pat.name or pat.name == '_':
        return None
    if pat.pattern is not None and (not (isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant))):
        raise NotImplementedError(f'case new 字段嵌套模式暂不支持: {ast.dump(pat)}')
    return ast.Assign(targets=[ast.Name(id=pat.name, ctx=ast.Store())], value=_new_pattern_field_attr_expr(recv, attr))

def _resolve_new_match_class_info(tr: Translator, subject_cpp: str, classes: dict[str, ClassInfo], at: ast.AST) -> ClassInfo:
    info = class_info_for_cpp_type(subject_cpp, classes)
    if info is None:
        from ..translation_error import raise_translation_error
        raise_translation_error(tr, at, f'case new(kw=…) 仅适用于用户自定义类，主体类型 {subject_cpp!r} 不可匹配')
    if _skip_class(info) or info.is_union or info.is_enum:
        from ..translation_error import raise_translation_error
        raise_translation_error(tr, at, f'case new(kw=…) 不适用于 @union / @enum / mixin / protocol；主体为 {info.name}')
    return info

def parse_new_class_pattern(tr: Translator, pattern: ast.pattern, *, subject_cpp: str, subject: ast.expr, subject_expr: str, classes: dict[str, ClassInfo]) -> tuple[str, list[ast.stmt]]:
    if isinstance(pattern, ast.MatchOr):
        raise NotImplementedError('new MatchOr 须在 pattern_to_match 层处理')
    if not isinstance(pattern, ast.MatchClass):
        raise NotImplementedError(f'非 new 类模式: {ast.dump(pattern)}')
    if not isinstance(pattern.cls, ast.Name) or pattern.cls.id != 'new':
        raise NotImplementedError('parse_new_class_pattern 仅处理 case new(...)')
    if pattern.patterns:
        from ..translation_error import raise_translation_error
        raise_translation_error(tr, pattern, 'case new(...) 仅支持关键字参数，勿写位置参数')
    info = _resolve_new_match_class_info(tr, subject_cpp, classes, pattern)
    allowed = _matchable_member_names(info)
    _validate_match_field_names(info.name, list(pattern.kwd_attrs), allowed, tr=tr, at=pattern)
    recv = _subject_ref(subject, subject_expr)
    lits: list[str] = []
    bindings: list[ast.stmt] = []
    for attr, pat in zip(pattern.kwd_attrs, pattern.kwd_patterns):
        c = _new_pattern_field_literal_cond(tr, recv, attr, pat)
        if c is not None:
            lits.append(c)
        b = _new_pattern_field_binding(recv, attr, pat)
        if b is not None:
            bindings.append(b)
    if not lits:
        return ('true', bindings)
    if len(lits) == 1:
        return (lits[0], bindings)
    return ('(' + ' && '.join(lits) + ')', bindings)

def parse_class_pattern(pattern: ast.pattern, *, subject_cpp: str, subject: ast.expr, subject_expr: str, classes: dict[str, ClassInfo]) -> tuple[str, list[ast.stmt]]:
    if isinstance(pattern, ast.MatchOr):
        conds = []
        all_binds: list[ast.stmt] = []
        for p in pattern.patterns:
            c, b = parse_class_pattern(p, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes)
            if c != 'true':
                conds.append(c)
            all_binds.extend(b)
        cond = ' || '.join(conds) if conds else 'true'
        return (cond, all_binds)
    if not isinstance(pattern, ast.MatchClass):
        raise NotImplementedError(f'非类模式: {ast.dump(pattern)}')
    if not isinstance(pattern.cls, ast.Name):
        raise NotImplementedError('类模式类名须为简单名称')
    cls = pattern.cls.id
    info = classes.get(cls)
    if info is None:
        raise ValueError(f'未知类: {cls}')
    if info.is_union:
        raise TypeError(f'match 主体为 @union {cls}，请使用 case {cls}.<Variant>(...)，勿用 MatchClass({cls})')
    cpp = info.cpp_name()
    if subject_cpp != cpp and subject_cpp != cls:
        raise TypeError(f'match 主体类型为 {subject_cpp}，不能与类模式 {cls}（{cpp}）匹配')
    recv = _subject_ref(subject, subject_expr)
    bindings: list[ast.stmt] = []
    for pat in pattern.patterns:
        if isinstance(pat, ast.MatchAs) and pat.name:
            if isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant):
                bindings.append(ast.Assign(targets=[ast.Name(id=pat.name, ctx=ast.Store())], value=ast.Constant(value=pat.pattern.value.value)))
            elif pat.pattern is None and isinstance(recv, ast.Attribute):
                bindings.append(ast.Assign(targets=[ast.Name(id=pat.name, ctx=ast.Store())], value=copy.deepcopy(recv)))
    for attr, pat in zip(pattern.kwd_attrs, pattern.kwd_patterns):
        if isinstance(pat, ast.MatchAs) and pat.name:
            bindings.append(ast.Assign(targets=[ast.Name(id=pat.name, ctx=ast.Store())], value=ast.Attribute(value=copy.deepcopy(recv), attr=attr, ctx=ast.Load())))
    return ('true', bindings)

def pattern_to_match(tr: Translator, pattern: ast.pattern, *, subject_cpp: str, subject: ast.expr, subject_expr: str, classes: dict[str, ClassInfo]) -> PatternMatch:
    if isinstance(pattern, ast.MatchValue):
        from .enum_match import enum_pattern_to_match
        em = enum_pattern_to_match(pattern, subject_expr=subject_expr, classes=classes)
        if em is not None:
            return em
        val = pattern.value
        if not isinstance(val, ast.Constant):
            raise NotImplementedError('match 字面量须为常量')
        if isinstance(val.value, str):
            if len(val.value) == 1:
                ch = ord(val.value)
                if is_char_type(subject_cpp):
                    return PatternMatch(condition=f'({subject_expr} == PyChar({ch}))')
                if is_int_type(subject_cpp):
                    return PatternMatch(condition=f'({subject_expr} == {format_cpp_int(ch)})')
            if is_str_type(subject_cpp):
                lit = str_cpp_from_literal(val.value)
                return PatternMatch(condition=f'({subject_expr} == {lit})')
            lit = quote_cpp_string(val.value)
            return PatternMatch(condition=f'({subject_expr} == {lit})')
        if isinstance(val.value, bool):
            return PatternMatch(condition=f"({subject_expr} == {('true' if val.value else 'false')})")
        return PatternMatch(condition=f'({subject_expr} == {val.value})')
    if isinstance(pattern, ast.MatchAs):
        if pattern.pattern is not None:
            inner = pattern_to_match(tr, pattern.pattern, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes)
            if pattern.name and pattern.name != '_' and (not _is_cpp_expr_subject(subject_expr)):
                inner.bindings.append(ast.Assign(targets=[ast.Name(id=pattern.name, ctx=ast.Store())], value=_subject_ref(subject, subject_expr)))
            return inner
        if pattern.name in (None, '_'):
            return PatternMatch(condition='true', is_wildcard=True)
        if pattern.name:
            return PatternMatch(condition='true', bindings=[ast.Assign(targets=[ast.Name(id=pattern.name, ctx=ast.Store())], value=_subject_ref(subject, subject_expr))])
    if isinstance(pattern, ast.MatchClass):
        if isinstance(pattern.cls, ast.Name):
            if pattern.cls.id == 'new':
                cond, binds = parse_new_class_pattern(tr, pattern, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes)
                return PatternMatch(condition=cond, bindings=binds)
            if pattern.cls.id == 'Self':
                raise NotImplementedError('类方法内暂不支持 case Self(...)，请使用 case new(kw=...)')
            info = classes.get(pattern.cls.id)
            if info is not None and (not info.is_union) and (not info.is_enum) and (not _skip_class(info)):
                from ..translation_error import raise_translation_error
                raise_translation_error(tr, pattern, f'用户类 match 请使用 case new(kw=...)，勿写 case {pattern.cls.id}(...)')
        cond, binds = parse_class_pattern(pattern, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes)
        return PatternMatch(condition=cond, bindings=binds)
    if isinstance(pattern, ast.MatchOr):
        from .enum_match import enum_or_pattern_to_match
        from .match_or_validate import merge_match_or_parts, validate_match_or
        em = enum_or_pattern_to_match(pattern, subject_expr=subject_expr, classes=classes)
        if em is not None:
            return em
        validate_match_or(tr, pattern, subject_cpp=subject_cpp, classes=classes)
        parts = [pattern_to_match(tr, p, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes) for p in pattern.patterns]
        return merge_match_or_parts(tr, parts, pattern, subject_cpp=subject_cpp, classes=classes)
    if isinstance(pattern, ast.MatchSequence):
        from .sequence_mapping_match import pattern_sequence_to_match
        return pattern_sequence_to_match(tr, pattern, subject_cpp=subject_cpp, subject_expr=subject_expr, classes=classes)
    if isinstance(pattern, ast.MatchMapping):
        from .sequence_mapping_match import pattern_mapping_to_match
        return pattern_mapping_to_match(tr, pattern, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes)
    raise NotImplementedError(f'不支持的 match 模式: {ast.dump(pattern)}')

def _needs_subject_temp(subject: ast.expr, subject_cpp: str) -> bool:
    if subject_cpp in (cpp_ident('int'), cpp_ident('float'), cpp_ident('bool'), cpp_ident('str'), cpp_ident('char'), 'CStr'):
        return False
    return not isinstance(subject, ast.Name)
_SWITCHABLE_SUBJECT_CPP = frozenset({cpp_ident('int'), cpp_ident('bool'), cpp_ident('char')})

def _is_simple_literal_pattern(pattern: ast.pattern) -> bool:
    if is_wildcard_pattern(pattern):
        return True
    if isinstance(pattern, ast.MatchValue):
        return isinstance(pattern.value, ast.Constant)
    if isinstance(pattern, ast.MatchSingleton):
        return pattern.value in (True, False)
    if isinstance(pattern, ast.MatchOr):
        return bool(pattern.patterns) and all((_is_simple_literal_pattern(p) for p in pattern.patterns))
    return False

def _switch_case_label(value: object, subject_cpp: str) -> str | None:
    if subject_cpp == cpp_ident('bool'):
        if value is True:
            return 'case true:'
        if value is False:
            return 'case false:'
        return None
    if subject_cpp in (cpp_ident('int'), cpp_ident('char')):
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return f'case {value}:'
        if isinstance(value, str) and len(value) == 1:
            return f'case {ord(value)}:'
    return None

def _collect_switch_case_labels(pattern: ast.pattern, subject_cpp: str) -> list[str] | None:
    if is_wildcard_pattern(pattern):
        return []
    if isinstance(pattern, ast.MatchValue):
        if not isinstance(pattern.value, ast.Constant):
            return None
        label = _switch_case_label(pattern.value.value, subject_cpp)
        return [label] if label else None
    if isinstance(pattern, ast.MatchSingleton):
        label = _switch_case_label(pattern.value, subject_cpp)
        return [label] if label else None
    if isinstance(pattern, ast.MatchOr):
        labels: list[str] = []
        for p in pattern.patterns:
            part = _collect_switch_case_labels(p, subject_cpp)
            if part is None:
                return None
            labels.extend(part)
        return labels
    return None

def is_simple_match(node: ast.Match, subject_cpp: str) -> bool:
    if subject_cpp not in _SWITCHABLE_SUBJECT_CPP:
        return False
    for case in node.cases:
        if case.guard is not None or not _is_simple_literal_pattern(case.pattern):
            return False
        if not is_wildcard_pattern(case.pattern) and _collect_switch_case_labels(case.pattern, subject_cpp) is None:
            return False
    return True

def emit_simple_match(tr: Translator, node: ast.Match, subject_cpp: str) -> None:
    subject_expr = tr.visit(node.subject)
    if _needs_subject_temp(node.subject, subject_cpp):
        tr.write_line(f'{subject_cpp} __match_subj = {subject_expr};')
        subject_expr = '__match_subj'
    with tr._use_block(f'switch ({subject_expr})'):
        for case in node.cases:
            if is_wildcard_pattern(case.pattern):
                tr.write_line('default:')
                with tr._use_indent():
                    tr.write_line('{')
                    with tr._use_indent():
                        tr._emit_body(case.body)
                    tr.write_line('}')
                    tr.write_line('break;')
                continue
            labels = _collect_switch_case_labels(case.pattern, subject_cpp)
            assert labels is not None
            for label in labels:
                tr.write_line(label)
            with tr._use_indent():
                tr.write_line('{')
                with tr._use_indent():
                    tr._emit_body(case.body)
                tr.write_line('}')
                tr.write_line('break;')

def _union_variant_by_name(info: ClassInfo, name: str):
    for v in info.union_variants:
        if v.name == name:
            return v
    return None

def _union_subject_member(subject_expr: str, member: str) -> str:
    """``match self`` 时主体为 ``this`` 指针，成员访问须 ``->``。"""
    sep = '->' if subject_expr == 'this' else '.'
    return f'{subject_expr}{sep}{member}'

def _union_match_tag_expr(subject_expr: str) -> str:
    return _union_subject_member(subject_expr, f"{property_getter_method_for('__enum__')}()")

def _union_variant_expr(subject_expr: str, variant_name: str) -> str:
    return _union_subject_member(subject_expr, f'_variant_{variant_name}()')

def _union_field_cpp_for_subject(info: ClassInfo, variant, fname: str, subject_cpp: str) -> str:
    """泛型 union ``match``：用主体实例化类型替换形参（如 ``Optional[T]`` + ``PyOptional<PyInt>``）。"""
    cpp_t = variant.field_cpp_types.get(fname, cpp_ident('int'))
    if not info.type_params or '<' not in subject_cpp:
        return cpp_t
    inner = cpp_template_inner_args(subject_cpp, f'{info.cpp_name()}<')
    if inner is None:
        return cpp_t
    args = split_cpp_template_args(inner)
    for i, tp in enumerate(info.type_params):
        if cpp_t == tp or cpp_t == cpp_ident(tp):
            if i < len(args):
                return args[i]
    return cpp_t

def _union_payload_field_binding_decl(cpp_t: str, name: str, rhs: str) -> str:
    """Union ``match`` 字段绑定：容器/``PyStr`` 用 ``const&``，避免整块拷贝（如 ``list[int]`` 变体）。"""
    if cpp_t.startswith('PyList<') or cpp_t.startswith('PyFrozenList<') or cpp_t.startswith('PyDict<') or cpp_t.startswith('PyFrozenDict<') or cpp_t.startswith('PyStr') or (cpp_t == cpp_ident('str')):
        return f'const {cpp_t}& {name} = {rhs};'
    return f'{cpp_t} {name} = {rhs};'

def _register_union_match_binding(tr: Translator, name: str, cpp_t: str) -> None:
    from ..translator import NameContext
    if not tr.scope:
        return
    if tr._try_declare(name):
        tr.scope.vars[name] = NameContext.Variable
        bind_scope_var(tr.scope, name, cpp_t, classes=tr.classes)

def _union_tag_enum_expr(info: ClassInfo, subject_cpp: str) -> str:
    tag = f'{info.cpp_name()}::Enum'
    cpp = info.cpp_name()
    if '<' in subject_cpp:
        return f'{subject_cpp}::{tag}'
    if subject_cpp == cpp or subject_cpp.endswith(f'::{cpp}'):
        return f'{cpp}::{tag}'
    return f'{cpp}::{tag}'

def _union_field_literal_cond(tr: Translator, variant, fname: str, pat: ast.pattern, payload_ref: str) -> str | None:
    if isinstance(pat, ast.MatchValue) and isinstance(pat.value, ast.Constant):
        return f'(({payload_ref}.{fname}) == ({tr.visit(pat.value)}))'
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        if isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant):
            return f'(({payload_ref}.{fname}) == ({tr.visit(pat.pattern.value)}))'
    return None

def _emit_union_field_binding(tr: Translator, info: ClassInfo, variant, fname: str, pat: ast.pattern, payload_ref: str, subject_cpp: str) -> None:
    cpp_t = _union_field_cpp_for_subject(info, variant, fname, subject_cpp)
    if isinstance(pat, ast.MatchValue) and isinstance(pat.value, ast.Constant):
        return
    if isinstance(pat, ast.MatchAs):
        if pat.name and pat.name != '_':
            if pat.pattern is None or (isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant)):
                tr.write_line(_union_payload_field_binding_decl(cpp_t, pat.name, f'{payload_ref}.{fname}'))
                _register_union_match_binding(tr, pat.name, cpp_t)
                return
            raise NotImplementedError(f'变体字段嵌套模式暂不支持: {ast.dump(pat)}')
        return
    raise NotImplementedError(f'变体字段模式须为名称或字面量: {ast.dump(pat)}')

def _union_arm_entry_cond(tr: Translator, info: ClassInfo, arm: UnionMatchArm, subject_expr: str, tag_enum: str) -> str:
    if len(arm.variant_names) == 1 and len(arm.cases) > 1:
        vn = arm.variant_names[0]
        return f'({_union_match_tag_expr(subject_expr)} == {tag_enum}::{vn})'
    binding_pat = arm.binding_pattern
    if not isinstance(binding_pat, ast.MatchClass):
        parts = [f'({_union_match_tag_expr(subject_expr)} == {tag_enum}::{vn})' for vn in arm.variant_names]
        return parts[0] if len(parts) == 1 else '(' + ' || '.join(parts) + ')'
    branches: list[str] = []
    for variant_name in arm.variant_names:
        variant = _union_variant_by_name(info, variant_name)
        if variant is None:
            raise ValueError(f'未知变体 {variant_name}')
        tag_part = f'({_union_match_tag_expr(subject_expr)} == {tag_enum}::{variant_name})'
        if variant.is_unit:
            branches.append(tag_part)
            continue
        payload_ref = _union_variant_expr(subject_expr, variant_name)
        lits: list[str] = []
        pos = 0
        for pat in binding_pat.patterns:
            if pos >= len(variant.fields):
                raise ValueError(f'{variant_name} 位置参数过多')
            c = _union_field_literal_cond(tr, variant, variant.fields[pos], pat, payload_ref)
            if c is not None:
                lits.append(c)
            pos += 1
        for attr, pat in zip(binding_pat.kwd_attrs, binding_pat.kwd_patterns):
            if attr not in variant.fields:
                raise ValueError(f'{variant_name} 无字段 {attr}')
            c = _union_field_literal_cond(tr, variant, attr, pat, payload_ref)
            if c is not None:
                lits.append(c)
        if lits:
            branches.append(f"({tag_part} && {' && '.join(lits)})")
        else:
            branches.append(tag_part)
    return branches[0] if len(branches) == 1 else '(' + ' || '.join(branches) + ')'

def _emit_union_variant_all_field_bindings(tr: Translator, info: ClassInfo, variant_name: str, subject_expr: str) -> None:
    variant = _union_variant_by_name(info, variant_name)
    if variant is None or variant.is_unit:
        return
    payload_ref = _union_variant_expr(subject_expr, variant_name)
    for fname in variant.fields:
        cpp_t = variant.field_cpp_types.get(fname, cpp_ident('int'))
        tr.write_line(_union_payload_field_binding_decl(cpp_t, fname, f'{payload_ref}.{fname}'))
        _register_union_match_binding(tr, fname, cpp_t)

def _emit_union_arm_bindings(tr: Translator, info: ClassInfo, arm: UnionMatchArm, subject_expr: str, subject_cpp: str, *, binding_pattern: ast.pattern | None=None) -> None:
    binding_pat = binding_pattern if binding_pattern is not None else arm.binding_pattern
    if isinstance(binding_pat, ast.MatchValue):
        return
    if not isinstance(binding_pat, ast.MatchClass):
        return
    if len(arm.variant_names) == 1:
        variant_name = arm.variant_names[0]
        variant = _union_variant_by_name(info, variant_name)
        if variant is None or variant.is_unit:
            return
        payload_ref = _union_variant_expr(subject_expr, variant_name)
        pos = 0
        for pat in binding_pat.patterns:
            if pos >= len(variant.fields):
                raise ValueError(f'{variant_name} 位置参数过多')
            _emit_union_field_binding(tr, info, variant, variant.fields[pos], pat, payload_ref, subject_cpp)
            pos += 1
        for attr, pat in zip(binding_pat.kwd_attrs, binding_pat.kwd_patterns):
            if attr not in variant.fields:
                raise ValueError(f'{variant_name} 无字段 {attr}')
            _emit_union_field_binding(tr, info, variant, attr, pat, payload_ref, subject_cpp)
        return
    ref_variant = _union_variant_by_name(info, arm.variant_names[0])
    if ref_variant is None or ref_variant.is_unit:
        return
    bindings: list[tuple[str, str]] = []
    pos = 0
    for pat in binding_pat.patterns:
        if pos >= len(ref_variant.fields):
            raise ValueError(f'{arm.variant_names[0]} 位置参数过多')
        if isinstance(pat, ast.MatchAs) and pat.name and (pat.name != '_'):
            if pat.pattern is not None:
                raise NotImplementedError(f'MatchOr 分支仅支持名称绑定: {ast.dump(pat)}')
            bindings.append((pat.name, ref_variant.fields[pos]))
        pos += 1
    for attr, pat in zip(binding_pat.kwd_attrs, binding_pat.kwd_patterns):
        if attr not in ref_variant.fields:
            raise ValueError(f'{arm.variant_names[0]} 无字段 {attr}')
        if isinstance(pat, ast.MatchAs) and pat.name and (pat.name != '_'):
            if pat.pattern is not None:
                raise NotImplementedError(f'MatchOr 分支仅支持名称绑定: {ast.dump(pat)}')
            bindings.append((pat.name, attr))
    for var_name, fname in bindings:
        cpp_t = _union_field_cpp_for_subject(info, ref_variant, fname, subject_cpp)
        tr.write_line(f'{cpp_t} {var_name};')
        _register_union_match_binding(tr, var_name, cpp_t)
    tag_enum = _union_tag_enum_expr(info, subject_cpp)
    for variant_name in arm.variant_names:
        variant = _union_variant_by_name(info, variant_name)
        if variant is None or variant.is_unit:
            continue
        payload_ref = _union_variant_expr(subject_expr, variant_name)
        with tr._use_block(f'if (({_union_match_tag_expr(subject_expr)} == {tag_enum}::{variant_name}))'):
            for var_name, fname in bindings:
                if fname not in variant.fields:
                    raise ValueError(f'{variant_name} 无字段 {fname}')
                tr.write_line(f'{var_name} = {payload_ref}.{fname};')

def _union_case_pattern_cond(tr: Translator, info: ClassInfo, variant_name: str, subject_expr: str, pattern: ast.pattern) -> str | None:
    """单条 ``case`` 模式中的字面量约束；无则 ``None``（变体标签内无条件）。"""
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    if isinstance(pat, ast.MatchValue):
        return None
    if not isinstance(pat, ast.MatchClass):
        return None
    variant = _union_variant_by_name(info, variant_name)
    if variant is None or variant.is_unit:
        return None
    payload_ref = _union_variant_expr(subject_expr, variant_name)
    lits: list[str] = []
    pos = 0
    for sub in pat.patterns:
        if pos >= len(variant.fields):
            break
        c = _union_field_literal_cond(tr, variant, variant.fields[pos], sub, payload_ref)
        if c is not None:
            lits.append(c)
        pos += 1
    for attr, sub in zip(pat.kwd_attrs, pat.kwd_patterns):
        if attr not in variant.fields:
            continue
        c = _union_field_literal_cond(tr, variant, attr, sub, payload_ref)
        if c is not None:
            lits.append(c)
    if not lits:
        return None
    return '(' + ' && '.join(lits) + ')' if len(lits) > 1 else lits[0]

def _union_case_branch_cond(tr: Translator, info: ClassInfo, variant_name: str | None, subject_expr: str, case: ast.match_case) -> str | None:
    """``guard`` 与模式字面量合取；皆无则 ``None``（仅此时末条可用 ``else``）。"""
    parts: list[str] = []
    if variant_name is not None:
        lit = _union_case_pattern_cond(tr, info, variant_name, subject_expr, case.pattern)
        if lit is not None:
            parts.append(lit)
    if case.guard is not None:
        parts.append(f'({tr.visit(case.guard)})')
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else '(' + ' && '.join(parts) + ')'

def _emit_union_arm_body_cases(tr: Translator, info: ClassInfo, arm: UnionMatchArm, subject_expr: str, subject_cpp: str, cases: tuple[ast.match_case, ...]) -> None:
    inner_emitted = False
    variant_name = arm.variant_names[0] if len(arm.variant_names) == 1 else None
    for case_i, case in enumerate(cases):
        is_last = case_i + 1 == len(cases)
        branch_cond = _union_case_branch_cond(tr, info, variant_name, subject_expr, case)
        if branch_cond is not None:
            inner_kw = 'if' if not inner_emitted else 'else if'
            inner_emitted = True
            with tr._use_block(f'{inner_kw} {branch_cond}'):
                tr._emit_body(case.body)
        elif is_last and inner_emitted:
            with tr._use_block('else'):
                tr._emit_body(case.body)
        elif is_last:
            tr._emit_body(case.body)
        else:
            inner_kw = 'if' if not inner_emitted else 'else if'
            inner_emitted = True
            with tr._use_block(f'{inner_kw} (true)'):
                tr._emit_body(case.body)

def emit_union_match(tr: Translator, node: ast.Match, info: ClassInfo, subject_cpp: str) -> None:
    wildcard_body, arms = partition_union_match_cases(info, node)
    has_wild = wildcard_body is not None
    check_union_match_exhaustive(info, arms, has_wild)
    tag_enum = _union_tag_enum_expr(info, subject_cpp)
    subject_expr = tr.visit(node.subject)
    if _needs_subject_temp(node.subject, subject_cpp):
        tr.write_line(f'{subject_cpp} __match_subj = {subject_expr};')
        subject_expr = '__match_subj'
    emitted = False
    for arm in arms:
        cond = _union_arm_entry_cond(tr, info, arm, subject_expr, tag_enum)
        kw = 'if' if not emitted else 'else if'
        emitted = True
        with tr._use_block(f'{kw} {cond}'):
            if len(arm.variant_names) == 1 and len(arm.cases) > 1:
                _emit_union_variant_all_field_bindings(tr, info, arm.variant_names[0], subject_expr)
            elif len(arm.cases) == 1:
                _emit_union_arm_bindings(tr, info, arm, subject_expr, subject_cpp)
            _emit_union_arm_body_cases(tr, info, arm, subject_expr, subject_cpp, arm.cases)
    if wildcard_body is not None:
        with tr._use_block('else'):
            tr._emit_body(wildcard_body)

def emit_match(tr: Translator, node: ast.Match) -> None:
    subject_cpp = tr._infer_expr_cpp_type(node.subject) or cpp_ident('int')
    union_info = union_info_from_subject_cpp(tr, subject_cpp)
    if union_info is None and is_optional_type(subject_cpp):
        union_info = tr.classes.get('Optional')
    optional_match = union_info is not None and is_optional_union_info(union_info)
    if union_info is not None and (not optional_match):
        emit_union_match(tr, node, union_info, subject_cpp)
        return
    if getattr(tr, '_active_generator_emitter', None) is None and is_simple_match(node, subject_cpp):
        emit_simple_match(tr, node, subject_cpp)
        return
    subject_expr = tr.visit(node.subject)
    if _needs_subject_temp(node.subject, subject_cpp):
        tr.write_line(f'{subject_cpp} __match_subj = {subject_expr};')
        subject_expr = '__match_subj'
        subject_for_bind = ast.Name(id='__match_subj', ctx=ast.Load())
    else:
        subject_for_bind = node.subject
    wildcard_body: list[ast.stmt] | None = None
    armed: list[tuple[ast.match_case, PatternMatch]] = []
    for case in node.cases:
        if is_wildcard_pattern(case.pattern):
            wildcard_body = case.body
            continue
        if optional_match:
            pm = optional_pattern_to_match(tr, case.pattern, subject_cpp=subject_cpp, subject=subject_for_bind, subject_expr=subject_expr, classes=tr.classes)
        else:
            pm = pattern_to_match(tr, case.pattern, subject_cpp=subject_cpp, subject=subject_for_bind, subject_expr=subject_expr, classes=tr.classes)
        armed.append((case, pm))
    if optional_match:
        check_optional_match_exhaustive(node, wildcard_body is not None)
    has_guard = any((case.guard is not None for case, _ in armed))

    def _emit_case_body(case: ast.match_case, pm: PatternMatch) -> None:
        for line in pm.prelude_lines:
            tr.write_line(line)
        for b in pm.bindings:
            tr.visit(b)
        if case.guard is not None:
            with tr._use_block(f'if ({tr.visit(case.guard)})'):
                tr._emit_body(case.body)
                if has_guard:
                    tr.write_line('__match_done = true;')
        else:
            tr._emit_body(case.body)
            if has_guard:
                tr.write_line('__match_done = true;')
    if has_guard:
        tr.write_line('bool __match_done = false;')
        for case, pm in armed:
            cond = pm.condition or 'true'
            with tr._use_block(f'if (!__match_done && ({cond}))'):
                _emit_case_body(case, pm)
        if wildcard_body is not None:
            with tr._use_block('if (!__match_done)'):
                tr._emit_body(wildcard_body)
    else:
        emitted = False
        for case, pm in armed:
            cond = pm.condition or 'true'
            kw = 'if' if not emitted else 'else if'
            emitted = True
            with tr._use_block(f'{kw} ({cond})'):
                _emit_case_body(case, pm)
        if wildcard_body is not None:
            with tr._use_block('else'):
                tr._emit_body(wildcard_body)
