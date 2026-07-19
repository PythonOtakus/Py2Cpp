"""FlowGraph JSON 序列化（``serde/json``）。"""
from ...builtins import *
from ...serde.json import Json, JsonEncoder
from ...serde.protocols import serializable
from .model import FlowGraph, FlowNode, FlowPin, FlowEdge, FlowPinKind


@serializable
@copyable
@dataclass
class FlowPinWire:
  id: int = 0
  name: str = ""
  kind: str = ""
  type_id: str = "object"


@serializable
@copyable
@dataclass
class FlowNodeWire:
  id: int = 0
  kind_id: str = ""
  title: str = ""
  x: float64 = 0.0
  y: float64 = 0.0
  pins: list[FlowPinWire, 0] @optional = []


@serializable
@copyable
@dataclass
class FlowEdgeWire:
  from_pin: int = 0
  to_pin: int = 0


@serializable
@copyable
@dataclass
class FlowGraphWire:
  version: int = 1
  nodes: list[FlowNodeWire, 0] @optional = []
  edges: list[FlowEdgeWire, 0] @optional = []


def _pin_kind_name(k: FlowPinKind) -> str:
  match k:
    case FlowPinKind.ExecIn:
      return "ExecIn"
    case FlowPinKind.ExecOut:
      return "ExecOut"
    case FlowPinKind.DataIn:
      return "DataIn"
    case _:
      return "DataOut"


def _parse_pin_kind(name: str) -> FlowPinKind:
  match name:
    case "ExecIn":
      return FlowPinKind.ExecIn
    case "ExecOut":
      return FlowPinKind.ExecOut
    case "DataIn":
      return FlowPinKind.DataIn
    case _:
      return FlowPinKind.DataOut


def graph_to_json(graph: FlowGraph @ref) -> str:
  wire: FlowGraphWire = new()
  for node in graph.nodes:
    nw: FlowNodeWire = new()
    nw.id = node.id
    nw.kind_id = node.kind_id
    nw.title = node.title
    nw.x = node.x
    nw.y = node.y
    for pin in node.pins:
      pw: FlowPinWire = new()
      pw.id = pin.id
      pw.name = pin.name
      pw.kind = _pin_kind_name(pin.kind)
      pw.type_id = pin.type_id
      nw.pins.append(pw)
    wire.nodes.append(nw)
  for edge in graph.edges:
    ew: FlowEdgeWire = new()
    ew.from_pin = edge.from_pin
    ew.to_pin = edge.to_pin
    wire.edges.append(ew)
  return Json.dumps(wire)


def graph_from_json(graph: FlowGraph @ref, text: str) -> None:
  graph.clear()
  wire: FlowGraphWire = Json.loads[FlowGraphWire](text)
  max_id: int = 0
  for nw in wire.nodes:
    node: FlowNode = new()
    node.id = nw.id
    node.kind_id = nw.kind_id
    node.title = nw.title
    node.x = nw.x
    node.y = nw.y
    if nw.id > max_id:
      max_id = nw.id
    for pw in nw.pins:
      pin: FlowPin = new()
      pin.id = pw.id
      pin.node_id = nw.id
      pin.name = pw.name
      pin.kind = _parse_pin_kind(pw.kind)
      pin.type_id = pw.type_id
      node.pins.append(pin)
      if pw.id > max_id:
        max_id = pw.id
    graph.nodes.append(node)
  for ew in wire.edges:
    edge: FlowEdge = new()
    edge.id = graph.alloc_id()
    edge.from_pin = ew.from_pin
    edge.to_pin = ew.to_pin
    graph.edges.append(edge)
  graph.set_next_id(max_id + 1)


def _node_id_selected(node_id: int, node_ids: list[int, 0]) -> bool:
  for nid in node_ids:
    if nid == node_id:
      return True
  return False


def _wire_pins_from_node(nw: FlowNodeWire @ref) -> list[FlowPin, 0]:
  pins: list[FlowPin, 0] = []
  for pw in nw.pins:
    pin: FlowPin = new()
    pin.name = pw.name
    pin.kind = _parse_pin_kind(pw.kind)
    pin.type_id = pw.type_id
    pins.append(pin)
  return pins


def subgraph_to_json(graph: FlowGraph @ref, node_ids: list[int, 0]) -> str:
  wire: FlowGraphWire = new()
  for node in graph.nodes:
    if not _node_id_selected(node.id, node_ids):
      continue
    nw: FlowNodeWire = new()
    nw.id = node.id
    nw.kind_id = node.kind_id
    nw.title = node.title
    nw.x = node.x
    nw.y = node.y
    for pin in node.pins:
      pw: FlowPinWire = new()
      pw.id = pin.id
      pw.name = pin.name
      pw.kind = _pin_kind_name(pin.kind)
      pw.type_id = pin.type_id
      nw.pins.append(pw)
    wire.nodes.append(nw)
  for edge in graph.edges:
    src_nid: int = graph.pin_node_id(edge.from_pin)
    dst_nid: int = graph.pin_node_id(edge.to_pin)
    if _node_id_selected(src_nid, node_ids) and _node_id_selected(dst_nid, node_ids):
      ew: FlowEdgeWire = new()
      ew.from_pin = edge.from_pin
      ew.to_pin = edge.to_pin
      wire.edges.append(ew)
  return Json.dumps(wire)


def _map_id(old_id: int, old_ids: list[int, 0], new_ids: list[int, 0]) -> int:
  for i in range(len(old_ids)):
    if old_ids[i] == old_id:
      return new_ids[i]
  return -1


def paste_subgraph(
  graph: FlowGraph @ref,
  text: str,
  offset_x: float64,
  offset_y: float64,
) -> list[int, 0]:
  wire: FlowGraphWire = Json.loads[FlowGraphWire](text)
  old_node_ids: list[int, 0] = []
  new_node_ids: list[int, 0] = []
  old_pin_ids: list[int, 0] = []
  new_pin_ids: list[int, 0] = []
  created: list[int, 0] = []
  for nw in wire.nodes:
    pins: list[FlowPin, 0] = _wire_pins_from_node(nw)
    nid: int = graph.add_node(nw.kind_id, nw.title, nw.x + offset_x, nw.y + offset_y, pins)
    created.append(nid)
    old_node_ids.append(nw.id)
    new_node_ids.append(nid)
    node = graph.find_node(nid)
    pi: int = 0
    for pw in nw.pins:
      old_pin_ids.append(pw.id)
      new_pin_ids.append(node.pins[pi].id)
      pi += 1
  for ew in wire.edges:
    new_from: int = _map_id(ew.from_pin, old_pin_ids, new_pin_ids)
    new_to: int = _map_id(ew.to_pin, old_pin_ids, new_pin_ids)
    if new_from < 0 or new_to < 0:
      continue
    try:
      graph.connect(new_from, new_to)
    except ValueError:
      pass
  return created
