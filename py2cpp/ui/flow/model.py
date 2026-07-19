"""``FlowGraph`` 数据模型与连线规则。"""
from ...builtins import *
from ...core.exceptions import ValueError


@enum
class FlowPinKind:
  ExecIn = 0
  ExecOut = 1
  DataIn = 2
  DataOut = 3


@enum
class FlowNodeKind:
  Callable = 0
  Pure = 1
  Event = 2
  Branch = 3
  ForLoop = 4


@copyable
class FlowPin:
  id: int = 0
  node_id: int = 0
  name: str = ""
  kind: FlowPinKind = FlowPinKind.DataIn
  type_id: str = "object"


@copyable
class FlowNode:
  id: int = 0
  kind_id: str = ""
  title: str = ""
  x: float64 = 0.0
  y: float64 = 0.0
  pins: list[FlowPin, 0] = []


@copyable
class FlowEdge:
  id: int = 0
  from_pin: int = 0
  to_pin: int = 0


@copyable
class FlowGraph:
  nodes: list[FlowNode, 0] = []
  edges: list[FlowEdge, 0] = []
  _next_id: int = 1

  def alloc_id(self) -> int:
    nid: int = self._next_id
    self._next_id += 1
    return nid

  def set_next_id(self, next_id: int) -> None:
    self._next_id = next_id

  def find_node(self, node_id: int) -> FlowNode:
    for n in self.nodes:
      if n.id == node_id:
        return n
    raise ValueError("flow node not found")

  def move_node(self, node_id: int, dx: float64, dy: float64) -> None:
    for i in range(len(self.nodes)):
      if self.nodes[i].id == node_id:
        node: FlowNode = self.nodes[i]
        node.x += dx
        node.y += dy
        self.nodes[i] = node
        return
    raise ValueError("flow node not found")

  def find_pin(self, pin_id: int) -> FlowPin:
    for n in self.nodes:
      for p in n.pins:
        if p.id == pin_id:
          return p
    raise ValueError("flow pin not found")

  def pin_node_id(self, pin_id: int) -> int:
    return self.find_pin(pin_id).node_id

  def _remove_edges_on_pin(self, pin_id: int) -> None:
    for i in range(len(self.edges) - 1, -1, -1):
      e: FlowEdge = self.edges[i]
      if e.from_pin == pin_id or e.to_pin == pin_id:
        self.edges.pop(i)

  def _pin_accepts_input(self, pin: FlowPin) -> bool:
    return pin.kind in {FlowPinKind.ExecIn, FlowPinKind.DataIn}

  def _pin_accepts_output(self, pin: FlowPin) -> bool:
    return pin.kind in {FlowPinKind.ExecOut, FlowPinKind.DataOut}

  def _types_compatible(self, out_tid: str, in_tid: str) -> bool:
    if out_tid == in_tid:
      return True
    if in_tid == "object":
      return True
    return False

  def connect(self, from_pin: int, to_pin: int) -> int:
    src: FlowPin = self.find_pin(from_pin)
    dst: FlowPin = self.find_pin(to_pin)
    if not self._pin_accepts_output(src):
      raise ValueError("flow connect: source must be output pin")
    if not self._pin_accepts_input(dst):
      raise ValueError("flow connect: target must be input pin")
    if src.kind == FlowPinKind.ExecOut:
      if dst.kind != FlowPinKind.ExecIn:
        raise ValueError("flow connect: exec out must target exec in")
    elif src.kind == FlowPinKind.DataOut:
      if dst.kind != FlowPinKind.DataIn:
        raise ValueError("flow connect: data out must target data in")
      if not self._types_compatible(src.type_id, dst.type_id):
        raise ValueError("flow connect: incompatible data types")
    else:
      raise ValueError("flow connect: invalid source pin kind")
    if src.node_id == dst.node_id:
      raise ValueError("flow connect: self loop")
    self._remove_edges_on_pin(to_pin)
    eid: int = self.alloc_id()
    edge: FlowEdge = new()
    edge.id = eid
    edge.from_pin = from_pin
    edge.to_pin = to_pin
    self.edges.append(edge)
    return eid

  def exec_target(self, from_pin: int) -> int:
    for e in self.edges:
      if e.from_pin == from_pin:
        return e.to_pin
    return -1

  def find_pin_on_node(self, node_id: int, name: str, kind: FlowPinKind) -> int:
    node = self.find_node(node_id)
    for p in node.pins:
      if p.name == name and p.kind == kind:
        return p.id
    return -1

  def data_source(self, to_pin: int) -> int:
    for e in self.edges:
      if e.to_pin == to_pin:
        return e.from_pin
    return -1

  def add_node(self, kind_id: str, title: str, x: float64, y: float64, pins: list[FlowPin, 0]) -> int:
    nid: int = self.alloc_id()
    node: FlowNode = new()
    node.id = nid
    node.kind_id = kind_id
    node.title = title
    node.x = x
    node.y = y
    for p in pins:
      pin: FlowPin = new()
      pin.id = self.alloc_id()
      pin.node_id = nid
      pin.name = p.name
      pin.kind = p.kind
      pin.type_id = p.type_id
      node.pins.append(pin)
    self.nodes.append(node)
    return nid

  def clear(self) -> None:
    for i in range(len(self.nodes) - 1, -1, -1):
      self.nodes.pop(i)
    for i in range(len(self.edges) - 1, -1, -1):
      self.edges.pop(i)
    self._next_id = 1

  def remove_node(self, node_id: int) -> None:
    pin_ids: list[int, 0] = []
    found: bool = False
    for i in range(len(self.nodes)):
      if self.nodes[i].id == node_id:
        node: FlowNode = self.nodes[i]
        for p in node.pins:
          pin_ids.append(p.id)
        self.nodes.pop(i)
        found = True
        break
    if not found:
      raise ValueError("flow node not found")
    for pid in pin_ids:
      for j in range(len(self.edges) - 1, -1, -1):
        e: FlowEdge = self.edges[j]
        if e.from_pin == pid or e.to_pin == pid:
          self.edges.pop(j)
