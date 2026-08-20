"""顶栏：Play / Pause / Stop / Step（自绘按钮）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.ui.canvas import UICanvas, UIPaintContext

from ..command import CommandBus, ZeusCommandUnion

BTN_H: int = 28
BTN_W: int = 72
PAD: int = 8
GAP: int = 6


@dataclass(eq=False, repr=False)
class ToolbarView(UICanvas):
  """点击工具条按钮 → ``Play*`` 命令。"""

  bus: CommandBus = new()

  def bind_bus(self, bus: CommandBus) -> None:
    self.bus = bus

  def _label_at(self, i: int) -> str:
    match i:
      case 0:
        return "Play"
      case 1:
        return "Pause"
      case 2:
        return "Stop"
      case _:
        return "Step"

  @override
  def on_paint(self, ctx: UIPaintContext @ref) -> None:
    ctx.zoom = 1.0
    ctx.fillRect(0, 0, ctx.width, ctx.height, (45, 45, 48))
    ctx.drawText(PAD, 6, 120, BTN_H, "Zeus", (220, 220, 230))
    x: int = 100
    for i in range(4):
      ctx.fillRect(x, 4, BTN_W, BTN_H, (70, 70, 78))
      ctx.drawText(x + 8, 6, BTN_W - 12, BTN_H, self._label_at(i), (240, 240, 245))
      x += BTN_W + GAP

  @override
  def on_pointer_down(self, btn: int, sx: int, sy: int) -> None:
    if btn != 1:
      return
    x: int = 100
    for i in range(4):
      if sx >= x and sx < x + BTN_W and sy >= 4 and sy < 4 + BTN_H:
        self._dispatch(self._label_at(i))
        self.invalidate()
        return
      x += BTN_W + GAP

  def _dispatch(self, name: str) -> None:
    match name:
      case "Play":
        self.bus.dispatch(ZeusCommandUnion.PlayStart())
      case "Pause":
        self.bus.dispatch(ZeusCommandUnion.PlayPause())
      case "Stop":
        self.bus.dispatch(ZeusCommandUnion.PlayStop())
      case "Step":
        self.bus.dispatch(ZeusCommandUnion.PlayStep(1))
      case _:
        pass
