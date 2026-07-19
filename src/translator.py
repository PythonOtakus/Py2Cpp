"""Python 源码 → C++11 翻译器。

架构概览
--------
1. **解析**：``ast.parse`` 收集模块、类（``ClassInfo``）、函数。
2. **预处理**：``SemanticAnalyzer`` 解析类型与签名（见 ``analyzer``、``ir``）。
3. **生成**：``Translator``（``ast.NodeVisitor``）输出 ``.h`` / ``.cpp`` / ``.inl``。

约定摘要
--------
- 运行时标准库在仓库根 ``py2cpp/*.py`` 用 Python 描述，与用户代码一同翻译；不依赖 STL。
- ``__next__``：Python 仍写 ``raise StopIteration`` / ``return value``，C++ 侧为 ``PyIterResult<Y,R>``。
- ``@refcount``：``A(...)`` → ``RefCount<A>(...)``（类型见 ``refcount.py``，装饰器见 ``py2cpp/__init__.py``）。
- ``@boxing``：``A(...)`` / ``A[T](...)`` → ``new A<...>(...)``（无引用计数的堆节点，如 ``dict_entry``）。
- ``@descriptor`` / ``@mixin`` / ``@annotation`` 等：见 ``py2cpp/__init__.py`` 与 ``passes`` 下 ``mixins`` / ``descriptors`` 展开模块。
- ``@immutable`` / ``@copyable`` / ``@decorator`` / ``@context``：声明见 ``py2cpp/__init__.py``；``@context`` 亦可作函数装饰器。
- 用户类算术/位运算/比较：映射为 ``__add__`` / ``__radd__`` / ``__iadd__`` 等；``+=`` 等增强赋值同理。
- ``for`` / ``while`` 的 ``else``：无 ``break`` 时执行；迭代器耗尽导致的内部 ``break`` 不算用户 ``break``。
- ``with``：调用 ``__enter__`` / ``__exit__``；``__exit__`` 无 ``exc_type`` / ``exc_val`` / ``exc_tb``；``as x`` 绑定 ``__enter__()`` 返回值。
- ``@staticproperty`` / ``Self`` 见 ``py2cpp/__init__.py``。
- ``a.__copy__(b)``：显式复制；``c = b`` 对含 ``__move__`` 的类（标准库容器等）走移动；``@copyable`` 类走 ``__copy__``；``+b`` 为复制构造。
- ``@refcount`` 变量赋值仍走引用计数拷贝。
- ``alloc[T]()`` / ``free(p)``：单对象；``allocArray[T](n)`` / ``freeArray(p)``：数组；``init(ptr, ...)``：placement new；``id(x)`` → ``&x``（``@refcount`` 为 ``&(*x)``）。
- 文档字符串经 ``ast.get_docstring`` 转为头文件中的 ``///`` 注释。
"""
from __future__ import annotations
import ast
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from enum import IntFlag
from pathlib import Path
from typing import Callable
from .analysis.analyzer import SemanticAnalyzer, TypeParser
from .analysis.delegates import is_delegate_definition
from .analysis.type_pred import is_delegate_type
from .codegen.delegate_gen import emit_delegate_class
from .analysis.import_resolver import discover_translation_modules, iter_module_import_requests, resolve_import_target_path
from .analysis.imports import ImportUsing
from .analysis.module_namespace import MODULES_WITHOUT_CPP_NAMESPACE, inl_namespace_segments, merge_consecutive_namespace_blocks, module_path_namespace_segments, namespace_qualifier_for_module, splice_before_innermost_namespace_close, qualify_base_in_module, qualify_symbol_in_module, use_cpp_namespaces, using_namespace_line, using_symbol_line
from .analysis.imports import binding_cpp_name, resolve_class_ref_cpp, resolve_ctor_cpp_type, resolve_import_attribute_chain
from .analysis.type_pred import is_str_type, is_bytes_type, is_char_type, is_int_type, is_int64_type, is_uint_type, is_uint64_type, is_uintptr_type, is_varint_type, is_float_type, is_float64_type, is_scalar_int_type, is_scalar_float_type, is_refcount_type, is_optional_type, is_array_type, is_byte_type, is_stack_array_type, is_span_type, is_dict_type, is_set_type, is_frozenset_type, is_frozenlist_type, is_frozendict_type, is_deque_type, is_list_type, is_container_type, is_callable_type, is_py_generator_type, is_concrete_generator_type, is_py_coroutine_type, is_concrete_coroutine_type, is_py_async_generator_type, is_char_heap_array_type, is_byte_heap_array_type, is_char_stack_array_type, is_heap_array_type, is_iter_result_type, is_fault_result_type, is_complex_type
from .analysis.type_extract import dict_type_args, set_elem_type, frozenset_elem_type, frozenlist_elem_type, frozendict_type_args, deque_elem_type, list_elem_type, optional_inner_type
from .analysis.ir import INT_FIELDS, ClassInfo, TypeAliasInfo, TYPE_MARKER_CLASSES, FuncTypeParams, class_base_name, FunctionSig, MethodSig, ModuleAnalysis, codegen_file_header_lines, cpp_ident, cpp_type_param_template_name, cpp_param, cpp_result_type_args, cpp_template_inner_args, cpp_template_type, cpp_result_type, cpp_iter_result_return_expr, cpp_iter_result_yield_expr, iter_result_done_cpp, iter_result_value_cpp, iter_result_return_value_cpp, cpp_refcount_type, cpp_iterator_type, is_json_doc_cursor_type, cpp_slice_result_type, strip_cpp_ref, format_cpp_int, format_cpp_int64, format_cpp_uint, format_cpp_uint64, format_cpp_uintptr, format_cpp_varint, format_cpp_complex_literal, format_cpp_float64, cpp_fault_ok_expr, cpp_fault_err_expr, fault_result_ok_expr, fault_result_value_expr, cpp_option_some_expr, cpp_option_none_expr, cpp_pointer_type_for_object, option_is_none_expr, option_is_not_none_expr, option_unbox_expr, bytes_cpp_from_literal, cpp_array_elem_type, cpp_array_ndim, cpp_stack_array_size, cpp_stack_array_offset, cpp_stack_array_field_decl, cpp_stack_array_var_decl, cpp_stack_array_elem_type, cpp_stack_array_type, parse_cpp_stack_array_type, cpp_span_var_decl, cpp_span_elem_type, cpp_span_type, parse_subslice_bounds, CPP_RESULT_PREFIX, CPP_REFCount_PREFIX, strip_cpp_type_qualifiers, format_fn_sig, fn_noexcept_suffix, format_cpp_float, format_cpp_callable_var_decl, cpp_make_py_generator_expr, cpp_make_py_coroutine_expr, cpp_make_py_async_generator_expr, is_overload_stub, is_stub_function_body, quote_cpp_string, str_cpp_from_literal, has_named_decorator
from .analysis.patterns import DUNDER_METHODS, RESERVED, temp_name
from .passes.dataclass_expand import check_native_function_bodies, expand_dataclass
from .passes.default_bool import expand_default_bool
from .passes.default_numeric_convert import expand_default_numeric_convert
from .passes.default_iter import expand_default_iter
from .passes.default_ne import expand_default_ne
from .passes.kwargs_options import expand_kwargs_options
from .translation_error import TranslationError, enhance_translation_exception
from .passes.access import expand_member_access
from .passes.copyable import expand_copyable
from .passes.serializable import expand_serializable
from .passes.enum_expand import enum_member_names, expand_enum
from .passes.enum_mro_expand import expand_enum_mro
from .passes.union_mro_expand import expand_union_mro
from .passes.class_id import expand_class_id
from .passes.class_type_base import expand_class_type_base, check_class_inheritance_bases
from .passes.proxy import check_proxy_nested_type_args, expand_proxy
from .passes.final_checks import check_final_rules
from .passes.abstract_checks import check_abstract_rules
from .passes.union_expand import expand_union, resolve_union_field_cpp_types, union_ctor_target_info, union_variant_names, union_variant_param_cpp_types
from .emit.enum_emit import emit_enum_declaration, emit_enum_support
from .emit.union_emit import emit_union_class_declaration, emit_union_class_impl, emit_union_user_methods
from .passes.move_state import MOVE_STATE_FIELD, emit_move_state_epilogue_lines, emit_move_state_prologue_lines, expand_move_state
from .passes.parallel_loop_check import check_parallel_loops
from .passes.moved_use_check import check_moved_use
from .passes.new_type_args import check_new_type_arguments
from .passes.strict_style import check_static_virtual_override_s18, check_strict_style, check_yield_from_for_style, check_refcount_source_style, check_pynone_source_style, check_s32_dataclass_required_fields, check_s44_field_annotation_markers, _resolve_inherited_method
from .passes.protocol import expand_protocol
from .codegen.protocol_traits_gen import compare_ops_no_pybool_only_helper_lines, protocol_traits_lines
from .passes.decorators import expand_decorators
from .passes.generator_emit import emit_generator_next
from .passes.coroutine_desugar import check_yield_from_in_async_def
from .passes.generators import body_has_yield, expand_generators
from .passes.descriptors import expand_descriptors
from .passes.descriptor_signatures import expand_descriptor_signatures, is_descriptor_signature_helper
from .passes.match_case import emit_match
from .analysis.type_compat import split_cpp_template
from .passes.type_if import TypeIfFunctionPlan, emit_type_if_dispatch, emit_type_if_return, plan_type_if_chain
from .passes.macro_if import collect_macro_if_chain, emit_macro_if_chain, looks_like_macro_if_head
from .passes.descriptors import property_getter_method_for, property_postsetter_method_for, property_setter_method_for, storage_field_for
from .passes.field_properties import expand_field_properties, expand_property_value_references
from .passes.mixins import expand_mixins, expand_static_reflect
from .passes.test_discovery import expand_test_discovery
from .passes.static_reflect import static_field_name
from .emit.fstring_emit import emit_format_expr, plan_joined_str
from .emit.object_repr_emit import has_effective_str
from .codegen.expand_py2cpp_template import expand_template
from .codegen.stdlib_mirror_codegen import expand_whole_file_template
from .emit.layout_emit import build_stdlib_cpp_lines, module_path_to_guard, sync_runtime_cpp_usings, write_per_module_headers, write_per_module_inl, write_primitive_type_headers, write_umbrella_header
from .emit.layout_config_emit import GENERATED_DIR, RUNTIME_CPP, RUNTIME_OUTPUT_SUBDIR, RUNTIME_PREFIX, _JSON_API_METHODS_NEED_TYPE_ARG, _OS_PATH_MODULE, _IO_PATH_OO_MODULE, _DATETIME_MODULE, UMBRELLA_HEADER
from .emit.loops_emit import element_type_of_iterable, emit_native_range_loop_from_call, emit_range_len_expr, is_direct_range_call, visit_async_for, visit_for, visit_while
from .emit.print_emit import emit_print
from .emit.binop_emit import emit_bin_op, emit_compare, emit_unary_op
from .emit.call_emit import call_param_cpp_types, call_param_names, class_info_from_receiver, emit_call_args, emit_call_expr, emit_named_call_args, templated_instance_call_return_type
from .emit.delegate_emit import delegate_py_callable_type, resolve_delegate_for_type, try_emit_delegate_handler
from .emit.builtin_call_emit import emit_abs_call, emit_cmp_call, emit_construct, emit_format_call, emit_instance_dunder_call, emit_json_class_api_call, emit_slice_call, emit_slice_ctor, emit_str_format_call, emit_user_ctor, is_json_class_ref
from .emit.subscript_emit import array_subscript_get, array_subscript_set, container_view_elem_cpp, emit_container_view_as_span, emit_del_subscript_index, emit_span_slice_subscript, emit_stack_array_slice_subscript, emit_str_slice_subscript, emit_subscript_store, index_tuple_ctor, is_slice_ctor_expr, read_span_view_property, try_emit_subscript_augassign, visit_delete, visit_subscript
from .emit.parallel_assign_emit import try_emit_parallel_tuple_assign
from .emit.literal_ctor_emit import _emit_same_class_ctor, _emit_new_ctor_expr, _try_emit_new_ann_assign, _analyze_list_ctor_call, _emit_empty_container_ctor, _emit_typed_container_init, _empty_container_rhs, _is_empty_container_call, _emit_self_member_typed_container_init, _declare_appendable_var, _declare_list_var, _emit_list_ctor_init, _emit_appendable_literal_init, _emit_appendable_rvalue_expr, _emit_list_comp_rvalue_expr, _emit_list_literal_init, _str_literal_codepoints, _heap_array_literal_lhs, _emit_heap_array_literal_init, _try_emit_heap_array_literal_assign, _emit_char_heap_array_from_str_literal, _emit_char_stack_array_from_str_literal, _emit_byte_heap_array_from_bytes_literal, _try_emit_byte_array_bytes_literal, _try_emit_char_array_str_literal, _raise_stack_array_literal_length_mismatch, _emit_stack_array_literal_init, _try_emit_stack_array_literal_assign, _emit_list_value_expr, _try_emit_list_init_assign, _try_emit_field_typed_empty_literal_assign, _try_emit_self_field_empty_list_assign, _declare_dict_var, _declare_mapping_var, _emit_dict_literal_init, _emit_dict_value_expr, _list_cpp_type, _try_emit_list_comp_assign, _try_emit_dict_comp_assign, _try_emit_dict_init_assign, _declare_addable_var, _declare_set_var, _emit_set_literal_init, _try_emit_set_comp_assign, _try_emit_set_init_assign, _infer_set_elem_type, _emit_frozenset_from_arg, _emit_frozenset_from_set_literal, _emit_frozenlist_from_list_comp, _emit_frozenlist_from_list_literal, _emit_frozendict_from_dict_comp, _emit_frozendict_from_dict_literal, _emit_frozenset_from_set_comp, _try_emit_frozenset_init_assign, _frozenlist_elem_type_from_ann, _frozendict_inner_from_ann, _emit_frozenlist_from_arg, _try_emit_frozenlist_init_assign, _emit_frozendict_from_arg, _try_emit_frozendict_init_assign
from .emit.class_emit import _emit_class_methods_body, _emit_class_methods_body_impl, _emit_repr_alias_method, _emit_operator_pystr_conversion, _emit_operator_pybool_conversion, _emit_auto_dtor, _emit_method, _emit_method_impl, _emit_field_backed_property_getter, _emit_property_method, _emit_static_property_method, _generator_host_init, _emit_generator_default_ctor
from .emit.class_decl_emit import _emit_class_type_usings, _emit_class_constraint_asserts, _emit_module_protocol_traits, _emit_class_static_field_decl, _emit_class_field_decl, _emit_class_method_decl, _emit_class_declaration
from .emit.stdlib_inject_emit import emit_stdlib_class_runtime, emit_stdlib_module_paste_after, emit_stdlib_module_paste_before, with_stdlib_inl
from .constant.parallel import CONCUR_PARALLEL_MODULE, PRANGE_TRANSLATION_ONLY_FUNCS
from .constant.stdlib_discovery import STDLIB_REL_PATH_SET, STDLIB_REL_PATHS
from .constant.ffi_layout import (
  ffi_header_include,
  ffi_runtime_module_path,
  is_ffi_module_path,
)
from .constant.stdlib_layout import CORE_PKG, RUNTIME_PKG, is_on_demand_stdlib_rel, stdlib_header_include, stdlib_module_path
from .constant.stdlib_layout import STR_PYSTR, cpp_exception_ctor
from .analysis.runtime_symbols import BUILTINS_CPP_RUNTIME_FUNCS, RUNTIME_PKG_QUALIFIED_SYMBOLS, TRANSLATION_ONLY_FUNCS, runtime_root_ctor_expr

_ITER_RESULT_MODULE = stdlib_module_path("core/iter_result")

class NameContext(IntFlag):
    """作用域内名称的角色（变量 / 形参 / 字段）。"""
    Variable = 1
    Argument = 2
    Field = 4

@dataclass
class _LoopFrame:
    """循环 ``else``：用户 ``break`` 时将 ``else_flag`` 置为 ``false``（无 ``else`` 时为 ``None``）。"""
    else_flag: str | None

@dataclass
class _WithFrame:
    """``with``：进入时登记管理器变量，``return`` / ``break`` 前依次 ``__exit__``。"""
    managers: list[str]

@dataclass
class _TryFrame:
    """``try`` / ``finally``：``return`` / ``break`` / ``continue`` 前须执行 ``finalbody``。"""
    finally_body: list[ast.stmt]
    finally_emitted: bool = False

class Scope:
    """单个函数或方法体的作用域：名称分类与 C++ 类型表。"""

    def __init__(self, node: ast.AST):
        self.node = node
        self.vars: dict[str, NameContext] = {}
        self.fields: set[str] = set()
        self.param_types: dict[str, str] = {}
        self.param_type_nodes: dict[str, 'TypeNode'] = {}
        self.var_types: dict[str, str] = {}
        self.var_type_nodes: dict[str, 'TypeNode'] = {}
        self.lazy_params: dict[str, 'LazyParamInfo'] = {}

    def __contains__(self, name: str) -> bool:
        return name in self.vars

