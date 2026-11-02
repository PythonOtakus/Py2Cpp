"""f-string / ``str.format``：``{}`` 占位 + 实参用 ``str(...)`` 构造。"""
from __future__ import annotations
import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_str_type
from ..analysis.ir import cpp_ident, quote_cpp_string
if TYPE_CHECKING:
    from ..translator import Translator
_FLOAT_PREC_RE = re.compile('\\.(\\d+)f')

@dataclass
class JoinedStrPlan:
    fmt: str
    arg_exprs: list[str]
    literal_only: bool

def escape_brace_literal(text: str) -> str:
    return text.replace('{', '{{').replace('}', '}}')

def float_precision_from_spec(format_spec: ast.expr | None) -> int | None:
    if format_spec is None:
        return None
    if isinstance(format_spec, ast.Constant) and isinstance(format_spec.value, str):
        m = _FLOAT_PREC_RE.match(format_spec.value.strip())
        if m:
            return int(m.group(1))
    if isinstance(format_spec, ast.JoinedStr) and len(format_spec.values) == 1:
        part = format_spec.values[0]
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            m = _FLOAT_PREC_RE.match(part.value.strip())
            if m:
                return int(m.group(1))
    return None

def emit_str_ctor(tr: Translator, value: ast.expr, format_spec: ast.expr | None=None) -> str:
    """将值转为 ``PyStr``：经全局 ``format``（转发 ``__format__``）。"""
    v = tr._visit_value_expr(value)
    if format_spec is None:
        from ..emit.builtin_call_emit import emit_format_call
        return emit_format_call(tr, v)
    if isinstance(format_spec, ast.Constant) and isinstance(format_spec.value, str):
        if format_spec.value == '':
            from ..emit.builtin_call_emit import emit_format_call
            return emit_format_call(tr, v)
    from ..emit.builtin_call_emit import emit_format_call
    return emit_format_call(tr, v, format_spec)

def emit_formatted_arg(tr: Translator, value: ast.expr, conversion: str | None, format_spec: ast.expr | None) -> str:
    if conversion == 'r':
        raise NotImplementedError('f-string !r')
    if conversion == 'a':
        raise NotImplementedError('f-string !a')
    return emit_str_ctor(tr, value, format_spec)

def plan_joined_str(tr: Translator, node: ast.JoinedStr) -> JoinedStrPlan:
    tokens: list[str] = []
    arg_exprs: list[str] = []
    for part in node.values:
        match part:
            case ast.Constant(value=text):
                tokens.append(escape_brace_literal(str(text)))
            case ast.FormattedValue(value=value, conversion=conv, format_spec=fspec):
                tokens.append('{}')
                conv_s = conv if isinstance(conv, str) and conv else None
                arg_exprs.append(emit_formatted_arg(tr, value, conv_s, fspec))
            case _:
                raise NotImplementedError(f'f-string part: {ast.dump(part)}')
    return JoinedStrPlan(fmt=''.join(tokens), arg_exprs=arg_exprs, literal_only=not arg_exprs)

def plan_format_literal(tr: Translator, fmt: str, args: list[ast.expr]) -> JoinedStrPlan:
    arg_exprs = [emit_str_ctor(tr, a, None) for a in args]
    return JoinedStrPlan(fmt=fmt, arg_exprs=arg_exprs, literal_only=not arg_exprs)

def emit_format_expr(tr: Translator, plan: JoinedStrPlan) -> str:
    ps = cpp_ident('str')
    if plan.literal_only:
        return f'{ps}::format({quote_cpp_string(plan.fmt)})'
    fmt = quote_cpp_string(plan.fmt)
    n = len(plan.arg_exprs)
    if n == 0:
        return f'{ps}::format({fmt})'
    if n > 32:
        raise NotImplementedError(f'{ps}::format 暂最多 32 个占位符，当前 {n} 个')
    return f"{ps}::format({fmt}, {', '.join(plan.arg_exprs)})"
