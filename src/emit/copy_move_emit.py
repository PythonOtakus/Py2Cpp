"""``__copy__`` / ``__move__``：用户方法体与默认实现、复制/移动特殊成员。"""
from __future__ import annotations
from contextlib import nullcontext
from typing import TYPE_CHECKING
from ..analysis.type_pred import is_array_type, is_container_type, is_stack_array_type
from ..analysis.ir import ClassInfo, cpp_array_ndim, cpp_ident, cpp_stack_array_size
from ..analysis.type_emit import field_storage_cpp
from ..passes.move_state import MOVE_STATE_FIELD
if TYPE_CHECKING:
    from ..translator import Translator

def _emit_ctx(tr: Translator, info: ClassInfo):
    if info.is_template():
        return tr._use_module_inl(info.module_path)
    if tr._is_stdlib_module(info.module_path):
        return tr._use_module_inl(info.module_path)
    return nullcontext()

def _qual_name(tr: Translator, info: ClassInfo) -> str:
    if hasattr(tr, '_class_method_qualifier'):
        return tr._class_method_qualifier(info)
    return info.cpp_specialization() if info.is_template() else info.cpp_name()

def emit_auto_copy(tr: Translator, info: ClassInfo) -> None:
    """按字段与 ``owned_fields`` 生成默认 ``__copy__``（深拷贝堆字段）。"""
    cpp = info.cpp_name()
    qual = _qual_name(tr, info)
    with _emit_ctx(tr, info), tr._use_source():
        if info.is_template():
            tr._emit_template_prefix(info)
        with tr._use_block(f'void {qual}::__copy__(const {cpp}& other)'):
            if MOVE_STATE_FIELD in info.fields:
                tr.write_line(f'this->{MOVE_STATE_FIELD} = false;')
            for field in info.fields:
                if field.startswith('__ann__') or field == MOVE_STATE_FIELD:
                    continue
                if field in info.owned_fields:
                    elem, kind = info.owned_fields[field]
                    if kind == 'free':
                        with tr._use_block(f'if ((other.{field} != nullptr))'):
                            tr.write_line(f'this->{field} = alloc<{elem}>();')
                            tr.write_line(f'*this->{field} = *other.{field};')
                        with tr._use_block('else'):
                            tr.write_line(f'this->{field} = nullptr;')
                    elif kind == 'freeArray':
                        n = info.owned_array_sizes.get(field)
                        if n is not None:
                            with tr._use_block(f'if ((other.{field} != nullptr))'):
                                tr.write_line(f'this->{field} = allocArray<{elem}>({n});')
                                with tr._use_block(f'for (int __i = 0; __i < {n}; __i = __i + 1)'):
                                    tr.write_line(f'this->{field}[__i] = other.{field}[__i];')
                            with tr._use_block('else'):
                                tr.write_line(f'this->{field} = nullptr;')
                        else:
                            tr.write_line(f'this->{field} = other.{field};')
                else:
                    ft = field_storage_cpp(info, field)
                    if is_container_type(ft) or is_stack_array_type(ft) or (is_array_type(ft) and cpp_array_ndim(ft) is not None):
                        tr.write_line(f'this->{field}.__copy__(other.{field});')
                    else:
                        tr.write_line(f'this->{field} = other.{field};')
        tr.write_line()

def emit_auto_move(tr: Translator, info: ClassInfo) -> None:
    """生成默认 ``__move__``：``owned_fields`` 窃取指针，其余字段按值拷贝。"""
    cpp = info.cpp_name()
    qual = _qual_name(tr, info)
    with _emit_ctx(tr, info), tr._use_source():
        if info.is_template():
            tr._emit_template_prefix(info)
        with tr._use_block(f'void {qual}::__move__({cpp}& other)'):
            if MOVE_STATE_FIELD in info.fields:
                tr.write_line(f'this->{MOVE_STATE_FIELD} = false;')
            for field in info.fields:
                if field.startswith('__ann__') or field == MOVE_STATE_FIELD:
                    continue
                ft = field_storage_cpp(info, field)
                if is_array_type(ft) and cpp_array_ndim(ft) is not None:
                    tr.write_line(f'this->{field}.__move__(other.{field});')
                    continue
                tr.write_line(f'this->{field} = other.{field};')
                if field in info.owned_fields:
                    tr.write_line(f'other.{field} = nullptr;')
            if MOVE_STATE_FIELD in info.fields:
                tr.write_line(f'other.{MOVE_STATE_FIELD} = true;')
        tr.write_line()

def emit_auto_copy_move(tr: Translator, info: ClassInfo) -> None:
    if info.needs_auto_copy():
        emit_auto_copy(tr, info)
    if info.needs_auto_move():
        emit_auto_move(tr, info)

def _emit_array_clone_from(tr: Translator, info: ClassInfo, qual: str, cpp: str, *, dest: str) -> None:
    """把 ``other`` 的缓冲克隆到 ``dest``（``dest`` 为 ``this`` 或已置空的成员）。"""
    tr.write_line(f'{dest}->_shape = other._shape;')
    tr.write_line('int __n = other._shape.__getitem__(0);')
    with tr._use_block('if ((__n > 0) && ((other.view__get()).at(0) != nullptr))'):
        tr.write_line(f'{dest}->copy_from_ptr((other.view__get()).at(0), __n, __n);')

def _emit_array_copy_ctor(tr: Translator, info: ClassInfo, qual: str, cpp: str) -> None:
    """``array`` 须在已置空状态下按元素 ``init``，不能对未构造的 ``this`` 调 ``__copy__``。"""
    with tr._use_block(f'{qual}::{cpp}(const {cpp}& other)'):
        _emit_array_clone_from(tr, info, qual, cpp, dest='this')
    tr.write_line()

