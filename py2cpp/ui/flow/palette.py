"""节点 palette 侧栏（分组列表 + 拖拽源）。"""
from ...builtins import *
from ..input import cursor_screen_pos
from ..canvas import UICanvas, UIPaintContext
from .canvas import UIFlowCanvas
from .catalog import FlowNodeCatalog, FlowNodeTemplate
from .model import FlowNodeKind
from .style import UIFlowStyle


GROUP_HEADER_H: int = 32
ITEM_ROW_H: int = 36


@copyable
class PaletteGroupView:
  name: str = ""
  collapsed: bool = False
  kind_ids: list[str, 0] = []


@dataclass(eq=False, repr=False)
class UIFlowPalette(UICanvas):
  catalog: FlowNodeCatalog = new()
  _canvas_ptr: int64 @optional = 0
  style: UIFlowStyle = new()
  groups: list[PaletteGroupView, 0] @optional = []
  scroll_y: int = 0
  hover_kind: str = ""
  _drag_kind: str = ""
  _drag_active: bool = False

  def rebuild_groups(self) -> None:
    for i in range(len(self.groups) - 1, -1, -1):
      self.groups.pop(i)
    for cat in self.catalog.categories():
      gv: PaletteGroupView = new()
      gv.name = cat
      gv.collapsed = False
      for tpl in self.catalog.entries_in(cat):
        gv.kind_ids.append(tpl.kind_id)
      self.groups.append(gv)

  def _content_height(self) -> int:
    h: int = 0
    for gv in self.groups:
      h += GROUP_HEADER_H
      if not gv.collapsed:
        h += len(gv.kind_ids) * ITEM_ROW_H
    return h

  def _hit_kind(self, sx: int, sy: int) -> str:
    y: int = -self.scroll_y
    for gv in self.groups:
      header_y: int = y
      y += GROUP_HEADER_H
      if sy >= header_y and sy < header_y + GROUP_HEADER_H:
        return ""
      if not gv.collapsed:
        for kind_id in gv.kind_ids:
          row_y: int = y
          y += ITEM_ROW_H
          if sy >= row_y and sy < row_y + ITEM_ROW_H:
            return kind_id
    return ""

  def _hit_group_header(self, sx: int, sy: int) -> int:
    y: int = -self.scroll_y
    gi: int = 0
    for gv in self.groups:
      header_y: int = y
      y += GROUP_HEADER_H
      if not gv.collapsed:
        y += len(gv.kind_ids) * ITEM_ROW_H
      if sy >= header_y and sy < header_y + GROUP_HEADER_H:
        return gi
      gi += 1
    return -1

  def _kind_dot_color(self, tpl: FlowNodeTemplate @ref) -> (int, int, int):
    match tpl.node_kind:
      case FlowNodeKind.Event:
        return (255, 160, 64)
      case FlowNodeKind.Pure:
        return self.style.wire_data
      case FlowNodeKind.Branch:
        return (200, 120, 255)
      case FlowNodeKind.ForLoop:
        return (120, 200, 255)
      case _:
        return self.style.wire_exec

  @override
  def on_paint(self, ctx: UIPaintContext @ref) -> None:
    # 侧栏不随画布 zoom；字号写在 ctx 上（``self.font`` 为值语义时赋值不可靠）。
    ctx.zoom = 1.0
    ctx.font.size = self.style.palette_font_size
    ctx.fill_rect(0, 0, ctx.width, ctx.height, (28, 28, 30))
    y: int = -self.scroll_y
    dot_pad: int = (ITEM_ROW_H - 10) // 2
    for gv in self.groups:
      header_y: int = y
      y += GROUP_HEADER_H
      ctx.fill_rect(0, header_y, ctx.width, GROUP_HEADER_H, (45, 45, 48))
      mark: str = "v"
      if gv.collapsed:
        mark = ">"
      ctx.draw_text(6, header_y, 20, GROUP_HEADER_H, mark, self.style.text_color)
      ctx.draw_text(28, header_y, ctx.width - 34, GROUP_HEADER_H, gv.name, self.style.text_color)
      if not gv.collapsed:
        for kind_id in gv.kind_ids:
          row_y: int = y
          y += ITEM_ROW_H
          if row_y + ITEM_ROW_H < 0:
            continue
          if row_y > ctx.height:
            break
          bg: (int, int, int) = (35, 35, 38)
          if kind_id == self.hover_kind:
            bg = (55, 55, 60)
          if kind_id == self._drag_kind and self._drag_active:
            bg = (0, 90, 150)
          ctx.fill_rect(0, row_y, ctx.width, ITEM_ROW_H, bg)
          tpl: FlowNodeTemplate = self.catalog.find(kind_id)
          dot = self._kind_dot_color(tpl)
          ctx.fill_ellipse(10, row_y + dot_pad, 20, row_y + dot_pad + 10, dot)
          ctx.draw_text(28, row_y, ctx.width - 34, ITEM_ROW_H, tpl.title, self.style.text_color)

  @override
  def on_wheel(self, delta: int, sx: int, sy: int) -> None:
    if delta == 0:
      return
    step: int = 24
    if delta > 0:
      self.scroll_y -= step
    else:
      self.scroll_y += step
    max_scroll: int = self._content_height() - 100
    if max_scroll < 0:
      max_scroll = 0
    if self.scroll_y < 0:
      self.scroll_y = 0
    if self.scroll_y > max_scroll:
      self.scroll_y = max_scroll
    self.invalidate()

  @override
  def on_pointer_down(self, btn: int, sx: int, sy: int) -> None:
    if btn != 1:
      return
    gi: int = self._hit_group_header(sx, sy)
    if gi >= 0:
      gv: PaletteGroupView = self.groups[gi]
      gv.collapsed = not gv.collapsed
      self.groups[gi] = gv
      self.invalidate()
      return
    kind: str = self._hit_kind(sx, sy)
    if kind:
      self._drag_kind = kind
      self._drag_active = True
      self.invalidate()

  @override
  def on_pointer_move(self, btn: int, sx: int, sy: int) -> None:
    if self._drag_active:
      self.invalidate()
      return
    kind: str = self._hit_kind(sx, sy)
    if kind != self.hover_kind:
      self.hover_kind = kind
      self.invalidate()

  @override
  def on_pointer_up(self, btn: int, sx: int, sy: int) -> None:
    if btn != 1:
      return
    if self._drag_active:
      self._finish_drag()
      return

  @native
  def bind_canvas(self, canvas: UIFlowCanvas @ref) -> None:
    """``attach`` 后绑定已 mount 的画布（值拷贝无法共享 ``handle`` / ``graph``）。"""
    ...

  @native
  def _drop_node_at_screen(self, kind: str, scr_x: int, scr_y: int) -> None:
    """经 ``_canvas_ptr`` 在屏幕坐标处投放节点。"""
    ...

  def _finish_drag(self) -> None:
    kind: str = self._drag_kind
    self._drag_active = False
    self._drag_kind = ""
    self.invalidate()
    if not kind:
      return
    sx: int = cursor_screen_pos()[0]
    sy: int = cursor_screen_pos()[1]
    self._drop_node_at_screen(kind, sx, sy)
