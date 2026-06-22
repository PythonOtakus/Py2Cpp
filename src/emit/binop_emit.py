"""一元/二元/比较表达式 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_byte_type, is_char_type, is_int_type, is_refcount_type, is_str_type, is_varint_type
from ..analysis.type_pred import is_complex_type
from ..analysis.ir import cpp_ident, format_cpp_int, format_cpp_varint, strip_cpp_ref
from .complex_literal_emit import complex_literal_parts, try_emit_complex_literal_expr
from .literal_map_lookup_emit import try_emit_set_literal_contains
from .literal_sequence_lookup_emit import try_emit_list_literal_contains, try_emit_str_literal_contains
if TYPE_CHECKING:
    from ..translator import Translator

def is_single_char_str_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and (len(node.value) == 1)

def emit_single_char_pychar_literal(node: ast.Constant) -> str:
    assert isinstance(node.value, str) and len(node.value) == 1
    return f'PyChar({ord(node.value)})'

def _coerce_pychar_to_pystr(tr: Translator, expr: str, ty: str) -> str:
    """``PyChar`` 实参传给 ``PyStr`` 形参时显式构造（``explicit PyStr``）。"""
    if is_char_type(ty, classes=tr.classes):
        ps = cpp_ident('str')
        return f'{ps}({expr})'
    return expr

def _contains_member_arg(tr: Translator, left_expr: ast.expr, container_expr: ast.expr) -> str:
    left_v = tr._visit_value_expr(left_expr)
    left_t = strip_cpp_ref(tr._infer_expr_cpp_type(left_expr) or '')
    comp_t = strip_cpp_ref(tr._infer_expr_cpp_type(container_expr) or '')
    if is_char_type(left_t, classes=tr.classes) and is_str_type(comp_t, classes=tr.classes):
        return _coerce_pychar_to_pystr(tr, left_v, left_t)
    return left_v

def _ord_single_char_value(node: ast.expr) -> int | None:
    """``ord("x")`` 单字符实参 → 码点；否则 ``None``。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id == 'ord') and (len(node.args) == 1) and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and (len(node.args[0].value) == 1):
        return ord(node.args[0].value)
    return None

def _ascii_int_char_code(node: ast.expr) -> int | None:
    """``42`` / ``ord("x")`` 等可安全升为 ``PyChar`` 比较的 ASCII 码点。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        v = int(node.value)
        if 0 <= v <= 127:
            return v
        return None
    return _ord_single_char_value(node)

def _scalar_scalar_binop(tr: Translator, node: ast.BinOp) -> bool:
    if is_varint_type(tr._infer_expr_cpp_type(node.left)):
        return False
    if is_varint_type(tr._infer_expr_cpp_type(node.right)):
        return False
    return tr._is_py_scalar_expr(node.left) and tr._is_py_scalar_expr(node.right)

def _operand_is_complex(tr: Translator, node: ast.expr, cpp_type: str | None) -> bool:
    t = cpp_type or tr._infer_expr_cpp_type(node) or ''
    if is_complex_type(t):
        return True
    return complex_literal_parts(node) is not None

def try_global_forward_binop(tr: Translator, node: ast.BinOp) -> str | None:
    """``PyComplex`` / ``varint`` 等：仅 ``/`` ``//`` ``%`` 走全局 dunder（与 C++ 语义不一致）。"""
    match node.op:
        case ast.Mod():
            fn = '__mod__'
        case ast.Div():
            fn = '__truediv__'
        case ast.FloorDiv():
            fn = '__floordiv__'
        case _:
            return None
    if isinstance(node.op, ast.Mod) and tr._is_str_expr(node.left):
        return None
    if _scalar_scalar_binop(tr, node):
        return None
    left_t = tr._infer_expr_cpp_type(node.left)
    right_t = tr._infer_expr_cpp_type(node.right)
    if not (_operand_is_complex(tr, node.left, left_t) or _operand_is_complex(tr, node.right, right_t) or is_varint_type(left_t) or is_varint_type(right_t)):
        return None
    l = tr._visit_value_expr(node.left)
    r = tr._visit_value_expr(node.right)
    return f'::{fn}({l}, {r})'

