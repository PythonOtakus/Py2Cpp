"""Hierarchy：自绘 ``UICanvas`` 对象树（无 Win32 Tree 控件时的最小替代）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.ui.canvas import UICanvas, UIPaintContext
from py2cpp.ui.events import UIValueChangedDelegate

from .session import HierarchyRow
from ..command import CommandBus, ZeusCommand

ROW_H: int = 24
PAD_X: int = 8
INDENT: int = 14


@dataclass(eq=False, repr=False)
class HierarchyView(UICanvas):
  """点击行 → ``EditorSelect``；``rows`` 由壳层 ``refresh`` 写入。"""

  bus: CommandBus = new()
  rows: list[HierarchyRow, 0] @optional = []
  selection_changed: UIValueChangedDelegate[str] = new()
  scroll_y: int = 0

  def refresh_from(self, rows: list[HierarchyRow, 0], bus: CommandBus) -> None:
    self.bus = bus
    for i in range(len(self.rows) - 1, -1, -1):
      self.rows.pop(i)
    for j in range(len(rows)):
      self.rows.append(rows[j])
    self.invalidate()

  @override
  def on_paint(self, ctx: UIPaintContext @ref) -> None:
    ctx.zoom = 1.0
    ctx.fill_rect(0, 0, ctx.width, ctx.height, (36, 36, 40))
    ctx.draw_text(PAD_X, 4, ctx.width - PAD_X, ROW_H, "Hierarchy", (180, 180, 190))
    y: int = 28 - self.scroll_y
    selected: str = self.bus.selected
    for i in range(len(self.rows)):
      row: HierarchyRow = self.rows[i]
      if selected == row.name:
        ctx.fill_rect(0, y, ctx.width, ROW_H, (55, 90, 140))
      x: int = PAD_X + row.depth * INDENT
      color: (int, int, int) = (230, 230, 235)
      if selected == row.name:
        color = (255, 255, 255)
      ctx.draw_text(x, y, ctx.width - x, ROW_H, row.name, color)
      y += ROW_H

  @override
  def on_pointer_down(self, btn: int, sx: int, sy: int) -> None:
    if btn != 1:
      return
    y: int = 28 - self.scroll_y
    for i in range(len(self.rows)):
      if sy >= y and sy < y + ROW_H:
        name: str = self.rows[i].name
        self.bus.dispatch(ZeusCommand.EditorSelect(name))
        self.selection_changed(name)
        self.invalidate()
        return
      y += ROW_H
