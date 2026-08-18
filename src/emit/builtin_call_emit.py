"""内建函数调用、构造与 slice 表达式 emit（自 ``translator.py`` 拆出）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_array_type, is_float64_type, is_float_type, is_int64_type, is_int_type, is_varint_type
from ..analysis.ir import cpp_ident, quote_cpp_string
from ..analysis.module_namespace import namespace_qualifier_for_module, qualify_symbol_in_module
from .fstring_emit import emit_format_expr, plan_format_literal
from ..emit.layout_config_emit import SLICE_START_UNSET, SLICE_STOP_UNSET, _JSON_API_METHODS_NEED_TYPE_ARG, _JSON_API_MODULE
from ..emit.call_emit import call_param_cpp_types, emit_call_args
from ..analysis.stubs.builtin_stubs import builtin_dunder_forward, builtin_global_call
from ..constant.stdlib_layout import RUNTIME_PKG
from ..analysis.runtime_symbols import runtime_make_range_expr
if TYPE_CHECKING:
    from ..translator import Translator

def _default_type_args_cpp(info) -> str | None:
    defaults = info.type_param_defaults
    if not defaults or len(defaults) != len(info.type_params):
        return None
    args: list[str] = []
    for p in info.type_params:
        dv = defaults.get(p)
        if isinstance(dv, ast.Name):
            args.append(cpp_ident(dv.id))
        else:
            return None
    return ', '.join(args)

def emit_user_ctor(tr: Translator, name: str, args: str) -> str:
    if name == 'range':
        return runtime_make_range_expr(args)
    info = tr.classes.get(name)
    if not info:
        return f'{cpp_ident(name)}({args})'
    if info.is_union:
        raise NotImplementedError(f'{name} 为 @union，请使用 Self.<Variant>(...) 构造，勿直接 {name}(...)')
    rc = tr._refcount_ctor_class(info)
    if rc is not None:
        return f'makeRefCount<{info.cpp_name()}>({args})'
    if info.is_template() and info.type_params:
        if tr.class_info and info.name == tr.class_info.name:
            cpp = tr.class_info.cpp_specialization()
        else:
            default_args = _default_type_args_cpp(info)
            cpp = f'{info.cpp_name()}<{default_args}>' if default_args is not None else info.cpp_specialization()
        if info.module_path != RUNTIME_PKG and tr._is_stdlib_module(info.module_path):
            base, _, tail = cpp.partition('<')
            q = qualify_symbol_in_module(info.module_path, base)
            cpp = f'{q}<{tail}' if tail else q
    else:
        cpp = info.cpp_name()
        if info.module_path != RUNTIME_PKG and tr._is_stdlib_module(info.module_path):
            cpp = f'::{qualify_symbol_in_module(info.module_path, cpp)}'
    return f'{cpp}({args})'

def emit_construct(tr: Translator, base: str, args_t: str, inner: str, py_class: str | None=None) -> str:
    spec = f'{base}<{args_t}>' if args_t else base
    if tr._is_boxing_ctor(base, py_class):
        return f'new {spec}({inner})' if inner else f'new {spec}()'
    value_types = {cpp_ident('str'), cpp_ident('int'), cpp_ident('int64'), cpp_ident('float'), cpp_ident('float64'), cpp_ident('bool'), cpp_ident('bytes'), cpp_ident('char'), cpp_ident('byte'), cpp_ident('range'), 'PyList', 'PyDeque', 'PyDict', 'PyTuple', 'PySlice', 'PyIterResult', cpp_ident('RefCount'), cpp_ident('object')}
    if base in value_types or base.startswith('Py') or is_array_type(base):
        return f'{spec}({inner})' if inner else f'{spec}()'
    return f'{spec}({inner})' if inner else f'{spec}()'

def emit_slice_ctor(tr: Translator, sl: ast.Slice) -> str:
    lo = str(SLICE_START_UNSET) if sl.lower is None else tr.visit(sl.lower)
    hi = str(SLICE_STOP_UNSET) if sl.upper is None else tr.visit(sl.upper)
    step = '1' if sl.step is None else tr.visit(sl.step)
    return f"{cpp_ident('slice')}<int, int>({lo}, {hi}, {step})"

def emit_slice_call(tr: Translator, node: ast.Call) -> str:
    args = node.args
    lo = str(SLICE_START_UNSET) if len(args) < 1 else tr.visit(args[0])
    hi = str(SLICE_STOP_UNSET) if len(args) < 2 else tr.visit(args[1])
    step = '1' if len(args) < 3 else tr.visit(args[2])
    return f"{cpp_ident('slice')}<int, int>({lo}, {hi}, {step})"

def emit_scalar_cmp_ternary(left: str, right: str) -> str:
    return f'({left} < {right} ? -1 : ({left} > {right} ? 1 : 0))'

def emit_cmp_call(tr: Translator, left: ast.expr, right: ast.expr) -> str:
    """``__cmp__(a, b)``：标量三目；有 ``__cmp__`` 的类 → ``a.__cmp__(b)``；其余 ``::py2cpp::py_cmp``。"""
    left_t = tr._infer_expr_cpp_type(left)
    right_t = tr._infer_expr_cpp_type(right)
    if (is_int_type(left_t) or is_int64_type(left_t) or is_float_type(left_t) or is_float64_type(left_t)) and (is_int_type(right_t) or is_int64_type(right_t) or is_float_type(right_t) or is_float64_type(right_t)):
        return emit_scalar_cmp_ternary(tr._visit_value_expr(left), tr._visit_value_expr(right))
    if is_varint_type(left_t):
        return tr._member_call_with_arg(left, '__cmp__', right)
    left_info = tr._class_info_for_expr(left)
    if left_info and '__cmp__' in left_info.methods:
        return tr._member_call_with_arg(left, '__cmp__', right)
    return f'::py2cpp::py_cmp({tr._visit_value_expr(left)}, {tr._visit_value_expr(right)})'

def emit_abs_call(tr: Translator, arg: ast.expr) -> str:
    """``abs(x)``：标量内联三目；类实例 ``__abs__``；其余 ``::py2cpp::abs``（与包根桩一致）。"""
    if isinstance(arg, ast.Name) and arg.id == 'self':
        return 'this->__abs__()'
    arg_t = tr._infer_expr_cpp_type(arg)
    if is_int_type(arg_t) or is_int64_type(arg_t) or is_float_type(arg_t):
        e = tr._visit_value_expr(arg)
        return f'({e} < 0 ? -{e} : {e})'
    if is_varint_type(arg_t):
        return emit_instance_dunder_call(tr, '__abs__', arg)
    info = tr._class_info_for_expr(arg)
    if info and '__abs__' in info.methods:
        return emit_instance_dunder_call(tr, '__abs__', arg)
    return f'::py2cpp::py_abs({tr._visit_value_expr(arg)})'

def emit_instance_dunder_call(tr: Translator, method: str, arg: ast.expr, *, extra_args: tuple[ast.expr, ...]=()) -> str:
    """``len(x)`` / ``repr(x)`` 等：按接收者类型选 ``.`` 或 ``->``（含 ``this->_lst`` 指针字段）。"""
    extra = ', '.join((tr.visit(a) for a in extra_args))
    call_inner = f'{method}({extra})' if extra else f'{method}()'
    if isinstance(arg, ast.Name) and arg.id == 'self':
        return f'this->{call_inner}'
    if not extra_args:
        recv, sep = tr._receiver_access(arg)
        return f'{tr._paren_expr(recv)}{sep}{call_inner}'
    if tr._use_member_dispatch_macro(arg):
        if extra_args:
            extra = ', '.join((tr.visit(a) for a in extra_args))
            return tr._cpp_call_expr(arg, method, extra, site=arg, arg_count=len(extra_args))
        return tr._cpp_call_expr(arg, method, site=arg)
    inner = tr.visit(arg)
    if inner == 'this':
        return f'this->{call_inner}'
    sep = tr._member_access(inner)
    if sep == '.' and isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and (arg.value.id == 'self') and tr.class_info:
        ft = tr._field_storage(arg.attr)
        if tr._uses_ptr_access(ft):
            sep = '->'
    return f'{tr._paren_expr(inner)}{sep}{call_inner}'

def try_emit_builtin_dunder_forward(tr: Translator, name: str, node: ast.Call) -> str | None:
    """由 ``py2cpp/__init__.py`` 桩 ``return recv.__dunder__(...)`` 推导的内建转发。"""
    fwd = builtin_dunder_forward(name)
    if fwd is None:
        return None
    expected = 1 + len(fwd.extra_arg_indices)
    if len(node.args) != expected:
        return None
    recv = node.args[fwd.receiver_index]
    extras = tuple((node.args[i] for i in fwd.extra_arg_indices))
    return emit_instance_dunder_call(tr, fwd.dunder, recv, extra_args=extras)

def try_emit_global_builtin_call(tr: Translator, name: str, node: ast.Call) -> str | None:
    """``@global_call`` 包根内建 → ``::fn(...)``。"""
    spec = builtin_global_call(name)
    if spec is None:
        return None
    if len(node.args) not in spec.arg_counts:
        return None
    args = ', '.join((tr._visit_value_expr(a) for a in node.args))
    return f'::{spec.cpp_name}({args})'

def try_emit_scandir_ctor_call(tr: Translator, name: str, node: ast.Call) -> str | None:
    """``os.scandir`` 返回迭代器：直接构造 ``PyScandirIterator``，避免按值返回的拷贝/移动陷阱。"""
    if name != 'scandir' or node.keywords or len(node.args) != 1:
        return None
    binding = tr._effective_import_bindings().get(name)
    if binding is None or binding.cpp_name != 'scandir':
        return None
    from ..analysis.module_namespace import namespace_qualifier_for_module
    path = tr._visit_value_expr(node.args[0])
    ns = namespace_qualifier_for_module(binding.module_path) or 'py2cpp::io::file'
    return f'::{ns}::{cpp_ident("ScandirIterator")}({path})'

def format_spec_literal(node: ast.expr) -> str | None:
    """f-string 内 ``format_spec`` 常为 ``JoinedStr``；能静态求值则返回规格串。"""
    match node:
        case ast.Constant(value=text) if isinstance(text, str):
            return text
        case ast.JoinedStr(values=parts):
            out: list[str] = []
            for part in parts:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    out.append(part.value)
                else:
                    return None
            return ''.join(out)
        case _:
            return None

def format_spec_cpp(tr: Translator, node: ast.expr | None) -> str:
    """``format_spec`` 编译期字符串 → ``CStr`` 字面量。"""
    if node is None:
        return quote_cpp_string('')
    lit = format_spec_literal(node)
    if lit is not None:
        return quote_cpp_string(lit)
    return tr._visit_value_expr(node)

def emit_format_call(tr: Translator, value_expr: str, format_spec: ast.expr | str | None=None) -> str:
    """全局 ``format(value[, format_spec])`` → ``::format``（转发 ``__format__``）。"""
    if isinstance(format_spec, ast.expr):
        spec = format_spec_cpp(tr, format_spec)
    elif format_spec is None:
        spec = quote_cpp_string('')
    else:
        spec = format_spec
    return f'::format({value_expr}, {spec})'

def emit_str_format_call(tr: Translator, node: ast.Call) -> str:
    """``str.format("{}", x)`` → ``PyStr::format``（``{}`` 占位）。"""
    if not node.args:
        raise NotImplementedError('str.format 至少需要一个格式串参数')
    fmt_arg = node.args[0]
    if isinstance(fmt_arg, ast.Constant) and isinstance(fmt_arg.value, str):
        return emit_format_expr(tr, plan_format_literal(tr, fmt_arg.value, list(node.args[1:])))
    raise NotImplementedError('str.format 格式串须为编译期字符串字面量（含 ``{}`` 占位）')

def is_json_class_ref(tr: Translator, name: str) -> bool:
    if not tr._name_refers_to_class(name):
        return False
    info = tr._class_info_for_ref(name)
    return info is not None and info.name == 'Json'

def json_api_callee(method: str) -> str:
    ns = namespace_qualifier_for_module(_JSON_API_MODULE)
    return f'::{ns}::{cpp_ident("Json")}::{method}'

def emit_json_class_api_call(tr: Translator, method: str, type_arg: str | None, node: ast.Call) -> str | None:
    """``Json.loads[T]`` / ``Json.load[T]``（``json.inl`` 模板 API）。"""
    if method not in _JSON_API_METHODS_NEED_TYPE_ARG:
        return None
    args = emit_call_args(tr, node, param_cpp_types=call_param_cpp_types(tr, node.func, call=node))
    callee = json_api_callee(method)
    if not type_arg:
        return None
    if args:
        return f'{callee}<{type_arg}>({args})'
    return f'{callee}<{type_arg}>()'
