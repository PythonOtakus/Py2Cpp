"""编码规范强检查（``--strict``，默认开启）。

S01–S29 按 A–F 分组（见 ``docs/编码规范.md`` §1.1）；``S06`` 构造优先级用子码 ``S06a``–``S06e``；``S18`` 为覆盖基类 ``@virtual``/``@abstract`` 方法（含继承链上纯虚/虚声明）时子类须 ``@override``；**静态**：覆盖基类 ``@staticmethod``+``@override``，或模块内 ``func[Cls]`` 绑定之 ``@protocol`` 静态虚成员，亦须 ``@staticmethod``+``@override``（不检查 dunder；``@mixin`` 基类豁免）；``S27`` 为 import 布局；``S28`` 为堆/栈数组切片注解；``S29`` 为同类型反向 dunder；``S30`` 为继承顺序（mixin 在实体类前、至多一个实体基类）；``S31`` 禁止显式 ``RefCount``（含 ``RefCount()`` / ``RefCount[T]``；``@refcount`` 类与 ``T: refcount`` 须写 ``T``，清空用 ``new()``）；``S32`` 为 ``@dataclass`` 须至少一个非 ``@optional`` 实例字段；``S33`` 禁止类成员名 ``assign``/``build``/``select``（与译期专用 API 冲突）；``S34`` 禁止非字面量 ``ord``；``S35`` 禁止仅作类型转换且无再赋值的注解临时变量（勿 ``n: int = int(x); return n``）；``S36`` 禁止定长元组解包中未使用的具名绑定（须 ``_`` / ``*_``）；``S37`` 禁止显式 ``PyNone``（须写 ``None``；``py2cpp/core/none.py`` 豁免）；``S38`` 禁止 ``for x in …: yield x``（须 ``yield from …``；``async def`` 异步生成器豁免；``for`` ``else`` 分支除外）；``S41`` 禁止 ``return self._field`` 与 ``self._field = 形参`` 成对的手写 getter/setter（须 ``@property`` 或公有字段）；``S42`` 禁止 trivial ``@property`` getter + 顶层 ``self._field = value`` 与其它语句的 ``@property.setter``（须 ``@property.postsetter`` / 字段简写）；``S45`` 禁止非 ``@dataclass`` 字段使用 ``@optional``；``S46`` 禁止仅为 ``new`` 造类型上下文的注解临时变量（勿 ``sp: T = new(...); self.f = sp`` / ``fn(sp)``，须 ``self.f = new(...)`` 或实参处 ``fn(Cls(...))`` / ``fn(Union.Variant(...))``）；``S47`` 强制特殊类型 / Meta / Var / Mixin / 异常类名后缀（见编码规范 §1.0.2）；``S48`` 禁止类 PEP 695 形参使用单字母或单字母+数字（``T`` / ``T1``；须 ``Element`` / ``Key`` 等语义名）。
检查 ``py2cpp/``、用户模块与 ``test/**``；``test/fail/`` 豁免；``# py2cpp: strict-off`` 可关单文件。

内部 helper 前缀 ``_sNN_`` / ``_check_sNN_`` 与 §1.1 规则 ID 一致。
"""
from __future__ import annotations
import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from ..analysis.stubs.builtin_stubs import DEDUCED_TEMPLATE_MEMORY_FUNCS as _DEDUCED_MEMORY_FUNCS
from ..analysis.type_pred import is_char_type, is_optional_type, is_str_type
from ..analysis.type_emit import field_ann_ast
from ..analysis.ir import ClassInfo, FuncTypeConstraint, FuncTypeParametricBound, FuncTypeParams, FunctionSig, MethodSig, cpp_ident, has_named_decorator, has_enum_mro_decorator, has_union_mro_decorator, pep695_declared_type_params, pep695_used_type_params, strip_type_annotation_markers
from ..emit.binop_emit import is_single_char_str_constant
from .enum_expand import enum_member_names
from .enum_match import _parse_enum_or_value
from .kwargs_options import TRANSLATOR_ONLY_METHODS as _S33_RESERVED_MEMBER_NAMES
from .match_case import is_wildcard_pattern
from ..translation_error import SourceLocation, TranslationError, location_from_node
if TYPE_CHECKING:
    from ..translator import Translator
_STRICT_OFF_FILE = re.compile('^\\s*#\\s*py2cpp:\\s*strict-off\\s*$', re.MULTILINE)
_STRICT_OFF_LINE = re.compile('#\\s*py2cpp:\\s*strict-off')
S01 = 'S01'
S02 = 'S02'
S03 = 'S03'
S04 = 'S04'
S05 = 'S05'
S06A = 'S06a'
S06B = 'S06b'
S06C = 'S06c'
S06D = 'S06d'
S06E = 'S06e'
S07 = 'S07'
S08 = 'S08'
S09 = 'S09'
S10 = 'S10'
S11 = 'S11'
S12 = 'S12'
S13 = 'S13'
S14 = 'S14'
S15 = 'S15'
S16 = 'S16'
S17 = 'S17'
S18 = 'S18'
S19 = 'S19'
S20 = 'S20'
S21 = 'S21'
S22 = 'S22'
S23 = 'S23'
S24 = 'S24'
S25 = 'S25'
S26 = 'S26'
S27 = 'S27'
S28 = 'S28'
S29 = 'S29'
S30 = 'S30'
S31 = 'S31'
S32 = 'S32'
S33 = 'S33'
S34 = 'S34'
S35 = 'S35'
S36 = 'S36'
S37 = 'S37'
S38 = 'S38'
S39 = 'S39'
S40 = 'S40'
S41 = 'S41'
S42 = 'S42'
S43 = 'S43'
S44 = 'S44'
S45 = 'S45'
S46 = 'S46'
S47 = 'S47'
S48 = 'S48'
_PRIMITIVE_CONVERT_CTORS = frozenset({'int', 'float', 'bool', 'char', 'byte', 'str', 'int64', 'float64', 'uint', 'uint64', 'uintptr'})
# 类 PEP 695 形参禁止单字母 / 单字母+数字（``T`` / ``T1``）；会落成 ``using`` 别名，须语义化。
_SHORT_CLASS_TYPE_PARAM = re.compile(r'^[A-Za-z]\d*$')
_UNION_NAME_EXEMPT_S47 = frozenset({'Result', 'Optional', 'IterResult'})
# CPython 同名异常：不强制 ``*Error``（含已以 Error 结尾的内建名）。
_CPYTHON_EXCEPTION_NAMES_S47 = frozenset({
    'BaseException', 'Exception', 'GeneratorExit', 'KeyboardInterrupt', 'SystemExit',
    'StopIteration', 'StopAsyncIteration',
    'ArithmeticError', 'FloatingPointError', 'OverflowError', 'ZeroDivisionError',
    'AssertionError', 'AttributeError', 'BufferError', 'EOFError',
    'ImportError', 'ModuleNotFoundError', 'LookupError', 'IndexError', 'KeyError',
    'MemoryError', 'NameError', 'UnboundLocalError',
    'OSError', 'BlockingIOError', 'ChildProcessError', 'ConnectionError',
    'BrokenPipeError', 'ConnectionAbortedError', 'ConnectionRefusedError',
    'ConnectionResetError', 'FileExistsError', 'FileNotFoundError',
    'InterruptedError', 'IsADirectoryError', 'NotADirectoryError',
    'PermissionError', 'ProcessLookupError', 'TimeoutError',
    'ReferenceError', 'RuntimeError', 'NotImplementedError', 'RecursionError',
    'SyntaxError', 'IndentationError', 'TabError',
    'SystemError', 'TypeError', 'ValueError', 'UnicodeError',
    'UnicodeDecodeError', 'UnicodeEncodeError', 'UnicodeTranslateError',
    'Warning', 'UserWarning', 'DeprecationWarning', 'PendingDeprecationWarning',
    'SyntaxWarning', 'RuntimeWarning', 'FutureWarning', 'ImportWarning',
    'UnicodeWarning', 'BytesWarning', 'ResourceWarning', 'EncodingWarning',
    'ExceptionGroup', 'BaseExceptionGroup',
    'BrokenBarrierError', 'CancelledError', 'InvalidStateError',
    'StatisticsError', 'JSONDecodeError',
    'DatabaseError', 'IntegrityError', 'OperationalError',
})
_S47_SUFFIX_RULES: tuple[tuple[str, str, str], ...] = (
    ('protocol', 'Type', '@protocol'),
    ('boxing', 'Unsafe', '@boxing'),
    ('annotation', 'Meta', '@annotation'),
    ('descriptor', 'Var', '@descriptor'),
    ('mixin', 'Mixin', '@mixin'),
)
# ``@delegate`` 为函数定义（非 ClassDef），见 ``_check_s47_naming_suffixes``
_SLICE_ARRAY_ANN_ROOTS = frozenset({'array', 'array2d', 'array3d', 'StackArray', 'StackArray2d', 'StackArray3d'})
_S20_MIN_DISPATCH_BRANCHES = 3
_S21_MIN_COMPARE_CHAIN_ARMS = 2
_EMPTY_CONTAINER_FACTORIES = frozenset({'list', 'dict', 'deque', 'tuple', 'frozendict', 'frozenlist'})
_EMPTY_SET_FACTORIES = frozenset({'set', 'frozenset'})
_NO_EMPTY_MAKE_ANN_ROOTS = frozenset({'deque'})
_SELF_LITERAL_HOST_HINTS: dict[str, str] = {'str': '""', 'bytes': 'b""', 'list': '[]', 'deque': '[]', 'array': '[]', 'array2d': '[]', 'array3d': '[]', 'frozenlist': '[]', 'dict': '{}', 'frozendict': '{}', 'Counter': '{}', 'set': 'new()', 'frozenset': 'new()'}
_SELF_LITERAL_HOST_CLASSES = frozenset(_SELF_LITERAL_HOST_HINTS)
_DESUGAR_CLASS_SUFFIXES = ('_coroutine', '_generator')
_DESUGAR_PROTO_DUNDERS = frozenset({'__aenter__', '__aexit__'})
_S01_GLOBAL_DUNDERS = frozenset({'__await__'})
_AUG_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.MatMult, ast.FloorDiv, ast.Mod, ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift)
_CPP_STYLE_METHOD_ALLOWLIST = frozenset({'reserve', 'reshape', 'capacity', 'clear', 'insert', 'remove', 'discard', 'update', 'get', 'find', 'index', 'rfind', 'rindex', 'startswith', 'endswith', 'startsWith', 'endsWith', 'split', 'strip', 'append', 'extend', 'pop', 'popLeft', 'appendLeft', 'add', 'copy', 'move', 'items', 'keys', 'values', 'getstate', 'setstate', 'getState', 'setState', 'getsize', 'getSize', 'getmtime', 'getMtime', 'getctime', 'getCtime', 'getatime', 'getAtime', 'join', 'replace', 'format', 'encode', 'decode'})
# 类限定 S02 豁免：空间矩形允许 ``contains`` / ``size``（非容器 ``len`` 语义）
_S02_CLASS_METHOD_ALLOW: dict[str, frozenset[str]] = {'Rect': frozenset({'contains', 'size'})}
_CPP_STYLE_METHOD_ALIASES: dict[str, str] = {'push_back': 'append', 'push_copy': 'append', 'pop_back': 'pop', 'emplace_back': 'append', 'emplace': 'append', 'assign_copy': 'copy_from(other)', 'subgroup_len': 'len(container) 或 __len__', 'push_front': 'insert(0, item) 或 deque.appendLeft', 'pop_front': 'popLeft', 'shrink_to_fit': '勿引入；用容器/缓冲自有扩容语义', 'substr': '切片 s[i:j]', 'erase': 'pop / del / remove', 'is_empty': 'not container', 'isempty': 'not container', 'get_size': 'len(container)', 'contains': 'item in container', 'front': 'seq[0]', 'back': 'seq[-1]', 'size': 'len(container)', 'empty': 'not container 或 if not container', 'length': 'len(container)', 'pushback': 'append', 'popback': 'pop', 'emplaceback': 'append'}
_CAMEL_CASE_BOUNDARY = re.compile('(?<!^)(?=[A-Z])')
_BUILTIN_CTORS = frozenset({'int', 'float', 'bool', 'new', 'range', 'print', 'len', 'min', 'max', 'abs', 'enumerate', 'zip', 'super', 'type', 'isinstance', 'hasattr', 'getattr', 'setattr', 'ord', 'chr', 'hex', 'oct', 'bin', 'repr', 'str', 'bytes'})

@dataclass(frozen=True)
class _Violation:
    rule: str
    message: str
    node: ast.AST
    module_path: str
_S31_EXEMPT = frozenset({'py2cpp/core/refcount.py', 'py2cpp/core/refcount'})

def _s31_module_exempt(module_path: str) -> bool:
    norm = module_path.replace('\\', '/')
    if norm in _S31_EXEMPT:
        return True
    return norm.endswith('/py2cpp/core/refcount.py') or norm.endswith('/py2cpp/core/refcount')
_S37_EXEMPT = frozenset({'py2cpp/core/none.py', 'py2cpp/core/none'})

def _s37_module_exempt(module_path: str) -> bool:
    norm = module_path.replace('\\', '/')
    if norm in _S37_EXEMPT:
        return True
    return norm.endswith('/py2cpp/core/none.py') or norm.endswith('/py2cpp/core/none')

def check_strict_style(tr: TranslatorState):
    if not getattr(tr, 'strict', True):
        return
    violations: list[_Violation] = []
    for module_path, tree in tr.module_asts.items():
        if not _should_check_module(tr, module_path):
            continue
        source = _module_source(tr, module_path)
        lines = source.splitlines() if source else []
        checker = _StrictStyleChecker(tr, module_path, lines)
        checker.visit(tree)
        violations.extend(checker.violations)
        _check_s17_overload(tr, module_path, tree, violations)
        _check_s18_override_virtual(tr, module_path, violations)
        _check_s39_method_decorator_conflicts(tr, module_path, violations)
        _check_static_virtual_protocol_rules(tr, module_path, violations)
        _check_s19_unused_pep695_type_params(tree, module_path, violations)
        _check_s29_reverse_self_dunder(tr, module_path, violations)
        _check_s47_naming_suffixes(tree, module_path, violations)
    _check_s41_private_field_accessor_pairs(tr, violations)
    _check_s42_prefer_postsetter(tr, violations)
    _check_s26_dataclass_container_optional(tr, violations)
    _check_s27_imports(tr, violations)
    _check_s28_slice_array_annotations(tr, violations)
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处编码规范违规（可用 --no-strict 关闭）：']
    first_loc: SourceLocation | None = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)

def check_refcount_source_style(tr: TranslatorState) -> None:
    """S31：全模块（含 ``test/fail/``）禁止显式 ``RefCount``。"""
    if not getattr(tr, 'strict', True):
        return
    violations: list[_Violation] = []
    for module_path, tree in tr.module_asts.items():
        skip = getattr(tr, 'skip_cached_analysis_module', None)
        if skip is not None and skip(module_path):
            continue
        norm = module_path.replace('\\', '/')
        if _s31_module_exempt(module_path):
            continue
        source = _module_source(tr, module_path)
        lines = source.splitlines() if source else []
        checker = _StrictStyleChecker(tr, module_path, lines)
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                checker._check_s31_refcount_subscript(node)
            elif isinstance(node, ast.Call):
                checker._check_s31_refcount_call(node)
        violations.extend(checker.violations)
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处 RefCount 用法违规（S31）：']
    first_loc: SourceLocation | None = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)
_S37_PYNONE_NAME = re.compile('\\bPyNone\\b')

def check_pynone_source_style(tr: TranslatorState) -> None:
    """S37：全模块（含 ``test/fail/``）禁止显式 ``PyNone``（查源码，非脱糖 AST）。"""
    if not getattr(tr, 'strict', True):
        return
    violations: list[_Violation] = []
    for module_path in tr.module_asts:
        skip = getattr(tr, 'skip_cached_analysis_module', None)
        if skip is not None and skip(module_path):
            continue
        if _s37_module_exempt(module_path):
            continue
        source = _module_source(tr, module_path)
        if not source or _STRICT_OFF_FILE.search(source):
            continue
        seen_lines: set[int] = set()
        for m in _S37_PYNONE_NAME.finditer(source):
            lineno = source.count('\n', 0, m.start()) + 1
            if lineno in seen_lines:
                continue
            if lineno <= 0 or lineno > len(source.splitlines()):
                continue
            line = source.splitlines()[lineno - 1]
            if _STRICT_OFF_LINE.search(line):
                continue
            seen_lines.add(lineno)
            node = ast.Name(id='PyNone', lineno=lineno, col_offset=m.start())
            violations.append(_Violation(S37, _strict_msg('PyNone', 'None', '源码', reason='``PyNone`` 为 C++ 基础设施类型名；注解与表达式须写 ``None``（如 ``IterResult[T, None]``）', example='got: -> IterResult[T, None]'), node, module_path))
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处 PyNone 用法违规（S37）：']
    first_loc: SourceLocation | None = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)

def _s47_enum_is_flag(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Name) or dec.func.id != 'enum':
            continue
        for kw in dec.keywords:
            if kw.arg == 'flag' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False

def _s47_base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name):
        return base.value.id
    return None

def _s47_collect_exception_names(tree: ast.Module) -> set[str]:
    """模块内继承 ``Exception`` / ``*Error`` 的类名闭包（含字面 ``Exception``）。"""
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    exc: set[str] = {'Exception'}
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in exc:
                continue
            for base in node.bases:
                b = _s47_base_name(base)
                if b is None:
                    continue
                if b in exc or b.endswith('Error'):
                    exc.add(node.name)
                    changed = True
                    break
    return exc

def _s47_require_suffix(name: str, suffix: str) -> bool:
    return name.endswith(suffix)

def _check_s47_naming_suffixes(tree: ast.Module, module_path: str, violations: list[_Violation]) -> None:
    """S47：特殊类型 / Meta / Var / Mixin / Delegate / 异常类名后缀（见编码规范 §1.0.2）。"""
    from ..constant.ffi_layout import is_ffi_module_path
    # C 结构体名可能含 Exception（如 ``_exception`` → ``PyiException``），非 Python 异常类
    if is_ffi_module_path(module_path.replace("\\", "/")):
        return
    exc_names = _s47_collect_exception_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and has_named_decorator(node, 'delegate'):
            name = node.name
            if not _s47_require_suffix(name, 'Delegate'):
                violations.append(_Violation(S47, _strict_msg(name, f'{name}…Delegate', f'def {name}', reason='``@delegate`` 名须以 ``Delegate`` 结尾', example='got: @delegate def UIEventDelegate(): …'), node, module_path))
            continue
        if not isinstance(node, ast.ClassDef):
            continue
        name = node.name
        if has_enum_mro_decorator(node):
            if not _s47_require_suffix(name, 'TypeEnum'):
                violations.append(_Violation(S47, _strict_msg(name, f'{name}…TypeEnum', f'class {name}', reason='``@enum.mro`` 类名须以 ``TypeEnum`` 结尾', example='got: @enum.mro class PetKindTypeEnum(base=…):'), node, module_path))
            continue
        if has_named_decorator(node, 'enum'):
            if _s47_enum_is_flag(node):
                if not _s47_require_suffix(name, 'Flag'):
                    violations.append(_Violation(S47, _strict_msg(name, f'{name}…Flag', f'class {name}', reason='``@enum(flag=True)`` 类名须以 ``Flag`` 结尾', example='got: @enum(flag=True) class PermFlag:'), node, module_path))
            elif not _s47_require_suffix(name, 'Enum'):
                violations.append(_Violation(S47, _strict_msg(name, f'{name}…Enum', f'class {name}', reason='``@enum`` 类名须以 ``Enum`` 结尾', example='got: @enum class ModeEnum:'), node, module_path))
            continue
        if has_union_mro_decorator(node):
            if not _s47_require_suffix(name, 'TypeUnion'):
                violations.append(_Violation(S47, _strict_msg(name, f'{name}…TypeUnion', f'class {name}', reason='``@union.mro`` 类名须以 ``TypeUnion`` 结尾', example='got: @union.mro class ExcTypeUnion(base=…):'), node, module_path))
            continue
        if has_named_decorator(node, 'union'):
            if name not in _UNION_NAME_EXEMPT_S47 and not _s47_require_suffix(name, 'Union'):
                violations.append(_Violation(S47, _strict_msg(name, f'{name}…Union', f'class {name}', reason='``@union`` 类名须以 ``Union`` 结尾（豁免 Result / Optional / IterResult）', example='got: @union class MessageUnion:'), node, module_path))
            continue
        for deco, suffix, label in _S47_SUFFIX_RULES:
            if has_named_decorator(node, deco):
                if not _s47_require_suffix(name, suffix):
                    violations.append(_Violation(S47, _strict_msg(name, f'{name}…{suffix}', f'class {name}', reason=f'``{label}`` 类名须以 ``{suffix}`` 结尾', example=f'got: {label} class Foo{suffix}:'), node, module_path))
                break
        if name in _CPYTHON_EXCEPTION_NAMES_S47:
            continue
        if name in exc_names or name.endswith('Exception'):
            if not name.endswith('Error'):
                violations.append(_Violation(S47, _strict_msg(name, f'{name}…Error', f'class {name}', reason='异常类除 CPython 同名外须以 ``Error`` 结尾', example='got: class EmptyError(Exception):'), node, module_path))

def _should_check_module(tr: Translator, module_path: str) -> bool:
    skip = getattr(tr, 'skip_cached_analysis_module', None)
    if skip is not None and skip(module_path):
        return False
    norm = module_path.replace('\\', '/')
    if '/test/fail/' in f'/{norm}/' or norm.startswith('test/fail/'):
        return False
    if norm.endswith('_fail') or '/test_fail/' in f'/{norm}/':
        return False
    source = _module_source(tr, module_path)
    if source and _STRICT_OFF_FILE.search(source):
        return False
    return True

def _module_source(tr: Translator, module_path: str) -> str:
    path = tr.module_py_paths.get(module_path)
    if path is None:
        return ''
    try:
        return path.read_text(encoding='utf-8')
    except OSError:
        return ''

def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith('__') and name.endswith('__')

def _call_target_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Subscript) and isinstance(func.value, ast.Name):
        return func.value.id
    return None

