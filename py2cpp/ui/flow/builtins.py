"""Flow 内置控制流节点（Branch / For Loop）。"""
from ...builtins import *
from .catalog import FlowNodeCatalog, FlowPinSpec
from .model import FlowNodeKind, FlowPinKind


BRANCH_KIND: str = "flow.builtin.branch"
FOR_LOOP_KIND: str = "flow.builtin.for_loop"
BUILTIN_CATEGORY: str = "Flow Control"


def _exec_in() -> FlowPinSpec:
  p: FlowPinSpec = new()
  p.name = "execute"
  p.kind = FlowPinKind.ExecIn
  return p


def _exec_out(name: str) -> FlowPinSpec:
  p: FlowPinSpec = new()
  p.name = name
  p.kind = FlowPinKind.ExecOut
  return p


def _data_in(name: str, type_id: str) -> FlowPinSpec:
  p: FlowPinSpec = new()
  p.name = name
  p.kind = FlowPinKind.DataIn
  p.type_id = type_id
  return p


def register_flow_builtins(catalog: FlowNodeCatalog @ref) -> None:
  branch_pins: list[FlowPinSpec, 0] = []
  branch_pins.append(_exec_in())
  branch_pins.append(_data_in("condition", "bool"))
  branch_pins.append(_exec_out("OnTrue"))
  branch_pins.append(_exec_out("OnFalse"))
  catalog.register(BRANCH_KIND, "Branch", BUILTIN_CATEGORY, FlowNodeKind.Branch, "", branch_pins)
  loop_pins: list[FlowPinSpec, 0] = []
  loop_pins.append(_exec_in())
  loop_pins.append(_data_in("count", "int"))
  loop_pins.append(_exec_out("LoopBody"))
  loop_pins.append(_exec_out("Completed"))
  catalog.register(FOR_LOOP_KIND, "For Loop", BUILTIN_CATEGORY, FlowNodeKind.ForLoop, "", loop_pins)
