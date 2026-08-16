"""Flow 图运行时：Event 入口、Exec 链、Pure 求值、Branch/ForLoop。"""
from ...builtins import *
from .catalog import FlowNodeCatalog
from .model import FlowGraph, FlowNodeEnum, FlowPinEnum


@dataclass
class FlowRuntime:
  cancelled: bool = False
  _pureCacheNode: list[int, 0] @optional = []
  _pureCacheVal: list[int, 0] @optional = []

  def reset(self) -> None:
    self.cancelled = False
    self._pureCacheNode.clear()
    self._pureCacheVal.clear()

  def stop(self) -> None:
    self.cancelled = True

  def _cachePure(self, nodeId: int, val: int) -> None:
    self._pureCacheNode.append(nodeId)
    self._pureCacheVal.append(val)

  def _cachedPure(self, nodeId: int) -> int:
    i: int = 0
    for nid in self._pureCacheNode:
      if nid == nodeId:
        return self._pureCacheVal[i]
      i += 1
    return 0

  def _hasPureCache(self, nodeId: int) -> bool:
    for nid in self._pureCacheNode:
      if nid == nodeId:
        return True
    return False

  def evalDataPin[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    nodeId: int,
    pinName: str,
  ) -> int:
    pinId: int = graph.findPinOnNode(nodeId, pinName, FlowPinEnum.DataIn)
    if pinId < 0:
      return 0
    src: int = graph.dataSource(pinId)
    if src < 0:
      return 0
    return self._evalDataOut(graph, catalog, host, src)

  def _evalDataOut[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    outPin: int,
  ) -> int:
    srcNodeId: int = graph.pinNodeId(outPin)
    if self._hasPureCache(srcNodeId):
      return self._cachedPure(srcNodeId)
    node = graph.findNode(srcNodeId)
    tpl = catalog.find(node.kindId)
    if tpl.nodeKind != FlowNodeEnum.Pure:
      return 0
    val: int = host.flowInvokePure(tpl.methodName)
    self._cachePure(srcNodeId, val)
    return val

  def runAll[T](self, graph: FlowGraph @ref, catalog: FlowNodeCatalog @ref, host: T @ref) -> None:
    self.reset()
    for node in graph.nodes:
      tpl = catalog.find(node.kindId)
      if tpl.nodeKind == FlowNodeEnum.Event:
        self.runFromEvent(graph, catalog, host, node.id)

  def runFromEvent[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    eventNodeId: int,
  ) -> None:
    self.reset()
    thenPin: int = graph.findPinOnNode(eventNodeId, "then", FlowPinEnum.ExecOut)
    if thenPin < 0:
      return
    self._runFromExecOut(graph, catalog, host, thenPin)

  def runFromSelected[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    nodeId: int,
  ) -> None:
    self.reset()
    node = graph.findNode(nodeId)
    tpl = catalog.find(node.kindId)
    if tpl.nodeKind == FlowNodeEnum.Event:
      self.runFromEvent(graph, catalog, host, nodeId)
      return
    execIn: int = graph.findPinOnNode(nodeId, "execute", FlowPinEnum.ExecIn)
    if execIn < 0:
      return
    self._stepExec(graph, catalog, host, execIn)

  def _runFromExecOut[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    outPin: int,
  ) -> None:
    cur: int = outPin
    while cur >= 0:
      if self.cancelled:
        return
      target: int = graph.execTarget(cur)
      if target < 0:
        return
      cur = self._stepExec(graph, catalog, host, target)

  def _stepExec[T](
    self,
    graph: FlowGraph @ref,
    catalog: FlowNodeCatalog @ref,
    host: T @ref,
    execInPin: int,
  ) -> int:
    if self.cancelled:
      return -1
    nodeId: int = graph.pinNodeId(execInPin)
    node = graph.findNode(nodeId)
    tpl = catalog.find(node.kindId)
    match tpl.nodeKind:
      case FlowNodeEnum.Callable:
        host.flowInvokeCallable(tpl.methodName, graph, nodeId, self)
        return graph.findPinOnNode(nodeId, "then", FlowPinEnum.ExecOut)
      case FlowNodeEnum.Branch:
        cond: int = self.evalDataPin(graph, catalog, host, nodeId, "condition")
        branchOut: int = -1
        if cond:
          branchOut = graph.findPinOnNode(nodeId, "OnTrue", FlowPinEnum.ExecOut)
        else:
          branchOut = graph.findPinOnNode(nodeId, "OnFalse", FlowPinEnum.ExecOut)
        self._runFromExecOut(graph, catalog, host, branchOut)
        return -1
      case FlowNodeEnum.ForLoop:
        count: int = self.evalDataPin(graph, catalog, host, nodeId, "count")
        bodyOut: int = graph.findPinOnNode(nodeId, "LoopBody", FlowPinEnum.ExecOut)
        for i in range(count):
          if self.cancelled:
            return -1
          self._runFromExecOut(graph, catalog, host, bodyOut)
        return graph.findPinOnNode(nodeId, "Completed", FlowPinEnum.ExecOut)
      case _:
        return -1