def _is_int_zero_literal(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and isinstance(expr.value, int) and (expr.value == 0)

def _is_int_one_literal(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and isinstance(expr.value, int) and (expr.value == 1)

def _s13_parse_range_start_stop_step(node: ast.Call) -> tuple[ast.expr, ast.expr, ast.expr | None] | None:
    """两/三参数 ``range(start, stop[, step])``；单参数 ``range(n)`` 返回 ``None``。"""
    if _call_target_name(node.func) != 'range':
        return None
    kw_map = {kw.arg: kw.value for kw in node.keywords if kw.arg}
    args = list(node.args)
    if len(args) > 3 or len(kw_map) > 3:
        return None
    start: ast.expr | None = kw_map.get('start')
    stop: ast.expr | None = kw_map.get('stop')
    step: ast.expr | None = kw_map.get('step')
    if len(args) == 3:
        if start is None:
            start = args[0]
        if stop is None:
            stop = args[1]
        if step is None:
            step = args[2]
    elif len(args) == 2:
        if start is None:
            start = args[0]
        if stop is None:
            stop = args[1]
    elif len(args) == 1:
        return None
    elif len(args) != 0:
        return None
    if start is None or stop is None:
        return None
    return (start, stop, step)

def _s13_try_range_redundant_form(node: ast.Call) -> str | None:
    """``range(0, n)``/``, 1)`` → ``range(n)``；``range(a, b, 1)`` → ``range(a, b)``。"""
    parsed = _s13_parse_range_start_stop_step(node)
    if parsed is None:
        return None
    start, stop, step = parsed
    start_t = ast.unparse(start)
    stop_t = ast.unparse(stop)
    zero_start = _is_int_zero_literal(start)
    if step is None:
        if not zero_start:
            return None
        wrong = f'`range(0, {stop_t})`'
        right = f'`range({stop_t})`'
        example = f'`for i in range({stop_t}):` 勿 `for i in range(0, {stop_t}):`'
        reason = '起始为 0 时省略下界，写 ``range(n)`` 勿 ``range(0, n)``'
    elif not _is_int_one_literal(step):
        return None
    elif zero_start:
        wrong = f'`range(0, {stop_t}, 1)`'
        right = f'`range({stop_t})`'
        example = f'`for i in range({stop_t}):` 勿 `for i in range(0, {stop_t}, 1):`'
        reason = '起始为 0、步长为 1 时写 ``range(n)``，勿写冗余的 ``0``/``, 1``'
    else:
        wrong = f'`range({start_t}, {stop_t}, 1)`'
        right = f'`range({start_t}, {stop_t})`'
        example = f'`for i in range({start_t}, {stop_t}):` 勿 `for i in range({start_t}, {stop_t}, 1):`'
        reason = '步长为 1 时省略第三参数，写 ``range(a, b)`` 勿 ``range(a, b, 1)``'
    return _strict_msg(wrong, right, '``range`` 调用处', example=example, reason=reason)
_METHOD_FORWARD_RECEIVERS = frozenset({'self', 'cls'})

def _s03_forward_param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: list[str] = []
    for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
        if arg.arg not in ('self', 'cls'):
            names.append(arg.arg)
    return set(names)

def _s03_body_single_forward_call(body: list[ast.stmt]) -> ast.Call | None:
    if len(body) != 1:
        return None
    stmt = body[0]
    if isinstance(stmt, ast.Return):
        inner = stmt.value
    elif isinstance(stmt, ast.Expr):
        inner = stmt.value
    else:
        return None
    if inner is None:
        return None
    if not isinstance(inner, ast.Call) or inner.keywords:
        return None
    return inner

def _s03_call_arg_names(call: ast.Call) -> set[str] | None:
    out: set[str] = set()
    for arg in call.args:
        if not isinstance(arg, ast.Name):
            return None
        out.add(arg.id)
    return out

def _s03_method_param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [arg.arg for arg in node.args.posonlyargs + node.args.args]

def _s03_forward_args_match_params(node: ast.FunctionDef | ast.AsyncFunctionDef, call: ast.Call) -> bool:
    expected = _s03_method_param_names(node)
    if len(call.args) != len(expected):
        return False
    for name, arg in zip(expected, call.args):
        if not isinstance(arg, ast.Name) or arg.id != name:
            return False
    return True

def _s03_try_thin_param_forward(node: ast.FunctionDef | ast.AsyncFunctionDef, *, class_methods: set[str] | None, module_funcs: set[str], self_like: set[str]) -> str | None:
    if _is_dunder(node.name):
        return None
    if _is_property_accessor(node):
        return None
    if has_named_decorator(node, 'overload'):
        return None
    if node.name.startswith('scan_test_') or node.name.startswith('scanTest'):
        return None
    call = _s03_body_single_forward_call(node.body)
    if call is None:
        return None
    if isinstance(call.func, ast.Attribute):
        if not isinstance(call.func.value, ast.Name):
            return None
        recv = call.func.value.id
        callee = call.func.attr
        if recv == 'Self':
            if class_methods is None or callee not in class_methods:
                return None
            if not _s03_forward_args_match_params(node, call):
                return None
            call_args = ', '.join(_s03_method_param_names(node))
            wrong = f'`def {node.name}(…): return Self.{callee}({call_args})`'
            example = f'删除 `{node.name}`，调用方直接写 `Self.{callee}(…)`'
            return _strict_msg(wrong, f'直接调用 Self.{callee}(…)', '同文件/同类仅转发参数的薄封装处', example=example, reason='除参数置换外无额外逻辑，薄封装徒增译码层数')
        if recv not in _METHOD_FORWARD_RECEIVERS and recv not in self_like:
            return None
        if class_methods is None or callee not in class_methods:
            return None
        params = _s03_forward_param_names(node)
        if not params:
            return None
        arg_names = _s03_call_arg_names(call)
        if arg_names is None or arg_names != params:
            return None
        call_args = ', '.join((a.id for a in call.args))
        wrong = f'`def {node.name}(…): return {recv}.{callee}({call_args})`'
        example = f'删除 `{node.name}`，调用方直接写 `{recv}.{callee}(…)`'
        return _strict_msg(wrong, f'直接调用 {callee}(…)', '同文件/同类仅转发参数的薄封装处', example=example, reason='除参数置换外无额外逻辑，薄封装徒增译码层数')
    if isinstance(call.func, ast.Name):
        callee = call.func.id
        if callee not in module_funcs:
            return None
        if callee == node.name or _is_dunder(callee):
            return None
        if not _s03_forward_args_match_params(node, call):
            return None
        call_args = ', '.join(_s03_method_param_names(node))
        wrong = f'`def {node.name}(…): return {callee}({call_args})`'
        example = f'删除 `{node.name}`，调用方直接写 `{callee}(…)`'
        return _strict_msg(wrong, f'直接调用 {callee}(…)', '同文件/同类仅转发参数的薄封装处', example=example, reason='除参数置换外无额外逻辑，薄封装徒增译码层数')
    return None
_TESTCASE_BASES = frozenset({'TestCase', 'TestCaseMixin'})

def _is_testcase_host(info: ClassInfo) -> bool:
    return bool(_TESTCASE_BASES.intersection(info.bases))

def _is_new_call(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and _call_target_name(node.func) == 'new'

def _is_new_receiver_attribute(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and (node.value.id == 'new')

def _is_new_ctor_expr(node: ast.expr | None) -> bool:
    """``new()`` / ``new(...)`` / ``new.方法(...)`` / ``new.静态属性``。"""
    if node is None:
        return False
    if _is_new_call(node):
        return True
    if isinstance(node, ast.Call) and _is_new_receiver_attribute(node.func):
        return True
    return _is_new_receiver_attribute(node)

def _ann_root_name(ann: ast.expr | None) -> str | None:
    if ann is None:
        return None
    core = strip_type_annotation_markers(ann)
    if core is None:
        return None
    if isinstance(core, ast.Name):
        return core.id
    if isinstance(core, ast.Subscript) and isinstance(core.value, ast.Name):
        return core.value.id
    return None

def _ann_is_self(ann: ast.expr | None) -> bool:
    return _ann_root_name(ann) == 'Self'

def _s02_alias_key_for_name(name: str) -> str | None:
    """将方法名（及去掉前导 ``_`` 后的形式）映射到 ``_CPP_STYLE_METHOD_ALIASES`` 键。"""
    if name in _CPP_STYLE_METHOD_ALLOWLIST:
        return None
    stripped = name.lstrip('_')
    if stripped and stripped in _CPP_STYLE_METHOD_ALLOWLIST:
        return None
    candidates = (name, stripped) if stripped and stripped != name else (name,)
    for cand in candidates:
        if cand in _CPP_STYLE_METHOD_ALIASES:
            return cand
        if '_' not in cand and any((c.isupper() for c in cand)):
            snake = _CAMEL_CASE_BOUNDARY.sub('_', cand).lower()
            if snake in _CPP_STYLE_METHOD_ALIASES:
                return snake
    return None

def _cpp_style_alias_key(name: str) -> str | None:
    if _is_dunder(name):
        return None
    return _s02_alias_key_for_name(name)
_S33_MEMBER_HINTS: dict[str, str] = {'assign': '字段赋值请用译期 ``obj.assign(kw=…)``，就地拷贝请 ``copy_from(other)``', 'build': '对象构造请用译期 ``Type.build("…")``', 'select': '路径读请用译期 ``obj.select("…")``'}

def _s33_translator_only_member_message(name: str, class_name: str, *, kind: str) -> str:
    hint = _S33_MEMBER_HINTS.get(name, '改用其它名称')
    return _strict_msg(f'类 `{class_name}` 的{kind} `{name}`', hint, '类体方法 / 属性 / 字段定义处', reason=f'``{name}`` 为译期专用标识符（``TRANSLATOR_ONLY_METHODS``），类成员同名会冲突', example=f'勿 `def {name}` / `{name}: T`；{hint}')

def _s02_cpp_style_message(name: str) -> str | None:
    key = _cpp_style_alias_key(name)
    if key is None:
        return None
    hint = _CPP_STYLE_METHOD_ALIASES[key]
    stripped = name.lstrip('_')
    if stripped != name and key == stripped:
        return _strict_msg(f'`def {name}`', f'Python/py2cpp 命名（{hint}）', '类/实例方法定义处', example=f'勿用前导 `_` 规避 {S02}；应写 `def append` 等，勿 `def _{key}`', reason=f'去掉前导 `_` 后仍为 C++/STL 风格名 `{key}`')
    return _strict_msg(f'`def {name}`', f'Python/py2cpp 命名（{hint}）', '类/实例方法定义处', example=f'将 `def {name}(…)` 改为规范写法（见编码规范 {S02} 表）', reason='勿引入 C++/STL 风格方法名')

def _s01_dunder_alternative(attr: str) -> str:
    if attr == '__cmp__':
        return '全局 ``__cmp__(a, b)``（勿 ``x.__cmp__(y)``）'
    if attr == '__mod__':
        return '``x % y`` 或全局 ``__mod__(x, y)``'
    if attr == '__truediv__':
        return '``x / y`` 或全局 ``__truediv__(x, y)``'
    if attr == '__floordiv__':
        return '``x // y`` 或全局 ``__floordiv__(x, y)``'
    alts: dict[str, str] = {'__len__': '`len(x)`', '__bool__': '`if x` / `not x`', '__contains__': '`item in x`', '__getitem__': '`x[i]`', '__setitem__': '`x[i] = v`', '__iter__': '`for v in x`', '__add__': '`x + y`', '__sub__': '`x - y`', '__mul__': '`x * y`', '__eq__': '`x == y`', '__ne__': '`x != y`', '__lt__': '`x < y`', '__le__': '`x <= y`', '__gt__': '`x > y`', '__ge__': '`x >= y`'}
    return alts.get(attr, f'对应运算符或内建（见编码规范 §1.1 {S01}）')

def _s01_dunder_call_message(attr: str) -> str:
    alt = _s01_dunder_alternative(attr)
    return _strict_msg(f'`.{attr}()`', alt, '调用表达式中', example=f'用 {alt} 代替 `recv.{attr}()`', reason='除全局 ``__cmp__``/``__mod__``/``__truediv__``/``__floordiv__``、``.__await__()``、copyable/__copy__/__move__、``__init__`` 内 ``super.__init__``/``self.__init__`` 转发、脱糖协议 dunder 豁免外禁止直接调 dunder')
_EMPTY_FACTORY_LITERAL: dict[str, str] = {'list': '[]', 'dict': '{}', 'deque': '[]', 'tuple': '()', 'frozendict': '{}', 'frozenlist': '[]'}

def _s04_empty_factory_message(factory: str) -> str:
    lit = _EMPTY_FACTORY_LITERAL.get(factory, '[] / {} 等字面量')
    return _strict_msg(f'`{factory}()`', lit, '空容器初始化处', example=f'`xs: list[int] = {lit}` 勿 `xs = {factory}()`', reason='字面量零开销且符合编码规范')

def _s06_no_empty_new_message(ann_root: str) -> str:
    lit = _EMPTY_FACTORY_LITERAL.get(ann_root, '[]')
    example = f'`q: {ann_root}[T] = {lit}` 勿 `q: {ann_root}[T] = new()`'
    if ann_root == 'deque':
        example += '；有界队列用 `new(maxLen)`'
    return _strict_msg('无参 `new()`', lit, f'注解为 `{ann_root}[T]` 的初始化/返回值等', example=example, reason=f'空 `{ann_root}` 须字面量，禁止无参 `new()`')

def _expr_name_for_len(arg: ast.expr) -> str:
    if isinstance(arg, ast.Name):
        return arg.id
    return ast.unparse(arg)

def _s08_len_zero_suggestion(node: ast.Compare) -> str:
    seq = _expr_name_for_len(node.left.args[0])
    op = node.ops[0]
    if isinstance(op, ast.Eq):
        wrong, right = (f'len({seq}) == 0', f'not {seq}')
        ex = f'`if not {seq}:` 勿 `if len({seq}) == 0:`'
    elif isinstance(op, ast.NotEq):
        wrong, right = (f'len({seq}) != 0', f'if {seq}')
        ex = f'`if {seq}:` 勿 `if len({seq}) != 0:`'
    elif isinstance(op, ast.Gt):
        wrong, right = (f'len({seq}) > 0', f'if {seq}')
        ex = f'`if {seq}:` 勿 `if len({seq}) > 0:`'
    elif isinstance(op, ast.GtE):
        wrong, right = (f'len({seq}) >= 1', f'if {seq}')
        ex = f'`if {seq}:` 勿 `if len({seq}) >= 1:`'
    else:
        wrong, right = (f'len({seq}) … 0', f'not {seq} / if {seq}')
        ex = f'`not {seq}` / `if {seq}` 勿基于 `len({seq})` 与 0 比较'
    return _strict_msg(wrong, right, '判断容器/序列是否为空时', example=ex, reason='布尔真值语义更贴近 Python 且利于译码')

def _s09_zero_slice_message(node: ast.Subscript) -> str:
    recv = ast.unparse(node.value)
    return _strict_msg(f'`{recv}[0:…]`', f'`{recv}[:…]`', '切片下标处', example=f'`{recv}[:k]` 勿 `{recv}[0:k]`（起始为 0 时省略下界）', reason='与编码规范 §栈子区间一致')

def _s10_len_minus_k_subscript_suggestion(name: str, k: int) -> str:
    return _strict_msg(f'`{name}[len({name}) - {k}]`', f'`{name}[-{k}]`', '负索引访问尾部元素时', example=f'`{name}[-{k}]` 勿 `{name}[len({name}) - {k}]`', reason='负下标更短且与 CPython 惯用法一致')

def _s12_parse_index_compare(test: ast.expr) -> tuple[str, ast.cmpop, ast.expr] | None:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    if not isinstance(test.left, ast.Name):
        return None
    op = test.ops[0]
    if not isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
        return None
    return (test.left.id, op, test.comparators[0])

def _s12_name_in_test(test: ast.expr, name: str) -> bool:
    for node in ast.walk(test):
        if isinstance(node, ast.Name) and node.id == name:
            return True
    return False

def _s12_body_updates_test_bound_names(stmts: list[ast.stmt], index: str, test: ast.expr) -> bool:
    """条件里出现的其它变量若在体内被赋值/增强赋值（如 ``lo``/``hi``），则视为双指针循环。"""
    for stmt in stmts:
        if isinstance(stmt, ast.AugAssign):
            if isinstance(stmt.target, ast.Name):
                other = stmt.target.id
                if other != index and _s12_name_in_test(test, other):
                    return True
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    other = t.id
                    if other != index and _s12_name_in_test(test, other):
                        return True
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name):
                other = stmt.target.id
                if other != index and _s12_name_in_test(test, other):
                    return True
        elif isinstance(stmt, ast.If):
            if _s12_body_updates_test_bound_names(stmt.body, index, test):
                return True
            if _s12_body_updates_test_bound_names(stmt.orelse, index, test):
                return True
        elif isinstance(stmt, ast.With):
            if _s12_body_updates_test_bound_names(stmt.body, index, test):
                return True
            if _s12_body_updates_test_bound_names(stmt.orelse, index, test):
                return True
        elif isinstance(stmt, (ast.Try, ast.TryStar)):
            if _s12_body_updates_test_bound_names(stmt.body, index, test):
                return True
            for handler in stmt.handlers:
                if _s12_body_updates_test_bound_names(handler.body, index, test):
                    return True
            if _s12_body_updates_test_bound_names(stmt.orelse, index, test):
                return True
            if _s12_body_updates_test_bound_names(stmt.finalbody, index, test):
                return True
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                if _s12_body_updates_test_bound_names(case.body, index, test):
                    return True
        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
    return False

def _s12_aug_is_self_referential_step(aug: ast.AugAssign) -> bool:
    val = aug.value
    return isinstance(val, ast.Name) and isinstance(aug.target, ast.Name) and (val.id == aug.target.id)

def _s12_aug_step_depends_on_index(aug: ast.AugAssign, index: str) -> bool:
    """步长表达式仍依赖索引（如树状数组 ``idx += idx & -idx``）时不能用固定 ``range`` 替代。"""
    for node in ast.walk(aug.value):
        if isinstance(node, ast.Name) and node.id == index:
            return True
    return False

def _s12_collect_index_stores(stmts: list[ast.stmt], index: str) -> list[ast.stmt]:
    """收集 ``while`` 体内（含 ``if``/嵌套 ``for``/``while``）对索引变量的赋值/增强赋值。"""
    out: list[ast.stmt] = []
    for stmt in stmts:
        if isinstance(stmt, ast.AugAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == index:
                out.append(stmt)
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == index:
                    out.append(stmt)
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == index:
                out.append(stmt)
        elif isinstance(stmt, ast.If):
            out.extend(_s12_collect_index_stores(stmt.body, index))
            out.extend(_s12_collect_index_stores(stmt.orelse, index))
        elif isinstance(stmt, ast.With):
            out.extend(_s12_collect_index_stores(stmt.body, index))
            out.extend(_s12_collect_index_stores(stmt.orelse, index))
        elif isinstance(stmt, (ast.Try, ast.TryStar)):
            out.extend(_s12_collect_index_stores(stmt.body, index))
            for handler in stmt.handlers:
                out.extend(_s12_collect_index_stores(handler.body, index))
            out.extend(_s12_collect_index_stores(stmt.orelse, index))
            out.extend(_s12_collect_index_stores(stmt.finalbody, index))
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                out.extend(_s12_collect_index_stores(case.body, index))
        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            out.extend(_s12_collect_index_stores(stmt.body, index))
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
    return out

def _s12_step_is_negative(aug: ast.AugAssign) -> bool:
    val = aug.value
    if isinstance(val, ast.Constant) and isinstance(val.value, int):
        return val.value < 0
    if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub) and isinstance(val.operand, ast.Constant) and isinstance(val.operand.value, int):
        return val.operand.value > 0
    return False

def _s12_aug_matches_compare(op: ast.cmpop, aug: ast.AugAssign) -> bool:
    aop = aug.op
    if isinstance(op, (ast.Lt, ast.LtE)):
        return isinstance(aop, ast.Add)
    if isinstance(op, (ast.Gt, ast.GtE)):
        if isinstance(aop, ast.Sub):
            return True
        if isinstance(aop, ast.Add):
            return _s12_step_is_negative(aug)
    return False

def _s12_while_range_message(index: str, bound: ast.expr, op: ast.cmpop, aug: ast.AugAssign) -> str:
    bound_t = ast.unparse(bound)
    step_t = ast.unparse(aug.value)
    if isinstance(op, ast.Lt):
        stop_t = bound_t
        wrong = f'`while {index} < {bound_t}: {index} += {step_t}`'
    elif isinstance(op, ast.LtE):
        stop_t = f'{bound_t} + 1'
        wrong = f'`while {index} <= {bound_t}: {index} += {step_t}`'
    elif isinstance(op, ast.Gt):
        stop_t = bound_t
        if isinstance(aug.op, ast.Sub):
            step_t = f'-{step_t}' if not step_t.startswith('-') else step_t
            wrong = f'`while {index} > {bound_t}: {index} -= {ast.unparse(aug.value)}`'
        else:
            wrong = f'`while {index} > {bound_t}: {index} += {step_t}`'
    else:
        stop_t = f'{bound_t} + 1'
        if isinstance(aug.op, ast.Sub):
            step_t = f'-{step_t}' if not step_t.startswith('-') else step_t
            wrong = f'`while {index} >= {bound_t}: {index} -= {ast.unparse(aug.value)}`'
        else:
            wrong = f'`while {index} >= {bound_t}: {index} += {step_t}`'
    example = f'`for {index} in range(start, {stop_t}, {step_t}):`'
    return _strict_msg(wrong, f'`for {index} in range(…)`', '索引型计数循环处', example=example, reason='``for i in range`` 可译为原生 C++ 索引 for，升序/降序与步长更清晰')

def _s12_len_bound_target_name(bound: ast.expr) -> str | None:
    if isinstance(bound, ast.Call) and isinstance(bound.func, ast.Name) and (bound.func.id == 'len') and (len(bound.args) == 1) and isinstance(bound.args[0], ast.Name):
        return bound.args[0].id
    return None

def _s12_body_appends_to_name(stmts: list[ast.stmt], name: str) -> bool:
    """``while head < len(q)`` 且体内 ``q.append`` 时队列长度在变，勿强改 ``range``。"""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (node.func.attr == 'append') and isinstance(node.func.value, ast.Name) and (node.func.value.id == name):
                return True
        if isinstance(stmt, ast.If):
            if _s12_body_appends_to_name(stmt.body, name) or _s12_body_appends_to_name(stmt.orelse, name):
                return True
        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            continue
    return False

def _s12_try_index_while_range(node: ast.While) -> str | None:
    if isinstance(node.test, ast.BoolOp):
        return None
    parsed = _s12_parse_index_compare(node.test)
    if parsed is None:
        return None
    index, op, bound = parsed
    len_name = _s12_len_bound_target_name(bound)
    if len_name is not None and _s12_body_appends_to_name(node.body, len_name):
        return None
    if _s12_body_updates_test_bound_names(node.body, index, node.test):
        return None
    stores = _s12_collect_index_stores(node.body, index)
    if len(stores) != 1 or not isinstance(stores[0], ast.AugAssign):
        return None
    aug = stores[0]
    if not isinstance(aug.target, ast.Name) or aug.target.id != index:
        return None
    if _s12_aug_is_self_referential_step(aug):
        return None
    if _s12_aug_step_depends_on_index(aug, index):
        return None
    if not _s12_aug_matches_compare(op, aug):
        return None
    return _s12_while_range_message(index, bound, op, aug)

def _tuple_subscript_type_shorthand(node: ast.Subscript) -> str | None:
    """``tuple[T, U]`` → ``(T, U)`` / ``tuple[*Ts]`` → ``(*Ts,)`` 建议文本。"""
    if not isinstance(node.value, ast.Name) or node.value.id != 'tuple':
        return None
    sl = node.slice
    if isinstance(sl, ast.Tuple):
        if not sl.elts:
            return '()'
        if len(sl.elts) == 1 and isinstance(sl.elts[0], ast.Starred):
            inner = sl.elts[0].value
            if isinstance(inner, ast.Name):
                return f'(*{inner.id},)'
        return f"({', '.join((ast.unparse(e) for e in sl.elts))})"
    return f'({ast.unparse(sl)},)'

def _ann_is_outermost_tuple_subscript(ann: ast.expr | None) -> ast.Subscript | None:
    if ann is None:
        return None
    core = strip_type_annotation_markers(ann)
    if isinstance(core, ast.Subscript) and isinstance(core.value, ast.Name) and (core.value.id == 'tuple'):
        return core
    return None

def _ann_slice_elem(ann: ast.expr | None) -> str | None:
    if ann is None:
        return None
    core = strip_type_annotation_markers(ann)
    if not isinstance(core, ast.Subscript):
        return None
    if isinstance(core.value, ast.Name):
        return core.value.id
    return None

def _is_desugar_generated_name(name: str | None) -> bool:
    if not name:
        return False
    return any((name.endswith(sfx) for sfx in _DESUGAR_CLASS_SUFFIXES))
_AUG_OP_SYMBOL: dict[type, str] = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.MatMult: '@', ast.Div: '/', ast.FloorDiv: '//', ast.Mod: '%', ast.Pow: '**', ast.LShift: '<<', ast.RShift: '>>', ast.BitOr: '|', ast.BitXor: '^', ast.BitAnd: '&'}

def _aug_op_text(op: ast.operator) -> str:
    sym = _AUG_OP_SYMBOL.get(type(op), '?')
    return f'{sym}='

def _binop_to_aug_op(op: type) -> str:
    sym = _AUG_OP_SYMBOL.get(op, '+')
    return f'{sym}='

def _s11_binop_assign_message(node: ast.Assign) -> str:
    target = ast.unparse(node.targets[0]) if node.targets else 'x'
    op_ty = type(node.value.op) if isinstance(node.value, ast.BinOp) else ast.Add
    sym = _AUG_OP_SYMBOL.get(op_ty, '+')
    aug = _binop_to_aug_op(op_ty)
    return _strict_msg(f'`{target} = {target} {sym} …`', f'`{target} {aug} …`', '对同一变量原地更新时', example=f'`{target} {aug} step` 勿 `{target} = {target} {sym} step`', reason='增强赋值与 Py2Cpp 惯用法一致')

def _s06_scene_label(*, aug_op: str | None=None, in_aug_assign: bool=False, in_binop: bool=False, in_call_arg: bool=False, in_new_preferred: bool=False) -> str:
    if in_aug_assign:
        if aug_op:
            return f'增强赋值（`{aug_op}`）右侧'
        return '增强赋值（`+=` 等）右侧'
    if in_binop:
        return '二元表达式（如 `return a + b` 的操作数）'
    if in_call_arg:
        return '调用实参位置'
    if in_new_preferred:
        return '带类型注解的赋值、`return` 或字段默认值处'
    return '该位置'

def _s06_reason_no_new_in_expr() -> str:
    return '仅赋值/return/默认参数等处的单个 new()/new(...)/new.静态方法/静态属性可用 new，其它均不规范'

def _strict_msg(wrong: str, right: str, scene: str, *, example: str | None=None, reason: str | None=None) -> str:
    """统一 strict 文案：场景 + 勿/请 + 原因 + 例如。"""
    msg = f'{scene}请用 `{right}`，勿用 `{wrong}`'
    if reason:
        msg += f'（{reason}）'
    if example:
        msg += f'；例如 {example}'
    return msg
_s06_msg_prefer = _strict_msg

def _s06_priority_message(hint: str, *, scene: str | None=None, example: str | None=None) -> str:
    where = scene or '同场景（字面量 > new > Self）'
    msg = f'{where}请用 `{hint}`'
    if example:
        msg += f'；例如 {example}'
    else:
        msg += '（优先于 `new()` / `Self()`）'
    return msg

def _s06_preferred_init_hint(ann: ast.expr | None) -> str | None:
    root = _ann_root_name(ann)
    if root == 'str':
        return '""'
    if root == 'bytes':
        return 'b""'
    elem = _ann_slice_elem(ann)
    if elem == 'char':
        return '""'
    if elem == 'byte':
        return 'b""'
    if root in ('list', 'deque', 'frozenlist'):
        return '[]'
    if root in ('dict', 'frozendict'):
        return '{}'
    if root in ('set', 'frozenset'):
        return 'new()'
    return None

def _empty_literal_hint(ann: ast.expr | None) -> str | None:
    """兼容旧名；空 set/frozenset 无字面量捷径，返回 None。"""
    hint = _s06_preferred_init_hint(ann)
    if hint == 'new()':
        return None
    return hint

def _class_info_for_ctor(tr: Translator, func: ast.expr) -> ClassInfo | None:
    name = _call_target_name(func)
    if name is None or name in _BUILTIN_CTORS:
        return None
    info = tr.classes.get(name)
    if info is None:
        return None
    if _is_testcase_host(info):
        return None
    if _is_desugar_generated_name(info.name):
        return None
    return info

def _delegate_info_for_ctor(tr: Translator, func: ast.expr):
    name = _call_target_name(func)
    if name is None:
        return None
    return tr.delegates.get(name)

def _delegate_ctor_display(func: ast.expr) -> str:
    return f'{ast.unparse(func)}()'

def _expr_same(a: ast.expr, b: ast.expr) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, ast.Name):
        return a.id == b.id
    if isinstance(a, ast.Attribute):
        return a.attr == b.attr and _expr_same(a.value, b.value)
    if isinstance(a, ast.Subscript):
        return _expr_same(a.value, b.value) and _expr_same(a.slice, b.slice)
    if isinstance(a, ast.Constant):
        return a.value == b.value
    return False

def _static_method_on_class(tr: Translator, type_expr: ast.expr, method: str) -> ClassInfo | None:
    name = _ann_root_name(type_expr)
    if name is None:
        return None
    info = tr.classes.get(name)
    if info is None:
        return None
    sig = info.method_sigs.get(method)
    if sig is None or not sig.is_static:
        return None
    return info

def _ann_union_info(tr: Translator, ann: ast.expr | None) -> ClassInfo | None:
    name = _ann_root_name(ann)
    if name is None:
        return None
    info = tr.classes.get(name)
    if info is not None and info.is_union:
        return info
    return None

def _s06_exempt_new_receiver_class(info: ClassInfo) -> bool:
    return info.name in _SELF_LITERAL_HOST_CLASSES

def _param_ann_from_func(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.expr | None:
    for arg in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs):
        if arg.arg == name:
            return arg.annotation
    return None

def _match_subject_union_info(checker, node: ast.Match) -> ClassInfo | None:
    from .union_expand import union_info_from_subject_cpp
    subj = node.subject
    if isinstance(subj, ast.Name):
        if subj.id == 'self':
            ci = checker._current_class_info()
            if ci is not None and ci.is_union:
                return ci
        if checker._current_func is not None:
            ann = _param_ann_from_func(checker._current_func, subj.id)
            if ann is not None:
                root = _ann_root_name(ann)
                if root is not None:
                    info = checker.tr.classes.get(root)
                    if info is not None and info.is_union:
                        return info
    subject_cpp = _s22_resolve_expr_cpp_type(checker, node.subject)
    if subject_cpp:
        info = union_info_from_subject_cpp(checker.tr, subject_cpp)
        if info is not None:
            return info
    return None

def _s20_is_ord_single_char(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and (expr.func.id == 'ord') and (len(expr.args) == 1) and (not expr.keywords) and isinstance(expr.args[0], ast.Constant) and isinstance(expr.args[0].value, str) and (len(expr.args[0].value) == 1)

def _s20_is_enum_member(expr: ast.expr) -> bool:
    if not isinstance(expr, ast.Attribute):
        return False
    root = expr.value
    while isinstance(root, ast.Attribute):
        root = root.value
    return isinstance(root, ast.Name) and root.id not in ('self', 'cls')

def _s20_eq_rhs_ok(rhs: ast.expr) -> bool:
    if isinstance(rhs, ast.Constant):
        return True
    if _s20_is_ord_single_char(rhs):
        return True
    return _s20_is_enum_member(rhs)

def _s20_in_container_ok(rhs: ast.expr) -> bool:
    if isinstance(rhs, ast.Constant) and isinstance(rhs.value, (str, bytes)):
        return True
    if isinstance(rhs, (ast.Set, ast.List, ast.Tuple)):
        return all((isinstance(elt, ast.Constant) or _s20_is_enum_member(elt) or _s20_is_ord_single_char(elt) for elt in rhs.elts))
    return False

def _s20_compare_rhs_ok(op: ast.cmpop, rhs: ast.expr) -> bool:
    if isinstance(op, ast.Eq):
        return _s20_eq_rhs_ok(rhs)
    if isinstance(op, ast.In):
        return _s20_in_container_ok(rhs)
    return False

def _s20_subject_from_test(test: ast.expr) -> ast.expr | None:
    """从 ``if``/``elif`` 条件提取 ``==``/``in`` 左侧 subject（``and`` 后缀允许）。

  仅当比较右端为字面量、枚举成员或 ``ord('x')``（``==``）/ 字面量容器（``in``）时计入。
  """
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        for value in test.values:
            subj = _s20_subject_from_test(value)
            if subj is not None:
                return subj
        return None
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and (len(test.comparators) == 1):
        op = test.ops[0]
        if isinstance(op, (ast.Eq, ast.In)) and _s20_compare_rhs_ok(op, test.comparators[0]):
            return test.left
    return None

def _s20_subjects_compatible(subjects: list[ast.expr]) -> bool:
    keys: list[str] = []
    for subj in subjects:
        try:
            keys.append(ast.unparse(subj))
        except Exception:
            return False
    return len(keys) >= _S20_MIN_DISPATCH_BRANCHES and len(set(keys)) == 1

def _s20_collect_elif_tests(node: ast.If) -> list[ast.expr]:
    tests = [node.test]
    cur = node.orelse
    while len(cur) == 1 and isinstance(cur[0], ast.If):
        inner = cur[0]
        tests.append(inner.test)
        cur = inner.orelse
    return tests

def _s20_dispatch_ladder_msg(subject: str, branch_count: int) -> str:
    return _strict_msg('多处 `if`/`elif` 上重复 `==`/`in` 判别', '`match`/`case`', f'同一表达式 `{subject}` 在 {branch_count} 个分支', reason='多路相等/成员判别宜合并为 `match`', example=f'match {subject}:\n  case ...:\n    ...')

def _s20_report_compare_ladder(checker: _StrictStyleChecker, anchor: ast.AST, tests: list[ast.expr]) -> None:
    if len(tests) < _S20_MIN_DISPATCH_BRANCHES:
        return
    subjects: list[ast.expr] = []
    for test in tests:
        subj = _s20_subject_from_test(test)
        if subj is None:
            return
        subjects.append(subj)
    if not _s20_subjects_compatible(subjects):
        return
    subject = ast.unparse(subjects[0])
    checker._add(S20, anchor, _s20_dispatch_ladder_msg(subject, len(tests)))

def _s20_scan_if_orelse(checker: _StrictStyleChecker, orelse: list[ast.stmt]) -> None:
    if not orelse:
        return
    if len(orelse) == 1 and isinstance(orelse[0], ast.If):
        cur = orelse[0]
        while True:
            _s20_scan_stmt_list(checker, cur.body)
            if not cur.orelse:
                return
            if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
                cur = cur.orelse[0]
                continue
            _s20_scan_stmt_list(checker, cur.orelse)
            return
    _s20_scan_stmt_list(checker, orelse)

def _s20_scan_stmt_list(checker: _StrictStyleChecker, stmts: list[ast.stmt]) -> None:
    i = 0
    while i < len(stmts):
        if isinstance(stmts[i], ast.If):
            group: list[ast.If] = []
            j = i
            while j < len(stmts) and isinstance(stmts[j], ast.If):
                group.append(stmts[j])
                j += 1
            if len(group) >= _S20_MIN_DISPATCH_BRANCHES:
                _s20_report_compare_ladder(checker, group[0], [node.test for node in group])
            i = j
        else:
            i += 1
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            _s20_report_compare_ladder(checker, stmt, _s20_collect_elif_tests(stmt))
            _s20_scan_stmt_list(checker, stmt.body)
            _s20_scan_if_orelse(checker, stmt.orelse)
        elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            _s20_scan_stmt_list(checker, stmt.body)
            _s20_scan_stmt_list(checker, stmt.orelse)
        elif isinstance(stmt, ast.With):
            _s20_scan_stmt_list(checker, stmt.body)
        elif isinstance(stmt, (ast.Try, ast.TryStar)):
            _s20_scan_stmt_list(checker, stmt.body)
            for handler in stmt.handlers:
                _s20_scan_stmt_list(checker, handler.body)
            _s20_scan_stmt_list(checker, stmt.orelse)
            _s20_scan_stmt_list(checker, stmt.finalbody)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                _s20_scan_stmt_list(checker, case.body)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

def _s38_for_target_name(target: ast.expr) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    return None

def _s38_is_trivial_yield_delegation(node: ast.For) -> bool:
    """``for x in it: yield x``（无 ``else``、体仅一条 ``yield x``）。"""
    if node.orelse:
        return False
    if len(node.body) != 1:
        return False
    stmt = node.body[0]
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Yield):
        return False
    yval = stmt.value.value
    if yval is None:
        return False
    tname = _s38_for_target_name(node.target)
    if tname is None:
        return False
    return isinstance(yval, ast.Name) and yval.id == tname

def _s38_yield_from_suggest(node: ast.For) -> str:
    try:
        return f'yield from {ast.unparse(node.iter)}'
    except Exception:
        return 'yield from <iterable>'

def _s38_for_yield_msg(node: ast.For) -> str:
    wrong = f'for {ast.unparse(node.target)} in …: yield …'
    return _strict_msg(wrong, _s38_yield_from_suggest(node), '生成器', reason='循环体仅 ``yield`` 循环变量时与 ``yield from`` 等价，状态机更简单', example=f'got: {wrong}')

def _s38_record_for_violation(violations: list[_Violation], module_path: str, node: ast.For, *, in_async: bool) -> None:
    if in_async:
        return
    if not _s38_is_trivial_yield_delegation(node):
        return
    violations.append(_Violation(S38, _s38_for_yield_msg(node), node, module_path))

def check_yield_from_for_style(tr: TranslatorState) -> None:
    """S38：须在 ``expand_generators`` **之前**调用（同步 ``def`` 尚未脱糖为 ``*_generator``）。"""
    if not getattr(tr, 'strict', True):
        return
    violations: list[_Violation] = []
    for module_path, tree in tr.module_asts.items():
        if not _should_check_module(tr, module_path):
            continue

        class _S38PreExpandWalker(ast.NodeVisitor):

            def __init__(self) -> None:
                self.in_async = False

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                prev = self.in_async
                self.in_async = True
                self.generic_visit(node)
                self.in_async = prev

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.generic_visit(node)

            def visit_For(self, node: ast.For) -> None:
                _s38_record_for_violation(violations, module_path, node, in_async=self.in_async)
                self.generic_visit(node)
        _S38PreExpandWalker().visit(tree)
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处编码规范违规（可用 --no-strict 关闭）：']
    first_loc: SourceLocation | None = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)