def try_global_scalar_binop(tr: Translator, node: ast.BinOp) -> str | None:
    """``int``/``float`` 的 ``%``、``/``、``//`` → 全局 ``__mod__`` / ``__truediv__`` / ``__floordiv__``。"""
    match node.op:
        case ast.Mod():
            fn = '__mod__'
        case ast.Div():
            fn = '__truediv__'
        case ast.FloorDiv():
            fn = '__floordiv__'
        case _:
            return None
    left_t = tr._infer_expr_cpp_type(node.left)
    right_t = tr._infer_expr_cpp_type(node.right)
    if is_varint_type(left_t) or is_varint_type(right_t):
        return None
    if not tr._is_py_scalar_expr(node.left) or not tr._is_py_scalar_expr(node.right):
        return None
    l = tr._visit_value_expr(node.left)
    r = tr._visit_value_expr(node.right)
    return f'::{fn}({l}, {r})'

def try_str_percent_binop(tr: Translator, node: ast.BinOp) -> str | None:
    """``"%d %d" % (1, 2)`` → ``__mod__(fmt, makeTuple(1, 2))``。"""
    if not isinstance(node.op, ast.Mod):
        return None
    if not tr._is_str_expr(node.left):
        return None
    fmt = tr._visit_value_expr(node.left)
    rhs = tr._emit_mod_rhs(node.right)
    return f'::__mod__({fmt}, {rhs})'

def try_emit_char_scalar_compare(tr: Translator, left_expr: ast.expr, comp: ast.expr, op: str) -> str | None:
    """``char``/``int`` 与单字符 ``str``/``ord``/ASCII ``int`` 比较。

  ``char == 'x'`` → ``PyChar`` 对 ``PyChar``；``int == 'x'`` / ``int == ord('x')`` → 整型码点。
  """
    if op not in ('==', '!='):
        return None
    left_ty = tr._infer_expr_cpp_type(left_expr)
    comp_ty = tr._infer_expr_cpp_type(comp)
    if is_char_type(left_ty) and is_single_char_str_constant(comp):
        assert isinstance(comp, ast.Constant)
        return f'{tr.visit(left_expr)} {op} {emit_single_char_pychar_literal(comp)}'
    if is_char_type(comp_ty) and is_single_char_str_constant(left_expr):
        assert isinstance(left_expr, ast.Constant)
        return f'{emit_single_char_pychar_literal(left_expr)} {op} {tr.visit(comp)}'
    ps = cpp_ident('str')
    if is_str_type(left_ty, classes=tr.classes) and is_char_type(comp_ty, classes=tr.classes):
        return f'{tr.visit(left_expr)} {op} {ps}({tr.visit(comp)})'
    if is_char_type(left_ty, classes=tr.classes) and is_str_type(comp_ty, classes=tr.classes):
        return f'{ps}({tr.visit(left_expr)}) {op} {tr.visit(comp)}'
    if is_int_type(left_ty) and is_single_char_str_constant(comp):
        assert isinstance(comp, ast.Constant)
        code = ord(comp.value)
        return f'({tr.visit(left_expr)} {op} {format_cpp_int(code)})'
    if is_int_type(comp_ty) and is_single_char_str_constant(left_expr):
        assert isinstance(left_expr, ast.Constant)
        code = ord(left_expr.value)
        return f'({format_cpp_int(code)} {op} {tr.visit(comp)})'
    code = _ascii_int_char_code(comp)
    if is_char_type(left_ty) and code is not None:
        return f'{tr.visit(left_expr)} {op} PyChar({code})'
    if is_byte_type(left_ty) and code is not None:
        return f'{tr.visit(left_expr)} {op} PyByte({code})'
    if is_int_type(left_ty) and code is not None:
        return f'({tr.visit(left_expr)} {op} {format_cpp_int(code)})'
    code = _ascii_int_char_code(left_expr)
    if is_char_type(comp_ty) and code is not None:
        return f'PyChar({code}) {op} {tr.visit(comp)}'
    if is_byte_type(comp_ty) and code is not None:
        return f'PyByte({code}) {op} {tr.visit(comp)}'
    if is_int_type(comp_ty) and code is not None:
        return f'({format_cpp_int(code)} {op} {tr.visit(comp)})'
    return None

