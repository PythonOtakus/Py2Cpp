"""``UIFlowMixin``：译期 ``iterMethods`` + 方法签名反射 → ``FlowNodeCatalog``。"""
from ...builtins import *
from ..app import UIApp
from ..window import UIWindow
from .builtins import registerFlowBuiltins
from .canvas import UIFlowCanvas
from .catalog import FlowNodeCatalog, FlowPinSpec
from .meta import FlowEventMeta, FlowNodeMeta, FlowPureMeta
from .model import FlowGraph, FlowNodeEnum, FlowPinEnum
from .runtime import FlowRuntime
from .shell import UIFlowShell


@mixin
class UIFlowMixin:
  _flowCanvas: UIFlowCanvas = new()
  _flowShell: UIFlowShell = new()
  _flowCatalog: FlowNodeCatalog = new()
  _flowCatalogReady: bool = False
  _flowRuntime: FlowRuntime = new()
  _flowWin: UIWindow = new()

  @staticmethod
  def _flowTypeId[T]() -> str:
    if T is bool:
      return "bool"
    elif T is int:
      return "int"
    elif T is float or T is float64:
      return "float"
    elif T is str:
      return "str"
    else:
      return "object"

  def _flowPinExecIn(self) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = "execute"
    p.kind = FlowPinEnum.ExecIn
    return p

  def _flowPinExecOut(self) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = "then"
    p.kind = FlowPinEnum.ExecOut
    return p

  def _flowPinDataIn(self, name: str, typeId: str) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = name
    p.kind = FlowPinEnum.DataIn
    p.typeId = typeId
    return p

  def _flowPinDataOut(self, name: str, typeId: str) -> FlowPinSpec:
    p: FlowPinSpec = new()
    p.name = name
    p.kind = FlowPinEnum.DataOut
    p.typeId = typeId
    return p

  def _registerFlowNode(
    self,
    method: str,
    metaTitle: str,
    metaCategory: str,
    nodeKind: FlowNodeEnum,
    pins: list[FlowPinSpec, 0],
  ) -> None:
    title: str = metaTitle
    if not title:
      title = method
    category: str = metaCategory
    if not category:
      category = Self.__name__
    kindId: str = Self.__name__ + "." + method
    self._flowCatalog.register(kindId, title, category, nodeKind, method, pins)

  def _ensureFlowCatalog(self) -> None:
    if self._flowCatalogReady:
      return
    self._flowCatalog.clear()
    for method in Self.iterMethods[FlowNodeMeta](mro=True):
      if Self.getMethodAnnotation[FlowNodeMeta](method) is None or not Self.getMethodAnnotation[FlowNodeMeta](method).hidden:
        title: str = ""
        category: str = ""
        if Self.getMethodAnnotation[FlowNodeMeta](method) is not None:
          title = Self.getMethodAnnotation[FlowNodeMeta](method).title
          category = Self.getMethodAnnotation[FlowNodeMeta](method).category
        pins: list[FlowPinSpec, 0] = []
        pins.append(self._flowPinExecIn())
        pins.append(self._flowPinExecOut())
        for param in Self.iterMethodParams(method):
          pins.append(self._flowPinDataIn(param, self._flowTypeId[Self.getMethodParamType(method, param)]()))
        if Self.getMethodReturnType(method) is not None:
          pins.append(self._flowPinDataOut("Return Value", self._flowTypeId[Self.getMethodReturnType(method)]()))
        self._registerFlowNode(method, title, category, FlowNodeEnum.Callable, pins)
    for method in Self.iterMethods[FlowPureMeta](mro=True):
      if Self.getMethodAnnotation[FlowPureMeta](method) is None or not Self.getMethodAnnotation[FlowPureMeta](method).hidden:
        title: str = ""
        category: str = ""
        if Self.getMethodAnnotation[FlowPureMeta](method) is not None:
          title = Self.getMethodAnnotation[FlowPureMeta](method).title
          category = Self.getMethodAnnotation[FlowPureMeta](method).category
        pins: list[FlowPinSpec, 0] = []
        for param in Self.iterMethodParams(method):
          pins.append(self._flowPinDataIn(param, self._flowTypeId[Self.getMethodParamType(method, param)]()))
        if Self.getMethodReturnType(method) is not None:
          pins.append(self._flowPinDataOut("Return Value", self._flowTypeId[Self.getMethodReturnType(method)]()))
        self._registerFlowNode(method, title, category, FlowNodeEnum.Pure, pins)
    for method in Self.iterMethods[FlowEventMeta](mro=True):
      if Self.getMethodAnnotation[FlowEventMeta](method) is None or not Self.getMethodAnnotation[FlowEventMeta](method).hidden:
        title: str = ""
        category: str = "Events"
        if Self.getMethodAnnotation[FlowEventMeta](method) is not None:
          title = Self.getMethodAnnotation[FlowEventMeta](method).title
          if Self.getMethodAnnotation[FlowEventMeta](method).category:
            category = Self.getMethodAnnotation[FlowEventMeta](method).category
        pins: list[FlowPinSpec, 0] = []
        pins.append(self._flowPinExecOut())
        self._registerFlowNode(method, title, category, FlowNodeEnum.Event, pins)
    registerFlowBuiltins(self._flowCatalog)
    self._flowCatalogReady = True

  def flowInvokeCallable(
    self,
    method: str,
    graph: FlowGraph @ref,
    nodeId: int,
    rt: FlowRuntime @ref,
  ) -> None:
    # 动态 ``getattr(self, method)`` 不受支持；宿主 ``@override`` 按方法名派发。
    return

  def flowInvokePure(self, method: str) -> int:
    return 0

  def _wireFlowShell(self) -> None:
    self._flowShell.catalog = self._flowCatalog
    self._flowCanvas.catalog = self._flowCatalog
    self._flowShell.runPlay += self.onFlowRun
    self._flowShell.runPlaySelected += self.onFlowRunFromSelected
    self._flowShell.runStop += self.onFlowStop

  def drawFlow(self, win: UIWindow @ref) -> None:
    self._ensureFlowCatalog()
    self._flowWin = win
    self._wireFlowShell()
    self._flowShell.attach(win, self._flowCanvas)
    self._flowShell.menu.setRunEnabled(True, True, True)

  def onFlowReady(self) -> None:
    pass

  def onFlowRun(self) -> None:
    self._flowRuntime.runAll(self._flowCanvas.graph, self._flowCatalog, self)

  def onFlowRunFromSelected(self) -> None:
    nid: int = self._flowCanvas.selectedNode
    if nid < 0:
      return
    self._flowRuntime.runFromSelected(self._flowCanvas.graph, self._flowCatalog, self, nid)

  def onFlowStop(self) -> None:
    self._flowRuntime.stop()

  def createFlow(self, title: str = "", width: int = -1, height: int = -1) -> UIWindow:
    self._flowWin = new()
    if not UIApp.isAvailable():
      return self._flowWin
    self._ensureFlowCatalog()
    self._wireFlowShell()
    self._flowWin.title = title
    if not self._flowWin.title:
      self._flowWin.title = Self.__name__
    self._flowWin.show(width, height)
    self.drawFlow(self._flowWin)
    if width < 0 or height < 0:
      self._flowWin.resize(width, height)
    self.onFlowReady()
    return self._flowWin

  def showFlow(self, title: str = "", width: int = 1280, height: int = 720) -> int:
    if not UIApp.isAvailable():
      return 1
    win: UIWindow = self.createFlow(title, width, height)
    return UIApp.run()
