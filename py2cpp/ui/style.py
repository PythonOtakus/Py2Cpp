"""Panel 面板样式（字体、颜色、布局 metrics）。"""
from ..builtins import *


@dataclass(eq=False, repr=False)
class UIStyle:
  """Win32 Panel 主题；逻辑像素，``UIWindow.show`` 时按窗口 DPI 缩放。"""

  fontName: str = "Segoe UI"
  fontSize: int = 11
  textColor: (int, int, int) = (0, 0, 0)
  panelColor: (int, int, int) = (243, 243, 243)
  margin: (int, int) = (12, 10)
  # 表单控件左缘额外偏移（一体窗右栏 Inspector 等）
  formOriginX: int = 0
  formOriginY: int = 0
  labelSize: (int, int) = (88, 22)
  editSize: (int, int) = (260, 22)
  sliderSize: (int, int) = (260, 22)
  checkboxSize: (int, int) = (18, 18)
  buttonSize: (int, int) = (260, 22)
  rowSpacing: int = 4
  formSpacing: int = 8
