"""译期节点模板目录（``FlowNodeCatalog``）。"""
from ...builtins import *
from ...core.exceptions import ValueError
from .model import FlowNodeKind, FlowPin, FlowPinKind


@copyable
class FlowPinSpec:
  name: str = ""
  kind: FlowPinKind = FlowPinKind.DataIn
  type_id: str = "object"


@copyable
class FlowNodeTemplate:
  kind_id: str = ""
  title: str = ""
  category: str = ""
  node_kind: FlowNodeKind = FlowNodeKind.Callable
  method_name: str = ""
  pins: list[FlowPinSpec, 0] = []


@copyable
class FlowNodeCatalog:
  templates: list[FlowNodeTemplate, 0] = []

  def clear(self) -> None:
    for i in range(len(self.templates) - 1, -1, -1):
      self.templates.pop(i)

  def register(
    self,
    kind_id: str,
    title: str,
    category: str,
    node_kind: FlowNodeKind,
    method_name: str,
    pins: list[FlowPinSpec, 0],
  ) -> None:
    tpl: FlowNodeTemplate = new()
    tpl.kind_id = kind_id
    tpl.title = title
    tpl.category = category
    tpl.node_kind = node_kind
    tpl.method_name = method_name
    for spec in pins:
      ps: FlowPinSpec = new()
      ps.name = spec.name
      ps.kind = spec.kind
      ps.type_id = spec.type_id
      tpl.pins.append(ps)
    self.templates.append(tpl)

  def find(self, kind_id: str) -> FlowNodeTemplate:
    for tpl in self.templates:
      if tpl.kind_id == kind_id:
        return tpl
    raise ValueError("flow template not found")

  def clone_pins(self, kind_id: str) -> list[FlowPin, 0]:
    tpl: FlowNodeTemplate = self.find(kind_id)
    out: list[FlowPin, 0] = []
    for spec in tpl.pins:
      p: FlowPin = new()
      p.name = spec.name
      p.kind = spec.kind
      p.type_id = spec.type_id
      out.append(p)
    return out

  def categories(self) -> list[str, 0]:
    out: list[str, 0] = []
    for tpl in self.templates:
      if not tpl.category:
        continue
      found: bool = False
      for c in out:
        if c == tpl.category:
          found = True
          break
      if not found:
        out.append(tpl.category)
    events_first: list[str, 0] = []
    rest: list[str, 0] = []
    for c in out:
      if c == "Events":
        events_first.append(c)
      else:
        rest.append(c)
    merged: list[str, 0] = []
    for c in events_first:
      merged.append(c)
    for c in rest:
      merged.append(c)
    return merged

  def entries_in(self, category: str) -> list[FlowNodeTemplate, 0]:
    out: list[FlowNodeTemplate, 0] = []
    for tpl in self.templates:
      if tpl.category == category:
        out.append(tpl)
    return out

  def tip_text(self, kind_id: str) -> str:
    tpl: FlowNodeTemplate = self.find(kind_id)
    tip: str = tpl.title
    tip = tip + "\n" + kind_id
    for spec in tpl.pins:
      line: str = spec.name
      if spec.kind in {FlowPinKind.DataIn, FlowPinKind.DataOut}:
        line = line + ":" + spec.type_id
      tip = tip + "\n" + line
    return tip
