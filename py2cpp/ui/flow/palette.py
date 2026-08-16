"""节点 palette 侧栏（分组列表 + 拖拽源）。"""
from ...builtins import *
from ..input import cursorScreenPos
from ..canvas import UICanvas, UIPaintContext
from .canvas import UIFlowCanvas
from .catalog import FlowNodeCatalog, FlowNodeTemplate
from .model import FlowNodeEnum
from .style import UIFlowStyle


GroupHeaderH: int = 32
ItemRowH: int = 36


@copyable
class PaletteGroupView:
  name: str = ""
  collapsed: bool = False
  kindIds: list[str, 0] = []


@dataclass(eq=False, repr=False)
class UIFlowPalette(UICanvas):
  catalog: FlowNodeCatalog = new()
  _canvasPtr: int64 @optional = 0
  style: UIFlowStyle = new()
  groups: list[PaletteGroupView, 0] @optional = []
  scrollY: int = 0
  hoverKind: str = ""
  _dragKind: str = ""
  _dragActive: bool = False

  def rebuildGroups(self) -> None:
    for i in range(len(self.groups) - 1, -1, -1):
      self.groups.pop(i)
    for cat in self.catalog.categories():
      gv: PaletteGroupView = new()
      gv.name = cat
      gv.collapsed = False
      for tpl in self.catalog.entriesIn(cat):
        gv.kindIds.append(tpl.kindId)
      self.groups.append(gv)

  def _contentHeight(self) -> int:
    h: int = 0
    for gv in self.groups:
      h += GroupHeaderH
      if not gv.collapsed:
        h += len(gv.kindIds) * ItemRowH
    return h

  def _hitKind(self, sx: int, sy: int) -> str:
    y: int = -self.scrollY
    for gv in self.groups:
      headerY: int = y
      y += GroupHeaderH
      if sy >= headerY and sy < headerY + GroupHeaderH:
        return ""
      if not gv.collapsed:
        for kindId in gv.kindIds:
          rowY: int = y
          y += ItemRowH
          if sy >= rowY and sy < rowY + ItemRowH:
            return kindId
    return ""

  def _hitGroupHeader(self, sx: int, sy: int) -> int:
    y: int = -self.scrollY
    gi: int = 0
    for gv in self.groups:
      headerY: int = y
      y += GroupHeaderH
      if not gv.collapsed:
        y += len(gv.kindIds) * ItemRowH
      if sy >= headerY and sy < headerY + GroupHeaderH:
        return gi
      gi += 1
    return -1

  def _kindDotColor(self, tpl: FlowNodeTemplate @ref) -> (int, int, int):
    match tpl.nodeKind:
      case FlowNodeEnum.Event:
        return (255, 160, 64)
      case FlowNodeEnum.Pure:
        return self.style.wireData
      case FlowNodeEnum.Branch:
        return (200, 120, 255)
      case FlowNodeEnum.ForLoop:
        return (120, 200, 255)
      case _:
        return self.style.wireExec

  @override
  def onPaint(self, ctx: UIPaintContext @ref) -> None:
    # 侧栏不随画布 zoom；字号写在 ctx 上（``self.font`` 为值语义时赋值不可靠）。
    ctx.zoom = 1.0
    ctx.font.size = self.style.paletteFontSize
    ctx.fillRect(0, 0, ctx.width, ctx.height, (28, 28, 30))
    y: int = -self.scrollY
    dotPad: int = (ItemRowH - 10) // 2
    for gv in self.groups:
      headerY: int = y
      y += GroupHeaderH
      ctx.fillRect(0, headerY, ctx.width, GroupHeaderH, (45, 45, 48))
      mark: str = "v"
      if gv.collapsed:
        mark = ">"
      ctx.drawText(6, headerY, 20, GroupHeaderH, mark, self.style.textColor)
      ctx.drawText(28, headerY, ctx.width - 34, GroupHeaderH, gv.name, self.style.textColor)
      if not gv.collapsed:
        for kindId in gv.kindIds:
          rowY: int = y
          y += ItemRowH
          if rowY + ItemRowH < 0:
            continue
          if rowY > ctx.height:
            break
          bg: (int, int, int) = (35, 35, 38)
          if kindId == self.hoverKind:
            bg = (55, 55, 60)
          if kindId == self._dragKind and self._dragActive:
            bg = (0, 90, 150)
          ctx.fillRect(0, rowY, ctx.width, ItemRowH, bg)
          tpl: FlowNodeTemplate = self.catalog.find(kindId)
          dot = self._kindDotColor(tpl)
          ctx.fillEllipse(10, rowY + dotPad, 20, rowY + dotPad + 10, dot)
          ctx.drawText(28, rowY, ctx.width - 34, ItemRowH, tpl.title, self.style.textColor)

  @override
  def onWheel(self, delta: int, sx: int, sy: int) -> None:
    if delta == 0:
      return
    step: int = 24
    if delta > 0:
      self.scrollY -= step
    else:
      self.scrollY += step
    maxScroll: int = self._contentHeight() - 100
    if maxScroll < 0:
      maxScroll = 0
    if self.scrollY < 0:
      self.scrollY = 0
    if self.scrollY > maxScroll:
      self.scrollY = maxScroll
    self.invalidate()

  @override
  def onPointerDown(self, btn: int, sx: int, sy: int) -> None:
    if btn != 1:
      return
    gi: int = self._hitGroupHeader(sx, sy)
    if gi >= 0:
      gv: PaletteGroupView = self.groups[gi]
      gv.collapsed = not gv.collapsed
      self.groups[gi] = gv
      self.invalidate()
      return
    kind: str = self._hitKind(sx, sy)
    if kind:
      self._dragKind = kind
      self._dragActive = True
      self.invalidate()

  @override
  def onPointerMove(self, btn: int, sx: int, sy: int) -> None:
    if self._dragActive:
      self.invalidate()
      return
    kind: str = self._hitKind(sx, sy)
    if kind != self.hoverKind:
      self.hoverKind = kind
      self.invalidate()

  @override
  def onPointerUp(self, btn: int, sx: int, sy: int) -> None:
    if btn != 1:
      return
    if self._dragActive:
      self._finishDrag()
      return

  @native
  def bindCanvas(self, canvas: UIFlowCanvas @ref) -> None:
    """``attach`` 后绑定已 mount 的画布（值拷贝无法共享 ``handle`` / ``graph``）。"""
    ...

  @native
  def _dropNodeAtScreen(self, kind: str, scrX: int, scrY: int) -> None:
    """经 ``_canvasPtr`` 在屏幕坐标处投放节点。"""
    ...

  def _finishDrag(self) -> None:
    kind: str = self._dragKind
    self._dragActive = False
    self._dragKind = ""
    self.invalidate()
    if not kind:
      return
    sx: int = cursorScreenPos()[0]
    sy: int = cursorScreenPos()[1]
    self._dropNodeAtScreen(kind, sx, sy)
