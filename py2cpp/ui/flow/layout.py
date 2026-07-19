"""节点布局、坐标变换与命中检测。"""
from ...builtins import *
from .model import FlowGraph, FlowNode, FlowPin, FlowPinKind


NODE_WIDTH: int = 240
TITLE_HEIGHT: int = 34
ROW_HEIGHT: int = 26
PIN_HIT_RADIUS: int = 10
NODE_CORNER_RADIUS: int = 10
PIN_LABEL_PAD: int = 12


def node_screen_width(zoom: float64) -> int:
  return int(float64(NODE_WIDTH) * zoom)


def node_body_height(pin_rows: int) -> int:
  if pin_rows < 1:
    return ROW_HEIGHT
  return pin_rows * ROW_HEIGHT


def node_height(pin_count: int) -> int:
  rows: int = pin_count
  if rows < 1:
    rows = 1
  return TITLE_HEIGHT + node_body_height(rows)


def graph_to_screen(gx: float64, gy: float64, pan_x: float64, pan_y: float64, zoom: float64) -> (float64, float64):
  sx: float64 = (gx + pan_x) * zoom
  sy: float64 = (gy + pan_y) * zoom
  return sx, sy


def screen_to_graph(sx: float64, sy: float64, pan_x: float64, pan_y: float64, zoom: float64) -> (float64, float64):
  gx: float64 = sx / zoom - pan_x
  gy: float64 = sy / zoom - pan_y
  return gx, gy


def pin_graph_pos(node: FlowNode @ref, pin_index: int) -> (float64, float64):
  rows: int = len(node.pins)
  if rows < 1:
    rows = 1
  h: int = node_height(rows)
  pin: FlowPin = node.pins[pin_index]
  py: float64 = node.y + float64(TITLE_HEIGHT) + float64(ROW_HEIGHT) * (float64(pin_index) + 0.5)
  px: float64 = node.x
  if pin.kind in {FlowPinKind.ExecOut, FlowPinKind.DataOut}:
    px = node.x + float64(NODE_WIDTH)
  return px, py


def node_contains(node: FlowNode @ref, gx: float64, gy: float64) -> bool:
  rows: int = len(node.pins)
  if rows < 1:
    rows = 1
  h: int = node_height(rows)
  if gx < node.x:
    return False
  if gx > node.x + float64(NODE_WIDTH):
    return False
  if gy < node.y:
    return False
  if gy > node.y + float64(h):
    return False
  return True


def _rects_overlap(
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


def nodes_in_graph_rect(
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
    if _rects_overlap(rx, ry, rw, rh, node.x, node.y, float64(NODE_WIDTH), float64(node_height(rows))):
      out.append(node.id)
  return out


def hit_test_pin(graph: FlowGraph @ref, gx: float64, gy: float64) -> int:
  best: int = -1
  best_d2: float64 = float64(PIN_HIT_RADIUS * PIN_HIT_RADIUS) + 1.0
  for node in graph.nodes:
    pi: int = 0
    for _ in node.pins:
      px, py = pin_graph_pos(node, pi)
      dx: float64 = gx - px
      dy: float64 = gy - py
      d2: float64 = dx * dx + dy * dy
      if d2 <= float64(PIN_HIT_RADIUS * PIN_HIT_RADIUS) and d2 < best_d2:
        best_d2 = d2
        best = node.pins[pi].id
      pi += 1
  return best


def hit_test_node(graph: FlowGraph @ref, gx: float64, gy: float64) -> int:
  best: int = -1
  for node in graph.nodes:
    if node_contains(node, gx, gy):
      best = node.id
  return best
