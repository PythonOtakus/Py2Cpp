"""移动后使用：翻译期数据流检查（``dst = src`` 移动语义）。"""
from __future__ import annotations
import ast
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_container_type
from ..analysis.ir import CPP_DEQUE_PREFIX, CPP_DICT_PREFIX, CPP_FROZENSET_PREFIX, CPP_LIST_PREFIX, CPP_SET_PREFIX, ClassInfo, FuncTypeParams, strip_cpp_type_qualifiers
from ..constant.stdlib_layout import RUNTIME_PKG
if TYPE_CHECKING:
    from ..translator import Translator
_MOVE_CONTAINER_NAMES = frozenset({'list', 'dict', 'set', 'frozenset', 'deque'})

def check_moved_use(tr: Translator) -> None:
    """对用户模块中每个函数/方法做直线+分支合并的 moved 活跃性检查。"""
    for module_path, tree in tr.module_asts.items():
        if tr._is_stdlib_module(module_path):
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                _FunctionMovedChecker(tr, module_path).visit(node)
        for info in tr.classes.values():
            if info.module_path != module_path or tr._is_stdlib_module(info.module_path):
                continue
            for method in list(info.methods.values()) + list(info.inits):
                _FunctionMovedChecker(tr, module_path, class_info=info).visit(method)

def _builtin_class_info(tr: Translator, py_name: str) -> ClassInfo | None:
    for info in tr.classes.values():
        if info.name == py_name and info.module_path.startswith(f'{RUNTIME_PKG}/'):
            return info
    return None
_CONTAINER_PREFIX_TO_PY: tuple[tuple[str, str], ...] = ((CPP_LIST_PREFIX, 'list'), (CPP_DICT_PREFIX, 'dict'), (CPP_SET_PREFIX, 'set'), (CPP_FROZENSET_PREFIX, 'frozenset'), (CPP_DEQUE_PREFIX, 'deque'))

def _class_info_from_cpp_type(tr: Translator, cpp_type: str) -> ClassInfo | None:
    if not is_container_type(cpp_type):
        return None
    base = strip_cpp_type_qualifiers(cpp_type)
    for prefix, py_name in _CONTAINER_PREFIX_TO_PY:
        if base.startswith(prefix):
            return _builtin_class_info(tr, py_name)
    return None

def _class_info_from_annotation(tr: Translator, ann: ast.expr | None, tparams: list[str], *, typevar_tuple_names: frozenset[str] | None=None) -> ClassInfo | None:
    if ann is None or tr.type_parser is None:
        return None
    cpp = tr.type_parser.parse_type(ann, set(tparams), typevar_tuple_names=typevar_tuple_names)
    return _class_info_from_cpp_type(tr, cpp)

def _is_move_container(info: ClassInfo | None) -> bool:
    if info is None:
        return False
    return info.name in _MOVE_CONTAINER_NAMES and info.has_move and (not info.is_refcount)