def _s20_body_has_yield(body: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
    return False

def _s20_skip_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """``async def`` / 含 ``yield`` 的生成器：脱糖为状态机，``match`` 暂不与 S20 同用。"""
    if isinstance(node, ast.AsyncFunctionDef):
        return True
    return _s20_body_has_yield(node.body)

def _s20_scan_function_body(checker: _StrictStyleChecker, body: list[ast.stmt], *, func: ast.FunctionDef | ast.AsyncFunctionDef | None=None) -> None:
    if func is not None and _s20_skip_function(func):
        return
    _s20_scan_stmt_list(checker, body)

def _s21_single_compare_arm(expr: ast.expr, *, eq: bool) -> tuple[ast.expr, ast.expr] | None:
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and (len(expr.comparators) == 1):
        op = expr.ops[0]
        if eq and isinstance(op, ast.Eq):
            return (expr.left, expr.comparators[0])
        if not eq and isinstance(op, ast.NotEq):
            return (expr.left, expr.comparators[0])
    return None

def _s21_collect_compare_chain_arms(expr: ast.expr, bool_op: type[ast.boolop], *, eq: bool) -> list[tuple[ast.expr, ast.expr]] | None:
    arm = _s21_single_compare_arm(expr, eq=eq)
    if arm is not None:
        return [arm]
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, bool_op):
        out: list[tuple[ast.expr, ast.expr]] = []
        for value in expr.values:
            part = _s21_collect_compare_chain_arms(value, bool_op, eq=eq)
            if part is None:
                return None
            out.extend(part)
        return out
    return None

def _s21_parse_compare_chain(expr: ast.expr, bool_op: type[ast.boolop], *, eq: bool) -> tuple[ast.expr, list[ast.expr]] | None:
    arms = _s21_collect_compare_chain_arms(expr, bool_op, eq=eq)
    if arms is None or len(arms) < _S21_MIN_COMPARE_CHAIN_ARMS:
        return None
    subject = arms[0][0]
    try:
        subject_key = ast.unparse(subject)
    except Exception:
        return None
    rhss: list[ast.expr] = []
    for left, rhs in arms:
        try:
            if ast.unparse(left) != subject_key:
                return None
        except Exception:
            return None
        rhss.append(rhs)
    return (subject, rhss)

def _s21_rhs_char_code(rhs: ast.expr) -> str | None:
    if isinstance(rhs, ast.Constant) and isinstance(rhs.value, str) and (len(rhs.value) == 1):
        return rhs.value
    if _s20_is_ord_single_char(rhs):
        arg = rhs.args[0]
        assert isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        return arg.value
    return None

def _s21_suggest_membership(subject: str, rhss: list[ast.expr], *, negate: bool) -> str:
    codes = [_s21_rhs_char_code(rhs) for rhs in rhss]
    op = 'not in' if negate else 'in'
    if codes and all((ch is not None for ch in codes)):
        seen: list[str] = []
        for ch in codes:
            assert ch is not None
            if ch not in seen:
                seen.append(ch)
        return f'''{subject} {op} "{''.join(seen)}"'''
    rhs_text = ', '.join((ast.unparse(rhs) for rhs in rhss))
    return f'{subject} {op} {{{rhs_text}}}'

def _s21_compare_chain_msg(subject: str, rhss: list[ast.expr], *, eq_or: bool) -> str:
    suggest = _s21_suggest_membership(subject, rhss, negate=not eq_or)
    if eq_or:
        wrong = '`expr == x or expr == y or …`'
        reason = '宜合并为 `in` 成员检测'
        scene = f'同一表达式 `{subject}` 的连续 `==` 比较'
    else:
        wrong = '`expr != x and expr != y and …`'
        reason = '宜合并为 `not in` 成员检测'
        scene = f'同一表达式 `{subject}` 的连续 `!=` 比较'
    return _strict_msg(wrong, suggest, scene, reason=reason, example=suggest)

def _s22_ann_is_char(ann: ast.expr | None) -> bool:
    if ann is None:
        return False
    try:
        text = strip_type_annotation_markers(ast.unparse(ann)).strip()
    except Exception:
        return False
    return text == 'char' or is_char_type(text)

