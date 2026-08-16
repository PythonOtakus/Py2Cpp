"""生成器 ``__resume``：``switch (_state)`` 状态机（``yield`` / ``yield from`` / ``return``）。"""
from __future__ import annotations
import ast
import copy
from contextlib import contextmanager
from typing import TYPE_CHECKING
from ..analysis.patterns import temp_name as _temp_name
if TYPE_CHECKING:
    from ..translator import Translator
from ..analysis.type_pred import is_list_type
from ..analysis.type_extract import list_elem_type
from ..analysis.ir import ClassInfo, cpp_iter_result_yield_expr, iter_result_done_cpp, iter_result_return_value_cpp, iter_result_value_cpp
from ..analysis.type_emit import field_ann_ast
from .generators import COROUTINE_SUFFIX, GENERATOR_SUFFIX, _FOR_PREFIX, _SEND_FIELD, _SEND_FLAG, _STATE_FIELD, _YF_PREFIX, _field_name, _is_async_generator_yield, async_for_needs_suspend, body_has_yield, _yield_from_iter_uses_assign, _iter_field_uses_copy_from

def _stmt_list_ends_with_yield(body: list[ast.stmt]) -> bool:
    """语句块末句为 ``yield`` / ``yield from``（续推后须落到 ``join``）。"""
    if not body:
        return False
    last = body[-1]
    if isinstance(last, ast.Expr):
        return isinstance(last.value, (ast.Yield, ast.YieldFrom))
    return False

def _then_ends_with_yield(body: list[ast.stmt]) -> bool:
    return _stmt_list_ends_with_yield(body)

def _branch_exits_abruptly(body: list[ast.stmt]) -> bool:
    """分支末句为 ``break`` / ``continue`` / ``return``（已离开分支，勿再桥接 ``join``）。"""
    if not body:
        return False
    return isinstance(body[-1], (ast.Break, ast.Continue, ast.Return))

