"""``UIFlowMixin``：译期 ``iter_methods`` + 方法签名反射 → ``FlowNodeCatalog``。"""
from ...builtins import *
from ..app import UIApp
from ..window import UIWindow
from .builtins import register_flow_builtins
from .canvas import UIFlowCanvas
from .catalog import FlowNodeCatalog, FlowPinSpec
from .meta import FlowEventMeta, FlowNodeMeta, FlowPureMeta
from .model import FlowGraph, FlowNodeKind, FlowPinKind
from .runtime import FlowRuntime
from .shell import UIFlowShell


@mixin
class UIFlowMixin:
  _flow_canvas: UIFlowCanvas = new()
  _flow_shell: UIFlowShell = new()
  _flow_catalog: FlowNodeCatalog = new()
  _flow_catalog_ready: bool = False
  _flow_runtime: FlowRuntime = new()
  _flow_win: UIWindow = new()

  def _flow_pin_exec_in(self) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = "execute"
    p.kind = FlowPinKind.ExecIn
    return p

  def _flow_pin_exec_out(self) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = "then"
    p.kind = FlowPinKind.ExecOut
    return p

  def _flow_pin_data_in(self, name: str, type_id: str) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = name
    p.kind = FlowPinKind.DataIn
    p.type_id = type_id
    return p

  def _flow_pin_data_out(self, name: str, type_id: str) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = name
    p.kind = FlowPinKind.DataOut
    p.type_id = type_id
    return p

  def _register_flow_node(
    self,
    method: str,
    meta_title: str,
    meta_category: str,
    node_kind: FlowNodeKind,
    pins: list[FlowPinSpec, 0],
  ) -> None:
    title: str = meta_title
    if not title:
      title = method
    category: str = meta_category
    if not category:
      category = Self.__name__
    kind_id: str = Self.__name__ + "." + method
    self._flow_catalog.register(kind_id, title, category, node_kind, method, pins)

  def _ensure_flow_catalog(self) -> None:
    if self._flow_catalog_ready:
      return
    self._flow_catalog.clear()
    for method in Self.iter_methods[FlowNodeMeta](mro=True):
      if Self.get_method_annotation[FlowNodeMeta](method) is None or not Self.get_method_annotation[FlowNodeMeta](method).hidden:
        title: str = ""
        category: str = ""
        if Self.get_method_annotation[FlowNodeMeta](method) is not None:
          title = Self.get_method_annotation[FlowNodeMeta](method).title
          category = Self.get_method_annotation[FlowNodeMeta](method).category
        pins: list[FlowPinSpec, 0] = []
        pins.append(self._flow_pin_exec_in())
        pins.append(self._flow_pin_exec_out())
        for param in Self.iter_method_params(method):
          type_id: str = Self.get_param_type(method, param)
          pins.append(self._flow_pin_data_in(param, type_id))
        return_type = Self.get_return_type(method)
        if return_type is not None:
          pins.append(self._flow_pin_data_out("Return Value", return_type))
        self._register_flow_node(method, title, category, FlowNodeKind.Callable, pins)
    for method in Self.iter_methods[FlowPureMeta](mro=True):
      if Self.get_method_annotation[FlowPureMeta](method) is None or not Self.get_method_annotation[FlowPureMeta](method).hidden:
        title: str = ""
        category: str = ""
        if Self.get_method_annotation[FlowPureMeta](method) is not None:
          title = Self.get_method_annotation[FlowPureMeta](method).title
          category = Self.get_method_annotation[FlowPureMeta](method).category
        pins: list[FlowPinSpec, 0] = []
        for param in Self.iter_method_params(method):
          type_id: str = Self.get_param_type(method, param)
          pins.append(self._flow_pin_data_in(param, type_id))
        return_type = Self.get_return_type(method)
        if return_type is not None:
          pins.append(self._flow_pin_data_out("Return Value", return_type))
        self._register_flow_node(method, title, category, FlowNodeKind.Pure, pins)
    for method in Self.iter_methods[FlowEventMeta](mro=True):
      if Self.get_method_annotation[FlowEventMeta](method) is None or not Self.get_method_annotation[FlowEventMeta](method).hidden:
        title: str = ""
        category: str = "Events"
        if Self.get_method_annotation[FlowEventMeta](method) is not None:
          title = Self.get_method_annotation[FlowEventMeta](method).title
          if Self.get_method_annotation[FlowEventMeta](method).category:
            category = Self.get_method_annotation[FlowEventMeta](method).category
        pins: list[FlowPinSpec, 0] = []
        pins.append(self._flow_pin_exec_out())
        self._register_flow_node(method, title, category, FlowNodeKind.Event, pins)
    register_flow_builtins(self._flow_catalog)
    self._flow_catalog_ready = True

  def flow_invoke_callable(
    self,
    method: str,
    graph: FlowGraph @ref,
    node_id: int,
    rt: FlowRuntime @ref,
  ) -> None:
    for m in Self.iter_methods[FlowNodeMeta](mro=True):
      for param in Self.iter_method_params(m):
        if method == m:
          getattr(self, m)(rt.eval_data_pin(graph, self._flow_catalog, self, node_id, param))

  def flow_invoke_pure(self, method: str) -> int:
    for m in Self.iter_methods[FlowPureMeta](mro=True):
      if method == m:
        return getattr(self, m)()
    return 0

  def _wire_flow_shell(self) -> None:
    self._flow_shell.catalog = self._flow_catalog
    self._flow_canvas.catalog = self._flow_catalog
    self._flow_shell.run_play += self.on_flow_run
    self._flow_shell.run_play_selected += self.on_flow_run_from_selected
    self._flow_shell.run_stop += self.on_flow_stop

  def draw_flow(self, win: UIWindow @ref) -> None:
    self._ensure_flow_catalog()
    self._flow_win = win
    self._wire_flow_shell()
    self._flow_shell.attach(win, self._flow_canvas)
    self._flow_shell.menu.set_run_enabled(True, True, True)

  def on_flow_ready(self) -> None:
    pass

  def on_flow_run(self) -> None:
    self._flow_runtime.run_all(self._flow_canvas.graph, self._flow_catalog, self)

  def on_flow_run_from_selected(self) -> None:
    nid: int = self._flow_canvas.selected_node
    if nid < 0:
      return
    self._flow_runtime.run_from_selected(self._flow_canvas.graph, self._flow_catalog, self, nid)

  def on_flow_stop(self) -> None:
    self._flow_runtime.stop()

  def create_flow(self, title: str = "", width: int = -1, height: int = -1) -> UIWindow:
    self._flow_win = new()
    if not UIApp.is_available():
      return self._flow_win
    self._ensure_flow_catalog()
    self._wire_flow_shell()
    self._flow_win.title = title
    if not self._flow_win.title:
      self._flow_win.title = Self.__name__
    self._flow_win.show(width, height)
    self.draw_flow(self._flow_win)
    if width < 0 or height < 0:
      self._flow_win.resize(width, height)
    self.on_flow_ready()
    return self._flow_win

  def show_flow(self, title: str = "", width: int = 1280, height: int = 720) -> int:
    if not UIApp.is_available():
      return 1
    win: UIWindow = self.create_flow(title, width, height)
    return UIApp.run()
