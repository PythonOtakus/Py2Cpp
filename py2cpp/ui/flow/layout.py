"""节点布局、坐标变换与命中检测。"""
from ...builtins import *
from .model import FlowGraph, FlowNode, FlowPin, FlowPinEnum


NodeWidth: int = 240
TitleHeight: int = 34
RowHeight: int = 26
PinHitRadius: int = 10
NodeCornerRadius: int = 10
PinLabelPad: int = 12


def nodeScreenWidth(zoom: float64) -> int:
  return int(float64(NodeWidth) * zoom)


def nodeBodyHeight(pinRows: int) -> int:
  if pinRows < 1:
    return RowHeight
  return pinRows * RowHeight


def nodeHeight(pinCount: int) -> int:
  rows: int = pinCount
  if rows < 1:
    rows = 1
  return TitleHeight + nodeBodyHeight(rows)


def graphToScreen(gx: float64, gy: float64, panX: float64, panY: float64, zoom: float64) -> (float64, float64):
  sx: float64 = (gx + panX) * zoom
  sy: float64 = (gy + panY) * zoom
  return sx, sy


def screenToGraph(sx: float64, sy: float64, panX: float64, panY: float64, zoom: float64) -> (float64, float64):
  gx: float64 = sx / zoom - panX
  gy: float64 = sy / zoom - panY
  return gx, gy


def pinGraphPos(node: FlowNode @ref, pinIndex: int) -> (float64, float64):
  rows: int = len(node.pins)
  if rows < 1:
    rows = 1
  h: int = nodeHeight(rows)
  pin: FlowPin = node.pins[pinIndex]
  py: float64 = node.y + float64(TitleHeight) + float64(RowHeight) * (float64(pinIndex) + 0.5)
  px: float64 = node.x
  if pin.kind in {FlowPinEnum.ExecOut, FlowPinEnum.DataOut}:
    px = node.x + float64(NodeWidth)
  return px, py


def nodeContains(node: FlowNode @ref, gx: float64, gy: float64) -> bool:
  rows: int = len(node.pins)
  if rows < 1:
    rows = 1
  h: int = nodeHeight(rows)
  if gx < node.x:
    return False
  if gx > node.x + float64(NodeWidth):
    return False
  if gy < node.y:
    return False
  if gy > node.y + float64(h):
    return False
  return True


def _rectsOverlap(
  ax: float64,
  ay: float64,
  aw: float64,
  ah: float64,
  bx: float64,
  by: float64,
  bw: float64,
  bh: float64,
) -> bool:
  if ax + aw <= bx:
    return False
  if bx + bw <= ax:
    return False
  if ay + ah <= by:
    return False
  if by + bh <= ay:
    return False
  return True


def nodesInGraphRect(
  graph: FlowGraph @ref,
  gx1: float64,
  gy1: float64,
  gx2: float64,
  gy2: float64,
) -> list[int, 0]:
  rx: float64 = gx1
  ry: float64 = gy1
  rw: float64 = gx2 - gx1
  rh: float64 = gy2 - gy1
  if rw < 0.0:
    rx = gx2
    rw = -rw
  if rh < 0.0:
    ry = gy2
    rh = -rh
  out: list[int, 0] = []
  for node in graph.nodes:
    rows: int = len(node.pins)
    if rows < 1:
      rows = 1
    if _rectsOverlap(rx, ry, rw, rh, node.x, node.y, float64(NodeWidth), float64(nodeHeight(rows))):
      out.append(node.id)
  return out


def hitTestPin(graph: FlowGraph @ref, gx: float64, gy: float64) -> int:
  best: int = -1
  bestD2: float64 = float64(PinHitRadius * PinHitRadius) + 1.0
  for node in graph.nodes:
    pi: int = 0
    for _ in node.pins:
      px, py = pinGraphPos(node, pi)
      dx: float64 = gx - px
      dy: float64 = gy - py
      d2: float64 = dx * dx + dy * dy
      if d2 <= float64(PinHitRadius * PinHitRadius) and d2 < bestD2:
        bestD2 = d2
        best = node.pins[pi].id
      pi += 1
  return best


def hitTestNode(graph: FlowGraph @ref, gx: float64, gy: float64) -> int:
  best: int = -1
  for node in graph.nodes:
    if nodeContains(node, gx, gy):
      best = node.id
  return best