def _emit_array_copy_assign(tr: Translator, info: ClassInfo, qual: str, cpp: str) -> None:
    """``operator=`` 须先释放旧缓冲再按 ``other`` 重建（``__copy__`` 要求等长）。"""
    with tr._use_block(f'{qual}& {qual}::operator=(const {cpp}& other)'):
        tr.write_line('if ((this == &other))')
        with tr._use_indent():
            tr.write_line('return *this;')
        tr.write_line(f'this->release(this->_shape.__getitem__(0));')
        _emit_array_clone_from(tr, info, qual, cpp, dest='this')
        tr.write_line('return *this;')
    tr.write_line()

def emit_copy_move_special_members(tr: Translator, info: ClassInfo) -> None:
    """在 ``__copy__`` / ``__move__`` 方法体之后生成对应的 C++ 特殊成员。"""
    if not info.has_copy and (not info.has_move):
        return
    cpp = info.cpp_name()
    qual = _qual_name(tr, info)
    with _emit_ctx(tr, info), tr._use_source():
        if info.has_copy:
            if info.is_template():
                tr._emit_template_prefix(info)
            if info.name == 'array':
                _emit_array_copy_ctor(tr, info, qual, cpp)
            elif info.name == 'list':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _length(0), _capacity(0), __moved__(false), _data()')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'str':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _data()')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'bytes':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _data()')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'dict':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _capacity(8), _size(0), __moved__(false), _order(), _buckets(0)')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name in ('set', 'frozenset'):
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _capacity(8), _size(0), __moved__(false), _buckets(0)')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'frozendict':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _capacity(8), _size(0), __moved__(false), _order(), _buckets(0)')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'frozenlist':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _length(0), _capacity(0), __moved__(false), _data()')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'deque':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _head(nullptr), _tail(nullptr), _length(0), __moved__(false), _maxlen(PY2CPP_INT_MIN)')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            elif info.name == 'ChunkDeque':
                tr.write_line(f'{qual}::{cpp}(const {cpp}& other) : _block_size(512), _head(nullptr), _tail(nullptr), _len(0), __moved__(false)')
                with tr._use_block():
                    tr.write_line('__copy__(other);')
            else:
                with tr._use_block(f'{qual}::{cpp}(const {cpp}& other)'):
                    tr.write_line('__copy__(other);')
            tr.write_line()
            if info.is_template():
                tr._emit_template_prefix(info)
            if info.name == 'array':
                _emit_array_copy_assign(tr, info, qual, cpp)
            else:
                with tr._use_block(f'{qual}& {qual}::operator=(const {cpp}& other)'):
                    tr.write_line('if ((this != &other))')
                    with tr._use_indent():
                        tr.write_line('__copy__(other);')
                    tr.write_line('return *this;')
                tr.write_line()
        if info.has_move:
            if info.is_template():
                tr._emit_template_prefix(info)
            if info.name == 'list':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _length(0), _capacity(0), __moved__(false), _data()')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name in ('set', 'frozenset'):
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _capacity(8), _size(0), __moved__(false), _buckets(0)')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name == 'frozendict':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _capacity(8), _size(0), __moved__(false), _order(), _buckets(0)')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name == 'frozenlist':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _length(0), _capacity(0), __moved__(false), _data()')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name == 'dict':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _capacity(8), _size(0), __moved__(false), _order(), _buckets(0)')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name == 'str':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _data()')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name == 'deque':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _head(nullptr), _tail(nullptr), _length(0), __moved__(false), _maxlen(PY2CPP_INT_MIN)')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            elif info.name == 'ChunkDeque':
                tr.write_line(f'{qual}::{cpp}({cpp}&& other) : _block_size(512), _head(nullptr), _tail(nullptr), _len(0), __moved__(false)')
                with tr._use_block():
                    tr.write_line('__move__(other);')
            else:
                with tr._use_block(f'{qual}::{cpp}({cpp}&& other)'):
                    tr.write_line('__move__(other);')
            tr.write_line()
            if info.is_template():
                tr._emit_template_prefix(info)
            with tr._use_block(f'{qual}& {qual}::operator=({cpp}&& other)'):
                tr.write_line('if ((this != &other))')
                with tr._use_indent():
                    tr.write_line('__move__(other);')
                tr.write_line('return *this;')
            tr.write_line()

def is_frozen_dataclass(info: ClassInfo) -> bool:
    opts = getattr(info, 'dataclass_options', None)
    return bool(info.is_dataclass and getattr(opts, 'frozen', False))

def emit_frozen_dataclass_assign(tr: Translator, info: ClassInfo) -> None:
    """``@dataclass(frozen=True)`` 局部 ``q = p``：重建对象以保留 const 字段语义。"""
    if not is_frozen_dataclass(info):
        return
    if info.is_refcount or info.is_uncopyable or info.has_copy:
        return
    cpp = info.cpp_name()
    spec = info.cpp_specialization() if info.is_template() else cpp
    qual = _qual_name(tr, info)
    with _emit_ctx(tr, info), tr._use_source():
        if info.is_template():
            tr._emit_template_prefix(info)
        with tr._use_block(f'{qual}& {qual}::operator=(const {spec}& other)'):
            tr.write_line('if ((this != &other))')
            with tr._use_block():
                tr.write_line(f'this->~{cpp}();')
                tr.write_line(f'::new (static_cast<void*>(this)) {spec}(other);')
            tr.write_line('return *this;')
        tr.write_line()