def emit_unary_op(tr: Translator, node: ast.UnaryOp) -> str:
    match node.op:
        case ast.UAdd():
            copied = tr._emit_copy_expr(node.operand)
            if copied:
                return copied
            return f'(+{tr.visit(node.operand)})'
        case ast.USub():
            if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int):
                neg_val = -int(node.operand.value)
                ctx_type = tr._infer_expr_cpp_type(node)
                if ctx_type and is_varint_type(ctx_type):
                    return format_cpp_varint(neg_val)
                return format_cpp_int(neg_val)
            info = tr._class_info_for_expr(node.operand)
            if info and '__neg__' in info.methods:
                return tr._member_call(node.operand, '__neg__')
            return f'(-{tr.visit(node.operand)})'
        case ast.Not():
            from ..passes.macro_if import parse_macro_if_test
            try:
                parsed = parse_macro_if_test(node)
            except ValueError:
                raise
            if parsed is not None:
                raise NotImplementedError('"NAME" in __macro__ 仅可用于 if/elif 条件（译为 #ifdef / #elif），不可作普通表达式')
            return f'(!{tr.visit(node.operand)})'
        case ast.Invert():
            info = tr._class_info_for_expr(node.operand)
            if info and info.is_enum and info.enum_is_flag:
                cpp = info.cpp_name()
                u = info.enum_underlying_cpp
                v = tr.visit(node.operand)
                return f'static_cast<{cpp}>(~static_cast<{u}>({v}))'
            if info and '__invert__' in info.methods:
                return tr._member_call(node.operand, '__invert__')
            return f'(~{tr.visit(node.operand)})'
        case _:
            raise NotImplementedError(node.op)

def _expr_is_complex(tr: Translator, node: ast.expr) -> bool:
    t = tr._infer_expr_cpp_type(node) or ''
    if is_complex_type(t):
        return True
    return complex_literal_parts(node) is not None

def try_scalar_complex_binop(tr: Translator, node: ast.BinOp) -> str | None:
    """标量与复数字面量/``PyComplex``：``*`` / ``**`` 走 ``__mul__`` / ``__rmul__`` / ``__rpow__``。"""
    left_scalar = tr._is_py_scalar_expr(node.left)
    right_scalar = tr._is_py_scalar_expr(node.right)
    left_complex = _expr_is_complex(tr, node.left)
    right_complex = _expr_is_complex(tr, node.right)
    match node.op:
        case ast.Mult():
            if left_complex and right_complex:
                return tr._emit_dunder_call(node.left, '__mul__', node.right)
            if left_scalar and right_complex and (not left_complex):
                return tr._emit_dunder_call(node.right, '__rmul__', node.left)
            if right_scalar and left_complex and (not right_complex):
                return tr._emit_dunder_call(node.left, '__mul__', node.right)
        case ast.Pow():
            if left_scalar and right_complex:
                return tr._emit_dunder_call(node.right, '__rpow__', node.left)
        case _:
            return None
    return None

def emit_bin_op(tr: Translator, node: ast.BinOp) -> str:
    if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
        base = try_emit_complex_literal_expr(node.left, None)
        if base is not None:
            return f'({base}.__pow__({node.right.value}))'
    complex_lit = try_emit_complex_literal_expr(node, None)
    if complex_lit is not None:
        return complex_lit
    percent = try_str_percent_binop(tr, node)
    if percent is not None:
        return percent
    scalar = try_global_scalar_binop(tr, node)
    if scalar is not None:
        return scalar
    forward = try_global_forward_binop(tr, node)
    if forward is not None:
        return forward
    scalar_complex = try_scalar_complex_binop(tr, node)
    if scalar_complex is not None:
        return scalar_complex
    dunder = tr._try_dunder_binop(node)
    if dunder is not None:
        return dunder
    enum_op = tr._try_enum_binop(node)
    if enum_op is not None:
        return enum_op
    l, r = (tr.visit(node.left), tr.visit(node.right))
    match node.op:
        case ast.Add():
            return f'({l} + {r})'
        case ast.Sub():
            return f'({l} - {r})'
        case ast.Mult():
            return f'({l} * {r})'
        case ast.Div():
            return f'({l} / {r})'
        case ast.Mod():
            return f'({l} % {r})'
        case ast.FloorDiv():
            return f'(({l}) / ({r}))'
        case ast.Pow():
            return f'pow({l}, {r})'
        case ast.LShift():
            return f'(({l}) << ({r}))'
        case ast.RShift():
            return f'(({l}) >> ({r}))'
        case ast.BitOr():
            return f'(({l}) | ({r}))'
        case ast.BitXor():
            return f'(({l}) ^ ({r}))'
        case ast.BitAnd():
            return f'(({l}) & ({r}))'
        case ast.MatMult():
            raise NotImplementedError('MatMult 需通过 @mixin 展开或类定义 __matmul__')
        case _:
            raise NotImplementedError(node.op)

