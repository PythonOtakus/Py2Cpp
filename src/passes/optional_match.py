"""``Optional[T]`` 的 ``match`` 语法糖（``case None`` / 字面量 / 捕获；**S25** 禁止 ``case Optional.Some`` / ``case Optional.None_``）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_extract import optional_inner_type
from ..analysis.ir import ClassInfo, cpp_option_tag_enum
from ..analysis.patterns import property_getter_method_for
from .union_expand import parse_union_case_pattern
if TYPE_CHECKING:
    from ..translator import Translator
_OPTIONAL_NAME = 'Optional'
_SOME_VARIANT = 'Some'
_NONE_VARIANT = 'None_'
_SOME_FIELD = 'value'

def is_optional_union_info(info: ClassInfo) -> bool:
    return info.is_union and info.name == _OPTIONAL_NAME

def _optional_access(subject_expr: str, member_expr: str) -> str:
    if subject_expr == 'this':
        return f'this->{member_expr}'
    return f'{subject_expr}.{member_expr}'

def _optional_some_value_expr(subject_expr: str) -> str:
    return _optional_access(subject_expr, f'_variant_{_SOME_VARIANT}().{_SOME_FIELD}')

def _is_none_match_pattern(pattern: ast.pattern) -> bool:
    if isinstance(pattern, ast.MatchValue):
        return isinstance(pattern.value, ast.Constant) and pattern.value.value is None
    if isinstance(pattern, ast.MatchSingleton):
        return pattern.value is None
    ref = parse_union_case_pattern(pattern)
    return ref is not None and ref.union_name == _OPTIONAL_NAME and (ref.variant_name == _NONE_VARIANT)

def _optional_some_union_ref(pattern: ast.pattern):
    ref = parse_union_case_pattern(pattern)
    if ref is None or ref.union_name != _OPTIONAL_NAME or ref.variant_name != _SOME_VARIANT:
        return None
    return ref

def _some_tag_cond(subject_expr: str, subject_cpp: str) -> str:
    tag_enum = cpp_option_tag_enum(subject_cpp)
    enum_get = property_getter_method_for('__enum__')
    return f"({_optional_access(subject_expr, f'{enum_get}()')} == {tag_enum}::{_SOME_VARIANT})"

def _none_tag_cond(subject_expr: str, subject_cpp: str) -> str:
    tag_enum = cpp_option_tag_enum(subject_cpp)
    enum_get = property_getter_method_for('__enum__')
    return f"({_optional_access(subject_expr, f'{enum_get}()')} == {tag_enum}::{_NONE_VARIANT})"

def _match_case_symbols():
    from .match_case import PatternMatch, pattern_to_match
    return (PatternMatch, pattern_to_match)

def _none_pattern_to_match(subject_expr: str, subject_cpp: str):
    PatternMatch, _ = _match_case_symbols()
    return PatternMatch(condition=_none_tag_cond(subject_expr, subject_cpp))

def _some_literal_pattern_to_match(tr: Translator, pattern: ast.pattern, *, subject_cpp: str, subject_expr: str, classes: dict[str, ClassInfo]):
    PatternMatch, pattern_to_match = _match_case_symbols()
    inner_cpp = optional_inner_type(subject_cpp) or 'PyInt'
    value_expr = _optional_some_value_expr(subject_expr)
    inner = pattern_to_match(tr, pattern, subject_cpp=inner_cpp, subject=ast.Name(id=value_expr, ctx=ast.Load()), subject_expr=value_expr, classes=classes)
    tag_part = _some_tag_cond(subject_expr, subject_cpp)
    cond = inner.condition or 'true'
    if cond == 'true':
        full = tag_part
    else:
        full = f'({tag_part} && ({cond}))'
    return PatternMatch(condition=full, bindings=inner.bindings, prelude_lines=list(inner.prelude_lines))

def _some_capture_pattern_to_match(pattern: ast.MatchAs, *, subject_cpp: str, subject_expr: str):
    PatternMatch, _ = _match_case_symbols()
    inner_cpp = optional_inner_type(subject_cpp) or 'PyInt'
    value_expr = _optional_some_value_expr(subject_expr)
    prelude: list[str] = []
    if pattern.name and pattern.name != '_':
        prelude.append(f'{inner_cpp} {pattern.name} = {value_expr};')
    return PatternMatch(condition=_some_tag_cond(subject_expr, subject_cpp), prelude_lines=prelude)

def _some_union_class_pattern_to_match(tr: Translator, pattern: ast.MatchClass, *, subject_cpp: str, subject_expr: str, classes: dict[str, ClassInfo]):
    PatternMatch, _ = _match_case_symbols()
    inner_cpp = optional_inner_type(subject_cpp) or 'PyInt'
    value_expr = _optional_some_value_expr(subject_expr)
    tag_part = _some_tag_cond(subject_expr, subject_cpp)
    prelude: list[str] = []
    lit_conds: list[str] = []

    def _field_pat(pat: ast.pattern) -> None:
        if isinstance(pat, ast.MatchValue) and isinstance(pat.value, ast.Constant):
            lit_conds.append(f'(({value_expr}) == ({tr.visit(pat.value)}))')
            return
        if isinstance(pat, ast.MatchAs):
            if pat.pattern is not None and isinstance(pat.pattern, ast.MatchValue):
                if isinstance(pat.pattern.value, ast.Constant):
                    lit_conds.append(f'(({value_expr}) == ({tr.visit(pat.pattern.value)}))')
            if pat.name and pat.name != '_':
                if pat.pattern is None or (isinstance(pat.pattern, ast.MatchValue) and isinstance(pat.pattern.value, ast.Constant)):
                    prelude.append(f'{inner_cpp} {pat.name} = {value_expr};')
                    return
            if pat.pattern is None:
                return
        raise NotImplementedError(f'Optional.Some(...) 仅支持名称或字面量绑定：{ast.dump(pat)}')
    if pattern.patterns:
        if len(pattern.patterns) != 1:
            raise ValueError('Optional.Some(...) 仅有一个位置参数（内层值）')
        _field_pat(pattern.patterns[0])
    for attr, pat in zip(pattern.kwd_attrs, pattern.kwd_patterns):
        if attr != _SOME_FIELD:
            raise ValueError(f'Optional.Some 仅支持字段 {_SOME_FIELD!r}，得到 {attr!r}')
        _field_pat(pat)
    if lit_conds:
        lit = lit_conds[0] if len(lit_conds) == 1 else '(' + ' && '.join(lit_conds) + ')'
        cond = f'({tag_part} && {lit})'
    else:
        cond = tag_part
    return PatternMatch(condition=cond, prelude_lines=prelude)

def optional_pattern_to_match(tr: Translator, pattern: ast.pattern, *, subject_cpp: str, subject: ast.expr, subject_expr: str, classes: dict[str, ClassInfo]):
    PatternMatch, _ = _match_case_symbols()
    if _is_none_match_pattern(pattern):
        return _none_pattern_to_match(subject_expr, subject_cpp)
    if _optional_some_union_ref(pattern) is not None:
        if isinstance(pattern, ast.MatchClass):
            return _some_union_class_pattern_to_match(tr, pattern, subject_cpp=subject_cpp, subject_expr=subject_expr, classes=classes)
        return PatternMatch(condition=_some_tag_cond(subject_expr, subject_cpp))
    if isinstance(pattern, ast.MatchValue):
        return _some_literal_pattern_to_match(tr, pattern, subject_cpp=subject_cpp, subject_expr=subject_expr, classes=classes)
    if isinstance(pattern, ast.MatchSingleton):
        if pattern.value is None:
            return _none_pattern_to_match(subject_expr, subject_cpp)
        return _some_literal_pattern_to_match(tr, ast.MatchValue(value=ast.Constant(value=pattern.value)), subject_cpp=subject_cpp, subject_expr=subject_expr, classes=classes)
    if isinstance(pattern, ast.MatchAs):
        if pattern.pattern is not None:
            inner = optional_pattern_to_match(tr, pattern.pattern, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes)
            if pattern.name and pattern.name != '_':
                inner.bindings.append(ast.Assign(targets=[ast.Name(id=pattern.name, ctx=ast.Store())], value=ast.Name(id=subject_expr, ctx=ast.Load())))
            return inner
        return _some_capture_pattern_to_match(pattern, subject_cpp=subject_cpp, subject_expr=subject_expr)
    if isinstance(pattern, ast.MatchOr):
        parts = [optional_pattern_to_match(tr, p, subject_cpp=subject_cpp, subject=subject, subject_expr=subject_expr, classes=classes) for p in pattern.patterns]
        conds = [p.condition for p in parts if p.condition and p.condition != 'true']
        if not conds:
            cond = 'true'
        elif len(conds) == 1:
            cond = conds[0]
        else:
            cond = '(' + ' || '.join((f'({c})' for c in conds)) + ')'
        prelude: list[str] = []
        bindings: list[ast.stmt] = []
        for p in parts:
            prelude.extend(p.prelude_lines)
            bindings.extend(p.bindings)
        return PatternMatch(condition=cond, bindings=bindings, prelude_lines=prelude)
    raise NotImplementedError(f'Optional match 不支持的模式: {ast.dump(pattern)}')

def _optional_arm_covers_none(pattern: ast.pattern) -> bool:
    if isinstance(pattern, ast.MatchOr):
        return any((_optional_arm_covers_none(p) for p in pattern.patterns))
    return _is_none_match_pattern(pattern)

def _optional_arm_covers_some(pattern: ast.pattern) -> bool:
    if isinstance(pattern, ast.MatchOr):
        return any((_optional_arm_covers_some(p) for p in pattern.patterns))
    if _is_none_match_pattern(pattern):
        return False
    return True

def is_optional_match_exhaustive(node: ast.Match, *, has_wildcard: bool=False) -> bool:
    if has_wildcard:
        return True
    covers_none = False
    covers_some = False
    for case in node.cases:
        from .match_case import is_wildcard_pattern
        if case.guard is not None or is_wildcard_pattern(case.pattern):
            continue
        if _optional_arm_covers_none(case.pattern):
            covers_none = True
        if _optional_arm_covers_some(case.pattern):
            covers_some = True
    return covers_none and covers_some

def check_optional_match_exhaustive(node: ast.Match, has_wildcard: bool) -> None:
    if is_optional_match_exhaustive(node, has_wildcard=has_wildcard):
        return
    from .match_case import is_wildcard_pattern
    missing: list[str] = []
    if not any((case.guard is None and (not is_wildcard_pattern(case.pattern)) and _optional_arm_covers_none(case.pattern) for case in node.cases)):
        missing.append('None')
    if not any((case.guard is None and (not is_wildcard_pattern(case.pattern)) and _optional_arm_covers_some(case.pattern) for case in node.cases)):
        missing.append('Some')
    raise ValueError(f"match Optional 未覆盖 {', '.join(missing)} 且无 case _")
