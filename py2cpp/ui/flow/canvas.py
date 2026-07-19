"""蓝图画布控件（``UIFlowCanvas``）。"""
from ...builtins import *
from ..canvas import TEXT_ALIGN_LEFT, TEXT_ALIGN_RIGHT, UICanvas, UIPaintContext
from ..events import UIEvent, UIValueChanged
from ..input import ctrl_down, shift_down
from .catalog import FlowNodeCatalog
from .history import FlowGraphHistory
from .layout import (
  NODE_CORNER_RADIUS,
  PIN_LABEL_PAD,
  ROW_HEIGHT,
  TITLE_HEIGHT,
  graph_to_screen,
  hit_test_node,
  hit_test_pin,
  node_height,
  node_screen_width,
  nodes_in_graph_rect,
  pin_graph_pos,
  screen_to_graph,
)
from .model import FlowGraph, FlowNode, FlowPinKind
from .serialize import paste_subgraph, subgraph_to_json
from .style import UIFlowStyle


MARQUEE_MIN_DRAG: int = 4
PASTE_OFFSET: float64 = 24.0


@dataclass(eq=False, repr=False)
class UIFlowCanvas(UICanvas):
  graph: FlowGraph = new()
  catalog: FlowNodeCatalog = new()
  style: UIFlowStyle = new()
  history: FlowGraphHistory = new()
  clipboard_json: str = ""
  selected_node: int = -1
  selected_nodes: list[int, 0] @optional = []
  _wire_active: bool = False
  _wire_x1: float64 = 0.0
  _wire_y1: float64 = 0.0
  _wire_x2: float64 = 0.0
  _wire_y2: float64 = 0.0
  _wire_exec: bool = True
  _drag_pan: bool = False
  _pan_last_sx: float64 = 0.0
  _pan_last_sy: float64 = 0.0
  _drag_node: bool = False
  _drag_node_id: int = -1
  _drag_moved: bool = False
  _drag_last_gx: float64 = 0.0
  _drag_last_gy: float64 = 0.0
  _wire_from_pin: int = -1
  _marquee_active: bool = False
  _marquee_additive: bool = False
  _marquee_sx: int = 0
  _marquee_sy: int = 0
  _marquee_ex: int = 0
  _marquee_ey: int = 0

  graph_changed: UIEvent = new()
  selection_changed: UIValueChanged[int] = new()

  def _is_node_selected(self, node_id: int) -> bool:
    for nid in self.selected_nodes:
      if nid == node_id:
        return True
    return False

  def _set_selection(self, node_ids: list[int, 0]) -> None:
    for i in range(len(self.selected_nodes) - 1, -1, -1):
      self.selected_nodes.pop(i)
    for nid in node_ids:
      self.selected_nodes.append(nid)
    primary: int = -1
    if self.selected_nodes:
      primary = self.selected_nodes[0]
    self.selected_node = primary
    self.selection_changed(primary)

  def _toggle_node_selection(self, node_id: int) -> None:
    found: bool = False
    for i in range(len(self.selected_nodes)):
      if self.selected_nodes[i] == node_id:
        self.selected_nodes.pop(i)
        found = True
        break
    if not found:
      self.selected_nodes.append(node_id)
    primary: int = -1
    if self.selected_nodes:
      primary = self.selected_nodes[0]
    self.selected_node = primary
    self.selection_changed(primary)

  def _has_selection(self) -> bool:
    for _ in self.selected_nodes:
      return True
    return False

  def _record_undo(self) -> None:
    self.history.push(self.graph)

  def select_all_nodes(self) -> None:
    ids: list[int, 0] = []
    for node in self.graph.nodes:
      ids.append(node.id)
    self._set_selection(ids)
    self.invalidate()

  def _clear_selection_state(self) -> None:
    for i in range(len(self.selected_nodes) - 1, -1, -1):
      self.selected_nodes.pop(i)
    self.selected_node = -1
    self.selection_changed(-1)

  def clear_selection(self) -> None:
    self._clear_selection_state()
    self.invalidate()

  def copy_selection_json(self) -> str:
    if not self._has_selection():
      return ""
    return subgraph_to_json(self.graph, self.selected_nodes)

  def copy_to_clipboard(self) -> None:
    self.clipboard_json = self.copy_selection_json()

  def paste_from_clipboard(self) -> None:
    self.paste_json(self.clipboard_json)

  def _merge_selection(self, node_ids: list[int, 0]) -> None:
    for nid in node_ids:
      if not self._is_node_selected(nid):
        self.selected_nodes.append(nid)
    primary: int = -1
    if self.selected_nodes:
      primary = self.selected_nodes[0]
    self.selected_node = primary
    self.selection_changed(primary)

  def cut_selection(self) -> str:
    text: str = self.copy_selection_json()
    empty: str = ""
    if text == empty:
      return empty
    self._record_undo()
    to_remove: list[int, 0] = []
    for nid in self.selected_nodes:
      to_remove.append(nid)
    for nid in to_remove:
      self.graph.remove_node(nid)
    self._clear_selection_state()
    self.graph_changed()
    self.invalidate()
    return text

  def delete_selected(self) -> None:
    if not self._has_selection():
      return
    self._record_undo()
    to_remove: list[int, 0] = []
    for nid in self.selected_nodes:
      to_remove.append(nid)
    for nid in to_remove:
      self.graph.remove_node(nid)
    self._clear_selection_state()
    self.graph_changed()
    self.invalidate()

  def paste_json(self, text: str) -> None:
    empty: str = ""
    if text == empty:
      return
    self._record_undo()
    off: float64 = PASTE_OFFSET
    new_ids: list[int, 0] = paste_subgraph(self.graph, text, off, off)
    self._set_selection(new_ids)
    self.graph_changed()
    self.invalidate()

  def undo_graph(self) -> bool:
    if self.history.undo(self.graph):
      self._clear_selection_state()
      self.graph_changed()
      self.invalidate()
      return True
    return False

  def redo_graph(self) -> bool:
    if self.history.redo(self.graph):
      self._clear_selection_state()
      self.graph_changed()
      self.invalidate()
      return True
    return False

  def _pin_index(self, node: FlowNode @ref, pin_id: int) -> int:
    pi: int = 0
    for p in node.pins:
      if p.id == pin_id:
        return pi
      pi += 1
    return -1

  def _paint_grid(self, ctx: UIPaintContext @ref) -> None:
    minor: int = self.style.grid_minor_step
    major: int = self.style.grid_major_step
    if minor < 4:
      minor = 4
    if major < minor:
      major = minor * 8
    for x in range(0, ctx.width, minor):
      if (x % major) == 0:
        ctx.draw_line(x, 0, x, ctx.height, self.style.grid_major)
      else:
        ctx.draw_line(x, 0, x, ctx.height, self.style.grid_minor)
    for y in range(0, ctx.height, minor):
      if (y % major) == 0:
        ctx.draw_line(0, y, ctx.width, y, self.style.grid_major)
      else:
        ctx.draw_line(0, y, ctx.width, y, self.style.grid_minor)

  def _draw_edges(self, ctx: UIPaintContext @ref) -> None:
    for edge in self.graph.edges:
      src_pin = self.graph.find_pin(edge.from_pin)
      dst_pin = self.graph.find_pin(edge.to_pin)
      src_node = self.graph.find_node(src_pin.node_id)
      dst_node = self.graph.find_node(dst_pin.node_id)
      sidx: int = self._pin_index(src_node, edge.from_pin)
      didx: int = self._pin_index(dst_node, edge.to_pin)
      x1, y1 = pin_graph_pos(src_node, sidx)
      x2, y2 = pin_graph_pos(dst_node, didx)
      sx1, sy1 = graph_to_screen(x1, y1, self.pan_x, self.pan_y, self.zoom)
      sx2, sy2 = graph_to_screen(x2, y2, self.pan_x, self.pan_y, self.zoom)
      if src_pin.kind == FlowPinKind.ExecOut:
        ctx.draw_bezier(int(sx1), int(sy1), int(sx2), int(sy2), self.style.wire_exec)
      else:
        ctx.draw_bezier(int(sx1), int(sy1), int(sx2), int(sy2), self.style.wire_data)
    if self._wire_active:
      wx1, wy1 = graph_to_screen(self._wire_x1, self._wire_y1, self.pan_x, self.pan_y, self.zoom)
      wx2, wy2 = graph_to_screen(self._wire_x2, self._wire_y2, self.pan_x, self.pan_y, self.zoom)
      if self._wire_exec:
        ctx.draw_bezier(int(wx1), int(wy1), int(wx2), int(wy2), self.style.wire_exec)
      else:
        ctx.draw_bezier(int(wx1), int(wy1), int(wx2), int(wy2), self.style.wire_data)

  def _draw_nodes(self, ctx: UIPaintContext @ref) -> None:
    title_h: int = int(float64(TITLE_HEIGHT) * self.zoom)
    if title_h < 1:
      title_h = 1
    row_h: int = int(float64(ROW_HEIGHT) * self.zoom)
    if row_h < 1:
      row_h = 1
    sw: int = node_screen_width(self.zoom)
    corner: int = int(float64(NODE_CORNER_RADIUS) * self.zoom)
    if corner < 2:
      corner = 2
    pad: int = int(float64(PIN_LABEL_PAD) * self.zoom)
    if pad < 4:
      pad = 4
    pin_r: int = int(6.0 * self.zoom)
    if pin_r < 4:
      pin_r = 4
    for node in self.graph.nodes:
      rows: int = len(node.pins)
      if rows < 1:
        rows = 1
      h: int = node_height(rows)
      nsx, nsy = graph_to_screen(node.x, node.y, self.pan_x, self.pan_y, self.zoom)
      ctx.fill_round_rect(
        int(nsx),
        int(nsy),
        sw,
        int(float64(h) * self.zoom),
        corner,
        self.style.node_body,
      )
      ctx.fill_rect_in_round_clip(
        int(nsx),
        int(nsy),
        sw,
        title_h,
        sw,
        int(float64(h) * self.zoom),
        corner,
        self.style.node_title,
      )
      if self._is_node_selected(node.id):
        ctx.stroke_round_rect(
          int(nsx),
          int(nsy),
          sw,
          int(float64(h) * self.zoom),
          corner,
          self.style.node_selected,
          2,
        )
      else:
        ctx.stroke_round_rect(
          int(nsx),
          int(nsy),
          sw,
          int(float64(h) * self.zoom),
          corner,
          self.style.node_border,
          1,
        )
      saved_size: int = ctx.font.size
      ctx.font.size = self.style.title_font_size
      ctx.draw_text(
        int(nsx) + pad,
        int(nsy),
        sw - pad * 2,
        title_h,
        node.title,
        self.style.text_color,
      )
      ctx.font.size = self.style.font_size
      pi: int = 0
      for pin in node.pins:
        px, py = pin_graph_pos(node, pi)
        psx, psy = graph_to_screen(px, py, self.pan_x, self.pan_y, self.zoom)
        if pin.kind in {FlowPinKind.ExecIn, FlowPinKind.ExecOut}:
          ctx.fill_ellipse(
            int(psx) - pin_r,
            int(psy) - pin_r,
            int(psx) + pin_r,
            int(psy) + pin_r,
            self.style.wire_exec,
          )
        else:
          ctx.fill_ellipse(
            int(psx) - pin_r,
            int(psy) - pin_r,
            int(psx) + pin_r,
            int(psy) + pin_r,
            self.style.wire_data,
          )
        if pin.name:
          label_y: int = int(nsy) + title_h + pi * row_h
          label_w: int = sw - pad * 2 - pin_r
          if label_w < 8:
            label_w = 8
          is_out: bool = pin.kind in {FlowPinKind.ExecOut, FlowPinKind.DataOut}
          if is_out:
            ctx.draw_text(
              int(nsx) + pad,
              label_y,
              label_w,
              row_h,
              pin.name,
              self.style.pin_label_color,
              TEXT_ALIGN_RIGHT,
            )
          else:
            ctx.draw_text(
              int(nsx) + pad + pin_r,
              label_y,
              label_w,
              row_h,
              pin.name,
              self.style.pin_label_color,
              TEXT_ALIGN_LEFT,
            )
        pi += 1
      ctx.font.size = saved_size

  @override
  def on_paint(self, ctx: UIPaintContext @ref) -> None:
    ctx.fill_rect(0, 0, ctx.width, ctx.height, self.style.bg_color)
    self._paint_grid(ctx)
    self._draw_edges(ctx)
    self._draw_nodes(ctx)
    if self._marquee_active:
      x1: int = self._marquee_sx
      y1: int = self._marquee_sy
      x2: int = self._marquee_ex
      y2: int = self._marquee_ey
      rx: int = x1
      ry: int = y1
      rw: int = x2 - x1
      rh: int = y2 - y1
      if rw < 0:
        rx = x2
        rw = -rw
      if rh < 0:
        ry = y2
        rh = -rh
      ctx.stroke_rect(rx, ry, rw, rh, self.style.node_selected, 1)

  def _pin_is_output(self, pin_id: int) -> bool:
    pin = self.graph.find_pin(pin_id)
    return pin.kind in {FlowPinKind.ExecOut, FlowPinKind.DataOut}

  def _begin_wire(self, pin_id: int, gx: float64, gy: float64) -> None:
    pin = self.graph.find_pin(pin_id)
    node = self.graph.find_node(pin.node_id)
    self._wire_from_pin = pin_id
    self._wire_active = True
    self._wire_exec = pin.kind == FlowPinKind.ExecOut
    pin_idx: int = self._pin_index(node, pin_id)
    wire_x, wire_y = pin_graph_pos(node, pin_idx)
    self._wire_x1 = wire_x
    self._wire_y1 = wire_y
    self._wire_x2 = gx
    self._wire_y2 = gy

  @override
  def on_pointer_down(self, btn: int, sx: int, sy: int) -> None:
    if btn in {2, 4}:
      self._drag_pan = True
      self._pan_last_sx = float64(sx)
      self._pan_last_sy = float64(sy)
      return
    gx, gy = screen_to_graph(float64(sx), float64(sy), self.pan_x, self.pan_y, self.zoom)
    if btn != 1:
      return
    pin_id: int = hit_test_pin(self.graph, gx, gy)
    if pin_id >= 0 and self._pin_is_output(pin_id):
      self._begin_wire(pin_id, gx, gy)
      self.invalidate()
      return
    node_id: int = hit_test_node(self.graph, gx, gy)
    if node_id >= 0:
      if shift_down():
        self._toggle_node_selection(node_id)
      else:
        ids: list[int, 0] = []
        ids.append(node_id)
        self._set_selection(ids)
      self._drag_node = True
      self._drag_node_id = node_id
      self._drag_moved = False
      self._drag_last_gx = gx
      self._drag_last_gy = gy
      self.invalidate()
      return
    self._marquee_active = True
    self._marquee_additive = shift_down()
    self._marquee_sx = sx
    self._marquee_sy = sy
    self._marquee_ex = sx
    self._marquee_ey = sy
    if not self._marquee_additive:
      self._clear_selection_state()
    self.invalidate()

  @override
  def on_pointer_move(self, btn: int, sx: int, sy: int) -> None:
    if self._drag_pan:
      dx: float64 = float64(sx) - self._pan_last_sx
      dy: float64 = float64(sy) - self._pan_last_sy
      self.pan_x += dx / self.zoom
      self.pan_y += dy / self.zoom
      self._pan_last_sx = float64(sx)
      self._pan_last_sy = float64(sy)
      self.invalidate()
      return
    gx, gy = screen_to_graph(float64(sx), float64(sy), self.pan_x, self.pan_y, self.zoom)
    if self._wire_active:
      self._wire_x2 = gx
      self._wire_y2 = gy
      self.invalidate()
      return
    if self._marquee_active:
      self._marquee_ex = sx
      self._marquee_ey = sy
      self.invalidate()
      return
    if self._drag_node and self._drag_node_id >= 0:
      dx = gx - self._drag_last_gx
      dy = gy - self._drag_last_gy
      if dx != 0.0 or dy != 0.0:
        if not self._drag_moved:
          self._record_undo()
          self._drag_moved = True
        for nid in self.selected_nodes:
          self.graph.move_node(nid, dx, dy)
      self._drag_last_gx = gx
      self._drag_last_gy = gy
      self.invalidate()

  @override
  def on_pointer_up(self, btn: int, sx: int, sy: int) -> None:
    if btn in {2, 4}:
      self._drag_pan = False
      return
    if btn != 1:
      return
    if self._marquee_active:
      self._marquee_active = False
      dx: int = self._marquee_ex - self._marquee_sx
      dy: int = self._marquee_ey - self._marquee_sy
      if dx < 0:
        dx = -dx
      if dy < 0:
        dy = -dy
      if dx < MARQUEE_MIN_DRAG and dy < MARQUEE_MIN_DRAG:
        if not self._marquee_additive:
          self._clear_selection_state()
      else:
        gx1, gy1 = screen_to_graph(float64(self._marquee_sx), float64(self._marquee_sy), self.pan_x, self.pan_y, self.zoom)
        gx2, gy2 = screen_to_graph(float64(self._marquee_ex), float64(self._marquee_ey), self.pan_x, self.pan_y, self.zoom)
        picked: list[int, 0] = nodes_in_graph_rect(self.graph, gx1, gy1, gx2, gy2)
        if self._marquee_additive:
          self._merge_selection(picked)
        else:
          self._set_selection(picked)
      self.invalidate()
      return
    if self._wire_active:
      gx, gy = screen_to_graph(float64(sx), float64(sy), self.pan_x, self.pan_y, self.zoom)
      pin_id = hit_test_pin(self.graph, gx, gy)
      if pin_id >= 0 and self._wire_from_pin >= 0:
        self._record_undo()
        try:
          self.graph.connect(self._wire_from_pin, pin_id)
          self.graph_changed()
        except ValueError:
          pass
      self._wire_active = False
      self._wire_from_pin = -1
      self.invalidate()
      return
    self._drag_node = False
    self._drag_node_id = -1
    self._drag_moved = False

  def add_node_from_kind(self, kind_id: str, gx: float64, gy: float64) -> int:
    self._record_undo()
    tpl = self.catalog.find(kind_id)
    pins = self.catalog.clone_pins(kind_id)
    nid: int = self.graph.add_node(kind_id, tpl.title, gx, gy, pins)
    self.graph_changed()
    return nid

  def cancel_interaction(self) -> None:
    self._wire_active = False
    self._wire_from_pin = -1
    self._drag_pan = False
    self._drag_node = False
    self._drag_node_id = -1
    self._drag_moved = False
    self._marquee_active = False
    self.clear_selection()

  @override
  def on_key(self, key: int) -> None:
    if key == 27:
      self.cancel_interaction()
      return
    if key == 46:
      self.delete_selected()
      return
    if not ctrl_down():
      return
    match key:
      case 90:
        self.undo_graph()
      case 89:
        self.redo_graph()
      case 88:
        self.clipboard_json = self.cut_selection()
      case 67:
        self.copy_to_clipboard()
      case 86:
        self.paste_from_clipboard()
      case 65:
        self.select_all_nodes()
      case _:
        pass