def _s22_sig_for_func_node(checker: _StrictStyleChecker, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionSig | MethodSig | None:
    sig = checker.tr.function_node_sigs.get(id(node))
    if sig is not None:
        return sig
    if not checker._class_stack:
        return None
    cls_name = checker._class_stack[-1]
    for info in checker.tr.classes.values():
        if info.name == cls_name and info.module_path == checker.module_path:
            return info.method_sigs.get(node.name)
    return None

def _s22_param_cpp_type(checker: _StrictStyleChecker, func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> str:
    sig = checker._current_func_sig
    if sig is not None:
        from ..analysis.type_emit import method_param_storage_cpp
        pt = method_param_storage_cpp(sig, name, fallback='')
        if pt:
            return pt
    for arg in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs):
        if arg.arg == name and _s22_ann_is_char(arg.annotation):
            return cpp_ident('char')
    return ''

def _s22_resolve_expr_cpp_type(checker: _StrictStyleChecker, expr: ast.expr) -> str:
    match expr:
        case ast.Name(id=name):
            if checker._current_func is not None:
                pt = _s22_param_cpp_type(checker, checker._current_func, name)
                if pt:
                    return pt
        case ast.Subscript(value=value, slice=sl) if not isinstance(sl, ast.Slice):
            vt = _s22_resolve_expr_cpp_type(checker, value)
            if is_str_type(vt):
                return cpp_ident('char')
    return checker.tr._infer_expr_cpp_type(expr)

def _s22_expr_is_char_typed(checker: _StrictStyleChecker, expr: ast.expr) -> bool:
    ty = _s22_resolve_expr_cpp_type(checker, expr)
    return bool(ty and is_char_type(ty))

def _s22_char_literal_compare_msg(ch: str) -> str:
    if ch == "'":
        wrong = 'ch == "\'"'
        right = 'ch == ord("\'")'
    else:
        wrong = f"ch == '{ch}'"
        right = f"ch == ord('{ch}')"
    return _strict_msg(wrong, right, '``char`` 与单字符字面量比较', reason='译后为 ``PyChar`` 对 ``PyStr``，易触发 MSVC C4805；``case`` 模式/分支体除外，``case … if …`` guard 须遵守', example=right)

def _s34_ord_non_literal_msg(bad: str) -> str:
    return _strict_msg(bad, "ord('x')", '``ord`` 调用', reason='``ord`` 仅接受单字符 ``str`` 字面量；``char``→整型用 ``int(c)``，``str[i]``→``char`` 用 ``char(s[i])``', example="c == ord('a') 或 int(c)")

def _s35_ctor_call_name(expr: ast.expr | None) -> str | None:
    if expr is None or not isinstance(expr, ast.Call):
        return None
    if expr.keywords or len(expr.args) != 1:
        return None
    if isinstance(expr.func, ast.Name):
        return expr.func.id
    return None

def _s35_ann_text(ann: ast.expr | None) -> str:
    if ann is None:
        return ''
    try:
        return strip_type_annotation_markers(ast.unparse(ann)).strip()
    except Exception:
        return ''

def _s35_ann_matches_ctor(ann: ast.expr | None, ctor: str) -> bool:
    text = _s35_ann_text(ann)
    if not text:
        return False
    if text == ctor:
        return True
    cpp_map = {'int': cpp_ident('int'), 'float': cpp_ident('float'), 'bool': cpp_ident('bool'), 'char': cpp_ident('char'), 'byte': cpp_ident('byte'), 'str': cpp_ident('str'), 'int64': cpp_ident('int64'), 'float64': cpp_ident('float64'), 'uint': cpp_ident('uint'), 'uint64': cpp_ident('uint64'), 'uintptr': cpp_ident('uintptr')}
    return text == cpp_map.get(ctor, ctor)

def _s35_primitive_convert_temp_msg(name: str, ctor: str, expr: str) -> str:
    return _strict_msg(f'`{name}: {ctor} = {ctor}({expr}); return {name}`', f'`return {ctor}({expr})` 或在用到处直接写 `{ctor}({expr})`', '标量显式转换临时变量', reason='临时变量仅用于类型转换时勿用注解变量承载（初始化后无其它赋值）', example=f'return {ctor}({expr})')

def _s35_name_in_assign_target(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any((_s35_name_in_assign_target(elt, name) for elt in target.elts))
    return False

def _s35_assign_hits_in_stmt(stmt: ast.stmt, name: str) -> list[ast.AST]:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    hits: list[ast.AST] = []
    if isinstance(stmt, ast.AnnAssign):
        if _s35_name_in_assign_target(stmt.target, name):
            hits.append(stmt)
    elif isinstance(stmt, ast.Assign):
        if any((_s35_name_in_assign_target(t, name) for t in stmt.targets)):
            hits.append(stmt)
    elif isinstance(stmt, ast.AugAssign):
        if _s35_name_in_assign_target(stmt.target, name):
            hits.append(stmt)
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        if _s35_name_in_assign_target(stmt.target, name):
            hits.append(stmt)
        for block in (stmt.body, stmt.orelse):
            for inner in block:
                hits.extend(_s35_assign_hits_in_stmt(inner, name))
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        for item in stmt.items:
            if item.optional_vars and _s35_name_in_assign_target(item.optional_vars, name):
                hits.append(stmt)
        for inner in stmt.body:
            hits.extend(_s35_assign_hits_in_stmt(inner, name))
    elif isinstance(stmt, ast.If):
        for block in (stmt.body, stmt.orelse):
            for inner in block:
                hits.extend(_s35_assign_hits_in_stmt(inner, name))
    elif isinstance(stmt, (ast.While,)):
        for inner in stmt.body + stmt.orelse:
            hits.extend(_s35_assign_hits_in_stmt(inner, name))
    elif isinstance(stmt, ast.Try):
        for inner in stmt.body + stmt.orelse + stmt.finalbody:
            hits.extend(_s35_assign_hits_in_stmt(inner, name))
        for handler in stmt.handlers:
            if handler.name == name:
                hits.append(handler)
            for inner in handler.body:
                hits.extend(_s35_assign_hits_in_stmt(inner, name))
    elif isinstance(stmt, ast.Match):
        for case in stmt.cases:
            for inner in case.body:
                hits.extend(_s35_assign_hits_in_stmt(inner, name))
    else:
        for child in ast.iter_child_nodes(stmt):
            if isinstance(child, ast.stmt):
                hits.extend(_s35_assign_hits_in_stmt(child, name))
    return hits

def _s35_assign_hits_in_function(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> list[ast.AST]:
    hits: list[ast.AST] = []
    for stmt in func.body:
        hits.extend(_s35_assign_hits_in_stmt(stmt, name))
    return hits

def _s35_check_primitive_convert_temp(checker: _StrictStyleChecker, node: ast.AnnAssign) -> None:
    if checker._s06_in_desugar_host():
        return
    if node.value is None:
        return
    ctor = _s35_ctor_call_name(node.value)
    if ctor is None or ctor not in _PRIMITIVE_CONVERT_CTORS:
        return
    if not _s35_ann_matches_ctor(node.annotation, ctor):
        return
    if not isinstance(node.target, ast.Name):
        return
    func = checker._current_func
    if func is not None:
        hits = _s35_assign_hits_in_function(func, node.target.id)
        if len(hits) != 1 or hits[0] is not node:
            return
    arg = node.value.args[0]
    try:
        arg_text = ast.unparse(arg)
    except Exception:
        arg_text = 'x'
    checker._add(S35, node, _s35_primitive_convert_temp_msg(node.target.id, ctor, arg_text))

def _s46_ast_parents(root: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents

def _s46_is_pure_forward_use(name_node: ast.Name, parents: dict[ast.AST, ast.AST]) -> bool:
    """``name`` 仅作为整表达式转发：``x = name`` / ``return name`` / ``fn(name)`` / ``fn(k=name)``。

    作为另一个 ``new(...)`` / ``new.meth(...)`` 的实参时不算（S06e 禁止嵌套 ``new``，须保留临时变量）。
    """
    parent = parents.get(name_node)
    if parent is None:
        return False
    if isinstance(parent, ast.Assign) and parent.value is name_node:
        return True
    if isinstance(parent, ast.AnnAssign) and parent.value is name_node:
        return True
    if isinstance(parent, ast.Return) and parent.value is name_node:
        return True
    call: ast.Call | None = None
    if isinstance(parent, ast.Call):
        if any(arg is name_node for arg in parent.args) or any(kw.value is name_node for kw in parent.keywords):
            call = parent
    elif isinstance(parent, ast.keyword) and parent.value is name_node:
        gp = parents.get(parent)
        if isinstance(gp, ast.Call):
            call = gp
    if call is None:
        return False
    # 嵌套进另一个 new 构造：临时变量是 S06e 所需，非「仅为类型上下文」
    if _is_new_ctor_expr(call):
        return False
    return True

def _s46_rewrite_new_to_cls(new_text: str, cls: str) -> str:
    """``new(...)`` / ``new.meth(...)`` → ``Cls(...)`` / ``Cls.meth(...)``（实参等无法用 ``new``）。"""
    if new_text.startswith('new.'):
        return f'{cls}.{new_text[4:]}'
    if new_text.startswith('new('):
        return f'{cls}{new_text[3:]}'
    return f'{cls}(...)'

def _s46_new_temp_msg(name: str, ann_text: str, new_text: str) -> str:
    cls = ann_text if ann_text else 'Cls'
    cls_form = _s46_rewrite_new_to_cls(new_text, cls)
    return _strict_msg(
        f'`{name}: {cls} = {new_text}; … = {name}` / `fn({name})`',
        f'`… = {new_text}`（有类型上下文）或 `fn({cls_form})`（调用实参等无法推断时）',
        '仅为 ``new`` 提供类型上下文的注解临时变量',
        reason='禁止为用 ``new`` 而创建临时变量再立刻转发（含赋值、``return``、调用实参）；优先对目标直接 ``new``，嵌入表达式用具体类名构造（``@union`` 变体为 ``Union.Variant(...)``）',
        example=f'`self.f = {new_text}` 或 `bus.dispatch({cls_form})`；勿 `{name}: {cls} = {new_text}; bus.dispatch({name})`',
    )

def _s46_find_stmt_list(stmts: list[ast.stmt], target: ast.stmt) -> tuple[list[ast.stmt], int] | None:
    for i, stmt in enumerate(stmts):
        if stmt is target:
            return (stmts, i)
        nested: list[list[ast.stmt]] = []
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested.append(stmt.body)
        elif isinstance(stmt, ast.If):
            nested.append(stmt.body)
            nested.append(stmt.orelse)
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            nested.append(stmt.body)
            nested.append(stmt.orelse)
        elif isinstance(stmt, ast.With) or (hasattr(ast, 'AsyncWith') and isinstance(stmt, ast.AsyncWith)):
            nested.append(stmt.body)
        elif isinstance(stmt, ast.Try):
            nested.append(stmt.body)
            nested.append(stmt.orelse)
            nested.append(stmt.finalbody)
            for h in stmt.handlers:
                nested.append(h.body)
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                nested.append(case.body)
        for child in nested:
            found = _s46_find_stmt_list(child, target)
            if found is not None:
                return found
    return None

def _s46_check_new_type_context_temp(checker: _StrictStyleChecker, node: ast.AnnAssign) -> None:
    """S46：勿 ``sp: T = new(...); self.f = sp``（中间无其它语句）。"""
    if checker._s06_in_desugar_host():
        return
    if node.value is None or not _is_new_ctor_expr(node.value):
        return
    if not isinstance(node.target, ast.Name):
        return
    # 类型形参 ``U = new()`` 再 ``fn(u)``：实参处无法写 ``new()`` 也无法写具体类名，须保留临时变量
    ann_root = _ann_root_name(node.annotation)
    if ann_root is not None and ann_root in checker._scope_type_params:
        return
    func = checker._current_func
    if func is None:
        return
    name = node.target.id
    hits = _s35_assign_hits_in_function(func, name)
    if len(hits) != 1 or hits[0] is not node:
        return
    parents = _s46_ast_parents(func)
    loads: list[ast.Name] = []
    for n in ast.walk(func):
        if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load):
            loads.append(n)
    if not loads:
        return
    # 多处使用（如可写缓冲先 fill 再 encode）不是「仅为类型上下文再立刻转发」
    if len(loads) > 1:
        return
    if not all(_s46_is_pure_forward_use(n, parents) for n in loads):
        return
    located = _s46_find_stmt_list(func.body, node)
    if located is None:
        return
    stmts, idx = located
    remaining = set(id(n) for n in loads)
    for stmt in stmts[idx + 1 :]:
        loads_in_stmt = [n for n in loads if id(n) in remaining and any(x is n for x in ast.walk(stmt))]
        if not loads_in_stmt:
            # 中间夹有其它语句（如 close 后再 return）——临时变量有序用途，不记 S46
            return
        if not all(_s46_is_pure_forward_use(n, parents) for n in loads_in_stmt):
            return
        for n in loads_in_stmt:
            remaining.discard(id(n))
        if not remaining:
            break
    if remaining:
        return
    try:
        new_text = ast.unparse(node.value)
    except Exception:
        new_text = 'new(...)'
    ann_text = _s35_ann_text(node.annotation) or 'Cls'
    checker._add(S46, node, _s46_new_temp_msg(name, ann_text, new_text))

def _s36_is_discard_of_name(stmt: ast.stmt, name: str) -> bool:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Name) or tgt.id != '_':
        return False
    return isinstance(stmt.value, ast.Name) and stmt.value.id == name

def _s36_name_meaningfully_used(stmts: list[ast.stmt], name: str) -> bool:
    for stmt in stmts:
        if _s36_is_discard_of_name(stmt, name):
            continue
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                return True
    return False

def _s36_stmts_after(node: ast.Assign, func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    hit = _s36_find_stmts_after(node, func.body)
    return hit if hit is not None else []

def _s36_nested_stmt_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    blocks: list[list[ast.stmt]] = []
    if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
        blocks.append(stmt.body)
        blocks.append(stmt.orelse)
    elif isinstance(stmt, ast.If):
        blocks.append(stmt.body)
        blocks.append(stmt.orelse)
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        blocks.append(stmt.body)
    elif isinstance(stmt, ast.Try):
        blocks.append(stmt.body)
        blocks.append(stmt.orelse)
        blocks.append(stmt.finalbody)
        for handler in stmt.handlers:
            blocks.append(handler.body)
    elif isinstance(stmt, ast.Match):
        for case in stmt.cases:
            blocks.append(case.body)
    return blocks

def _s36_find_stmts_after(node: ast.Assign, stmts: list[ast.stmt]) -> list[ast.stmt] | None:
    for i, stmt in enumerate(stmts):
        if stmt is node:
            return stmts[i + 1:]
        for block in _s36_nested_stmt_blocks(stmt):
            hit = _s36_find_stmts_after(node, block)
            if hit is not None:
                return hit
    return None

def _s36_tuple_unpack_msg(name: str) -> str:
    return f'元组解包绑定 ``{name}`` 在后续未使用；未用槽位写 ``_``，或中间段写 ``*_``（如 ``{name}, *_ = …`` / ``*_, {name} = …``）'

def _s36_check_tuple_unpack(checker: _StrictStyleChecker, node: ast.Assign) -> None:
    if checker._s06_in_desugar_host():
        return
    func = checker._current_func
    if func is None:
        return
    target = node.targets[0]
    assert isinstance(target, ast.Tuple)
    from ..emit.pytuple_unpack_emit import tuple_unpack_bound_names
    names = tuple_unpack_bound_names(target.elts)
    if not names:
        return
    rest = _s36_stmts_after(node, func)
    for name in names:
        if _s36_rhs_loads_name(node, name):
            continue
        if _s36_name_meaningfully_used(rest, name):
            continue
        checker._add(S36, node, _s36_tuple_unpack_msg(name))

def _s36_rhs_loads_name(node: ast.Assign, name: str) -> bool:
    for sub in ast.walk(node.value):
        if isinstance(sub, ast.Name) and sub.id == name and isinstance(sub.ctx, ast.Load):
            return True
    return False

def _s23_match_missing_default_msg() -> str:
    return _strict_msg('match 无末尾 `case _:`', 'match … case _:', '``match`` 语句', reason='须以通配 ``case _`` 收尾，或 ``@enum``/``@union`` 已由无 guard 的穷尽 ``case`` 覆盖', example='match x:\n  case 1:\n    ...\n  case _:\n    ...')

def _s23_wildcard_with_guard_msg() -> str:
    return _strict_msg('末尾 `case _` 带 guard', 'case _:', '``match`` 最后一个 ``case``', reason='通配收尾不得写 ``case _ if …``；guard 请写在其它 ``case`` 上', example='match x:\n  case 1:\n    ...\n  case _:\n    ...')

def _s23_union_case_ref(pattern: ast.pattern, *, subject_union: ClassInfo | None=None) -> tuple[str, str] | None:
    """``case U.Variant(...)`` / ``case new.Variant(...)`` → ``(union, variant)``。"""
    from .union_expand import parse_union_case_pattern
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    ref = parse_union_case_pattern(pat, subject_union=subject_union)
    if ref is None:
        return None
    return (ref.union_name, ref.variant_name)

def _s23_union_case_uses_explicit_union_syntax(pattern: ast.pattern) -> bool:
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    if isinstance(pat, ast.MatchClass):
        cls = pat.cls
        if isinstance(cls, ast.Attribute) and isinstance(cls.value, ast.Name):
            return cls.value.id != 'new'
    if isinstance(pat, ast.MatchValue):
        val = pat.value
        if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name):
            return val.value.id != 'new'
    return False

def _s23_union_branch_patterns(pattern: ast.pattern) -> list[ast.pattern]:
    if isinstance(pattern, ast.MatchOr):
        return list(pattern.patterns)
    return [pattern]

def _s23_union_field_fully_bound(sub: ast.pattern) -> bool:
    """字段槽位须为名称绑定（``MatchAs``），勿用字面量约束（``MatchValue``）。"""
    return isinstance(sub, ast.MatchAs)

def _s23_union_variant_fully_captured(info: ClassInfo, variant_name: str, pattern: ast.pattern, *, subject_union: ClassInfo | None=None) -> bool:
    """有字段变体：出现的槽位须为名称绑定；``U.A()`` / ``U.A(x)`` / ``U.A(x, y)`` 计入；``U.A(x, 1)`` 不算。"""
    variant = next((v for v in info.union_variants if v.name == variant_name), None)
    if variant is None:
        return False
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    ref = _s23_union_case_ref(pat, subject_union=subject_union)
    if ref is None or ref[1] != variant_name:
        return False
    if variant.is_unit:
        if isinstance(pat, ast.MatchValue):
            return True
        return isinstance(pat, ast.MatchClass) and (not pat.patterns) and (not pat.kwd_patterns)
    if not isinstance(pat, ast.MatchClass):
        return False
    if not pat.patterns and (not pat.kwd_patterns):
        return True
    for i, sub in enumerate(pat.patterns):
        if i >= len(variant.fields):
            return False
        if not _s23_union_field_fully_bound(sub):
            return False
    for attr, sub in zip(pat.kwd_attrs, pat.kwd_patterns):
        if attr not in variant.fields:
            return False
        if not _s23_union_field_fully_bound(sub):
            return False
    return True

def _s23_enum_members_from_pattern(pattern: ast.pattern) -> tuple[str, list[str]] | None:
    """``case E.A`` / ``case E.A | E.B`` → ``(enum 类名, [成员, …])``。"""
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    if isinstance(pat, ast.MatchValue):
        return _parse_enum_or_value(pat.value)
    if isinstance(pat, ast.MatchOr):
        cls_name: str | None = None
        members: list[str] = []
        for branch in pat.patterns:
            if not isinstance(branch, ast.MatchValue):
                return None
            hit = _parse_enum_or_value(branch.value)
            if hit is None:
                return None
            if cls_name is None:
                cls_name = hit[0]
            elif cls_name != hit[0]:
                return None
            members.extend(hit[1])
        if cls_name is None:
            return None
        return (cls_name, members)
    return None

def _s23_is_exhaustive_enum_match_for(checker: _StrictStyleChecker, node: ast.Match) -> bool:
    """每个 ``@enum`` 成员至少一条无 guard 的 member ``case``。"""
    covered: dict[str, set[str]] = {}
    for case in node.cases:
        if case.guard is not None or is_wildcard_pattern(case.pattern):
            continue
        hit = _s23_enum_members_from_pattern(case.pattern)
        if hit is None:
            return False
        cls_name, members = hit
        covered.setdefault(cls_name, set()).update(members)
    if len(covered) != 1:
        return False
    cls_name = next(iter(covered))
    info = checker.tr.classes.get(cls_name)
    if info is None or not info.is_enum:
        return False
    return covered[cls_name] == enum_member_names(info)

def _s23_is_exhaustive_optional_match_for(checker: _StrictStyleChecker, node: ast.Match) -> bool:
    from .optional_match import is_optional_match_exhaustive, is_optional_union_info
    from .union_expand import union_info_from_subject_cpp
    subject = node.subject
    if isinstance(subject, ast.Name) and subject.id == 'self':
        ci = checker._current_class_info()
        if ci is not None and is_optional_union_info(ci):
            return is_optional_match_exhaustive(node)
    subject_cpp = _s22_resolve_expr_cpp_type(checker, subject)
    if is_optional_type(subject_cpp):
        return is_optional_match_exhaustive(node)
    info = union_info_from_subject_cpp(checker.tr, subject_cpp)
    if info is not None and is_optional_union_info(info):
        return is_optional_match_exhaustive(node)
    return False

def _s23_is_exhaustive_union_match_for(checker: _StrictStyleChecker, node: ast.Match) -> bool:
    """每个 ``@union`` 变体至少一条无 guard、字段全捕获/省略的 ``case``。"""
    subject_union = _match_subject_union_info(checker, node)
    covered: dict[str, set[str]] = {}
    union_name: str | None = None
    union_info: ClassInfo | None = None
    for case in node.cases:
        if case.guard is not None or is_wildcard_pattern(case.pattern):
            continue
        for branch_pat in _s23_union_branch_patterns(case.pattern):
            ref = _s23_union_case_ref(branch_pat, subject_union=subject_union)
            if ref is None:
                return False
            u_name, variant_name = ref
            if union_name is None:
                union_name = u_name
                union_info = checker.tr.classes.get(u_name)
                if union_info is None or not union_info.is_union:
                    return False
            elif union_name != u_name:
                return False
            assert union_info is not None
            if not _s23_union_variant_fully_captured(union_info, variant_name, branch_pat, subject_union=subject_union):
                continue
            covered.setdefault(u_name, set()).add(variant_name)
    if union_info is None or union_name is None:
        return False
    required = {v.name for v in union_info.union_variants}
    return covered.get(union_name) == required

def _s23_check_match_default_case(checker: _StrictStyleChecker, node: ast.Match) -> None:
    if not node.cases:
        checker._add(S23, node, _s23_match_missing_default_msg())
        return
    last = node.cases[-1]
    if is_wildcard_pattern(last.pattern):
        if last.guard is not None:
            checker._add(S23, last, _s23_wildcard_with_guard_msg())
        return
    if _s23_is_exhaustive_optional_match_for(checker, node):
        return
    if _s23_is_exhaustive_union_match_for(checker, node):
        return
    if _s23_is_exhaustive_enum_match_for(checker, node):
        return
    checker._add(S23, node, _s23_match_missing_default_msg())

def _s24_slot_literal(sub: ast.pattern) -> object | None:
    """``None`` 表示槽位任意；否则为常量字面量。"""
    if isinstance(sub, ast.MatchValue) and isinstance(sub.value, ast.Constant):
        return sub.value.value
    if isinstance(sub, ast.MatchAs):
        if sub.pattern is None:
            return None
        if isinstance(sub.pattern, ast.MatchValue) and isinstance(sub.pattern.value, ast.Constant):
            return sub.pattern.value.value
    return None

def _s24_union_field_slots(pattern: ast.pattern, field_names: list[str]) -> list[object | None] | None:
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    if isinstance(pat, ast.MatchValue):
        return [None] * len(field_names)
    if not isinstance(pat, ast.MatchClass):
        return None
    slots: list[object | None] = [None] * len(field_names)
    for i, sub in enumerate(pat.patterns):
        if i >= len(field_names):
            break
        slots[i] = _s24_slot_literal(sub)
    for attr, sub in zip(pat.kwd_attrs, pat.kwd_patterns):
        if attr in field_names:
            slots[field_names.index(attr)] = _s24_slot_literal(sub)
    return slots

def _s24_earlier_pattern_shadows_later(slots_earlier: list[object | None], slots_later: list[object | None]) -> bool:
    if slots_earlier == slots_later:
        return True
    has_narrower_later = False
    for left, right in zip(slots_earlier, slots_later):
        if right is not None:
            if left is None:
                has_narrower_later = True
            elif left != right:
                return False
    return has_narrower_later

def _s24_shadowed_case_msg(variant_name: str) -> str:
    return _strict_msg('宽模式 case 排在具体 case 之前', '字面量更具体的 case 写在前面', f'``@union`` 变体 ``{variant_name}`` 多条 ``case``', reason='源序先匹配者生效；前序无 guard 的宽模式会吞掉后序字面量分支（暂不分析 guard）', example='case U.A(1, y):\n  ...\ncase U.A(x, _):\n  ...')

def _s24_non_contiguous_variant_msg(variant_name: str) -> str:
    return _strict_msg('同变体 case 与其它变体穿插', '同一变体的全部 case 连续排列', f'``@union`` 变体 ``{variant_name}`` 的 ``case``', reason='同一变体的多条 ``case`` 须成组出现，中间不得插入其它变体', example='case U.A(...):\n  ...\ncase U.A(...):\n  ...\ncase U.B:\n  ...')

def _s24_single_variant_for_case(info: ClassInfo, case: ast.match_case) -> str | None:
    if is_wildcard_pattern(case.pattern):
        return None
    if isinstance(case.pattern, ast.MatchOr):
        return None
    ref = _s23_union_case_ref(case.pattern, subject_union=info)
    if ref is None:
        return None
    union_name, variant_name = ref
    from .union_expand import union_accepts_case_union
    if not union_accepts_case_union(info, union_name):
        return None
    if variant_name not in {v.name for v in info.union_variants}:
        return None
    return variant_name

def _s24_check_union_variant_contiguity(checker: _StrictStyleChecker, node: ast.Match, info: ClassInfo) -> None:
    last_index_by_variant: dict[str, int] = {}
    for idx, case in enumerate(node.cases):
        variant_name = _s24_single_variant_for_case(info, case)
        if variant_name is None:
            continue
        prev = last_index_by_variant.get(variant_name)
        if prev is not None and idx != prev + 1:
            checker._add(S24, case, _s24_non_contiguous_variant_msg(variant_name))
        last_index_by_variant[variant_name] = idx

def _s24_union_info_for_match(checker: _StrictStyleChecker, node: ast.Match) -> ClassInfo | None:
    from .union_expand import union_info_from_subject_cpp
    subject_union = _match_subject_union_info(checker, node)
    if subject_union is not None:
        return subject_union
    subject_cpp = _s22_resolve_expr_cpp_type(checker, node.subject)
    if subject_cpp:
        info = union_info_from_subject_cpp(checker.tr, subject_cpp)
        if info is not None:
            return info
    union_names: set[str] = set()
    for case in node.cases:
        if is_wildcard_pattern(case.pattern):
            continue
        for branch_pat in _s23_union_branch_patterns(case.pattern):
            ref = _s23_union_case_ref(branch_pat, subject_union=subject_union)
            if ref is not None:
                union_names.add(ref[0])
    if len(union_names) != 1:
        return None
    union_name = next(iter(union_names))
    info = checker.tr.classes.get(union_name)
    if info is None or not info.is_union:
        return None
    return info

def _s25_optional_match_msg() -> str:
    return _strict_msg('case Optional.Some(...) / case Optional.None_:', 'case None: / 字面量 / case v:', '``Optional`` 的 ``match``', reason='内层 ``Some`` 用语法糖，勿写 union 变体名', example='match opt:\n  case None:\n    ...\n  case v:\n    ...')

def _s25_optional_variant_ctor_msg() -> str:
    return _strict_msg('Optional.Some(...) / Optional.None_()', 'None 或内层值', '``Optional[T]`` 赋值/传参/返回', reason='勿显式构造 union 变体，译器按目标 ``PyOptional<T>`` 自动装箱', example='`opt: Optional[T] = None` / `self.field = v` / `return x`')

def _s25_optional_identity_compare_msg(*, eq: bool) -> str:
    if eq:
        return _strict_msg('opt == None', 'opt is None', '``Optional`` 判空', example='if opt is None:\n  ...')
    return _strict_msg('opt != None', 'opt is not None', '``Optional`` 判非空', example='if opt is not None:\n  ...')

def _s25_optional_union_pattern(pattern: ast.pattern) -> ast.pattern | None:
    from .union_expand import parse_union_case_pattern
    if isinstance(pattern, ast.MatchOr):
        for branch in pattern.patterns:
            hit = _s25_optional_union_pattern(branch)
            if hit is not None:
                return hit
        return None
    pat = pattern
    if isinstance(pat, ast.MatchAs) and pat.pattern is not None:
        pat = pat.pattern
    ref = parse_union_case_pattern(pat)
    if ref is not None and ref.union_name == 'Optional':
        return pattern
    return None

def _s25_check_optional_match_patterns(checker: _StrictStyleChecker, node: ast.Match) -> None:
    for case in node.cases:
        hit = _s25_optional_union_pattern(case.pattern)
        if hit is not None:
            checker._add(S25, hit, _s25_optional_match_msg())

def _s25_is_none_like_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, ast.Name) and node.value.id == 'Optional' and (node.attr == 'None_')
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            return isinstance(func.value, ast.Name) and func.value.id == 'Optional' and (func.attr == 'None_')
    return False

def _s25_optional_variant_attr(func: ast.expr) -> ast.Attribute | None:
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in ('Some', 'None_'):
        return None
    val = func.value
    if isinstance(val, ast.Name) and val.id == 'Optional':
        return func
    if isinstance(val, ast.Subscript) and isinstance(val.value, ast.Name) and (val.value.id == 'Optional'):
        return func
    return None

def _s25_check_optional_variant_ctor(checker: _StrictStyleChecker, node: ast.Call) -> None:
    attr = _s25_optional_variant_attr(node.func)
    if attr is None:
        return
    if attr.attr == 'Some' or attr.attr == 'None_':
        checker._add(S25, attr, _s25_optional_variant_ctor_msg())

def _s25_expr_is_optional_typed(checker: _StrictStyleChecker, expr: ast.expr) -> bool:
    ty = _s22_resolve_expr_cpp_type(checker, expr)
    return bool(ty and is_optional_type(ty))

def _s25_check_optional_identity_compare(checker: _StrictStyleChecker, node: ast.Compare) -> None:
    left: ast.expr = node.left
    for op, right in zip(node.ops, node.comparators):
        if isinstance(op, ast.Eq):
            if _s25_expr_is_optional_typed(checker, left) and _s25_is_none_like_expr(right):
                checker._add(S25, node, _s25_optional_identity_compare_msg(eq=True))
            elif _s25_expr_is_optional_typed(checker, right) and _s25_is_none_like_expr(left):
                checker._add(S25, node, _s25_optional_identity_compare_msg(eq=True))
        elif isinstance(op, ast.NotEq):
            if _s25_expr_is_optional_typed(checker, left) and _s25_is_none_like_expr(right):
                checker._add(S25, node, _s25_optional_identity_compare_msg(eq=False))
            elif _s25_expr_is_optional_typed(checker, right) and _s25_is_none_like_expr(left):
                checker._add(S25, node, _s25_optional_identity_compare_msg(eq=False))
        left = right

def _s24_check_union_case_order(checker: _StrictStyleChecker, node: ast.Match) -> None:
    """Phase 1：``@union`` 同变体 ``case`` 须连续；前序无 guard 宽模式不得遮蔽后序更具体模式。"""
    from .optional_match import is_optional_union_info
    from .union_match import partition_union_match_cases
    info = _s24_union_info_for_match(checker, node)
    if info is None or is_optional_union_info(info):
        return
    _s24_check_union_variant_contiguity(checker, node, info)
    _, arms = partition_union_match_cases(info, node)
    for arm in arms:
        if len(arm.variant_names) != 1 or len(arm.cases) < 2:
            continue
        variant_name = arm.variant_names[0]
        variant = next((v for v in info.union_variants if v.name == variant_name), None)
        if variant is None:
            continue
        field_names = variant.fields
        cases = arm.cases
        for i in range(len(cases)):
            if cases[i].guard is not None:
                continue
            slots_i = _s24_union_field_slots(cases[i].pattern, field_names)
            if slots_i is None:
                continue
            for j in range(i + 1, len(cases)):
                slots_j = _s24_union_field_slots(cases[j].pattern, field_names)
                if slots_j is None:
                    continue
                if _s24_earlier_pattern_shadows_later(slots_i, slots_j):
                    checker._add(S24, cases[j], _s24_shadowed_case_msg(variant_name))

def _s22_check_char_literal_compare(checker: _StrictStyleChecker, node: ast.Compare) -> None:
    if checker._context_has('match') and (not checker._context_has('match_guard')):
        return
    left: ast.expr = node.left
    for op, right in zip(node.ops, node.comparators):
        if not isinstance(op, (ast.Eq, ast.NotEq)):
            left = right
            continue
        for char_expr, lit_expr in ((left, right), (right, left)):
            if not is_single_char_str_constant(lit_expr):
                continue
            if not _s22_expr_is_char_typed(checker, char_expr):
                continue
            assert isinstance(lit_expr, ast.Constant) and isinstance(lit_expr.value, str)
            checker._add(S22, node, _s22_char_literal_compare_msg(lit_expr.value))
            return
        left = right

def _s21_check_compare_chain(checker: _StrictStyleChecker, node: ast.BoolOp) -> None:
    if isinstance(node.op, ast.Or):
        parsed = _s21_parse_compare_chain(node, ast.Or, eq=True)
        if parsed is not None:
            subject, rhss = parsed
            checker._add(S21, node, _s21_compare_chain_msg(ast.unparse(subject), rhss, eq_or=True))
        return
    if isinstance(node.op, ast.And):
        parsed = _s21_parse_compare_chain(node, ast.And, eq=False)
        if parsed is None:
            return
        subject, rhss = parsed
        checker._add(S21, node, _s21_compare_chain_msg(ast.unparse(subject), rhss, eq_or=False))

def _s08_is_len_zero_compare(node: ast.Compare) -> bool:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    if not isinstance(node.left, ast.Call):
        return False
    if not isinstance(node.left.func, ast.Name) or node.left.func.id != 'len':
        return False
    if len(node.left.args) != 1 or node.left.keywords:
        return False
    right = node.comparators[0]
    if not isinstance(right, ast.Constant) or right.value != 0:
        return False
    op = node.ops[0]
    return isinstance(op, (ast.Eq, ast.NotEq, ast.Gt, ast.Lt, ast.GtE, ast.LtE))

def _slice_has_zero_lower(sl: ast.expr) -> bool:
    if isinstance(sl, ast.Slice):
        return isinstance(sl.lower, ast.Constant) and sl.lower.value == 0
    return False

def _same_simple_name_expr(a: ast.expr, b: ast.expr) -> bool:
    return isinstance(a, ast.Name) and isinstance(b, ast.Name) and (a.id == b.id)

def _subscript_len_minus_k_index(sl: ast.expr) -> int | None:
    """``seq[len(seq) - k]`` 中的 ``k``（正整数）。"""
    if not isinstance(sl, ast.BinOp) or not isinstance(sl.op, ast.Sub):
        return None
    if not isinstance(sl.left, ast.Call):
        return None
    if not isinstance(sl.left.func, ast.Name) or sl.left.func.id != 'len':
        return None
    if len(sl.left.args) != 1 or sl.left.keywords:
        return None
    if not isinstance(sl.right, ast.Constant) or not isinstance(sl.right.value, int):
        return None
    k: int = sl.right.value
    if k <= 0:
        return None
    return k

def _s10_is_len_minus_k_subscript(node: ast.Subscript) -> int | None:
    k: int | None = _subscript_len_minus_k_index(node.slice)
    if k is None or not isinstance(node.value, ast.Name):
        return None
    if not isinstance(node.slice, ast.BinOp):
        return None
    call: ast.Call = node.slice.left
    if not _same_simple_name_expr(node.value, call.args[0]):
        return None
    return k

def _is_self_field_ann_assign(target: ast.expr) -> bool:
    return isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and (target.value.id == 'self')

def _self_like_param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = {'self'}
    for arg in node.args.args:
        if _ann_is_self(arg.annotation):
            names.add(arg.arg)
    return names

def _field_name_from_ann_target(target: ast.expr) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and (target.value.id == 'self'):
        return target.attr
    return None

def _field_annotation_from_class_info(info: ClassInfo, attr: str) -> ast.expr | None:
    """字段 Python 注解（分析后 ``__ann__*`` 可能已删，回退类体 / ``__init__`` AST）。"""
    cached = field_ann_ast(info, attr)
    if cached is not None and isinstance(cached, ast.expr):
        return cached
    for stmt in info.node.body:
        if isinstance(stmt, ast.AnnAssign):
            if _field_name_from_ann_target(stmt.target) == attr:
                return strip_type_annotation_markers(stmt.annotation)
        elif isinstance(stmt, ast.FunctionDef) and stmt.name == '__init__':
            for child in stmt.body:
                if isinstance(child, ast.AnnAssign):
                    if _field_name_from_ann_target(child.target) == attr:
                        return strip_type_annotation_markers(child.annotation)
    return None

def _field_annotation_for_assign_target(checker: '_StrictStyleChecker', target: ast.expr) -> ast.expr | None:
    """``self._f`` / ``other._f``（``other: Self`` 等）→ 类字段注解 AST。"""
    if not isinstance(target, ast.Attribute):
        return None
    if not isinstance(target.value, ast.Name):
        return None
    if target.value.id not in checker._self_like_params:
        return None
    info = checker._current_class_info()
    if info is None:
        return None
    if target.attr not in info.fields:
        return None
    return _field_annotation_from_class_info(info, target.attr)

def _type_param_names(node: ast.ClassDef | ast.FunctionDef | ast.TypeAlias) -> set[str]:
    names: set[str] = set()
    for tp in getattr(node, 'type_params', None) or ():
        if isinstance(tp, ast.TypeVar):
            names.add(tp.name)
    return names

def _is_short_class_type_param_name(name: str) -> bool:
    """``T`` / ``T1`` / ``_K``：单字母（可加数字）；``Element`` / ``Key`` / ``Dim0`` 合法。"""
    body = name.lstrip('_')
    return bool(body) and bool(_SHORT_CLASS_TYPE_PARAM.match(body))

def _s48_short_class_type_param_message(class_name: str, param: str) -> str:
    return _strict_msg(
        f'class {class_name}[{param}, …]',
        '语义化形参名（如 Element / Key / Value / Bound）',
        '类 PEP 695 类型形参列表',
        reason='类形参会生成 ``using Alias = _Alias``，短名难读且易与译器隐式 ``T0``/``T1`` 混淆',
        example=f'class {class_name}[Element]: … 勿 class {class_name}[{param}]:',
    )

def _s15_subscript_slice_matches_class_type_params(sl: ast.expr, class_type_params: list[str]) -> bool:
    """``Task[T]`` 体内 ``Task[T]`` 表当前实例；``Task[None]``/``Task[U]``/``Task[list[U]]`` 等不算。"""
    if not class_type_params:
        return False
    if len(class_type_params) == 1:
        if isinstance(sl, ast.Tuple):
            return False
        return isinstance(sl, ast.Name) and sl.id == class_type_params[0]
    if isinstance(sl, ast.Tuple) and len(sl.elts) == len(class_type_params):
        return all((isinstance(elt, ast.Name) and elt.id == param for elt, param in zip(sl.elts, class_type_params)))
    return False

def _s15_allows_class_type_reference(hit: ast.expr, class_name: str, class_type_params: list[str]) -> bool:
    """``Cls[其它类型]`` 允许；裸 ``Cls`` 与 ``Cls[当前形参…]`` 仍须 ``Self``。"""
    if not isinstance(hit, ast.Subscript):
        return False
    if not isinstance(hit.value, ast.Name) or hit.value.id != class_name:
        return False
    return not _s15_subscript_slice_matches_class_type_params(hit.slice, class_type_params)

def _s15_same_class_message(class_name: str, *, scene: str, attr: str | None=None) -> str:
    if attr is not None:
        wrong = f'`{class_name}.{attr}`'
        right = f'`Self.{attr}`'
        example = f'`new._sqr_length(self)`、`return new.zero`'
    else:
        wrong = f'`{class_name}` / `list[{class_name}]` 等'
        right = '`Self` / `list[Self]` 等'
        example = f'`def f(self) -> Self:`、`nodes: list[Self] = []`'
    return _strict_msg(wrong, right, f'类 `{class_name}` 体内{scene}', example=example, reason=f'同类引用须用 PEP 695 `Self`（裸 `Cls` / `Cls[当前形参…]` 表当前实例；`{class_name}[其它类型]` 如 `{class_name}[None]`、`{class_name}[U]`、`{class_name}[list[U]]` 除外）')

def _find_class_name_in_annotation(ann: ast.expr | None, class_name: str) -> ast.expr | None:
    """注解 AST 中首次出现当前类名（非 ``Self``）的节点。"""
    if ann is None:
        return None
    core = strip_type_annotation_markers(ann)
    if core is None:
        return None

    def walk(node: ast.expr) -> ast.expr | None:
        if isinstance(node, ast.Name):
            if node.id == class_name:
                return node
            return None
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == class_name:
                return node
            hit = walk(node.value)
            if hit is not None:
                return hit
            sl = node.slice
            if isinstance(sl, ast.Tuple):
                for elt in sl.elts:
                    hit = walk(elt)
                    if hit is not None:
                        return hit
                return None
            return walk(sl)
        if isinstance(node, ast.Tuple):
            for elt in node.elts:
                hit = walk(elt)
                if hit is not None:
                    return hit
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return walk(node.left) or walk(node.right)
        if isinstance(node, ast.Constant) and node.value == class_name:
            return node
        return None
    return walk(core)

def _is_property_accessor(defn: ast.FunctionDef) -> bool:
    for dec in defn.decorator_list:
        if isinstance(dec, ast.Name) and dec.id in ('property', 'staticproperty'):
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in ('setter', 'getter', 'deleter'):
            if isinstance(dec.value, ast.Name) and dec.value.id in ('property', 'staticproperty'):
                return True
            return True
    return False

def _s41_self_private_attr(node: ast.Attribute) -> str | None:
    if isinstance(node.value, ast.Name) and node.value.id == 'self':
        if node.attr.startswith('_') and (not node.attr.startswith('__')):
            return node.attr
    return None

def _s41_instance_params(method: ast.FunctionDef) -> list[str]:
    return [a.arg for a in method.args.args if a.arg not in ('self', 'cls')]

def _s41_decapitalize(s: str) -> str:
    if not s:
        return s
    return s[0].lower() + s[1:]

def _s41_camel_prefix_stem(name: str, prefix: str) -> str | None:
    """``getValue`` / ``isDone`` / ``setKind`` → ``value`` / ``done`` / ``kind``（前缀后首字母须大写）。"""
    if not name.startswith(prefix):
        return None
    rest = name[len(prefix):]
    if not rest or not rest[0].isupper():
        return None
    return _s41_decapitalize(rest)

def _s41_getter_stem(name: str) -> str | None:
    for prefix in ('get', 'is'):
        stem = _s41_camel_prefix_stem(name, prefix)
        if stem is not None:
            return stem
    if _s41_camel_prefix_stem(name, 'set') is not None:
        return None
    return name

def _s41_setter_stem(name: str) -> str | None:
    return _s41_camel_prefix_stem(name, 'set')

def _s41_try_pure_field_getter(method: ast.FunctionDef) -> str | None:
    if _is_dunder(method.name) or _is_property_accessor(method):
        return None
    if has_named_decorator(method, 'staticmethod'):
        return None
    if _s41_instance_params(method):
        return None
    if len(method.body) != 1:
        return None
    stmt = method.body[0]
    if not isinstance(stmt, ast.Return) or stmt.value is None:
        return None
    if isinstance(stmt.value, ast.Attribute):
        return _s41_self_private_attr(stmt.value)
    return None

def _s41_try_pure_field_setter(method: ast.FunctionDef) -> str | None:
    if _is_dunder(method.name) or _is_property_accessor(method):
        return None
    if has_named_decorator(method, 'staticmethod'):
        return None
    params = _s41_instance_params(method)
    if len(params) != 1:
        return None
    if len(method.body) != 1:
        return None
    stmt = method.body[0]
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Attribute):
        return None
    field = _s41_self_private_attr(tgt)
    if field is None:
        return None
    val = stmt.value
    if not isinstance(val, ast.Name) or val.id not in params:
        return None
    return field