def _compare_operand(tr: Translator, node: ast.expr) -> str:
    return tr._visit_value_expr(node)

def _is_raw_ptr_cpp_type(cpp_type: str) -> bool:
    t = cpp_type.strip()
    return t.endswith('*') and (not is_refcount_type(t))

def _is_nullable_identity_cpp_type(cpp_type: str) -> bool:
    """``is None`` / ``is not None`` 可与 ``nullptr`` 比较的 C++ 类型（裸指针、``Callable`` 函数指针）。"""
    t = cpp_type.strip()
    if _is_raw_ptr_cpp_type(t):
        return True
    return '(*)' in t

def _identity_addr_expr(tr: Translator, node: ast.expr, cpp_type: str) -> str:
    """``is`` / ``is not``：取对象身份（地址）；``PyRefCount`` 比堆对象，裸指针比指针值。"""
    v = tr.visit(node)
    if is_refcount_type(cpp_type):
        return f'(&(*({v})))'
    if _is_raw_ptr_cpp_type(cpp_type):
        return v
    val = tr._visit_value_expr(node)
    return f'(&({val}))'

def _emit_identity_compare(tr: Translator, left_expr: ast.expr, comp_expr: ast.expr, *, is_not: bool) -> str:
    from .lazy_param_emit import try_emit_lazy_param_is_none
    if isinstance(left_expr, ast.Name):
        lazy_cmp = try_emit_lazy_param_is_none(tr, left_expr, is_not=is_not)
        if lazy_cmp is not None and tr._is_none_constant(comp_expr):
            return lazy_cmp
    if isinstance(comp_expr, ast.Name):
        lazy_cmp = try_emit_lazy_param_is_none(tr, comp_expr, is_not=is_not)
        if lazy_cmp is not None and tr._is_none_constant(left_expr):
            return lazy_cmp
    opt_none = tr._try_option_none_compare(left_expr, comp_expr, is_not=is_not)
    if opt_none is not None:
        return opt_none
    opt_some = tr._try_option_none_compare(comp_expr, left_expr, is_not=is_not)
    if opt_some is not None:
        return opt_some
    left_none = tr._is_none_constant(left_expr)
    right_none = tr._is_none_constant(comp_expr)
    if left_none or right_none:
        if left_none and right_none:
            return 'false' if is_not else 'true'
        other_expr = comp_expr if left_none else left_expr
        other_t = strip_cpp_ref(tr._infer_expr_cpp_type(other_expr) or '')
        if _is_nullable_identity_cpp_type(other_t) or is_refcount_type(other_t):
            v = tr.visit(other_expr)
            if is_refcount_type(other_t):
                pb = cpp_ident('bool')
                if is_not:
                    return f'static_cast<{pb}>({v})'
                return f'(!static_cast<{pb}>({v}))'
            op = '!=' if is_not else '=='
            return f'({v} {op} nullptr)'
        return 'true' if is_not else 'false'
    if isinstance(left_expr, ast.Constant) or isinstance(comp_expr, ast.Constant):
        return 'true' if is_not else 'false'
    left_t = tr._infer_expr_cpp_type(left_expr)
    right_t = tr._infer_expr_cpp_type(comp_expr)
    left_addr = _identity_addr_expr(tr, left_expr, left_t)
    right_addr = _identity_addr_expr(tr, comp_expr, right_t)
    op = '!=' if is_not else '=='
    return f'({left_addr} {op} {right_addr})'

def _emit_eq_compare(tr: Translator, left_expr: ast.expr, comp: ast.expr) -> str:
    opt_none = tr._try_option_none_compare(left_expr, comp, is_not=False)
    if opt_none is not None:
        return opt_none
    opt_some = tr._try_option_none_compare(comp, left_expr, is_not=False)
    if opt_some is not None:
        return opt_some
    char_cmp = try_emit_char_scalar_compare(tr, left_expr, comp, '==')
    if char_cmp is not None:
        return char_cmp
    left_v = _compare_operand(tr, left_expr)
    right_v = _compare_operand(tr, comp)
    return f'({left_v} == {right_v})'

