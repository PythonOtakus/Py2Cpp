"""通用画布：``ctx.draw_*`` 录命令；``commit`` 纯 Python 分发 + GDI/GDI+ 叶子；pan/zoom。"""
from ..builtins import *
from .widget import UIWidget
from .window import UIWindow


@enum
class DrawCmdEnum:
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
  kind: DrawCmdEnum = DrawCmdEnum.FillRect
  x: int = 0
  y: int = 0
  w: int = 0
  h: int = 0
  x2: int = 0
  y2: int = 0
  r: int = 0
  g: int = 0
  b: int = 0
  penW: int = 1
  radius: int = 0
  text: str = ""
  fontName: str = "Segoe UI"
  fontSize: int = 11
  fontBold: bool = False
  textAlign: int = 0


@copyable
class UICanvasFont:
  name: str = "Segoe UI"
  size: int = 11
  bold: bool = False


# ``drawText`` / ``DrawCmd.textAlign``
TextAlignLeft: int = 0
TextAlignRight: int = 1
TextAlignCenter: int = 2


def _bezierControls(x1: int, y1: int, x2: int, y2: int) -> (int, int, int, int):
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

  def beginFrame(
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

  def cmdCount(self) -> int:
    return len(self._cmds)

  def scaledFontSize(self) -> int:
    sz: int = int(float64(self.font.size) * self.zoom)
    if sz < 1:
      sz = 1
    return sz

  def _pushColor(self, cmd: DrawCmd @ref, color: (int, int, int)) -> None:
    cmd.r = color[0]
    cmd.g = color[1]
    cmd.b = color[2]

  def _pushFont(self, cmd: DrawCmd @ref) -> None:
    cmd.fontName = self.font.name
    cmd.fontSize = self.scaledFontSize()
    cmd.fontBold = self.font.bold

  def fillRect(self, x: int, y: int, w: int, h: int, color: (int, int, int)) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.FillRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def strokeRect(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    color: (int, int, int),
    width: int = 1,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.StrokeRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.penW = width
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def drawLine(
    self,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: (int, int, int),
    width: int = 1,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.DrawLine
    cmd.x = x1
    cmd.y = y1
    cmd.x2 = x2
    cmd.y2 = y2
    cmd.penW = width
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def drawBezier(
    self,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: (int, int, int),
    width: int = 2,
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.DrawBezier
    cmd.x = x1
    cmd.y = y1
    cmd.x2 = x2
    cmd.y2 = y2
    cmd.penW = width
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def drawText(
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
    cmd.kind = DrawCmdEnum.DrawText
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.text = text
    cmd.textAlign = align
    self._pushColor(cmd, color)
    self._pushFont(cmd)
    self._cmds.append(cmd)

  def fillEllipse(self, x1: int, y1: int, x2: int, y2: int, color: (int, int, int)) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.FillEllipse
    cmd.x = x1
    cmd.y = y1
    cmd.x2 = x2
    cmd.y2 = y2
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def fillRoundRect(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    color: (int, int, int),
  ) -> None:
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.FillRoundRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.radius = radius
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def strokeRoundRect(
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
    cmd.kind = DrawCmdEnum.StrokeRoundRect
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.radius = radius
    cmd.penW = width
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  def fillRectInRoundClip(
    self,
    x: int,
    y: int,
    w: int,
    h: int,
    roundW: int,
    roundH: int,
    radius: int,
    color: (int, int, int),
  ) -> None:
    """在 ``(x,y,roundW,roundH)`` 圆角区域内填充 ``(x,y,w,h)``（节点标题栏）。"""
    cmd: DrawCmd = new()
    cmd.kind = DrawCmdEnum.FillRectInRoundClip
    cmd.x = x
    cmd.y = y
    cmd.w = w
    cmd.h = h
    cmd.x2 = roundW
    cmd.y2 = roundH
    cmd.radius = radius
    self._pushColor(cmd, color)
    self._cmds.append(cmd)

  @native
  def _gdiFillRect(
    self, dc: int64, x: int, y: int, w: int, h: int, r: int, g: int, b: int,
  ) -> None:
    ...

  @native
  def _gdiStrokeRect(
    self, dc: int64, x: int, y: int, w: int, h: int, r: int, g: int, b: int, penW: int,
  ) -> None:
    ...

  @native
  def _gdiDrawLine(
    self,
    dc: int64,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    r: int,
    g: int,
    b: int,
    penW: int,
  ) -> None:
    ...

  @native
  def _gdiDrawBezier(
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
    penW: int,
  ) -> None:
    ...

  @native
  def _gdiDrawText(
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
    fontName: str,
    fontSize: int,
    fontBold: bool,
    textAlign: int,
  ) -> None:
    ...

  @native
  def _gdiFillEllipse(
    self, dc: int64, x1: int, y1: int, x2: int, y2: int, r: int, g: int, b: int,
  ) -> None:
    ...

  @native
  def _gdiFillRoundRect(
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
  def _gdiStrokeRoundRect(
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
    penW: int,
  ) -> None:
    ...

  @native
  def _gdiFillRectInRoundClip(
    self,
    dc: int64,
    x: int,
    y: int,
    w: int,
    h: int,
    roundW: int,
    roundH: int,
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
        case DrawCmdEnum.FillRect:
          self._gdiFillRect(dc, cmd.x, cmd.y, cmd.w, cmd.h, cmd.r, cmd.g, cmd.b)
        case DrawCmdEnum.StrokeRect:
          self._gdiStrokeRect(
            dc, cmd.x, cmd.y, cmd.w, cmd.h, cmd.r, cmd.g, cmd.b, cmd.penW,
          )
        case DrawCmdEnum.DrawLine:
          self._gdiDrawLine(
            dc, cmd.x, cmd.y, cmd.x2, cmd.y2, cmd.r, cmd.g, cmd.b, cmd.penW,
          )
        case DrawCmdEnum.DrawBezier:
          cx1, cy1, cx2, cy2 = _bezierControls(cmd.x, cmd.y, cmd.x2, cmd.y2)
          self._gdiDrawBezier(
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
            cmd.penW,
          )
        case DrawCmdEnum.DrawText:
          self._gdiDrawText(
            dc,
            cmd.x,
            cmd.y,
            cmd.w,
            cmd.h,
            cmd.text,
            cmd.r,
            cmd.g,
            cmd.b,
            cmd.fontName,
            cmd.fontSize,
            cmd.fontBold,
            cmd.textAlign,
          )
        case DrawCmdEnum.FillEllipse:
          self._gdiFillEllipse(
            dc, cmd.x, cmd.y, cmd.x2, cmd.y2, cmd.r, cmd.g, cmd.b,
          )
        case DrawCmdEnum.FillRoundRect:
          self._gdiFillRoundRect(
            dc, cmd.x, cmd.y, cmd.w, cmd.h, cmd.radius, cmd.r, cmd.g, cmd.b,
          )
        case DrawCmdEnum.StrokeRoundRect:
          self._gdiStrokeRoundRect(
            dc,
            cmd.x,
            cmd.y,
            cmd.w,
            cmd.h,
            cmd.radius,
            cmd.r,
            cmd.g,
            cmd.b,
            cmd.penW,
          )
        case DrawCmdEnum.FillRectInRoundClip:
          self._gdiFillRectInRoundClip(
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
  panX: float64 = 0.0
  panY: float64 = 0.0
  zoom: float64 = 1.0
  zoomMin: float64 = 0.25
  zoomMax: float64 = 2.0
  font: UICanvasFont = new()
  _pctx: UIPaintContext = new()

  @native
  def _winParentClientSize(self, parent: int64) -> (int, int):
    """父窗口客户区宽高。"""
    ...

  @native
  def _winMountChild(self, parent: int64, x: int, y: int, w: int, h: int) -> None:
    """创建/重建画布子 HWND 并挂到 ``parent``。"""
    ...

  @native
  def _winClientSize(self) -> (int, int):
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
      cw, ch = self._winParentClientSize(parent)
      if ww < 0:
        ww = cw - x
      if wh < 0:
        wh = ch - y
    if ww < 1:
      ww = 1
    if wh < 1:
      wh = 1
    self._winMountChild(parent, x, y, ww, wh)

  @native
  def setBounds(self, x: int, y: int, w: int, h: int) -> None:
    """``MoveWindow`` 调整已 mount 的子窗口。"""
    ...

  @native
  def clientFromScreen(self, scrX: int, scrY: int) -> (int, int):
    """屏幕坐标 → 本控件客户区坐标。"""
    ...

  def containsScreenPoint(self, scrX: int, scrY: int) -> bool:
    if self.handle == 0:
      return False
    cx, cy = self.clientFromScreen(scrX, scrY)
    cw, ch = self._winClientSize()
    if cx < 0 or cy < 0:
      return False
    if cx >= cw or cy >= ch:
      return False
    return True

  @native
  def invalidate(self) -> None:
    """请求重绘。"""
    ...

  def worldToScreen(self, wx: float64, wy: float64) -> (float64, float64):
    sx: float64 = (wx + self.panX) * self.zoom
    sy: float64 = (wy + self.panY) * self.zoom
    return sx, sy

  def screenToWorld(self, sx: float64, sy: float64) -> (float64, float64):
    wx: float64 = sx / self.zoom - self.panX
    wy: float64 = sy / self.zoom - self.panY
    return wx, wy

  def screenToWorldAt(self, sx: float64, sy: float64, zoom: float64) -> (float64, float64):
    wx: float64 = sx / zoom - self.panX
    wy: float64 = sy / zoom - self.panY
    return wx, wy

  def paintFrame(self, dc: int64, width: int, height: int) -> None:
    self._pctx.beginFrame(dc, width, height, self.font, self.zoom)
    self.onPaint(self._pctx)
    self._pctx.commit()

  @virtual
  def onPaint(self, ctx: UIPaintContext @ref) -> None:
    pass

  @virtual
  def onPointerDown(self, btn: int, sx: int, sy: int) -> None:
    pass

  @virtual
  def onPointerMove(self, btn: int, sx: int, sy: int) -> None:
    pass

  @virtual
  def onPointerUp(self, btn: int, sx: int, sy: int) -> None:
    pass

  @virtual
  def onKey(self, key: int) -> None:
    pass

  @virtual
  def onWheel(self, delta: int, sx: int, sy: int) -> None:
    if delta == 0:
      return
    oldZoom: float64 = self.zoom
    step: float64 = 0.1
    if delta > 0:
      self.zoom += step
    else:
      self.zoom -= step
    if self.zoom < self.zoomMin:
      self.zoom = self.zoomMin
    if self.zoom > self.zoomMax:
      self.zoom = self.zoomMax
    if self.zoom == oldZoom:
      return
    wx, wy = self.screenToWorldAt(float64(sx), float64(sy), oldZoom)
    self.panX = float64(sx) / self.zoom - wx
    self.panY = float64(sy) / self.zoom - wy
    self.invalidate()