def _s41_private_accessor_pair_msg(*, getter: str, setter: str, field: str) -> str:
    public = field[1:] if field.startswith('_') else field
    return _strict_msg(f'`def {getter}(self): return self.{field}` 与 `def {setter}(self, …): self.{field} = …`', f'``@property def {public}(self)`` + ``@property.setter``，或改为公有字段 ``{public}: T``', '类内私有字段纯读写方法对（``kind``/``isDone``/``getValue`` 与 ``setKind``/``setValue`` 同理）', reason='仅读写 ``self._field`` 的 getter/setter 须 ``@property`` 或公有字段；getter 除 ``self`` 外无参，setter 除 ``self`` 外仅一个赋值形参', example=f'``@property def {public}(self) -> T: return self.{field}``；``@property.setter def {public}(self, v: T): self.{field} = v``')

def _check_s41_private_field_accessor_pairs(tr: Translator, violations: list[_Violation]) -> None:
    skip = getattr(tr, 'skip_cached_analysis_module', None)
    for info in tr.classes.values():
        if skip is not None and skip(info.module_path):
            continue
        if info.is_protocol or info.is_descriptor or info.is_annotation:
            continue
        getters_by_field: dict[str, ast.FunctionDef] = {}
        setters_by_field: dict[str, ast.FunctionDef] = {}
        getters_by_stem: dict[str, ast.FunctionDef] = {}
        setters_by_stem: dict[str, ast.FunctionDef] = {}
        for method in _iter_class_methods(info):
            field = _s41_try_pure_field_getter(method)
            if field is not None:
                getters_by_field[field] = method
                stem = _s41_getter_stem(method.name)
                if stem is not None:
                    getters_by_stem[stem] = method
                continue
            field = _s41_try_pure_field_setter(method)
            if field is not None:
                setters_by_field[field] = method
                stem = _s41_setter_stem(method.name)
                if stem is not None:
                    setters_by_stem[stem] = method
        reported: set[tuple[str, str]] = set()
        for field, getter in getters_by_field.items():
            setter = setters_by_field.get(field)
            if setter is None:
                g_stem = _s41_getter_stem(getter.name)
                if g_stem is not None:
                    setter = setters_by_stem.get(g_stem)
            if setter is None:
                continue
            key = (getter.name, setter.name)
            if key in reported:
                continue
            reported.add(key)
            msg = _s41_private_accessor_pair_msg(getter=getter.name, setter=setter.name, field=field)
            violations.append(_Violation(S41, msg, getter, info.module_path))
            violations.append(_Violation(S41, msg, setter, info.module_path))

def _s42_is_trivial_instance_getter(method: ast.FunctionDef, prop_name: str) -> bool:
    if len(method.body) != 1:
        return False
    stmt = method.body[0]
    if not isinstance(stmt, ast.Return) or stmt.value is None:
        return False
    val = stmt.value
    if not isinstance(val, ast.Attribute):
        return False
    if not isinstance(val.value, ast.Name) or val.value.id != 'self':
        return False
    attr = val.attr
    if attr == f'{prop_name}__value':
        return True
    return attr.startswith('_') and (not attr.startswith('__'))

def _s42_is_trivial_static_getter(method: ast.FunctionDef) -> bool:
    if len(method.body) != 1:
        return False
    stmt = method.body[0]
    if not isinstance(stmt, ast.Return) or stmt.value is None:
        return False
    val = stmt.value
    if not isinstance(val, ast.Attribute):
        return False
    if not isinstance(val.value, ast.Name) or val.value.id != 'Self':
        return False
    return val.attr == '__value__'

def _s42_is_pure_instance_setter(setter: ast.FunctionDef, prop_name: str) -> bool:
    params = _s41_instance_params(setter)
    if len(params) != 1:
        return False
    if len(setter.body) != 1:
        return False
    stmt = setter.body[0]
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Attribute):
        return False
    if not isinstance(tgt.value, ast.Name) or tgt.value.id != 'self':
        return False
    val = stmt.value
    if not isinstance(val, ast.Name) or val.id != params[0]:
        return False
    attr = tgt.attr
    if attr == f'{prop_name}__value':
        return True
    return attr.startswith('_') and (not attr.startswith('__'))

def _s42_is_pure_static_setter(setter: ast.FunctionDef) -> bool:
    params = [a.arg for a in setter.args.args if a.arg not in ('self', 'cls')]
    if len(params) != 1:
        return False
    if len(setter.body) != 1:
        return False
    stmt = setter.body[0]
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Attribute):
        return False
    if not isinstance(tgt.value, ast.Name) or tgt.value.id != 'Self':
        return False
    if tgt.attr != '__value__':
        return False
    val = stmt.value
    return isinstance(val, ast.Name) and val.id == params[0]

def _s42_prefer_postsetter_msg(*, prop: str, static: bool) -> str:
    dec = '@staticproperty.postsetter' if static else '@property.postsetter'
    return _strict_msg(f'``@property def {prop}`` 仅 ``return self._…``/``{prop}__value`` 且 ``@property.setter`` 含赋值后逻辑', f'``{prop}: T {dec}(cb) = …`` 或 ``{dec} def {prop}(self, value: T): …``（getter 由译器合成）', '可写属性 getter 无额外逻辑时', reason='getter 仅读存储字段时应使用 postsetter 合成 ``name__get``/``name__set``，回调写在 postsetter 体或 ``cb`` 参数', example=f'``{prop}: int {dec}(self._sync) = 0`` 或 ``{dec} def {prop}(self, value: int): self._sync(value)``')

def _s42_is_backing_assign_to_param(stmt: ast.stmt, prop_name: str, param: str, *, static: bool) -> bool:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    tgt = stmt.targets[0]
    if not isinstance(tgt, ast.Attribute):
        return False
    if static:
        if not isinstance(tgt.value, ast.Name) or tgt.value.id != 'Self':
            return False
        if tgt.attr != '__value__':
            return False
    else:
        if not isinstance(tgt.value, ast.Name) or tgt.value.id != 'self':
            return False
        attr = tgt.attr
        if attr != f'{prop_name}__value' and (not (attr.startswith('_') and (not attr.startswith('__')))):
            return False
    val = stmt.value
    return isinstance(val, ast.Name) and val.id == param

def _s42_is_assign_then_extra_setter(setter: ast.FunctionDef, prop_name: str, *, static: bool) -> bool:
    """setter 体顶层的 ``self._field = value`` + 其它语句（postsetter 可合成赋值）。"""
    if static:
        if _s42_is_pure_static_setter(setter):
            return False
        params = [a.arg for a in setter.args.args if a.arg not in ('self', 'cls')]
    else:
        if _s42_is_pure_instance_setter(setter, prop_name):
            return False
        params = _s41_instance_params(setter)
    if len(params) != 1:
        return False
    if len(setter.body) <= 1:
        return False
    param = params[0]
    for stmt in setter.body:
        if _s42_is_backing_assign_to_param(stmt, prop_name, param, static=static):
            return True
    return False

def _check_s42_prefer_postsetter(tr: Translator, violations: list[_Violation]) -> None:
    for info in tr.classes.values():
        if info.is_protocol or info.is_descriptor or info.is_annotation:
            continue
        for prop_name, prop in info.properties.items():
            if prop.from_descriptor or prop.descriptor_protocol_bounds:
                continue
            if prop.postsetter is not None:
                continue
            if prop.getter is None or prop.setter is None:
                continue
            if not _s42_is_trivial_instance_getter(prop.getter, prop_name):
                continue
            if not _s42_is_assign_then_extra_setter(prop.setter, prop_name, static=False):
                continue
            msg = _s42_prefer_postsetter_msg(prop=prop_name, static=False)
            violations.append(_Violation(S42, msg, prop.getter, info.module_path))
            violations.append(_Violation(S42, msg, prop.setter, info.module_path))
        for prop_name, prop in info.static_properties.items():
            if prop.postsetter is not None:
                continue
            if prop.getter is None or prop.setter is None:
                continue
            if not _s42_is_trivial_static_getter(prop.getter):
                continue
            if not _s42_is_assign_then_extra_setter(prop.setter, prop_name, static=True):
                continue
            msg = _s42_prefer_postsetter_msg(prop=prop_name, static=True)
            violations.append(_Violation(S42, msg, prop.getter, info.module_path))
            violations.append(_Violation(S42, msg, prop.setter, info.module_path))

def _function_def_groups(stmts: list[ast.stmt]) -> dict[str, list[ast.FunctionDef]]:
    groups: dict[str, list[ast.FunctionDef]] = {}
    for stmt in stmts:
        if isinstance(stmt, ast.FunctionDef):
            groups.setdefault(stmt.name, []).append(stmt)
    return groups

def _s17_group_requires_overload(defs: list[ast.FunctionDef]) -> bool:
    if len(defs) < 2:
        return False
    if len(defs) == 2 and all((_is_property_accessor(d) for d in defs)):
        return False
    return True

def _dataclass_field_ann_node(info: ClassInfo, field_name: str) -> ast.AST | None:
    for stmt in info.node.body:
        if isinstance(stmt, ast.AnnAssign):
            if _field_name_from_ann_target(stmt.target) == field_name:
                return stmt
    return info.node

def _s26_dataclass_container_optional_msg(field: str) -> str:
    return _strict_msg(f'`{field}: list[…] = []` 等容器默认', f'`{field}: list[…] @optional = []`', '@dataclass 类体', example='``@dataclass`` 时 ``tags: list[str] @optional = []``（``char[:]/byte[:]`` 空默认同理）；``@copyable`` 选项类勿叠 ``@dataclass``，直接 ``headers: dict[str, str] = {}``（**不必** ``@optional``，见 S32）', reason='``@dataclass`` 容器/``char[:]`` 默认须在 ``__init__`` 体内初始化，不能作 C++ 引用形参默认；``@copyable`` 走类体成员 C++ 字段初值')

def _s32_dataclass_no_fields_msg(class_name: str) -> str:
    return _strict_msg(f'`@dataclass class {class_name}` 无实例字段', '去掉 ``@dataclass`` 或至少写一个带类型注解的实例字段', '@dataclass 类体', example='无字段占位类勿 ``@dataclass``；纯选项袋（``**kwargs: Opt``）用 ``@copyable class Opt: …`` + 类体 ``T = 默认``', reason='空 dataclass 无法生成有意义的 ``__init__``')