class Translator(ast.NodeVisitor):
    """遍历 AST 并写入 C++ 源码行缓冲。

  对外入口为类方法 ``translate_file``；实例方法 ``_emit_*`` / ``visit_*``
  负责具体语句与表达式的降级规则。
  """

    def __init__(self, module_name: str, source_path: str, *, debug: bool=False, strict: bool=True, openmp_enabled: bool=True):
        super().__init__()
        self.module_name = module_name
        self.source_path = source_path
        self.debug = debug
        self.strict = strict
        self.openmp_enabled = openmp_enabled
        self.uses_openmp = False
        self.header_lines: list[str] = []
        self.source_lines: list[str] = []
        self.in_header = True
        self.indent_level = 0
        self.scopes: list[Scope] = []
        self.scope: Scope | None = None
        self._active_generator_emitter = None
        self.class_info: ClassInfo | None = None
        self.classes: dict[str, ClassInfo] = {}
        self.delegates: dict = {}
        self.module_functions: list[tuple[str, ast.FunctionDef]] = []
        self.module_function_overloads: dict[tuple[str, str], list[ast.FunctionDef]] = {}
        self.module_function_overload_sigs: dict[tuple[str, str], list[FunctionSig]] = {}
        self.function_node_sigs: dict[int, FunctionSig] = {}
        self.descriptor_helper_protocol_bounds: dict[tuple[str, str], tuple[str, ...]] = {}
        self.module_constants: list[tuple[str, ast.AnnAssign]] = []
        self.emit_main: bool = True
        self.module_order: list[str] = []
        self.module_asts: dict[str, ast.Module] = {}
        self.type_parser: TypeParser | None = None
        self.module_analysis: dict[str, ModuleAnalysis] = {}
        self.header_usings_index: dict[str, list[tuple[str, str]]] = {}
        self.function_sigs: dict[tuple[str, str], FunctionSig] = {}
        self.import_bindings: dict = {}
        self.module_import_bindings: dict[str, dict] = {}
        self.module_import_usings: dict[str, list[ImportUsing]] = {}
        self._emit_bindings_scope: dict | None = None
        self.stdlib_modules_for_umbrella: tuple[str, ...] = ()
        self.per_module_header_lines: dict[str, list[str]] = {}
        self.per_module_deferred_header_lines: dict[str, list[str]] = {}
        self.per_module_global_traits_lines: dict[str, list[str]] = {}
        self.per_module_inl_lines: dict[str, list[str]] = {}
        self.per_module_source_lines: dict[str, list[str]] = {}
        self._py_callable_thunk_bodies: list[str] = []
        self._py_callable_thunk_names: dict[tuple[str, str, str], str] = {}
        self.lazy_param_default_exprs: dict[int, dict[str, ast.expr]] = {}
        self._lazy_lambda_counter = 0
        self._delegate_lambda_counter: int = 0
        self.header_target: str | None = None
        self.deferred_header_target: str | None = None
        self.inl_target: str | None = None
        self.source_target: str | None = None
        self.base_output_dir: Path = Path('.')
        self.runtime_output_dir: Path = Path('.')
        self.entry_output_dir: Path = Path('.')
        self.entry_module_path: str = ''
        self.module_debug_files: dict[str, str] = {}
        self._cpp_namespace_stack: list[str] = []
        self._py2cpp_current_stmt: ast.stmt | None = None
        self._py2cpp_stmt_dispatch_prepped: bool = False
        self.module_py_paths: dict[str, Path] = {}
        self._ast_node_stack: list[ast.AST] = []
        self.current_class: str | None = None
        self.current_method: ast.FunctionDef | None = None
        self._self_type_class: ClassInfo | None = None
        self.generated_at: str = ''
        self._loop_stack: list[_LoopFrame] = []
        self._with_stack: list[_WithFrame] = []
        self._try_stack: list[_TryFrame] = []
        self._try_star_depth: int = 0
        self._emit_line_sink: list[str] | None = None
        self._genexp_inline_self_cpp: str | None = None
        self._genexp_inline_name_map: dict[str, str] = {}
        self.generator_methods: set[tuple[str, str, str]] = set()
        self._type_if_extra_params: set[str] = set()
        self._type_if_concrete_bind: tuple[str, str] | None = None
        self._literal_target_ann: ast.expr | None = None

    @staticmethod
    def _runtime_root() -> Path:
        return Path(__file__).resolve().parent.parent / RUNTIME_PREFIX

    @staticmethod
    def _package_root() -> Path:
        return Path(__file__).parent.resolve()

    @classmethod
    def _repo_root(cls) -> Path:
        """仓库根目录（与 ``main.py``、用户 ``example.py`` 同级）。"""
        return cls._package_root().parent

    @classmethod
    def runtime_dir(cls, out_dir: Path) -> Path:
        """标准库头与 ``py2cpp.cpp`` 的 -I 根目录（``generated/runtime/``，其下为 ``py2cpp/*.h``）。"""
        out = out_dir.resolve()
        if out.name == RUNTIME_OUTPUT_SUBDIR:
            return out
        if out.name == RUNTIME_PREFIX and out.parent.name == RUNTIME_OUTPUT_SUBDIR:
            return out.parent
        return out / RUNTIME_OUTPUT_SUBDIR

    @classmethod
    def _is_runtime_py(cls, path: Path) -> bool:
        try:
            path.resolve().relative_to(cls._runtime_root().resolve())
            return True
        except ValueError:
            return False

    @classmethod
    def _entry_output_reldir(cls, path: Path) -> Path:
        """用户脚本相对 ``generated/`` 的子目录（镜像仓库内路径，如 ``examples``）。"""
        path = path.resolve()
        if cls._is_runtime_py(path):
            return Path(RUNTIME_OUTPUT_SUBDIR)
        repo = cls._repo_root()
        try:
            rel = path.parent.relative_to(repo)
            return Path('.') if rel == Path('.') else rel
        except ValueError:
            name = path.parent.name
            return Path(name) if name else Path('.')

    @classmethod
    def default_output_dir(cls, input_path: Path) -> Path:
        """生成物统一写入仓库根下的 ``generated/``，不与根目录 ``py2cpp/*.py`` 标准库混放。"""
        path = input_path.resolve()
        pkg_root = cls._package_root()
        repo_generated = cls._repo_root() / GENERATED_DIR
        runtime_root = cls._runtime_root().resolve()
        if path == runtime_root / '__init__.py' or path.parent == runtime_root:
            return repo_generated
        try:
            path.relative_to(pkg_root)
            return repo_generated
        except ValueError:
            return path.parent / GENERATED_DIR

    @classmethod
    def _resolve_output_dir(cls, input_path: Path, output_dir: str | None) -> Path:
        out = Path(output_dir).resolve() if output_dir else cls.default_output_dir(input_path)
        out.mkdir(parents=True, exist_ok=True)
        runtime_headers = (out / RUNTIME_OUTPUT_SUBDIR / RUNTIME_PREFIX).resolve()
        runtime_sources = cls._runtime_root().resolve()
        if runtime_headers == runtime_sources:
            raise ValueError(f'output directory {out} would overwrite Python runtime sources at {runtime_sources}; use -o {cls._repo_root() / GENERATED_DIR} or another empty directory')
        return out

    @classmethod
    def _entry_output_stem(cls, path: Path) -> str:
        """运行时包入口 __init__.py → 输出主文件名 py2cpp。"""
        if path.name == '__init__.py' and path.parent.resolve() == cls._runtime_root().resolve():
            return RUNTIME_PREFIX
        if path.name == '__init__.py':
            return path.parent.name or path.stem
        return path.stem

    @staticmethod
    def _entry_module_path(path: Path, runtime_root: Path) -> str:
        try:
            path.relative_to(runtime_root)
        except ValueError:
            try:
                return path.with_suffix('').relative_to(runtime_root.parent).as_posix()
            except ValueError:
                return f'{path.parent.name}/{path.stem}' if path.parent.name else path.stem
        if path.name == '__init__.py':
            rel = path.parent.relative_to(runtime_root)
            if rel.parts:
                return f'{RUNTIME_PREFIX}/{rel.as_posix()}'
            return RUNTIME_PREFIX
        return f'{RUNTIME_PREFIX}/{path.stem}'

    @classmethod
    def translate_file(cls, input_path: str, output_dir: str | None=None, include_stdlib: bool=True, *, emit_main: bool=True, debug: bool=False, strict: bool=True, openmp_enabled: bool=True) -> tuple[Path, Path]:
        path = Path(input_path).resolve()
        out_dir = cls._resolve_output_dir(path, output_dir)
        runtime_root = cls._runtime_root()
        runtime_init = runtime_root / '__init__.py'
        entry_is_runtime_init = path.resolve() == runtime_init.resolve()
        project_root = runtime_root.parent if entry_is_runtime_init or cls._is_runtime_py(path) else path.parent
        if entry_is_runtime_init:
            entry_path = cls._entry_module_path(path, runtime_root)
        elif cls._is_runtime_py(path):
            rel = path.with_suffix('').resolve().relative_to(runtime_root.resolve())
            entry_path = f'{RUNTIME_PREFIX}/{rel.as_posix()}' if rel.parts else RUNTIME_PKG
        else:
            entry_path = path.with_suffix('').resolve().relative_to(project_root.resolve()).as_posix()
        if not entry_is_runtime_init:
            modules = discover_translation_modules(path, include_stdlib=include_stdlib, runtime_root=runtime_root, project_root=project_root)
        else:
            modules = discover_translation_modules(runtime_init, include_stdlib=True, runtime_root=runtime_root, project_root=runtime_root.parent)
        out_stem = cls._entry_output_stem(path)
        entry_rel = cls._entry_output_reldir(path)
        runtime_out = cls.runtime_dir(out_dir)
        entry_out = out_dir if entry_rel == Path('.') else out_dir / entry_rel
        runtime_out.mkdir(parents=True, exist_ok=True)
        if entry_out != out_dir:
            entry_out.mkdir(parents=True, exist_ok=True)
        emit_user_entry = not cls._is_runtime_py(path)
        translator = cls(out_stem, str(path), debug=debug, strict=strict, openmp_enabled=openmp_enabled)
        translator.base_output_dir = out_dir
        translator.runtime_output_dir = runtime_out
        translator.entry_output_dir = entry_out
        translator.entry_module_path = entry_path
        translator.emit_main = emit_main
        translator._import_project_root_cache = project_root
        translator._parse_modules(modules)
        if include_stdlib and entry_is_runtime_init:
            from .codegen.template_conventions import check_template_conventions
            check_template_conventions(strict=strict)
        stdlib_names: list[str] = []
        for mp in translator.module_order:
            if not translator._is_stdlib_module(mp):
                continue
            if mp == RUNTIME_PKG:
                continue
            if mp.startswith(f'{RUNTIME_PKG}/'):
                rel = mp[len(f'{RUNTIME_PKG}/'):]
                if rel in STDLIB_REL_PATH_SET:
                    stdlib_names.append(rel)
        translator.stdlib_modules_for_umbrella = tuple(stdlib_names)
        try:
            check_s32_dataclass_required_fields(translator)
            check_s44_field_annotation_markers(translator)
            expand_dataclass(translator)
            expand_class_id(translator)
            expand_enum_mro(translator)
            expand_union_mro(translator)
            expand_enum(translator)
            expand_union(translator)
            expand_serializable(translator)
            check_native_function_bodies(translator)
            expand_default_iter(translator)
            expand_descriptors(translator)
            expand_mixins(translator)
            expand_proxy(translator)
            expand_class_type_base(translator)
            expand_field_properties(translator.classes)
            expand_property_value_references(translator.classes)
            expand_default_bool(translator)
            expand_default_numeric_convert(translator)
            expand_default_ne(translator)
            expand_test_discovery(translator)
            expand_kwargs_options(translator)
            expand_static_reflect(translator)
            check_yield_from_for_style(translator)
            check_yield_from_in_async_def(translator)
            expand_generators(translator)
            expand_decorators(translator)
            from .passes.noexcept_meta import check_noexcept_functions
            check_noexcept_functions(translator)
            expand_copyable(translator)
            expand_move_state(translator)
            expand_protocol(translator)
            expand_member_access(translator)
            expand_descriptor_signatures(translator)
            from .passes.lazy_params import expand_lazy_params
            expand_lazy_params(translator)
            from .passes.final_expand import expand_final_ctor_inits
            expand_final_ctor_inits(translator)
            SemanticAnalyzer().analyze(translator)
            check_proxy_nested_type_args(translator)
            resolve_union_field_cpp_types(translator)
            check_new_type_arguments(translator)
            check_class_inheritance_bases(translator)
            check_final_rules(translator)
            check_abstract_rules(translator)
            check_refcount_source_style(translator)
            check_pynone_source_style(translator)
            check_strict_style(translator)
            check_static_virtual_override_s18(translator)
            check_parallel_loops(translator)
            check_moved_use(translator)
            translator.generated_at = datetime.now().strftime('生成时间: %Y-%m-%d %H:%M:%S')
            translator._emit_all()
        except Exception as exc:
            raise enhance_translation_exception(exc, translator, fallback_absolute=path) from exc
        translator._ensure_member_access_header()
        translator._write_per_module_headers()
        from .analysis.stdlib_module_order import reorder_stdlib_modules_for_umbrella
        reorder_stdlib_modules_for_umbrella(translator)
        translator._write_umbrella_header()
        translator._write_per_module_inl()
        runtime_cpp = runtime_out / RUNTIME_CPP
        umbrella_header = runtime_out / UMBRELLA_HEADER
        has_stdlib_body = include_stdlib and translator._has_stdlib_source() and translator._is_runtime_bootstrap()
        if has_stdlib_body:
            runtime_cpp.write_text('\n'.join(translator._build_stdlib_cpp_lines(merge_entry_runtime=entry_path == RUNTIME_PREFIX)) + '\n', encoding='utf-8')
        elif include_stdlib and translator._is_runtime_bootstrap():
            runtime_cpp.write_text('\n'.join(codegen_file_header_lines('标准库实现均在各模块 *.inl（测试 TU 不链本文件）', translator.generated_at)) + '\n', encoding='utf-8')
        if emit_user_entry:
            header_path = entry_out / f'{out_stem}.h'
            entry_cpp = entry_out / f'{out_stem}.cpp'
            header_path.write_text('\n'.join(translator.header_lines) + '\n', encoding='utf-8')
            entry_cpp.write_text('\n'.join(translator.source_lines) + '\n', encoding='utf-8')
            source_path = entry_cpp
        else:
            header_path = umbrella_header
            source_path = runtime_cpp if has_stdlib_body else umbrella_header
        from .codegen.nav_index import write_nav_index
        write_nav_index(translator)
        return (header_path, source_path)

    @contextmanager
    def _use_import_bindings(self, module_path: str):
        prev = self._emit_bindings_scope
        self._emit_bindings_scope = self.module_import_bindings.get(module_path, {})
        try:
            yield
        finally:
            self._emit_bindings_scope = prev

    def _effective_import_bindings(self) -> dict:
        if self._emit_bindings_scope is not None:
            return self._emit_bindings_scope
        return self.import_bindings

    def _import_attr_chain_cpp(self, node: ast.Attribute) -> str | None:
        attrs: list[str] = []
        cur: ast.expr = node
        while isinstance(cur, ast.Attribute):
            attrs.insert(0, cur.attr)
            cur = cur.value
        if not isinstance(cur, ast.Name) or not attrs:
            return None
        binding = resolve_import_attribute_chain(self, cur.id, attrs)
        if binding is None:
            return None
        if binding.kind == 'class':
            cpp = binding.cpp_name
            if '::' not in cpp and binding.module_path:
                ns = namespace_qualifier_for_module(binding.module_path)
                if ns:
                    cpp = f'::{ns}::{cpp}'
            return cpp
        if binding.kind == 'function':
            cpp = binding.cpp_name
            if '::' not in cpp and binding.module_path:
                ns = namespace_qualifier_for_module(binding.module_path)
                if ns:
                    cpp = f'::{ns}::{cpp}'
            return self._qualify_import_call(cpp, binding.local_name, module_path=binding.module_path)
        return None

    def _display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self._repo_root().resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def _resolve_module_py_path(self, module_path: str) -> Path:
        """模块 ``.py`` 绝对路径（缓存）。"""
        cached = self.module_py_paths.get(module_path)
        if cached is not None:
            return cached
        if module_path == self.entry_module_path:
            resolved = Path(self.source_path).resolve()
        elif module_path == RUNTIME_PKG:
            resolved = (self._runtime_root() / '__init__.py').resolve()
        else:
            from .analysis.import_resolver import _find_user_py_file, _stdlib_py_path
            resolved = _stdlib_py_path(self._runtime_root(), module_path)
            if resolved is None:
                found = _find_user_py_file(module_path, project_root=self._import_project_root_cache, runtime_root=self._runtime_root())
                resolved = found.resolve() if found is not None else Path(self.source_path).resolve()
            else:
                resolved = resolved.resolve()
        self.module_py_paths[module_path] = resolved
        return resolved

    def _module_source_file_path(self, module_path: str) -> str:
        """模块对应 ``.py`` 路径（``__file__`` / ``--debug``）。"""
        return self._display_path(self._resolve_module_py_path(module_path))

    def visit(self, node: ast.AST):
        self._ast_node_stack.append(node)
        try:
            return super().visit(node)
        except TranslationError:
            raise
        except Exception as exc:
            raise enhance_translation_exception(exc, self, node=node) from exc
        finally:
            self._ast_node_stack.pop()

    def _register_module_debug_file(self, module_path: str) -> None:
        """``--debug`` 日志中的路径与对应 ``.py`` 源文件一致。"""
        self.module_debug_files[module_path] = self._module_source_file_path(module_path)

    def _active_module_path(self) -> str:
        if self.source_target:
            return self.source_target
        if self.inl_target:
            return self.inl_target
        if self.class_info is not None:
            return self.class_info.module_path
        return self.entry_module_path

    def _module_dunder_name(self, module_path: str) -> str:
        """``__name__``：入口用户模块为 ``__main__``，其余为 ``a/b`` → ``a.b``。"""
        if module_path == self.entry_module_path and self.entry_module_path != RUNTIME_PKG:
            return '__main__'
        return module_path.replace('/', '.')

    def _emit_dunder_name(self, module_path: str | None=None) -> str:
        mp = module_path if module_path is not None else self._active_module_path()
        return str_cpp_from_literal(self._module_dunder_name(mp))

    def _emit_dunder_file(self, module_path: str | None=None) -> str:
        mp = module_path if module_path is not None else self._active_module_path()
        return str_cpp_from_literal(self._module_source_file_path(mp))

    def _active_debug_module_path(self) -> str:
        if self.inl_target:
            return self.inl_target
        if self.source_target and self._is_stdlib_module(self.source_target):
            return self.source_target
        if self.class_info is not None:
            return self.class_info.module_path
        return self.entry_module_path

    def _debug_loc(self, node: ast.AST) -> str:
        path = self.module_debug_files.get(self._active_debug_module_path(), Path(self.source_path).name)
        lineno = getattr(node, 'lineno', None)
        if lineno:
            return f'{path}:{lineno}'
        return path

    def _parse_modules(self, modules: list[tuple[str, str]]):
        for module_path, code in modules:
            if module_path not in self.module_order:
                self.module_order.append(module_path)
            self._register_module_debug_file(module_path)
            tree = ast.parse(code)
            self.module_asts[module_path] = tree
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    info = ClassInfo(node, module_path)
                    self.classes[info.name] = info
                    self._register_nested_classes(info)
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        self.module_constants.append((module_path, node))
                elif isinstance(node, ast.FunctionDef):
                    from .constant.stdlib_layout import RUNTIME_BUILTINS_MODULE
                    if module_path in (RUNTIME_PKG, RUNTIME_BUILTINS_MODULE):
                        if node.name not in BUILTINS_CPP_RUNTIME_FUNCS:
                            continue
                        if has_named_decorator(node, 'global_call'):
                            continue
                    if node.name in TRANSLATION_ONLY_FUNCS:
                        continue
                    if module_path == CONCUR_PARALLEL_MODULE and node.name in PRANGE_TRANSLATION_ONLY_FUNCS:
                        continue
                    if is_delegate_definition(node):
                        continue
                    if has_named_decorator(node, 'overload'):
                        self.module_function_overloads.setdefault((module_path, node.name), []).append(node)
                    else:
                        self.module_functions.append((module_path, node))

    @staticmethod
    def _is_decorator_impl(func: ast.FunctionDef) -> bool:
        return func.name.endswith('_impl')

    @staticmethod
    def _translator_only_skip_method(info: ClassInfo, method: ast.FunctionDef) -> bool:
        from .passes.kwargs_options import is_translator_only_method, is_varstack_translator_only_method
        if info.name == 'VarStack' and is_varstack_translator_only_method(method):
            return True
        return is_translator_only_method(method.name, method)

    def _skip_runtime_method_decl(self, info: ClassInfo, method: ast.FunctionDef) -> bool:
        """``.h`` 声明：仅译器注入项跳过（类/方法 ``@native`` 仍须从 Python 桩生成声明）。"""
        if info.name == 'ExceptionGroup' and method.name == 'append':
            from .codegen.exception_group_gen import _exc_slot_info
            if _exc_slot_info(self) is not None:
                return True
        return self._translator_only_skip_method(info, method)

    def _skip_runtime_method_emit(self, info: ClassInfo, method: ast.FunctionDef) -> bool:
        """``.inl`` 实现：类/方法 ``@native`` 由 ``codegen/*_cpp.py`` 注入；``@abstract`` 仅 ``.h`` 声明。"""
        sig = info.method_sig_for(method)
        return self._skip_runtime_method_decl(info, method) or self._io_skip_runtime_method(info, method) or has_named_decorator(method, 'native') or (sig is not None and sig.is_abstract)

    @staticmethod
    def _io_skip_runtime_method(info: ClassInfo, method: ast.FunctionDef) -> bool:
        """``@native`` 类/方法：声明可生成，实现由 ``codegen/*_cpp.py`` 或整模块 codegen 注入。"""
        return info.is_native

    @staticmethod
    def _method_static_prefix(msig: MethodSig) -> str:
        return 'static ' if msig.is_static else ''

    @staticmethod
    def _method_virtual_prefix(msig: MethodSig) -> str:
        if msig.is_static or msig.is_override:
            return ''
        if msig.is_virtual or msig.is_final or msig.is_abstract:
            return 'virtual '
        return ''

    @staticmethod
    def _method_pure_virtual_suffix(msig: MethodSig) -> str:
        return ' = 0' if msig.is_abstract and (not msig.is_static) else ''

    @staticmethod
    def _method_final_suffix(msig: MethodSig) -> str:
        return ' final' if msig.is_final and (not msig.is_static) else ''

    @staticmethod
    def _cpp_override_signatures_match(child: MethodSig, base: MethodSig) -> bool:
        return Translator._sig_return_full(child) == Translator._sig_return_full(base) and child.params_decl.strip() == base.params_decl.strip()

    def _method_override_suffix(self, msig: MethodSig, info: ClassInfo | None=None, method_name: str='') -> str:
        if msig.is_static or not msig.is_override:
            return ''
        if info is not None and method_name:
            inherited = _resolve_inherited_method(self, info, method_name)
            if inherited is None:
                return ''
            base_info, _ = inherited
            base_sig = base_info.method_sigs.get(method_name)
            if base_sig is None or not self._cpp_override_signatures_match(msig, base_sig):
                return ''
        return ' override'

    @staticmethod
    def _method_const_suffix(msig: MethodSig, method_name: str='') -> str:
        if msig.is_static:
            return ''
        if method_name in ('__str__', '__bool__'):
            return ' const'
        return ' const' if msig.is_const else ''

    def _entry_functions(self) -> list[ast.FunctionDef]:
        return [f for mp, f in self.module_functions if mp == self.entry_module_path and f.name not in self.delegates]

    def _delegate_names(self) -> frozenset[str]:
        return frozenset(self.delegates.keys())

    def _has_stdlib_source(self) -> bool:
        return any((self.per_module_source_lines.get(mp) for mp in self.module_order if self._is_stdlib_module(mp)))

    def _build_stdlib_cpp_lines(self, *, merge_entry_runtime: bool=False) -> list[str]:
        return build_stdlib_cpp_lines(self, merge_entry_runtime=merge_entry_runtime)

    def _emit_module_delegates(self, module_path: str) -> None:
        items = [d for d in self.delegates.values() if d.module_path == module_path]
        if not items:
            return
        with self._use_module_decl(module_path), self._use_header():
            buf: list[str] = []
            for info in items:
                emit_delegate_class(info, lines=buf)
            for line in buf:
                self.write_line(line)
            self.write_line()

    def _stdlib_rel_from_module_path(self, module_path: str) -> str:
        mp = module_path.replace('\\', '/')
        prefix = f'{RUNTIME_PKG}/'
        if mp.startswith(prefix):
            return mp[len(prefix):]
        return mp

    def _is_on_demand_stdlib_module(self, module_path: str) -> bool:
        """``STDLIB_SKIP_PREFIXES`` 等不参与 bootstrap 的标准库，须显式 import 后翻译/链头。"""
        return is_on_demand_stdlib_rel(self._stdlib_rel_from_module_path(module_path))

    def _entry_imports_io_module(self) -> bool:
        """仅显式 ``from py2cpp.io import …`` 时拉 ``io.h``（``from py2cpp import *`` 不重导出实现头）。"""
        tree = self.module_asts.get(self.entry_module_path)
        if tree is None:
            return False
        proj = self._import_project_root_cache
        runtime = self._runtime_root()
        for req in iter_module_import_requests(tree):
            if req.is_star:
                continue
            target = resolve_import_target_path(self.entry_module_path, req, project_root=proj, runtime_root=runtime)
            if target == stdlib_module_path('io'):
                return True
        return False

    def _start_header(self):
        with self._use_header():
            self.write_comment('由 py2cpp 自动生成，请勿手动编辑')
            self.write_comment(f'源文件: {self.source_path}')
            self.write_comment(self.generated_at)
            self.write_line()
            guard = module_path_to_guard(self.entry_module_path)
            self.write_line(f'#ifndef {guard}')
            self.write_line(f'#define {guard}')
            self.write_line()
            self.write_line(f'// C++11，无 STL；运行时见 {RUNTIME_OUTPUT_SUBDIR}/{RUNTIME_PREFIX}/，编译时 -I 该 runtime 目录')
            has_stdlib = any((self._is_stdlib_module(mp) for mp in self.module_order))
            if has_stdlib or not self._is_runtime_bootstrap():
                self.write_line(f'#include "{UMBRELLA_HEADER}"')
            if self._entry_imports_io_module():
                self.write_line(f'''#include "{stdlib_header_include('io')}"''')
            if self.delegates:
                self.write_line(f'''#include "{stdlib_header_include('core/delegate')}"''')
            for module_path in self.module_order:
                if module_path == self.entry_module_path:
                    continue
                if is_ffi_module_path(module_path):
                    self.write_line(f'#include "{ffi_header_include(module_path)}"')
                    continue
                if has_stdlib and self._is_stdlib_module(module_path):
                    if self._is_on_demand_stdlib_module(module_path):
                        rel = self._stdlib_rel_from_module_path(module_path)
                        self.write_line(f'#include "{stdlib_header_include(rel)}"')
                    continue
                rel = self._user_module_output_relpath(module_path)
                self.write_line(f'#include "{rel}.h"')
            self.write_line()

    def _start_source(self):
        with self._use_source():
            self.write_comment('由 py2cpp 自动生成')
            self.write_comment(f'源文件: {self.source_path}')
            self.write_comment(self.generated_at)
            self.write_line(f'#include "{self.module_name}.h"')
            for mp in self._entry_imported_user_modules():
                if self.per_module_inl_lines.get(mp):
                    rel = self._user_module_output_relpath(mp)
                    self.write_line(f'#include "{rel}.inl"')
            self.write_line('#include <stdio.h>')
            self.write_line('#include <string.h>')
            self.write_line('#include <math.h>')
            self._emit_debug_helper()
            self.write_line()

    def _umbrella_has_debug_helpers(self) -> bool:
        """``py2cpp.h`` 已在 bootstrap ``--debug`` 时注入跟踪辅助（须在 include 之前）。"""
        hpath = self.runtime_output_dir / UMBRELLA_HEADER
        if not hpath.is_file():
            return False
        try:
            return '_py2cpp_debug_call' in hpath.read_text(encoding='utf-8')
        except OSError:
            return False

    def _emit_debug_helper(self) -> None:
        if not self.debug:
            return
        if self._umbrella_has_debug_helpers():
            return
        from .codegen.expand_py2cpp_template import expand_template
        for line in expand_template('debug.inl', apply_allman=True).splitlines():
            self.write_line(line)
        self.write_line()

    def _stdlib_entry_header_stays_in_per_module(self) -> bool:
        """单模块 runtime 翻译：声明留在 ``per_module_header_lines`` 供 ``write_per_module_headers`` 写入。"""
        if self._is_runtime_bootstrap() and self.entry_module_path == RUNTIME_PKG:
            return True
        return (
            self._is_stdlib_module(self.entry_module_path)
            and self._can_write_stdlib_artifact(self.entry_module_path)
        )

    def _splice_entry_deferred_header_lines(self, entry_body: list[str]) -> list[str]:
        """入口模块 ``.h``：``PyList`` 等延后类声明须在 ``} // namespace`` 之前（``write_per_module_headers`` 已处理非入口模块）。"""
        if self._stdlib_entry_header_stays_in_per_module():
            deferred = self.per_module_deferred_header_lines.get(self.entry_module_path, [])
        else:
            deferred = self.per_module_deferred_header_lines.pop(self.entry_module_path, [])
        return splice_before_innermost_namespace_close(entry_body, deferred)

    def _finish_header(self):
        if self._stdlib_entry_header_stays_in_per_module():
            entry_body = self.per_module_header_lines.get(self.entry_module_path, [])
        else:
            entry_body = self.per_module_header_lines.pop(self.entry_module_path, [])
        entry_body = self._splice_entry_deferred_header_lines(entry_body)
        if self._stdlib_entry_header_stays_in_per_module():
            global_traits = self.per_module_global_traits_lines.get(self.entry_module_path, [])
        else:
            global_traits = self.per_module_global_traits_lines.pop(self.entry_module_path, [])
        if global_traits:
            entry_body = entry_body + ['', '#include "py2cpp/core/refcount.h"', '', *global_traits, '']
        if self.per_module_inl_lines.get(self.entry_module_path):
            entry_body = [*entry_body, '', f'#include "{self.module_name}.inl"', '']
        if self._stdlib_entry_header_stays_in_per_module():
            self.per_module_header_lines[self.entry_module_path] = entry_body
            if self.entry_module_path in self.per_module_deferred_header_lines:
                self.per_module_deferred_header_lines.pop(self.entry_module_path, None)
            if self.entry_module_path in self.per_module_global_traits_lines:
                self.per_module_global_traits_lines.pop(self.entry_module_path, None)
        elif entry_body:
            self.header_lines.extend(entry_body)
        with self._use_header():
            guard = module_path_to_guard(self.entry_module_path)
            self.write_line(f'#endif // {guard}')
        self.in_header = False

    @contextmanager
    def _use_module_header(self, module_path: str):
        prev = self.header_target
        prev_deferred = self.deferred_header_target
        self.header_target = module_path
        self.deferred_header_target = None
        self.per_module_header_lines.setdefault(module_path, [])
        yield
        self.header_target = prev
        self.deferred_header_target = prev_deferred

    @contextmanager
    def _use_module_deferred_decl(self, module_path: str):
        """``PyList`` 等完整类型成员：在 ``post_class_includes`` 之后再声明。"""
        prev = self.header_target
        prev_deferred = self.deferred_header_target
        self.header_target = module_path
        self.deferred_header_target = module_path
        self.per_module_deferred_header_lines.setdefault(module_path, [])
        with self._use_header():
            yield
        self.header_target = prev
        self.deferred_header_target = prev_deferred

    @contextmanager
    def _use_module_inl(self, module_path: str):
        prev = self.inl_target
        self.inl_target = module_path
        self.per_module_inl_lines.setdefault(module_path, [])
        yield
        self.inl_target = prev

    @contextmanager
    def _use_module_source(self, module_path: str):
        prev = self.source_target
        self.source_target = module_path
        self.per_module_source_lines.setdefault(module_path, [])
        yield
        self.source_target = prev

    @contextmanager
    def _use_module_decl(self, module_path: str):
        """各模块声明写入 ``per_module_header_lines``（入口模块在 ``_finish_header`` 合并）。"""
        with self._use_module_header(module_path), self._use_header():
            yield

    def _current_module_path(self) -> str:
        return self._active_module_path()

    def _module_type_alias_map(self, module_path: str | None=None) -> dict[str, TypeAliasInfo]:
        from .analysis.imports import effective_module_type_aliases
        mp = module_path or self._current_module_path()
        return effective_module_type_aliases(self, mp)

    def _expand_module_type_alias_cpp(self, cpp_type: str, module_path: str | None=None) -> str:
        """模块级 ``type Int = ModInt[…]`` → 展开为具体 C++ 类型（``@property`` 等派发）。"""
        bare = ClassInfo.unwrap_refcount_type(cpp_type.strip())
        if bare.endswith('*'):
            bare = bare[:-1].strip()
        if bare.endswith('&'):
            bare = bare[:-1].strip()
        if bare.startswith('const '):
            bare = bare[6:].strip()
        if '<' in bare or '::' in bare:
            return cpp_type
        aliases = self._module_type_alias_map(module_path)
        alias = aliases.get(bare)
        if alias is None or self.type_parser is None:
            return cpp_type
        others = {n: a for n, a in aliases.items() if n != bare}
        self.type_parser.set_type_aliases(others, use_as_cpp_name=False)
        return self.type_parser.parse_type(alias.value, set(alias.type_params))

    def _class_info_for_type(self, cpp_type: str) -> ClassInfo | None:
        if not cpp_type:
            return None
        from .analysis.ir import strip_cpp_type_qualifiers
        base = strip_cpp_type_qualifiers(cpp_type)
        base = ClassInfo.unwrap_refcount_type(base)
        from .analysis.proxy import is_cpp_proxy_type
        if is_cpp_proxy_type(base):
            for info in self.classes.values():
                if getattr(info, 'is_proxy', False):
                    return info
        if base == 'Self':
            return self._active_class_info()
        expanded = self._expand_module_type_alias_cpp(base)
        if expanded != base:
            info = self._class_info_for_type(expanded)
            if info is not None:
                return info
        if '<' in base:
            generic = base.split('<', 1)[0].strip()
            if '::' in generic:
                generic = generic.rsplit('::', 1)[-1]
            for info in self.classes.values():
                if info.cpp_name() == generic or info.name == generic:
                    return info
            return None
        if '::' in base:
            base = base.rsplit('::', 1)[-1]
        for info in self.classes.values():
            if info.cpp_name() == base or info.name == base:
                return info
        return None

    def _uses_ptr_access(self, cpp_type: str) -> bool:
        t = cpp_type.strip()
        if t in self._active_type_params() and self._type_param_has_boxing_constraint(t):
            return True
        return t.endswith('*') or is_refcount_type(t) or (t.endswith('&') and is_refcount_type(t.rstrip('&')))

    def _type_param_has_boxing_constraint(self, name: str) -> bool:
        if name not in self._active_type_params():
            return False
        dec: dict[str, tuple[str, ...]] = {}
        if self.class_info:
            dec.update(getattr(self.class_info, 'type_param_decorator_constraints', {}))
        if self.current_method:
            if self.class_info:
                sig = self.class_info.method_sigs.get(self.current_method.name)
                if sig:
                    dec.update(getattr(sig.func_ft, 'decorator_constraints', {}))
            else:
                mp = self._active_module_path()
                fsig = self.function_sigs.get((mp, self.current_method.name))
                if fsig:
                    dec.update(getattr(fsig.func_ft, 'decorator_constraints', {}))
        return 'boxing' in dec.get(name, ())

    def _expr_is_list_element_ref(self, node: ast.expr) -> bool:
        """``self._cases[i]`` / ``self._cases.__getitem__(i)`` → 列表元素引用（非列表本身）。"""
        match node:
            case ast.Subscript(value=ast.Attribute(value=ast.Name(id='self'), attr=attr), slice=_):
                if self.class_info:
                    return is_list_type(self._field_storage(attr))
            case ast.Call(func=ast.Attribute(value=ast.Attribute(value=ast.Name(id='self'), attr=attr), attr='__getitem__'), args=[_]):
                if self.class_info:
                    return is_list_type(self._field_storage(attr))
            case _:
                return False

    def _friend_class_decl_lines(self, info: ClassInfo) -> list[str]:
        """``friends=(A,)`` → ``friend class …PyA;``（写在类体最前，无访问前缀）。"""
        lines: list[str] = []
        host_tp = list(info.type_params)
        for friend_py in info.friend_classes:
            fi = self.classes.get(friend_py)
            if fi is not None:
                fq = qualify_base_in_module(info.module_path, fi.module_path, fi.cpp_name())
                friend_tp = list(fi.type_params)
            else:
                fq = cpp_ident(friend_py)
                friend_tp = []
            if host_tp and friend_tp == host_tp:
                args = ', '.join((cpp_type_param_template_name(p) for p in host_tp))
                lines.append(f'friend class {fq}<{args}>;')
            elif host_tp and friend_tp and len(host_tp) > len(friend_tp) and friend_tp == host_tp[:len(friend_tp)]:
                args = ', '.join((cpp_type_param_template_name(p) for p in friend_tp))
                lines.append(f'friend class {fq}<{args}>;')
            elif host_tp and len(friend_tp) > len(host_tp) and (friend_tp[:len(host_tp)] == host_tp):
                extra = friend_tp[len(host_tp):]
                extra_decl = ', '.join((f'typename {cpp_type_param_template_name(p)}' for p in extra))
                lines.append(f'template<{extra_decl}>')
                all_args = ', '.join((cpp_type_param_template_name(p) for p in friend_tp))
                lines.append(f'friend class {fq}<{all_args}>;')
            elif friend_tp and (not host_tp):
                extra_decl = ', '.join((f'typename {cpp_type_param_template_name(p)}' for p in friend_tp))
                lines.append(f'template<{extra_decl}>')
                lines.append(f'friend class {fq};')
            else:
                lines.append(f'friend class {fq};')
        return lines

    def _cpp_public_bases(self, info: ClassInfo) -> list[str]:
        """C++ 继承列表：跳过 ``@mixin`` / ``@annotation`` 基类（无对应 C++ 类型）。"""
        out: list[str] = []
        tp = set(info.type_params)
        node_bases: dict[str, ast.expr] = {}
        for base_ast in info.node.bases:
            name = class_base_name(base_ast)
            if name is not None:
                node_bases[name] = base_ast
        for base in info.bases:
            bi = self.classes.get(base)
            if bi is not None and (bi.is_mixin or bi.is_annotation or bi.is_protocol):
                continue
            base_ast = node_bases.get(base)
            if bi is not None:
                if isinstance(base_ast, ast.Subscript):
                    base_cpp = self._parse_type(base_ast, tp).strip()
                    out.append(self._rewrite_template_args_to_cpp_params(base_cpp, info))
                else:
                    out.append(qualify_base_in_module(info.module_path, bi.module_path, bi.cpp_name()))
            else:
                out.append(cpp_ident(base))
        return out

    def _inherits_virtual_polymorphic(self, info: ClassInfo) -> bool:
        if info.has_virtual_methods:
            return True
        for base in info.bases:
            bi = self.classes.get(base)
            if bi is not None and (bi.is_mixin or bi.is_annotation):
                continue
            if self._inherits_virtual_polymorphic(bi):
                return True
        return False

    def _needs_virtual_dtor_decl(self, info: ClassInfo) -> bool:
        return self._inherits_virtual_polymorphic(info) and '__del__' not in info.methods

    def _emit_virtual_dtor_definition(self, info: ClassInfo) -> None:
        if info.needs_auto_dtor() or not self._needs_virtual_dtor_decl(info):
            return
        ctx = self._use_module_inl(info.module_path) if info.is_template() or self._is_stdlib_module(info.module_path) else self._use_module_source(info.module_path)
        qual = self._class_method_qualifier(info)
        with ctx, self._use_source():
            if info.is_template():
                self._emit_template_prefix(info)
            self.write_line(f'{qual}::~{info.cpp_name()}()')
            self.write_line('{')
            self.write_line('}')
            self.write_line()

    def _refcount_ctor_class(self, info: ClassInfo) -> ClassInfo | None:
        """返回应用 ``makeRefCount`` 时应使用的类（含 ``@refcount`` 基类派生）。"""
        if info.is_refcount:
            return info
        for base in info.bases:
            bi = self.classes.get(base)
            if bi is None or bi.is_mixin or bi.is_annotation:
                continue
            rc = self._refcount_ctor_class(bi)
            if rc is not None:
                return info
        return None

    def _class_info_for_expr(self, node: ast.expr) -> ClassInfo | None:
        if isinstance(node, ast.Name):
            if node.id == 'self' and self.class_info:
                return self.class_info
            if self.scope:
                t = self._scope_storage(node.id)
                return self._class_info_for_type(t)
        if isinstance(node, ast.Call):
            info = self._class_info_for_call(node)
            if info is not None:
                return info
            ctor = self._constructor_type(node)
            if ctor:
                return self._class_info_for_type(ctor)
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Invert):
                operand = self._class_info_for_expr(node.operand)
                if operand and self._class_info_has_method(operand, '__invert__'):
                    return operand
            if isinstance(node.op, (ast.UAdd, ast.USub)):
                return self._class_info_for_expr(node.operand)
        if isinstance(node, ast.BinOp):
            dunder = self._binop_dunder(node.op)
            if dunder:
                left = self._class_info_for_expr(node.left)
                if left and self._class_info_has_method(left, dunder):
                    return left
        return None

    def _infer_dunder_forward_call_return_type(self, name: str, node: ast.Call) -> str | None:
        """``iter(x)`` / ``reversed(x)`` 等包根 dunder 转发：按接收者方法返回类型推断，勿用桩 ``decltype(obj.__iter__())``。"""
        from .analysis.stubs.builtin_stubs import builtin_dunder_forward
        from .analysis.stubs.iterator_return_stubs import iter_method_return_type, reversed_method_return_type
        fwd = builtin_dunder_forward(name)
        if fwd is None or len(node.args) <= fwd.receiver_index:
            return None
        dunder = fwd.dunder
        recv = node.args[fwd.receiver_index]
        info = self._class_info_for_expr(recv)
        if info is None and isinstance(recv, ast.Call):
            ctor = self._constructor_type(recv)
            if ctor:
                info = self._class_info_for_type(ctor)
        if info is None:
            return None
        hit = None
        if dunder == '__iter__':
            hit = iter_method_return_type(info)
        elif dunder == '__reversed__':
            hit = reversed_method_return_type(info)
        if hit is not None:
            ret = hit[0].strip().rstrip('&')
        else:
            ret = self._receiver_method_return_cpp_type(info, dunder, recv, node.args)
            if not ret:
                return None
            ret = ret.strip().rstrip('&')
        if info.module_path != RUNTIME_PKG and self._is_stdlib_module(info.module_path):
            base, _, tail = ret.partition('<')
            if tail:
                ret = f'{qualify_symbol_in_module(info.module_path, base)}<{tail}'
            else:
                ret = qualify_symbol_in_module(info.module_path, ret)
        return ret

    def _function_sig_for_name(self, name: str) -> FunctionSig | None:
        for mp in (self.source_target, self.entry_module_path, *reversed(self.module_order)):
            if not mp:
                continue
            fsig = self.function_sigs.get((mp, name))
            if fsig is not None:
                return fsig
        return None

    def _class_info_for_call(self, node: ast.Call) -> ClassInfo | None:
        if isinstance(node.func, ast.Name):
            if node.func.id == 'Self' and self._self_type_class:
                return self._self_type_class
            binding = self._effective_import_bindings().get(node.func.id)
            sym = binding.symbol if binding and binding.kind == 'class' else node.func.id
            return self.classes.get(sym)
        if not isinstance(node.func, ast.Attribute):
            return None
        recv_info = self._class_info_for_attr_value(node.func.value)
        if recv_info:
            if node.func.attr in recv_info.method_sigs:
                return self._class_info_for_type(self._sig_return_storage(recv_info.method_sigs[node.func.attr]))
            prop = recv_info.properties.get(node.func.attr)
            if prop and prop.getter_sig:
                return self._class_info_for_type(self._sig_return_storage(prop.getter_sig))
        return None

    def _class_info_for_attr_value(self, node: ast.expr) -> ClassInfo | None:
        if isinstance(node, ast.Name):
            return self._class_info_for_expr(node)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and self._name_refers_to_class(node.value.id):
            return self._class_info_for_ref(node.value.id)
        if isinstance(node, ast.Call):
            return self._class_info_for_call(node)
        return None

    def _emit_str_bool(self, node: ast.expr) -> str:
        return self._truthiness_condition(node)

    def _boxing_pointer_truthiness(self, node: ast.expr, cpp: str) -> str | None:
        """``@boxing`` 堆节点指针 ``T*`` → ``(ptr != nullptr)``。"""
        t = self._infer_expr_cpp_type(node).strip().rstrip('&')
        if not t.endswith('*'):
            return None
        base = t[:-1].strip()
        for info in self.classes.values():
            if info.is_boxing and info.cpp_name() == base:
                return f'({cpp} != nullptr)'
        return None

    def _truthiness_condition(self, node: ast.expr) -> str:
        """表达式在 ``if`` / ``and`` / ``or`` 中的真假条件（C++ ``bool``）。"""
        if isinstance(node, ast.Compare):
            return self.visit(node)
        cpp = self._paren_expr(self.visit(node))
        return self._truthiness_condition_from_cpp(node, cpp)

    def _truthiness_condition_from_cpp(self, node: ast.expr, cpp: str) -> str:
        """对已求值一次的 ``cpp`` 生成真假条件（三目/``if``/``while``；``__bool__`` 类经 ``static_cast<PyBool>``）。"""
        t = self._infer_expr_cpp_type(node).strip().rstrip('&')
        boxing = self._boxing_pointer_truthiness(node, cpp)
        if boxing is not None:
            return boxing
        if t in ('bool', cpp_ident('bool')):
            return cpp
        if t in (cpp_ident('int'), cpp_ident('int64'), cpp_ident('float'), cpp_ident('float64'), cpp_ident('char'), 'int', 'float'):
            return f'({cpp})'
        if is_char_type(t, classes=self.classes):
            return f'({cpp})'
        if t in ('c_str', 'const char*'):
            return f'({cpp} != 0)'
        if is_refcount_type(t, classes=self.classes):
            pb = cpp_ident('PyBool')
            if cpp == 'this':
                return f'(static_cast<{pb}>(*this))'
            return f'(static_cast<{pb}>({cpp}))'
        if t.endswith('*'):
            return f'({cpp} != 0)'
        info = self._class_info_for_expr(node) or self._class_info_for_type(t)
        if info and '__bool__' in info.methods:
            pb = cpp_ident('PyBool')
            if cpp == 'this':
                return f'(static_cast<{pb}>(*this))'
            return f'(static_cast<{pb}>({cpp}))'
        if is_delegate_type(t, delegate_names=frozenset(self.delegates.keys())):
            pb = cpp_ident('PyBool')
            return f'(static_cast<{pb}>({cpp}))'
        from .analysis.type_pred import is_frozenlist_type, is_list_type
        if is_list_type(t, classes=self.classes) or is_frozenlist_type(t, classes=self.classes):
            pb = cpp_ident('PyBool')
            if cpp == 'this':
                return f'(static_cast<{pb}>(*this))'
            return f'(static_cast<{pb}>({cpp}))'
        return f'({cpp})'

    @staticmethod
    def _is_trivial_boolop_operand(node: ast.expr) -> bool:
        """变量/字面量/简单成员或下标：``and``/``or`` 可在外层直接嵌套三目。"""
        match node:
            case ast.Name() | ast.Constant():
                return True
            case ast.Attribute(value=ast.Name(), attr=_):
                return True
            case ast.Subscript(value=ast.Name(), slice=_):
                return True
            case _:
                return False

    def _lower_boolop_or(self, values: list[ast.expr]) -> str:
        """``a or b``：短路；为真返回左操作数，否则右操作数（对齐 CPython）。"""
        if len(values) == 1:
            return self._paren_expr(self.visit(values[0]))
        if any((not self._is_trivial_boolop_operand(v) for v in values)):
            return self._lower_boolop_or_iife(values)
        acc = self._paren_expr(self.visit(values[-1]))
        for expr in reversed(values[:-1]):
            val = self._paren_expr(self.visit(expr))
            cond = self._truthiness_condition_from_cpp(expr, val)
            acc = f'({cond} ? {val} : {acc})'
        return acc

    def _lower_boolop_or_iife(self, values: list[ast.expr]) -> str:
        stmts: list[str] = []
        acc = self._paren_expr(self.visit(values[-1]))
        for expr in reversed(values[:-1]):
            v = temp_name('bo')
            stmts.append(f'auto {v} = {self.visit(expr)};')
            cond = self._truthiness_condition_from_cpp(expr, v)
            acc = f'({cond} ? {v} : {acc})'
        stmts.append(f'return {acc};')
        from .emit.iife_emit import emit_iife
        return emit_iife(None, stmts)

    def _lower_boolop_and(self, values: list[ast.expr]) -> str:
        """``a and b``：短路；为假返回左操作数，否则右操作数。"""
        if len(values) == 1:
            return self._paren_expr(self.visit(values[0]))
        if any((not self._is_trivial_boolop_operand(v) for v in values)):
            return self._lower_boolop_and_iife(values)
        acc = self._paren_expr(self.visit(values[-1]))
        for expr in reversed(values[:-1]):
            val = self._paren_expr(self.visit(expr))
            cond = self._truthiness_condition_from_cpp(expr, val)
            acc = f'({cond} ? {acc} : {val})'
        return acc

    def _lower_boolop_and_iife(self, values: list[ast.expr]) -> str:
        stmts: list[str] = []
        acc = self._paren_expr(self.visit(values[-1]))
        for expr in reversed(values[:-1]):
            v = temp_name('bo')
            stmts.append(f'auto {v} = {self.visit(expr)};')
            cond = self._truthiness_condition_from_cpp(expr, v)
            acc = f'({cond} ? {acc} : {v})'
        stmts.append(f'return {acc};')
        from .emit.iife_emit import emit_iife
        return emit_iife(None, stmts)

    def _expr_is_str_value(self, node: ast.expr) -> bool:
        if is_str_type(self._infer_expr_cpp_type(node)):
            return True
        info = self._class_info_for_expr(node)
        return info is not None and info.name == 'str'

    def _visit_value_expr(self, node: ast.expr) -> str:
        """按值传递的实参：成员函数内 ``self`` → ``*this``。"""
        if isinstance(node, ast.Name) and node.id == 'self':
            if self.class_info and (not self.class_info.is_refcount):
                return '*this'
        return self.visit(node)

    def _static_property_read(self, class_name: str, attr: str) -> str | None:
        info = self.classes.get(class_name)
        if not info or attr not in info.static_properties:
            return None
        getter = self._property_getter_cpp_name(info, attr)
        from .analysis.ir import qualified_class_static_callee
        return f'{qualified_class_static_callee(info, getter)}()'

    def _binop_dunder(self, op: ast.operator) -> str | None:
        match op:
            case ast.Add():
                return '__add__'
            case ast.Sub():
                return '__sub__'
            case ast.Mult():
                return '__mul__'
            case ast.Div():
                return '__truediv__'
            case ast.FloorDiv():
                return '__floordiv__'
            case ast.Mod():
                return '__mod__'
            case ast.Pow():
                return '__pow__'
            case ast.LShift():
                return '__lshift__'
            case ast.RShift():
                return '__rshift__'
            case ast.BitOr():
                return '__or__'
            case ast.BitXor():
                return '__xor__'
            case ast.BitAnd():
                return '__and__'
            case ast.MatMult():
                return '__matmul__'
            case _:
                return None

    def _binop_rdunder(self, op: ast.operator) -> str | None:
        match op:
            case ast.Add():
                return '__radd__'
            case ast.Sub():
                return '__rsub__'
            case ast.Mult():
                return '__rmul__'
            case ast.Div():
                return '__rtruediv__'
            case ast.FloorDiv():
                return '__rfloordiv__'
            case ast.Mod():
                return '__rmod__'
            case ast.Pow():
                return '__rpow__'
            case ast.LShift():
                return '__rlshift__'
            case ast.RShift():
                return '__rrshift__'
            case ast.BitOr():
                return '__ror__'
            case ast.BitXor():
                return '__rxor__'
            case ast.BitAnd():
                return '__rand__'
            case ast.MatMult():
                return '__rmatmul__'
            case _:
                return None

    def _binop_iform(self, op: ast.operator) -> str | None:
        match op:
            case ast.Add():
                return '__iadd__'
            case ast.Sub():
                return '__isub__'
            case ast.Mult():
                return '__imul__'
            case ast.Div():
                return '__itruediv__'
            case ast.FloorDiv():
                return '__ifloordiv__'
            case ast.Mod():
                return '__imod__'
            case ast.Pow():
                return '__ipow__'
            case ast.LShift():
                return '__ilshift__'
            case ast.RShift():
                return '__irshift__'
            case ast.BitOr():
                return '__ior__'
            case ast.BitXor():
                return '__ixor__'
            case ast.BitAnd():
                return '__iand__'
            case ast.MatMult():
                return '__imatmul__'
            case _:
                return None

    @staticmethod
    def _cpp_augassign_op(op: ast.operator) -> str | None:
        match op:
            case ast.Add():
                return '+='
            case ast.Sub():
                return '-='
            case ast.Mult():
                return '*='
            case ast.Div():
                return '/='
            case ast.Mod():
                return '%='
            case ast.LShift():
                return '<<='
            case ast.RShift():
                return '>>='
            case ast.BitOr():
                return '|='
            case ast.BitXor():
                return '^='
            case ast.BitAnd():
                return '&='
            case _:
                return None

    @staticmethod
    def _paren_expr(recv: str) -> str:
        if recv.isidentifier() or recv == 'this':
            return recv
        return f'({recv})'

    def _member_call(self, receiver: ast.expr, method: str, args: str='') -> str:
        recv = self.visit(receiver)
        sep = self._member_access(recv)
        if sep == '.' and isinstance(receiver, ast.Name) and self.scope:
            t = self._scope_storage(receiver.id)
            if self._uses_ptr_access(t):
                sep = '->'
        if sep == '.' and isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name) and (receiver.value.id == 'self') and self.class_info:
            ft = self._field_storage(receiver.attr)
            if self._uses_ptr_access(ft):
                sep = '->'
        if args:
            return f'{recv}{sep}{method}({args})'
        return f'{recv}{sep}{method}()'

    @staticmethod
    def _is_none_constant(node: ast.expr | None) -> bool:
        if isinstance(node, ast.Constant) and node.value is None:
            return True
        return isinstance(node, ast.Name) and node.id == 'None'

    def _coerce_expr_to_cpp_type(self, expr: str, cpp_type: str, *, rhs_node: ast.expr | None=None) -> str:
        tgt = strip_cpp_ref(cpp_type) if cpp_type else ''
        if rhs_node is not None and self._is_none_constant(rhs_node):
            if tgt == cpp_ident('PyNone'):
                return f"{cpp_ident('PyNone')}()"
        if rhs_node is not None:
            if self._is_none_constant(rhs_node) and tgt and is_refcount_type(tgt):
                return f'{strip_cpp_ref(tgt)}()'
            if isinstance(rhs_node, ast.Name) and rhs_node.id == 'self' and tgt and is_refcount_type(tgt) and self.class_info and self.class_info.is_refcount:
                from .analysis.type_extract import refcount_inner_type
                inner = refcount_inner_type(tgt)
                cn = self.class_info.cpp_name()
                if inner and (inner == cn or inner.endswith(f'::{cn}')):
                    return f'{strip_cpp_ref(tgt)}::from_object(this)'
        if rhs_node is not None:
            rhs_t = strip_cpp_ref(self._infer_expr_cpp_type(rhs_node) or '')
            if is_iter_result_type(rhs_t) and tgt and (not is_iter_result_type(tgt)):
                return iter_result_value_cpp(expr)
            if is_fault_result_type(rhs_t) and tgt and (not is_fault_result_type(tgt)):
                return fault_result_value_expr(expr)
            if is_optional_type(rhs_t) and tgt and (not is_optional_type(tgt)):
                inner = optional_inner_type(rhs_t)
                if not inner or inner == tgt:
                    return option_unbox_expr(expr)
            if tgt and is_py_generator_type(tgt) and rhs_t and is_concrete_generator_type(rhs_t):
                return cpp_make_py_generator_expr(tgt, expr)
            if tgt and is_py_coroutine_type(tgt) and rhs_t and is_concrete_coroutine_type(rhs_t):
                return cpp_make_py_coroutine_expr(tgt, expr)
            if tgt and is_py_async_generator_type(tgt) and rhs_t and is_concrete_coroutine_type(rhs_t):
                return cpp_make_py_async_generator_expr(tgt, expr)
            from .analysis.ir import cpp_make_erased_storage_expr
            from .analysis.type_pred import is_erased_protocol_storage_type
            tgt_b = strip_cpp_ref(tgt) if tgt else ''
            rhs_b = strip_cpp_ref(rhs_t) if rhs_t else ''
            if tgt_b and is_erased_protocol_storage_type(tgt_b) and rhs_b and (rhs_b != tgt_b) and (not is_erased_protocol_storage_type(rhs_b)):
                return cpp_make_erased_storage_expr(tgt_b, expr)
            if is_optional_type(tgt):
                if is_optional_type(rhs_t):
                    return expr
                if isinstance(rhs_node, ast.Call) and isinstance(rhs_node.func, ast.Attribute):
                    if rhs_node.func.attr in ('Some', 'None_'):
                        return expr
                if isinstance(rhs_node, ast.Call):
                    ret_t = strip_cpp_ref(self._infer_expr_cpp_type(rhs_node) or '')
                    if is_optional_type(ret_t):
                        return expr
                if self._is_none_constant(rhs_node):
                    if tgt and is_refcount_type(tgt):
                        return f'{strip_cpp_ref(tgt)}()'
                    return cpp_option_none_expr(tgt)
                inner = optional_inner_type(tgt)
                val = self._coerce_expr_to_cpp_type(expr, inner, rhs_node=None) if inner else expr
                return cpp_option_some_expr(tgt, val)
        if tgt and is_char_type(tgt) and (not expr.startswith('PyChar(')):
            if rhs_node is not None and is_char_type(self._infer_expr_cpp_type(rhs_node)):
                return expr
            return f'PyChar({expr})'
        if tgt and is_byte_type(tgt) and (not expr.startswith('PyByte(')):
            return f'PyByte({expr})'
        if tgt and is_str_type(tgt) and (rhs_node is not None):
            rhs_t = strip_cpp_ref(self._infer_expr_cpp_type(rhs_node) or '')
            if rhs_t and is_char_type(rhs_t, classes=self.classes):
                ps = cpp_ident('str')
                return f'{ps}({expr})'
            if rhs_t and is_byte_heap_array_type(rhs_t, classes=self.classes):
                pb = cpp_ident('bytes')
                return f'{pb}({expr})'
            if rhs_t and (not is_str_type(rhs_t)):
                info = self._class_info_for_expr(rhs_node) or self._class_info_for_type(rhs_t)
                if info and has_effective_str(info, self):
                    ps = cpp_ident('str')
                    return f'static_cast<{ps}>({self._paren_expr(expr)})'
        coerced = self._coerce_json_doc_cursor_read(expr, cpp_type, rhs_node=rhs_node)
        if coerced is not None:
            return coerced
        tgt = strip_cpp_ref(cpp_type) if cpp_type else ''
        if tgt and rhs_node is not None:
            rhs_t = strip_cpp_ref(self._infer_expr_cpp_type(rhs_node) or '')
            if tgt.endswith('&') and rhs_t.endswith('*'):
                return f'(*{expr})'
            if tgt.endswith('*') and rhs_t and (not rhs_t.endswith('*')) and (not is_refcount_type(rhs_t)) and (not expr.startswith('&')) and isinstance(rhs_node, ast.Name):
                return f'&{expr}'
        return expr

    def _overload_param_match_score(self, param_t: str, arg_t: str) -> int:
        """``@overload`` 首参 C++ 类型与实参类型的匹配分（越高越优先）。"""
        pt = strip_cpp_ref(param_t or '')
        at = strip_cpp_ref(arg_t or '')
        if not pt or not at:
            return 0
        if pt == at:
            return 100
        if is_list_type(pt) and is_list_type(at):
            pe = list_elem_type(pt) or ''
            ae = list_elem_type(at) or ''
            if pe and ae and (pe == ae):
                return 95
            return 90
        if is_stack_array_type(pt) and is_stack_array_type(at):
            return 90
        if is_char_stack_array_type(pt) and is_char_stack_array_type(at):
            return 90
        if is_list_type(pt) or is_stack_array_type(pt):
            return 0
        if is_bytes_type(pt) and is_bytes_type(at):
            return 80
        if is_bytes_type(pt) and is_str_type(at):
            return 0
        if is_str_type(pt) and is_bytes_type(at):
            return 0
        if is_str_type(pt) and is_str_type(at):
            return 80
        if is_str_type(pt) and (not is_str_type(at)):
            return 0
        return 1

    def _pick_method_overload_for_call(self, info: ClassInfo, overloads: list[ast.FunctionDef], call: ast.Call) -> ast.FunctionDef | None:
        pos = len(call.args)
        exact: list[ast.FunctionDef] = []
        loose: list[ast.FunctionDef] = []
        for ov in overloads:
            params = [a for a in ov.args.args if a.arg not in ('self', 'cls')]
            if len(params) == pos:
                exact.append(ov)
            elif pos <= len(params):
                loose.append(ov)
        candidates = exact or loose
        if not candidates:
            return overloads[-1] if overloads else None
        if len(candidates) == 1:
            return candidates[0]
        if not call.args:
            return candidates[0]
        arg_t = self._infer_expr_cpp_type(call.args[0]) or ''
        scored: list[tuple[int, ast.FunctionDef]] = []
        for ov in candidates:
            sig = info.method_sig_for(ov)
            if sig is None:
                continue
            param_names = [a.arg for a in ov.args.args if a.arg not in ('self', 'cls')]
            if not param_names:
                continue
            pt = self._msig_param_storage(sig, param_names[0], fallback='')
            scored.append((self._overload_param_match_score(pt, arg_t), ov))
        if not scored:
            return candidates[0]
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return scored[0][1]
        return candidates[0]

    def _method_def_for_call(self, info: ClassInfo, method_name: str, call: ast.Call | None) -> ast.FunctionDef | None:
        method = info.methods.get(method_name)
        if method is None and info.class_type_if_specs:
            from .passes.class_type_if import class_type_if_method_def
            method = class_type_if_method_def(info, method_name)
        if method is not None:
            return method
        overloads = info.method_overloads.get(method_name)
        if not overloads:
            return None
        if call is None:
            return overloads[-1]
        picked = self._pick_method_overload_for_call(info, overloads, call)
        if picked is not None:
            return picked
        return overloads[-1]

    def _pick_module_function_overload_for_call(self, module_path: str, name: str, overloads: list[ast.FunctionDef], call: ast.Call) -> ast.FunctionDef | None:
        pos = len(call.args)
        exact: list[ast.FunctionDef] = []
        loose: list[ast.FunctionDef] = []
        for ov in overloads:
            params = [a.arg for a in ov.args.args if a.arg not in ('self', 'cls')]
            if len(params) == pos:
                exact.append(ov)
            elif pos <= len(params):
                loose.append(ov)
        candidates = exact or loose
        if not candidates:
            return overloads[-1] if overloads else None
        if len(candidates) == 1:
            return candidates[0]
        if not call.args:
            return candidates[0]
        arg_t = self._infer_expr_cpp_type(call.args[0]) or ''
        sigs = self.module_function_overload_sigs.get((module_path, name), [])
        scored: list[tuple[int, ast.FunctionDef]] = []
        for ov in candidates:
            idx = next((i for i, o in enumerate(overloads) if o is ov), -1)
            if idx < 0 or idx >= len(sigs):
                continue
            fsig = sigs[idx]
            param_names = [a.arg for a in ov.args.args if a.arg not in ('self', 'cls')]
            if not param_names:
                continue
            pt = self._msig_param_storage(fsig, param_names[0], fallback='')
            scored.append((self._overload_param_match_score(pt, arg_t), ov))
        if not scored:
            return candidates[0]
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return scored[0][1]
        return candidates[0]

    def _module_function_def_for_call(self, module_path: str, name: str, call: ast.Call | None) -> ast.FunctionDef | None:
        func = next((f for mp, f in self.module_functions if mp == module_path and f.name == name), None)
        if func is not None:
            return func
        overloads = self.module_function_overloads.get((module_path, name))
        if not overloads:
            return None
        if call is None:
            return overloads[-1]
        picked = self._pick_module_function_overload_for_call(module_path, name, overloads, call)
        if picked is not None:
            return picked
        return overloads[-1]

    def _ordered_method_param_cpp_types(self, info: ClassInfo, method_name: str, *, call: ast.Call | None=None) -> list[str]:
        method = self._method_def_for_call(info, method_name, call)
        if method is None:
            return []
        sig = info.method_sig_for(method)
        if sig is None:
            return []
        out: list[str] = []
        for arg in method.args.args:
            if arg.arg in ('self', 'cls'):
                continue
            out.append(self._msig_param_storage(sig, arg.arg, fallback=''))
        if sig.variadic_template is not None:
            out.append(self._msig_param_storage(sig, sig.variadic_template.param_name, fallback=''))
        elif sig.vararg_pack is not None:
            out.append(sig.vararg_pack.cpp_type)
        return out

    def _dict_key_cpp_type(self, base_expr: ast.expr) -> str | None:
        t = self._expr_cpp_type(base_expr)
        if not t and isinstance(base_expr, ast.Name) and self.scope:
            t = self._scope_storage(base_expr.id)
        if not t or not is_dict_type(t):
            return None
        inner = dict_type_args(t) or ''
        key = inner.split(',')[0].strip() if inner else ''
        return key or None

    def _coerce_dict_key_expr(self, base_expr: ast.expr, key_node: ast.expr) -> str:
        kt = self._dict_key_cpp_type(base_expr)
        v = self.visit(key_node)
        if kt:
            return self._coerce_expr_to_cpp_type(v, kt)
        return v

    def _subscript_container_elem_type(self, base_expr: ast.expr) -> str | None:
        t = self._expr_cpp_type(base_expr)
        if not t and isinstance(base_expr, ast.Attribute):
            ft = self._field_cpp_type_for_attribute(base_expr.value, base_expr.attr)
            if ft:
                t = ft
        if not t:
            t = self._infer_expr_cpp_type(base_expr) or ''
        return cpp_array_elem_type(t) or list_elem_type(t)

    def _dict_value_cpp_type(self, base_expr: ast.expr) -> str | None:
        t = self._expr_cpp_type(base_expr)
        if not t and isinstance(base_expr, ast.Name) and self.scope:
            t = self._scope_storage(base_expr.id)
        if not t or not is_dict_type(t):
            return None
        inner = dict_type_args(t) or ''
        parts = [p.strip() for p in inner.split(',')]
        if len(parts) >= 2:
            return parts[1]
        return None

    def _coerce_subscript_assign_value(self, base_expr: ast.expr, value: str) -> str:
        et = self._subscript_container_elem_type(base_expr)
        if not et:
            et = self._dict_value_cpp_type(base_expr)
        if et:
            return self._coerce_expr_to_cpp_type(value, et)
        return value

    def _method_return_cpp_type(self) -> str | None:
        if self.current_method is None:
            return None
        if self.class_info:
            sig = self.class_info.method_sig_for(self.current_method)
            ret_storage = self._sig_return_storage(sig)
            if sig is not None and ret_storage and (ret_storage != 'void'):
                return ret_storage
        mp = self._active_module_path()
        fsig = self.function_sigs.get((mp, self.current_method.name))
        fsig_ret = self._sig_return_storage(fsig)
        if fsig is not None and fsig_ret and (fsig_ret != 'void'):
            return fsig_ret
        if self.current_method.returns is None:
            return None
        return self._parse_storage_type(self.current_method.returns, self._active_type_params())

    def _emit_single_pychar_as_pystr(self, node: ast.expr) -> str:
        """``str + char``：单码点经 ``PyStr(PyChar)`` 构造（与 ``str(c)`` 一致）。"""
        ps = cpp_ident('str')
        v = self._visit_value_expr(node)
        t = strip_cpp_ref(self._infer_expr_cpp_type(node) or '')
        if is_char_type(t, classes=self.classes) or t in ('PyChar', 'char'):
            return f'{ps}({v})'
        return f'{ps}(PyChar({v}))'

    def _coerce_dunder_other_for_str_add(self, dunder: str, receiver: ast.expr, other: ast.expr) -> str:
        if dunder not in ('__add__', '__radd__'):
            return self._visit_value_expr(other)
        ps = cpp_ident('str')
        if dunder == '__add__':
            left_ty = self._infer_expr_cpp_type(receiver)
            right_ty = self._infer_expr_cpp_type(other)
            if is_str_type(left_ty) or left_ty == ps or self._expr_is_str_value(receiver):
                rt = strip_cpp_ref(right_ty or '')
                if is_char_type(rt, classes=self.classes) or rt in ('PyChar', 'char') or not rt:
                    return self._emit_single_pychar_as_pystr(other)
        else:
            left_ty = self._infer_expr_cpp_type(other)
            right_ty = self._infer_expr_cpp_type(receiver)
            if is_str_type(right_ty) or right_ty == ps or self._expr_is_str_value(other):
                if is_char_type(left_ty, classes=self.classes) or left_ty in ('PyChar', 'char'):
                    return self._emit_single_pychar_as_pystr(other)
        return self._visit_value_expr(other)

    def _emit_dunder_call(self, receiver: ast.expr, dunder: str, other: ast.expr) -> str:
        recv_ty = strip_cpp_ref(self._infer_expr_cpp_type(receiver) or '')
        left_info = self._class_info_for_expr(receiver) or self._class_info_for_type(recv_ty)
        if dunder == '__mul__' and left_info and self._class_info_has_method(left_info, '__matmul__'):
            right_t = strip_cpp_ref(self._infer_expr_cpp_type(other) or '')
            right_info = self._class_info_for_expr(other) or self._class_info_for_type(right_t)
            lt = strip_cpp_ref(recv_ty or '')
            if right_info is left_info or (lt and right_t and (lt == right_t or lt.split('::')[-1] == right_t.split('::')[-1])):
                dunder = '__matmul__'
        recv = self._paren_expr(self.visit(receiver))
        sep = self._member_access(recv)
        rhs = self._coerce_dunder_other_for_str_add(dunder, receiver, other)
        return f'{recv}{sep}{dunder}({rhs})'

    def _try_enum_binop(self, node: ast.BinOp) -> str | None:
        """``@enum(flag=True)`` 的 ``|`` / ``&`` / ``^``（底层整型位运算后转回枚举）。"""
        if not isinstance(node.op, (ast.BitOr, ast.BitAnd, ast.BitXor)):
            return None
        left_info = self._class_info_for_expr(node.left)
        right_info = self._class_info_for_expr(node.right)
        if left_info is None or right_info is None or left_info is not right_info or (not left_info.is_enum) or (not left_info.enum_is_flag):
            return None
        sym = '|' if isinstance(node.op, ast.BitOr) else '&' if isinstance(node.op, ast.BitAnd) else '^'
        cpp = left_info.cpp_name()
        u = left_info.enum_underlying_cpp
        l, r = (self.visit(node.left), self.visit(node.right))
        return f'static_cast<{cpp}>(static_cast<{u}>({l}) {sym} static_cast<{u}>({r}))'

    def _try_dunder_binop(self, node: ast.BinOp) -> str | None:
        dunder = self._binop_dunder(node.op)
        if dunder is None:
            return None
        if isinstance(node.op, ast.Mod):
            if self._is_str_expr(node.left):
                return None
        left_t = self._infer_expr_cpp_type(node.left)
        left_info = self._class_info_for_expr(node.left)
        if left_info is None and left_t:
            left_info = self._class_info_for_type(strip_cpp_ref(left_t))
        if left_info is None and is_str_type(left_t):
            left_info = self.classes.get('str')
        if isinstance(node.op, ast.Mult) and left_info and self._class_info_has_method(left_info, '__matmul__'):
            right_t = strip_cpp_ref(self._infer_expr_cpp_type(node.right) or '')
            lt = strip_cpp_ref(left_t or '')
            right_info = self._class_info_for_expr(node.right)
            if right_info is None and right_t:
                right_info = self._class_info_for_type(right_t)
            if right_info is left_info or (
                lt and right_t and (lt == right_t or lt.split('::')[-1] == right_t.split('::')[-1])
            ):
                return self._emit_dunder_call(node.left, '__matmul__', node.right)
        if left_info and self._class_info_has_method(left_info, dunder):
            return self._emit_dunder_call(node.left, dunder, node.right)
        if is_varint_type(left_t):
            return self._emit_dunder_call(node.left, dunder, node.right)
        rdunder = self._binop_rdunder(node.op)
        if rdunder:
            right_t = self._infer_expr_cpp_type(node.right)
            right_info = self._class_info_for_expr(node.right)
            if right_info is None and right_t:
                right_info = self._class_info_for_type(strip_cpp_ref(right_t))
            if right_info is None and is_str_type(right_t):
                right_info = self.classes.get('str')
            if right_info and self._class_info_has_method(right_info, rdunder):
                return self._emit_dunder_call(node.right, rdunder, node.left)
            if is_varint_type(right_t):
                return self._emit_dunder_call(node.right, rdunder, node.left)
        return None

    def _receiver_method_return_cpp_type(self, info: ClassInfo, method: str, receiver: ast.expr | None=None, call_args: list[ast.expr] | None=None) -> str | None:
        """实例方法返回 C++ 类型（含仅 ``@overload`` 声明的方法）。"""
        from .analysis.ir import cpp_template_base_and_args, specialize_cpp_template_placeholders
        from .analysis.variadic_template import parse_function_type_params
        sig = info.method_sigs.get(method)
        ret = self._sig_return_storage(sig) if sig is not None else None
        if ret is None:
            ov_sigs = info.method_overload_sigs.get(method)
            if ov_sigs:
                ret = self._sig_return_storage(ov_sigs[0])
        if ret is None or receiver is None:
            return ret
        recv_cpp = strip_cpp_ref(self._infer_expr_cpp_type(receiver) or '')
        if not recv_cpp:
            return ret

        def _default_cpp(param: str) -> str | None:
            dv = info.type_param_defaults.get(param)
            if dv is None or self.type_parser is None:
                return None
            return self.type_parser.parse_type(dv, set(info.type_params))
        if info.type_params:
            ret = specialize_cpp_template_placeholders(ret, class_cpp_name=info.cpp_name(), type_params=list(info.type_params), recv_cpp=recv_cpp, default_cpp_for_param=_default_cpp)
        method_node = info.methods.get(method)
        if method_node is not None and call_args:
            method_regular, _method_capture, method_tvt = parse_function_type_params(method_node)
            method_extra = list(method_regular)
            if method_tvt:
                method_extra.append(method_tvt)
            if method_extra:
                other_cpp = strip_cpp_ref(self._infer_expr_cpp_type(call_args[0]) or '')
                other_parsed = cpp_template_base_and_args(other_cpp)
                if other_parsed is not None and other_parsed[0] == info.cpp_name() and other_parsed[1]:
                    import re
                    for param in method_extra:
                        ret = re.sub(f'\\b{re.escape(param)}\\b', other_parsed[1][0], ret)
        return ret

    @staticmethod
    def _class_info_has_method(info: ClassInfo, name: str) -> bool:
        return name in info.methods or name in info.method_overloads

    def _class_info_for_receiver(self, node: ast.expr) -> ClassInfo | None:
        """属性读/``@property`` 派发：推断接收者 ``ClassInfo``（含 ``self`` 与构造调用）。"""
        if isinstance(node, ast.Name):
            if node.id == 'self':
                return self.class_info or self._self_type_class
            if node.id == 'Self':
                static_host = self._static_generator_host_class_info()
                if static_host is not None:
                    return static_host
                return self._active_class_info()
            if node.id in self.classes:
                return self.classes[node.id]
            t = self._lookup_var_type(node.id)
            if not t and self.scope:
                t = self._scope_storage(node.id)
            if t:
                info = self._class_info_for_type(t)
                if info:
                    return info
                if info:
                    return info
        if isinstance(node, ast.Subscript):
            elem_t = self._subscript_container_elem_type(node.value)
            if elem_t:
                info = self._class_info_for_type(elem_t)
                if info is not None:
                    return info
            t = self._infer_expr_cpp_type(node.value)
            return self._class_info_for_type(t)
        if isinstance(node, ast.Call):
            t = self._constructor_type(node)
            if t:
                return self._class_info_for_type(t)
            if isinstance(node.func, ast.Attribute) and node.func.attr == '__getitem__':
                elem_t = self._subscript_container_elem_type(node.func.value)
                if elem_t:
                    info = self._class_info_for_type(elem_t)
                    if info is not None:
                        return info
        if isinstance(node, ast.Attribute):
            ft = self._field_cpp_type_for_attribute(node.value, node.attr)
            if ft:
                info = self._class_info_for_type(ft)
                if info:
                    return info
            t = self._infer_expr_cpp_type(node)
            return self._class_info_for_type(t)
        return self._class_info_for_expr(node)

    def _is_resolved_instance_member(self, info: ClassInfo, attr: str) -> bool:
        if attr in info.fields or attr in info.properties:
            return True
        if attr in info.methods:
            return True
        return False

    def _try_emit_dunder_getattr(self, receiver: ast.expr, attr: str) -> str | None:
        info = self._class_info_for_receiver(receiver)
        if info is None or self._is_resolved_instance_member(info, attr):
            return None
        if '__getattr__' not in info.methods:
            return None
        recv, sep = self._receiver_access(receiver)
        return f'{recv}{sep}__getattr__({str_cpp_from_literal(attr)})'

    def _coerce_json_doc_cursor_read(self, expr: str, cpp_type: str, *, rhs_node: ast.expr | None=None) -> str | None:
        if rhs_node is None:
            return None
        rhs_t = strip_cpp_ref(self._infer_expr_cpp_type(rhs_node))
        if not is_json_doc_cursor_type(rhs_t):
            return None
        tgt = strip_cpp_ref(cpp_type) if cpp_type else ''
        if is_str_type(tgt):
            return f'({expr}).read_str()'
        if is_int_type(tgt) or is_int64_type(tgt) or is_varint_type(tgt):
            return f'({expr}).read_int()'
        ps_bool = cpp_ident('bool')
        if tgt in ('bool', ps_bool):
            return f'({expr}).read_bool()'
        return None

    def _should_use_cpp_attr_dispatch(self, receiver: ast.expr) -> bool:
        """接收者为当前函数的模板形参（如未注解的 ``node``→``T0``）时用宏派发。"""
        if self._class_info_for_receiver(receiver) is not None:
            return False
        if not isinstance(receiver, ast.Name) or not self.scope or (not self.current_method):
            return False
        mp = self._active_module_path()
        fsig = self.function_sigs.get((mp, self.current_method.name))
        if fsig is None or not fsig.func_ft.template_names:
            return False
        pt = self._scope_storage(receiver.id)
        if not pt:
            return False
        ft = fsig.func_ft
        if pt in ft.template_names:
            return self._is_unannotated_template_param_name(pt)
        bound = ft.arg_types.get(pt)
        if bound and bound in ft.template_names:
            return self._is_unannotated_template_param_name(bound)
        return False

    @staticmethod
    def _is_unannotated_template_param_name(name: str) -> bool:
        """PEP 695 命名形参（``Coro``）按值类类型用 ``.``；``T0`` 等缺注解形参才走宏。"""
        import re
        return bool(re.fullmatch('T\\d+', name))

    def _receiver_named_class_template_param(self, receiver: ast.expr) -> bool:
        if not isinstance(receiver, ast.Name) or not self.scope or (not self.current_method):
            return False
        mp = self._active_module_path()
        fsig = self.function_sigs.get((mp, self.current_method.name))
        if fsig is None or not fsig.func_ft.template_names:
            return False
        pt = self._scope_storage(receiver.id)
        if not pt:
            return False
        t = strip_cpp_ref(pt).strip()
        return t in fsig.func_ft.template_names and (not self._is_unannotated_template_param_name(t))

    def _concrete_member_receiver_type(self, cpp_type: str) -> bool:
        """可静态选定 ``.``/``->`` 的 C++ 类型（非模板形参 / ``auto`` / 空）。"""
        t = strip_cpp_ref(cpp_type).strip() if cpp_type else ''
        if not t or t == 'auto':
            return False
        if self.scope and self.current_method:
            mp = self._active_module_path()
            fsig = self.function_sigs.get((mp, self.current_method.name))
            if fsig is not None and t in fsig.func_ft.template_names:
                return False
        return True

    def _use_member_dispatch_macro(self, receiver: ast.expr) -> bool:
        """无法可靠选定 ``.``/``->`` 时走 ``PY2CPP_GETATTR`` / ``SETATTR`` / ``CALL``。"""
        if self._class_info_for_receiver(receiver) is not None:
            return False
        if isinstance(receiver, ast.Name) and receiver.id == 'self':
            return False
        if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name) and (receiver.value.id == 'self') and self.class_info and (receiver.attr in self.class_info.fields):
            return False
        if isinstance(receiver, ast.Name) and self.scope:
            t = self._scope_storage(receiver.id)
            if self._concrete_member_receiver_type(t):
                return False
        if self._should_use_cpp_attr_dispatch(receiver):
            return True
        if self._receiver_named_class_template_param(receiver):
            return False
        t = self._infer_expr_cpp_type(receiver)
        if self._concrete_member_receiver_type(t):
            return False
        return True

    def _cpp_attr_object_expr(self, receiver: ast.expr) -> str:
        return self.visit(receiver)

    def _compile_diag_loc_prefix(self, node: ast.AST | None) -> str:
        from .translation_error import location_from_node
        if node is None:
            return ''
        loc = location_from_node(self, node)
        if loc is None:
            return ''
        return f'{loc.prefix()}: '

    def _begin_py2cpp_stmt(self, stmt: ast.stmt) -> None:
        self._py2cpp_current_stmt = stmt
        self._py2cpp_stmt_dispatch_prepped = False
        self._py2cpp_dispatch_checks_emitted: set[tuple[str, str]] = set()

    def _member_dispatch_receiver_cpp_type(self, receiver: ast.expr) -> str:
        obj = self._cpp_attr_object_expr(receiver)
        return f'decltype({obj})'

    def _emit_py2cpp_dispatch_check(self, kind: str, receiver: ast.expr, cpp_name: str, *, arg_types: list[str] | None=None) -> None:
        if self._py2cpp_current_stmt is None:
            return
        key = (kind, cpp_name)
        if key in self._py2cpp_dispatch_checks_emitted:
            return
        self._py2cpp_dispatch_checks_emitted.add(key)
        from .emit.compile_diagnostic_emit import compile_diag_c_utf8_literal, compile_diag_py2cpp_call, compile_diag_py2cpp_getattr, compile_diag_py2cpp_setattr
        self._emit_py2cpp_dispatch_stmt_lines()
        recv_ty = self._member_dispatch_receiver_cpp_type(receiver)
        if kind == 'getattr':
            msg = compile_diag_py2cpp_getattr(cpp_name)
            self.write_line(f'static_assert(::py2cpp::access::can_get_{cpp_name}<{recv_ty}>::value, {compile_diag_c_utf8_literal(msg)});')
        elif kind == 'setattr':
            val_ty = (arg_types or ['decltype(v)'])[0]
            msg = compile_diag_py2cpp_setattr(cpp_name)
            self.write_line(f'static_assert(::py2cpp::access::can_set_{cpp_name}<{recv_ty}, {val_ty}>::value, {compile_diag_c_utf8_literal(msg)});')
        elif kind == 'call':
            n = len(arg_types or [])
            msg = compile_diag_py2cpp_call(cpp_name, arg_count=n)
            if n == 0:
                self.write_line(f'static_assert(::py2cpp::access::can_call0_{cpp_name}<{recv_ty}>::value, {compile_diag_c_utf8_literal(msg)});')
            elif n == 1:
                self.write_line(f'static_assert(::py2cpp::access::can_call1_{cpp_name}<{recv_ty}, {arg_types[0]}>::value, {compile_diag_c_utf8_literal(msg)});')
            elif n == 2:
                self.write_line(f'static_assert(::py2cpp::access::can_call2_{cpp_name}<{recv_ty}, {arg_types[0]}, {arg_types[1]}>::value, {compile_diag_c_utf8_literal(msg)});')
            elif n == 3:
                self.write_line(f'static_assert(::py2cpp::access::can_call3_{cpp_name}<{recv_ty}, {arg_types[0]}, {arg_types[1]}, {arg_types[2]}>::value, {compile_diag_c_utf8_literal(msg)});')

    def _emit_py2cpp_dispatch_stmt_lines(self) -> None:
        if self._py2cpp_stmt_dispatch_prepped:
            return
        self._py2cpp_stmt_dispatch_prepped = True
        from .translation_error import location_from_node
        stmt = self._py2cpp_current_stmt
        loc = location_from_node(self, stmt) if stmt is not None else None
        if loc is not None and loc.lineno > 0:
            self.write_line(f'#line {loc.lineno} "{loc.display}"')

    def _cpp_getattr_expr(self, receiver: ast.expr, attr: str, *, site: ast.AST | None=None) -> str:
        cpp_attr = self._attr_cpp_name(receiver, attr)
        self._emit_py2cpp_dispatch_check('getattr', receiver, cpp_attr)
        obj = self._cpp_attr_object_expr(receiver)
        return f'PY2CPP_GETATTR({obj}, {cpp_attr})'

    def _cpp_call_expr(self, receiver: ast.expr, method: str, args: str='', *, site: ast.AST | None=None, arg_count: int | None=None) -> str:
        cpp_method = self._attr_cpp_name(receiver, method)
        arg_types: list[str] | None = None
        n = 0
        if args:
            parts = [p.strip() for p in args.split(',')]
            n = arg_count if arg_count is not None else len(parts)
            arg_types = [f'decltype({parts[i]})' for i in range(n)]
        self._emit_py2cpp_dispatch_check('call', receiver, cpp_method, arg_types=arg_types)
        obj = self._cpp_attr_object_expr(receiver)
        if not args:
            return f'PY2CPP_CALL({obj}, {cpp_method})'
        if n == 1:
            return f'PY2CPP_CALL1({obj}, {cpp_method}, {args})'
        if n == 2:
            return f'PY2CPP_CALL2({obj}, {cpp_method}, {args})'
        if n == 3:
            return f'PY2CPP_CALL3({obj}, {cpp_method}, {args})'
        raise NotImplementedError(f'PY2CPP_CALL 最多 3 个实参，收到 {n} 个')

    def _emit_cpp_setattr(self, receiver: ast.expr, attr: str, value: str, *, site: ast.AST | None=None) -> bool:
        if not self._use_member_dispatch_macro(receiver):
            return False
        cpp_attr = self._attr_cpp_name(receiver, attr)
        self._emit_py2cpp_dispatch_check('setattr', receiver, cpp_attr, arg_types=[f'decltype({value})'])
        obj = self._cpp_attr_object_expr(receiver)
        self.write_line(f'PY2CPP_SETATTR({obj}, {cpp_attr}, {value});')
        return True

    @staticmethod
    def _collect_member_dispatch_names(lines: list[str]) -> tuple[set[str], set[str]]:
        import re
        attrs: set[str] = set()
        calls: set[str] = set()
        for line in lines:
            attrs.update(re.findall('PY2CPP_GETATTR\\([^,]+,\\s*(\\w+)\\)', line))
            attrs.update(re.findall('PY2CPP_SETATTR\\([^,]+,\\s*(\\w+),', line))
            calls.update(re.findall('PY2CPP_CALL\\d?\\([^,]+,\\s*(\\w+)', line))
        return (attrs, calls)

    def _ensure_member_access_header(self) -> None:
        rel = f'{RUNTIME_PREFIX}/member_access'
        if not self._can_write_stdlib_artifact(rel):
            return
        hpath = self.runtime_output_dir / f'{rel}.h'
        guard = module_path_to_guard(rel)
        hpath.parent.mkdir(parents=True, exist_ok=True)
        note = f'{RUNTIME_PREFIX}/__init__.py'
        hpath.write_text(expand_whole_file_template('member_access.h', self.generated_at, {'source_note': note}, apply_allman=False).strip(), encoding='utf-8')

    def _inject_cpp_attr_dispatch_definitions(self) -> None:
        targets: list[list[str]] = [self.source_lines]
        targets.extend(self.per_module_source_lines.values())
        targets.extend(self.per_module_inl_lines.values())
        for target in targets:
            attrs, calls = self._collect_member_dispatch_names(target)
            if not attrs and (not calls):
                continue
            self._ensure_member_access_header()
            inc = f'#include "{RUNTIME_PREFIX}/member_access.h"'
            insert: list[str] = []
            if not any((inc in line for line in target[:40])):
                insert.extend([inc, ''])
            if attrs or calls:
                block = ['namespace py2cpp', '{', '  namespace access', '  {']
                for name in sorted(attrs):
                    block.append(f'    PY2CPP_DECLARE_GETATTR({name})')
                    block.append(f'    PY2CPP_DECLARE_SETATTR({name})')
                for name in sorted(calls):
                    block.append(f'    PY2CPP_DECLARE_CALL({name})')
                block.extend(['  } // namespace access', '} // namespace py2cpp', ''])
                insert.extend(block)
            if insert:
                self._insert_lines_after_includes(target, insert)

    @staticmethod
    def _insert_lines_after_includes(target: list[str], insert: list[str]) -> None:
        i = 0
        while i < len(target) and (target[i].startswith('#include') or target[i].startswith('//') or (not target[i].strip())):
            i += 1
        for line in reversed(insert):
            target.insert(i, line)

    def _field_cpp_type_for_attribute(self, val: ast.expr, attr: str) -> str | None:
        inner_t = self._infer_expr_cpp_type(val)
        if not inner_t:
            return None
        owner = self._class_info_for_type(inner_t)
        if owner is None:
            return None
        ft = self._field_storage(attr, info=owner)
        return ft if ft else None

    def _member_access_sep(self, receiver_expr: ast.expr, recv_cpp: str | None=None) -> str:
        """按接收者表达式的 C++ 类型选 ``.`` / ``->``（链式 ``cur.prev.next`` 等）。"""
        t = self._infer_expr_cpp_type(receiver_expr)
        if self._uses_ptr_access(t):
            return '->'
        recv = recv_cpp if recv_cpp is not None else self.visit(receiver_expr)
        return self._member_access(recv)

    def _receiver_access(self, node: ast.expr) -> tuple[str, str]:
        recv = self.visit(node)
        sep = self._member_access_sep(node, recv)
        return (recv, sep)

    def _emit_static_field_read(self, receiver: ast.expr, field: str) -> str:
        prop = self._property_read(receiver, field)
        if prop is not None:
            return prop
        if isinstance(receiver, ast.Name) and receiver.id == 'self':
            if self.class_info and field in self.class_info.static_class_fields:
                cpp = self.class_info.cpp_member_name(field)
                return f'{self.class_info.cpp_name()}::{cpp}'
            if self.class_info and (field in self.class_info.field_properties or field in self.class_info.postsetter_properties):
                getter = self._property_getter_cpp_name(self.class_info, field)
                return f'this->{getter}()'
            return f'this->{self._attr_cpp_name(receiver, field)}'
        recv, sep = self._receiver_access(receiver)
        return f'{recv}{sep}{self._attr_cpp_name(receiver, field)}'

    def _generator_host_class_info(self) -> ClassInfo | None:
        """实例方法 ``*_generator`` / ``*_coroutine`` 内 ``Self._…`` 解析到宿主类（``g_self`` 字段）。"""
        info = self.class_info
        if info is None:
            return None
        from .passes.generators import COROUTINE_SUFFIX, GENERATOR_SUFFIX, _field_name
        if not (info.name.endswith(GENERATOR_SUFFIX) or info.name.endswith(COROUTINE_SUFFIX)):
            return None
        host_field = _field_name('self')
        if host_field not in info.fields:
            return None
        host_ty = self._field_storage(host_field, info=info)
        if not host_ty:
            return None
        host = self.classes.get(host_ty)
        if host is not None:
            return host
        for candidate in self.classes.values():
            if candidate.name == host_ty or candidate.cpp_name() == host_ty:
                return candidate
        return None

    def _static_generator_host_class_info(self) -> ClassInfo | None:
        """``Path__glob_select_parts_generator`` 等静态方法生成器：从类名反推 ``Path`` 宿主。"""
        info = self.class_info
        if info is None:
            return None
        from .passes.generators import COROUTINE_SUFFIX, GENERATOR_SUFFIX
        if not (info.name.endswith(GENERATOR_SUFFIX) or info.name.endswith(COROUTINE_SUFFIX)):
            return None
        from .passes.generators import _field_name
        if _field_name('self') in info.fields:
            return None
        stem = info.name
        for suffix in (GENERATOR_SUFFIX, COROUTINE_SUFFIX):
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
                break
        else:
            return None
        best: ClassInfo | None = None
        best_prefix = -1
        for candidate in self.classes.values():
            prefix = f'{candidate.name}_'
            if stem.startswith(prefix) and len(prefix) > best_prefix:
                meth = stem[len(prefix):]
                if meth in candidate.methods:
                    best = candidate
                    best_prefix = len(prefix)
        return best

    def _active_class_info(self) -> ClassInfo | None:
        host = self._generator_host_class_info()
        if host is not None:
            return host
        return self.class_info or self._self_type_class

    def _recv_is_host_class(self, recv: str) -> bool:
        """``Self`` 或 mixin 内联后的宿主 C++ 类名（如 ``PyBytes``）。"""
        if recv == 'Self':
            return True
        static_host = self._static_generator_host_class_info()
        if static_host is not None and recv in (static_host.cpp_name(), static_host.name):
            return True
        info = self._generator_host_class_info()
        if info is not None and recv in (info.cpp_name(), info.name):
            return True
        info = self.class_info
        return info is not None and recv in (info.cpp_name(), info.name)

    def _class_static_member_ref(self, info: ClassInfo, attr: str) -> str | None:
        """``Self._helper`` / ``Cls._const`` → ``PyCls::_helper``（静态成员或 ``@staticmethod``）。"""
        from .analysis.ir import qualified_class_static_callee
        if info.is_union and attr in union_variant_names(info):
            return f'{info.cpp_name()}::{attr}'
        if info.is_enum and attr in enum_member_names(info):
            return f'{info.cpp_name()}::{attr}'
        if attr in info.static_class_fields:
            cpp = info.cpp_member_name(attr)
            if info.is_template():
                return cpp
            return f'{info.cpp_name()}::{cpp}'
        if attr in info.static_property_storage:
            return f'{info.cpp_name()}::{info.cpp_member_name(attr)}'
        sig = info.method_sigs.get(attr)
        if sig is not None and sig.is_static:
            return f'{info.cpp_name()}::{info.cpp_member_name(attr)}'
        ov_sigs = info.method_overload_sigs.get(attr)
        if ov_sigs and ov_sigs[0].is_static:
            return f'{info.cpp_name()}::{info.cpp_member_name(attr)}'
        return None

    def _emit_static_field_set(self, receiver: ast.expr, field: str, value: ast.expr) -> None:
        val = self._visit_value_expr(value)
        if self._emit_property_set(receiver, field, val):
            return
        if self._emit_cpp_setattr(receiver, field, val):
            return
        if isinstance(receiver, ast.Name) and receiver.id == 'self':
            self.write_line(f'this->{self._attr_cpp_name(receiver, field)} = {val};')
            return
        recv, sep = self._receiver_access(receiver)
        self.write_line(f'{recv}{sep}{self._attr_cpp_name(receiver, field)} = {val};')

    def _property_getter_cpp_name(self, info: ClassInfo, prop_name: str) -> str:
        """``@property def xxx`` → C++ ``xxx__get() const``。"""
        return info.cpp_member_name(property_getter_method_for(prop_name))

    def _property_setter_cpp_name(self, info: ClassInfo, prop_name: str) -> str:
        """``@property.setter`` / ``@staticproperty.setter`` → C++ ``name__set(…)``。"""
        return info.cpp_member_name(property_setter_method_for(prop_name))

    def _property_postsetter_cpp_name(self, info: ClassInfo, prop_name: str) -> str:
        """``@property.postsetter`` → C++ ``name__postset(…)``。"""
        return info.cpp_member_name(property_postsetter_method_for(prop_name))

    def _property_read(self, receiver: ast.expr, attr: str) -> str | None:
        if attr == 'view':
            view_read = read_span_view_property(self, receiver)
            if view_read is not None:
                return view_read
        recv_t = strip_cpp_ref(self._infer_expr_cpp_type(receiver) or self._expr_cpp_type(receiver) or '')
        if recv_t.startswith('PyWeakRef<') and attr in ('alive', 'value'):
            recv, sep = self._receiver_access(receiver)
            return f'{recv}{sep}{property_getter_method_for(attr)}()'
        if is_optional_type(recv_t) and attr == 'value':
            recv, sep = self._receiver_access(receiver)
            return f"{recv}{sep}{property_getter_method_for('value')}()"
        info = self._class_info_for_receiver(receiver)
        if info:
            if info.is_union and attr == '__enum__':
                recv, sep = self._receiver_access(receiver)
                return f'{recv}{sep}{property_getter_method_for(attr)}()'
            if info.inject_type_id and attr == '__class_id__':
                recv, sep = self._receiver_access(receiver)
                return f'{recv}{sep}{property_getter_method_for(attr)}()'
            if isinstance(receiver, ast.Name) and receiver.id == 'self' and (attr in info.field_properties):
                return None
            resolved = info.resolve_instance_property(attr, self.classes)
            if resolved is not None:
                owner, prop = resolved
                recv, sep = self._receiver_access(receiver)
                getter = self._property_getter_cpp_name(owner, attr)
                return f'{recv}{sep}{getter}()'
        recv_t = self._infer_expr_cpp_type(receiver) or self._expr_cpp_type(receiver) or ''
        if attr in ('done', 'value', 'return_value') and is_iter_result_type(recv_t):
            recv, sep = self._receiver_access(receiver)
            return f'{recv}{sep}{property_getter_method_for(attr)}()'
        if attr in ('ok', 'value') and is_fault_result_type(recv_t):
            recv, sep = self._receiver_access(receiver)
            return f'{recv}{sep}{property_getter_method_for(attr)}()'
        if attr in ('done', 'return_value'):
            recv, sep = self._receiver_access(receiver)
            return f'{recv}{sep}{property_getter_method_for(attr)}()'
        if self._use_member_dispatch_macro(receiver):
            return self._cpp_getattr_expr(receiver, attr)
        return None

    def _coerce_property_setter_value(self, info: ClassInfo, prop_name: str, value: str, rhs_node: ast.expr | None) -> str:
        prop = info.properties.get(prop_name)
        if prop is None:
            resolved = info.resolve_instance_property(prop_name, self.classes, need_setter=True)
            if resolved is not None:
                info, prop = resolved
        if prop is None or prop.setter_sig is None or rhs_node is None:
            return value
        pt = self._msig_param_storage(prop.setter_sig, 'value', fallback='')
        if not pt:
            return value
        return self._coerce_expr_to_cpp_type(value, pt, rhs_node=rhs_node)

    def _emit_property_set(self, receiver: ast.expr, attr: str, value: str, *, rhs_node: ast.expr | None=None) -> bool:
        if attr == 'view':
            raise NotImplementedError('``.view`` 为只读属性，不可赋值')
        info = self._class_info_for_receiver(receiver)
        if info:
            resolved = info.resolve_instance_property(attr, self.classes, need_setter=True)
            if resolved is not None:
                owner, prop = resolved
                recv, sep = self._receiver_access(receiver)
                setter = self._property_setter_cpp_name(owner, attr)
                val = self._coerce_property_setter_value(owner, attr, value, rhs_node)
                self.write_line(f'{recv}{sep}{setter}({val});')
                return True
            sp = info.static_properties.get(attr)
            if sp and (sp.setter or sp.postsetter):
                setter = self._property_setter_cpp_name(info, attr)
                val = value
                if sp.setter_sig and rhs_node is not None:
                    pt = self._msig_param_storage(sp.setter_sig, 'value', fallback='')
                    if pt:
                        val = self._coerce_expr_to_cpp_type(value, pt, rhs_node=rhs_node)
                self.write_line(f'{info.cpp_name()}::{setter}({val});')
                return True
        return self._emit_cpp_setattr(receiver, attr, value)

    def _constructor_type(self, node: ast.expr) -> str | None:
        match node:
            case ast.Call(func=ast.Name(id='Self')) if self._self_type_class:
                return self._self_type_class.storage_cpp_type()
            case ast.Call(func=ast.Name(id=name)) if self._self_type_class and name == self._self_type_class.cpp_name():
                return self._self_type_class.storage_cpp_type()
            case ast.Call(func=ast.Name(id=name)):
                binding = self._effective_import_bindings().get(name)
                if binding and binding.kind == 'function':
                    func_def = self._module_function_def_for_call(binding.module_path, binding.symbol, node)
                    if func_def is not None:
                        fsig = self.function_sigs.get((binding.module_path, func_def.name))
                        if fsig is not None:
                            from .analysis.type_emit import sig_return_storage_cpp
                            t = sig_return_storage_cpp(fsig)
                            if binding.module_path != RUNTIME_PKG and self._is_stdlib_module(binding.module_path):
                                base, _, tail = t.partition('<')
                                if tail:
                                    t = f'{qualify_symbol_in_module(binding.module_path, base)}<{tail}'
                                else:
                                    t = qualify_symbol_in_module(binding.module_path, t)
                            return t
                if binding:
                    sym = binding_cpp_name(self._effective_import_bindings(), name) or binding
                    base = sym.rsplit('::', 1)[-1]
                    info = self.classes.get(base) or self.classes.get(name)
                    if info:
                        t = info.storage_cpp_type()
                        if info.module_path != RUNTIME_PKG and self._is_stdlib_module(info.module_path):
                            base_cpp, _, tail = t.partition('<')
                            if tail:
                                t = f'{qualify_symbol_in_module(info.module_path, base_cpp)}<{tail}'
                            else:
                                t = qualify_symbol_in_module(info.module_path, t)
                        return t
                info = self.classes.get(name)
                if info is None:
                    info = self._class_info_for_type(cpp_ident(name))
                if info:
                    t = info.storage_cpp_type()
                    if info.module_path != RUNTIME_PKG and self._is_stdlib_module(info.module_path):
                        base, _, tail = t.partition('<')
                        if tail:
                            t = f'{qualify_symbol_in_module(info.module_path, base)}<{tail}'
                        else:
                            t = qualify_symbol_in_module(info.module_path, t)
                    return t
            case ast.Call(func=ast.Attribute(attr=name)):
                info = self.classes.get(name)
                if info:
                    t = info.storage_cpp_type()
                    if info.module_path != RUNTIME_PKG and self._is_stdlib_module(info.module_path):
                        base, _, tail = t.partition('<')
                        if tail:
                            t = f'{qualify_symbol_in_module(info.module_path, base)}<{tail}'
                        else:
                            t = qualify_symbol_in_module(info.module_path, t)
                    return t
            case ast.Call(func=ast.Subscript(value=ast.Attribute(value=recv, attr=method), slice=sl)):
                info = self._class_info_for_expr(recv)
                if info is not None:
                    rt = templated_instance_call_return_type(self, info, method, sl)
                    if rt is not None:
                        return rt
            case _:
                return None

    def _member_call_with_arg(self, receiver: ast.expr, method: str, arg: ast.expr) -> str:
        recv = self.visit(receiver)
        sep = self._member_access_sep(receiver, recv)
        return f'{recv}{sep}{method}({self._visit_value_expr(arg)})'

    def _class_info_for_var(self, name: str) -> ClassInfo | None:
        if not self.scope:
            return None
        t = self._scope_storage(name)
        return self._class_info_for_type(t)

    def _emit_copy_expr(self, node: ast.expr) -> str | None:
        info = self._class_info_for_expr(node)
        if info and info.has_copy:
            inner = self.visit(node)
            cpp = info.cpp_name()
            if inner == 'this':
                return f'{cpp}(*this)'
            return f'{cpp}({inner})'
        return None

    def _field_storage(self, field: str, *, info: ClassInfo | None=None, fallback: str='') -> str:
        from .analysis.type_emit import field_storage_cpp
        ci = info if info is not None else self.class_info
        if ci is None:
            return fallback
        return field_storage_cpp(ci, field, fallback=fallback)

    def _field_type_node(self, field: str, *, info: ClassInfo | None=None):
        from .analysis.type_emit import field_type_node
        ci = info if info is not None else self.class_info
        if ci is None:
            return None
        return field_type_node(ci, field, classes=self.classes)

    @staticmethod
    def _param_type_node(sig, name: str, *, classes: dict | None=None):
        from .analysis.type_emit import param_type_node
        return param_type_node(sig, name, classes=classes)

    @staticmethod
    def _msig_param_storage(sig, name: str, *, fallback: str='void*') -> str:
        from .analysis.type_emit import method_param_storage_cpp
        return method_param_storage_cpp(sig, name, fallback=fallback)

    @staticmethod
    def _sig_param_types_map(sig) -> dict[str, str]:
        from .analysis.type_emit import method_param_types_map
        return method_param_types_map(sig)

    def _scope_storage(self, name: str, *, fallback: str = '') -> str:
        from .analysis.type_emit import lookup_scope_storage_cpp
        return lookup_scope_storage_cpp(self, name, fallback=fallback)

    def _scope_type_node(self, name: str):
        from .analysis.type_emit import lookup_scope_type_node
        return lookup_scope_type_node(self, name)

    def _bind_scope_var(self, name: str, cpp_type: str, *, node=None) -> None:
        if self.scope is None:
            return
        from .analysis.type_emit import bind_scope_var
        bind_scope_var(self.scope, name, cpp_type, node=node, classes=self.classes)

    @staticmethod
    def _sig_return_storage(sig, *, fallback: str='void') -> str:
        from .analysis.type_emit import sig_return_storage_cpp
        if sig is None:
            return fallback
        return sig_return_storage_cpp(sig, fallback=fallback)

    @staticmethod
    def _sig_return_full(sig, *, fallback: str='void') -> str:
        from .analysis.type_emit import sig_return_full_cpp
        if sig is None:
            return fallback
        return sig_return_full_cpp(sig, fallback=fallback)

    def _field_has_move(self, attr: str) -> bool:
        if not self.class_info:
            return False
        ft = self._field_storage(attr)
        if ft.endswith('*'):
            return False
        info = self._class_info_for_type(ft)
        return bool(info and info.has_move)

    def _field_has_copy(self, attr: str) -> bool:
        if not self.class_info:
            return False
        ft = self._field_storage(attr)
        if ft.endswith('*'):
            return False
        info = self._class_info_for_type(ft)
        return bool(info and info.has_copy)

    def _is_empty_heap_buffer_init(self, value: ast.expr, cpp_type: str) -> bool:
        if not isinstance(value, ast.Constant):
            return False
        if is_char_heap_array_type(cpp_type):
            return value.value == ''
        if is_byte_heap_array_type(cpp_type):
            return value.value == b''
        return False

    def _try_emit_self_empty_heap_buffer_init(self, attr: str, value: ast.expr, *, cpp_type: str) -> bool:
        """``self.buf: char[:] = ""``：成员默认构造即为空缓冲，跳过冗余赋值。"""
        if not self._is_empty_heap_buffer_init(value, cpp_type):
            return False
        return True

    def _try_emit_self_field_protocol_from_other(self, attr: str, rhs: ast.expr) -> bool:
        """``__copy__`` / ``__move__`` 内 ``self.f = other.f`` → 字段协议调用。"""
        if not isinstance(rhs, ast.Attribute):
            return False
        if not isinstance(rhs.value, ast.Name) or rhs.value.id != 'other':
            return False
        if not self.current_method or not self.class_info:
            return False
        if self.current_method.name == '__copy__' and self._field_has_copy(attr):
            self.write_line(f'this->{attr}.__copy__(other.{attr});')
            return True
        if self.current_method.name == '__move__' and self._field_has_move(attr):
            self.write_line(f'this->{attr}.__move__(other.{attr});')
            return True
        return False

    def _try_emit_self_field_move_from_param(self, attr: str, rhs: ast.expr) -> bool:
        """``__init__`` 中 ``self.xs = xs``：一维堆 ``PyArray`` 形参按值接管用 ``__move__``；
    ``list`` 等容器字段有 ``__copy__`` 时保留调用方所有权。"""
        if not isinstance(rhs, ast.Name):
            return False
        if not self.current_method or self.current_method.name != '__init__':
            return False
        from .analysis.type_emit import scope_has_param
        if not self.scope or not scope_has_param(self.scope, rhs.id):
            return False
        ft = self._field_storage(attr) if self.class_info else ''
        if is_array_type(ft) and cpp_array_ndim(ft) == 1 and self._field_has_move(attr):
            self.write_line(f'this->{attr}.__move__({cpp_param(rhs.id)});')
            return True
        if self._field_has_copy(attr):
            self.write_line(f'this->{attr}.__copy__({cpp_param(rhs.id)});')
            return True
        if self._field_has_move(attr):
            self.write_line(f'this->{attr}.__move__({cpp_param(rhs.id)});')
            return True
        return False

    def _try_emit_move_assign(self, target: ast.expr, rhs: ast.expr, *, target_ann: ast.expr | None=None) -> bool:
        if not isinstance(target, ast.Name) or not isinstance(rhs, ast.Name):
            return False
        target_info = self._class_info_for_var(target.id)
        if target_info is None and target_ann is not None:
            target_info = self._class_info_for_type(self._parse_storage_type(target_ann, self._active_type_params()))
        rhs_info = self._class_info_for_var(rhs.id)
        if not target_info or not rhs_info or target_info.name != rhs_info.name or (not target_info.has_move) or target_info.is_copyable or target_info.is_refcount:
            return False
        if self._try_declare(target.id):
            vtype = self._scope_storage(target.id) if self.scope else ''
            if not vtype and target_ann is not None:
                vtype = self._parse_storage_type(target_ann, self._active_type_params())
            if not vtype:
                vtype = target_info.storage_cpp_type()
            if self.scope:
                self._bind_scope_var(target.id, vtype)
            self.write_line(f'{vtype} {cpp_param(target.id)};')
        self.write_line(self._member_call_with_arg(target, '__move__', rhs) + ';')
        return True

    def _try_emit_copy_assign(self, target: ast.expr, rhs: ast.expr, *, target_ann: ast.expr | None=None) -> bool:
        """``c = b``：仅 ``@copyable`` 类生成 ``c.__copy__(b)``（不含 ``c = +b``）。"""
        if not isinstance(target, ast.Name) or not isinstance(rhs, ast.Name):
            return False
        target_info = self._class_info_for_var(target.id)
        if target_info is None and target_ann is not None:
            target_info = self._class_info_for_type(self._parse_storage_type(target_ann, self._active_type_params()))
        rhs_info = self._class_info_for_var(rhs.id)
        if not target_info or not rhs_info or target_info.name != rhs_info.name or (not target_info.is_copyable) or (not target_info.has_copy):
            return False
        source_cpp = self.visit(rhs)
        if self._try_declare(target.id):
            vtype = self._scope_storage(target.id) if self.scope else ''
            if not vtype and target_ann is not None:
                vtype = self._parse_storage_type(target_ann, self._active_type_params())
            if not vtype:
                vtype = target_info.storage_cpp_type()
            if self.scope:
                self._bind_scope_var(target.id, vtype)
            self.write_line(f'{vtype} {cpp_param(target.id)}({source_cpp});')
        else:
            self.write_line(self._member_call_with_arg(target, '__copy__', rhs) + ';')
        return True

    def _rhs_cpp_for_assign(self, node: ast.expr) -> tuple[str, str | None]:
        """赋值右值（移动/复制赋值由 ``_try_emit_*_assign`` 单独处理）。"""
        match node:
            case ast.UnaryOp(op=ast.UAdd(), operand=operand):
                copied = self._emit_copy_expr(operand)
                if copied:
                    info = self._class_info_for_expr(operand)
                    return (copied, info.storage_cpp_type() if info else None)
                return (f'(+{self.visit(operand)})', None)
            case ast.Name():
                return (self.visit(node), self._scope_storage(node.id) or None)
            case ast.Call():
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Subscript) and isinstance(node.func.value.value, ast.Name):
                    cls_name = node.func.value.value.id
                    if self._name_refers_to_class(cls_name):
                        from .emit.call_emit import class_subscript_static_call_return_type
                        info = self._class_info_for_ref(cls_name)
                        if info is not None and info.type_params:
                            rt = class_subscript_static_call_return_type(self, info, node.func.attr, node.func.value.slice)
                            if rt is not None:
                                return (emit_call_expr(self, node), rt)
                if isinstance(node.func, ast.Subscript) and isinstance(node.func.value, ast.Attribute):
                    recv_info = self._class_info_for_expr(node.func.value.value)
                    if recv_info is not None:
                        rt = templated_instance_call_return_type(self, recv_info, node.func.value.attr, node.func.slice)
                        if rt is not None:
                            return (emit_call_expr(self, node), rt)
                if isinstance(node.func, ast.Name):
                    if node.func.id == 'next' and len(node.args) == 1 and (not node.keywords):
                        recv_info = self._class_info_for_attr_value(node.args[0])
                        if recv_info and '__next__' in recv_info.method_sigs:
                            sig = recv_info.method_sigs['__next__']
                            ret = self._sig_return_full(sig)
                            if ret:
                                return (self.visit(node), ret)
                    fsig = self._function_sig_for_name(node.func.id)
                    if fsig is not None:
                        ret = self._sig_return_full(fsig)
                        if ret:
                            return (self.visit(node), ret)
                if isinstance(node.func, ast.Attribute):
                    recv_info = self._class_info_for_attr_value(node.func.value)
                    if recv_info and node.func.attr in recv_info.method_sigs:
                        sig = recv_info.method_sigs[node.func.attr]
                        ret = self._sig_return_full(sig)
                        if ret:
                            return (emit_call_expr(self, node), ret)
                info = self._class_info_for_call(node)
                cpp = emit_call_expr(self, node)
                if info:
                    t = info.storage_cpp_type()
                    if info.module_path != RUNTIME_PKG and self._is_stdlib_module(info.module_path):
                        base, _, tail = t.partition('<')
                        if tail:
                            t = f'{qualify_symbol_in_module(info.module_path, base)}<{tail}'
                        else:
                            t = qualify_symbol_in_module(info.module_path, t)
                    return (cpp, t)
                return (cpp, self._type_from_rhs(cpp))
            case ast.BinOp():
                left_info = self._class_info_for_expr(node.left)
                dunder = self._binop_dunder(node.op)
                if left_info and dunder and self._class_info_has_method(left_info, dunder):
                    return (self.visit(node), left_info.storage_cpp_type())
                cpp = self.visit(node)
                return (cpp, self._type_from_rhs(cpp))
            case ast.List() as list_node:
                elem_t = self._infer_list_elem_type(list_node.elts)
                cpp = _emit_list_value_expr(self, list_node)
                return (cpp, cpp_template_type('list', elem_t))
            case _:
                cpp = self.visit(node)
                hint = self._type_from_rhs(cpp)
                return (cpp, hint)

    @staticmethod
    def _is_type_marker(info: ClassInfo) -> bool:
        return info.name in TYPE_MARKER_CLASSES

    def _skip_module_classes(self, module_path: str) -> bool:
        from .constant.stdlib_discovery import is_stdlib_codegen_module
        return is_stdlib_codegen_module(module_path)

    def _write_primitive_type_headers(self) -> None:
        write_primitive_type_headers(self)

    @staticmethod
    def _is_stdlib_module(module_path: str) -> bool:
        return module_path == RUNTIME_PKG or module_path.startswith(f'{RUNTIME_PREFIX}/')

    @staticmethod
    def _is_ffi_module(module_path: str) -> bool:
        return is_ffi_module_path(module_path)

    def _is_runtime_bootstrap(self) -> bool:
        """仅翻译 ``py2cpp/__init__.py`` 时写 runtime 标准库头/实现，避免测试覆盖共享产物。"""
        return self.entry_module_path == RUNTIME_PKG

    def _module_output_dir(self, module_path: str) -> Path:
        if self._is_stdlib_module(module_path) or self._is_ffi_module(module_path):
            return self.runtime_output_dir
        return self.entry_output_dir

    def _stdlib_artifact_path(self, module_path: str, suffix: str) -> Path:
        """``py2cpp/array`` + ``.h`` → ``<runtime>/py2cpp/array.h``（相对 ``runtime_output_dir``）。"""
        return self.runtime_output_dir / f'{module_path}{suffix}'

    def _ffi_artifact_path(self, module_path: str, suffix: str) -> Path:
        """``ffi/windows`` + ``.h`` → ``<runtime>/ffi/windows.h``（与 ``py2cpp/`` 并列）。"""
        return self.runtime_output_dir / f'{ffi_runtime_module_path(module_path)}{suffix}'

    def _can_write_ffi_artifact(self, module_path: str) -> bool:
        """FFI 被 import 进闭包即可写 runtime 产物（不依赖 bootstrap）。"""
        return self._is_ffi_module(module_path)

    def _user_module_output_relpath(self, module_path: str) -> str:
        """用户子模块在入口输出目录下的相对路径。"""
        return module_path

    @contextmanager
    def _use_module_namespace(self, module_path: str):
        norm = module_path.replace('\\', '/')
        if norm in MODULES_WITHOUT_CPP_NAMESPACE:
            yield
            return
        q = namespace_qualifier_for_module(module_path)
        segments = q.split('::') if q else []
        if segments:
            with use_cpp_namespaces(self, segments):
                yield
        else:
            yield

    @contextmanager
    def _use_inl_namespace(self, module_path: str):
        """``.inl`` 在 ``.h`` 闭合后包含：子模块默认套完整 ``namespace``；单层子包用全局全限定实现。"""
        segments = inl_namespace_segments(module_path)
        if segments:
            with use_cpp_namespaces(self, segments):
                yield
        else:
            yield

    def _emit_module_import_usings(self, module_path: str) -> None:
        """模块内 ``from … import`` → ``using`` / ``using namespace``（写在 namespace 块内首部）。"""
        for u in self.module_import_usings.get(module_path, []):
            if u.kind == 'namespace':
                self.write_line(using_namespace_line(u.qualifier))
            elif u.symbol:
                self.write_line(using_symbol_line(u.qualifier, u.symbol))
        self._emit_runtime_header_usings(module_path)
        if not self._is_stdlib_module(module_path) and module_path == self.entry_module_path and any((self._is_stdlib_module(mp) for mp in self.module_order)):
            seen_umbrella: set[str] = set()
            idx = self.header_usings_index
            for ns, sym in idx.get(stdlib_header_include(RUNTIME_PKG), ()):
                if sym in RUNTIME_PKG_QUALIFIED_SYMBOLS:
                    continue
                if ns == 'py2cpp':
                    continue
                line = using_symbol_line(ns, sym)
                if line not in seen_umbrella:
                    seen_umbrella.add(line)
                    self.write_line(line)
            stdlib_names = frozenset(self.stdlib_modules_for_umbrella or STDLIB_REL_PATHS)
            for name in stdlib_names:
                header = stdlib_header_include(name)
                for ns, sym in idx.get(header, ()):
                    line = using_symbol_line(ns, sym)
                    if line not in seen_umbrella:
                        seen_umbrella.add(line)
                        self.write_line(line)
        usings = self.module_import_usings.get(module_path, [])
        if usings or self.module_analysis.get(module_path):
            self.write_line()

    def _stdlib_inl_using_lines(self, module_path: str) -> list[str]:
        """``.inl`` 在 ``.h`` 的 ``namespace`` 闭合之后 ``#include``，须自行 ``using`` 短名。"""
        from .analysis.header_usings import usings_for_headers
        ma = self.module_analysis.get(module_path)
        seen: set[str] = set()
        out: list[str] = []
        if ma:
            headers = list(ma.includes) + list(ma.post_class_includes)
            for ns, sym in usings_for_headers(headers, self.header_usings_index):
                if module_path == _ITER_RESULT_MODULE and ns == 'py2cpp::text::str' and sym != 'PyStr':
                    continue
                line = using_symbol_line(ns, sym)
                if line not in seen:
                    seen.add(line)
                    out.append(f'  {line}')
        if self._is_stdlib_module(module_path) and (not inl_namespace_segments(module_path)) and (module_path != RUNTIME_PKG):
            q = namespace_qualifier_for_module(module_path)
            if q:
                line = using_namespace_line(q)
                if line not in seen:
                    seen.add(line)
                    out.append(line)
        return out

    def _emit_runtime_header_usings(self, module_path: str) -> None:
        """按 ``#include`` / 前向声明为模块 ``namespace`` 注入 ``using``（避免全局短名污染）。"""
        from .constant.stdlib_modules import PYSTR_FORWARD_ONLY_MODULES
        from .constant.stdlib_layout import stdlib_module_path as _stdlib_mp
        ma = self.module_analysis.get(module_path)
        if not ma:
            return
        if module_path == RUNTIME_PKG:
            line = using_symbol_line('py2cpp::text::str', 'PyStr')
            self.write_line(line)
        headers = list(ma.includes)
        pystr_forward_only = module_path in frozenset((_stdlib_mp(m) for m in PYSTR_FORWARD_ONLY_MODULES))
        seen: set[str] = set()
        if pystr_forward_only and any(('namespace str' in d for d in ma.forward_decls)):
            if module_path != _ITER_RESULT_MODULE:
                line = using_symbol_line('py2cpp::text::str', 'PyStr')
                seen.add(line)
                self.write_line(line)
        if not pystr_forward_only and any(('namespace str' in d for d in ma.forward_decls)):
            h = stdlib_header_include('text/str')
            if h not in headers:
                headers.append(h)
        if any(('namespace iter_result' in d for d in ma.forward_decls)):
            h = stdlib_header_include('core/iter_result')
            if h not in headers:
                headers.append(h)
        from .analysis.header_usings import usings_for_headers
        for ns, sym in usings_for_headers(headers, self.header_usings_index):
            line = using_symbol_line(ns, sym)
            if line not in seen:
                seen.add(line)
                self.write_line(line)

    def _register_nested_classes(self, info: ClassInfo) -> None:
        for nested in info.nested_classes:
            self.classes[nested.class_registry_key()] = nested
            self._register_nested_classes(nested)

    def _class_method_qualifier(self, info: ClassInfo) -> str:
        """``ns::Outer::Inner<T>``，用于类外方法定义（含嵌套类）。"""
        ns = namespace_qualifier_for_module(info.module_path)
        parts: list[str] = []
        cur: ClassInfo | None = info
        while cur is not None:
            if cur.is_template():
                parts.append(cur.cpp_specialization())
            else:
                parts.append(cur.cpp_name())
            cur = cur.outer_class
        inner = '::'.join(reversed(parts))
        return f'{ns}::{inner}' if ns else inner

    def _module_function_qualifier(self, module_path: str, func_name: str) -> str:
        """模块内自由函数的全局限定名（模板实现写在 ``.inl`` 时）。"""
        ns = namespace_qualifier_for_module(module_path)
        return f'{ns}::{func_name}' if ns else func_name

    @staticmethod
    def _stdlib_source_note(module_path: str) -> str:
        if module_path == RUNTIME_PKG:
            return f'{RUNTIME_PREFIX}/__init__.py'
        if module_path == stdlib_module_path('io/file'):
            return f'{RUNTIME_PREFIX}/io/file/__init__.py'
        if module_path == _OS_PATH_MODULE:
            return f'{RUNTIME_PREFIX}/io/file/path.py'
        if module_path == _IO_PATH_OO_MODULE:
            return f'{RUNTIME_PREFIX}/io/path.py'
        return f'{module_path}.py'

    def _write_per_module_headers(self) -> None:
        write_per_module_headers(self)

    def _write_umbrella_header(self) -> None:
        write_umbrella_header(self)

    def _sync_runtime_cpp_usings(self) -> None:
        sync_runtime_cpp_usings(self)

    def _can_write_stdlib_artifact(self, module_path: str) -> bool:
        """允许写 ``generated/runtime`` 下标准库产物（bootstrap 或单模块 runtime 翻译）。

    用户/测试入口仅分析标准库、读已有头文件；勿并行重写 ``test/unittest.h`` 等 on-demand 模块。
    """
        if not self._is_stdlib_module(module_path):
            return False
        if self._is_runtime_bootstrap():
            return True
        entry: str = self.entry_module_path.replace('\\', '/')
        if self._is_stdlib_module(entry):
            return module_path == entry
        return False

    def _write_per_module_inl(self) -> None:
        write_per_module_inl(self)

    @property
    def indent(self) -> str:
        return '  ' * self.indent_level

    @contextmanager
    def _use_header(self):
        prev = self.in_header
        self.in_header = True
        yield
        self.in_header = prev

    @contextmanager
    def _use_source(self):
        prev = self.in_header
        self.in_header = False
        yield
        self.in_header = prev

    @contextmanager
    def _use_indent(self):
        self.indent_level += 1
        yield
        self.indent_level -= 1

    @contextmanager
    def _use_block(self, header: str=''):
        if header:
            self.write_line(header)
        self.write_line('{')
        block_scope = Scope(self.scope.node if self.scope else None)
        if self.scope:
            block_scope.param_types = dict(self.scope.param_types)
            block_scope.param_type_nodes = dict(self.scope.param_type_nodes)
            block_scope.var_types = dict(self.scope.var_types)
            block_scope.var_type_nodes = dict(self.scope.var_type_nodes)
            block_scope.lazy_params = dict(self.scope.lazy_params)
        self.scopes.append(block_scope)
        self.scope = block_scope
        try:
            with self._use_indent():
                yield
        finally:
            self.scopes.pop()
            self.scope = self.scopes[-1] if self.scopes else None
        self.write_line('}')

    @contextmanager
    def _use_scope(self, node: ast.AST):
        scope = Scope(node)
        prev_method = self.current_method
        if isinstance(node, ast.FunctionDef):
            self.current_method = node
        self.scopes.append(scope)
        self.scope = scope
        try:
            yield scope
        finally:
            self.scopes.pop()
            self.scope = self.scopes[-1] if self.scopes else None
            if isinstance(node, ast.FunctionDef):
                self.current_method = prev_method

    @contextmanager
    def _use_self_type(self, info: ClassInfo | None):
        prev = self._self_type_class
        self._self_type_class = info
        try:
            yield
        finally:
            self._self_type_class = prev

    def write_line(self, line: str=''):
        if self._emit_line_sink is not None:
            sink = self._emit_line_sink
            if not line:
                sink.append('')
                return
            if '\n' not in line:
                sink.append(f'{self.indent}{line}')
                return
            for part in line.split('\n'):
                sink.append(f'{self.indent}{part}')
            return
        if self.in_header and self.deferred_header_target is not None:
            target = self.per_module_deferred_header_lines.setdefault(self.deferred_header_target, [])
        elif self.in_header and self.header_target is not None:
            target = self.per_module_header_lines.setdefault(self.header_target, [])
        elif self.source_target is not None and self._is_stdlib_module(self.source_target):
            target = self.per_module_source_lines.setdefault(self.source_target, [])
        elif self.inl_target is not None:
            target = self.per_module_inl_lines.setdefault(self.inl_target, [])
        else:
            target = self.header_lines if self.in_header else self.source_lines
        if not line:
            target.append('')
            return
        if '\n' not in line:
            target.append(f'{self.indent}{line}')
            return
        for part in line.split('\n'):
            target.append(f'{self.indent}{part}')

    def write_comment(self, text: str):
        """写入单行 ``//`` 注释（用于生成文件头，非 Doxygen）。"""
        self.write_line(f'// {text}')

    def _write_doc_lines(self, lines: list[str] | tuple[str, ...]):
        if not lines:
            return
        for line in lines:
            self.write_line(line)

    @staticmethod
    def _strip_leading_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
        if body and isinstance(body[0], ast.Expr):
            val = body[0].value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                return body[1:]
        return body

    def _emit_module_docstring(self, module_path: str):
        ma = self.module_analysis.get(module_path)
        if ma and ma.doc_lines:
            self._write_doc_lines(ma.doc_lines)

    def _sync_type_aliases(self, info: ClassInfo | None) -> None:
        if self.type_parser is None:
            return
        if info is None:
            self.type_parser.set_type_aliases(None)
            return
        self.type_parser.set_type_aliases(info.type_aliases, use_as_cpp_name=not info.is_protocol)

    def _type_alias_rhs_cpp(self, alias: TypeAliasInfo, info: ClassInfo) -> str:
        assert self.type_parser is not None
        if alias.is_conditional:
            from .passes.type_conditional import conditional_alias_rhs_cpp
            return conditional_alias_rhs_cpp(alias)
        others = {n: a for n, a in info.type_aliases.items() if n != alias.name}
        self.type_parser.set_type_aliases(others, use_as_cpp_name=True)
        tparams = set(info.type_params) | set(alias.type_params)
        return self._parse_type(alias.value, tparams)

    def _emit_type_alias_using(self, alias: TypeAliasInfo, rhs: str) -> None:
        if alias.type_params:
            parts = [f'typename {p}' for p in alias.type_params]
            for p in alias.type_params:
                for bound in alias.type_param_constraints.get(p, ()):
                    parts.append(f'{bound}_requires<{p}> = 0')
            for dec in getattr(alias, 'type_param_decorator_constraints', {}).get(p, ()):
                parts.append(f'py2cpp_{dec}_requires<{p}> = 0')
            self.write_line(f"template<{', '.join(parts)}>")
            self.write_line(f'  using {alias.name} = {rhs};')
        else:
            self.write_line(f'using {alias.name} = {rhs};')

    def _qualified_member_alias_type(self, name: str, info: ClassInfo) -> str:
        return f'typename {info.cpp_specialization()}::{name}'

    def _typename_dependent_member_types(self, cpp_type: str, type_params: set[str]) -> str:
        """``ItL::Element`` 等依赖名在类外定义中加 ``typename``。"""
        out = cpp_type
        for p in type_params:
            needle = f'{p}::'
            if needle in out and f'typename {needle}' not in out:
                out = out.replace(needle, f'typename {needle}')
        return out

    def _typename_member_alias_type(self, cpp_type: str, info: ClassInfo) -> str:
        """类外模板成员定义中，成员 ``using`` 别名须为 ``typename Qual::Alias``（MSVC）。"""
        if not info.is_template():
            return cpp_type
        t = cpp_type.strip()
        for p in info.type_params:
            qual = self._qualified_member_alias_type(p, info)
            if t == p:
                return qual
            if t.startswith(f'{p} ') or t.startswith(f'{p}&') or t.startswith(f'{p}*'):
                return qual + t[len(p):]
        if info.type_aliases:
            if t.startswith('typename '):
                return cpp_type
            for name in info.type_aliases:
                if info.type_aliases[name].member_constraint:
                    continue
                qual = self._qualified_member_alias_type(name, info)
                if t == name:
                    return qual
                if t.startswith(f'{name} ') or t.startswith(f'{name}&'):
                    return qual + t[len(name):]
        out = self._typename_dependent_member_types(cpp_type, set(info.type_params))
        return self._rewrite_template_args_to_cpp_params(out, info)

    def _rewrite_template_args_to_cpp_params(self, cpp_type: str, info: ClassInfo) -> str:
        """类外成员定义 / 基类列表等：模板实参与 ``T::`` 依赖名须用 ``_T``。"""
        if not info.type_params:
            return cpp_type
        out = cpp_type
        for p in sorted(info.type_params, key=len, reverse=True):
            unders = cpp_type_param_template_name(p)
            for old, new in ((f'<{p}>', f'<{unders}>'), (f'<{p},', f'<{unders},'), (f', {p}>', f', {unders}>'), (f', {p},', f', {unders},'), (f'{p}::', f'{unders}::')):
                out = out.replace(old, new)
        return out

    def _typename_member_alias_params(self, params: str, info: ClassInfo) -> str:
        if not params:
            return params
        from .analysis.ir import split_cpp_param_list
        out = ', '.join((self._typename_member_alias_type(p.strip(), info) for p in split_cpp_param_list(params)))
        return self._rewrite_template_args_to_cpp_params(out, info)

    def _qualify_module_type_alias_rhs(self, module_path: str, rhs: str) -> str:
        """模块级 ``using`` 写在 namespace 外时，同模块类名须全限定（MSVC）。"""
        ns = namespace_qualifier_for_module(module_path)
        if not ns or '::' in rhs.split('<', 1)[0]:
            return rhs
        names = sorted({info.cpp_name() for info in self.classes.values() if info.module_path == module_path}, key=len, reverse=True)
        for name in names:
            prefix = f'{name}<'
            if rhs.startswith(prefix):
                return f'{ns}::{rhs}'
            if rhs == name:
                return f'{ns}::{rhs}'
        return rhs

    def _emit_module_type_aliases(self, module_path: str, *, conditional_only: bool | None=None, use_deferred: bool=True) -> None:
        ma = self.module_analysis.get(module_path)
        if not ma or not ma.type_aliases:
            return
        assert self.type_parser is not None
        from .passes.type_conditional import emit_conditional_type_alias, plan_conditional_alias
        prev_deferred = self.deferred_header_target
        if not use_deferred:
            self.deferred_header_target = None
        try:
            for alias in ma.type_aliases:
                if conditional_only is True and (not alias.is_conditional):
                    continue
                if conditional_only is False and alias.is_conditional:
                    continue
                if alias.is_conditional:
                    others = {a.name: a for a in ma.type_aliases if a.name != alias.name}
                    self.type_parser.set_type_aliases(others, use_as_cpp_name=False)
                    plan = plan_conditional_alias(self, alias)
                    emit_conditional_type_alias(self, alias, plan)
                    continue
                others = {a.name: a for a in ma.type_aliases if a.name != alias.name}
                self.type_parser.set_type_aliases(others, use_as_cpp_name=False)
                rhs = self.type_parser.parse_type(alias.value, set(alias.type_params))
                rhs = self._qualify_module_type_alias_rhs(module_path, rhs)
                self._emit_type_alias_using(alias, rhs)
            self.write_line()
        finally:
            self.deferred_header_target = prev_deferred

    def _active_type_params(self) -> set[str]:
        s = set(self._type_if_extra_params)
        if self.current_method is not None:
            for tp in getattr(self.current_method, 'type_params', None) or ():
                if isinstance(tp, (ast.TypeVar, ast.TypeVarTuple)):
                    s.add(tp.name)
        if self.class_info:
            s |= set(self.class_info.type_params)
            if self.class_info.typevar_tuple:
                s.add(self.class_info.typevar_tuple)
        s |= set(self._active_typevar_tuple_names())
        return s

    def _active_typevar_tuple_names(self) -> frozenset[str]:
        names: set[str] = set()
        if self.class_info and self.class_info.typevar_tuple:
            names.add(self.class_info.typevar_tuple)
        if self.current_method is not None:
            from .analysis.variadic_template import parse_function_type_params, resolve_variadic_template
            _, _cap, header_tuple = parse_function_type_params(self.current_method)
            if header_tuple is not None:
                names.add(header_tuple)
            class_tps = list(self.class_info.type_params) if self.class_info else None
            vt = resolve_variadic_template(self.current_method, class_type_params=class_tps, class_typevar_tuple=self.class_info.typevar_tuple if self.class_info else None)
            if vt is not None:
                names.add(vt.pack_name)
        return frozenset(names)

    def _emit_generic_body_or_type_if(self, func: ast.FunctionDef, sig: FunctionSig | MethodSig, *, type_if_plan: TypeIfFunctionPlan | None=None, type_if_pick: str | None=None) -> None:
        if type_if_plan is not None and type_if_pick is not None:
            emit_type_if_return(self, func, sig, type_if_plan, type_if_pick)
            return
        self._emit_body(func.body)

    def _parse_type(self, node: ast.expr | None, type_params: set[str]) -> str:
        assert self.type_parser is not None
        if isinstance(node, ast.Name) and node.id == 'Super' and self.class_info:
            from .analysis.proxy import entity_base_ast
            base_ast = entity_base_ast(self.class_info)
            if base_ast is not None:
                node = base_ast
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.MatMult):
            from .analysis.ir import iter_matmult_marker_names
            from .analysis.lazy_param import is_lazy_type_annotation
            if is_lazy_type_annotation(node):
                return self._parse_type(node.left, type_params)
            base = self._parse_type(node.left, type_params)
            if 'ref' in iter_matmult_marker_names(node):
                if not base.endswith('&'):
                    return f'{base}&'
            return base
        bind = self._type_if_concrete_bind
        if bind is not None:
            if isinstance(node, ast.Name) and node.id == bind[0]:
                return bind[1]
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == bind[0]:
                    idx = {'Element': 0, 'Value': 1}.get(node.attr)
                    if idx is not None:
                        _base, args = split_cpp_template(bind[1])
                        if idx < len(args):
                            return args[idx]
            if isinstance(node, ast.Subscript):
                val = self._parse_type(node.value, type_params)
                sl = node.slice
                if isinstance(sl, ast.Tuple):
                    args = ', '.join((self._parse_type(e, type_params) for e in sl.elts))
                else:
                    args = self._parse_type(sl, type_params)
                return f'{val}<{args}>'
        self_class = self._self_type_class.template_cpp_type() if self._self_type_class else None
        return self.type_parser.parse_type(node, type_params, self_class=self_class, typevar_tuple_names=self._active_typevar_tuple_names())

    def _emit_ecs_query_ctor_inner(self, call: ast.Call) -> str:
        if len(call.args) != 2:
            return ', '.join((self._visit_value_expr(a) for a in call.args))
        parts: list[str] = []
        for arg in call.args:
            if isinstance(arg, ast.Name) and arg.id == 'self':
                parts.append('this')
                continue
            v = self.visit(arg)
            if v == 'this':
                parts.append('this')
                continue
            t = self._infer_expr_cpp_type(arg)
            if self._is_ptr_type(t):
                parts.append(v)
                continue
            bare = t.strip()
            if bare.startswith('const '):
                bare = bare[6:].strip()
            if bare.endswith('*'):
                bare = bare[:-1].strip()
            if bare.startswith(f"{cpp_ident('ECSComponentTable')}<") or bare == cpp_ident('ECSComponentTable'):
                parts.append(f'&{v}')
            else:
                parts.append(self._visit_value_expr(arg))
        return ', '.join(parts)

    def _emit_list_iterator_ctor_inner(self, call: ast.Call) -> str:
        if len(call.args) != 1:
            return ', '.join((self._visit_value_expr(a) for a in call.args))
        arg = call.args[0]
        if isinstance(arg, ast.Name) and arg.id == 'self':
            from .analysis.stubs.iterator_host_stubs import iterator_ctor_self_expr
            host = self.class_info.name if self.class_info else ''
            return iterator_ctor_self_expr(host)
        v = self.visit(arg)
        if v == 'this':
            return 'this'
        t = self._infer_expr_cpp_type(arg)
        if self._is_ptr_type(t):
            return v
        if is_set_type(t) or is_frozenset_type(t) or is_frozenlist_type(t) or is_frozendict_type(t):
            return f'&{v}'
        if is_list_type(t) or is_deque_type(t) or is_frozenlist_type(t):
            return f'&{v}'
        bare = t.strip()
        if bare.startswith('const '):
            bare = bare[6:].strip()
        if bare.endswith('*'):
            bare = bare[:-1].strip()
        if bare.startswith(f"{cpp_ident('ECSComponentTable')}<") or bare == cpp_ident('ECSComponentTable'):
            return f'&{v}'
        return self._visit_value_expr(arg)

    def _is_boxing_ctor(self, base: str, py_class: str | None=None) -> bool:
        if py_class and py_class in self.classes:
            return self.classes[py_class].is_boxing
        for info in self.classes.values():
            if info.cpp_name() == base or info.name == base:
                return info.is_boxing
        return base.startswith('_Char') or base.startswith('_DictKey')

    def _parse_type_args(self, slice_node: ast.expr, type_params: set[str]) -> str:
        match slice_node:
            case ast.Tuple(elts=elts):
                return ', '.join((self._parse_type(e, type_params) for e in elts))
            case _:
                return self._parse_type(slice_node, type_params)

    def _class_template_param_decls(self, info: ClassInfo) -> list[str]:
        """``template<typename _Element, …>`` 或 NTTP ``template<typename _T, _T Mod>``。"""
        if not info.type_params:
            return []
        class_tparams = set(info.type_params)
        nttp = getattr(info, 'type_param_nttp', None) or {}
        parts: list[str] = []
        for p in info.type_params:
            cpp_p = cpp_type_param_template_name(p)
            val_ty = nttp.get(p)
            if val_ty is not None:
                from .analysis.ir import cpp_nttp_value_type_name
                val_cpp = cpp_nttp_value_type_name(val_ty)
                decl = f'{val_cpp} {cpp_p}'
                dv = info.type_param_defaults.get(p)
                if dv is not None and self.type_parser is not None:
                    cpp_default = self.type_parser.parse_type(dv, class_tparams)
                    decl = f'{val_cpp} {cpp_p} = {cpp_default}'
            else:
                decl = f'typename {cpp_p}'
                dv = info.type_param_defaults.get(p)
                if dv is not None and self.type_parser is not None:
                    cpp_default = self.type_parser.parse_type(dv, class_tparams)
                    decl = f'typename {cpp_p} = {cpp_default}'
            parts.append(decl)
        if info.typevar_tuple:
            parts.append(f'typename... {cpp_type_param_template_name(info.typevar_tuple)}')
        return parts

    def _emit_template_prefix(self, info: ClassInfo):
        if not info.is_template():
            return
        parts = self._class_template_param_decls(info)
        if not parts:
            return
        self.write_line(f"template<{', '.join(parts)}>")

    def _emit_template_prefix_forward(self, info: ClassInfo):
        """批量前向声明：省略默认模板实参（完整类定义处再写，避免 C4348）。"""
        if not info.is_template():
            return
        from .emit.class_decl_emit import _class_template_param_decls_plain

        parts = _class_template_param_decls_plain(self, info)
        if not parts:
            return
        self.write_line(f"template<{', '.join(parts)}>")

    def _emit_descriptor_protocol_static_asserts(self, cpp_type: str, protocols: tuple[str, ...], *, node: ast.AST | None=None) -> None:
        if not protocols or not cpp_type:
            return
        from .emit.compile_diagnostic_emit import compile_diag_c_utf8_literal, compile_diag_descriptor_protocol
        loc_prefix = self._compile_diag_loc_prefix(node) if node is not None else ''
        for protocol in protocols:
            msg = compile_diag_descriptor_protocol(cpp_type, protocol, loc_prefix=loc_prefix)
            self.write_line(f'static_assert(::{protocol}_check<{cpp_type}>::value, {compile_diag_c_utf8_literal(msg)});')

    def _descriptor_validate_value_cpp_type(self, msig: MethodSig) -> str | None:
        for name, pt in self._sig_param_types_map(msig).items():
            if name != 'self':
                return pt
        return None

    def _emit_function_template_prefix(self, func_ft: FuncTypeParams, *, default_constraint: bool=True, variadic_template: 'VariadicTemplateInfo | None'=None):
        from .analysis.variadic_template import typevar_tuple_names_for_emit
        tuple_names = typevar_tuple_names_for_emit(func_ft, variadic_template)
        if not func_ft.template_names and (not tuple_names):
            return
        info = self.class_info
        if info and info.is_template():
            class_params = set(info.type_params)
            if info.typevar_tuple:
                class_params.add(info.typevar_tuple)
            if all((n in class_params for n in func_ft.template_names)):
                return
        parts: list[str] = [f'typename {p}' for p in func_ft.template_names]
        for t in tuple_names:
            parts.append(f'typename... {t}')
        from .analysis.ir import FuncTypeParametricBound
        for p in func_ft.template_names:
            bound = func_ft.constraints.get(p)
            if not bound:
                continue
            if isinstance(bound, FuncTypeParametricBound):
                req = f'{bound.protocol}_requires<{p}, {bound.assoc_type_param}>'
                parts.append(f'{req} = 0' if default_constraint else req)
                continue
            bounds = (bound,) if isinstance(bound, str) else bound
            for b in bounds:
                req = f'{b}_requires<{p}>'
                parts.append(f'{req} = 0' if default_constraint else req)
        for p in func_ft.template_names:
            for dec in getattr(func_ft, 'decorator_constraints', {}).get(p, ()):
                req = f'py2cpp_{dec}_requires<{p}>'
                parts.append(f'{req} = 0' if default_constraint else req)
        self.write_line(f"template<{', '.join(parts)}>")

    def _member_cpp_name(self, info: ClassInfo | None, name: str) -> str:
        if info is not None:
            return info.cpp_member_name(name)
        if self.class_info is not None:
            return self.class_info.cpp_member_name(name)
        return name

    def _attr_cpp_name(self, receiver: ast.expr, attr: str) -> str:
        info = self._class_info_for_receiver(receiver)
        if info is None and isinstance(receiver, ast.Name) and (receiver.id == 'self'):
            info = self.class_info
        if info is None and isinstance(receiver, ast.Name):
            from .analysis.access import _infer_receiver_class
            cls = _infer_receiver_class(receiver, context=self.class_info, func=self.current_method, classes=self.classes, import_bindings=self.import_bindings)
            if cls:
                info = self.classes.get(cls)
        return self._member_cpp_name(info, attr)

    def _stdlib_module_classes(self, module_path: str) -> list[ClassInfo]:
        if self._skip_module_classes(module_path):
            return []
        from .emit.class_decl_emit import sort_module_classes_for_declaration
        classes = [info for info in self.classes.values() if info.module_path == module_path and info.outer_class is None and (not info.is_descriptor) and (not info.is_mixin) and (not info.is_annotation) and (not info.is_protocol) and (not info.is_variant_mixin) and (not self._is_type_marker(info))]
        return sort_module_classes_for_declaration(classes)

    def _emit_stdlib_class_methods_body(self, info: ClassInfo) -> None:
        self.current_class = info.name
        self.class_info = info
        self._sync_type_aliases(info)
        try:
            _emit_class_methods_body(self, info)
        finally:
            self.current_class = None
            self.class_info = None
            self._sync_type_aliases(None)

    @staticmethod
    def _function_sig_params_impl(params: str) -> str:
        """``.inl`` / ``.cpp`` 定义不得重复 ``.h`` 默认实参（MSVC C2572）。"""
        if ' = ' not in params:
            return params
        return ', '.join((piece.split(' = ')[0].strip() for piece in params.split(',')))

    def _emit_stdlib_module_function_body(self, module_path: str, func: ast.FunctionDef, *, qualified_name: str | None=None) -> None:
        if is_overload_stub(func):
            return
        fsig = self._function_sig_for(module_path, func)
        cpp_name = qualified_name or self._module_function_cpp_name(module_path, func)
        sig = format_fn_sig(self._sig_return_storage(fsig), fsig.ret_trail, cpp_name, self._function_sig_params_impl(fsig.params)) + fn_noexcept_suffix(fsig.is_noexcept)
        with self._use_scope(func) as scope:
            from .analysis.type_emit import bind_scope_param
            for arg in func.args.args:
                bind_scope_param(scope, arg.arg, fsig)
                scope.vars[arg.arg] = NameContext.Argument
            if fsig.variadic_template is not None:
                vt = fsig.variadic_template
                bind_scope_param(scope, vt.param_name, fsig)
                scope.vars[vt.param_name] = NameContext.Argument
            elif fsig.vararg_pack is not None:
                vp = fsig.vararg_pack
                from .analysis.type_emit import bind_scope_vararg
                bind_scope_vararg(scope, vp.param_name, vp.cpp_type, classes=self.classes)
                scope.vars[vp.param_name] = NameContext.Argument
            if fsig.lazy_params:
                scope.lazy_params = dict(fsig.lazy_params)
            type_if_plan = plan_type_if_chain(self, func)
            type_if_pick = None
            if type_if_plan is not None:
                type_if_pick = emit_type_if_dispatch(self, type_if_plan, fsig)
            if fsig.variadic_template is not None:
                from .emit.variadic_template_emit import prescan_emit_vt_loop_structs
                prescan_emit_vt_loop_structs(self, func, fsig.variadic_template, param_types=self._sig_param_types_map(fsig))
            from .analysis.variadic_template import typevar_tuple_names_for_emit
            if fsig.func_ft.template_names or typevar_tuple_names_for_emit(fsig.func_ft, fsig.variadic_template):
                self._emit_function_template_prefix(fsig.func_ft, default_constraint=False, variadic_template=fsig.variadic_template)
            with self._use_block(sig):
                if fsig.lazy_params:
                    from .emit.lazy_param_emit import emit_lazy_param_prologue
                    emit_lazy_param_prologue(self, fsig.lazy_params)
                self._emit_generic_body_or_type_if(func, fsig, type_if_plan=type_if_plan, type_if_pick=type_if_pick)
                if func.name == 'result_done' and (not self._function_has_return(func)):
                    names = fsig.func_ft.template_names
                    if len(names) >= 2:
                        y, r = (names[0], names[1])
                        rt = cpp_result_type(y, r)
                        self.write_line(f"return {cpp_iter_result_return_expr(rt, f'{r}()')};")
                    else:
                        tn = names[0]
                        rt = cpp_result_type(tn)
                        self.write_line(f"return {cpp_iter_result_return_expr(rt, f'{tn}()')};")
        self.write_line()

    def _emit_stdlib_module_implementations(self) -> None:
        """标准库实现：非模板自由函数与类方法/模板 → 各模块 ``.inl``（测试 TU 只含 ``py2cpp.h``，不链 ``py2cpp.cpp``）。"""
        for module_path in self.module_order:
            if not self._is_stdlib_module(module_path):
                continue
            if module_path == RUNTIME_PKG and self.entry_module_path == RUNTIME_PKG and self._is_runtime_bootstrap():
                continue
            # 单模块 stdlib 入口由 ``_emit_entry_module_implementations`` 写入 ``.inl``，此处跳过以免重复定义。
            if module_path == self.entry_module_path and self.entry_module_path != RUNTIME_PKG:
                continue
            funcs = self._module_emit_functions_for(module_path)
            classes = self._stdlib_module_classes(module_path)
            non_tpl_funcs = [f for f in funcs if not self._function_sig_for(module_path, f).func_ft.template_names and (not has_named_decorator(f, 'native')) and (not is_overload_stub(f))]
            tpl_funcs = [f for f in funcs if self._function_sig_for(module_path, f).func_ft.template_names and (not has_named_decorator(f, 'native')) and (not is_overload_stub(f))]
            non_tpl_classes = [c for c in classes if not c.is_template()]
            tpl_classes = [c for c in classes if c.is_template()]
            emit_stdlib_module_paste_before(self, module_path)
            if non_tpl_funcs:
                with with_stdlib_inl(self, module_path):
                    for func in non_tpl_funcs:
                        qname = self._module_function_qualifier(module_path, self._module_function_cpp_name(module_path, func))
                        self._emit_stdlib_module_function_body(module_path, func, qualified_name=qname)
            if non_tpl_classes or tpl_classes or tpl_funcs:
                with with_stdlib_inl(self, module_path):
                    for info in non_tpl_classes + tpl_classes:
                        self._emit_stdlib_class_methods_body(info)
                    for func in tpl_funcs:
                        qname = self._module_function_qualifier(module_path, self._module_function_cpp_name(module_path, func))
                        self._emit_stdlib_module_function_body(module_path, func, qualified_name=qname)
            emit_stdlib_module_paste_after(self, module_path)

    @staticmethod
    def _generator_host_init(info: ClassInfo) -> str | None:
        return _generator_host_init(info)

    def _method_emit_context(self, info: ClassInfo, msig: MethodSig | None=None):
        if info.is_template():
            return self._use_module_inl(info.module_path)
        if msig and msig.func_ft.template_names and self._is_stdlib_module(info.module_path):
            return self._use_module_inl(info.module_path)
        if self._is_stdlib_module(info.module_path):
            return self._use_module_inl(info.module_path)
        return nullcontext()

    def _emit_body(self, body: list[ast.stmt]):
        emitter = self._active_generator_emitter
        if emitter is not None:
            for stmt in self._strip_leading_docstring(body):
                self._begin_py2cpp_stmt(stmt)
                emitter._emit_stmt(stmt)
            return
        for stmt in self._strip_leading_docstring(body):
            self._begin_py2cpp_stmt(stmt)
            self.visit(stmt)

    @contextmanager
    def _loop_with_else(self, orelse: list[ast.stmt]):
        flag: str | None = None
        if orelse:
            flag = temp_name('loop_else')
            self.write_line(f'bool {flag} = true;')
        self._loop_stack.append(_LoopFrame(flag))
        try:
            yield
        finally:
            self._loop_stack.pop()
        if flag:
            with self._use_block(f'if ({flag})'):
                self._emit_body(orelse)

    def _in_next_method(self) -> bool:
        return self._in_result_method()

    def _in_result_method(self) -> bool:
        return self.current_method is not None and self.current_method.name in ('__next__', 'send', '__resume')

    def _active_function_sig(self) -> FunctionSig | MethodSig | None:
        if self.current_method is None:
            return None
        if self.class_info is not None:
            return self.class_info.method_sigs.get(self.current_method.name)
        mp = self._active_module_path()
        return self.function_sigs.get((mp, self.current_method.name))

    def _in_noexcept_function(self) -> bool:
        sig = self._active_function_sig()
        return sig is not None and getattr(sig, 'is_noexcept', False)

    def _noexcept_result_cpp_type(self) -> str:
        sig = self._active_function_sig()
        if sig is None or not getattr(sig, 'is_noexcept', False):
            return ''
        return self._sig_return_full(sig)

    def _fault_ok_return_expr(self, value_cpp: str) -> str:
        return cpp_fault_ok_expr(self._noexcept_result_cpp_type(), value_cpp)

    def _fault_err_return_expr(self, err_cpp: str) -> str:
        return cpp_fault_err_expr(self._noexcept_result_cpp_type(), err_cpp)

    def _is_user_generator_class(self) -> bool:
        """含 ``__resume`` 的 ``*_generator`` 类（``__next__``/``send`` 已返回 ``PyIterResult``）。"""
        info = self.class_info
        return info is not None and any((m.name == '__resume' for m in info.methods.values()))

    def _next_result_cpp_type(self) -> str:
        if not self.current_method or not self.class_info:
            return cpp_result_type('void*')
        msig = self.class_info.method_sigs.get(self.current_method.name)
        if msig and msig.is_next:
            return msig.result_cpp_type
        if self.current_method.name in ('send', '__resume'):
            resume = self.class_info.method_sigs.get('__resume')
            if resume and resume.is_next:
                return resume.result_cpp_type
        return cpp_result_type('void*')

    def _iter_result_return_expr(self) -> str:
        rt = self._next_result_cpp_type()
        args = cpp_result_type_args(rt)
        if args is None:
            return cpp_iter_result_return_expr(rt)
        _y, r = args
        return cpp_iter_result_return_expr(rt, f'{r}()')

    def _result_value_expr(self, value_cpp: str) -> str:
        rt = self._next_result_cpp_type()
        return cpp_iter_result_yield_expr(rt, value_cpp)

    def _result_return_done_expr(self, return_cpp: str) -> str:
        rt = self._next_result_cpp_type()
        return cpp_iter_result_return_expr(rt, return_cpp)

    @staticmethod
    def _is___next___call(node: ast.expr) -> bool:
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (node.func.attr == '__next__') and (not node.args)

    def _emit_next_call_assign(self, name: str, elem_t: str, call: ast.Call, *, declare: bool):
        recv = self.visit(call.func.value)
        nx = temp_name('nx')
        self.write_line(f'{cpp_result_type(elem_t)} {nx} = {recv}.__next__();')
        self.write_line(f'if ({iter_result_done_cpp(nx)}) return {self._iter_result_return_expr()};')
        if declare:
            if self.scope:
                self._bind_scope_var(name, elem_t)
                self.scope.vars[name] = NameContext.Variable
            self.write_line(f'{elem_t} {name} = {iter_result_value_cpp(nx)};')
        else:
            self.write_line(f'{name} = {iter_result_value_cpp(nx)};')

    def _is_stop_iteration_exc(self, exc: ast.expr | None) -> bool:
        match exc:
            case ast.Name(id='StopIteration'):
                return True
            case ast.Call(func=ast.Name(id='StopIteration')):
                return True
            case _:
                return False

    def _emit_try_finally_body(self, frame: _TryFrame) -> None:
        if frame.finally_body:
            self._emit_body(frame.finally_body)

    def _emit_try_finally(self, frame: _TryFrame) -> None:
        if not frame.finally_body or frame.finally_emitted:
            return
        frame.finally_emitted = True
        self._emit_body(frame.finally_body)

    def _emit_active_finally(self) -> None:
        for frame in reversed(self._try_stack):
            self._emit_try_finally(frame)

    def visit_Return(self, node: ast.Return):
        self._emit_active_finally()
        self._emit_with_exits()
        if node.value and self._is_new_call(node.value) and self.current_method and self.current_method.returns:
            tparams = self._active_type_params()
            t = self._parse_storage_type(self.current_method.returns, tparams)
            self.write_line(f'return {_emit_new_ctor_expr(self, t, node.value)};')
            return
        if node.value is not None:
            from .emit.call_emit import is_new_receiver_attr_call, try_emit_new_receiver_static_call
            if is_new_receiver_attr_call(node.value) and self.current_method and self.current_method.returns:
                out = try_emit_new_receiver_static_call(self, node.value)
                if out is not None:
                    self.write_line(f'return {out};')
                    return
        if self._in_noexcept_function():
            sig = self._active_function_sig()
            ok_cpp = getattr(sig, 'noexcept_ok_cpp', '') if sig else ''
            if node.value is None:
                from .analysis.ir import cpp_ident
                val = f"{cpp_ident('PyNone')}()"
                if ok_cpp and ok_cpp != cpp_ident('PyNone'):
                    val = f'{ok_cpp}()'
                self.write_line(f'return {self._fault_ok_return_expr(val)};')
                return
            ret_ty = ok_cpp or self._method_return_cpp_type()
            val = self.visit(node.value)
            if ret_ty:
                val = self._coerce_expr_to_cpp_type(val, ret_ty, rhs_node=node.value)
            self.write_line(f'return {self._fault_ok_return_expr(val)};')
            return
        if self._in_result_method():
            if self.current_method and self.current_method.name == '__resume':
                return
            if node.value is None:
                self.write_line(f'return {self._iter_result_return_expr()};')
                return
            if self._is_user_generator_class() and self.current_method and (self.current_method.name in ('__next__', 'send')):
                self.write_line(f'return {self.visit(node.value)};')
                return
            match node.value:
                case ast.Name(id='self'):
                    raise NotImplementedError('return self from __next__')
                case _:
                    self.write_line(f'return {self._result_value_expr(self.visit(node.value))};')
            return
        if node.value is not None and self._is_none_constant(node.value):
            ret_ty = strip_cpp_ref(self._method_return_cpp_type() or '')
            bind = self._type_if_concrete_bind
            if bind is not None and ret_ty == bind[0]:
                ret_ty = bind[1]
            if ret_ty:
                from .analysis.ir import cpp_option_none_expr, default_new_ctor_cpp
                if is_refcount_type(ret_ty):
                    self.write_line(f'return {ret_ty}();')
                    return
                if is_optional_type(ret_ty):
                    self.write_line(f'return {cpp_option_none_expr(ret_ty)};')
                    return
                if ret_ty.endswith('*'):
                    self.write_line('return nullptr;')
                    return
                self.write_line(f'return {default_new_ctor_cpp(ret_ty)};')
                return
        if node.value is None:
            self.write_line('return;')
        else:
            match node.value:
                case ast.Name(id='self'):
                    self.write_line('return *this;')
                case _:
                    ret_ty = self._method_return_cpp_type()
                    val = self.visit(node.value)
                    if ret_ty:
                        val = self._coerce_expr_to_cpp_type(val, ret_ty, rhs_node=node.value)
                    self.write_line(f'return {val};')

    def visit_Pass(self, node: ast.Pass):
        pass

    def _cpp_exception_ctor(self, name: str) -> str:
        from .analysis.module_namespace import namespace_qualifier_for_module
        from .analysis.runtime_symbols import CPP_EXCEPTION_TYPES
        mp = self._active_module_path()
        for info in self.classes.values():
            if info.name == name and info.module_path == mp and (not self._is_type_marker(info)):
                ns = namespace_qualifier_for_module(mp)
                cls = info.cpp_name()
                if ns:
                    return f'::{ns}::{cls}()'
                return f'{cls}()'
        if name in CPP_EXCEPTION_TYPES:
            return cpp_exception_ctor(name)
        return f'{name}()'

    def visit_Raise(self, node: ast.Raise):
        from .emit.raise_emit import emit_raise
        emit_raise(self, node)

    def _list_elem_type_from_ann(self, annotation: ast.expr) -> str | None:
        """``list[T]`` 注解的元素类型（兼容旧调用方）。"""
        pair = self._appendable_init_from_ann(annotation)
        return pair[1] if pair and pair[0] == 'list' else None

    def _appendable_init_from_ann(self, annotation: ast.expr) -> tuple[str, str] | None:
        """``list[T]`` / ``deque[T]`` / 带 ``append`` 的类 → ``(完整 C++ 类型, 元素类型)``。"""
        from .analysis.ir import cpp_type_supports_list_literal_append
        t = self._parse_storage_type(annotation, self._active_type_params())
        pair = cpp_type_supports_list_literal_append(t, self.classes)
        if pair is not None:
            return pair
        if self.class_info and self.class_info.name in ('list', 'deque') and (len(self.class_info.type_params) >= 1) and isinstance(annotation, ast.Name) and (annotation.id in ('Self', self.class_info.cpp_name())):
            et = self.class_info.type_params[0]
            return (cpp_template_type(self.class_info.name, et), et)
        return None

    def _mapping_literal_spec_from_ann(self, annotation: ast.expr) -> str | None:
        """``{…}`` 注解目标 → 完整 C++ 映射类型（``dict`` / ``Counter`` 等）。"""
        from .analysis.ir import cpp_type_supports_dict_literal_setitem
        t = self._parse_storage_type(annotation, self._active_type_params())
        spec = cpp_type_supports_dict_literal_setitem(t, self.classes)
        if spec is not None:
            return spec
        if self.class_info and isinstance(annotation, ast.Name) and (annotation.id in ('Self', self.class_info.cpp_name())):
            if self.class_info.name == 'dict' and len(self.class_info.type_params) >= 2:
                return cpp_template_type('dict', ', '.join(self.class_info.type_params))
            if self.class_info.name == 'Counter' and len(self.class_info.type_params) >= 2:
                return f"{self.class_info.cpp_name()}<{', '.join(self.class_info.type_params)}>"
        return None

    def _dict_type_args_from_ann(self, annotation: ast.expr) -> str | None:
        spec = self._mapping_literal_spec_from_ann(annotation)
        if spec is None:
            return None
        if is_dict_type(spec):
            return dict_type_args(spec)
        return None

    def _set_literal_target_from_ann(self, annotation: ast.expr) -> tuple[str, str] | None:
        """``{…}`` 赋值：返回 ``(完整 C++ 类型, 元素类型)``，须支持 ``add``。"""
        from .analysis.ir import cpp_type_supports_set_literal_add
        t = self._parse_storage_type(annotation, self._active_type_params())
        elem_t = cpp_type_supports_set_literal_add(t, self.classes)
        if elem_t is not None:
            return (t, elem_t)
        if self.class_info and self.class_info.name == 'set' and (len(self.class_info.type_params) >= 1) and isinstance(annotation, ast.Name) and (annotation.id in ('Self', self.class_info.cpp_name())):
            et = self.class_info.type_params[0]
            return (cpp_template_type('set', et), et)
        return None

    def _set_elem_type_from_ann(self, annotation: ast.expr) -> str | None:
        target = self._set_literal_target_from_ann(annotation)
        if target is None:
            return None
        return target[1]

    def _frozenset_elem_type_from_ann(self, annotation: ast.expr) -> str | None:
        t = self._parse_type(annotation, self._active_type_params())
        if is_frozenset_type(t):
            return frozenset_elem_type(t)
        if self.class_info and self.class_info.name == 'frozenset' and (len(self.class_info.type_params) >= 1) and isinstance(annotation, ast.Name) and (annotation.id in ('Self', self.class_info.cpp_name())):
            return self.class_info.type_params[0]
        return None

    def _parse_storage_type(self, node: ast.expr | None, type_params: set[str]) -> str:
        from .analysis.ir import ClassInfo
        if node is None:
            return 'void'
        if self._type_if_concrete_bind is not None:
            cpp = self._parse_type(node, type_params)
            if cpp.endswith('&'):
                return cpp
            return ClassInfo.apply_refcount_storage_cpp_type(cpp, self.classes)
        dec: dict[str, tuple[str, ...]] = {}
        if self.class_info:
            dec.update(getattr(self.class_info, 'type_param_decorator_constraints', {}))
        if self.current_method:
            if self.class_info:
                sig = self.class_info.method_sigs.get(self.current_method.name)
                if sig:
                    dec.update(getattr(sig.func_ft, 'decorator_constraints', {}))
            else:
                mp = self._active_module_path()
                fsig = self.function_sigs.get((mp, self.current_method.name))
                if fsig:
                    dec.update(getattr(fsig.func_ft, 'decorator_constraints', {}))
        assert self.type_parser is not None
        cpp = self.type_parser.parse_storage_type(node, type_params, decorator_constraints=dec or None, self_class=self.class_info.template_cpp_type() if self.class_info else None)
        return ClassInfo.apply_refcount_storage_cpp_type(cpp, self.classes)

    @staticmethod
    def _is_new_call(expr: ast.expr | None) -> bool:
        return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and (expr.func.id == 'new')

    def _is_self_class_cpp_type(self, cpp_type: str) -> bool:
        info = self.class_info or self._self_type_class
        if not info:
            return False
        base = info.cpp_name()
        t = cpp_type.strip()
        return t == base or t.startswith(f'{base}<')

    def _current_method_is_static(self) -> bool:
        if self.current_method is None or self.class_info is None:
            return False
        name = self.current_method.name
        sig = self.class_info.method_sigs.get(name)
        if sig is not None and sig.is_static:
            return True
        ov = self.class_info.method_overload_sigs.get(name)
        return bool(ov and ov[0].is_static)

    @staticmethod
    def _str_literal_codepoints(text: str) -> list[int]:
        return _str_literal_codepoints(text)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if _try_emit_new_ann_assign(self, node):
            return
        from .emit.build_emit import try_emit_build_ann_assign
        from .emit.selector_emit import try_emit_select_ann_assign
        if try_emit_build_ann_assign(self, node):
            return
        if try_emit_select_ann_assign(self, node):
            return
        from .emit.variadic_template_emit import try_emit_vt_pack_to_tuple_ann_assign
        if try_emit_vt_pack_to_tuple_ann_assign(self, node):
            return
        if isinstance(node.target, ast.Name) and node.value is not None and isinstance(node.value, ast.Lambda) and (node.annotation is not None):
            from .emit.delegate_emit import try_emit_delegate_lambda_assign
            callable_type = self._parse_type(node.annotation, self._active_type_params())
            if is_py_callable_type(callable_type):
                if try_emit_delegate_lambda_assign(self, node.target, node.value, callable_type=callable_type):
                    return
        if node.value is not None:
            ann = node.annotation
            if self._try_emit_move_assign(node.target, node.value, target_ann=ann):
                return
            if self._try_emit_copy_assign(node.target, node.value, target_ann=ann):
                return
        tparams = self._active_type_params()
        match node.target:
            case ast.Name(id=name):
                if self._in_next_method() and node.value and self._is___next___call(node.value) and node.annotation:
                    elem_t = self._parse_type(node.annotation, tparams)
                    self._emit_next_call_assign(name, elem_t, node.value, declare=self._try_declare(name))
                    return
                appendable = self._appendable_init_from_ann(node.annotation) if node.annotation else None
                if appendable is not None and node.value is not None:
                    cpp_spec, elem_t = appendable
                    if isinstance(node.value, ast.ListComp):
                        if _try_emit_list_comp_assign(self, [node.target], node.value, elem_t=elem_t, cpp_spec=cpp_spec):
                            return
                    if isinstance(node.value, ast.List):
                        decl = self._try_declare(name)
                        _emit_appendable_literal_init(self, cpp_spec, name, elem_t, node.value.elts, declare=decl)
                        return
                    container = 'list' if is_list_type(cpp_spec) else 'deque' if is_deque_type(cpp_spec) else ''
                    if container and _emit_typed_container_init(self, name, container, elem_t, node.value, declare=self._try_declare(name)):
                        return
                    if is_list_type(cpp_spec) and isinstance(node.value, ast.Call):
                        analyzed = _analyze_list_ctor_call(self, node.value)
                        if analyzed and analyzed[1] != 'empty_untyped':
                            et, mode, args = analyzed
                            decl = self._try_declare(name)
                            _emit_list_ctor_init(self, name, et, mode, args, declare=decl)
                            return
                mapping_spec = self._mapping_literal_spec_from_ann(node.annotation) if node.annotation else None
                if mapping_spec is not None and node.value is not None:
                    if isinstance(node.value, ast.DictComp):
                        if _try_emit_dict_comp_assign(self, [node.target], node.value, cpp_spec=mapping_spec):
                            return
                    if isinstance(node.value, ast.Dict):
                        _emit_dict_literal_init(self, name, mapping_spec, node.value, declare=self._try_declare(name))
                        return
                    dict_inner = dict_type_args(mapping_spec) if is_dict_type(mapping_spec) else None
                    if dict_inner is not None and _emit_typed_container_init(self, name, 'dict', dict_inner, node.value, declare=self._try_declare(name)):
                        return
                set_target = self._set_literal_target_from_ann(node.annotation) if node.annotation else None
                if set_target is not None and node.value is not None:
                    set_spec, set_elem = set_target
                    if isinstance(node.value, ast.SetComp):
                        if _try_emit_set_comp_assign(self, [node.target], node.value, elem_t=set_elem, cpp_spec=set_spec):
                            return
                    if isinstance(node.value, ast.Set):
                        _emit_set_literal_init(self, name, set_elem, node.value, declare=self._try_declare(name), cpp_spec=set_spec)
                        return
                    if is_set_type(set_spec) and _emit_typed_container_init(self, name, 'set', set_elem, node.value, declare=self._try_declare(name)):
                        return
                fs_elem = self._frozenset_elem_type_from_ann(node.annotation) if node.annotation else None
                if fs_elem is not None and node.value is not None:
                    if isinstance(node.value, ast.SetComp):
                        _emit_frozenset_from_set_comp(self, name, fs_elem, node.value, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Set):
                        _emit_frozenset_from_set_literal(self, name, fs_elem, node.value, declare=self._try_declare(name))
                        if self.scope:
                            self._bind_scope_var(name, cpp_template_type('frozenset', fs_elem))
                        return
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and (node.value.func.id == 'frozenset'):
                        if not node.value.args:
                            _emit_empty_container_ctor(self, name, 'frozenset', fs_elem, declare=self._try_declare(name))
                            if self.scope:
                                self._bind_scope_var(name, cpp_template_type('frozenset', fs_elem))
                            return
                        if len(node.value.args) == 1:
                            _emit_frozenset_from_arg(self, name, fs_elem, node.value.args[0], declare=self._try_declare(name))
                            if self.scope:
                                self._bind_scope_var(name, cpp_template_type('frozenset', fs_elem))
                            return
                fl_elem = _frozenlist_elem_type_from_ann(self, node.annotation) if node.annotation else None
                if fl_elem is not None and node.value is not None:
                    if isinstance(node.value, ast.ListComp):
                        _emit_frozenlist_from_list_comp(self, name, fl_elem, node.value, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.List):
                        _emit_frozenlist_from_list_literal(self, name, fl_elem, node.value.elts, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and (node.value.func.id == 'frozenlist'):
                        if not node.value.args:
                            _emit_empty_container_ctor(self, name, 'frozenlist', fl_elem, declare=self._try_declare(name))
                            if self.scope:
                                self._bind_scope_var(name, cpp_template_type('frozenlist', fl_elem))
                            return
                        if len(node.value.args) == 1:
                            _emit_frozenlist_from_arg(self, name, fl_elem, node.value.args[0], declare=self._try_declare(name))
                            if self.scope:
                                self._bind_scope_var(name, cpp_template_type('frozenlist', fl_elem))
                            return
                fd_inner = _frozendict_inner_from_ann(self, node.annotation) if node.annotation else None
                if fd_inner is not None and node.value is not None:
                    if isinstance(node.value, ast.DictComp):
                        _emit_frozendict_from_dict_comp(self, name, fd_inner, node.value, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Dict):
                        _emit_frozendict_from_dict_literal(self, name, fd_inner, node.value, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and (node.value.func.id == 'frozendict'):
                        if not node.value.args:
                            _emit_empty_container_ctor(self, name, 'frozendict', fd_inner, declare=self._try_declare(name))
                            if self.scope:
                                self._bind_scope_var(name, cpp_template_type('frozendict', fd_inner))
                            return
                        if len(node.value.args) == 1:
                            _emit_frozendict_from_arg(self, name, fd_inner, node.value.args[0], declare=self._try_declare(name))
                            if self.scope:
                                self._bind_scope_var(name, cpp_template_type('frozendict', fd_inner))
                            return
                t = self._parse_storage_type(node.annotation, tparams)
                if node.value is not None and self._expr_is_list_element_ref(node.value):
                    if not t.endswith('&'):
                        t = f'{t}&'
                from .analysis.ir import cpp_type_supports_dict_literal_setitem
                mapping_spec = cpp_type_supports_dict_literal_setitem(t, self.classes)
                if mapping_spec is not None and node.value is not None:
                    if isinstance(node.value, ast.DictComp):
                        if _try_emit_dict_comp_assign(self, [node.target], node.value, cpp_spec=mapping_spec):
                            return
                    if isinstance(node.value, ast.Dict):
                        _emit_dict_literal_init(self, name, mapping_spec, node.value, declare=self._try_declare(name))
                        return
                    dict_inner = dict_type_args(mapping_spec) if is_dict_type(mapping_spec) else None
                    if dict_inner is not None and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and (node.value.func.id == 'dict') and (not node.value.args):
                        _emit_empty_container_ctor(self, name, 'dict', dict_inner, declare=self._try_declare(name))
                        return
                from .analysis.ir import cpp_type_supports_set_literal_add
                set_elem_ann = cpp_type_supports_set_literal_add(t, self.classes)
                if set_elem_ann is not None and node.value is not None:
                    elem = set_elem_ann
                    if isinstance(node.value, ast.SetComp):
                        if _try_emit_set_comp_assign(self, [node.target], node.value, elem_t=elem, cpp_spec=t):
                            return
                    if isinstance(node.value, ast.Set):
                        _emit_set_literal_init(self, name, elem, node.value, declare=self._try_declare(name), cpp_spec=t)
                        return
                    if is_set_type(t) and isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Name) and node.value.func.id == 'set' and (not node.value.args):
                            _emit_empty_container_ctor(self, name, 'set', elem, declare=self._try_declare(name))
                            return
                if is_frozenset_type(t) and node.value is not None:
                    elem = frozenset_elem_type(t) or ''
                    if isinstance(node.value, ast.Set):
                        _emit_frozenset_from_set_literal(self, name, elem, node.value, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        if node.value.func.id == 'frozenset' and (not node.value.args):
                            _emit_empty_container_ctor(self, name, 'frozenset', elem, declare=self._try_declare(name))
                            return
                        if node.value.func.id == 'frozenset' and len(node.value.args) == 1:
                            _emit_frozenset_from_arg(self, name, elem, node.value.args[0], declare=self._try_declare(name))
                            return
                if is_frozenlist_type(t) and node.value is not None:
                    elem = frozenlist_elem_type(t) or ''
                    if isinstance(node.value, ast.List):
                        _emit_frozenlist_from_list_literal(self, name, elem, node.value.elts, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        if node.value.func.id == 'frozenlist' and (not node.value.args):
                            _emit_empty_container_ctor(self, name, 'frozenlist', elem, declare=self._try_declare(name))
                            return
                        if node.value.func.id == 'frozenlist' and len(node.value.args) == 1:
                            _emit_frozenlist_from_arg(self, name, elem, node.value.args[0], declare=self._try_declare(name))
                            return
                if is_frozendict_type(t) and node.value is not None:
                    inner = frozendict_type_args(t) or ''
                    if isinstance(node.value, ast.Dict):
                        _emit_frozendict_from_dict_literal(self, name, inner, node.value, declare=self._try_declare(name))
                        return
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        if node.value.func.id == 'frozendict' and (not node.value.args):
                            _emit_empty_container_ctor(self, name, 'frozendict', inner, declare=self._try_declare(name))
                            return
                        if node.value.func.id == 'frozendict' and len(node.value.args) == 1:
                            _emit_frozendict_from_arg(self, name, inner, node.value.args[0], declare=self._try_declare(name))
                            return
                if is_stack_array_type(t):
                    pname = cpp_param(name)
                    decl = cpp_stack_array_var_decl(t, pname)
                    if node.value is not None:
                        if isinstance(node.value, ast.List):
                            _emit_stack_array_literal_init(self, name, t, node.value.elts, declare=self._try_declare(name), node=node)
                            return
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and is_char_stack_array_type(t):
                            _emit_char_stack_array_from_str_literal(self, name, t, node.value.value, declare=self._try_declare(name), node=node)
                            return
                        if not self._is_new_call(node.value):
                            raise NotImplementedError('栈数组请用 ``new()``、列表字面量 ``[…]`` 或下标赋值，勿其它整体赋值')
                        val = _emit_new_ctor_expr(self, t, node.value)
                        if self._try_declare(name):
                            if self.scope:
                                self._bind_scope_var(name, t)
                            self.write_line(f'{decl} = {val};')
                        else:
                            self.write_line(f'{pname} = {val};')
                        return
                    if self._try_declare(name):
                        if self.scope:
                            self._bind_scope_var(name, t)
                        self.write_line(f'{decl};')
                    return
                if is_array_type(t) and cpp_array_ndim(t) == 1 and (node.value is not None) and isinstance(node.value, ast.List):
                    _emit_heap_array_literal_init(self, cpp_param(name), t, node.value.elts, declare=self._try_declare(name), name=name, node=node)
                    return
                if is_bytes_type(t) and node.value is not None and isinstance(node.value, ast.Constant) and isinstance(node.value.value, bytes):
                    val = bytes_cpp_from_literal(node.value.value)
                    pname = cpp_param(name)
                    if self._try_declare(name):
                        if self.scope:
                            self._bind_scope_var(name, t)
                        self.write_line(f'{t} {pname} = {val};')
                    else:
                        self.write_line(f'{pname} = {val};')
                    return
                if node.value is not None and _try_emit_byte_array_bytes_literal(self, node.target, node.value, cpp_type=t, node=node):
                    return
                if node.value is not None and _try_emit_char_array_str_literal(self, node.target, node.value, cpp_type=t, node=node):
                    return
                if is_span_type(t):
                    pname = cpp_param(name)
                    decl = cpp_span_var_decl(t, pname)
                    if node.value is None:
                        if self._try_declare(name):
                            if self.scope:
                                self._bind_scope_var(name, t)
                            self.write_line(f'{decl};')
                        return
                    val = self.visit(node.value)
                    if self._try_declare(name):
                        if self.scope:
                            self._bind_scope_var(name, t)
                        self.write_line(f'{decl} = {val};')
                    else:
                        self.write_line(f'{pname} = {val};')
                    return
                val = self._visit_value_for_type(node.value, t) if node.value else f'{t}()'
                pname = cpp_param(name)
                if self._try_declare(name):
                    if self.scope:
                        self._bind_scope_var(name, t)
                    decl = format_cpp_callable_var_decl(t, pname) or f'{t} {pname}'
                    self.write_line(decl + (f' = {val};' if node.value else ';'))
                else:
                    if self.scope:
                        self._bind_scope_var(name, t)
                    self.write_line(f'{pname} = {val};')
            case ast.Attribute(value=ast.Name(id='self'), attr=attr):
                if _emit_self_member_typed_container_init(self, attr, node):
                    return
                if node.value and self._try_emit_self_field_move_from_param(attr, node.value):
                    return
                if node.annotation:
                    t = self._parse_storage_type(node.annotation, tparams)
                    if is_stack_array_type(t):
                        if node.value is not None:
                            raise NotImplementedError('T[:N] 栈数组成员请仅声明类型或 ``= new()``，勿整体赋值')
                        return
                    fcpp = self._attr_cpp_name(node.target, attr)
                    lhs = f'this->{fcpp}'
                    if node.value is not None and self._try_emit_self_empty_heap_buffer_init(attr, node.value, cpp_type=t):
                        return
                    if is_array_type(t) and cpp_array_ndim(t) == 1 and (node.value is not None) and isinstance(node.value, ast.List):
                        _emit_heap_array_literal_init(self, lhs, t, node.value.elts, declare=False, node=node)
                        return
                    if node.value is not None and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and is_char_heap_array_type(t):
                        _emit_char_heap_array_from_str_literal(self, '', node.value.value, t, declare=False, target_expr=lhs)
                        return
                    if node.value is not None and isinstance(node.value, ast.Constant) and isinstance(node.value.value, bytes) and is_byte_heap_array_type(t):
                        _emit_byte_heap_array_from_bytes_literal(self, '', node.value.value, t, declare=False, target_expr=lhs)
                        return
                val = self.visit(node.value) if node.value else '0'
                self.write_line(f'this->{self._attr_cpp_name(node.target, attr)} = {val};')
            case _:
                raise NotImplementedError('AnnAssign target')

    def _try_emit_new_simple_assign(self, target: ast.expr, call: ast.Call) -> bool:
        if not self._is_new_call(call):
            return False
        tparams = self._active_type_params()
        match target:
            case ast.Name(id=name):
                if not self.scope:
                    return False
                t = self._scope_storage(name)
                if not t:
                    return False
                val = _emit_new_ctor_expr(self, t, call)
                self.write_line(f'{cpp_param(name)} = {val};')
                return True
            case ast.Attribute(value=receiver, attr=attr):
                t = ''
                if isinstance(receiver, ast.Name) and receiver.id == 'self':
                    if self.class_info:
                        t = self._field_storage(attr)
                else:
                    t = self._field_cpp_type_for_attribute(receiver, attr) or ''
                if not t:
                    return False
                val = _emit_new_ctor_expr(self, t, call)
                if isinstance(receiver, ast.Name) and receiver.id == 'self':
                    self.write_line(f'this->{self._attr_cpp_name(target, attr)} = {val};')
                else:
                    recv, sep = self._receiver_access(receiver)
                    self.write_line(f'{recv}{sep}{self._attr_cpp_name(target, attr)} = {val};')
                return True
            case _:
                return False

    def visit_Assign(self, node: ast.Assign):
        if len(node.targets) == 1 and self._try_emit_new_simple_assign(node.targets[0], node.value):
            return
        if len(node.targets) == 1 and isinstance(node.value, ast.Attribute):
            from .emit.call_emit import try_emit_new_staticproperty_ref
            target = node.targets[0]
            field_cpp_type = None
            if isinstance(target, ast.Attribute):
                field_cpp_type = self._cpp_type_for_assign_target(target) or None
                if not field_cpp_type and self.class_info and self.class_info.dataclass_field_specs:
                    for spec in self.class_info.dataclass_field_specs:
                        if spec.name == target.attr:
                            field_cpp_type = self._parse_storage_type(spec.annotation, self._active_type_params())
                            break
            sp = try_emit_new_staticproperty_ref(self, node.value, field_cpp_type=field_cpp_type)
            if sp is not None:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and (target.value.id == 'self'):
                    self.write_line(f'this->{self._attr_cpp_name(target, target.attr)} = {sp};')
                    return
                if isinstance(target, ast.Name):
                    self.write_line(f'{cpp_param(target.id)} = {sp};')
                    return
        if len(node.targets) == 1 and isinstance(node.value, ast.Lambda):
            from .emit.delegate_emit import try_emit_delegate_lambda_assign
            if try_emit_delegate_lambda_assign(self, node.targets[0], node.value):
                return
        if len(node.targets) == 1 and _try_emit_byte_array_bytes_literal(self, node.targets[0], node.value, node=node):
            return
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute):
            target = node.targets[0]
            attr = target.attr
            ft = ''
            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                if self.class_info:
                    ft = self._field_storage(attr)
            else:
                ft = self._field_cpp_type_for_attribute(target.value, attr) or ''
            if ft and self._try_emit_self_empty_heap_buffer_init(attr, node.value, cpp_type=ft):
                if isinstance(target.value, ast.Name) and target.value.id == 'self':
                    return
            if _try_emit_field_typed_empty_literal_assign(self, target, node.value):
                return
        if len(node.targets) == 1 and _try_emit_char_array_str_literal(self, node.targets[0], node.value, node=node):
            return
        if _try_emit_heap_array_literal_assign(self, node.targets, node.value, node=node):
            return
        if _try_emit_stack_array_literal_assign(self, node.targets, node.value, node=node):
            return
        if _try_emit_list_init_assign(self, node.targets, node.value):
            return
        if _try_emit_dict_init_assign(self, node.targets, node.value):
            return
        if _try_emit_set_init_assign(self, node.targets, node.value):
            return
        if _try_emit_frozenset_init_assign(self, node.targets, node.value):
            return
        if _try_emit_frozenlist_init_assign(self, node.targets, node.value):
            return
        if _try_emit_frozendict_init_assign(self, node.targets, node.value):
            return
        if self._in_next_method() and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and self._is___next___call(node.value):
            name = node.targets[0].id
            elem_t = 'auto'
            if self.scope and self._scope_storage(name):
                elem_t = self._scope_storage(name)
            self._emit_next_call_assign(name, elem_t, node.value, declare=self._try_declare(name))
            return
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and self._is___next___call(node.value):
            name = node.targets[0].id
            recv = self.visit(node.value.func.value)
            if self._try_declare(name):
                if self.scope:
                    self._bind_scope_var(name, 'auto')
                    self.scope.vars[name] = NameContext.Variable
                self.write_line(f'auto {cpp_param(name)} = {recv}.__next__();')
            else:
                self.write_line(f'{cpp_param(name)} = {recv}.__next__();')
            return
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
            te = node.targets[0].elts
            if isinstance(node.value, ast.Tuple) and try_emit_parallel_tuple_assign(self, te, node.value.elts):
                return
        value, type_hint = (None, None)
        for target in node.targets:
            if self._try_emit_move_assign(target, node.value):
                continue
            if self._try_emit_copy_assign(target, node.value):
                continue
            if value is None:
                value, type_hint = self._rhs_cpp_for_assign(node.value)
            self._emit_assign(target, value, type_hint=type_hint, rhs_node=node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        if self._try_emit_delegate_augassign(node):
            return
        if self._try_emit_iform_assign(node):
            return
        if try_emit_subscript_augassign(self, node):
            return
        if self._try_emit_native_augassign(node):
            return
        bin_node = ast.BinOp(left=node.target, op=node.op, right=node.value)
        value = self.visit(bin_node)
        self._emit_assign(node.target, value, rhs_node=bin_node)

    @staticmethod
    def _is_primitive_cpp_type(cpp_type: str) -> bool:
        base = cpp_type.strip().rstrip('*').split('<', 1)[0]
        return base in (cpp_ident('int'), cpp_ident('int64'), cpp_ident('float'), cpp_ident('float64'), cpp_ident('bool'), cpp_ident('char'))

    def _cpp_type_for_assign_target(self, target: ast.expr) -> str:
        match target:
            case ast.Name(id=name):
                if self.scope:
                    return self._scope_storage(name)
            case ast.Attribute(value=val, attr=attr):
                ft = self._field_cpp_type_for_attribute(val, attr)
                if ft:
                    return ft
                if isinstance(val, ast.Name) and val.id == 'self' and self.class_info:
                    if attr in self.class_info.field_properties:
                        return self._field_storage(storage_field_for(attr))
                    if attr in self.class_info.postsetter_properties:
                        return self._field_storage(storage_field_for(attr))
                    return self._field_storage(attr)
            case ast.Subscript(value=base_expr, slice=sl):
                from .emit.subscript_emit import _ptr_subscript_base_type
                ptr_t = _ptr_subscript_base_type(self, base_expr)
                if ptr_t:
                    inner = ptr_t[:-1].strip() if ptr_t.endswith('*') else ptr_t
                    return inner
                if isinstance(base_expr, ast.Attribute) and isinstance(base_expr.value, ast.Name):
                    if base_expr.value.id == 'self' and self.class_info:
                        ft = self._field_storage(base_expr.attr)
                        if is_stack_array_type(ft):
                            return cpp_stack_array_elem_type(ft) or ''
                if isinstance(base_expr, ast.Name) and self.scope:
                    vt = self._scope_storage(base_expr.id)
                    if is_stack_array_type(vt):
                        return cpp_stack_array_elem_type(vt) or ''
        return ''

    def _try_emit_delegate_augassign(self, node: ast.AugAssign) -> bool:
        vtype = self._cpp_type_for_assign_target(node.target)
        if not vtype or not is_delegate_type(vtype, delegate_names=frozenset(self.delegates.keys())):
            return False
        match node.op:
            case ast.Add():
                op = '+='
            case ast.Sub():
                op = '-='
            case _:
                return False
        info = resolve_delegate_for_type(vtype, self.delegates)
        if info is None:
            return False
        rhs = try_emit_delegate_handler(self, info, node.value)
        if rhs is None:
            raise NotImplementedError(f'委托 += / -= 支持：模块函数、lambda、Cls.static_method、self.method；不支持的右侧: {ast.dump(node.value, include_attributes=False)}')
        target = self.visit(node.target)
        self.write_line(f'{target} {op} {rhs};')
        return True

    def _ensure_py_callable_method_thunk(self, class_info: ClassInfo, method_name: str, delegate_info) -> str:
        from .analysis.module_namespace import qualify_symbol_in_module
        slot_type = delegate_py_callable_type(delegate_info)
        cls_cpp = class_info.cpp_name()
        key = (cls_cpp, method_name, slot_type)
        existing = self._py_callable_thunk_names.get(key)
        if existing is not None:
            return existing
        if method_name not in class_info.method_sigs:
            raise NotImplementedError(f'委托 += self.{method_name} 需要已分析的实例方法签名')
        ret = delegate_info.ret_cpp
        param_decls = ', '.join((f'{p.cpp_type} {p.name}' for p in delegate_info.params))
        param_args = ', '.join((p.name for p in delegate_info.params))
        method_cpp = self._member_cpp_name(class_info, method_name)
        thunk_name = f'{cls_cpp}_{method_cpp}_py_callable_thunk'
        cls_qual = qualify_symbol_in_module(class_info.module_path, cls_cpp)
        call_args = param_args if param_args else ''
        body_lines: list[str] = [f"static {ret} {thunk_name}(void* ctx{(', ' + param_decls if param_decls else '')}) {{"]
        invoke = f'static_cast<{cls_qual}*>(ctx)->{method_cpp}({call_args})'
        if ret == 'void':
            body_lines.append(f'  {invoke};')
        else:
            body_lines.append(f'  return {invoke};')
        body_lines.append('}')
        body_lines.append('')
        self._py_callable_thunk_bodies.extend(body_lines)
        self._py_callable_thunk_names[key] = thunk_name
        return thunk_name

    def _delegate_lambda_param_types(self, lam: ast.Lambda) -> list[tuple[str, str]]:
        tparams = self._active_type_params()
        pairs: list[tuple[str, str]] = []
        for arg in lam.args.args:
            if arg.annotation:
                cpp_t = self._parse_type(arg.annotation, tparams)
            else:
                cpp_t = cpp_ident('int')
            pairs.append((arg.arg, cpp_t))
        return pairs

    def _emit_delegate_cpp_lambda(self, lam: ast.Lambda, delegate_info: DelegateInfo | None, *, var_name: str | None=None) -> str:
        from .emit.delegate_emit import lambda_ast_uses_name, validate_delegate_lambda, validate_delegate_lambda_shape
        if delegate_info is not None:
            validate_delegate_lambda(lam, delegate_info)
            param_pairs = [(lam_arg.arg, deleg_param.cpp_type) for deleg_param, lam_arg in zip(delegate_info.params, lam.args.args)]
            ret = delegate_info.ret_cpp
        else:
            validate_delegate_lambda_shape(lam)
            param_pairs = self._delegate_lambda_param_types(lam)
            ret = None
        uses_self = lambda_ast_uses_name(lam, 'self')
        if uses_self and self.class_info is None:
            raise NotImplementedError('委托 lambda 引用 self 须位于实例方法内')
        if var_name is None:
            idx = self._delegate_lambda_counter
            self._delegate_lambda_counter += 1
            var = f'_delegate_lam_{lam.lineno}_{lam.col_offset}_{idx}'
        else:
            var = var_name
        param_decls = ', '.join((f'{cpp_t} {name}' for name, cpp_t in param_pairs))
        capture = '[this]' if uses_self else '[]'
        saved_types = dict(self.scope.var_types) if self.scope else {}
        saved_vars = dict(self.scope.vars) if self.scope else {}
        try:
            if self.scope:
                for name, cpp_t in param_pairs:
                    self._bind_scope_var(name, cpp_t)
                    self.scope.vars[name] = NameContext.Variable
            body = self._visit_value_expr(lam.body)
        finally:
            if self.scope:
                self.scope.var_types.clear()
                self.scope.var_types.update(saved_types)
                self.scope.vars.clear()
                self.scope.vars.update(saved_vars)
        if ret == 'void':
            body_stmt = f'{body};'
        else:
            body_stmt = f'return {body};'
        self.write_line(f'auto {var} = {capture}({param_decls}) {{ {body_stmt} }};')
        return var

    def _inject_py_callable_thunks(self) -> None:
        if not self._py_callable_thunk_bodies:
            return
        self._insert_lines_after_includes(self.source_lines, self._py_callable_thunk_bodies)

    def _try_emit_iform_assign(self, node: ast.AugAssign) -> bool:
        iform = self._binop_iform(node.op)
        if not iform:
            return False
        match node.target:
            case ast.Name() as target:
                info = self._class_info_for_expr(target)
                if not info or iform not in info.methods:
                    return False
                self.write_line(f'{self._member_call_with_arg(target, iform, node.value)};')
                return True
            case ast.Attribute(value=val, attr=attr) if not (isinstance(val, ast.Name) and val.id == 'self'):
                info = self._class_info_for_receiver(val)
                if not info or iform not in info.methods:
                    return False
                recv, sep = self._receiver_access(val)
                rhs = self._visit_value_expr(node.value)
                self.write_line(f'{recv}{sep}{iform}({rhs});')
                return True
            case ast.Attribute(value=ast.Name(id='self'), attr=attr):
                if self.class_info and iform in self.class_info.methods:
                    ft = self._field_storage(attr)
                    if self._is_primitive_cpp_type(ft):
                        return False
                    rhs = self._visit_value_expr(node.value)
                    self.write_line(f'this->{iform}({rhs});')
                    return True
            case _:
                return False
        return False

    def _try_emit_native_augassign(self, node: ast.AugAssign) -> bool:
        aug_op = self._cpp_augassign_op(node.op)
        if aug_op is None:
            return False
        vtype = self._cpp_type_for_assign_target(node.target)
        if is_scalar_int_type(vtype) or is_scalar_float_type(vtype):
            if isinstance(node.op, (ast.Mod, ast.Div, ast.FloorDiv)):
                return False
        rhs = self._visit_value_expr(node.value)
        match node.target:
            case ast.Name(id=name):
                if not self._is_primitive_cpp_type(vtype):
                    return False
                self.write_line(f'{cpp_param(name)} {aug_op} {rhs};')
                return True
            case ast.Attribute(value=ast.Name(id='self'), attr=attr):
                if not self._is_primitive_cpp_type(vtype):
                    return False
                storage_attr = attr
                if self.class_info and attr in self.class_info.field_properties:
                    storage_attr = storage_field_for(attr)
                self.write_line(f'this->{self._attr_cpp_name(node.target, storage_attr)} {aug_op} {rhs};')
                return True
            case ast.Subscript(value=base_expr, slice=sl):
                vtype = self._cpp_type_for_assign_target(node.target)
                if not self._is_primitive_cpp_type(vtype):
                    return False
                idx = self.visit(sl)
                from .emit.subscript_emit import _ptr_subscript_base_type
                if _ptr_subscript_base_type(self, base_expr) is not None:
                    base_cpp = self.visit(base_expr)
                    self.write_line(f'{base_cpp}[{idx}] {aug_op} {rhs};')
                    return True
                if isinstance(base_expr, ast.Attribute) and isinstance(base_expr.value, ast.Name):
                    if base_expr.value.id == 'self':
                        fcpp = self._attr_cpp_name(base_expr.value, base_expr.attr)
                        ft = self._field_storage(base_expr.attr) if self.class_info else ''
                        if is_stack_array_type(ft):
                            self.write_line(f'this->{fcpp}.__getitem__({idx}) {aug_op} {rhs};')
                            return True
                if isinstance(base_expr, ast.Name):
                    base_cpp = cpp_param(base_expr.id)
                    vt = self._scope_storage(base_expr.id) if self.scope else ''
                    if is_stack_array_type(vt):
                        self.write_line(f'{base_cpp}.__getitem__({idx}) {aug_op} {rhs};')
                        return True
            case _:
                return False
        return False

    def _emit_assign(self, target: ast.expr, value: str, *, type_hint: str | None=None, rhs_node: ast.expr | None=None):
        match target:
            case ast.Name(id=name):
                if name == '_':
                    self.write_line(f'(void)({value});')
                    return
                vtype = self._lookup_var_type(name) or None
                if self._try_declare(name):
                    if not vtype:
                        vtype = type_hint or (self._constructor_type(rhs_node) if rhs_node else None) or (self._infer_expr_cpp_type(rhs_node) if rhs_node else None) or self._type_from_rhs(value) or (cpp_ident('int') if self._looks_like_int_rhs(value) else 'auto')
                    if '-> decltype' in vtype:
                        vtype = 'auto'
                    if self.scope:
                        self._bind_scope_var(name, vtype)
                    pname = cpp_param(name)
                    decl = format_cpp_callable_var_decl(vtype, pname) or f'{vtype} {pname}'
                    coerced = self._coerce_expr_to_cpp_type(value, vtype, rhs_node=rhs_node)
                    self.write_line(f'{decl} = {coerced};')
                else:
                    vtype = self._lookup_var_type(name) or type_hint
                    coerced = value
                    if vtype:
                        coerced = self._coerce_expr_to_cpp_type(value, vtype, rhs_node=rhs_node)
                    self.write_line(f'{cpp_param(name)} = {coerced};')
            case ast.Attribute(value=ast.Name(id='self'), attr=attr):
                if rhs_node is not None and self._try_emit_self_field_protocol_from_other(attr, rhs_node):
                    pass
                elif rhs_node is not None and self._try_emit_self_field_move_from_param(attr, rhs_node):
                    pass
                elif self.class_info and attr in self.class_info.properties and (self.class_info.properties[attr].setter or self.class_info.properties[attr].postsetter):
                    val = self._coerce_property_setter_value(self.class_info, attr, value, rhs_node)
                    self.write_line(f'this->{self._property_setter_cpp_name(self.class_info, attr)}({val});')
                else:
                    storage_attr = attr
                    if self.class_info and attr in self.class_info.field_properties:
                        storage_attr = storage_field_for(attr)
                    ft = self._field_storage(storage_attr) if self.class_info else ''
                    assign_val = value
                    from .analysis.type_emit import scope_binding_storage_cpp, scope_has_param
                    if ft.endswith('*') and rhs_node is not None and isinstance(rhs_node, ast.Name) and self.scope and scope_has_param(self.scope, rhs_node.id):
                        pt = scope_binding_storage_cpp(self.scope, rhs_node.id)
                        if not pt.endswith('*') and (not is_refcount_type(pt)):
                            assign_val = f'&{cpp_param(rhs_node.id)}'
                    elif ft:
                        from .analysis.ir import strip_cpp_ref
                        from .analysis.type_pred import is_erased_protocol_storage_type
                        ft_node = self._field_type_node(storage_attr)
                        if is_erased_protocol_storage_type(ft_node) and isinstance(rhs_node, ast.Name) and self.scope and scope_has_param(self.scope, rhs_node.id):
                            ft_base = strip_cpp_ref(self._field_storage(storage_attr))
                            assign_val = f'static_cast<{ft_base}&&>({cpp_param(rhs_node.id)})'
                        else:
                            assign_val = self._coerce_expr_to_cpp_type(value, ft, rhs_node=rhs_node)
                    self.write_line(f'this->{self._attr_cpp_name(target, storage_attr)} = {assign_val};')
            case ast.Subscript(value=base_expr, slice=sl):
                set_val = self._coerce_subscript_assign_value(base_expr, value)
                emit_subscript_store(self, base_expr, sl, set_val)
            case ast.Tuple(elts=elts):
                if not self._emit_pytuple_unpack(value, elts, rhs_node=rhs_node):
                    raise NotImplementedError('多目标赋值右值须为元组字面量 ``(a, b, …)``、``a, b = …`` 形式，或返回 ``PyTuple<…>`` 的表达式')
            case ast.Attribute(value=val, attr=attr) if not (isinstance(val, ast.Name) and val.id == 'self'):
                from .analysis.proxy import unwrap_super_receiver
                if isinstance(val, ast.Name) and val.id == 'super' or unwrap_super_receiver(val):
                    from .emit.proxy_emit import try_super_assign
                    if try_super_assign(self, attr, value, rhs_node=rhs_node):
                        return
                from .emit.proxy_emit import try_proxy_peel_assign
                if try_proxy_peel_assign(self, val, attr, value, rhs_node=rhs_node):
                    return
                info = self._class_info_for_receiver(val)
                if info and attr not in info.fields and (attr not in info.properties) and ('__setattr__' in info.methods):
                    recv = self.visit(val)
                    self.write_line(f'{recv}.__setattr__({str_cpp_from_literal(attr)}, {value});')
                    return
                assign_val = value
                from .analysis.type_emit import scope_binding_storage_cpp, scope_has_param
                if info and self._field_storage(attr, info=info).endswith('*') and (rhs_node is not None) and isinstance(rhs_node, ast.Name) and self.scope and scope_has_param(self.scope, rhs_node.id):
                    pt = scope_binding_storage_cpp(self.scope, rhs_node.id)
                    if pt and (not pt.endswith('*')) and (not is_refcount_type(pt)):
                        assign_val = f'&{cpp_param(rhs_node.id)}'
                if not self._emit_property_set(val, attr, assign_val, rhs_node=rhs_node):
                    self.write_line(f'{self.visit(target)} = {assign_val};')
            case _:
                self.write_line(f'{self.visit(target)} = {value};')

    def _infer_subscript_type(self, value: str, index: int) -> str | None:
        vt = self._scope_storage(value)
        if vt and is_list_type(vt):
            inner = list_elem_type(vt)
            return inner
        return None

    @staticmethod
    def _type_from_rhs(value: str) -> str | None:
        if not value:
            return None
        v = value.strip()
        if v.startswith('new '):
            paren = v.find('(', 4)
            if paren > 4:
                return v[4:paren].strip() + '*'
        if v.startswith('PyTuple<'):
            paren = v.find('(')
            if paren > 0:
                return v[:paren]
        if v.endswith('()') and '<' in v:
            return v[:-2]
        if v.startswith('makeRefCount<') and '(' in v:
            inner = v[len('makeRefCount<'):v.find('(')]
            return cpp_refcount_type(inner.strip())
        rc = cpp_ident('RefCount')
        if v.startswith(f'{rc}<') and '(' in v:
            return v[:v.find('(')]
        ps = cpp_ident('str')
        if v.startswith(f'{ps}('):
            return ps
        return None

    @staticmethod
    def _pytuple_element_types(vt: str) -> list[str]:
        from .analysis.ir import cpp_template_inner_args, split_cpp_template_args

        inner = cpp_template_inner_args(vt, "PyTuple<")
        if inner is None:
            return []
        if not inner.strip():
            return []
        return split_cpp_template_args(inner)

    def _function_sig_for_call(self, node: ast.Call) -> FunctionSig | None:
        match node.func:
            case ast.Name(id=name):
                return self._function_sig_for_name(name)
            case ast.Attribute():
                attrs: list[str] = []
                cur: ast.expr = node.func
                while isinstance(cur, ast.Attribute):
                    attrs.insert(0, cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    from .analysis.imports import resolve_import_attribute_chain
                    binding = resolve_import_attribute_chain(self, cur.id, attrs)
                    if binding is not None and binding.kind == 'function':
                        fsig = self.function_sigs.get((binding.module_path, binding.symbol))
                        if fsig is not None:
                            return fsig
            case _:
                pass
        return None

    def _call_return_pytuple_cpp_type(self, node: ast.Call) -> str:
        fsig = self._function_sig_for_call(node)
        if fsig is not None:
            ret = self._sig_return_full(fsig)
            if ret.startswith('PyTuple<'):
                return ret
        ret = self._infer_expr_cpp_type(node)
        if ret.startswith('PyTuple<'):
            return ret
        return ''

    def _expr_tuple_type(self, node: ast.expr) -> str:
        match node:
            case ast.Call() as call:
                return self._call_return_pytuple_cpp_type(call)
            case ast.Name():
                vt = self._expr_var_type(node)
                if vt.startswith('PyTuple<'):
                    return vt
            case _:
                pass
        return ''

    def _emit_pytuple_unpack(self, value: str, elts: list[ast.expr], *, rhs_node: ast.expr | None=None) -> bool:
        vt = self._type_from_rhs(value)
        if not vt and rhs_node is not None:
            vt = self._expr_tuple_type(rhs_node)
        if not vt or not vt.startswith('PyTuple<'):
            return False
        types = self._pytuple_element_types(vt)
        from .emit.pytuple_unpack_emit import emit_pytuple_unpack_assignments
        emit_pytuple_unpack_assignments(self, value, elts, types)
        return True

    def _expr_var_type(self, node: ast.expr) -> str:
        match node:
            case ast.Name(id=name):
                if self.scope:
                    return self._scope_storage(name)
            case _:
                return ''
        return ''

    @staticmethod
    def _reject_tuple_literal_expr(node: ast.expr, *, context: str) -> None:
        """``x in (a,b)`` / ``(a,b)[i]`` 等不译元组字面量容器；见 reference §8.3。"""
        if isinstance(node, ast.Tuple):
            raise NotImplementedError(f'{context}：不支持元组字面量 ``(a, b, …)``；成员检测用 ``x in {{a,b}}``、``x == a or x == b`` 或 ``match``；下标表用 ``x: list[T] = [a, b, c]`` 再 ``x[i]`` 或 ``match``。')

    def _try_pytuple_const_subscript(self, value_node: ast.expr, slice_node: ast.expr) -> str | None:
        if isinstance(value_node, ast.Tuple):
            return None
        if not isinstance(slice_node, ast.Constant) or not isinstance(slice_node.value, int):
            return None
        idx = slice_node.value
        vt = self._expr_var_type(value_node)
        if not vt.startswith('PyTuple<'):
            return None
        base = self.visit(value_node)
        sep = self._member_access(base)
        return f'{base}{sep}template get<{idx}>()'

    @staticmethod
    def _looks_like_int_rhs(value: str) -> bool:
        v = value.strip()
        if v.lstrip('-').isdigit():
            return True
        if v.startswith('(') and v.endswith(')') and ('+' in v):
            parts = v[1:-1].split('+')
            return all((p.strip().lstrip('-').isdigit() or p.strip().isidentifier() for p in parts))
        return False

    def _is_local_declared(self, name: str) -> bool:
        from .analysis.type_emit import scope_has_type_binding
        for scope in reversed(self.scopes):
            if scope_has_type_binding(scope, name):
                return True
        return False

    def _lookup_var_type(self, name: str) -> str:
        return self._scope_storage(name)

    def _try_declare(self, name: str) -> bool:
        if self._is_local_declared(name):
            return False
        if self.scope:
            self.scope.vars[name] = NameContext.Variable
        return True

    def _bool_test_condition(self, node: ast.expr) -> str:
        """``if``/``while`` 条件：``and``/``or`` 用 ``&&``/``||``，勿用值语义的 ``?:``。"""
        match node:
            case ast.BoolOp(op=ast.And(), values=vals):
                return ' && '.join((self._bool_test_condition(v) for v in vals))
            case ast.BoolOp(op=ast.Or(), values=vals):
                return ' || '.join((self._bool_test_condition(v) for v in vals))
            case ast.UnaryOp(op=ast.Not(), operand=op):
                inner = self._bool_test_condition(op)
                if inner.isidentifier() or inner in ('true', 'false'):
                    return f'!{inner}'
                return f'!({inner})'
            case ast.Compare():
                return self.visit(node)
            case _:
                return self._truthiness_condition(node)

    def visit_If(self, node: ast.If, in_elif: bool=False):
        if not in_elif and looks_like_macro_if_head(node.test):
            emit_macro_if_chain(self, collect_macro_if_chain(node))
            return
        kw = 'else if' if in_elif else 'if'
        with self._use_block(f'{kw} ({self._bool_test_condition(node.test)})'):
            self._emit_body(node.body)
        match node.orelse:
            case []:
                pass
            case [ast.If() as elif_node]:
                self.visit_If(elif_node, True)
            case _:
                with self._use_block('else'):
                    self._emit_body(node.orelse)

    def visit_Match(self, node: ast.Match):
        emit_match(self, node)

    def visit_While(self, node: ast.While):
        visit_while(self, node)

    def _active_with_managers(self) -> list[str]:
        out: list[str] = []
        for frame in self._with_stack:
            out.extend(frame.managers)
        return out

    def _emit_with_exits(self) -> None:
        for mgr in reversed(self._active_with_managers()):
            self.write_line(f'{mgr}.__exit__();')

    def visit_AsyncWith(self, node: ast.AsyncWith):
        raise NotImplementedError('async with 仅支持 async def 内（由 coroutine_desugar 脱糖）')

    def visit_With(self, node: ast.With):
        if getattr(node, 'is_async', False):
            raise NotImplementedError('async with 仅支持 async def 内（由 coroutine_desugar 脱糖）')
        frame = _WithFrame([])
        self._with_stack.append(frame)
        try:
            self._emit_with_items(node.items, node.body, frame)
        finally:
            self._with_stack.pop()

    def _emit_with_items(self, items: list[ast.withitem], body: list[ast.stmt], frame: _WithFrame) -> None:
        if not items:
            self._emit_with_body(body)
            return
        item = items[0]
        mgr = temp_name('with_mgr')
        frame.managers.append(mgr)
        mgr_type = self._constructor_type(item.context_expr)
        with self._use_block():
            self.write_line(f'auto {mgr} = {self.visit(item.context_expr)};')
            if mgr_type and self.scope:
                self._bind_scope_var(mgr, mgr_type)
            if item.optional_vars is None:
                self.write_line(f'{mgr}.__enter__();')
            else:
                self._emit_with_as_target(item.optional_vars, mgr, mgr_type=mgr_type)
            self._emit_with_items(items[1:], body, frame)
            self.write_line(f'{mgr}.__exit__();')

    def _context_manager_enter_return_type(self, mgr_type: str | None) -> str | None:
        if not mgr_type:
            return None
        from .analysis.ir import strip_cpp_ref
        from .analysis.stubs.protocol_erase_stubs import parse_erased_protocol_from_cpp
        t = strip_cpp_ref(mgr_type)
        parsed = parse_erased_protocol_from_cpp(t)
        if parsed is not None and parsed[0] == 'ContextManager' and parsed[1]:
            return parsed[1]
        info = self._class_info_for_type(t)
        if info is None:
            return None
        ret = self._receiver_method_return_cpp_type(info, '__enter__')
        if not ret or ret == 'Self':
            enter_ty = info.storage_cpp_type()
        else:
            enter_ty = strip_cpp_ref(ret)
        if info.module_path != RUNTIME_PKG and self._is_stdlib_module(info.module_path):
            base, _, tail = enter_ty.partition('<')
            if tail:
                enter_ty = f'{qualify_symbol_in_module(info.module_path, base)}<{tail}'
            else:
                enter_ty = qualify_symbol_in_module(info.module_path, enter_ty)
        return enter_ty

    def _emit_with_as_target(self, target: ast.expr, mgr: str, *, mgr_type: str | None=None) -> None:
        """``as x`` 绑定 ``__enter__()`` 返回值（对齐 CPython ``with m as x``）。"""
        enter_tmp = temp_name('with_ent')
        self.write_line(f'auto {enter_tmp} = {mgr}.__enter__();')
        enter_ty = self._context_manager_enter_return_type(mgr_type)
        match target:
            case ast.Name(id=name):
                pname = cpp_param(name)
                if self._try_declare(name) and self.scope:
                    self.scope.vars[name] = NameContext.Variable
                    if enter_ty:
                        self._bind_scope_var(name, enter_ty)
                        self.write_line(f'{enter_ty} {pname} = {enter_tmp};')
                    else:
                        self.write_line(f'auto {pname} = {enter_tmp};')
                else:
                    self.write_line(f'auto {pname} = {enter_tmp};')
            case _:
                raise NotImplementedError('with ... as 仅支持简单变量名')

    def _emit_with_body(self, body: list[ast.stmt]) -> None:
        self._emit_body(body)

    def visit_Break(self, node: ast.Break):
        self._emit_active_finally()
        self._emit_with_exits()
        if not self._loop_stack:
            raise NotImplementedError('break 不在循环内')
        flag = self._loop_stack[-1].else_flag
        if flag:
            self.write_line(f'{flag} = false;')
        self.write_line('break;')

    def visit_Continue(self, node: ast.Continue):
        if not self._loop_stack:
            raise NotImplementedError('continue 不在循环内')
        self._emit_active_finally()
        self.write_line('continue;')

    def visit_Try(self, node: ast.Try):
        from .emit.try_emit import emit_try
        emit_try(self, node)

    def visit_TryStar(self, node: ast.TryStar):
        from .emit.try_emit import emit_try_star
        emit_try_star(self, node)

    def _in_try_star(self) -> bool:
        return self._try_star_depth > 0

    @staticmethod
    def _is_direct_range_call(node: ast.expr) -> bool:
        return is_direct_range_call(node)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        visit_async_for(self, node)

    def visit_For(self, node: ast.For):
        visit_for(self, node)

    def _emit_native_range_loop_from_call(self, name: str, iter_call: ast.Call, body: Callable[[], None]) -> None:
        emit_native_range_loop_from_call(self, name, iter_call, body)

    def visit_Expr(self, node: ast.Expr):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            if node.value.func.id == 'print':
                emit_print(self, node.value)
                return
            if node.value.func.id == 'setattr' and len(node.value.args) == 3 and ((field := static_field_name(node.value.args[1])) is not None):
                self._emit_static_field_set(node.value.args[0], field, node.value.args[2])
                return
        if self.debug and isinstance(node.value, ast.Call):
            expr = emit_call_expr(self, node.value)
            if expr and expr.strip():
                label = self._debug_call_label(node.value).replace('\\', '\\\\').replace('"', '\\"')
                self.write_line(f'_py2cpp_debug_call("{label}");')
                self.write_line(f'{expr};')
                return
        val = self.visit(node.value)
        if val:
            self.write_line(f'{val};')

    def _is_ptr_type(self, t: str) -> bool:
        return bool(t) and t.endswith('*') and (t not in ('c_str', 'const char*'))

    @staticmethod
    def _array_ndim_from_type(t: str) -> int | None:
        return cpp_array_ndim(t)

    def _expr_cpp_type(self, node: ast.expr) -> str:
        match node:
            case ast.Name(id=name):
                if self.scope:
                    return self._scope_storage(name)
            case ast.Attribute(value=ast.Name(id='self'), attr=attr):
                if self.class_info:
                    return self._field_storage(attr)
            case _:
                return ''
        return ''

    @staticmethod
    def _index_tuple_ctor(ndim: int, args: str) -> str:
        return index_tuple_ctor(ndim, args)

    def visit_Call(self, node: ast.Call):
        return self._debug_wrap_call(node, emit_call_expr(self, node))

    def _debug_call_label(self, node: ast.Call) -> str:
        loc = self._debug_loc(node)
        match node.func:
            case ast.Name(id=name):
                return f'{loc} {name}()'
            case ast.Attribute(value=val, attr=attr):
                recv = self._debug_recv_label(val)
                if recv:
                    return f'{loc} {recv}.{attr}()'
                return f'{loc} {attr}()'
            case _:
                return f'{loc} call()'

    def _debug_recv_label(self, node: ast.expr) -> str:
        match node:
            case ast.Name(id=name):
                return name
            case ast.Attribute(value=inner, attr=attr):
                base = self._debug_recv_label(inner)
                return f'{base}.{attr}' if base else attr
            case _:
                return ''

    def _debug_call_is_void(self, node: ast.Call) -> bool:
        match node.func:
            case ast.Name(id=name):
                return name in ('destroy', 'free', 'freeArray', 'init')
            case ast.Subscript(value=ast.Name(id=name), slice=_):
                return name in ('destroy', 'free', 'freeArray', 'init')
            case _:
                return False

    def _debug_uses_ref_wrap(self, expr: str) -> bool:
        """仅当整段表达式就是 ``(this->...).__getitem__(...)`` 时用引用包装。"""
        import re
        e = expr.strip()
        return bool(re.match('^\\(this->[^)]+\\)\\.__getitem__\\([^)]*\\)$', e))

    def _debug_wrap_call(self, node: ast.Call, expr: str) -> str:
        if not self.debug or not expr or (not expr.strip()):
            return expr
        label = self._debug_call_label(node).replace('\\', '\\\\').replace('"', '\\"')
        if self._debug_call_is_void(node):
            return expr
        if self._debug_uses_ref_wrap(expr):
            return f'_py2cpp_debug_wrap("{label}", {expr})'
        return f'_py2cpp_debug_wrap_val("{label}", {expr})'

    def _class_info_for_ref(self, name: str) -> ClassInfo | None:
        binding = self._effective_import_bindings().get(name)
        if binding is not None and binding.kind == 'class':
            return self.classes.get(binding.symbol)
        return self.classes.get(name)

    def _name_refers_to_class(self, name: str) -> bool:
        """``Name`` 是否指类型（``Foo.bar``），而非实例变量（``result.bar``）。"""
        if name in self.classes:
            return True
        binding = self._effective_import_bindings().get(name)
        return binding is not None and binding.kind == 'class'

    def _member_access(self, receiver: str) -> str:
        if receiver.startswith('(') and receiver.endswith(')'):
            inner = receiver[1:-1].strip()
            if inner.startswith('this->') and '.' not in inner and (inner.count('->') == 1):
                return self._member_access(inner)
            return '.'
        if receiver.count('->') >= 2:
            return '.'
        if receiver == 'this':
            return '->'
        if receiver.startswith('this->') and self.class_info:
            field = receiver[6:].split('->', 1)[0]
            ft = self._field_storage(field)
            if ft.rstrip().endswith('*'):
                return '->'
            return '.'
        if receiver.endswith('*'):
            return '->'
        if self.scope:
            from .analysis.type_emit import scope_binding_storage_cpp
            bound = (
                set(self.scope.var_type_nodes)
                | set(self.scope.var_types)
                | set(self.scope.param_type_nodes)
                | set(self.scope.param_types)
            )
            for name in bound:
                t = scope_binding_storage_cpp(self.scope, name)
                if receiver in (name, cpp_param(name)) and self._uses_ptr_access(t):
                    return '->'
        return '.'

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.ctx, ast.Load):
            from .analysis.proxy import unwrap_super_receiver
            if isinstance(node.value, ast.Name) and node.value.id == 'super' or unwrap_super_receiver(node.value):
                from .emit.proxy_emit import try_emit_super_attribute
                out = try_emit_super_attribute(self, node.attr)
                if out is not None:
                    return out
            from .emit.proxy_emit import try_proxy_peel_attribute
            peeled = try_proxy_peel_attribute(self, node.value, node.attr)
            if peeled is not None:
                return peeled
            if isinstance(node.value, ast.Name):
                from .analysis.ir import scalar_type_static_attr_cpp
                scalar_attr = scalar_type_static_attr_cpp(node.value.id, node.attr)
                if scalar_attr is not None:
                    return scalar_attr
                if node.value.id == 'new':
                    from .emit.call_emit import try_emit_new_staticproperty_ref
                    for stack_node in reversed(self._ast_node_stack):
                        if isinstance(stack_node, ast.Assign) and len(stack_node.targets) == 1:
                            tgt = stack_node.targets[0]
                            if isinstance(tgt, ast.Attribute):
                                ft = self._cpp_type_for_assign_target(tgt)
                                if not ft and self.class_info and self.class_info.dataclass_field_specs:
                                    for spec in self.class_info.dataclass_field_specs:
                                        if spec.name == tgt.attr:
                                            ft = self._parse_storage_type(spec.annotation, self._active_type_params())
                                            break
                                sp_read = try_emit_new_staticproperty_ref(self, node, field_cpp_type=ft or None)
                                if sp_read is not None:
                                    return sp_read
                            break
                    sp_read = try_emit_new_staticproperty_ref(self, node)
                    if sp_read is not None:
                        return sp_read
                    info = self._active_class_info()
                    if info is not None and node.attr in info.static_properties:
                        sp_read = self._static_property_read(info.name, node.attr)
                        if sp_read is not None:
                            return sp_read
        if isinstance(node.value, ast.Attribute) and node.value.attr == 'Enum':
            from .emit.union_emit import try_emit_union_enum_member
            from .emit.union_mro_emit import try_emit_union_mro_enum_member
            union_enum = try_emit_union_enum_member(self, node)
            if union_enum is not None:
                return union_enum
            union_enum = try_emit_union_mro_enum_member(self, node)
            if union_enum is not None:
                return union_enum
        if isinstance(node.value, ast.Name) and node.value.id in self.classes:
            if not (node.value.id == 'Self' and self._active_class_info()):
                from .analysis.ir import qualified_class_static_callee
                cls = self.classes[node.value.id]
                if cls.is_enum and node.attr in enum_member_names(cls):
                    return f'{cls.cpp_name()}::{node.attr}'
                if node.attr in cls.static_class_fields:
                    cpp = cls.cpp_member_name(node.attr)
                    return qualified_class_static_callee(cls, cpp)
                if cls.inject_type_id and node.attr == '__id__':
                    return f"{cls.cpp_name()}::{property_getter_method_for('__id__')}()"
                sp_read = self._static_property_read(node.value.id, node.attr)
                if sp_read is not None:
                    return sp_read
        import_ref = self._import_attr_chain_cpp(node)
        if import_ref is not None:
            return import_ref
        if isinstance(node.ctx, ast.Load):
            dunder_get = self._try_emit_dunder_getattr(node.value, node.attr)
            if dunder_get is not None:
                return dunder_get
        if isinstance(node.value, ast.Name) and self._recv_is_host_class(node.value.id):
            info = self._active_class_info()
            if info is not None:
                if node.attr == '__name__':
                    return f'str("{info.name}")'
                static_ref = self._class_static_member_ref(info, node.attr)
                if static_ref is not None:
                    return static_ref
                sp = info.static_properties.get(node.attr)
                if sp:
                    getter = self._property_getter_cpp_name(info, node.attr)
                    return f'{info.cpp_name()}::{getter}()'
        prop_read = self._property_read(node.value, node.attr)
        if prop_read is not None:
            return prop_read
        match node.value:
            case ast.Name(id='self'):
                if self.class_info and node.attr in self.class_info.static_class_fields:
                    cpp = self.class_info.cpp_member_name(node.attr)
                    return f'{self.class_info.cpp_name()}::{cpp}'
                attr = node.attr
                if self.class_info and attr in self.class_info.field_properties:
                    attr = storage_field_for(attr)
                return f'this->{self._attr_cpp_name(node.value, attr)}'
            case ast.Name(id=name):
                t = ''
                if self.scope:
                    t = self._scope_storage(name)
                attr = self._attr_cpp_name(node.value, node.attr)
                if self._uses_ptr_access(t):
                    return f'{name}->{attr}'
                return f'{name}.{attr}'
            case _:
                if self._use_member_dispatch_macro(node.value):
                    return self._cpp_getattr_expr(node.value, node.attr, site=node)
                recv = self.visit(node.value)
                attr = self._attr_cpp_name(node.value, node.attr)
                return f'{recv}{self._member_access_sep(node.value, recv)}{attr}'

    def _emit_del_subscript_index(self, base_expr: ast.expr, slice_expr: ast.expr) -> None:
        emit_del_subscript_index(self, base_expr, slice_expr)

    def visit_Delete(self, node: ast.Delete):
        visit_delete(self, node)

    def visit_Subscript(self, node: ast.Subscript):
        return visit_subscript(self, node)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        return emit_unary_op(self, node)

    def visit_BinOp(self, node: ast.BinOp):
        return emit_bin_op(self, node)

    def visit_Compare(self, node: ast.Compare):
        return emit_compare(self, node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        raise NotImplementedError('生成器表达式仅支持作为 min/max/sum/any/all 的唯一 positional 实参，或传给注解为 Iterable[...] 的用户函数/方法形参（调用点内联）')

    def visit_JoinedStr(self, node: ast.JoinedStr):
        return emit_format_expr(self, plan_joined_str(self, node))

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load) and self.scope is not None and (node.id in self.scope.lazy_params):
            from .emit.lazy_param_emit import emit_lazy_param_materialize
            return emit_lazy_param_materialize(self, node.id, self.scope.lazy_params[node.id])
        if node.id == 'self':
            if self._genexp_inline_self_cpp is not None:
                return self._genexp_inline_self_cpp
            return 'this'
        if node.id == '__name__':
            return self._emit_dunder_name()
        if node.id == '__file__':
            return self._emit_dunder_file()
        if node.id == '__line__':
            return str(node.lineno)
        if node.id == '__debug__':
            return 'true' if self.debug else 'false'
        if node.id == 'None':
            return '0'
        if node.id == 'True':
            return 'true'
        if node.id == 'False':
            return 'false'
        mapped = self._genexp_inline_name_map.get(node.id)
        if mapped is not None:
            return mapped
        if isinstance(node.ctx, ast.Load) and (not self.in_header) and self.class_info and self.class_info.is_template() and (node.id in self._active_type_params()):
            nttp = getattr(self.class_info, 'type_param_nttp', None) or {}
            if node.id in nttp:
                return node.id
            return cpp_type_param_template_name(node.id)
        bound = binding_cpp_name(self._effective_import_bindings(), node.id)
        if bound is not None:
            return bound
        return cpp_param(node.id)

    def _emit_str_expr(self, node: ast.expr) -> str:
        """``str(expr)`` → ``PyStr(...)`` 或 ``static_cast<PyStr>(...)``。"""
        ps = cpp_ident('str')
        inner = self._cpp_str_ctor_arg(node)
        if inner.startswith(f'static_cast<{ps}>'):
            return inner
        return f'{ps}({inner})'

    def _cpp_str_ctor_arg(self, node: ast.expr) -> str:
        """``str(...)`` 的单层构造实参（外层 ``_emit_call_expr`` 再包一层 ``str(...)``）。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return quote_cpp_string(node.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (resolve_ctor_cpp_type(self, node.func.id) == cpp_ident('str')) and (len(node.args) == 1):
            return self._cpp_str_ctor_arg(node.args[0])
        t = self._infer_expr_cpp_type(node)
        v = self.visit(node)
        if is_str_type(t):
            return v
        info = self._class_info_for_expr(node) or self._class_info_for_type(t)
        from .emit.union_mro_emit import try_emit_union_mro_enum_member, union_mro_enum_helper_name
        umem = try_emit_union_mro_enum_member(self, node) if isinstance(node, ast.Attribute) else None
        if umem is not None:
            ps = cpp_ident('str')
            owner_info = self._class_info_for_ref(node.value.value.id)
            helper = union_mro_enum_helper_name(owner_info) if owner_info else 'PyStr'
            return f'static_cast<{ps}>({helper}{{{umem}}})'
        if info and info.is_enum:
            from .emit.enum_emit import enum_pystr_cast_expr
            return enum_pystr_cast_expr(self, info, self._paren_expr(v))
        if info and has_effective_str(info, self):
            ps = cpp_ident('str')
            if isinstance(node, ast.Name) and node.id == 'self' and self._active_class_info():
                return f'static_cast<{ps}>(*this)'
            inner = self._paren_expr(v)
            if is_str_type(t):
                return inner
            return f'static_cast<{ps}>({inner})'
        return v

    def visit_Constant(self, node: ast.Constant):
        return self._literal(node.value)

    def _union_ctor_class_cpp(self, info: ClassInfo, *, type_args_slice: ast.expr | None=None, context_cpp: str | None=None) -> str:
        if type_args_slice is not None and info.type_params:
            args = self._parse_type_args(type_args_slice, set(info.type_params))
            return f'{info.cpp_name()}<{args}>'
        if context_cpp and '<' in context_cpp:
            return context_cpp.strip()
        if info.is_template():
            return info.template_cpp_type()
        return info.cpp_name()

    def _emit_union_variant_ctor(self, cls_name: str, variant: str, node: ast.Call, *, context_cpp: str | None, type_args_slice: ast.expr | None=None) -> str | None:
        target = union_ctor_target_info(self, cls_name, variant, context_cpp)
        if target is None:
            return None
        variant_info = next((v for v in target.union_variants if v.name == variant), None)
        if variant_info is None:
            return None
        from .passes.union_expand import specialize_union_variant_param_cpp_types
        param_types = specialize_union_variant_param_cpp_types(target, variant, context_cpp)
        arg_str = emit_call_args(self, node, param_cpp_types=param_types, param_names=list(variant_info.fields))
        cls_cpp = self._union_ctor_class_cpp(target, type_args_slice=type_args_slice, context_cpp=context_cpp)
        from .analysis.ir import cpp_union_static_call
        if arg_str:
            return cpp_union_static_call(cls_cpp, variant, arg_str)
        return cpp_union_static_call(cls_cpp, variant)

    def _visit_value_for_type(self, node: ast.expr, cpp_type: str) -> str:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            match node.func.value:
                case ast.Name(id=cls) if is_json_class_ref(self, cls):
                    if node.func.attr in _JSON_API_METHODS_NEED_TYPE_ARG:
                        out = emit_json_class_api_call(self, node.func.attr, cpp_type, node)
                        if out is not None:
                            return out
                case ast.Name(id=cls) if self._name_refers_to_class(cls):
                    out = self._emit_union_variant_ctor(cls, node.func.attr, node, context_cpp=cpp_type)
                    if out is not None:
                        return out
                case ast.Subscript(value=ast.Name(id=cls), slice=sl) if self._name_refers_to_class(cls):
                    out = self._emit_union_variant_ctor(cls, node.func.attr, node, context_cpp=cpp_type, type_args_slice=sl)
                    if out is not None:
                        return out
        from .emit.complex_literal_emit import try_emit_complex_literal_expr
        complex_lit = try_emit_complex_literal_expr(node, cpp_type)
        if complex_lit is not None:
            return complex_lit
        if isinstance(node, ast.Constant):
            lit = self._literal(node.value, cpp_type=cpp_type)
            return self._coerce_expr_to_cpp_type(lit, cpp_type, rhs_node=node)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int):
            lit = self._literal(-node.operand.value, cpp_type=cpp_type)
            return self._coerce_expr_to_cpp_type(lit, cpp_type, rhs_node=node)
        if isinstance(node, ast.Dict):
            dict_param = cpp_type if is_dict_type(cpp_type) else None
            return _emit_dict_value_expr(self, node, param_cpp_type=dict_param)
        v = self._visit_value_expr(node)
        return self._coerce_expr_to_cpp_type(v, cpp_type, rhs_node=node)

    def _try_option_none_compare(self, left_expr: ast.expr, comp_expr: ast.expr, *, is_not: bool=False) -> str | None:
        if not self._is_none_constant(comp_expr):
            return None
        lt = self._infer_expr_cpp_type(left_expr)
        if self.class_info:
            from .analysis.ir import resolve_self_in_cpp_type
            lt = resolve_self_in_cpp_type(lt, self.class_info.cpp_name())
        if not is_optional_type(lt):
            return None
        left_cpp = self.visit(left_expr)
        if is_not:
            return option_is_not_none_expr(left_cpp, lt)
        return option_is_none_expr(left_cpp, lt)

    def _literal(self, value, *, cpp_type: str | None=None):
        match value:
            case None:
                tgt = strip_cpp_ref(cpp_type) if cpp_type else ''
                if tgt == cpp_ident('PyNone'):
                    return f"{cpp_ident('PyNone')}()"
                if self._in_result_method():
                    return f"{cpp_ident('PyNone')}()"
                return 'nullptr'
            case bool():
                return 'true' if value else 'false'
            case int():
                if cpp_type and is_byte_type(cpp_type):
                    return f'PyByte({value})'
                if cpp_type and is_char_type(cpp_type):
                    return f'PyChar({value})'
                if cpp_type and is_int64_type(cpp_type):
                    return format_cpp_int64(value)
                if cpp_type and is_uint_type(cpp_type):
                    return format_cpp_uint(value)
                if cpp_type and is_uint64_type(cpp_type):
                    return format_cpp_uint64(value)
                if cpp_type and is_uintptr_type(cpp_type):
                    return format_cpp_uintptr(value)
                if cpp_type and is_varint_type(cpp_type):
                    return format_cpp_varint(value)
                return format_cpp_int(value)
            case float():
                if cpp_type and is_float64_type(cpp_type):
                    return format_cpp_float64(value)
                return format_cpp_float(value)
            case str():
                return str_cpp_from_literal(value)
            case bytes():
                return bytes_cpp_from_literal(value)
            case complex() as c:
                return format_cpp_complex_literal(float(c.real), float(c.imag), cpp_type)
            case _:
                raise ValueError(value)

    def _appendable_literal_from_return_ann(self) -> tuple[str, str] | None:
        if self.current_method is None or self.current_method.returns is None:
            return None
        return self._appendable_init_from_ann(self.current_method.returns)

    def _appendable_literal_ann(self) -> tuple[str, str] | None:
        pair = self._appendable_literal_from_return_ann()
        if pair is not None:
            return pair
        if self._literal_target_ann is not None:
            return self._appendable_init_from_ann(self._literal_target_ann)
        return None

    def _mapping_literal_from_return_ann(self) -> str | None:
        if self.current_method is None or self.current_method.returns is None:
            return None
        return self._mapping_literal_spec_from_ann(self.current_method.returns)

    def _mapping_literal_ann(self) -> str | None:
        spec = self._mapping_literal_from_return_ann()
        if spec is not None:
            return spec
        if self._literal_target_ann is not None:
            return self._mapping_literal_spec_from_ann(self._literal_target_ann)
        return None

    def _set_literal_from_return_ann(self) -> tuple[str, str] | None:
        if self.current_method is None or self.current_method.returns is None:
            return None
        return self._set_literal_target_from_ann(self.current_method.returns)

    def _set_literal_ann(self) -> tuple[str, str] | None:
        target = self._set_literal_from_return_ann()
        if target is not None:
            return target
        if self._literal_target_ann is not None:
            return self._set_literal_target_from_ann(self._literal_target_ann)
        return None

    def visit_List(self, node: ast.List):
        pair = self._appendable_literal_ann()
        if pair is not None:
            cpp_spec, elem_t = pair
            return _emit_appendable_rvalue_expr(self, node, cpp_spec, elem_t)
        raise NotImplementedError('序列字面量请写 x: list[T] = [a,b,...]、x: deque[T] = [a,b,...] 或 x = [a,b,...]；空列表用 []')

    def visit_ListComp(self, node: ast.ListComp):
        pair = self._appendable_literal_ann()
        if pair is not None:
            cpp_spec, elem_t = pair
            return _emit_list_comp_rvalue_expr(self, node, cpp_spec, elem_t)
        raise NotImplementedError('列表推导请写 x: list[T] = [e for …] 或在 ``-> Self`` 的宿主 list/deque 方法内 return')

    def visit_Dict(self, node: ast.Dict):
        mapping = self._mapping_literal_ann()
        return _emit_dict_value_expr(self, node, param_cpp_type=mapping)

    def visit_DictComp(self, node: ast.DictComp):
        mapping = self._mapping_literal_ann()
        if mapping is not None:
            from .analysis.patterns import temp_name
            from .emit.literal_ctor_emit import emit_dict_comprehension
            tmp = temp_name('dict_comp')
            emit_dict_comprehension(self, name=tmp, cpp_spec=mapping, comp=node, declare=True)
            return cpp_param(tmp)
        raise NotImplementedError('字典推导请写 x: dict[K,V] = {… for …} 或在 ``-> Self`` 的宿主 dict/Counter 方法内 return')

    def visit_Set(self, node: ast.Set):
        target = self._set_literal_ann()
        if target is not None:
            from .analysis.patterns import temp_name
            set_spec, set_elem = target
            tmp = temp_name('set_val')
            _emit_set_literal_init(self, tmp, set_elem, node, declare=True, cpp_spec=set_spec)
            return cpp_param(tmp)
        raise NotImplementedError('集合字面量请写 s: set[T] = {a, b, ...} 或 fs: frozenset[T] = {a, b, ...}；空 set 用 set()，勿用 {}（那是 dict）')

    def visit_SetComp(self, node: ast.SetComp):
        target = self._set_literal_ann()
        if target is not None:
            from .analysis.patterns import temp_name
            from .emit.literal_ctor_emit import emit_set_comprehension
            set_spec, set_elem = target
            tmp = temp_name('set_comp')
            emit_set_comprehension(self, name=tmp, cpp_spec=set_spec, elem_t=set_elem, comp=node, declare=True)
            return cpp_param(tmp)
        raise NotImplementedError('集合推导请写在 ``-> Self`` 的宿主 set 方法内 return，或赋值到带注解变量')

    def _infer_list_elem_type(self, elts: list[ast.expr]) -> str:
        if not elts:
            return cpp_ident('int')
        for elt in elts:
            if isinstance(elt, ast.Starred):
                et = element_type_of_iterable(self, elt.value)
                if et:
                    return et
            else:
                return self._infer_expr_cpp_type(elt)
        return cpp_ident('int')

    def _infer_view_span_type(self, receiver: ast.expr) -> str | None:
        bt = self._infer_expr_cpp_type(receiver)
        elem = None
        if is_stack_array_type(bt):
            elem = cpp_stack_array_elem_type(bt)
        elif is_array_type(bt) and cpp_array_ndim(bt) == 1:
            elem = cpp_array_elem_type(bt)
        elif is_list_type(bt):
            inner = list_elem_type(bt)
            elem = inner.strip() if inner else None
        if elem:
            return cpp_span_type(elem)
        return None

    def _module_constant_cpp_type(self, name: str, *, module_path: str | None=None) -> str | None:
        """模块级 ``name: T = …`` 注解的 C++ 类型（供 ``_infer_expr_cpp_type`` 查 ``@const`` 等）。"""
        from .analysis.ir import strip_type_annotation_markers
        mp = module_path or self._active_module_path()
        for mod_path, node in self.module_constants:
            if mod_path != mp:
                continue
            if not isinstance(node.target, ast.Name) or node.target.id != name:
                continue
            ann = strip_type_annotation_markers(node.annotation)
            if ann is None:
                return None
            return self._parse_type(ann, [])
        return None

    def _infer_expr_cpp_type(self, node: ast.expr) -> str:
        match node:
            case ast.Constant(value=v):
                if isinstance(v, bool):
                    return 'bool'
                if isinstance(v, int):
                    return cpp_ident('int')
                if isinstance(v, float):
                    return cpp_ident('float')
                if isinstance(v, str):
                    return cpp_ident('str')
                if isinstance(v, bytes):
                    return cpp_ident('bytes')
            case ast.Name(id='self'):
                if self.class_info:
                    if self.class_info.is_refcount:
                        return self.class_info.storage_cpp_type()
                    if self.class_info.type_params:
                        return self.class_info.template_cpp_type()
                    return self.class_info.cpp_name()
            case ast.Name(id='__name__') | ast.Name(id='__file__'):
                return cpp_ident('str')
            case ast.Name(id='__line__'):
                return cpp_ident('int')
            case ast.Name(id='__debug__'):
                return 'bool'
            case ast.Name(id=name):
                if self.scope:
                    t = self._scope_storage(name)
                    if t:
                        return t
                mod_t = self._module_constant_cpp_type(name)
                if mod_t:
                    return mod_t
                return cpp_ident('int')
            case ast.Call(func=ast.Name(id=name)):
                dunder_ret = self._infer_dunder_forward_call_return_type(name, node)
                if dunder_ret:
                    return dunder_ret
                if name == 'next' and len(node.args) == 1 and (not node.keywords):
                    recv_info = self._class_info_for_expr(node.args[0])
                    if recv_info and '__next__' in recv_info.method_sigs:
                        sig = recv_info.method_sigs['__next__']
                        ret = self._sig_return_full(sig)
                        if ret:
                            return ret
                fsig = self._function_sig_for_name(name)
                if fsig is not None:
                    ret = self._sig_return_full(fsig)
                    if ret:
                        return ret
                ctor = resolve_ctor_cpp_type(self, name)
                if ctor:
                    return ctor
            case ast.Call(func=ast.Attribute(attr='bytes_from_literal')):
                return cpp_ident('bytes')
            case ast.Call(func=ast.Name(id='getattr'), args=[recv, attr]) if (field := static_field_name(attr)):
                return self._infer_expr_cpp_type(ast.Attribute(value=recv, attr=field, ctx=ast.Load()))
            case ast.Attribute(value=ast.Name(id='Self'), attr=attr):
                info = self._active_class_info()
                if info is not None:
                    sp = info.static_properties.get(attr)
                    if sp and sp.getter_sig:
                        return self._sig_return_storage(sp.getter_sig)
            case ast.Attribute(value=ast.Name(id=cls), attr=attr) if cls in self.classes and (not (cls == 'Self' and self._active_class_info())):
                cls_info = self.classes[cls]
                if cls_info.is_enum and attr in enum_member_names(cls_info):
                    return cls_info.cpp_name()
                sp = cls_info.static_properties.get(attr)
                if sp and sp.getter_sig:
                    return self._sig_return_storage(sp.getter_sig)
            case ast.Attribute(value=ast.Name(id='self'), attr=attr):
                if self.class_info:
                    p = self.class_info.properties.get(attr)
                    if p and p.getter_sig:
                        ret = self._sig_return_storage(p.getter_sig)
                        from .analysis.ir import resolve_self_in_cpp_type
                        return resolve_self_in_cpp_type(ret, self.class_info.cpp_name())
                    ft = self._field_storage(attr)
                    if ft:
                        from .analysis.ir import resolve_self_in_cpp_type
                        return resolve_self_in_cpp_type(ft, self.class_info.cpp_name())
            case ast.Attribute(value=val, attr='value'):
                vt = self._infer_expr_cpp_type(val)
                if vt and is_optional_type(vt):
                    inner = optional_inner_type(vt)
                    if inner:
                        from .analysis.ir import resolve_self_in_cpp_type
                        if self.class_info:
                            inner = resolve_self_in_cpp_type(inner, self.class_info.cpp_name())
                        return inner
            case ast.Attribute(value=ast.Attribute(value=ast.Name(id='self'), attr=mid), attr=attr):
                if self.class_info:
                    mid_t = self._field_storage(mid)
                    owner = self._class_info_for_type(mid_t)
                    if owner:
                        p = owner.properties.get(attr)
                        if p and p.getter_sig:
                            return self._sig_return_storage(p.getter_sig)
                        ft = self._field_storage(attr, info=owner)
                        if ft:
                            return ft
            case ast.Attribute(value=val, attr=attr) if isinstance(val, ast.Name) and val.id != 'self':
                info = self._class_info_for_receiver(val)
                if info:
                    p = info.properties.get(attr)
                    if p and p.getter_sig:
                        return self._sig_return_storage(p.getter_sig)
                    ft = self._field_storage(attr, info=info)
                    if ft:
                        return ft
                    if not self._is_resolved_instance_member(info, attr) and '__getattr__' in info.methods:
                        sig = info.method_sigs.get('__getattr__')
                        if sig:
                            return self._sig_return_full(sig)
            case ast.Attribute(value=val, attr='view'):
                view_t = self._infer_view_span_type(val)
                if view_t:
                    return view_t
            case ast.Attribute(value=val, attr=attr):
                info = self._class_info_for_receiver(val)
                if info and (not self._is_resolved_instance_member(info, attr)):
                    if '__getattr__' in info.methods:
                        sig = info.method_sigs.get('__getattr__')
                        if sig:
                            return self._sig_return_full(sig)
                ft = self._field_cpp_type_for_attribute(val, attr)
                if ft:
                    return ft
            case ast.Call(func=ast.Attribute(value=recv, attr=method)):
                if method == '__next__' and (not node.args) and (not node.keywords):
                    info = self._class_info_for_expr(recv)
                    if info and '__next__' in info.method_sigs:
                        sig = info.method_sigs['__next__']
                        ret = self._sig_return_full(sig)
                        if ret:
                            return ret
                if method == '__getitem__' and isinstance(recv, ast.Attribute):
                    if isinstance(recv.value, ast.Name) and recv.value.id == 'self' and self.class_info:
                        ft = self._field_storage(recv.attr)
                    elif isinstance(recv.value, ast.Name) and self.scope:
                        ft = self._scope_storage(recv.value.id)
                    else:
                        ft = ''
                    if is_list_type(ft):
                        inner = list_elem_type(ft)
                        return inner.strip() if inner else None
                info = self._class_info_for_receiver(recv)
                if info is None and isinstance(recv, ast.Constant) and isinstance(recv.value, str):
                    info = self._class_info_for_type(cpp_ident('str'))
                if info is None:
                    rt = strip_cpp_ref(self._infer_expr_cpp_type(recv) or '')
                    if rt:
                        info = self._class_info_for_type(rt)
                if info:
                    ret = self._receiver_method_return_cpp_type(info, method, recv, node.args)
                    if ret:
                        return ret
                if isinstance(recv, ast.Name) and self.scope:
                    vt = self._scope_storage(recv.id)
                    if method == 'data' and is_span_type(vt):
                        elem = cpp_span_elem_type(vt)
                        if elem:
                            return f'{elem.strip()}*'
                    if method == '__getitem__' and is_list_type(vt):
                        inner = list_elem_type(vt)
                        return inner.strip() if inner else None
                if isinstance(recv, ast.Name) and recv.id in self.classes:
                    ret = self._receiver_method_return_cpp_type(self.classes[recv.id], method, recv)
                    if ret:
                        return ret
            case ast.BinOp() as bin_node:
                dunder = self._binop_dunder(bin_node.op)
                if dunder:
                    left_info = self._class_info_for_expr(bin_node.left)
                    if left_info and self._class_info_has_method(left_info, dunder):
                        ret = self._receiver_method_return_cpp_type(left_info, dunder, bin_node.left, [bin_node.right])
                        if ret:
                            return ret
                    rdunder = self._binop_rdunder(bin_node.op)
                    if rdunder:
                        right_info = self._class_info_for_expr(bin_node.right)
                        if right_info and self._class_info_has_method(right_info, rdunder):
                            ret = self._receiver_method_return_cpp_type(right_info, rdunder, bin_node.right, [bin_node.left])
                            if ret:
                                return ret
            case ast.Call(func=ast.Subscript(value=ast.Name(id='id'), slice=sl), args=_):
                elem = self._parse_type_args(sl, self._active_type_params())
                return f'{elem}*'
            case ast.Call(func=ast.Name(id='id'), args=[arg]):
                return cpp_pointer_type_for_object(self._infer_expr_cpp_type(arg))
            case ast.JoinedStr():
                return cpp_ident('str')
            case ast.List(elts=elts):
                inner = self._infer_list_elem_type(elts)
                return cpp_template_type('list', inner)
            case ast.UnaryOp(op=ast.Invert(), operand=operand):
                op_t = strip_cpp_ref(self._infer_expr_cpp_type(operand) or '')
                if op_t:
                    info = self._class_info_for_type(op_t)
                    if info and '__invert__' in info.methods:
                        ret = self._receiver_method_return_cpp_type(info, '__invert__', operand, [])
                        if ret:
                            return ret
                    return op_t
            case ast.Subscript(value=value, slice=sl) if not isinstance(sl, ast.Slice):
                vt = self._infer_expr_cpp_type(value)
                if is_str_type(vt):
                    return cpp_ident('char')
                if is_char_heap_array_type(vt) or is_byte_heap_array_type(vt):
                    elem = cpp_array_elem_type(vt)
                    if elem:
                        return elem.strip()
                if is_list_type(vt):
                    inner = list_elem_type(vt)
                    if inner:
                        return inner.strip()
            case ast.Subscript(value=value, slice=sl) if isinstance(sl, ast.Slice) or is_slice_ctor_expr(self, sl):
                vt = self._infer_expr_cpp_type(value)
                sliced = cpp_slice_result_type(vt)
                if sliced is not None:
                    return sliced
                if is_span_type(vt):
                    elem = cpp_span_elem_type(vt)
                    if elem:
                        return cpp_span_type(elem)
                if is_stack_array_type(vt):
                    elem = cpp_stack_array_elem_type(vt)
                    if elem:
                        return cpp_template_type('array', elem)
            case ast.Attribute(value=val, attr='view'):
                bt = self._infer_expr_cpp_type(val)
                elem = None
                if is_stack_array_type(bt):
                    elem = cpp_stack_array_elem_type(bt)
                elif is_array_type(bt) and cpp_array_ndim(bt) == 1:
                    elem = cpp_array_elem_type(bt)
                elif is_list_type(bt):
                    inner = list_elem_type(bt)
                    elem = inner.strip() if inner else None
                if elem:
                    return cpp_span_type(elem)
            case _:
                return cpp_ident('int')
        return cpp_ident('int')

    def _is_str_expr(self, node: ast.expr) -> bool:
        t = self._infer_expr_cpp_type(node)
        if is_str_type(t):
            return True
        return isinstance(node, ast.Constant) and isinstance(node.value, str)

    def _is_py_scalar_expr(self, node: ast.expr) -> bool:
        t = self._infer_expr_cpp_type(node)
        return is_scalar_int_type(t) or is_scalar_float_type(t)

    def _emit_mod_rhs(self, right: ast.expr) -> str:
        """``str %`` 右操作数：仅 ``PyTuple`` / ``makeTuple``（禁止裸标量直传 ``__mod__``）。"""
        if isinstance(right, ast.Tuple):
            if not right.elts:
                return 'PyTuple<>()'
            vals = ', '.join((self._visit_value_expr(e) for e in right.elts))
            return f'makeTuple({vals})'
        t = self._infer_expr_cpp_type(right)
        if t.startswith('PyTuple<'):
            return self._visit_value_expr(right)
        return f'makeTuple({self._visit_value_expr(right)})'

    def visit_Tuple(self, node: ast.Tuple):
        from .analysis.ir import strip_cpp_type_qualifiers
        if not node.elts:
            return 'PyTuple<>()'
        args = ', '.join((self._visit_value_expr(e) for e in node.elts))
        types = ', '.join(
            strip_cpp_type_qualifiers(self._infer_expr_cpp_type(e) or 'void*')
            for e in node.elts
        )
        return f'PyTuple<{types}>({args})'

    def visit_BoolOp(self, node: ast.BoolOp):
        if isinstance(node.op, ast.And):
            return self._lower_boolop_and(node.values)
        return self._lower_boolop_or(node.values)

    def visit_IfExp(self, node: ast.IfExp):
        return f'({self.visit(node.test)} ? {self.visit(node.body)} : {self.visit(node.orelse)})'

    def _emit_all(self):
        self._start_header()
        for module_path in self.module_order:
            with self._use_module_decl(module_path):
                _emit_module_protocol_traits(self, module_path)
                if self._skip_module_classes(module_path):
                    continue
                self._emit_module_docstring(module_path)
        for module_path in self.module_order:
            if self._skip_module_classes(module_path):
                continue
            with self._use_module_decl(module_path), self._use_module_namespace(module_path):
                self._emit_module_import_usings(module_path)
                module_classes = [info for info in self.classes.values() if info.module_path == module_path and info.outer_class is None and (not info.is_descriptor) and (not info.is_mixin) and (not info.is_annotation) and (not info.is_protocol) and (not info.is_variant_mixin) and (not self._is_type_marker(info))]
                from .emit.class_decl_emit import sort_module_classes_for_declaration
                module_classes = sort_module_classes_for_declaration(module_classes)
                if self._is_stdlib_module(module_path):
                    tpl_classes = [c for c in module_classes if c.is_template()]
                    if len(tpl_classes) > 1:
                        for info in tpl_classes:
                            self._emit_template_prefix_forward(info)
                            self.write_line(f'class {info.cpp_name()};')
                        self.write_line()
                    for info in module_classes:
                        _emit_class_declaration(self, info)
                else:
                    for info in module_classes:
                        if info.is_enum:
                            continue
                        self._emit_template_prefix(info)
                        self.write_line(f'class {info.cpp_name()};')
                    self.write_line()
                if self._is_stdlib_module(module_path) or module_path != self.entry_module_path:
                    self._emit_module_constants(module_path)
                    self._emit_module_type_aliases(module_path, conditional_only=True, use_deferred=False)
                    self._emit_module_function_decls(module_path)
                    self._emit_module_delegates(module_path)
                elif not self._is_stdlib_module(module_path):
                    self._emit_module_constants(module_path)
                    self._emit_module_type_aliases(module_path, conditional_only=True, use_deferred=False)
                with self._use_module_deferred_decl(module_path):
                    self._emit_module_type_aliases(module_path, conditional_only=False, use_deferred=True)
                if not self._is_stdlib_module(module_path):
                    self._emit_module_delegates(module_path)
                    for info in module_classes:
                        _emit_class_declaration(self, info)
                    if module_path == self.entry_module_path:
                        self._emit_module_function_decls(module_path, skip_main=True)
        with self._use_header():
            entry_funcs = [f for f in self._entry_functions() if f.name == 'main']
            if entry_funcs:
                for func in entry_funcs:
                    if func.name == 'main' and (not self.emit_main):
                        continue
                    if func.name in self.delegates:
                        continue
                    if self._is_decorator_impl(func):
                        continue
                    fsig = self.function_sigs[self.entry_module_path, func.name]
                    self._write_doc_lines(fsig.doc_lines)
                    from .analysis.variadic_template import typevar_tuple_names_for_emit
                    if fsig.func_ft.template_names or typevar_tuple_names_for_emit(fsig.func_ft, fsig.variadic_template):
                        self._emit_function_template_prefix(fsig.func_ft, variadic_template=fsig.variadic_template)
                    self.write_line(format_fn_sig(self._sig_return_storage(fsig), fsig.ret_trail, func.name, fsig.params) + fn_noexcept_suffix(fsig.is_noexcept) + ';')
                if self.emit_main and (not any((f.name == 'main' for f in self._entry_functions()))):
                    self.write_line('int main();')
                self.write_line()
        from .emit.enum_mro_emit import emit_user_module_mro_inl
        emit_user_module_mro_inl(self)
        self._finish_header()
        self._start_source()
        self._emit_stdlib_module_implementations()
        from .emit.ffi_glue_emit import emit_all_ffi_glue
        emit_all_ffi_glue(self)
        self._emit_user_module_functions()
        self._emit_entry_module_implementations()
        self._emit_module_functions()
        self._inject_cpp_attr_dispatch_definitions()
        self._inject_py_callable_thunks()
        self._ensure_entry_inl_header_include()

    def _ensure_entry_inl_header_include(self) -> None:
        """用户入口模板类方法写入 ``.inl`` 晚于 ``_finish_header``，此处补 ``#include``。"""
        mp = self.entry_module_path
        if not self.per_module_inl_lines.get(mp):
            return
        incl = f'#include "{self.module_name}.inl"'
        if any((incl in ln for ln in self.header_lines)):
            return
        for i in range(len(self.header_lines) - 1, -1, -1):
            if self.header_lines[i].startswith('#endif'):
                self.header_lines[i:i] = ['', incl, '']
                return

    def _module_functions_for(self, module_path: str) -> list[ast.FunctionDef]:
        return [f for mp, f in self.module_functions if mp == module_path]

    def _function_sig_for(self, module_path: str, func: ast.FunctionDef) -> FunctionSig:
        sig = self.function_node_sigs.get(id(func))
        if sig is not None:
            return sig
        return self.function_sigs[module_path, func.name]

    def _module_emit_functions_for(self, module_path: str) -> list[ast.FunctionDef]:
        """``.h`` / ``.inl`` 须 emit 的全部模块函数（``@overload`` 在前、实现随后）。"""
        from .constant.stdlib_layout import BUILTINS_OPERATORS_FUNCS, RUNTIME_BUILTINS_MODULE
        seen: set[int] = set()
        funcs: list[ast.FunctionDef] = []
        for (mp, _name), ovs in self.module_function_overloads.items():
            if mp != module_path:
                continue
            for ov in ovs:
                oid = id(ov)
                if oid not in seen:
                    funcs.append(ov)
                    seen.add(oid)
        for f in self._module_functions_for(module_path):
            fid = id(f)
            if fid not in seen:
                funcs.append(f)
                seen.add(fid)
        if module_path == RUNTIME_BUILTINS_MODULE:
            funcs = [f for f in funcs if f.name not in BUILTINS_OPERATORS_FUNCS]
        return self._module_functions_emit_order(funcs)

    def _module_function_cpp_name(self, module_path: str, func: ast.FunctionDef) -> str:
        if func.name == 'main' and module_path != self.entry_module_path:
            stem = module_path.rsplit('/', 1)[-1]
            return f'{stem}_main'
        from .analysis.stubs.builtin_stubs import function_cpp_rename
        from .analysis.stubs.class_stubs import lookup_module_function_cpp_name
        mapped = lookup_module_function_cpp_name(module_path, func.name)
        if mapped is not None:
            return mapped
        renamed = function_cpp_rename(func)
        if renamed is not None:
            return renamed
        return func.name

    def _is_serializable_cpp_type(self, cpp_type: str) -> bool:
        t = cpp_type.strip()
        if t.endswith('&'):
            t = t[:-1].strip()
        if t.startswith('const '):
            t = t[6:].strip()
        for info in self.classes.values():
            if not info.is_serializable:
                continue
            if t == info.name or t.endswith(f'::{info.name}'):
                return True
        return False

    @staticmethod
    def _pylist_elem_cpp_type(cpp_type: str) -> str | None:
        t = cpp_type.strip()
        if t.startswith('const '):
            t = t[6:].strip()
        prefix = 'PyList<'
        if not t.startswith(prefix) or not t.endswith('>'):
            return None
        inner = t[len(prefix):-1].strip()
        return inner or None

    def _qualify_import_call(self, cpp_name: str, local_name: str, *, module_path: str | None=None) -> str:
        """成员函数内调用导入名时加限定，避免与同类成员（如 unittest ``run``）冲突。"""
        if self.class_info is None or local_name not in self.class_info.methods:
            return cpp_name
        if '::' in cpp_name:
            return cpp_name
        if module_path:
            ns = namespace_qualifier_for_module(module_path)
            if ns:
                return f'::{ns}::{cpp_name}'
        return f'::{cpp_name}'

    @staticmethod
    def _function_has_return(func: ast.FunctionDef) -> bool:
        return any((isinstance(node, ast.Return) for node in ast.walk(func)))

    def _emit_module_constants(self, module_path: str) -> None:
        from .analysis.ir import is_const_type_annotation
        from .emit.literal_ctor_emit import _emit_new_ctor_expr
        items = [n for mp, n in self.module_constants if mp == module_path]
        if not items:
            return
        with self._use_module_header(module_path), self._use_header():
            for node in items:
                name = node.target.id
                if name == '__all__':
                    continue
                t = self._parse_type(node.annotation, [])
                is_const = is_const_type_annotation(node.annotation)
                if node.value is not None and self._is_new_call(node.value) and (not is_const):
                    val = _emit_new_ctor_expr(self, t, node.value)
                    self.write_line(f'static {t} {name} = {val};')
                    continue
                if node.value is not None:
                    if isinstance(node.value, ast.Constant) and node.value.value is None:
                        from .analysis.ir import cpp_union_static_call, strip_cpp_ref
                        ct = t.strip()
                        if ct.startswith('PyOptional<'):
                            val = cpp_union_static_call(strip_cpp_ref(ct), 'None_')
                        else:
                            val = '0'
                    else:
                        self._literal_target_ann = node.annotation
                        try:
                            val = self.visit(node.value)
                        finally:
                            self._literal_target_ann = None
                elif t.strip().startswith('PyOptional<'):
                    from .analysis.ir import cpp_union_static_call, strip_cpp_ref
                    val = cpp_union_static_call(strip_cpp_ref(t.strip()), 'None_')
                else:
                    val = '0'
                const_kw = 'const ' if is_const else ''
                self.write_line(f'static {const_kw}{t} {name} = {val};')
            self.write_line()

    @staticmethod
    def _module_functions_emit_order(funcs: list[ast.FunctionDef]) -> list[ast.FunctionDef]:
        """描述符签名校验辅助函数须在调用它的模块函数之前生成/声明。"""
        helpers = [f for f in funcs if is_descriptor_signature_helper(f.name)]
        rest = [f for f in funcs if not is_descriptor_signature_helper(f.name)]
        return helpers + rest

    def _emit_module_function_decls(self, module_path: str, *, skip_main: bool=False) -> None:
        funcs = self._module_emit_functions_for(module_path)
        if skip_main:
            funcs = [f for f in funcs if f.name != 'main']
        if not funcs:
            return
        funcs = self._module_functions_emit_order(funcs)
        with self._use_module_header(module_path), self._use_header():
            for func in funcs:
                if has_named_decorator(func, 'native'):
                    cpp_name = self._module_function_cpp_name(module_path, func)
                    if '::' in cpp_name:
                        continue
                fsig = self._function_sig_for(module_path, func)
                cpp_name = self._module_function_cpp_name(module_path, func)
                self._write_doc_lines(fsig.doc_lines)
                from .analysis.variadic_template import typevar_tuple_names_for_emit
                if fsig.func_ft.template_names or typevar_tuple_names_for_emit(fsig.func_ft, fsig.variadic_template):
                    self._emit_function_template_prefix(fsig.func_ft, variadic_template=fsig.variadic_template)
                self.write_line(format_fn_sig(self._sig_return_storage(fsig), fsig.ret_trail, cpp_name, fsig.params) + fn_noexcept_suffix(fsig.is_noexcept) + ';')
            self.write_line()

    def _entry_imported_user_modules(self) -> list[str]:
        return [
            mp
            for mp in self.module_order
            if mp != self.entry_module_path
            and (not self._is_stdlib_module(mp))
            and (not self._is_ffi_module(mp))
        ]

    def _emit_user_module_functions(self) -> None:
        for module_path in self._entry_imported_user_modules():
            funcs = self._module_functions_emit_order(self._module_emit_functions_for(module_path))
            if not funcs:
                continue
            with self._use_module_inl(module_path), self._use_source(), self._use_import_bindings(module_path), self._use_inl_namespace(module_path):
                for func in funcs:
                    if is_overload_stub(func):
                        continue
                    fsig = self._function_sig_for(module_path, func)
                    cpp_name = self._module_function_cpp_name(module_path, func)
                    sig = format_fn_sig(self._sig_return_storage(fsig), fsig.ret_trail, cpp_name, self._function_sig_params_impl(fsig.params)) + fn_noexcept_suffix(fsig.is_noexcept)
                    with self._use_scope(func) as scope:
                        from .analysis.type_emit import bind_scope_param
                        for arg in func.args.args:
                            bind_scope_param(scope, arg.arg, fsig)
                            scope.vars[arg.arg] = NameContext.Argument
                        if fsig.variadic_template is not None:
                            vt = fsig.variadic_template
                            bind_scope_param(scope, vt.param_name, fsig)
                            scope.vars[vt.param_name] = NameContext.Argument
                        elif fsig.vararg_pack is not None:
                            vp = fsig.vararg_pack
                            from .analysis.type_emit import bind_scope_vararg
                            bind_scope_vararg(scope, vp.param_name, vp.cpp_type, classes=self.classes)
                            scope.vars[vp.param_name] = NameContext.Argument
                        if fsig.lazy_params:
                            scope.lazy_params = dict(fsig.lazy_params)
                        type_if_plan = plan_type_if_chain(self, func)
                        type_if_pick = None
                        if type_if_plan is not None:
                            type_if_pick = emit_type_if_dispatch(self, type_if_plan, fsig)
                        if fsig.variadic_template is not None:
                            from .emit.variadic_template_emit import prescan_emit_vt_loop_structs
                            prescan_emit_vt_loop_structs(self, func, fsig.variadic_template, param_types=self._sig_param_types_map(fsig))
                        from .analysis.variadic_template import typevar_tuple_names_for_emit
                        if fsig.func_ft.template_names or typevar_tuple_names_for_emit(fsig.func_ft, fsig.variadic_template):
                            self._emit_function_template_prefix(fsig.func_ft, default_constraint=False, variadic_template=fsig.variadic_template)
                        with self._use_block(sig):
                            bounds = self.descriptor_helper_protocol_bounds.get((module_path, func.name))
                            if bounds:
                                value_cpp = self._descriptor_validate_value_cpp_type(fsig)
                                if value_cpp:
                                    self._emit_descriptor_protocol_static_asserts(value_cpp, bounds, node=func)
                            if fsig.lazy_params:
                                from .emit.lazy_param_emit import emit_lazy_param_prologue
                                emit_lazy_param_prologue(self, fsig.lazy_params)
                            self._emit_generic_body_or_type_if(func, fsig, type_if_plan=type_if_plan, type_if_pick=type_if_pick)

    def _emit_entry_module_implementations(self) -> None:
        """入口实现：用户模块 → ``source_lines``；bootstrap ``py2cpp`` → ``.cpp`` / ``.inl``。"""
        entry_classes = [info for info in self.classes.values() if info.module_path == self.entry_module_path and (not info.is_descriptor) and (not info.is_mixin) and (not info.is_annotation) and (not info.is_variant_mixin) and (not self._is_type_marker(info))]
        entry_funcs = [f for f in self._entry_functions() if not (f.name == 'main' and (not self.emit_main)) and f.name != 'main' and (f.name not in self.delegates)]
        others = [f for f in entry_funcs if not self._is_decorator_impl(f)]
        impl_funcs = [f for f in entry_funcs if self._is_decorator_impl(f)]
        all_funcs = self._module_functions_emit_order(others) + impl_funcs
        if not entry_classes and (not all_funcs):
            return
        if self._is_stdlib_module(self.entry_module_path) and self._can_write_stdlib_artifact(self.entry_module_path):
            mp = self.entry_module_path
            allowed = {id(f) for f in all_funcs}
            emit_funcs = self._module_emit_functions_for(mp)
            from .analysis.variadic_template import typevar_tuple_names_for_emit

            def _needs_func_template(func: ast.FunctionDef) -> bool:
                fsig = self._function_sig_for(mp, func)
                return bool(fsig.func_ft.template_names or typevar_tuple_names_for_emit(fsig.func_ft, fsig.variadic_template))
            non_tpl_funcs = [f for f in emit_funcs if id(f) in allowed and (not _needs_func_template(f)) and (not is_overload_stub(f))]
            tpl_funcs = [f for f in emit_funcs if id(f) in allowed and _needs_func_template(f) and (not is_overload_stub(f))]
            non_tpl_classes = [c for c in entry_classes if not c.is_template()]
            tpl_classes = [c for c in entry_classes if c.is_template()]
            emit_stdlib_module_paste_before(self, mp)
            if non_tpl_funcs:
                with with_stdlib_inl(self, mp):
                    for func in non_tpl_funcs:
                        qname = self._module_function_qualifier(mp, self._module_function_cpp_name(mp, func))
                        self._emit_stdlib_module_function_body(mp, func, qualified_name=qname)
            if non_tpl_classes or tpl_classes or tpl_funcs:
                with self._use_module_inl(mp), self._use_import_bindings(mp), self._use_inl_namespace(mp):
                    for info in non_tpl_classes + tpl_classes:
                        _emit_class_methods_body(self, info)
                    for func in tpl_funcs:
                        qname = self._module_function_qualifier(mp, self._module_function_cpp_name(mp, func))
                        self._emit_stdlib_module_function_body(mp, func, qualified_name=qname)
            emit_stdlib_module_paste_after(self, mp)
            return
        with self._use_source(), self._use_import_bindings(self.entry_module_path), self._use_module_namespace(self.entry_module_path):
            self._emit_module_import_usings(self.entry_module_path)
            for info in entry_classes:
                _emit_class_methods_body(self, info)
            for func in all_funcs:
                fsig = self.function_sigs[self.entry_module_path, func.name]
                sig = format_fn_sig(self._sig_return_storage(fsig), fsig.ret_trail, func.name, self._function_sig_params_impl(fsig.params)) + fn_noexcept_suffix(fsig.is_noexcept)
                with self._use_scope(func) as scope:
                    from .analysis.type_emit import bind_scope_param
                    for arg in func.args.args:
                        bind_scope_param(scope, arg.arg, fsig)
                        scope.vars[arg.arg] = NameContext.Argument
                    if fsig.variadic_template is not None:
                        vt = fsig.variadic_template
                        bind_scope_param(scope, vt.param_name, fsig)
                        scope.vars[vt.param_name] = NameContext.Argument
                    elif fsig.vararg_pack is not None:
                        vp = fsig.vararg_pack
                        from .analysis.type_emit import bind_scope_vararg
                        bind_scope_vararg(scope, vp.param_name, vp.cpp_type, classes=self.classes)
                        scope.vars[vp.param_name] = NameContext.Argument
                    if fsig.lazy_params:
                        scope.lazy_params = dict(fsig.lazy_params)
                    type_if_plan = plan_type_if_chain(self, func)
                    type_if_pick = None
                    if type_if_plan is not None:
                        type_if_pick = emit_type_if_dispatch(self, type_if_plan, fsig)
                    if fsig.variadic_template is not None:
                        from .emit.variadic_template_emit import prescan_emit_vt_loop_structs
                        prescan_emit_vt_loop_structs(self, func, fsig.variadic_template, param_types=self._sig_param_types_map(fsig))
                    from .analysis.variadic_template import typevar_tuple_names_for_emit
                    if fsig.func_ft.template_names or typevar_tuple_names_for_emit(fsig.func_ft, fsig.variadic_template):
                        self._emit_function_template_prefix(fsig.func_ft, default_constraint=False, variadic_template=fsig.variadic_template)
                    with self._use_block(sig):
                        if fsig.lazy_params:
                            from .emit.lazy_param_emit import emit_lazy_param_prologue
                            emit_lazy_param_prologue(self, fsig.lazy_params)
                        self._emit_generic_body_or_type_if(func, fsig, type_if_plan=type_if_plan, type_if_pick=type_if_pick)

    def _emit_module_functions(self):
        with self._use_source(), self._use_import_bindings(self.entry_module_path):
            entry_ns = namespace_qualifier_for_module(self.entry_module_path)
            if entry_ns:
                self.write_line(f'using namespace {entry_ns};')
                self.write_line()
            mains = [f for f in self._entry_functions() if f.name == 'main' and self.emit_main]
            for func in mains:
                fsig = self.function_sigs[self.entry_module_path, func.name]
                sig = format_fn_sig(self._sig_return_storage(fsig), fsig.ret_trail, func.name, self._function_sig_params_impl(fsig.params)) + fn_noexcept_suffix(fsig.is_noexcept)
                with self._use_scope(func) as scope:
                    with self._use_block(sig):
                        self._emit_body(func.body)
                        if not self._function_has_return(func):
                            self.write_line('return 0;')
            if self.emit_main and (not mains):
                with self._use_block('int main()'):
                    self.write_line('return 0;')
