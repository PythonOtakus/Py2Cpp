"""译期节点模板目录（``FlowNodeCatalog``）。"""
from ...builtins import *
from ...core.exceptions import ValueError
from .model import FlowNodeEnum, FlowPin, FlowPinEnum


@copyable
class FlowPinSpec:
  name: str = ""
  kind: FlowPinEnum = FlowPinEnum.DataIn
  typeId: str = "object"


@copyable
class FlowNodeTemplate:
  kindId: str = ""
  title: str = ""
  category: str = ""
  nodeKind: FlowNodeEnum = FlowNodeEnum.Callable
  methodName: str = ""
  pins: list[FlowPinSpec, 0] = []


@copyable
class FlowNodeCatalog:
  templates: list[FlowNodeTemplate, 0] = []

  def clear(self) -> None:
    for i in range(len(self.templates) - 1, -1, -1):
      self.templates.pop(i)

  def register(
    self,
    kindId: str,
    title: str,
    category: str,
    nodeKind: FlowNodeEnum,
    methodName: str,
    pins: list[FlowPinSpec, 0],
  ) -> None:
    tpl: FlowNodeTemplate = new(
      kindId=kindId,
      title=title,
      category=category,
      nodeKind=nodeKind,
      methodName=methodName,
    )
    for spec in pins:
      ps: FlowPinSpec = new(name=spec.name, kind=spec.kind, typeId=spec.typeId)
      tpl.pins.append(ps)
    self.templates.append(tpl)

  def find(self, kindId: str) -> FlowNodeTemplate:
    for tpl in self.templates:
      if tpl.kindId == kindId:
        return tpl
    raise ValueError("flow template not found")

  def clonePins(self, kindId: str) -> list[FlowPin, 0]:
    tpl: FlowNodeTemplate = self.find(kindId)
    out: list[FlowPin, 0] = []
    for spec in tpl.pins:
      p: FlowPin = new(name=spec.name, kind=spec.kind, typeId=spec.typeId)
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
    eventsFirst: list[str, 0] = []
    rest: list[str, 0] = []
    for c in out:
      if c == "Events":
        eventsFirst.append(c)
      else:
        rest.append(c)
    merged: list[str, 0] = []
    for c in eventsFirst:
      merged.append(c)
    for c in rest:
      merged.append(c)
    return merged

  def entriesIn(self, category: str) -> list[FlowNodeTemplate, 0]:
    out: list[FlowNodeTemplate, 0] = []
    for tpl in self.templates:
      if tpl.category == category:
        out.append(tpl)
    return out

  def tipText(self, kindId: str) -> str:
    tpl: FlowNodeTemplate = self.find(kindId)
    tip: str = tpl.title
    tip = tip + "\n" + kindId
    for spec in tpl.pins:
      line: str = spec.name
      if spec.kind in {FlowPinEnum.DataIn, FlowPinEnum.DataOut}:
        line = line + ":" + spec.typeId
      tip = tip + "\n" + line
    return tip
