"""交互式 Panel 演示（Win32 窗口；关闭窗口退出）。"""
from py2cpp import *
from py2cpp.ui.meta import UIButtonMeta, UIInvisibleMeta, UILabelMeta, UISliderMeta
from py2cpp.ui.panel import UIPanelMixin


@dataclass
class PlayerConfig(UIPanelMixin):
  hp: int @UILabelMeta("HP") @UISliderMeta(0, 100) = 50
  name: str @UILabelMeta("Name") = "hero"
  enabled: bool = True
  clicks: int @UILabelMeta("Clicks") = 0
  _seed: int @UIInvisibleMeta = 0

  @UIButtonMeta()
  def apply(self) -> None:
    self.clicks += 1

  @UIButtonMeta("重置 HP")
  def resetHp(self) -> None:
    self.hp = 50


def main() -> int:
  cfg: PlayerConfig = new()
  return cfg.showPanel()


if __name__ == "__main__":
  raise SystemExit(main())
