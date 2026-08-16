"""FlowGraph JSON 序列化（``serde/json``）。"""
from ...builtins import *
from ...serde.json import Json, JsonEncoder
from ...serde.protocols import serializable
from .model import FlowGraph, FlowNode, FlowPin, FlowEdge, FlowPinEnum


@serializable
@copyable
@dataclass
class FlowPinWire:
  id: int = 0
  name: str = ""
  kind: str = ""
  typeId: str = "object"


@serializable
@copyable
@dataclass
class FlowNodeWire:
  id: int = 0
  kindId: str = ""
  title: str = ""
  x: float64 = 0.0
  y: float64 = 0.0
  pins: list[FlowPinWire, 0] @optional = []


@serializable
@copyable
@dataclass
class FlowEdgeWire:
  fromPin: int = 0
  toPin: int = 0


@serializable
@copyable
@dataclass
class FlowGraphWire:
  version: int = 1
  nodes: list[FlowNodeWire, 0] @optional = []
  edges: list[FlowEdgeWire, 0] @optional = []


def _pinKindName(k: FlowPinEnum) -> str:
  match k:
    case FlowPinEnum.ExecIn:
      return "ExecIn"
    case FlowPinEnum.ExecOut:
      return "ExecOut"
    case FlowPinEnum.DataIn:
      return "DataIn"
    case _:
      return "DataOut"


def _parsePinKind(name: str) -> FlowPinEnum:
  match name:
    case "ExecIn":
      return FlowPinEnum.ExecIn
    case "ExecOut":
      return FlowPinEnum.ExecOut
    case "DataIn":
      return FlowPinEnum.DataIn
    case _:
      return FlowPinEnum.DataOut


def graphToJson(graph: FlowGraph @ref) -> str:
  wire: FlowGraphWire = new()
  for node in graph.nodes:
    nw: FlowNodeWire = new()
    nw.id = node.id
    nw.kindId = node.kindId
    nw.title = node.title
    nw.x = node.x
    nw.y = node.y
    for pin in node.pins:
      pw: FlowPinWire = new()
      pw.id = pin.id
      pw.name = pin.name
      pw.kind = _pinKindName(pin.kind)
      pw.typeId = pin.typeId
      nw.pins.append(pw)
    wire.nodes.append(nw)
  for edge in graph.edges:
    ew: FlowEdgeWire = new()
    ew.fromPin = edge.fromPin
    ew.toPin = edge.toPin
    wire.edges.append(ew)
  return Json.dumps(wire)


def graphFromJson(graph: FlowGraph @ref, text: str) -> None:
  graph.clear()
  wire: FlowGraphWire = Json.loads[FlowGraphWire](text)
  maxId: int = 0
  for nw in wire.nodes:
    node: FlowNode = new()
    node.id = nw.id
    node.kindId = nw.kindId
    node.title = nw.title
    node.x = nw.x
    node.y = nw.y
    if nw.id > maxId:
      maxId = nw.id
    for pw in nw.pins:
      pin: FlowPin = new()
      pin.id = pw.id
      pin.nodeId = nw.id
      pin.name = pw.name
      pin.kind = _parsePinKind(pw.kind)
      pin.typeId = pw.typeId
      node.pins.append(pin)
      if pw.id > maxId:
        maxId = pw.id
    graph.nodes.append(node)
  for ew in wire.edges:
    edge: FlowEdge = new()
    edge.id = graph.allocId()
    edge.fromPin = ew.fromPin
    edge.toPin = ew.toPin
    graph.edges.append(edge)
  graph.setNextId(maxId + 1)


def _nodeIdSelected(nodeId: int, nodeIds: list[int, 0]) -> bool:
  for nid in nodeIds:
    if nid == nodeId:
      return True
  return False


def _wirePinsFromNode(nw: FlowNodeWire @ref) -> list[FlowPin, 0]:
  pins: list[FlowPin, 0] = []
  for pw in nw.pins:
    pin: FlowPin = new()
    pin.name = pw.name
    pin.kind = _parsePinKind(pw.kind)
    pin.typeId = pw.typeId
    pins.append(pin)
  return pins


def subgraphToJson(graph: FlowGraph @ref, nodeIds: list[int, 0]) -> str:
  wire: FlowGraphWire = new()
  for node in graph.nodes:
    if not _nodeIdSelected(node.id, nodeIds):
      continue
    nw: FlowNodeWire = new()
    nw.id = node.id
    nw.kindId = node.kindId
    nw.title = node.title
    nw.x = node.x
    nw.y = node.y
    for pin in node.pins:
      pw: FlowPinWire = new()
      pw.id = pin.id
      pw.name = pin.name
      pw.kind = _pinKindName(pin.kind)
      pw.typeId = pin.typeId
      nw.pins.append(pw)
    wire.nodes.append(nw)
  for edge in graph.edges:
    srcNid: int = graph.pinNodeId(edge.fromPin)
    dstNid: int = graph.pinNodeId(edge.toPin)
    if _nodeIdSelected(srcNid, nodeIds) and _nodeIdSelected(dstNid, nodeIds):
      ew: FlowEdgeWire = new()
      ew.fromPin = edge.fromPin
      ew.toPin = edge.toPin
      wire.edges.append(ew)
  return Json.dumps(wire)


def _mapId(oldId: int, oldIds: list[int, 0], newIds: list[int, 0]) -> int:
  for i in range(len(oldIds)):
    if oldIds[i] == oldId:
      return newIds[i]
  return -1


def pasteSubgraph(
  graph: FlowGraph @ref,
  text: str,
  offsetX: float64,
  offsetY: float64,
) -> list[int, 0]:
  wire: FlowGraphWire = Json.loads[FlowGraphWire](text)
  oldNodeIds: list[int, 0] = []
  newNodeIds: list[int, 0] = []
  oldPinIds: list[int, 0] = []
  newPinIds: list[int, 0] = []
  created: list[int, 0] = []
  for nw in wire.nodes:
    pins: list[FlowPin, 0] = _wirePinsFromNode(nw)
    nid: int = graph.addNode(nw.kindId, nw.title, nw.x + offsetX, nw.y + offsetY, pins)
    created.append(nid)
    oldNodeIds.append(nw.id)
    newNodeIds.append(nid)
    node = graph.findNode(nid)
    pi: int = 0
    for pw in nw.pins:
      oldPinIds.append(pw.id)
      newPinIds.append(node.pins[pi].id)
      pi += 1
  for ew in wire.edges:
    newFrom: int = _mapId(ew.fromPin, oldPinIds, newPinIds)
    newTo: int = _mapId(ew.toPin, oldPinIds, newPinIds)
    if newFrom < 0 or newTo < 0:
      continue
    try:
      graph.connect(newFrom, newTo)
    except ValueError:
      pass
  return created
