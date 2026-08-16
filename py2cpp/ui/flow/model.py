"""``FlowGraph`` 数据模型与连线规则。"""
from ...builtins import *
from ...core.exceptions import ValueError


@enum
class FlowPinEnum:
  ExecIn = 0
  ExecOut = 1
  DataIn = 2
  DataOut = 3


@enum
class FlowNodeEnum:
  Callable = 0
  Pure = 1
  Event = 2
  Branch = 3
  ForLoop = 4


@copyable
class FlowPin:
  id: int = 0
  nodeId: int = 0
  name: str = ""
  kind: FlowPinEnum = FlowPinEnum.DataIn
  typeId: str = "object"


@copyable
class FlowNode:
  id: int = 0
  kindId: str = ""
  title: str = ""
  x: float64 = 0.0
  y: float64 = 0.0
  pins: list[FlowPin, 0] = []


@copyable
class FlowEdge:
  id: int = 0
  fromPin: int = 0
  toPin: int = 0


@copyable
class FlowGraph:
  nodes: list[FlowNode, 0] = []
  edges: list[FlowEdge, 0] = []
  _nextId: int = 1

  def allocId(self) -> int:
    nid: int = self._nextId
    self._nextId += 1
    return nid

  def setNextId(self, nextId: int) -> None:
    self._nextId = nextId

  def findNode(self, nodeId: int) -> FlowNode:
    for n in self.nodes:
      if n.id == nodeId:
        return n
    raise ValueError("flow node not found")

  def moveNode(self, nodeId: int, dx: float64, dy: float64) -> None:
    for i in range(len(self.nodes)):
      if self.nodes[i].id == nodeId:
        node: FlowNode = self.nodes[i]
        node.x += dx
        node.y += dy
        self.nodes[i] = node
        return
    raise ValueError("flow node not found")

  def findPin(self, pinId: int) -> FlowPin:
    for n in self.nodes:
      for p in n.pins:
        if p.id == pinId:
          return p
    raise ValueError("flow pin not found")

  def pinNodeId(self, pinId: int) -> int:
    return self.findPin(pinId).nodeId

  def _removeEdgesOnPin(self, pinId: int) -> None:
    for i in range(len(self.edges) - 1, -1, -1):
      e: FlowEdge = self.edges[i]
      if e.fromPin == pinId or e.toPin == pinId:
        self.edges.pop(i)

  def _pinAcceptsInput(self, pin: FlowPin) -> bool:
    return pin.kind in {FlowPinEnum.ExecIn, FlowPinEnum.DataIn}

  def _pinAcceptsOutput(self, pin: FlowPin) -> bool:
    return pin.kind in {FlowPinEnum.ExecOut, FlowPinEnum.DataOut}

  def _typesCompatible(self, outTid: str, inTid: str) -> bool:
    if outTid == inTid:
      return True
    if inTid == "object":
      return True
    return False

  def connect(self, fromPin: int, toPin: int) -> int:
    src: FlowPin = self.findPin(fromPin)
    dst: FlowPin = self.findPin(toPin)
    if not self._pinAcceptsOutput(src):
      raise ValueError("flow connect: source must be output pin")
    if not self._pinAcceptsInput(dst):
      raise ValueError("flow connect: target must be input pin")
    if src.kind == FlowPinEnum.ExecOut:
      if dst.kind != FlowPinEnum.ExecIn:
        raise ValueError("flow connect: exec out must target exec in")
    elif src.kind == FlowPinEnum.DataOut:
      if dst.kind != FlowPinEnum.DataIn:
        raise ValueError("flow connect: data out must target data in")
      if not self._typesCompatible(src.typeId, dst.typeId):
        raise ValueError("flow connect: incompatible data types")
    else:
      raise ValueError("flow connect: invalid source pin kind")
    if src.nodeId == dst.nodeId:
      raise ValueError("flow connect: self loop")
    self._removeEdgesOnPin(toPin)
    eid: int = self.allocId()
    edge: FlowEdge = new()
    edge.id = eid
    edge.fromPin = fromPin
    edge.toPin = toPin
    self.edges.append(edge)
    return eid

  def execTarget(self, fromPin: int) -> int:
    for e in self.edges:
      if e.fromPin == fromPin:
        return e.toPin
    return -1

  def findPinOnNode(self, nodeId: int, name: str, kind: FlowPinEnum) -> int:
    node = self.findNode(nodeId)
    for p in node.pins:
      if p.name == name and p.kind == kind:
        return p.id
    return -1

  def dataSource(self, toPin: int) -> int:
    for e in self.edges:
      if e.toPin == toPin:
        return e.fromPin
    return -1

  def addNode(self, kindId: str, title: str, x: float64, y: float64, pins: list[FlowPin, 0]) -> int:
    nid: int = self.allocId()
    node: FlowNode = new()
    node.id = nid
    node.kindId = kindId
    node.title = title
    node.x = x
    node.y = y
    for p in pins:
      pin: FlowPin = new()
      pin.id = self.allocId()
      pin.nodeId = nid
      pin.name = p.name
      pin.kind = p.kind
      pin.typeId = p.typeId
      node.pins.append(pin)
    self.nodes.append(node)
    return nid

  def clear(self) -> None:
    for i in range(len(self.nodes) - 1, -1, -1):
      self.nodes.pop(i)
    for i in range(len(self.edges) - 1, -1, -1):
      self.edges.pop(i)
    self._nextId = 1

  def removeNode(self, nodeId: int) -> None:
    pinIds: list[int, 0] = []
    found: bool = False
    for i in range(len(self.nodes)):
      if self.nodes[i].id == nodeId:
        node: FlowNode = self.nodes[i]
        for p in node.pins:
          pinIds.append(p.id)
        self.nodes.pop(i)
        found = True
        break
    if not found:
      raise ValueError("flow node not found")
    for pid in pinIds:
      for j in range(len(self.edges) - 1, -1, -1):
        e: FlowEdge = self.edges[j]
        if e.fromPin == pid or e.toPin == pid:
          self.edges.pop(j)
