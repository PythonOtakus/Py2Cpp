"""Flow 图运行时：Event 入口、Exec 链、Pure 求值、Branch/ForLoop。"""
from ...builtins import *
from .catalog import FlowNodeCatalog
from .model import FlowGraph, FlowNodeKind, FlowPinKind


@dataclass
class FlowRuntime:
  cancelled: bool = False
  _pure_cache_node: list[int, 0] @optional = []
  _pure_cache_val: list[int, 0] @optional = []

  def reset(self) -> None:
    self.cancelled = False
    self._pure_cache_node.clear()
    self._pure_cache_val.clear()

  def stop(self) -> None:
    self.cancelled = True

  def _cache_pure(self, node_id: int, val: int) -> None:
    self._pure_cache_node.append(node_id)
    self._pure_cache_val.append(val)

  def _cached_pure(self, node_id: int) -> int:
    i: int = 0
    for nid in self._pure_cache_node:
      if nid == node_id:
        return self._pure_cache_val[i]
      i += 1
    return 0

  def _has_pure_cache(self, node_id: int) -> bool:
    for nid in self._pure_cache_node:
      if nid == node_id:
        return True
    return False

  def eval_data_pin[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    node_id: int,
    pin_name: str,
  ) -> int:
    pin_id: int = graph.find_pin_on_node(node_id, pin_name, FlowPinKind.DataIn)
    if pin_id < 0:
      return 0
    src: int = graph.data_source(pin_id)
    if src < 0:
      return 0
    return self._eval_data_out(graph, catalog, host, src)

  def _eval_data_out[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    out_pin: int,
  ) -> int:
    src_node_id: int = graph.pin_node_id(out_pin)
    if self._has_pure_cache(src_node_id):
      return self._cached_pure(src_node_id)
    node = graph.find_node(src_node_id)
    tpl = catalog.find(node.kind_id)
    if tpl.node_kind != FlowNodeKind.Pure:
      return 0
    val: int = host.flow_invoke_pure(tpl.method_name)
    self._cache_pure(src_node_id, val)
    return val

  def run_all[T](self, graph: FlowGraph @ref, catalog: FlowNodeCatalog @ref, host: T @ref) -> None:
    self.reset()
    for node in graph.nodes:
      tpl = catalog.find(node.kind_id)
      if tpl.node_kind == FlowNodeKind.Event:
        self.run_from_event(graph, catalog, host, node.id)

  def run_from_event[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    event_node_id: int,
  ) -> None:
    self.reset()
    then_pin: int = graph.find_pin_on_node(event_node_id, "then", FlowPinKind.ExecOut)
    if then_pin < 0:
      return
    self._run_from_exec_out(graph, catalog, host, then_pin)

  def run_from_selected[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    node_id: int,
  ) -> None:
    self.reset()
    node = graph.find_node(node_id)
    tpl = catalog.find(node.kind_id)
    if tpl.node_kind == FlowNodeKind.Event:
      self.run_from_event(graph, catalog, host, node_id)
      return
    exec_in: int = graph.find_pin_on_node(node_id, "execute", FlowPinKind.ExecIn)
    if exec_in < 0:
      return
    self._step_exec(graph, catalog, host, exec_in)

  def _run_from_exec_out[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    out_pin: int,
  ) -> None:
    cur: int = out_pin
    while cur >= 0:
      if self.cancelled:
        return
      target: int = graph.exec_target(cur)
      if target < 0:
        return
      cur = self._step_exec(graph, catalog, host, target)

  def _step_exec[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    exec_in_pin: int,
  ) -> int:
    if self.cancelled:
      return -1
    node_id: int = graph.pin_node_id(exec_in_pin)
    node = graph.find_node(node_id)
    tpl = catalog.find(node.kind_id)
    match tpl.node_kind:
      case FlowNodeKind.Callable:
        host.flow_invoke_callable(tpl.method_name, graph, node_id, self)
        return graph.find_pin_on_node(node_id, "then", FlowPinKind.ExecOut)
      case FlowNodeKind.Branch:
        cond: int = self.eval_data_pin(graph, catalog, host, node_id, "condition")
        branch_out: int = -1
        if cond:
          branch_out = graph.find_pin_on_node(node_id, "OnTrue", FlowPinKind.ExecOut)
        else:
          branch_out = graph.find_pin_on_node(node_id, "OnFalse", FlowPinKind.ExecOut)
        self._run_from_exec_out(graph, catalog, host, branch_out)
        return -1
      case FlowNodeKind.ForLoop:
        count: int = self.eval_data_pin(graph, catalog, host, node_id, "count")
        body_out: int = graph.find_pin_on_node(node_id, "LoopBody", FlowPinKind.ExecOut)
        for i in range(count):
          if self.cancelled:
            return -1
          self._run_from_exec_out(graph, catalog, host, body_out)
        return graph.find_pin_on_node(node_id, "Completed", FlowPinKind.ExecOut)
      case _:
        return -1
