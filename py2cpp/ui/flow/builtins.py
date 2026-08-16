"""Flow 内置控制流节点（Branch / For Loop）。"""
from ...builtins import *
from .catalog import FlowNodeCatalog, FlowPinSpec
from .model import FlowNodeEnum, FlowPinEnum


BranchKind: str = "flow.builtin.branch"
ForLoopKind: str = "flow.builtin.for_loop"
BuiltinCategory: str = "Flow Control"


def _execIn() -> FlowPinSpec:
  p: FlowPinSpec = new()
  p.name = "execute"
  p.kind = FlowPinEnum.ExecIn
  return p


def _execOut(name: str) -> FlowPinSpec:
  p: FlowPinSpec = new()
  p.name = name
  p.kind = FlowPinEnum.ExecOut
  return p


def _dataIn(name: str, typeId: str) -> FlowPinSpec:
  p: FlowPinSpec = new()
  p.name = name
  p.kind = FlowPinEnum.DataIn
  p.typeId = typeId
  return p


def registerFlowBuiltins(catalog: FlowNodeCatalog @ref) -> None:
  branchPins: list[FlowPinSpec, 0] = []
  branchPins.append(_execIn())
  branchPins.append(_dataIn("condition", "bool"))
  branchPins.append(_execOut("OnTrue"))
  branchPins.append(_execOut("OnFalse"))
  catalog.register(BranchKind, "Branch", BuiltinCategory, FlowNodeEnum.Branch, "", branchPins)
  loopPins: list[FlowPinSpec, 0] = []
  loopPins.append(_execIn())
  loopPins.append(_dataIn("count", "int"))
  loopPins.append(_execOut("LoopBody"))
  loopPins.append(_execOut("Completed"))
  catalog.register(ForLoopKind, "For Loop", BuiltinCategory, FlowNodeEnum.ForLoop, "", loopPins)
