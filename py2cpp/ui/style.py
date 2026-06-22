"""Panel 面板样式（字体、颜色、布局 metrics）。"""
from ..builtins import *


@dataclass(eq=False, repr=False)
class UIStyle:
  """Win32 Panel 主题；逻辑像素，``UIWindow.show`` 时按窗口 DPI 缩放。"""

  font_name: str = "Segoe UI"
  font_size: int = 11
  text_color: (int, int, int) = (0, 0, 0)
  panel_color: (int, int, int) = (243, 243, 243)
  margin: (int, int) = (12, 10)
  label_size: (int, int) = (88, 22)
  edit_size: (int, int) = (260, 22)
  slider_size: (int, int) = (260, 22)
  checkbox_size: (int, int) = (18, 18)
  button_size: (int, int) = (260, 22)
  row_spacing: int = 4
  form_spacing: int = 8