class GeneratorSwitchEmitter:
    """将含 ``yield`` 的 ``__resume`` 体译为 C++ ``switch`` 状态机。"""

    def __init__(self, tr: Translator, *, class_info: ClassInfo | None=None):
        self.tr = tr
        self._class_info = class_info
        self._state = 0
        self._state_slot = 0
        self._yf_index = 0
        self._open_case: int | None = None
        self._case_brace_open = False
        self._yield_recv: dict[int, ast.expr] = {}
        self._while_recv_stack: list[int | None] = []
        self._while_loop_recv_state: int | None = None
        self._while_loop_recv_reserved: bool = False
        self._while_continue_stack: list[int] = []
        self._for_continue_stack: list[int] = []
        self._for_recv_stack: list[int | None] = []
        self._for_index_by_id: dict[int, int] = {}
        self._gen_break_target_stack: list[int] = []
        self._loop_else_flag_by_id: dict[int, str] = {}
        self._native_for_depth: int = 0
        self._current_stmts: list[ast.stmt] = []
        self._stmt_index: int = 0
        self._resume_tail_state: int | None = None

    def _collect_loop_else_nodes(self, stmts: list[ast.stmt], out: list[ast.For | ast.AsyncFor | ast.While]) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                if stmt.orelse:
                    out.append(stmt)
                self._collect_loop_else_nodes(stmt.body, out)
            elif isinstance(stmt, ast.If):
                self._collect_loop_else_nodes(stmt.body, out)
                self._collect_loop_else_nodes(stmt.orelse, out)

    def _loop_else_flag(self, node: ast.For | ast.AsyncFor | ast.While) -> str | None:
        if not node.orelse:
            return None
        fid = id(node)
        if fid not in self._loop_else_flag_by_id:
            self._loop_else_flag_by_id[fid] = _temp_name('loop_else')
        return self._loop_else_flag_by_id[fid]

    def _emit_loop_else_stmts(self, node: ast.For | ast.AsyncFor | ast.While, flag: str) -> None:
        """``for``/``while`` 的 ``else``：``flag`` 为假时跳过 else 体（勿用 ``if/else``，避免与 ``case`` 花括号冲突）。"""
        merge_st = self._alloc_state()
        with self.tr._use_block(f'if (!({flag}))'):
            self._set_state(merge_st)
            self.tr.write_line('continue;')
        with self.tr._use_block(f'if ({flag})'):
            self._emit_stmts(node.orelse)
        if self._open_case is not None and self._case_brace_open:
            self._close_case_block()
        self._open_case_block(merge_st)
        self._state = merge_st

    @contextmanager
    def _use_gen_loop_else(self, node: ast.For | ast.AsyncFor | ast.While):
        """``for``/``while`` 的 ``else``：标志在 ``switch`` 前声明，此处仅 ``break`` 置假与收尾 ``if``。"""
        from ..translator import _LoopFrame
        flag = self._loop_else_flag(node)
        self.tr._loop_stack.append(_LoopFrame(flag))
        try:
            yield
        finally:
            self.tr._loop_stack.pop()
        if flag is not None:
            self._emit_loop_else_stmts(node, flag)

    def _build_for_iter_index_map(self, body: list[ast.stmt]) -> dict[int, int]:
        from ..emit.loops_emit import is_direct_range_call
        out: dict[int, int] = {}
        idx = 0
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(node, ast.For):
                if not body_has_yield(node.body):
                    continue
                if is_direct_range_call(node.iter):
                    continue
            elif isinstance(node, ast.AsyncFor):
                if not async_for_needs_suspend(node):
                    continue
            else:
                continue
            out[id(node)] = idx
            idx += 1
        return out

    def emit(self, body: list[ast.stmt]) -> None:
        loops: list[ast.For | ast.While] = []
        self._collect_loop_else_nodes(body, loops)
        self._for_index_by_id = self._build_for_iter_index_map(body)
        self._loop_else_flag_by_id = {id(node): _temp_name('loop_else') for node in loops}
        for flag in self._loop_else_flag_by_id.values():
            self.tr.write_line(f'bool {flag} = true;')
        with self.tr._use_block('while (true)'):
            with self.tr._use_block(f'switch (this->{_STATE_FIELD})'):
                self._emit_stmts(body)
                self._close_case_block()
                self.tr.write_line('default:')
                with self.tr._use_block():
                    self.tr.write_line(f'return {self.tr._iter_result_return_expr()};')
            self.tr.write_line(f'return {self.tr._iter_result_return_expr()};')

    def _set_state(self, n: int) -> None:
        self.tr.write_line(f'this->{_STATE_FIELD} = {n};')

    def _alloc_state(self) -> int:
        self._state_slot += 1
        return self._state_slot

    def _close_case_block(self) -> None:
        if self._case_brace_open:
            self.tr.indent_level -= 1
            self.tr.write_line('}')
            self._case_brace_open = False

    def _open_case_block(self, n: int) -> None:
        if self._open_case == n and self._case_brace_open:
            return
        self._close_case_block()
        self._open_case = n
        self.tr.write_line(f'case {n}:')
        self.tr.write_line('{')
        self.tr.indent_level += 1
        self._case_brace_open = True
        recv_tgt = self._yield_recv.pop(n, None)
        if recv_tgt is not None:
            lhs = self.tr.visit(recv_tgt)
            with self.tr._use_block(f'if (this->{_SEND_FLAG})'):
                self.tr.write_line(f'{lhs} = this->{_SEND_FIELD};')
                self.tr.write_line(f'this->{_SEND_FLAG} = false;')

    def _emit_stmts(self, stmts: list[ast.stmt]) -> None:
        prev_stmts, prev_idx = (self._current_stmts, self._stmt_index)
        self._current_stmts = stmts
        try:
            for i, stmt in enumerate(stmts):
                self._stmt_index = i
                self._emit_stmt(stmt)
        finally:
            self._current_stmts, self._stmt_index = (prev_stmts, prev_idx)

    def _emit_for_after_loop_tail_jump(self, node: ast.For | ast.AsyncFor) -> None:
        """``for`` 后还有语句时，从 after 态显式跳转（勿依赖 ``switch`` 落入）。"""
        stmts = self._current_stmts
        idx = self._stmt_index
        if idx + 1 >= len(stmts):
            return
        tail_st = self._alloc_state()
        self._resume_tail_state = tail_st
        self._set_state(tail_st)
        self.tr.write_line('continue;')

    def _recv_target(self, target: ast.expr) -> ast.expr | None:
        if isinstance(target, ast.Name):
            return target
        if isinstance(target, ast.Attribute):
            cur: ast.expr = target
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id == 'self':
                return target
        return None

    def _recv_from_yield_value(self, stmt: ast.stmt, value: ast.expr | None) -> tuple[ast.expr, ast.expr] | None:
        tgt_expr: ast.expr | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            tgt_expr = stmt.targets[0]
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is value:
            tgt_expr = stmt.target
        else:
            return None
        tgt = self._recv_target(tgt_expr) if tgt_expr is not None else None
        if tgt is None or value is None:
            return None
        return (tgt, value)

    def _recv_from_yield_stmt(self, stmt: ast.stmt) -> tuple[ast.expr, ast.expr | None] | None:
        val: ast.expr | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            val = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            val = stmt.value
        else:
            return None
        if not isinstance(val, ast.Yield):
            return None
        got = self._recv_from_yield_value(stmt, val)
        if got is None:
            return None
        tgt, y = got
        return (tgt, y.value)

    def _recv_from_yield_from_stmt(self, stmt: ast.stmt) -> tuple[ast.expr, ast.expr] | None:
        val: ast.expr | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            val = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            val = stmt.value
        else:
            return None
        if not isinstance(val, ast.YieldFrom):
            return None
        got = self._recv_from_yield_value(stmt, val)
        if got is None:
            return None
        tgt, yf = got
        return (tgt, yf.value)

    def _emit_stmt(self, stmt: ast.stmt) -> None:
        if self._resume_tail_state is not None:
            self._state = self._resume_tail_state
            self._resume_tail_state = None
        recv = self._recv_from_yield_stmt(stmt)
        if recv is not None:
            tgt, val = recv
            self._open_case_block(self._state)
            self._emit_yield(val, recv_target=tgt)
            return
        recv_yf = self._recv_from_yield_from_stmt(stmt)
        if recv_yf is not None:
            tgt, val = recv_yf
            self._open_case_block(self._state)
            self._emit_yield_from(val, recv_target=tgt)
            return
        self._open_case_block(self._state)
        match stmt:
            case ast.Expr(value=ast.Yield(value=v)):
                self._emit_yield(v)
            case ast.Expr(value=ast.YieldFrom(value=v)):
                self._emit_yield_from(v)
            case ast.If():
                if_y = body_has_yield(stmt.body) or body_has_yield(stmt.orelse)
                if if_y:
                    self._emit_if(stmt)
                elif self._native_for_depth > 0:
                    self.tr.visit_If(stmt)
                elif self._while_continue_stack or self._for_continue_stack:
                    self._emit_if_plain(stmt)
                else:
                    self._emit_if(stmt)
            case ast.While():
                self._emit_while(stmt)
            case ast.For() | ast.AsyncFor():
                self._emit_for(stmt)
            case ast.With() | ast.AsyncWith():
                if isinstance(stmt, ast.AsyncWith) or getattr(stmt, 'is_async', False):
                    raise NotImplementedError('async with 须在 async def 内，并由 coroutine_desugar 脱糖后再生成')
                self.tr.visit_With(stmt)
            case ast.Return():
                self._emit_return(stmt)
            case ast.Break():
                if self._gen_break_target_stack:
                    flag = self.tr._loop_stack[-1].else_flag if self.tr._loop_stack else None
                    if flag:
                        self.tr.write_line(f'{flag} = false;')
                    self._set_state(self._gen_break_target_stack[-1])
                    self.tr.write_line('continue;')
                elif self.tr._loop_stack:
                    self.tr.visit_Break(stmt)
                else:
                    self.tr.write_line(f'return {self.tr._iter_result_return_expr()};')
            case ast.Continue():
                if self._for_continue_stack:
                    self._set_state(self._for_continue_stack[-1])
                    self.tr.write_line('continue;')
                elif self._while_continue_stack:
                    self._set_state(self._while_continue_stack[-1])
                    self.tr.write_line('continue;')
                else:
                    self.tr.visit_Continue(stmt)
            case ast.Pass():
                pass
            case _:
                ctx: ast.expr | None = None
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    ctx = self._target_context_ann(stmt.targets[0])
                with self.tr._use_type_context_ann(ctx):
                    self.tr.visit(stmt)

    def _emit_return(self, node: ast.Return) -> None:
        self.tr._emit_active_finally()
        self.tr._emit_with_exits()
        if node.value is None:
            self.tr.write_line(f'return {self.tr._iter_result_return_expr()};')
        else:
            with self.tr._use_type_context_ann(self._return_context_ann()):
                val = self.tr.visit(node.value)
            self.tr.write_line(f'return {self.tr._result_return_done_expr(val)};')

    def _emit_yield(self, value: ast.expr | None, *, recv_target: ast.expr | None=None) -> None:
        if recv_target is not None and self._while_recv_stack and (self._while_loop_recv_state is not None) and (not self._while_loop_recv_reserved):
            nxt = self._while_loop_recv_state
            self._while_loop_recv_reserved = True
        else:
            nxt = self._alloc_state()
        if recv_target is not None:
            self._yield_recv[nxt] = recv_target
            if self._while_recv_stack:
                self._while_recv_stack[-1] = nxt
            if self._for_recv_stack:
                self._for_recv_stack[-1] = nxt
        self._set_state(nxt)
        if value is None:
            self.tr.write_line(f"return {self.tr._result_value_expr('0')};")
        else:
            val = self.tr.visit(value)
            self.tr.write_line(f'return {self.tr._result_value_expr(val)};')
        self._close_case_block()
        self._open_case = None
        self._state = nxt

    def _is_async_generator_class(self) -> bool:
        """``AsyncGeneratorType[Y, None]``：只识别已混入 ``__aiter__``/``__anext__`` 的 async 生成器类。"""
        info = self._class_info
        if info is None:
            return False
        method_names = {
            node.name
            for node in info.node.body
            if isinstance(node, ast.FunctionDef)
        }
        if '__aiter__' not in method_names or '__anext__' not in method_names:
            return False
        element_ann: ast.expr | None = None
        return_ann: ast.expr | None = None
        for node in info.node.body:
            if isinstance(node, ast.TypeAlias):
                if node.name.id == 'Element':
                    element_ann = node.value
                elif node.name.id == 'ReturnType':
                    return_ann = node.value
        if return_ann is None or element_ann is None:
            return False
        if isinstance(return_ann, ast.Name) and return_ann.id in ('PyNone', 'None'):
            return _is_async_generator_yield(element_ann)
        return False

    def _yf_it_field_uses_assign(self, it_field: str) -> bool:
        return _iter_field_uses_copy_from(it_field, self._class_info)

    @staticmethod
    def _ann_is_none(ann: ast.expr | None) -> bool:
        return (
            isinstance(ann, ast.Constant) and ann.value is None
        ) or (
            isinstance(ann, ast.Name) and ann.id in ('None', 'PyNone')
        )

    def _outer_yield_ann_is_none(self) -> bool:
        if self._class_info is None:
            return False
        alias = self._class_info.type_aliases.get('Element')
        if alias is not None:
            return self._ann_is_none(alias.value)
        for stmt in self._class_info.node.body:
            if (
                isinstance(stmt, ast.TypeAlias)
                and isinstance(stmt.name, ast.Name)
                and stmt.name.id == 'Element'
            ):
                return self._ann_is_none(stmt.value)
        return False

    def _yield_from_iter_yields_none(self, it_field: str) -> bool:
        if self._class_info is None:
            return False
        ann = field_ann_ast(self._class_info, it_field)
        if (
            isinstance(ann, ast.Subscript)
            and isinstance(ann.value, ast.Name)
            and ann.value.id in ('CoroutineType', 'GeneratorType', 'AsyncGeneratorType')
        ):
            sl = ann.slice
            if isinstance(sl, ast.Tuple) and sl.elts:
                return self._ann_is_none(sl.elts[0])
        from ..analysis.type_emit import field_storage_cpp
        ft = field_storage_cpp(self._class_info, it_field)
        return bool(
            ft
            and (
                ft.startswith('PyCoroutine<PyNone,')
                or ft.startswith('PyGenerator<PyNone,')
                or ft.startswith('PyAsyncGenerator<PyNone,')
            )
        )

    def _target_context_ann(self, target: ast.expr | None) -> ast.expr | None:
        if target is None:
            return None
        if isinstance(target, ast.Attribute) and not (
            isinstance(target.value, ast.Name) and target.value.id == 'self'
        ):
            recv_ann = self._target_context_ann(target.value)
            if isinstance(recv_ann, ast.Name):
                info = self.tr.classes.get(recv_ann.id)
                if info is not None:
                    ann = field_ann_ast(info, target.attr)
                    if ann is not None:
                        return copy.deepcopy(ann)
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == 'self'
            and self._class_info is not None
        ):
            ann = field_ann_ast(self._class_info, target.attr)
            if ann is not None:
                return copy.deepcopy(ann)
            for stmt in self._class_info.node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Attribute)
                    and isinstance(stmt.target.value, ast.Name)
                    and stmt.target.value.id == 'self'
                    and stmt.target.attr == target.attr
                ):
                    return copy.deepcopy(stmt.annotation)
            return None
        if isinstance(target, ast.Name):
            t = self.tr._scope_storage(target.id)
            info = self.tr._class_info_for_type(t)
            if info is not None:
                return ast.Name(id=info.name, ctx=ast.Load())
        return None

    def _return_context_ann(self) -> ast.expr | None:
        if self._class_info is None:
            return None
        alias = self._class_info.type_aliases.get('ReturnType')
        if alias is None:
            return None
        return copy.deepcopy(alias.value)

    def _emit_yield_from(self, value: ast.expr, *, recv_target: ast.expr | None=None) -> None:
        idx = self._yf_index
        self._yf_index += 1
        active = f'{_YF_PREFIX}{idx}_active'
        it_field = f'{_YF_PREFIX}{idx}_it'
        with self.tr._use_type_context_ann(self._target_context_ann(recv_target)):
            src = self.tr.visit(value)
        sep = self.tr._member_access(src)
        iter_expr = f'({src}){sep}__iter__()'
        yf_state = self._alloc_state()
        self._set_state(yf_state)
        self.tr.write_line('continue;')
        self._close_case_block()
        self._open_case_block(yf_state)
        self._state = yf_state
        with self.tr._use_block(f'if (!this->{active})'):
            if self._yf_it_field_uses_assign(it_field):
                self.tr.write_line(f'this->{it_field}.copyFrom({iter_expr});')
            else:
                self.tr.write_line(f'this->{it_field} = {iter_expr};')
            self.tr.write_line(f'this->{active} = true;')
        res = _temp_name('yf')
        self.tr.write_line(f'auto {res} = this->{it_field}.__next__();')
        with self.tr._use_block(f'if (!{iter_result_done_cpp(res)})'):
            if (
                self._is_async_generator_class()
                or (
                    self._yield_from_iter_yields_none(it_field)
                    and not self._outer_yield_ann_is_none()
                )
            ):
                self.tr.write_line('continue;')
            else:
                rt = self.tr._next_result_cpp_type()
                self.tr.write_line(f'return {cpp_iter_result_yield_expr(rt, iter_result_value_cpp(res))};')
        self.tr.write_line(f'this->{active} = false;')
        if recv_target is not None:
            lhs = self.tr.visit(recv_target)
            self.tr.write_line(f'{lhs} = {iter_result_return_value_cpp(res)};')
        nxt = self._alloc_state()
        self._set_state(nxt)
        self.tr.write_line('continue;')
        self._close_case_block()
        self._open_case = None
        self._state = nxt

    def _body_has_recv_yield(self, body: list[ast.stmt]) -> bool:
        for stmt in body:
            if self._recv_from_yield_stmt(stmt) is not None:
                return True
            if isinstance(stmt, ast.If):
                if self._body_has_recv_yield(stmt.body) or self._body_has_recv_yield(stmt.orelse):
                    return True
        return False

    def _emit_loop_body_tail(self, loop_target: int, recv_stack: list[int | None]) -> None:
        """循环体扫完后落回下一迭代；``yield`` 后若已关 ``case`` 则先 ``open`` 当前态再跳。"""
        if not self._case_brace_open:
            self._open_case_block(self._state)
        self._set_state(loop_target)
        self.tr.write_line('continue;')

    def _emit_yield_to_join_bridge(self, resume_st: int, join_st: int) -> None:
        """``yield`` 续推态 ``resume_st`` 再 ``continue`` 到 ``join_st``。"""
        if self._open_case == resume_st and self._case_brace_open:
            self._set_state(join_st)
            self.tr.write_line('continue;')
            self._close_case_block()
            return
        if self._open_case is not None and self._case_brace_open:
            self._close_case_block()
        else:
            self._open_case = None
            self._case_brace_open = False
        self._open_case_block(resume_st)
        self._set_state(join_st)
        self.tr.write_line('continue;')
        self._close_case_block()

    def _emit_if_plain(self, node: ast.If) -> None:
        """常规 ``if``/``else``（子语句仍走 ``_emit_stmt``，``continue``/``break`` 走状态机栈）。"""
        with self.tr._use_block(f'if ({self.tr.visit(node.test)})'):
            self._emit_stmts(node.body)
        if node.orelse:
            with self.tr._use_block('else'):
                self._emit_stmts(node.orelse)

    def _emit_if(self, node: ast.If) -> None:
        """``if``/``else`` 用 ``if (!test) { state=else; continue; }`` 分态，避免 ``while`` 截断 ``case`` 后 ``else`` 落入错误态。"""
        else_st = self._alloc_state() if node.orelse else None
        join_st = self._alloc_state()
        entry_st = self._state
        with self.tr._use_block(f'if (!({self.tr.visit(node.test)}))'):
            if else_st is not None:
                self._set_state(else_st)
            else:
                self._set_state(join_st)
            self.tr.write_line('continue;')
        self._emit_stmts(node.body)
        then_fell_through = self._state == entry_st
        if not then_fell_through and body_has_yield(node.body) and (not _branch_exits_abruptly(node.body)):
            self._emit_yield_to_join_bridge(self._state, join_st)
        if then_fell_through:
            self._set_state(join_st)
            self.tr.write_line('continue;')
            self._close_case_block()
        if else_st is not None:
            if self._open_case is not None and self._case_brace_open:
                self._close_case_block()
            else:
                self._open_case = None
                self._case_brace_open = False
            self._open_case_block(else_st)
            else_entry = else_st
            self._state = else_st
            self._emit_stmts(node.orelse)
            else_fell_through = self._state == else_entry
            if else_fell_through:
                self._set_state(join_st)
                self.tr.write_line('continue;')
                self._close_case_block()
            elif body_has_yield(node.orelse) and (not _branch_exits_abruptly(node.orelse)):
                self._emit_yield_to_join_bridge(self._state, join_st)
        if self._open_case != join_st or not self._case_brace_open:
            self._open_case_block(join_st)
        self._state = join_st

    def _emit_while(self, node: ast.While) -> None:
        """``while``：独立 loop head / after 态，避免 ``continue`` 回到 case 0 重跑初始化；条件假时落到 after（非 ``return``）。"""
        from ..translator import _LoopFrame
        loop_head = self._alloc_state()
        after_loop = self._alloc_state()
        else_flag = self._loop_else_flag(node)
        self.tr._loop_stack.append(_LoopFrame(else_flag))
        self._while_recv_stack.append(None)
        saved_recv_state = self._while_loop_recv_state
        saved_recv_reserved = self._while_loop_recv_reserved
        self._while_loop_recv_state = None
        self._while_loop_recv_reserved = False
        if self._body_has_recv_yield(node.body):
            self._while_loop_recv_state = self._alloc_state()
        self._while_continue_stack.append(loop_head)
        self._gen_break_target_stack.append(after_loop)
        try:
            self._set_state(loop_head)
            self.tr.write_line('continue;')
            self._close_case_block()
            self._open_case_block(loop_head)
            self._state = loop_head
            if self._while_loop_recv_state is not None:
                with self.tr._use_block(f'if (this->{_SEND_FLAG})'):
                    self._set_state(self._while_loop_recv_state)
                    self.tr.write_line('continue;')
            with self.tr._use_block(f'if (!({self.tr.visit(node.test)}))'):
                self._set_state(after_loop)
                self.tr.write_line('continue;')
            self._emit_stmts(node.body)
            self._emit_loop_body_tail(loop_head, self._while_recv_stack)
            self._close_case_block()
            self._open_case_block(after_loop)
            self._state = after_loop
            if else_flag is not None:
                self._emit_loop_else_stmts(node, else_flag)
        finally:
            self._while_recv_stack.pop()
            self._while_continue_stack.pop()
            self._while_loop_recv_state = saved_recv_state
            self._while_loop_recv_reserved = saved_recv_reserved
            self._gen_break_target_stack.pop()
            self.tr._loop_stack.pop()

    def _emit_for(self, node: ast.For | ast.AsyncFor) -> None:
        if isinstance(node, ast.AsyncFor) or getattr(node, 'is_async', False):
            if async_for_needs_suspend(node):
                self._emit_for_async_suspend(node)
            else:
                self._emit_for_async(node)
            return
        if self.tr._is_direct_range_call(node.iter):
            if body_has_yield(node.body):
                self._emit_for_range_suspend(node)
            else:
                self._emit_for_range(node)
            return
        if body_has_yield(node.body):
            self._emit_for_iter_suspend(node)
            return
        self._emit_for_iter(node)

    def _emit_for_async(self, node: ast.For | ast.AsyncFor) -> None:
        """``async for``：``__aiter__`` / ``__anext__`` + ``PyIterResult`` 的 ``done``（同 ``for`` / ``__next__``）。"""
        from ..emit.loops_emit import element_type_of_iterable
        elem_t = element_type_of_iterable(self.tr, node.iter)
        iter_cpp = self.tr.visit(node.iter)
        match node.target:
            case ast.Name(id=name):
                it = _temp_name('ait')
                sep = self.tr._member_access(iter_cpp)
                self.tr.write_line(f'auto {it} = {iter_cpp}{sep}__aiter__();')
                res = _temp_name('ar')
                value_t = elem_t or 'auto'
                with self.tr._use_block('while (true)'):
                    gname = _field_name(name)
                    if self.tr.class_info and gname in self.tr.class_info.fields:
                        self.tr.write_line(f'auto {res} = {it}.__anext__();')
                        self.tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                        self.tr.write_line(f'this->{gname} = {iter_result_value_cpp(res)};')
                    else:
                        from ..emit.loops_emit import _emit_iter_next_unpack
                        _emit_iter_next_unpack(self.tr, it, res, name, value_t, iter_suffix='.__anext__()')
                    self._emit_stmts(node.body)
            case _:
                raise NotImplementedError('async for 目标仅支持简单变量名')

    def _emit_for_async_suspend(self, node: ast.AsyncFor) -> None:
        """``async for`` + ``await``/``else``：持久化 ``__aiter__`` + 分态续推。"""
        from ..translator import _LoopFrame
        match node.target:
            case ast.Name(id=name):
                fi = self._for_index_by_id[id(node)]
                active = f'{_FOR_PREFIX}{fi}_active'
                it_field = f'{_FOR_PREFIX}{fi}_it'
                loop_head = self._alloc_state()
                after_loop = self._alloc_state()
                self._for_continue_stack.append(loop_head)
                self._for_recv_stack.append(None)
                self._gen_break_target_stack.append(after_loop)
                else_flag = self._loop_else_flag(node)
                self.tr._loop_stack.append(_LoopFrame(else_flag))
                try:
                    self._set_state(loop_head)
                    self.tr.write_line('continue;')
                    self._close_case_block()
                    self._open_case_block(loop_head)
                    self._state = loop_head
                    src = self.tr.visit(node.iter)
                    sep = self.tr._member_access(src)
                    iter_expr = f'({src}){sep}__aiter__()'
                    with self.tr._use_block(f'if (!this->{active})'):
                        if self._for_it_field_uses_assign(it_field):
                            self.tr.write_line(f'this->{it_field}.copyFrom({iter_expr});')
                        else:
                            self.tr.write_line(f'this->{it_field} = std::move({iter_expr});')
                        self.tr.write_line(f'this->{active} = true;')
                    res = _temp_name('afen')
                    self.tr.write_line(f'auto {res} = this->{it_field}.__anext__();')
                    with self.tr._use_block(f'if ({iter_result_done_cpp(res)})'):
                        self.tr.write_line(f'this->{active} = false;')
                        self._set_state(after_loop)
                        self.tr.write_line('continue;')
                    val = iter_result_value_cpp(res)
                    gname = _field_name(name)
                    if self.tr.class_info and gname in self.tr.class_info.fields:
                        self.tr.write_line(f'this->{gname} = {val};')
                    else:
                        self.tr.write_line(f'auto {name} = {val};')
                    self._emit_stmts(node.body)
                    self._emit_loop_body_tail(loop_head, self._for_recv_stack)
                    self._close_case_block()
                    self._open_case_block(after_loop)
                    self._state = after_loop
                    if else_flag is not None:
                        self._emit_loop_else_stmts(node, else_flag)
                    self._emit_for_after_loop_tail_jump(node)
                finally:
                    self.tr._loop_stack.pop()
                    self._for_continue_stack.pop()
                    self._for_recv_stack.pop()
                    self._gen_break_target_stack.pop()
            case _:
                raise NotImplementedError('async for suspend 目标仅支持简单变量名')

    def _emit_for_range(self, node: ast.For) -> None:
        from ..emit.loops_emit import emit_native_range_loop
        match (node.target, node.iter.args):
            case [ast.Name(id=name), [stop]]:
                start, step = ('0', '1')
                stop_v = self.tr.visit(stop)
            case [ast.Name(id=name), [start, stop]]:
                start, step = (self.tr.visit(start), '1')
                stop_v = self.tr.visit(stop)
            case [ast.Name(id=name), [start, stop, step]]:
                start, step = (self.tr.visit(start), self.tr.visit(step))
                stop_v = self.tr.visit(stop)
            case _:
                raise NotImplementedError('generator for-range')
        gname = _field_name(name)
        if self.tr.class_info and gname in self.tr.class_info.fields:
            loop_var = f'this->{gname}'
            redeclare = False
        else:
            loop_var = name
            redeclare = True
        after = self._alloc_state()
        with self._use_gen_loop_else(node):
            self._native_for_depth += 1
            try:
                emit_native_range_loop(self.tr, loop_var, start, stop_v, step, lambda: self._emit_stmts(node.body), redeclare=redeclare)
            finally:
                self._native_for_depth -= 1
        self._set_state(after)
        self.tr.write_line('continue;')
        self._close_case_block()
        self._open_case = None
        self._state = after

    def _for_it_field_uses_assign(self, it_field: str) -> bool:
        return _iter_field_uses_copy_from(it_field, self._class_info)

    def _emit_for_range_suspend(self, node: ast.For) -> None:
        """``for i in range(...)`` 且循环体含 ``yield``：分态（条件 / 递增 / ``continue``）。"""
        from ..emit.loops_emit import cpp_range_loop_cond, range_step_is_negative
        from ..translator import _LoopFrame, temp_name
        match (node.target, node.iter.args):
            case [ast.Name(id=name), [stop]]:
                start, step = ('0', '1')
                stop_v = self.tr.visit(stop)
            case [ast.Name(id=name), [start, stop]]:
                start, step = (self.tr.visit(start), '1')
                stop_v = self.tr.visit(stop)
            case [ast.Name(id=name), [start, stop, step]]:
                start, step = (self.tr.visit(start), self.tr.visit(step))
                stop_v = self.tr.visit(stop)
            case _:
                raise NotImplementedError('generator for-range suspend')
        gname = _field_name(name)
        loop_head = self._alloc_state()
        inc_state = self._alloc_state()
        after_loop = self._alloc_state()
        self._for_continue_stack.append(inc_state)
        self._for_recv_stack.append(None)
        self._gen_break_target_stack.append(after_loop)
        else_flag = self._loop_else_flag(node)
        self.tr._loop_stack.append(_LoopFrame(else_flag))
        try:
            if self.tr.class_info and gname in self.tr.class_info.fields:
                self.tr.write_line(f'this->{gname} = ({start});')
                loop_var = f'this->{gname}'
            else:
                self.tr.write_line(f'{name} = ({start});')
                loop_var = name
            neg_flag: str | None = None
            if range_step_is_negative(step) is None:
                neg_flag = temp_name('rng_neg')
                self.tr.write_line(f'PyBool {neg_flag} = (({step}) < 0);')
            self._set_state(loop_head)
            self.tr.write_line('continue;')
            self._close_case_block()
            self._open_case_block(loop_head)
            self._state = loop_head
            cond = cpp_range_loop_cond(loop_var, stop_v, step, neg_step_flag=neg_flag)
            with self.tr._use_block(f'if (!({cond}))'):
                self._set_state(after_loop)
                self.tr.write_line('continue;')
            self._emit_stmts(node.body)
            self._emit_loop_body_tail(inc_state, self._for_recv_stack)
            self._close_case_block()
            self._open_case_block(inc_state)
            self._state = inc_state
            self.tr.write_line(f'{loop_var} += {step};')
            self._set_state(loop_head)
            self.tr.write_line('continue;')
            self._close_case_block()
            self._open_case_block(after_loop)
            self._state = after_loop
            if else_flag is not None:
                self._emit_loop_else_stmts(node, else_flag)
            self._emit_for_after_loop_tail_jump(node)
        finally:
            self.tr._loop_stack.pop()
            self._for_continue_stack.pop()
            self._for_recv_stack.pop()
            self._gen_break_target_stack.pop()

    def _emit_for_iter_suspend(self, node: ast.For) -> None:
        """``for x in it`` 且循环体含 ``yield``：持久化迭代器 + 分态续推。"""
        from ..emit.loops_emit import _iterable_cpp_type, _materialize_for_iterable
        from ..translator import _LoopFrame
        match node.target:
            case ast.Name(id=name):
                fi = self._for_index_by_id[id(node)]
                active = f'{_FOR_PREFIX}{fi}_active'
                it_field = f'{_FOR_PREFIX}{fi}_it'
                loop_head = self._alloc_state()
                after_loop = self._alloc_state()
                self._for_continue_stack.append(loop_head)
                self._for_recv_stack.append(None)
                self._gen_break_target_stack.append(after_loop)
                else_flag = self._loop_else_flag(node)
                self.tr._loop_stack.append(_LoopFrame(else_flag))
                try:
                    self._set_state(loop_head)
                    self.tr.write_line('continue;')
                    self._close_case_block()
                    self._open_case_block(loop_head)
                    self._state = loop_head
                    src, _ = _materialize_for_iterable(self.tr, node.iter)
                    sep = self.tr._member_access(src)
                    seq_field = f'{_FOR_PREFIX}{fi}_seq'
                    has_seq = self._class_info is not None and seq_field in self._class_info.fields
                    with self.tr._use_block(f'if (!this->{active})'):
                        if has_seq:
                            iter_ty = _iterable_cpp_type(self.tr, node.iter) or ''
                            seq_ty = self.tr._field_storage(seq_field) if self._class_info is not None else ''
                            if iter_ty.endswith(GENERATOR_SUFFIX) and is_list_type(seq_ty):
                                elem = list_elem_type(seq_ty) or 'auto'
                                self.tr.write_line(f'this->{seq_field} = PyList<{elem}>();')
                                it_tmp = _temp_name('gdi')
                                self.tr.write_line(f'auto& {it_tmp} = ({src}).__iter__();')
                                with self.tr._use_block('while (true)'):
                                    res_d = _temp_name('gdn')
                                    self.tr.write_line(f'auto {res_d} = {it_tmp}.__next__();')
                                    self.tr.write_line(f'if ({iter_result_done_cpp(res_d)}) break;')
                                    self.tr.write_line(f'this->{seq_field}.append({iter_result_value_cpp(res_d)});')
                                iter_expr = f'this->{seq_field}{sep}__iter__()'
                            else:
                                self.tr.write_line(f'this->{seq_field} = ({src});')
                                iter_expr = f'this->{seq_field}{sep}__iter__()'
                        else:
                            iter_expr = f'({src}){sep}__iter__()'
                        if self._for_it_field_uses_assign(it_field):
                            self.tr.write_line(f'this->{it_field}.copyFrom({iter_expr});')
                        else:
                            self.tr.write_line(f'this->{it_field} = std::move({iter_expr});')
                        self.tr.write_line(f'this->{active} = true;')
                    res = _temp_name('fen')
                    self.tr.write_line(f'auto {res} = this->{it_field}.__next__();')
                    with self.tr._use_block(f'if ({iter_result_done_cpp(res)})'):
                        self.tr.write_line(f'this->{active} = false;')
                        self._set_state(after_loop)
                        self.tr.write_line('continue;')
                    val = iter_result_value_cpp(res)
                    gname = _field_name(name)
                    if self.tr.class_info and gname in self.tr.class_info.fields:
                        self.tr.write_line(f'this->{gname} = {val};')
                    else:
                        self.tr.write_line(f'auto {name} = {val};')
                    self._emit_stmts(node.body)
                    self._emit_loop_body_tail(loop_head, self._for_recv_stack)
                    self._close_case_block()
                    self._open_case_block(after_loop)
                    self._state = after_loop
                    if else_flag is not None:
                        self._emit_loop_else_stmts(node, else_flag)
                    self._emit_for_after_loop_tail_jump(node)
                finally:
                    self.tr._loop_stack.pop()
                    self._for_continue_stack.pop()
                    self._for_recv_stack.pop()
                    self._gen_break_target_stack.pop()
            case _:
                raise NotImplementedError('generator for-loop suspend target')

    def _emit_for_iter(self, node: ast.For) -> None:
        from ..emit.loops_emit import _materialize_for_iterable
        match node.target:
            case ast.Name(id=name):
                it = _temp_name('it')
                iter_cpp, _ = _materialize_for_iterable(self.tr, node.iter)
                sep = self.tr._member_access(iter_cpp)
                self.tr.write_line(f'auto& {it} = {iter_cpp}{sep}__iter__();')
                res = _temp_name('en')
                with self._use_gen_loop_else(node):
                    self._native_for_depth += 1
                    try:
                        with self.tr._use_block('while (true)'):
                            self.tr.write_line(f'auto {res} = {it}.__next__();')
                            self.tr.write_line(f'if ({iter_result_done_cpp(res)}) break;')
                            self.tr.write_line(f'auto {name} = {iter_result_value_cpp(res)};')
                            gname = _field_name(name)
                            if self.tr.class_info and gname in self.tr.class_info.fields:
                                self.tr.write_line(f'this->{gname} = {name};')
                            self._emit_stmts(node.body)
                    finally:
                        self._native_for_depth -= 1
                nxt = self._alloc_state()
                self._set_state(nxt)
                self.tr.write_line('continue;')
                self._close_case_block()
                self._open_case = None
                self._state = nxt
            case _:
                raise NotImplementedError('generator for-loop target')

def emit_generator_next(tr: Translator, body: list[ast.stmt], *, class_info: ClassInfo | None=None) -> None:
    emitter = GeneratorSwitchEmitter(tr, class_info=class_info)
    tr._active_generator_emitter = emitter
    try:
        emitter.emit(body)
    finally:
        tr._active_generator_emitter = None
