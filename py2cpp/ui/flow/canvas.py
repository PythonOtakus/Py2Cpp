"""蓝图画布控件（``UIFlowCanvas``）。"""
from ...builtins import *
from ..canvas import TextAlignLeft, TextAlignRight, UICanvas, UIPaintContext
from ..events import UIEvent, UIValueChanged
from ..input import ctrlDown, shiftDown
from .catalog import FlowNodeCatalog
from .history import FlowGraphHistory
from .layout import (
  NodeCornerRadius,
  PinLabelPad,
  RowHeight,
  TitleHeight,
  graphToScreen,
  hitTestNode,
  hitTestPin,
  nodeHeight,
  nodeScreenWidth,
  nodesInGraphRect,
  pinGraphPos,
  screenToGraph,
)
from .model import FlowGraph, FlowNode, FlowPinEnum
from .serialize import pasteSubgraph, subgraphToJson
from .style import UIFlowStyle


MarqueeMinDrag: int = 4
PasteOffset: float64 = 24.0


@dataclass(eq=False, repr=False)
class UIFlowCanvas(UICanvas):
  graph: FlowGraph = new()
  catalog: FlowNodeCatalog = new()
  style: UIFlowStyle = new()
  history: FlowGraphHistory = new()
  clipboardJson: str = ""
  selectedNode: int = -1
  selectedNodes: list[int, 0] @optional = []
  _wireActive: bool = False
  _wireX1: float64 = 0.0
  _wireY1: float64 = 0.0
  _wireX2: float64 = 0.0
  _wireY2: float64 = 0.0
  _wireExec: bool = True
  _dragPan: bool = False
  _panLastSx: float64 = 0.0
  _panLastSy: float64 = 0.0
  _dragNode: bool = False
  _dragNodeId: int = -1
  _dragMoved: bool = False
  _dragLastGx: float64 = 0.0
  _dragLastGy: float64 = 0.0
  _wireFromPin: int = -1
  _marqueeActive: bool = False
  _marqueeAdditive: bool = False
  _marqueeSx: int = 0
  _marqueeSy: int = 0
  _marqueeEx: int = 0
  _marqueeEy: int = 0

  graphChanged: UIEvent = new()
  selectionChanged: UIValueChanged[int] = new()

  def _isNodeSelected(self, nodeId: int) -> bool:
    for nid in self.selectedNodes:
      if nid == nodeId:
        return True
    return False

  def _setSelection(self, nodeIds: list[int, 0]) -> None:
    for i in range(len(self.selectedNodes) - 1, -1, -1):
      self.selectedNodes.pop(i)
    for nid in nodeIds:
      self.selectedNodes.append(nid)
    primary: int = -1
    if self.selectedNodes:
      primary = self.selectedNodes[0]
    self.selectedNode = primary
    self.selectionChanged(primary)

  def _toggleNodeSelection(self, nodeId: int) -> None:
    found: bool = False
    for i in range(len(self.selectedNodes)):
      if self.selectedNodes[i] == nodeId:
        self.selectedNodes.pop(i)
        found = True
        break
    if not found:
      self.selectedNodes.append(nodeId)
    primary: int = -1
    if self.selectedNodes:
      primary = self.selectedNodes[0]
    self.selectedNode = primary
    self.selectionChanged(primary)

  def _hasSelection(self) -> bool:
    for _ in self.selectedNodes:
      return True
    return False

  def _recordUndo(self) -> None:
    self.history.push(self.graph)

  def selectAllNodes(self) -> None:
    ids: list[int, 0] = []
    for node in self.graph.nodes:
      ids.append(node.id)
    self._setSelection(ids)
    self.invalidate()

  def _clearSelectionState(self) -> None:
    for i in range(len(self.selectedNodes) - 1, -1, -1):
      self.selectedNodes.pop(i)
    self.selectedNode = -1
    self.selectionChanged(-1)

  def clearSelection(self) -> None:
    self._clearSelectionState()
    self.invalidate()

  def copySelectionJson(self) -> str:
    if not self._hasSelection():
      return ""
    return subgraphToJson(self.graph, self.selectedNodes)

  def copyToClipboard(self) -> None:
    self.clipboardJson = self.copySelectionJson()

  def pasteFromClipboard(self) -> None:
    self.pasteJson(self.clipboardJson)

  def _mergeSelection(self, nodeIds: list[int, 0]) -> None:
    for nid in nodeIds:
      if not self._isNodeSelected(nid):
        self.selectedNodes.append(nid)
    primary: int = -1
    if self.selectedNodes:
      primary = self.selectedNodes[0]
    self.selectedNode = primary
    self.selectionChanged(primary)

  def cutSelection(self) -> str:
    text: str = self.copySelectionJson()
    empty: str = ""
    if text == empty:
      return empty
    self._recordUndo()
    toRemove: list[int, 0] = []
    for nid in self.selectedNodes:
      toRemove.append(nid)
    for nid in toRemove:
      self.graph.removeNode(nid)
    self._clearSelectionState()
    self.graphChanged()
    self.invalidate()
    return text

  def deleteSelected(self) -> None:
    if not self._hasSelection():
      return
    self._recordUndo()
    toRemove: list[int, 0] = []
    for nid in self.selectedNodes:
      toRemove.append(nid)
    for nid in toRemove:
      self.graph.removeNode(nid)
    self._clearSelectionState()
    self.graphChanged()
    self.invalidate()

  def pasteJson(self, text: str) -> None:
    empty: str = ""
    if text == empty:
      return
    self._recordUndo()
    off: float64 = PasteOffset
    newIds: list[int, 0] = pasteSubgraph(self.graph, text, off, off)
    self._setSelection(newIds)
    self.graphChanged()
    self.invalidate()

  def undoGraph(self) -> bool:
    if self.history.undo(self.graph):
      self._clearSelectionState()
      self.graphChanged()
      self.invalidate()
      return True
    return False

  def redoGraph(self) -> bool:
    if self.history.redo(self.graph):
      self._clearSelectionState()
      self.graphChanged()
      self.invalidate()
      return True
    return False

  def _pinIndex(self, node: FlowNode @ref, pinId: int) -> int:
    pi: int = 0
    for p in node.pins:
      if p.id == pinId:
        return pi
      pi += 1
    return -1

  def _paintGrid(self, ctx: UIPaintContext @ref) -> None:
    minor: int = self.style.gridMinorStep
    major: int = self.style.gridMajorStep
    if minor < 4:
      minor = 4
    if major < minor:
      major = minor * 8
    for x in range(0, ctx.width, minor):
      if (x % major) == 0:
        ctx.drawLine(x, 0, x, ctx.height, self.style.gridMajor)
      else:
        ctx.drawLine(x, 0, x, ctx.height, self.style.gridMinor)
    for y in range(0, ctx.height, minor):
      if (y % major) == 0:
        ctx.drawLine(0, y, ctx.width, y, self.style.gridMajor)
      else:
        ctx.drawLine(0, y, ctx.width, y, self.style.gridMinor)

  def _drawEdges(self, ctx: UIPaintContext @ref) -> None:
    for edge in self.graph.edges:
      srcPin = self.graph.findPin(edge.fromPin)
      dstPin = self.graph.findPin(edge.toPin)
      srcNode = self.graph.findNode(srcPin.nodeId)
      dstNode = self.graph.findNode(dstPin.nodeId)
      sidx: int = self._pinIndex(srcNode, edge.fromPin)
      didx: int = self._pinIndex(dstNode, edge.toPin)
      x1, y1 = pinGraphPos(srcNode, sidx)
      x2, y2 = pinGraphPos(dstNode, didx)
      sx1, sy1 = graphToScreen(x1, y1, self.panX, self.panY, self.zoom)
      sx2, sy2 = graphToScreen(x2, y2, self.panX, self.panY, self.zoom)
      if srcPin.kind == FlowPinEnum.ExecOut:
        ctx.drawBezier(int(sx1), int(sy1), int(sx2), int(sy2), self.style.wireExec)
      else:
        ctx.drawBezier(int(sx1), int(sy1), int(sx2), int(sy2), self.style.wireData)
    if self._wireActive:
      wx1, wy1 = graphToScreen(self._wireX1, self._wireY1, self.panX, self.panY, self.zoom)
      wx2, wy2 = graphToScreen(self._wireX2, self._wireY2, self.panX, self.panY, self.zoom)
      if self._wireExec:
        ctx.drawBezier(int(wx1), int(wy1), int(wx2), int(wy2), self.style.wireExec)
      else:
        ctx.drawBezier(int(wx1), int(wy1), int(wx2), int(wy2), self.style.wireData)

  def _drawNodes(self, ctx: UIPaintContext @ref) -> None:
    titleH: int = int(float64(TitleHeight) * self.zoom)
    if titleH < 1:
      titleH = 1
    rowH: int = int(float64(RowHeight) * self.zoom)
    if rowH < 1:
      rowH = 1
    sw: int = nodeScreenWidth(self.zoom)
    corner: int = int(float64(NodeCornerRadius) * self.zoom)
    if corner < 2:
      corner = 2
    pad: int = int(float64(PinLabelPad) * self.zoom)
    if pad < 4:
      pad = 4
    pinR: int = int(6.0 * self.zoom)
    if pinR < 4:
      pinR = 4
    for node in self.graph.nodes:
      rows: int = len(node.pins)
      if rows < 1:
        rows = 1
      h: int = nodeHeight(rows)
      nsx, nsy = graphToScreen(node.x, node.y, self.panX, self.panY, self.zoom)
      ctx.fillRoundRect(
        int(nsx),
        int(nsy),
        sw,
        int(float64(h) * self.zoom),
        corner,
        self.style.nodeBody,
      )
      ctx.fillRectInRoundClip(
        int(nsx),
        int(nsy),
        sw,
        titleH,
        sw,
        int(float64(h) * self.zoom),
        corner,
        self.style.nodeTitle,
      )
      if self._isNodeSelected(node.id):
        ctx.strokeRoundRect(
          int(nsx),
          int(nsy),
          sw,
          int(float64(h) * self.zoom),
          corner,
          self.style.nodeSelected,
          2,
        )
      else:
        ctx.strokeRoundRect(
          int(nsx),
          int(nsy),
          sw,
          int(float64(h) * self.zoom),
          corner,
          self.style.nodeBorder,
          1,
        )
      savedSize: int = ctx.font.size
      ctx.font.size = self.style.titleFontSize
      ctx.drawText(
        int(nsx) + pad,
        int(nsy),
        sw - pad * 2,
        titleH,
        node.title,
        self.style.textColor,
      )
      ctx.font.size = self.style.fontSize
      pi: int = 0
      for pin in node.pins:
        px, py = pinGraphPos(node, pi)
        psx, psy = graphToScreen(px, py, self.panX, self.panY, self.zoom)
        if pin.kind in {FlowPinEnum.ExecIn, FlowPinEnum.ExecOut}:
          ctx.fillEllipse(
            int(psx) - pinR,
            int(psy) - pinR,
            int(psx) + pinR,
            int(psy) + pinR,
            self.style.wireExec,
          )
        else:
          ctx.fillEllipse(
            int(psx) - pinR,
            int(psy) - pinR,
            int(psx) + pinR,
            int(psy) + pinR,
            self.style.wireData,
          )
        if pin.name:
          labelY: int = int(nsy) + titleH + pi * rowH
          labelW: int = sw - pad * 2 - pinR
          if labelW < 8:
            labelW = 8
          isOut: bool = pin.kind in {FlowPinEnum.ExecOut, FlowPinEnum.DataOut}
          if isOut:
            ctx.drawText(
              int(nsx) + pad,
              labelY,
              labelW,
              rowH,
              pin.name,
              self.style.pinLabelColor,
              TextAlignRight,
            )
          else:
            ctx.drawText(
              int(nsx) + pad + pinR,
              labelY,
              labelW,
              rowH,
              pin.name,
              self.style.pinLabelColor,
              TextAlignLeft,
            )
        pi += 1
      ctx.font.size = savedSize

  @override
  def onPaint(self, ctx: UIPaintContext @ref) -> None:
    ctx.fillRect(0, 0, ctx.width, ctx.height, self.style.bgColor)
    self._paintGrid(ctx)
    self._drawEdges(ctx)
    self._drawNodes(ctx)
    if self._marqueeActive:
      x1: int = self._marqueeSx
      y1: int = self._marqueeSy
      x2: int = self._marqueeEx
      y2: int = self._marqueeEy
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
      ctx.strokeRect(rx, ry, rw, rh, self.style.nodeSelected, 1)

  def _pinIsOutput(self, pinId: int) -> bool:
    pin = self.graph.findPin(pinId)
    return pin.kind in {FlowPinEnum.ExecOut, FlowPinEnum.DataOut}

  def _beginWire(self, pinId: int, gx: float64, gy: float64) -> None:
    pin = self.graph.findPin(pinId)
    node = self.graph.findNode(pin.nodeId)
    self._wireFromPin = pinId
    self._wireActive = True
    self._wireExec = pin.kind == FlowPinEnum.ExecOut
    pinIdx: int = self._pinIndex(node, pinId)
    wireX, wireY = pinGraphPos(node, pinIdx)
    self._wireX1 = wireX
    self._wireY1 = wireY
    self._wireX2 = gx
    self._wireY2 = gy

  @override
  def onPointerDown(self, btn: int, sx: int, sy: int) -> None:
    if btn in {2, 4}:
      self._dragPan = True
      self._panLastSx = float64(sx)
      self._panLastSy = float64(sy)
      return
    gx, gy = screenToGraph(float64(sx), float64(sy), self.panX, self.panY, self.zoom)
    if btn != 1:
      return
    pinId: int = hitTestPin(self.graph, gx, gy)
    if pinId >= 0 and self._pinIsOutput(pinId):
      self._beginWire(pinId, gx, gy)
      self.invalidate()
      return
    nodeId: int = hitTestNode(self.graph, gx, gy)
    if nodeId >= 0:
      if shiftDown():
        self._toggleNodeSelection(nodeId)
      else:
        ids: list[int, 0] = []
        ids.append(nodeId)
        self._setSelection(ids)
      self._dragNode = True
      self._dragNodeId = nodeId
      self._dragMoved = False
      self._dragLastGx = gx
      self._dragLastGy = gy
      self.invalidate()
      return
    self._marqueeActive = True
    self._marqueeAdditive = shiftDown()
    self._marqueeSx = sx
    self._marqueeSy = sy
    self._marqueeEx = sx
    self._marqueeEy = sy
    if not self._marqueeAdditive:
      self._clearSelectionState()
    self.invalidate()

  @override
  def onPointerMove(self, btn: int, sx: int, sy: int) -> None:
    if self._dragPan:
      dx: float64 = float64(sx) - self._panLastSx
      dy: float64 = float64(sy) - self._panLastSy
      self.panX += dx / self.zoom
      self.panY += dy / self.zoom
      self._panLastSx = float64(sx)
      self._panLastSy = float64(sy)
      self.invalidate()
      return
    gx, gy = screenToGraph(float64(sx), float64(sy), self.panX, self.panY, self.zoom)
    if self._wireActive:
      self._wireX2 = gx
      self._wireY2 = gy
      self.invalidate()
      return
    if self._marqueeActive:
      self._marqueeEx = sx
      self._marqueeEy = sy
      self.invalidate()
      return
    if self._dragNode and self._dragNodeId >= 0:
      dx = gx - self._dragLastGx
      dy = gy - self._dragLastGy
      if dx != 0.0 or dy != 0.0:
        if not self._dragMoved:
          self._recordUndo()
          self._dragMoved = True
        for nid in self.selectedNodes:
          self.graph.moveNode(nid, dx, dy)
      self._dragLastGx = gx
      self._dragLastGy = gy
      self.invalidate()

  @override
  def onPointerUp(self, btn: int, sx: int, sy: int) -> None:
    if btn in {2, 4}:
      self._dragPan = False
      return
    if btn != 1:
      return
    if self._marqueeActive:
      self._marqueeActive = False
      dx: int = self._marqueeEx - self._marqueeSx
      dy: int = self._marqueeEy - self._marqueeSy
      if dx < 0:
        dx = -dx
      if dy < 0:
        dy = -dy
      if dx < MarqueeMinDrag and dy < MarqueeMinDrag:
        if not self._marqueeAdditive:
          self._clearSelectionState()
      else:
        gx1, gy1 = screenToGraph(float64(self._marqueeSx), float64(self._marqueeSy), self.panX, self.panY, self.zoom)
        gx2, gy2 = screenToGraph(float64(self._marqueeEx), float64(self._marqueeEy), self.panX, self.panY, self.zoom)
        picked: list[int, 0] = nodesInGraphRect(self.graph, gx1, gy1, gx2, gy2)
        if self._marqueeAdditive:
          self._mergeSelection(picked)
        else:
          self._setSelection(picked)
      self.invalidate()
      return
    if self._wireActive:
      gx, gy = screenToGraph(float64(sx), float64(sy), self.panX, self.panY, self.zoom)
      pinId = hitTestPin(self.graph, gx, gy)
      if pinId >= 0 and self._wireFromPin >= 0:
        self._recordUndo()
        try:
          self.graph.connect(self._wireFromPin, pinId)
          self.graphChanged()
        except ValueError:
          pass
      self._wireActive = False
      self._wireFromPin = -1
      self.invalidate()
      return
    self._dragNode = False
    self._dragNodeId = -1
    self._dragMoved = False

  def addNodeFromKind(self, kindId: str, gx: float64, gy: float64) -> int:
    self._recordUndo()
    tpl = self.catalog.find(kindId)
    pins = self.catalog.clonePins(kindId)
    nid: int = self.graph.addNode(kindId, tpl.title, gx, gy, pins)
    self.graphChanged()
    return nid

  def cancelInteraction(self) -> None:
    self._wireActive = False
    self._wireFromPin = -1
    self._dragPan = False
    self._dragNode = False
    self._dragNodeId = -1
    self._dragMoved = False
    self._marqueeActive = False
    self.clearSelection()

  @override
  def onKey(self, key: int) -> None:
    if key == 27:
      self.cancelInteraction()
      return
    if key == 46:
      self.deleteSelected()
      return
    if not ctrlDown():
      return
    match key:
      case 90:
        self.undoGraph()
      case 89:
        self.redoGraph()
      case 88:
        self.clipboardJson = self.cutSelection()
      case 67:
        self.copyToClipboard()
      case 86:
        self.pasteFromClipboard()
      case 65:
        self.selectAllNodes()
      case _:
        pass
