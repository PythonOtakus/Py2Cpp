"""蓝图式工作流编辑器示例（``py2cpp.ui.flow``）。"""
from py2cpp import *
from py2cpp.ui.flow.meta import FlowEventMeta, FlowNodeMeta, FlowPureMeta
from py2cpp.ui.flow.panel import UIFlowMixin


@dataclass
class ShooterLogic(UIFlowMixin):
  hp: int = 100
  ammo: int = 30

  @FlowEventMeta("Begin Play")
  def onBegin(self) -> None:
    pass

  @FlowNodeMeta("Fire", category="Combat")
  def fire(self, shots: int) -> bool:
    if self.ammo < shots:
      return False
    self.ammo -= shots
    return True

  @FlowPureMeta("HP")
  def getHp(self) -> int:
    return self.hp

  def onFlowReady(self) -> None:
    self._flowCanvas.addNodeFromKind("ShooterLogic.onBegin", 80.0, 80.0)
    self._flowCanvas.addNodeFromKind("ShooterLogic.fire", 320.0, 80.0)


def main() -> int:
  logic: ShooterLogic = new()
  return logic.showFlow("Shooter Blueprint", 1280, 720)
