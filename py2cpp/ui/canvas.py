"""通用画布：``ctx.draw_*`` 录命令；``commit`` 纯 Python 分发 + GDI/GDI+ 叶子；pan/zoom。"""
from ..builtins import *
from .widget import UIWidget
from .window import UIWindow


@enum
class DrawCmdKind:
  FillRect = 0
  StrokeRect = 1
  DrawLine = 2
  DrawBezier = 3
  DrawText = 4
  FillEllipse = 5
  FillRoundRect = 6
  StrokeRoundRect = 7
  FillRectInRoundClip = 8


@copyable
class DrawCmd:
  kind: DrawCmdKind = DrawCmdKind.FillRect
  x: int = 0
  y: int = 0
  w: int = 0
  h: int = 0
  x2: int = 0
  y2: int = 0
  r: int = 0
  g: int = 0
  b: int = 0
  pen_w: int = 1
  radius: int = 0
  text: str = ""
  font_name: str = "Segoe UI"
  font_size: int = 11
  font_bold: bool = False
  text_align: int = 0


@copyable
class UICanvasFont:
  name: str = "Segoe UI"
  size: int = 11
  bold: bool = False


# ``draw_text`` / ``DrawCmd.text_align``
TEXT_ALIGN_LEFT: int = 0
TEXT_ALIGN_RIGHT: int = 1
TEXT_ALIGN_CENTER: int = 2


def _bezier_controls(x1: int, y1: int, x2: int, y2: int) -> (int, int, int, int):
  """水平 cubic 控制点（与旧 ``+canvas.inl`` 几何一致）。"""
  dx: int = x2 - x1
  if dx < 0:
    dx = -dx
  if dx < 40:
    dx = 40
  cx1: int = x1 + dx // 2
  cx2: int = x2 - dx // 2
  return cx1, y1, cx2, y2