def _emit_ne_compare(tr: Translator, left_expr: ast.expr, comp: ast.expr) -> str:
    opt_none = tr._try_option_none_compare(left_expr, comp, is_not=True)
    if opt_none is not None:
        return opt_none
    opt_some = tr._try_option_none_compare(comp, left_expr, is_not=True)
    if opt_some is not None:
        return opt_some
    char_cmp = try_emit_char_scalar_compare(tr, left_expr, comp, '!=')
    if char_cmp is not None:
        return char_cmp
    left_v = _compare_operand(tr, left_expr)
    right_v = _compare_operand(tr, comp)
    if tr.current_method is not None and tr.current_method.name == '__ne__' and isinstance(left_expr, ast.Name) and (left_expr.id == 'self'):
        return f'(!({left_v} == {right_v}))'
    return f'({left_v} != {right_v})'

def emit_compare(tr: Translator, node: ast.Compare) -> str:
    from ..passes.macro_if import parse_macro_if_test
    if parse_macro_if_test(node) is not None:
        raise NotImplementedError('"NAME" in __macro__ 仅可用于 if/elif 条件（译为 #ifdef / #elif），不可作普通表达式')
    left_expr = node.left
    parts = []
    for op, comp in zip(node.ops, node.comparators):
        match op:
            case ast.Eq():
                parts.append(_emit_eq_compare(tr, left_expr, comp))
            case ast.NotEq():
                parts.append(_emit_ne_compare(tr, left_expr, comp))
            case ast.Lt():
                parts.append(f'{tr.visit(left_expr)} < {tr._visit_value_expr(comp)}')
            case ast.LtE():
                parts.append(f'{tr.visit(left_expr)} <= {tr._visit_value_expr(comp)}')
            case ast.Gt():
                parts.append(f'{tr.visit(left_expr)} > {tr._visit_value_expr(comp)}')
            case ast.GtE():
                parts.append(f'{tr.visit(left_expr)} >= {tr._visit_value_expr(comp)}')
            case ast.Is():
                parts.append(_emit_identity_compare(tr, left_expr, comp, is_not=False))
            case ast.IsNot():
                parts.append(_emit_identity_compare(tr, left_expr, comp, is_not=True))
            case ast.In():
                tr._reject_tuple_literal_expr(comp, context='in / not in 的容器')
                if isinstance(comp, ast.Set):
                    parts.append(f'({try_emit_set_literal_contains(tr, comp, left_expr)})')
                elif isinstance(comp, ast.List):
                    parts.append(f'({try_emit_list_literal_contains(tr, comp, left_expr)})')
                elif isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    parts.append(f'({try_emit_str_literal_contains(tr, comp.value, left_expr)})')
                else:
                    left_v = _contains_member_arg(tr, left_expr, comp)
                    if tr._use_member_dispatch_macro(comp):
                        parts.append(tr._cpp_call_expr(comp, '__contains__', left_v, site=node, arg_count=1))
                    else:
                        comp_v = tr.visit(comp)
                        sep = tr._member_access(comp_v)
                        parts.append(f'({comp_v}{sep}__contains__({left_v}))')
            case ast.NotIn():
                tr._reject_tuple_literal_expr(comp, context='in / not in 的容器')
                if isinstance(comp, ast.Set):
                    parts.append(f'({try_emit_set_literal_contains(tr, comp, left_expr, negate=True)})')
                elif isinstance(comp, ast.List):
                    parts.append(f'({try_emit_list_literal_contains(tr, comp, left_expr, negate=True)})')
                elif isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    parts.append(f'({try_emit_str_literal_contains(tr, comp.value, left_expr, negate=True)})')
                else:
                    left_v = _contains_member_arg(tr, left_expr, comp)
                    if tr._use_member_dispatch_macro(comp):
                        parts.append(f"(!{tr._cpp_call_expr(comp, '__contains__', left_v, site=node, arg_count=1)})")
                    else:
                        comp_v = tr.visit(comp)
                        sep = tr._member_access(comp_v)
                        parts.append(f'(!({comp_v}{sep}__contains__({left_v})))')
            case _:
                raise NotImplementedError(op)
        left_expr = comp
    return ' && '.join(parts) if len(parts) > 1 else parts[0]