def _s32_dataclass_all_optional_msg(class_name: str) -> str:
    return _strict_msg(f'`@dataclass class {class_name}` 全部字段 ``@optional``', '去掉 ``@dataclass``，改用 ``@copyable`` + 类体 ``T = 默认``（**不必** ``@optional``）', '@dataclass 类体', example='``@copyable class RequestOptions: headers: dict[str, str] = {}; params: dict[str, str] = {}; data: bytes = b""``（``**kwargs: RequestOptions`` 仍可用）；勿 ``_pad`` 占位 + ``@dataclass``', reason='全部 ``@optional`` 时 ``__init__`` 无构造形参，``@dataclass`` 无意义；``@copyable`` 由 C++ 成员初值承担默认（空 ``{}`` → ``PyDict<K,V>()``，空 ``b""`` 等同理）')

def check_s32_dataclass_required_fields(tr: Translator) -> None:
    """S32：``@dataclass`` 须至少一个非 ``@optional`` 实例字段（须在 ``expand_dataclass`` 之前调用）。"""
    if not getattr(tr, 'strict', True):
        return
    from .dataclass_expand import _collect_dataclass_fields, _parse_dataclass_options
    violations: list[_Violation] = []
    for info in tr.classes.values():
        if info.is_descriptor or info.is_mixin or info.is_protocol:
            continue
        if _parse_dataclass_options(info.node) is None:
            continue
        specs = _collect_dataclass_fields(info.node, allow_empty=True)
        if not specs:
            violations.append(_Violation(S32, _s32_dataclass_no_fields_msg(info.name), info.node, info.module_path))
        elif all((spec.optional for spec in specs)):
            violations.append(_Violation(S32, _s32_dataclass_all_optional_msg(info.name), info.node, info.module_path))
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处编码规范违规（可用 --no-strict 关闭）：']
    first_loc: SourceLocation | None = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)

def _check_s26_dataclass_container_optional(tr: Translator, violations: list[_Violation]) -> None:
    from .dataclass_expand import _annotation_is_mutable_container
    for info in tr.classes.values():
        if not info.is_dataclass:
            continue
        specs = info.dataclass_field_specs
        if not specs:
            continue
        for spec in specs:
            if spec.optional:
                continue
            if not _annotation_is_mutable_container(spec.annotation):
                continue
            if spec.body_init is None and spec.default is None:
                continue
            node = _dataclass_field_ann_node(info, spec.name)
            violations.append(_Violation(S26, _s26_dataclass_container_optional_msg(spec.name), node, info.module_path))

def _s44_final_optional_msg(field: str) -> str:
    return _strict_msg(
        f'`{field}: T @final @optional`',
        '去掉 ``@optional`` 或 ``@final`` 之一',
        '类体字段注解',
        example='``@final`` 字段须进 ``__init__`` 形参；``@optional`` 字段不进形参——二者不可同字段',
        reason='``@final`` 与 ``@optional`` 在构造形参与 C++ ``const`` 语义上互斥',
    )

def _s44_frozen_optional_msg(class_name: str, field: str) -> str:
    return _strict_msg(
        f'`@dataclass(frozen=True) class {class_name}` 字段 ``{field} @optional``',
        '去掉 ``@optional`` 或勿 ``frozen=True``',
        '@dataclass 类体',
        example='``@dataclass(frozen=True) class P: x: int``（全字段 ``@final``，勿 ``T @optional``）',
        reason='``frozen=True`` 等价全字段 ``@final``；``@optional`` 不进 ``__init__`` 形参，与 frozen 字段初始化冲突',
    )

def _s45_optional_non_dataclass_msg(class_name: str, field: str) -> str:
    return _strict_msg(
        f'`class {class_name}` 非 dataclass 字段 ``{field}: T @optional``',
        '去掉 ``@optional``；若需要自动构造参数控制，则给类加 ``@dataclass``',
        '类体字段注解',
        example='``@copyable class Opt: headers: dict[str, str] = {}``；或 ``@dataclass class Row: tags: list[str] @optional = []``',
        reason='``@optional`` 只用于 ``@dataclass`` 生成 ``__init__`` 时排除该字段；普通类字段默认值直接由类体初始化承担',
    )

def check_s44_field_annotation_markers(tr: Translator) -> None:
    """S44/S45：字段标记组合约束（须在 ``expand_dataclass`` 之前）。"""
    if not getattr(tr, 'strict', True):
        return
    from ..analysis.ir import iter_matmult_marker_names
    from .dataclass_expand import _parse_dataclass_options

    violations: list[_Violation] = []
    for info in tr.classes.values():
        opts = _parse_dataclass_options(info.node)
        frozen = opts is not None and opts.frozen
        is_dc = opts is not None
        for stmt in info.node.body:
            if not isinstance(stmt, ast.AnnAssign) or stmt.annotation is None:
                continue
            name = _field_name_from_ann_target(stmt.target)
            if name is None:
                continue
            markers = set(iter_matmult_marker_names(stmt.annotation))
            if 'final' in markers and 'optional' in markers:
                violations.append(
                    _Violation(S44, _s44_final_optional_msg(name), stmt, info.module_path),
                )
            if (not is_dc) and 'optional' in markers:
                violations.append(
                    _Violation(S45, _s45_optional_non_dataclass_msg(info.name, name), stmt, info.module_path),
                )
            if frozen and 'optional' in markers:
                violations.append(
                    _Violation(
                        S44,
                        _s44_frozen_optional_msg(info.name, name),
                        stmt,
                        info.module_path,
                    ),
                )
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处编码规范违规（可用 --no-strict 关闭）：']
    first_loc: SourceLocation | None = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)

def _expected_builtins_import_line(tr: Translator, module_path: str) -> str:
    from ..analysis.stubs.paths import PY2CPP
    path = tr.module_py_paths.get(module_path)
    if path is None:
        return ''
    try:
        rel = path.resolve().relative_to(PY2CPP.resolve()).as_posix()
    except ValueError:
        return ''
    depth = rel.count('/')
    prefix = '.' * (depth + 1)
    return f'from {prefix}builtins import *'

def _s27_missing_builtins_msg(expected: str) -> str:
    return _strict_msg(f'缺少 ``{expected}``', f'模块顶部写 ``{expected}``', '``py2cpp/`` 标准库子模块', reason='内建/装饰器由 ``builtins`` 统一提供，勿 ``from .. import …`` 挑符号', example=expected)

def _s27_missing_py2cpp_star_msg() -> str:
    return _strict_msg('缺少 ``from py2cpp import *``', '模块顶部写 ``from py2cpp import *``', '用户/测试模块', reason='内建/标准库类型统一 star import，勿 ``from py2cpp import foo, bar``', example='from py2cpp import *')

def _s27_forbidden_named_py2cpp_import_msg() -> str:
    return _strict_msg('``from py2cpp import foo, bar``', '``from py2cpp import *``', '用户/测试模块', reason='包根 star import 已提供内建/装饰器，勿具名挑符号', example='from py2cpp import *')

def _s27_forbidden_submodule_root_import_msg(module: str, sym: str) -> str:
    return _strict_msg(f'``from {module} import {sym}``', '``from py2cpp import *``', '用户/测试模块', reason='包根 star import 已提供的符号，勿从其它子模块路径导入', example='from py2cpp import *')
_PY2CPP_ROOT_STAR_NAMES: frozenset[str] | None = None
_IO_SUBMODULE_ROOT_OK = frozenset({'open', 'StringIO', 'TextIOWrapper'})
_UNITTEST_SUBMODULE_OK = frozenset({'TestCaseMixin', 'TestSuite', 'TextTestRunner'})

def _py2cpp_root_star_names() -> frozenset[str]:
    global _PY2CPP_ROOT_STAR_NAMES
    if _PY2CPP_ROOT_STAR_NAMES is not None:
        return _PY2CPP_ROOT_STAR_NAMES
    from ..analysis.stubs.paths import PY2CPP
    init = PY2CPP / '__init__.py'
    tree = ast.parse(init.read_text(encoding='utf-8'))
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id != '__all__':
                continue
            if not isinstance(node.value, ast.List):
                continue
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(elt.value)
    _PY2CPP_ROOT_STAR_NAMES = frozenset(names)
    return _PY2CPP_ROOT_STAR_NAMES

def _check_s27_user_py2cpp_imports(tr: Translator, module_path: str, tree: ast.AST, violations: list[_Violation]) -> None:
    root_names = _py2cpp_root_star_names()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        mod = node.module or ''
        imported = [alias.name for alias in node.names if alias.name != '*']
        if mod == 'py2cpp':
            if imported and any((name in root_names for name in imported)):
                violations.append(_Violation(S27, _s27_forbidden_named_py2cpp_import_msg(), node, module_path))
            continue
        if not mod.startswith('py2cpp.'):
            continue
        for sym in imported:
            if sym not in root_names:
                continue
            if mod == 'py2cpp.io' and sym in _IO_SUBMODULE_ROOT_OK:
                continue
            if mod == 'py2cpp.test.unittest' and sym in _UNITTEST_SUBMODULE_OK:
                continue
            violations.append(_Violation(S27, _s27_forbidden_submodule_root_import_msg(mod, sym), node, module_path))

def _check_s27_imports(tr: Translator, violations: list[_Violation]) -> None:
    from ..constant.stdlib_layout import RUNTIME_PKG
    star = 'from py2cpp import *'
    for module_path, tree in tr.module_asts.items():
        if not _should_check_module(tr, module_path):
            continue
        source = _module_source(tr, module_path)
        if not source:
            continue
        norm = module_path.replace('\\', '/')
        if norm == RUNTIME_PKG or norm.startswith(f'{RUNTIME_PKG}/'):
            if norm in (RUNTIME_PKG, f'{RUNTIME_PKG}/builtins'):
                continue
            rel = norm[len(RUNTIME_PKG) + 1:]
            expected = _expected_builtins_import_line(tr, norm)
            if expected and expected not in source:
                violations.append(_Violation(S27, _s27_missing_builtins_msg(expected), tree, module_path))
            continue
        from ..constant.ffi_layout import is_ffi_module_path
        if is_ffi_module_path(norm):
            # 生成器产出 ``from py2cpp.builtins import *``（同标准库域内风格），勿要求包根 star
            if 'from py2cpp.builtins import *' not in source and 'from py2cpp import *' not in source:
                violations.append(
                    _Violation(S27, _s27_missing_builtins_msg('from py2cpp.builtins import *'), tree, module_path)
                )
            continue
        if star not in source:
            violations.append(_Violation(S27, _s27_missing_py2cpp_star_msg(), tree, module_path))
        _check_s27_user_py2cpp_imports(tr, module_path, tree, violations)

def _s28_forbidden_array_ann_message(root: str) -> str:
    return f'堆/栈数组类型须用切片注解（如 int[:]、int[:,:]、int[:R, :C]），勿写 {root}[…]'

def _s28_array_ann_allowed(node: ast.Subscript) -> bool:
  if not isinstance(node.value, ast.Name) or node.value.id != "array":
    return False
  sl = node.slice
  if not isinstance(sl, ast.Tuple) or len(sl.elts) < 2:
    return False
  cap = sl.elts[1]
  if isinstance(cap, ast.Name):
    return True
  if isinstance(cap, ast.Constant) and isinstance(cap.value, int):
    return True
  return False

def _iter_s28_array_ann_nodes(ann: ast.expr | None):
    if ann is None:
        return
    for node in ast.walk(ann):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in _SLICE_ARRAY_ANN_ROOTS:
                if _s28_array_ann_allowed(node):
                    continue
                yield node

def _check_s28_slice_array_annotations(tr: Translator, violations: list[_Violation]) -> None:
    for module_path, tree in tr.module_asts.items():
        if not _should_check_module(tr, module_path):
            continue
        for node in ast.walk(tree):
            ann: ast.expr | None = None
            if isinstance(node, ast.AnnAssign):
                ann = node.annotation
            elif isinstance(node, ast.arg):
                ann = node.annotation
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is not None:
                    for hit in _iter_s28_array_ann_nodes(node.returns):
                        violations.append(_Violation(S28, _s28_forbidden_array_ann_message(hit.value.id), hit, module_path))
                continue
            if ann is None:
                continue
            for hit in _iter_s28_array_ann_nodes(ann):
                violations.append(_Violation(S28, _s28_forbidden_array_ann_message(hit.value.id), hit, module_path))

def _check_s17_overload(tr: Translator, module_path: str, tree: ast.Module, violations: list[_Violation]) -> None:
    groups = _function_def_groups(tree.body)
    for name, defs in groups.items():
        if not _s17_group_requires_overload(defs):
            continue
        if all((has_named_decorator(d, 'overload') for d in defs)):
            continue
        for defn in defs:
            if has_named_decorator(defn, 'overload'):
                continue
            violations.append(_Violation(S17, _strict_msg('部分 `def` 未标 `@overload`', '同名组全部 `@overload`', f'模块级同名函数 `{name}`（共 {len(defs)} 个）', example=f'在每个 `def {name}(…)` 上一行加 `@overload`', reason='静态重载须显式声明'), defn, module_path))
    for info in tr.classes.values():
        if info.module_path != module_path:
            continue
        class_groups = _function_def_groups(info.node.body)
        for name, defs in class_groups.items():
            if not _s17_group_requires_overload(defs):
                continue
            if all((has_named_decorator(d, 'overload') for d in defs)):
                continue
            for defn in defs:
                if has_named_decorator(defn, 'overload'):
                    continue
                violations.append(_Violation(S17, _strict_msg('部分方法未标 `@overload`', '同名组全部 `@overload`', f'类 `{info.name}` 内同名方法 `{name}`（共 {len(defs)} 个）', example=f'在每个 `def {name}(…)` 上一行加 `@overload`', reason='静态重载须显式声明'), defn, module_path))

def _resolve_inherited_method(tr: Translator, info: ClassInfo, method_name: str) -> tuple[ClassInfo, ast.FunctionDef] | None:
    seen: set[str] = set()
    stack = list(info.bases)
    while stack:
        base_name = stack.pop(0)
        if base_name in seen:
            continue
        seen.add(base_name)
        base_info = tr.classes.get(base_name)
        if base_info is None:
            continue
        if method_name in base_info.methods:
            return (base_info, base_info.methods[method_name])
        if method_name == '__init__' and base_info.inits:
            return (base_info, base_info.inits[-1])
        stack.extend(base_info.bases)
    return None

def _skip_class_for_s18(info: ClassInfo) -> bool:
    return info.is_protocol or info.is_descriptor or info.is_annotation or info.is_union

def _iter_class_methods(info: ClassInfo) -> list[ast.FunctionDef]:
    out: list[ast.FunctionDef] = list(info.methods.values())
    out.extend(info.inits)
    for overloads in info.method_overloads.values():
        out.extend(overloads)
    return out

def _reverse_binop_other_is_self_type(func: ast.FunctionDef, class_name: str) -> bool:
    args = list(func.args.args)
    if len(args) < 2:
        return False
    ann = args[1].annotation
    if ann is None:
        return False
    stripped = strip_type_annotation_markers(ann)
    if isinstance(stripped, ast.Name):
        return stripped.id in ('Self', class_name)
    return False

def _s29_reverse_self_dunder_message(method_name: str) -> str:
    forward = method_name.replace('__r', '__', 1) if method_name.startswith('__r') else method_name
    return _strict_msg(f'`def {method_name}(self, other: Self)`', '仅保留异类型右操作数重载（如 `__radd__(self, other: int)`）', f'反向运算符 `{method_name}` 与同类型 `{forward}` 重复', reason='同类型 `a op b` 已由正向 dunder / C++ `operator` 覆盖；同类型 `__r*` 易与成员 `operator` 二义且多为恒等转发', example=f'删除 `{method_name}(self, other: Self)`，保留标量/其它类型参数版本')

def _check_s29_reverse_self_dunder(tr: Translator, module_path: str, violations: list[_Violation]) -> None:
    from ..constant.dunder_ops import BINARY_DUNDER_TO_REVERSE
    reverse_dunders = frozenset(BINARY_DUNDER_TO_REVERSE.values()) | frozenset({'__rpow__', '__rmatmul__'})
    for info in tr.classes.values():
        if info.module_path != module_path:
            continue
        if _skip_class_for_s18(info):
            continue
        for method in _iter_class_methods(info):
            if method.name not in reverse_dunders:
                continue
            if not _reverse_binop_other_is_self_type(method, info.name):
                continue
            violations.append(_Violation(S29, _s29_reverse_self_dunder_message(method.name), method, module_path))

def _s30_base_category(tr: Translator, base_ast: ast.expr) -> str:
    """``entity`` | ``mixin`` | ``skip``（``@protocol`` / ``@annotation``）。"""
    from ..analysis.ir import class_base_name
    from .mixins import is_mixin_class
    name = class_base_name(base_ast)
    if name is None:
        return 'skip'
    info = tr.classes.get(name)
    if info is None:
        return 'entity'
    if is_mixin_class(info):
        return 'mixin'
    if info.is_protocol or info.is_annotation:
        return 'skip'
    return 'entity'

def _skip_class_for_s30(info: ClassInfo) -> bool:
    return info.is_protocol or info.is_descriptor or info.is_annotation or info.is_enum or info.is_union or info.is_refcount or info.is_boxing

def _check_s30_inheritance_bases(tr: Translator, module_path: str, violations: list[_Violation]) -> None:
    for info in tr.classes.values():
        if info.module_path != module_path:
            continue
        if _skip_class_for_s30(info):
            continue
        entity_count = 0
        seen_entity = False
        for base_ast in info.node.bases:
            cat = _s30_base_category(tr, base_ast)
            if cat == 'skip':
                continue
            if cat == 'entity':
                entity_count += 1
                if entity_count > 1:
                    violations.append(_Violation(S30, _strict_msg(f'class {info.name}(…)', '至多继承一个实体类', '基类列表含多个实体类', reason='Py2Cpp 不允许多继承实体类；可用多个 ``@mixin`` + 一个实体基类', example='class Host(MixinA, MixinB, Base): …'), info.node, module_path))
                    break
                seen_entity = True
                continue
            if cat == 'mixin' and seen_entity:
                violations.append(_Violation(S30, _strict_msg(f'class {info.name}(…)', '``@mixin`` 写在实体基类之前', '实体基类之后出现 ``@mixin``', reason='mixin 须先于实体类，以便 ``__base__`` 唯一表示实体基类', example='class Host(IncMixin, Base): …'), base_ast, module_path))
                break

def _s18_virtual_or_abstract_origin(tr: Translator, base_info: ClassInfo, base_method: ast.FunctionDef, method_name: str) -> ClassInfo | None:
    """继承链上是否存在 ``@virtual``/``@abstract`` 声明（含中间层仅 ``@override`` 实现者）。"""
    if has_named_decorator(base_method, 'virtual') or has_named_decorator(base_method, 'abstract'):
        return base_info
    seen: set[str] = {base_info.name}
    stack = list(base_info.bases)
    while stack:
        bn = stack.pop(0)
        if bn in seen:
            continue
        seen.add(bn)
        bi = tr.classes.get(bn)
        if bi is None:
            continue
        if bi.is_mixin:
            stack.extend(bi.bases)
            continue
        if method_name in bi.methods:
            bm = bi.methods[method_name]
            if has_named_decorator(bm, 'virtual') or has_named_decorator(bm, 'abstract'):
                return bi
            return None
        stack.extend(bi.bases)
    return None

def _constraint_protocol_names(constraint: FuncTypeConstraint) -> tuple[str, ...]:
    if isinstance(constraint, str):
        return (constraint,)
    if isinstance(constraint, tuple):
        return constraint
    if isinstance(constraint, FuncTypeParametricBound):
        return (constraint.protocol,)
    return ()

def _subscript_type_arg_names(slice_node: ast.expr) -> list[str]:
    if isinstance(slice_node, ast.Name):
        return [slice_node.id]
    if isinstance(slice_node, ast.Tuple):
        return [el.id for el in slice_node.elts if isinstance(el, ast.Name)]
    return []

def _module_function_def(tr: Translator, module_path: str, name: str) -> ast.FunctionDef | None:
    for mp, func in tr.module_functions:
        if mp == module_path and func.name == name:
            return func
    return None