@copyable
class UIPaintContext:
  width: int = 0
  height: int = 0
  zoom: float64 = 1.0
  font: UICanvasFont = new()
  _dc: int64 = 0
  _cmds: list[DrawCmd, 0] = []

  def begin_frame(
    self,
    dc: int64,
    width: int,
    height: int,
    font: UICanvasFont,
    zoom: float64 = 1.0,
  ) -> None:
    self._dc = dc
    self.width = width
    self.height = height
    self.font = font
    self.zoom = zoom
    for i in range(len(self._cmds) - 1, -1, -1):
      self._cmds.pop(i)

  def cmd_count(self) -> int:
    return len(self._cmds)

  def scaled_font_size(self) -> int:
    sz: int = int(float64(self.font.size) * self.zoom)
    if sz < 1:
      sz = 1
    return sz

  def _push_color(self, cmd: DrawCmd @ref, color: (int, int, int)) -> None:
    cmd.r = color[0]
    cmd.g = color[1]
    cmd.b = color[2]

  def _push_font(self, cmd: DrawCmd @ref) -> None:
    cmd.font_name = self.font.name
    cmd.font_size = self.scaled_font_size()
    cmd.font_bold = self.font.bold

  def fill_rect(self, x: int, y: int, w: int, h: int, color: (int, int, int)) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.FillRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def stroke_rect(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    color: (int, int, int),
    width: int = 1,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.StrokeRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.pen_w = width
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def draw_line(
    self,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: (int, int, int),
    width: int = 1,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.DrawLine
    cmd.x = x1
    cmd.y = y1
    cmd.x2 = x2
    cmd.y2 = y2
    cmd.pen_w = width
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def draw_bezier(
    self,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: (int, int, int),
    width: int = 2,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.DrawBezier
    cmd.x = x1
    cmd.y = y1
    cmd.x2 = x2
    cmd.y2 = y2
    cmd.pen_w = width
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def draw_text(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    color: (int, int, int),
    align: int = 0,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.DrawText
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.text = text
    cmd.text_align = align
    self._push_color(cmd, color)
    self._push_font(cmd)
    self._cmds.append(cmd)

  def fill_ellipse(self, x1: int, y1: int, x2: int, y2: int, color: (int, int, int)) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.FillEllipse
    cmd.x = x1
    cmd.y = y1
    cmd.x2 = x2
    cmd.y2 = y2
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def fill_round_rect(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    color: (int, int, int),
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.FillRoundRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.radius = radius
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def stroke_round_rect(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    color: (int, int, int),
    width: int = 1,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.StrokeRoundRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.radius = radius
    cmd.pen_w = width
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  def fill_rect_in_round_clip(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    round_w: int,
    round_h: int,
    radius: int,
    color: (int, int, int),
  ) -> None:
    """在 ``(x,y,round_w,round_h)`` 圆角区域内填充 ``(x,y,w,h)``（节点标题栏）。"""
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdKind.FillRectInRoundClip
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.x2 = round_w
    cmd.y2 = round_h
    cmd.radius = radius
    self._push_color(cmd, color)
    self._cmds.append(cmd)

  @native
  def _gdi_fill_rect(
    self, dc: int64, x: int, y: int, w: int, h: int, r: int, g: int, b: int,
  ) -> None:
    ...

  @native
  def _gdi_stroke_rect(
    self, dc: int64, x: int, y: int, w: int, h: int, r: int, g: int, b: int, pen_w: int,
  ) -> None:
    ...

  @native
  def _gdi_draw_line(
    self,
    dc: int64,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    r: int,
    g: int,
    b: int,
    pen_w: int,
  ) -> None:
    ...

  @native
  def _gdi_draw_bezier(
    self,
    dc: int64,
    x1: int,
    y1: int,
    cx1: int,
    cy1: int,
    cx2: int,
    cy2: int,
    x2: int,
    y2: int,
    r: int,
    g: int,
    b: int,
    pen_w: int,
  ) -> None:
    ...

  @native
  def _gdi_draw_text(
    self,
    dc: int64,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    r: int,
    g: int,
    b: int,
    font_name: str,
    font_size: int,
    font_bold: bool,
    text_align: int,
  ) -> None:
    ...

  @native
  def _gdi_fill_ellipse(
    self, dc: int64, x1: int, y1: int, x2: int, y2: int, r: int, g: int, b: int,
  ) -> None:
    ...

  @native
  def _gdi_fill_round_rect(
    self,
    dc: int64,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    r: int,
    g: int,
    b: int,
  ) -> None:
    ...

  @native
  def _gdi_stroke_round_rect(
    self,
    dc: int64,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    r: int,
    g: int,
    b: int,
    pen_w: int,
  ) -> None:
    ...

  @native
  def _gdi_fill_rect_in_round_clip(
    self,
    dc: int64,
    x: int,
    y: int,
    w: int,
    h: int,
    round_w: int,
    round_h: int,
    radius: int,
    r: int,
    g: int,
    b: int,
  ) -> None:
    ...

  def commit(self) -> None:
    """分发 ``_cmds`` 到 GDI/GDI+ 叶子（``dc==0`` 时 no-op，供单测录命令）。"""
    dc: int64 = self._dc
    if dc == 0:
      return
    n: int = len(self._cmds)
    for i in range(n):
      cmd: DrawCmd = self._cmds[i]
      match cmd.kind:
        case DrawCmdKind.FillRect:
          self._gdi_fill_rect(dc, cmd.x, cmd.y, cmd.w, cmd.h, cmd.r, cmd.g, cmd.b)
        case DrawCmdKind.StrokeRect:
          self._gdi_stroke_rect(
            dc, cmd.x, cmd.y, cmd.w, cmd.h, cmd.r, cmd.g, cmd.b, cmd.pen_w,
          )
        case DrawCmdKind.DrawLine:
          self._gdi_draw_line(
            dc, cmd.x, cmd.y, cmd.x2, cmd.y2, cmd.r, cmd.g, cmd.b, cmd.pen_w,
          )
        case DrawCmdKind.DrawBezier:
          cx1, cy1, cx2, cy2 = _bezier_controls(cmd.x, cmd.y, cmd.x2, cmd.y2)
          self._gdi_draw_bezier(
            dc,
            cmd.x,
            cmd.y,
            cx1,
            cy1,
            cx2,
            cy2,
            cmd.x2,
            cmd.y2,
            cmd.r,
            cmd.g,
            cmd.b,
            cmd.pen_w,
          )
        case DrawCmdKind.DrawText:
          self._gdi_draw_text(
            dc,
            cmd.x,
            cmd.y,
            cmd.w,
            cmd.h,
            cmd.text,
            cmd.r,
            cmd.g,
            cmd.b,
            cmd.font_name,
            cmd.font_size,
            cmd.font_bold,
            cmd.text_align,
          )
        case DrawCmdKind.FillEllipse:
          self._gdi_fill_ellipse(
            dc, cmd.x, cmd.y, cmd.x2, cmd.y2, cmd.r, cmd.g, cmd.b,
          )
        case DrawCmdKind.FillRoundRect:
          self._gdi_fill_round_rect(
            dc, cmd.x, cmd.y, cmd.w, cmd.h, cmd.radius, cmd.r, cmd.g, cmd.b,
          )
        case DrawCmdKind.StrokeRoundRect:
          self._gdi_stroke_round_rect(
            dc,
            cmd.x,
            cmd.y,
            cmd.w,
            cmd.h,
            cmd.radius,
            cmd.r,
            cmd.g,
            cmd.b,
            cmd.pen_w,
          )
        case DrawCmdKind.FillRectInRoundClip:
          self._gdi_fill_rect_in_round_clip(
            dc,
            cmd.x,
            cmd.y,
            cmd.w,
            cmd.h,
            cmd.x2,
            cmd.y2,
            cmd.radius,
            cmd.r,
            cmd.g,
            cmd.b,
          )
        case _:
          pass


@dataclass(eq=False, repr=False)
class UICanvas(UIWidget):
  pan_x: float64 = 0.0
  pan_y: float64 = 0.0
  zoom: float64 = 1.0
  zoom_min: float64 = 0.25
  zoom_max: float64 = 2.0
  font: UICanvasFont = new()
  _pctx: UIPaintContext = new()

  @native
  def _win_parent_client_size(self, parent: int64) -> (int, int):
    """父窗口客户区宽高。"""
    ...

  @native
  def _win_mount_child(self, parent: int64, x: int, y: int, w: int, h: int) -> None:
    """创建/重建画布子 HWND 并挂到 ``parent``。"""
    ...

  @native
  def _win_client_size(self) -> (int, int):
    """本控件客户区宽高；未 mount 时 ``(0,0)``。"""
    ...

  def mount(self, win: UIWindow @ref, x: int = 0, y: int = 0, w: int = -1, h: int = -1) -> None:
    """在 ``win`` 客户区 ``(x,y,w,h)`` 创建画布子窗口；``w``/``h`` 为 ``-1`` 时用剩余区域。"""
    parent: int64 = win.handle
    if parent == 0:
      return
    ww: int = w
    wh: int = h
    if ww < 0 or wh < 0:
      cw, ch = self._win_parent_client_size(parent)
      if ww < 0:
        ww = cw - x
      if wh < 0:
        wh = ch - y
    if ww < 1:
      ww = 1
    if wh < 1:
      wh = 1
    self._win_mount_child(parent, x, y, ww, wh)

  @native
  def set_bounds(self, x: int, y: int, w: int, h: int) -> None:
    """``MoveWindow`` 调整已 mount 的子窗口。"""
    ...

  @native
  def client_from_screen(self, scr_x: int, scr_y: int) -> (int, int):
    """屏幕坐标 → 本控件客户区坐标。"""
    ...

  def contains_screen_point(self, scr_x: int, scr_y: int) -> bool:
    if self.handle == 0:
      return False
    cx, cy = self.client_from_screen(scr_x, scr_y)
    cw, ch = self._win_client_size()
    if cx < 0 or cy < 0:
      return False
    if cx >= cw or cy >= ch:
      return False
    return True

  @native
  def invalidate(self) -> None:
    """请求重绘。"""
    ...

  def world_to_screen(self, wx: float64, wy: float64) -> (float64, float64):
    sx: float64 = (wx + self.pan_x) * self.zoom
    sy: float64 = (wy + self.pan_y) * self.zoom
    return sx, sy

  def screen_to_world(self, sx: float64, sy: float64) -> (float64, float64):
    wx: float64 = sx / self.zoom - self.pan_x
    wy: float64 = sy / self.zoom - self.pan_y
    return wx, wy

  def screen_to_world_at(self, sx: float64, sy: float64, zoom: float64) -> (float64, float64):
    wx: float64 = sx / zoom - self.pan_x
    wy: float64 = sy / zoom - self.pan_y
    return wx, wy

  def paint_frame(self, dc: int64, width: int, height: int) -> None:
    self._pctx.begin_frame(dc, width, height, self.font, self.zoom)
    self.on_paint(self._pctx)
    self._pctx.commit()

  @virtual
  def on_paint(self, ctx: UIPaintContext @ref) -> None:
    pass

  @virtual
  def on_pointer_down(self, btn: int, sx: int, sy: int) -> None:
    pass

  @virtual
  def on_pointer_move(self, btn: int, sx: int, sy: int) -> None:
    pass

  @virtual
  def on_pointer_up(self, btn: int, sx: int, sy: int) -> None:
    pass

  @virtual
  def on_key(self, key: int) -> None:
    pass

  @virtual
  def on_wheel(self, delta: int, sx: int, sy: int) -> None:
    if delta == 0:
      return
    old_zoom: float64 = self.zoom
    step: float64 = 0.1
    if delta > 0:
      self.zoom += step
    else:
      self.zoom -= step
    if self.zoom < self.zoom_min:
      self.zoom = self.zoom_min
    if self.zoom > self.zoom_max:
      self.zoom = self.zoom_max
    if self.zoom == old_zoom:
      return
    wx, wy = self.screen_to_world_at(float64(sx), float64(sy), old_zoom)
    self.pan_x = float64(sx) / self.zoom - wx
    self.pan_y = float64(sy) / self.zoom - wy
    self.invalidate()