class _FunctionMovedChecker(ast.NodeVisitor):

    def __init__(self, tr: Translator, module_path: str, *, class_info: ClassInfo | None=None):
        self.tr = tr
        self.module_path = module_path
        self.class_info = class_info
        self.func_ft = FuncTypeParams([], None, {}, {})
        self._current_func: ast.FunctionDef | None = None
        self.var_types: dict[str, str] = {}
        self.param_types: dict[str, str] = {}
        self.moved: set[str] = set()
        self._allow_moved_attr = False

    def _active_tparams(self) -> list[str]:
        if self.class_info and self.class_info.type_params:
            out = list(self.class_info.type_params)
        else:
            out = list(self.func_ft.template_names)
        if self.func_ft.typevar_tuple and self.func_ft.typevar_tuple not in out:
            out.append(self.func_ft.typevar_tuple)
        return out

    def _active_typevar_tuple_names(self) -> frozenset[str]:
        names: set[str] = set()
        if self.func_ft.typevar_tuple:
            names.add(self.func_ft.typevar_tuple)
        if self.class_info and self.class_info.typevar_tuple:
            names.add(self.class_info.typevar_tuple)
        if self._current_func is not None:
            from ..analysis.variadic_template import resolve_variadic_template
            ctp = list(self.class_info.type_params) if self.class_info else None
            vt = resolve_variadic_template(self._current_func, class_type_params=ctp, class_typevar_tuple=self.class_info.typevar_tuple if self.class_info else None)
            if vt is not None:
                names.add(vt.pack_name)
        return frozenset(names)

    def _class_info_for_var(self, name: str) -> ClassInfo | None:
        t = self.var_types.get(name) or self.param_types.get(name, '')
        if not t and self.tr.type_parser:
            return None
        return _class_info_from_cpp_type(self.tr, t)

    def _is_move_name_assign(self, target: ast.Name, rhs: ast.Name, target_ann: ast.expr | None=None) -> bool:
        target_info = self._class_info_for_var(target.id)
        if target_info is None and target_ann is not None:
            target_info = _class_info_from_annotation(self.tr, target_ann, self._active_tparams(), typevar_tuple_names=self._active_typevar_tuple_names())
        rhs_info = self._class_info_for_var(rhs.id)
        if not _is_move_container(target_info) or not _is_move_container(rhs_info):
            return False
        return target_info.name == rhs_info.name

    def _error(self, name: str, node: ast.AST) -> None:
        lineno = getattr(node, 'lineno', 0)
        raise ValueError(f'{self.module_path}:{lineno}: 变量 `{name}` 已在移动赋值中交出所有权，不能再使用（可读取 `{name}.__moved__` 或重新赋值）')

    def _check_name_load(self, name: str, node: ast.AST) -> None:
        if self._allow_moved_attr:
            return
        if name in self.moved:
            self._error(name, node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._current_func = node
        self.func_ft = FuncTypeParams.collect(node)
        self.var_types = {}
        self.param_types = {}
        self.moved = set()
        if self.tr.sigs and self.class_info:
            msig = self.class_info.method_sigs.get(node.name)
            if msig:
                from ..analysis.type_emit import method_param_types_map
                self.param_types = dict(method_param_types_map(msig))
        elif self.tr.function_sigs:
            fsig = self.tr.function_sigs.get((self.module_path, node.name))
            if fsig:
                from ..analysis.type_emit import method_param_types_map
                self.param_types = dict(method_param_types_map(fsig))
        for arg in node.args.args:
            if arg.arg in ('self', 'cls'):
                continue
            if arg.annotation and self.tr.type_parser:
                self.param_types[arg.arg] = self.tr.type_parser.parse_type(arg.annotation, set(self._active_tparams()), typevar_tuple_names=self._active_typevar_tuple_names())
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value is not None and isinstance(node.target, ast.Name) and isinstance(node.value, ast.Name) and self._is_move_name_assign(node.target, node.value, node.annotation):
            self.visit(node.value)
            if self.tr.type_parser and node.annotation:
                self.var_types[node.target.id] = self.tr.type_parser.parse_type(node.annotation, set(self._active_tparams()), typevar_tuple_names=self._active_typevar_tuple_names())
            self.moved.add(node.value.id)
            return
        if isinstance(node.target, ast.Name):
            self.moved.discard(node.target.id)
            if node.annotation and self.tr.type_parser:
                self.var_types[node.target.id] = self.tr.type_parser.parse_type(node.annotation, set(self._active_tparams()), typevar_tuple_names=self._active_typevar_tuple_names())
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        move_rhs: str | None = None
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Name) and self._is_move_name_assign(target, node.value):
                move_rhs = node.value.id
        if move_rhs is not None:
            self.visit(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.moved.discard(target.id)
            self.moved.add(move_rhs)
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.moved.discard(target.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr == '__moved__':
            prev = self._allow_moved_attr
            self._allow_moved_attr = True
            self.visit(node.value)
            self._allow_moved_attr = prev
            return
        if isinstance(node.value, ast.Name):
            self._check_name_load(node.value.id, node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self._check_name_load(node.id, node)

    def visit_If(self, node: ast.If):
        self.visit(node.test)
        before = set(self.moved)
        for stmt in node.body:
            self.visit(stmt)
        after_body = set(self.moved)
        self.moved = before
        for stmt in node.orelse:
            self.visit(stmt)
        after_orelse = set(self.moved)
        self.moved = before | after_body | after_orelse

    def visit_For(self, node: ast.For):
        self.visit(node.target)
        self.visit(node.iter)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_While(self, node: ast.While):
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