def _iter_func_type_arg_subscripts(tree: ast.AST):
    """``try_parse[Widget](…)`` / ``read_tag[Labeled]`` → ``(函数名, slice)``。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            yield (node.value.id, node.slice)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Subscript) and isinstance(node.func.value, ast.Name):
            yield (node.func.value.id, node.func.slice)

def _func_type_param_protocol_bounds(func: ast.FunctionDef) -> dict[str, tuple[str, ...]]:
    """PEP 695 头上 ``T: IParsableType``（含用户 ``@protocol``）→ 形参协议名。"""
    from ..analysis.ir import parse_typevar_protocol_bounds
    out: dict[str, tuple[str, ...]] = {}
    for tp in getattr(func, 'type_params', None) or ():
        if isinstance(tp, ast.TypeVar):
            bounds = parse_typevar_protocol_bounds(tp.bound)
            if bounds:
                out[tp.name] = bounds
    return out

def _collect_class_protocol_bindings(tr: Translator, module_path: str) -> dict[str, set[str]]:
    """``func[Widget]`` 且 ``func`` 头上 ``T: IParsableType`` → ``Widget`` 绑定 ``IParsableType``。"""
    from collections import defaultdict
    bindings: dict[str, set[str]] = defaultdict(set)
    tree = tr.module_asts.get(module_path)
    if tree is None:
        return {}
    func_cache: dict[str, ast.FunctionDef | None] = {}

    def func_def(name: str) -> ast.FunctionDef | None:
        if name not in func_cache:
            func_cache[name] = _module_function_def(tr, module_path, name)
        return func_cache[name]
    seen_subscripts: set[tuple[str, str]] = set()
    for func_name, slice_node in _iter_func_type_arg_subscripts(tree):
        class_names = _subscript_type_arg_names(slice_node)
        if not class_names:
            continue
        key = (func_name, ','.join(class_names))
        if key in seen_subscripts:
            continue
        seen_subscripts.add(key)
        func = func_def(func_name)
        if func is None:
            continue
        ft = FuncTypeParams.collect(func)
        ast_bounds = _func_type_param_protocol_bounds(func)
        for i, cls_name in enumerate(class_names):
            if i >= len(ft.template_names):
                break
            tp = ft.template_names[i]
            protos: set[str] = set()
            constraint = ft.constraints.get(tp)
            if constraint is not None:
                protos.update(_constraint_protocol_names(constraint))
            for pb in ast_bounds.get(tp, ()):
                protos.add(pb)
            for proto in protos:
                proto_info = tr.classes.get(proto)
                if proto_info is not None and proto_info.is_protocol:
                    bindings[cls_name].add(proto)
    return dict(bindings)

def _module_protocol_static_virtual_methods(tr: Translator, module_path: str) -> dict[str, dict[str, str]]:
    """``@protocol`` 静态虚成员：``协议名 → { 方法名: @abstract|@virtual }``。"""
    from .protocol import is_protocol_static_virtual_method
    merged: dict[str, dict[str, str]] = {}

    def collect(info: ClassInfo) -> dict[str, str]:
        if info.name in merged:
            return merged[info.name]
        methods: dict[str, str] = {}
        for base_name in info.bases:
            parent = tr.classes.get(base_name)
            if parent is not None and parent.is_protocol and (parent.module_path == module_path):
                methods.update(collect(parent))
        for stmt in info.node.body:
            if not isinstance(stmt, ast.FunctionDef):
                continue
            if not is_protocol_static_virtual_method(stmt):
                continue
            tag = '@abstract' if has_named_decorator(stmt, 'abstract') else '@virtual'
            methods[stmt.name] = tag
        merged[info.name] = methods
        return methods
    for info in tr.classes.values():
        if info.module_path == module_path and info.is_protocol:
            collect(info)
    return merged

def _append_s18_override_violation(violations: list[_Violation], *, info: ClassInfo, method: ast.FunctionDef, module_path: str, detail: str, static: bool) -> None:
    kind = '静态方法' if static else '方法'
    violations.append(_Violation(S18, _strict_msg(f'子类 `{info.name}.{method.name}` 覆盖{kind}', '在子类方法上加 `@override`', detail, example=f'在 `{info.name}.{method.name}` 上一行加 `@override`', reason='基类虚/纯虚或协议静态虚契约被覆盖时须显式标注，便于译期与阅读对齐 C++ ``override``'), method, module_path))

def _check_s18_static_override(tr: Translator, info: ClassInfo, method: ast.FunctionDef, module_path: str, violations: list[_Violation], *, protocol_static: dict[str, dict[str, str]], class_bindings: dict[str, set[str]]) -> None:
    if not has_named_decorator(method, 'staticmethod'):
        return
    if has_named_decorator(method, 'override'):
        return
    detail: str | None = None
    inherited = _resolve_inherited_method(tr, info, method.name)
    if inherited is not None:
        base_info, base_method = inherited
        if not base_info.is_mixin and (has_named_decorator(base_method, 'staticmethod') and has_named_decorator(base_method, 'override')):
            detail = f'继承链上 `{base_info.name}.{method.name}` 已标 `@override`。'
    if detail is None:
        for proto in class_bindings.get(info.name, ()):
            tag = protocol_static.get(proto, {}).get(method.name)
            if tag is not None:
                detail = f'模块内 ``…[{info.name}]`` 绑定 ``@protocol {proto}``，协议静态虚成员 ``{method.name}`` 为 {tag}。'
                break
    if detail is not None:
        _append_s18_override_violation(violations, info=info, method=method, module_path=module_path, detail=detail, static=True)

def _check_s18_instance_override(tr: Translator, info: ClassInfo, method: ast.FunctionDef, module_path: str, violations: list[_Violation]) -> None:
    if has_named_decorator(method, 'staticmethod'):
        return
    if has_named_decorator(method, 'override'):
        return
    inherited = _resolve_inherited_method(tr, info, method.name)
    if inherited is None:
        return
    base_info, base_method = inherited
    if base_info.is_mixin:
        return
    origin = _s18_virtual_or_abstract_origin(tr, base_info, base_method, method.name)
    if origin is None:
        return
    origin_method = base_method if origin is base_info else origin.methods[method.name]
    origin_tag = '@abstract' if has_named_decorator(origin_method, 'abstract') else '@virtual'
    _append_s18_override_violation(violations, info=info, method=method, module_path=module_path, detail=f'继承链上 `{origin.name}.{method.name}` 已标 {origin_tag}。', static=False)

def check_static_virtual_override_s18(tr: Translator) -> None:
    """静态虚 ``@override``（**S18**）：全模块含 ``test/fail/``。"""
    violations: list[_Violation] = []
    for module_path in tr.module_asts:
        skip = getattr(tr, 'skip_cached_analysis_module', None)
        if skip is not None and skip(module_path):
            continue
        protocol_static = _module_protocol_static_virtual_methods(tr, module_path)
        class_bindings = _collect_class_protocol_bindings(tr, module_path)
        for info in tr.classes.values():
            if info.module_path != module_path:
                continue
            if _skip_class_for_s18(info):
                continue
            for method in _iter_class_methods(info):
                if _is_dunder(method.name):
                    continue
                if _is_property_accessor(method):
                    continue
                _check_s18_static_override(tr, info, method, module_path, violations, protocol_static=protocol_static, class_bindings=class_bindings)
    if not violations:
        return
    parts: list[str] = [f'发现 {len(violations)} 处静态虚 ``@override`` 违规（S18）：']
    first_loc = None
    for v in violations:
        loc = location_from_node(tr, v.node, module_path=v.module_path)
        prefix = loc.prefix() if loc is not None else '?'
        parts.append(f'  {prefix}: [{v.rule}] {v.message}')
        if first_loc is None and loc is not None:
            first_loc = loc
    raise TranslationError('\n'.join(parts), location=first_loc)

def _check_s18_override_virtual(tr: Translator, module_path: str, violations: list[_Violation]) -> None:
    for info in tr.classes.values():
        if info.module_path != module_path:
            continue
        if _skip_class_for_s18(info):
            continue
        for method in _iter_class_methods(info):
            if _is_dunder(method.name):
                continue
            if _is_property_accessor(method):
                continue
            _check_s18_instance_override(tr, info, method, module_path, violations)

def _method_decorator_names(method: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for dec in method.decorator_list:
        if isinstance(dec, ast.Name):
            names.add(dec.id)
        elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
            names.add(dec.func.id)
    return names
_S39_FORBIDDEN_DECORATOR_PAIRS: tuple[tuple[str, str, str], ...] = (('abstract', 'virtual', '``@abstract`` 已隐含 ``virtual``，勿再标 ``@virtual``'), ('abstract', 'final', '``@abstract`` 纯虚方法不可 ``@final``'), ('abstract', 'staticmethod', '``@abstract`` 不可用于 ``@staticmethod``（``@protocol`` 内静态纯虚除外）'), ('abstract', 'native', '``@abstract`` 不可与 ``@native`` 同用'), ('virtual', 'final', '勿 ``@virtual`` + ``@final``；请单独 ``@final``（隐含 ``virtual``）或 ``@override`` + ``@final``'), ('virtual', 'override', '``@override`` 与 ``@virtual`` 勿同标于同一方法'), ('staticmethod', 'virtual', '静态方法不可 ``@virtual``（``@protocol`` 内 ``@staticmethod`` + ``@virtual``/``@abstract`` 除外）'), ('staticmethod', 'final', '静态方法不可 ``@final``'))

def _check_s39_method_decorator_conflicts(tr: Translator, module_path: str, violations: list[_Violation]) -> None:
    for info in tr.classes.values():
        if info.module_path != module_path:
            continue
        if _skip_class_for_s18(info):
            continue
        for method in _iter_class_methods(info):
            if method.name == '__init__':
                continue
            decs = _method_decorator_names(method)
            for a, b, reason in _S39_FORBIDDEN_DECORATOR_PAIRS:
                if a in decs and b in decs:
                    if info.is_protocol and a == 'abstract' and (b == 'staticmethod'):
                        continue
                    violations.append(_Violation(S39, _strict_msg(f'`{info.name}.{method.name}` 装饰器冲突', f'移除 ``@{a}`` 或 ``@{b}``', reason, example=f'``@{a}`` + ``@{b}`` 不可同用（类比 C# 修饰符）'), method, module_path))
                    break

def _check_static_virtual_protocol_rules(tr: Translator, module_path: str, violations: list[_Violation]) -> None:
    from .protocol import is_protocol_static_virtual_method
    for info in tr.classes.values():
        if info.module_path != module_path:
            continue
        for method in _iter_class_methods(info):
            if method.name == '__init__':
                continue
            decs = _method_decorator_names(method)
            is_static_virt = is_protocol_static_virtual_method(method)
            if info.is_protocol:
                if 'staticmethod' in decs and (not is_static_virt):
                    violations.append(_Violation(S39, _strict_msg(f'`{info.name}.{method.name}` 协议静态成员', '``@protocol`` 内 ``@staticmethod`` 须与 ``@virtual`` 或 ``@abstract`` 同用', '静态虚契约仅用于协议编译期派发'), method, module_path))
                if ('virtual' in decs or 'abstract' in decs) and 'staticmethod' not in decs:
                    violations.append(_Violation(S39, _strict_msg(f'`{info.name}.{method.name}` 协议虚成员', '``@protocol`` 内 ``@virtual``/``@abstract`` 实例方法须写 ``...`` 桩体；静态契约须 ``@staticmethod`` + ``@virtual``/``@abstract``', '实例虚表与静态虚契约语义不同'), method, module_path))
                continue
            if is_static_virt:
                violations.append(_Violation(S39, _strict_msg(f'`{info.name}.{method.name}` 静态虚方法', '``@staticmethod`` + ``@virtual``/``@abstract`` 仅允许写在 ``@protocol`` 内', '实体类静态方法无运行期虚派发'), method, module_path))

def _s19_unused_type_param_message(name: str) -> str:
    return _strict_msg(f'头上形参 `[{name}, …]`', '删除未用形参或写入注解/体', '函数 PEP 695 类型形参列表', example=f'删 `[{name}]`，或写 `def f[{name}: Bound](x: Foo[{name}], …)`；勿保留与实参无关的占位形参', reason=f'形参 `{name}` 未出现在注解、约束或函数体中')

def _check_s19_unused_pep695_type_params(tree: ast.Module, module_path: str, violations: list[_Violation]) -> None:
    """仅检查模块/类内 **函数** 的 PEP 695 头（``@protocol``/``@mixin`` 类形参另议）。"""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        declared = pep695_declared_type_params(node)
        if not declared:
            continue
        used = pep695_used_type_params(node, frozenset(declared))
        for name in declared:
            if name not in used:
                violations.append(_Violation(S19, _s19_unused_type_param_message(name), node, module_path))

class _StrictStyleChecker(ast.NodeVisitor):

    def __init__(self, tr: Translator, module_path: str, source_lines: list[str]):
        self.tr = tr
        self.module_path = module_path
        self.source_lines = source_lines
        self.violations: list[_Violation] = []
        self._dunder_method: str | None = None
        self._current_method: str | None = None
        self._class_stack: list[str] = []
        self._class_type_params: list[str] = []
        self._scope_type_params: set[str] = set()
        self._refcount_constrained_params: set[str] = set()
        self._kwargs_opts_ctor_ids: set[int] = set()
        self._context_stack: list[str] = []
        self._type_context_ann: ast.expr | None = None
        self._current_returns: ast.expr | None = None
        self._current_aug_op: str | None = None
        self._self_like_params: set[str] = {'self'}
        self._module_func_names: set[str] = set()
        self._class_methods: dict[str, set[str]] = {}
        self._in_async_def: bool = False
        self._current_func: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        self._current_func_sig: FunctionSig | MethodSig | None = None

    def _context_has(self, kind: str) -> bool:
        return kind in self._context_stack

    def _in_new_preferred_context(self) -> bool:
        return self._context_has('new_preferred') and (not self._context_has('call_arg'))

    def _in_self_literal_host_class(self) -> bool:
        return bool(self._class_stack) and self._class_stack[-1] in _SELF_LITERAL_HOST_CLASSES

    def _s06_construct_rule(self) -> str:
        if self._context_has('call_arg'):
            return S06E
        if self._context_has('aug_assign'):
            return S06C
        if self._context_has('binop'):
            return S06D
        return S06A

    def _s06_self_ann_rule(self) -> str:
        return S06B

    def _s06_scene(self) -> str:
        return _s06_scene_label(aug_op=self._current_aug_op, in_aug_assign=self._context_has('aug_assign'), in_binop=self._context_has('binop'), in_call_arg=self._context_has('call_arg'), in_new_preferred=self._in_new_preferred_context())

    def _host_empty_literal_hint(self) -> str | None:
        if not self._class_stack:
            return None
        return _SELF_LITERAL_HOST_HINTS.get(self._class_stack[-1])

    def _push(self, kind: str):
        self._context_stack.append(kind)

    def _pop(self):
        self._context_stack.pop()

    def _visit_in_context(self, kind: str, node: ast.AST | None):
        if node is None:
            return
        self._push(kind)
        self.visit(node)
        self._pop()

    def _line_disabled(self, node: ast.AST) -> bool:
        lineno = getattr(node, 'lineno', None)
        if not lineno or lineno <= 0 or lineno > len(self.source_lines):
            return False
        return bool(_STRICT_OFF_LINE.search(self.source_lines[lineno - 1]))

    def _add(self, rule: str, node: ast.AST, message: str) -> None:
        if self._line_disabled(node):
            return
        self.violations.append(_Violation(rule, message, node, self.module_path))

    def _check_s02_cpp_style_name(self, name: str, node: ast.AST) -> None:
        if _is_dunder(name):
            return
        if self._class_stack:
            allowed = _S02_CLASS_METHOD_ALLOW.get(self._class_stack[-1])
            if allowed is not None:
                key = name.lstrip('_') if name.lstrip('_') else name
                if name in allowed or key in allowed:
                    return
        msg = _s02_cpp_style_message(name)
        if msg is None:
            return
        self._add(S02, node, msg)

    def _check_s33_translator_only_member(self, name: str, node: ast.AST, *, kind: str) -> None:
        if not self._class_stack:
            return
        if _is_dunder(name):
            return
        if name not in _S33_RESERVED_MEMBER_NAMES:
            return
        class_name = self._class_stack[-1]
        self._add(S33, node, _s33_translator_only_member_message(name, class_name, kind=kind))

    def _check_s16_tuple_annotation(self, ann: ast.expr | None, node: ast.AST) -> None:
        sub = _ann_is_outermost_tuple_subscript(ann)
        if sub is None:
            return
        hint = _tuple_subscript_type_shorthand(sub)
        if hint is None:
            return
        self._add(S16, sub, _strict_msg('`tuple[…]`', hint, '最外层元组类型注解处', example=f'`x: {hint} = …` 勿 `x: tuple[…] = …`（内层 `list[tuple[K,V]]` 可保留）', reason='PEP 695 元组类型简写须用括号形式'))

    def _check_s15_annotation(self, ann: ast.expr | None, node: ast.AST) -> None:
        if not self._class_stack or ann is None:
            return
        class_name = self._class_stack[-1]
        if _is_desugar_generated_name(class_name):
            return
        info = self._current_class_info()
        if info is not None and info.is_serializable:
            return
        class_name = self._class_stack[-1]
        hit = _find_class_name_in_annotation(ann, class_name)
        if hit is None:
            return
        if _s15_allows_class_type_reference(hit, class_name, self._class_type_params):
            return
        self._add(S15, hit, _s15_same_class_message(class_name, scene='类型注解'))

    def _check_s15_same_class_expr(self, node: ast.Attribute) -> None:
        if not self._class_stack:
            return
        class_name = self._class_stack[-1]
        if _is_desugar_generated_name(class_name):
            return
        info = self._current_class_info()
        if info is not None and info.is_serializable:
            return
        class_name = self._class_stack[-1]
        if not isinstance(node.value, ast.Name) or node.value.id != class_name:
            return
        self._add(S15, node, _s15_same_class_message(class_name, scene='表达式', attr=node.attr))

    def _check_s06_prefer_new_staticproperty(self, node: ast.Attribute) -> None:
        if not isinstance(node.value, ast.Name) or node.value.id != 'Self':
            return
        info = self._current_class_info()
        if info is None or node.attr not in info.static_properties:
            return
        if _s06_exempt_new_receiver_class(info):
            return
        bad = f'Self.{node.attr}'
        self._add(S06B, node, _s06_msg_prefer(bad, f'new.{node.attr}', self._s06_scene(), example=f'`return new.{node.attr}` 勿 `{bad}`', reason='``@staticproperty`` 与静态工厂一致，同类内须 ``new.属性`` 勿 ``Self.属性``'))

    def visit_Attribute(self, node: ast.Attribute):
        self._check_s15_same_class_expr(node)
        self._check_s06_prefer_new_staticproperty(node)
        if _is_new_receiver_attribute(node) and (self._context_has('binop') or self._context_has('aug_assign')):
            self._add(S06D, node, _s06_msg_prefer(f'new.{node.attr}', f'Self(...) 或显式 Cls.{node.attr}', self._s06_scene(), example=f'`rotation * Vector3.{node.attr}`、`out += Self(x)` 勿 `rotation * new.{node.attr}`', reason=_s06_reason_no_new_in_expr()))
        self.generic_visit(node)

    def _visit_function_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for default in node.args.defaults:
            self._visit_in_context('new_preferred', default)
        for default in node.args.kw_defaults:
            if default is not None:
                self._visit_in_context('new_preferred', default)

    def visit_Module(self, node: ast.Module):
        self._module_func_names = {stmt.name for stmt in node.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if _is_desugar_generated_name(node.name):
            self._class_stack.append(node.name)
            self.generic_visit(node)
            self._class_stack.pop()
            return
        for tp in getattr(node, 'type_params', None) or ():
            if isinstance(tp, ast.TypeVar) and _is_short_class_type_param_name(tp.name):
                self._add(S48, tp, _s48_short_class_type_param_message(node.name, tp.name))
        info = self.tr.classes.get(node.name)
        prev_params = self._class_type_params
        prev_scope = set(self._scope_type_params)
        prev_rc = set(self._refcount_constrained_params)
        self._class_type_params = list(info.type_params) if info and info.type_params else _type_param_names(node)
        self._scope_type_params = set(self._class_type_params)
        if info:
            dec = getattr(info, 'type_param_decorator_constraints', {})
            self._refcount_constrained_params = {p for p, bounds in dec.items() if 'refcount' in bounds}
        else:
            self._refcount_constrained_params = set()
        self._class_stack.append(node.name)
        self._class_methods[node.name] = {stmt.name for stmt in node.body if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.generic_visit(node)
        self._class_methods.pop(node.name, None)
        self._class_stack.pop()
        self._class_type_params = prev_params
        self._scope_type_params = prev_scope
        self._refcount_constrained_params = prev_rc

    def _s31_exempt(self) -> bool:
        return _s31_module_exempt(self.module_path)

    def _check_s31_refcount_use(self, node: ast.AST, *, form: str, example: str) -> None:
        if self._s31_exempt():
            return
        self._add(S31, node, _strict_msg(form, 'T / new()', '源码', reason='``RefCount`` 为基础设施类型名，用户代码须写 ``@refcount`` 类名 ``T``（或 ``T: refcount`` 形参）；清空强引用用 ``x = new()``，勿 ``RefCount()``', example=example))

    def _check_s31_refcount_subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == 'RefCount':
            self._check_s31_refcount_use(node, form='RefCount[…]', example='got: n: Node = new()')

    def _check_s31_refcount_call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == 'RefCount':
            self._check_s31_refcount_use(node, form='RefCount(…)', example='got: n = new()')

    def _check_s03_thin_wrapper(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        class_methods: set[str] | None = None
        if self._class_stack:
            class_methods = self._class_methods.get(self._class_stack[-1])
        msg = _s03_try_thin_param_forward(node, class_methods=class_methods, module_funcs=self._module_func_names, self_like=self._self_like_params)
        if msg is not None:
            self._add(S03, node, msg)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_method = self._current_method
        prev_dunder = self._dunder_method
        prev_scope = set(self._scope_type_params)
        prev_rc = set(self._refcount_constrained_params)
        prev_self_like = self._self_like_params
        prev_async = self._in_async_def
        self._in_async_def = False
        self._self_like_params = _self_like_param_names(node)
        self._scope_type_params |= _type_param_names(node)
        for tp in getattr(node, 'type_params', None) or ():
            if isinstance(tp, ast.TypeVar) and tp.bound is not None:
                from ..analysis.ir import parse_typevar_protocol_bounds, split_typevar_bounds
                _proto, dec = split_typevar_bounds(parse_typevar_protocol_bounds(tp.bound))
                if 'refcount' in dec:
                    self._refcount_constrained_params.add(tp.name)
        self._current_method = node.name
        if _is_dunder(node.name):
            self._dunder_method = node.name
        else:
            self._check_s02_cpp_style_name(node.name, node)
            if self._class_stack:
                self._check_s33_translator_only_member(node.name, node, kind='方法')
        for dec in node.decorator_list:
            self.visit(dec)
        for arg in node.args.args:
            if arg.arg not in ('self', 'cls'):
                self._check_s15_annotation(arg.annotation, arg)
                self._check_s16_tuple_annotation(arg.annotation, arg)
        self._check_s15_annotation(node.returns, node)
        self._check_s16_tuple_annotation(node.returns, node)
        prev_returns = self._current_returns
        prev_func = self._current_func
        prev_func_sig = self._current_func_sig
        self._current_returns = node.returns
        self._current_func = node
        self._current_func_sig = _s22_sig_for_func_node(self, node)
        self._visit_function_defaults(node)
        self._check_s03_thin_wrapper(node)
        for stmt in node.body:
            self.visit(stmt)
        _s20_scan_function_body(self, node.body, func=node)
        self._current_returns = prev_returns
        self._current_func = prev_func
        self._current_func_sig = prev_func_sig
        self._current_method = prev_method
        self._dunder_method = prev_dunder
        self._scope_type_params = prev_scope
        self._refcount_constrained_params = prev_rc
        self._self_like_params = prev_self_like
        self._in_async_def = prev_async

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev_method = self._current_method
        prev_dunder = self._dunder_method
        prev_scope = set(self._scope_type_params)
        prev_rc = set(self._refcount_constrained_params)
        prev_self_like = self._self_like_params
        prev_async = self._in_async_def
        self._in_async_def = True
        self._self_like_params = _self_like_param_names(node)
        self._scope_type_params |= _type_param_names(node)
        for tp in getattr(node, 'type_params', None) or ():
            if isinstance(tp, ast.TypeVar) and tp.bound is not None:
                from ..analysis.ir import parse_typevar_protocol_bounds, split_typevar_bounds
                _proto, dec = split_typevar_bounds(parse_typevar_protocol_bounds(tp.bound))
                if 'refcount' in dec:
                    self._refcount_constrained_params.add(tp.name)
        self._current_method = node.name
        if _is_dunder(node.name):
            self._dunder_method = node.name
        else:
            self._check_s02_cpp_style_name(node.name, node)
            if self._class_stack:
                self._check_s33_translator_only_member(node.name, node, kind='方法')
        for dec in node.decorator_list:
            self.visit(dec)
        for arg in node.args.args:
            if arg.arg not in ('self', 'cls'):
                self._check_s15_annotation(arg.annotation, arg)
                self._check_s16_tuple_annotation(arg.annotation, arg)
        self._check_s15_annotation(node.returns, node)
        self._check_s16_tuple_annotation(node.returns, node)
        prev_returns = self._current_returns
        prev_func = self._current_func
        prev_func_sig = self._current_func_sig
        self._current_returns = node.returns
        self._current_func = node
        self._current_func_sig = _s22_sig_for_func_node(self, node)
        self._visit_function_defaults(node)
        self._check_s03_thin_wrapper(node)
        for stmt in node.body:
            self.visit(stmt)
        _s20_scan_function_body(self, node.body, func=node)
        self._current_returns = prev_returns
        self._current_func = prev_func
        self._current_func_sig = prev_func_sig
        self._current_method = prev_method
        self._dunder_method = prev_dunder
        self._scope_type_params = prev_scope
        self._refcount_constrained_params = prev_rc
        self._self_like_params = prev_self_like
        self._in_async_def = prev_async

    def visit_TypeAlias(self, node: ast.TypeAlias):
        prev_scope = set(self._scope_type_params)
        self._scope_type_params |= _type_param_names(node)
        if self._class_stack and self._class_type_params:
            if isinstance(node.value, ast.Name) and node.value.id in self._class_type_params:
                info = self._current_class_info()
                cls = info.name if info else self._class_stack[-1]
                if node.name != node.value.id:
                    hint = f'class {cls}[{node.name}]'
                else:
                    hint = f'class {cls}[{node.name}]（勿写 ``type {node.name} = {node.name}``）'
                self._add(S43, node, f'类形参 ``{node.value.id}`` 已自动生成 ``using {node.name} = _{node.name}``；勿手写 ``type {node.name} = {node.value.id}``，请改为 {hint}')
        self._check_s15_annotation(node.value, node)
        self._check_s16_tuple_annotation(node.value, node)
        self.generic_visit(node)
        self._scope_type_params = prev_scope

    def _note_kwargs_opts_ctor(self, node: ast.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return
        if not node.targets[0].id.startswith('_opts'):
            return
        if isinstance(node.value, ast.Call):
            self._kwargs_opts_ctor_ids.add(id(node.value))

    def _current_class_info(self) -> ClassInfo | None:
        if not self._class_stack:
            return None
        return self.tr.classes.get(self._class_stack[-1])

    def _module_has_coroutine_class(self, func_name: str) -> bool:
        tree = self.tr.module_asts.get(self.module_path)
        if tree is None:
            return False
        target = f'{func_name}_coroutine'
        return any((isinstance(node, ast.ClassDef) and node.name == target for node in tree.body))

    def _s01_allows_dunder_call(self, dunder: str) -> bool:
        if dunder in _S01_GLOBAL_DUNDERS:
            return True
        if self._dunder_method == '__copy__' and dunder == '__copy__':
            return True
        if self._dunder_method == '__move__' and dunder == '__move__':
            return True
        if self._s06_in_desugar_host():
            return True
        if dunder in _DESUGAR_PROTO_DUNDERS:
            if self._class_stack and _is_desugar_generated_name(self._class_stack[-1]):
                return True
        info = self._current_class_info()
        if info is None:
            return False
        if dunder == '__move__':
            return info.is_copyable or info.is_uncopyable
        if dunder == '__copy__':
            return not info.is_copyable
        return False

    def _s06_cls_call_in_new_context(self, node: ast.Call, info: ClassInfo) -> bool:
        name = _call_target_name(node.func)
        if name == 'Self':
            return False
        if node.keywords:
            return True
        if not node.args:
            if info.module_path != self.module_path:
                return False
            return True
        ann_cls = _ann_root_name(self._type_context_ann)
        return ann_cls == info.name

    def _s06_explicit_ctor_example(self, node: ast.Call, info: ClassInfo) -> str:
        sub = '[T]' if isinstance(node.func, ast.Subscript) else ''
        if len(node.args) == 1 and isinstance(node.args[0], ast.Name):
            a = node.args[0].id
            return f'`return new({a})` 勿 `return {info.name}{sub}({a})`'
        if len(node.args) == 2 and all((isinstance(a, ast.Name) for a in node.args)):
            a0, a1 = (node.args[0].id, node.args[1].id)
            return f'`return new({a0}, {a1})` 勿 `return {info.name}{sub}({a0}, {a1})`'
        return f'`return new(...)` 勿 `{info.name}{sub}(...)`'

    def _check_s06_prefer_new_receiver_static(self, node: ast.Call) -> None:
        if self._context_has('binop') or self._context_has('aug_assign'):
            return
        if not self._in_new_preferred_context() or self._type_context_ann is None:
            return
        from ..emit.call_emit import static_method_call_type_receiver
        from .union_expand import union_accepts_case_union, union_variant_names
        recv = static_method_call_type_receiver(node.func)
        if recv is None:
            return
        type_expr, method = recv
        ann = self._type_context_ann
        ann_text = ast.unparse(ann)
        if isinstance(type_expr, ast.Name) and type_expr.id == 'Self' and _ann_is_self(ann):
            info = self._current_class_info()
            if info is not None:
                sig = info.method_sigs.get(method)
                if sig is not None and sig.is_static and (not _s06_exempt_new_receiver_class(info)):
                    bad = f'Self.{method}(...)'
                    self._add(S06B, node, _s06_msg_prefer(bad, f'new.{method}(...)', self._s06_scene(), example=f'`x: Self = new.{method}(...)` 勿 `{bad}`', reason='注解/返回为 `Self` 时静态工厂须 `new.方法` 勿 `Self.方法`'))
            return
        ann_info = _ann_union_info(self.tr, ann)
        if ann_info is not None:
            if isinstance(type_expr, ast.Name):
                union_name = type_expr.id
                if union_accepts_case_union(ann_info, union_name) and method in union_variant_names(ann_info):
                    bad = f'{union_name}.{method}(...)'
                    self._add(S06B, node, _s06_msg_prefer(bad, f'new.{method}(...)', self._s06_scene(), example=f'`x: {ann_text} = new.{method}(...)` 勿 `{bad}`', reason='注解已给出 @union 类型，变体构造须 `new.变体` 勿显式 `Union.变体`'))
                    return
            elif isinstance(type_expr, ast.Subscript) and _expr_same(ann, type_expr):
                if method in union_variant_names(ann_info):
                    bad = f'{ast.unparse(type_expr)}.{method}(...)'
                    self._add(S06B, node, _s06_msg_prefer(bad, f'new.{method}(...)', self._s06_scene(), example=f'`x: {ann_text} = new.{method}(...)` 勿 `{bad}`', reason='注解已给出 @union 类型，变体构造须 `new.变体` 勿显式 `Union.变体`'))
                    return
        if isinstance(type_expr, ast.Subscript):
            if not _expr_same(ann, type_expr):
                return
        elif isinstance(type_expr, ast.Name):
            if not _expr_same(ann, type_expr):
                return
            info = _static_method_on_class(self.tr, type_expr, method)
            if info is None or info.type_params or _s06_exempt_new_receiver_class(info):
                return
        else:
            return
        if _static_method_on_class(self.tr, type_expr, method) is None:
            return
        bad = f'{ast.unparse(type_expr)}.{method}(...)'
        self._add(S06B, node, _s06_msg_prefer(bad, f'new.{method}(...)', self._s06_scene(), example=f'`x: {ann_text} = new.{method}(...)` 勿 `{bad}`', reason='注解已给出目标类，静态工厂/方法须 `new.方法` 勿显式 `Cls.方法`/`Cls[T].方法`/`Self.方法`'))

    def _check_s06_prefer_new_union_match(self, node: ast.Match) -> None:
        from .union_expand import union_accepts_case_union, union_variant_names
        subject_union = _match_subject_union_info(self, node)
        if subject_union is None:
            subject_union = _s24_union_info_for_match(self, node)
        if subject_union is None:
            return
        for case in node.cases:
            if is_wildcard_pattern(case.pattern):
                continue
            for branch_pat in _s23_union_branch_patterns(case.pattern):
                if not _s23_union_case_uses_explicit_union_syntax(branch_pat):
                    continue
                ref = _s23_union_case_ref(branch_pat)
                if ref is None:
                    continue
                union_name, variant = ref
                if not union_accepts_case_union(subject_union, union_name):
                    continue
                if variant not in union_variant_names(subject_union):
                    continue
                bad = f'{union_name}.{variant}'
                self._add(S06B, case, _s06_msg_prefer(bad, f'new.{variant}', 'match @union', example=f'`case new.{variant}:` / `case new.{variant}(...):` 勿 `case {bad}:`', reason='match 主体已是 @union，case 须 `new.变体` 勿显式 `Union.变体`'))

    def _s06_in_desugar_host(self) -> bool:
        if not self._class_stack:
            return False
        return _is_desugar_generated_name(self._class_stack[-1])

    def _s06_call_exempt(self, node: ast.Call) -> bool:
        if self._s06_in_desugar_host():
            return True
        name = _call_target_name(node.func)
        return _is_desugar_generated_name(name)

    def _check_s06_new_str_bytes_literal(self, node: ast.Call) -> bool:
        if not _is_new_call(node) or node.keywords:
            return False
        ann = self._type_context_ann
        if len(node.args) == 1 and isinstance(node.args[0], ast.Constant):
            val = node.args[0].value
            if isinstance(val, str) and _ann_root_name(ann) == 'str':
                self._add(S06A, node, _s06_priority_message('""', scene=self._s06_scene(), example='`s: str = "hi"` 勿 `s: str = new("hi")`'))
                return True
            if isinstance(val, bytes) and _ann_root_name(ann) == 'bytes':
                self._add(S06A, node, _s06_priority_message('b""', scene=self._s06_scene(), example='`b: bytes = b"\\x00"` 勿 `b: bytes = new(b"\\x00")`'))
                return True
        return False

    def _check_s06_construct_priority(self, node: ast.Call) -> None:
        if not self._in_new_preferred_context():
            return
        if self._check_s06_new_str_bytes_literal(node):
            return
        ann = self._type_context_ann
        if _is_new_call(node) and (not node.args) and (not node.keywords):
            ann_root = _ann_root_name(ann)
            if ann_root in _NO_EMPTY_MAKE_ANN_ROOTS:
                self._add(S06A, node, _s06_no_empty_new_message(ann_root))
                return
        hint = _s06_preferred_init_hint(ann)
        func_name = _call_target_name(node.func)
        host_hint: str | None = None
        if _ann_is_self(ann) and self._in_self_literal_host_class():
            host_hint = self._host_empty_literal_hint()
        if host_hint is not None:
            host = self._class_stack[-1] if self._class_stack else '宿主类'
            if _is_new_call(node) and (not node.args) and (not node.keywords):
                if host_hint != 'new()':
                    self._add(S06A, node, _s06_priority_message(host_hint, scene=f'`{host}` 类内 `-> Self` 的{self._s06_scene()}', example=f'`return {host_hint}` 或 `out: Self = {host_hint}` 勿 `new()`'))
                return
            if func_name == 'Self' and (not node.args) and (not node.keywords):
                self._add(S06A, node, _s06_priority_message(host_hint, scene=f'`{host}` 类内 `-> Self` 的{self._s06_scene()}', example=f'`return {host_hint}` 勿 `return Self()`'))
                return
        if func_name in _EMPTY_SET_FACTORIES and (not node.args) and (not node.keywords):
            self._add(S06A, node, _strict_msg('`set()` / `frozenset()`', 'new()', self._s06_scene(), example='`s: set[int] = new()` 勿 `s = set()`', reason='空集合无 `{}` 字面量，须靠类型上下文 `new()`'))
            return
        if hint == 'new()':
            if _is_new_call(node) and (not node.args) and (not node.keywords):
                return
            if func_name == 'Self' and (not node.args) and (not node.keywords) and (not _ann_is_self(ann)):
                self._add(S06A, node, _strict_msg('Self()', 'new()', self._s06_scene(), example='`fs: frozenset[T] = new()` 勿 `fs = Self()`', reason='空 set/frozenset 无字面量捷径'))
            return
        if _is_new_call(node) and (not node.args) and (not node.keywords):
            if hint is not None:
                self._add(S06A, node, _s06_priority_message(hint, scene=self._s06_scene()))
                return
        if func_name == 'Self' and (not node.args) and (not node.keywords) and (not _ann_is_self(ann)):
            if hint is not None:
                self._add(S06A, node, _s06_priority_message(hint, scene=self._s06_scene()))
            else:
                self._add(S06A, node, _s06_msg_prefer('Self()', 'new() 或容器/str 字面量', self._s06_scene(), example='`return new()`、`scratch: list[T] = []`', reason='无更具体的类型字面量捷径'))
            return
        if func_name == 'Self' and (not node.args) and (not node.keywords) and _ann_is_self(ann) and (not self._in_self_literal_host_class()):
            self._add(S06B, node, _s06_msg_prefer('Self()', 'new()', self._s06_scene(), example='`return new()` 或 `z: Self = new()`（mixin/泛型类无 `[]`/`""` 宿主）', reason='注解为 `Self` 且非 str/bytes/list 等具体宿主类'))
            return
        if func_name == 'Self' and _ann_is_self(ann) and (node.args or node.keywords) and (not self._context_has('aug_assign')) and (not self._context_has('binop')):
            self._add(S06B, node, _s06_msg_prefer('Self(...)', 'new(...)', self._s06_scene(), example='`return new(buf)`、`out: Self = new(x)` 勿 `return Self(x)`', reason='左侧/返回注解为 `Self` 时有类型上下文，`new` 优先'))

    def visit_BinOp(self, node: ast.BinOp):
        self._visit_in_context('binop', node.left)
        self._visit_in_context('binop', node.right)

    def visit_Constant(self, node: ast.Constant):
        if self._in_new_preferred_context() and _ann_is_self(self._type_context_ann) and (not self._in_self_literal_host_class()) and (node.value == '' or node.value == b''):
            self._add(S06B, node, _s06_msg_prefer('""` / `b""`', 'new()', self._s06_scene(), example='`return new()`（`StringMixin` 等）；`str`/`bytes` 类内仍写 `return ""`', reason='注解为 `Self` 且当前类非 str/bytes 具体宿主'))

    def visit_Call(self, node: ast.Call):
        _s25_check_optional_variant_ctor(self, node)
        if isinstance(node.func, ast.Name) and node.func.id == 'ord':
            if not _s20_is_ord_single_char(node):
                try:
                    bad = ast.unparse(node)
                except Exception:
                    bad = 'ord(...)'
                self._add(S34, node, _s34_ord_non_literal_msg(bad))
        s13 = _s13_try_range_redundant_form(node)
        if s13 is not None:
            self._add(S13, node, s13)
        if isinstance(node.func, ast.Name) and node.func.id in ('__cmp__', '__mod__', '__truediv__', '__floordiv__'):
            pass
        elif isinstance(node.func, ast.Attribute) and _is_dunder(node.func.attr):
            from ..analysis.proxy import is_s01_init_forward_call, is_super_dunder_call
            in_init = self._current_method == '__init__' and bool(self._class_stack)
            if not is_super_dunder_call(node) and (not is_s01_init_forward_call(node, in_class_init=in_init)) and (not self._s01_allows_dunder_call(node.func.attr)):
                self._add('S01', node, _s01_dunder_call_message(node.func.attr))
        if isinstance(node.func, ast.Subscript) and isinstance(node.func.value, ast.Name) and (node.func.value.id in _DEDUCED_MEMORY_FUNCS):
            fn = node.func.value.id
            self._add(S07, node, _strict_msg(f'`{fn}[T](…)`', f'`{fn}(…)`', '内存/指针辅助调用处', example=f'`destroy(ptr)`、`freeArray(arr)` 勿 `{fn}[T](ptr)`', reason='C++ 侧从指针/实参推导模板实参'))
        func_name = _call_target_name(node.func)
        if func_name in _EMPTY_CONTAINER_FACTORIES and (not node.args) and (not node.keywords):
            self._add(S04, node, _s04_empty_factory_message(func_name))
        if func_name == 'str' and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                val = arg.value
                self._add(S05, node, _strict_msg(f"`str('{val}')`", f"`'{val}'`", '字符串初始化/表达式处', example=f"`msg: str = '{val}'` 勿 `msg = str('{val}')`", reason='字面量可直接译为 C++ 字符串'))
        if _is_new_call(node) and self._context_has('call_arg'):
            self._add(S06E, node, _s06_msg_prefer('new(...)', 'Cls(...) 或字面量', _s06_scene_label(in_call_arg=True), example='`self.split(Self(), sep)`、`fn([])`；勿 `fn(new())`', reason='仅赋值处单个 new 调用可用 new，调用实参处不规范'))
        if _is_new_call(node) and (self._context_has('aug_assign') or self._context_has('binop')):
            scene = self._s06_scene()
            if self._context_has('binop'):
                example = '`return out + Self(ch)`、`rotation * Vector3.right` 勿 `return out + new(ch)`'
            else:
                example = '`out += Self(ch)` 勿 `out += new(ch)`'
            self._add(self._s06_construct_rule(), node, _s06_msg_prefer('new(...)', 'Self(...) 或显式 `Cls(...)` / `Cls.静态成员`', scene, example=example, reason=_s06_reason_no_new_in_expr()))
        if isinstance(node.func, ast.Attribute) and _is_new_receiver_attribute(node.func) and (self._context_has('aug_assign') or self._context_has('binop')):
            attr = node.func.attr
            self._add(S06D, node, _s06_msg_prefer(f'new.{attr}(...)', f'Self.{attr}(...) 或显式 Cls.{attr}(...)', self._s06_scene(), example=f'`varint._one() + varint._one()`、`rotation * Vector3.right` 勿 `new.{attr}() + new.{attr}()`', reason=_s06_reason_no_new_in_expr()))
        self._check_s06_construct_priority(node)
        self._check_s06_prefer_new_receiver_static(node)
        if isinstance(node.func, ast.Subscript) and isinstance(node.func.value, ast.Name) and (node.func.value.id == 'cast') and self._in_new_preferred_context() and (self._type_context_ann is not None) and node.args:
            cast_ty = node.func.slice
            ctx_ty = strip_type_annotation_markers(self._type_context_ann)
            if _expr_same(cast_ty, ctx_ty):
                bad = f'cast[{ast.unparse(cast_ty)}](...)'
                self._add(S40, node, _strict_msg(bad, 'cast(...)', self._s06_scene(), example=f'`x: {ast.unparse(ctx_ty)} = cast(obj)` 勿 `{bad}`', reason='赋值/返回注解已给出目标类型，须 `cast(obj)` 简写'))
        info = _class_info_for_ctor(self.tr, node.func)
        if info is not None and info.name != 'varint' and (not self._s06_call_exempt(node)) and self._in_new_preferred_context() and self._s06_cls_call_in_new_context(node, info) and (self._dunder_method not in ('__copy__', '__move__')) and (id(node) not in self._kwargs_opts_ctor_ids) and (not self._context_has('binop')) and (not self._context_has('aug_assign')):
            ann_cls = _ann_root_name(self._type_context_ann)
            if ann_cls == info.name and node.args and (not node.keywords):
                bad = f'{info.name}[T](...)' if isinstance(node.func, ast.Subscript) else f'{info.name}(...)'
                self._add(S06B, node, _s06_msg_prefer(bad, 'new(...)', self._s06_scene(), example=self._s06_explicit_ctor_example(node, info), reason='返回/赋值注解已给出目标类，须 `new` 勿显式 `Cls`/`Cls[T]` 构造'))
            else:
                self._add(S06A, node, _s06_msg_prefer(f'{info.name}(...)', 'new(...)', self._s06_scene(), example=f'`x: {info.name} = new(field=v)` 勿 `{info.name}(field=v)`', reason='初始化/返回有类型注解时 `new` 优先于显式类名构造'))
        deleg = _delegate_info_for_ctor(self.tr, node.func)
        if deleg is not None and (not self._s06_call_exempt(node)) and self._in_new_preferred_context() and (not node.args) and (not node.keywords) and (self._dunder_method not in ('__copy__', '__move__')):
            bad = _delegate_ctor_display(node.func)
            ann_text = ast.unparse(self._type_context_ann) if self._type_context_ann is not None else deleg.name
            self._add(S06A, node, _s06_msg_prefer(bad, 'new(...)', self._s06_scene(), example=f'`d: {ann_text} = new()` 勿 `{bad}`', reason='`@delegate` 空实例须 `new`，勿显式委托类型构造'))
        self.visit(node.func)
        for arg in node.args:
            self._visit_in_context('call_arg', arg)
        for kw in node.keywords:
            self._visit_in_context('call_arg', kw.value)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if self._class_stack and self._current_method is None:
            field = _field_name_from_ann_target(node.target)
            if field:
                self._check_s33_translator_only_member(field, node, kind='字段')
        if self._current_method is not None and self._current_method != '__init__' and _is_self_field_ann_assign(node.target) and (not self._s06_in_desugar_host()):
            field = _field_name_from_ann_target(node.target) or 'field'
            self._add(S14, node, _strict_msg(f'`self.{field}: T = …`', f'`self.{field} = …`', f'非 `__init__` 方法 `{self._current_method}` 内', example=f'类体或 `__init__` 写 `{field}: T`；方法内写 `self.{field} = v`', reason='实例字段类型注解仅允许在类体或 `__init__`'))
        self._check_s15_annotation(node.annotation, node)
        self._check_s16_tuple_annotation(node.annotation, node)
        _s35_check_primitive_convert_temp(self, node)
        _s46_check_new_type_context_temp(self, node)
        prev_ann = self._type_context_ann
        self._type_context_ann = node.annotation
        self._visit_in_context('new_preferred', node.value)
        self._type_context_ann = prev_ann

    def visit_Assign(self, node: ast.Assign):
        self._note_kwargs_opts_ctor(node)
        if isinstance(node.value, ast.BinOp) and type(node.value.op) in _AUG_BINOPS:
            for target in node.targets:
                if _expr_same(target, node.value.left):
                    self._add(S11, node, _s11_binop_assign_message(node))
                    break
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
            _s36_check_tuple_unpack(self, node)
        if not self._context_has('call_arg'):
            prev_ann = self._type_context_ann
            field_ann: ast.expr | None = None
            if len(node.targets) == 1 and (not self._s06_in_desugar_host()):
                field_ann = _field_annotation_for_assign_target(self, node.targets[0])
            if field_ann is not None:
                self._type_context_ann = field_ann
                self._visit_in_context('new_preferred', node.value)
                self._type_context_ann = prev_ann
            else:
                self._visit_in_context('new_preferred', node.value)
        else:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        prev_aug = self._current_aug_op
        self._current_aug_op = _aug_op_text(node.op)
        self.visit(node.target)
        self._visit_in_context('aug_assign', node.value)
        self._current_aug_op = prev_aug

    def visit_Return(self, node: ast.Return):
        prev_ann = self._type_context_ann
        self._type_context_ann = self._current_returns
        self._visit_in_context('new_preferred', node.value)
        self._type_context_ann = prev_ann

    def visit_Expr(self, node: ast.Expr):
        if not self._context_has('call_arg'):
            self._visit_in_context('new_preferred', node.value)
        else:
            self.visit(node.value)

    def _visit_comprehension_body(self, node: ast.ListComp | ast.SetComp | ast.DictComp) -> None:
        for gen in node.generators:
            self.visit(gen.target)
            self.visit(gen.iter)
            for if_clause in gen.ifs:
                self.visit(if_clause)
        if isinstance(node, ast.DictComp):
            self._visit_in_context('new_preferred', node.key)
            self._visit_in_context('new_preferred', node.value)
        else:
            self._visit_in_context('new_preferred', node.elt)

    def visit_ListComp(self, node: ast.ListComp):
        if self._in_new_preferred_context():
            self._visit_comprehension_body(node)
        else:
            self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp):
        if self._in_new_preferred_context():
            self._visit_comprehension_body(node)
        else:
            self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp):
        if self._in_new_preferred_context():
            self._visit_comprehension_body(node)
        else:
            self.generic_visit(node)

    def visit_List(self, node: ast.List):
        if self._context_has('call_arg'):
            for elt in node.elts:
                self._visit_in_context('call_arg', elt)
        elif self._in_new_preferred_context():
            for elt in node.elts:
                self._visit_in_context('new_preferred', elt)
        else:
            for elt in node.elts:
                self.visit(elt)

    def visit_Tuple(self, node: ast.Tuple):
        if self._context_has('call_arg'):
            for elt in node.elts:
                self._visit_in_context('call_arg', elt)
        else:
            for elt in node.elts:
                self.visit(elt)

    def visit_Dict(self, node: ast.Dict):
        if self._context_has('call_arg'):
            for key in node.keys:
                if key is not None:
                    self._visit_in_context('call_arg', key)
            for val in node.values:
                self._visit_in_context('call_arg', val)
        elif self._in_new_preferred_context():
            for key in node.keys:
                if key is not None:
                    self._visit_in_context('new_preferred', key)
            for val in node.values:
                self._visit_in_context('new_preferred', val)
        else:
            for key in node.keys:
                if key is not None:
                    self.visit(key)
            for val in node.values:
                self.visit(val)

    def visit_Set(self, node: ast.Set):
        if self._context_has('call_arg'):
            for elt in node.elts:
                self._visit_in_context('call_arg', elt)
        elif self._in_new_preferred_context():
            for elt in node.elts:
                self._visit_in_context('new_preferred', elt)
        else:
            for elt in node.elts:
                self.visit(elt)

    def visit_For(self, node: ast.For):
        if not (self._class_stack and _is_desugar_generated_name(self._class_stack[-1])) and isinstance(self._current_func, ast.FunctionDef):
            _s38_record_for_violation(self.violations, self.module_path, node, in_async=self._in_async_def)
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        msg = _s12_try_index_while_range(node)
        if msg is not None:
            self._add(S12, node, msg)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        _s21_check_compare_chain(self, node)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match):
        _s23_check_match_default_case(self, node)
        _s25_check_optional_match_patterns(self, node)
        _s24_check_union_case_order(self, node)
        self._check_s06_prefer_new_union_match(node)
        self._push('match')
        self.visit(node.subject)
        for case in node.cases:
            self.visit(case)
        self._pop()

    def visit_match_case(self, node: ast.match_case):
        self.visit(node.pattern)
        if node.guard is not None:
            self._push('match_guard')
            self.visit(node.guard)
            self._pop()
        for stmt in node.body:
            self.visit(stmt)

    def visit_Compare(self, node: ast.Compare):
        _s22_check_char_literal_compare(self, node)
        _s25_check_optional_identity_compare(self, node)
        if _s08_is_len_zero_compare(node) and self._current_method != '__bool__':
            self._add(S08, node, _s08_len_zero_suggestion(node))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        if _slice_has_zero_lower(node.slice):
            self._add(S09, node, _s09_zero_slice_message(node))
        k: int | None = _s10_is_len_minus_k_subscript(node)
        if k is not None and isinstance(node.value, ast.Name):
            self._add(S10, node, _s10_len_minus_k_subscript_suggestion(node.value.id, k))
        self.generic_visit(node)
