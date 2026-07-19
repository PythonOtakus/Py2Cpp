"""蓝图画布主题。"""
from ...builtins import *


@dataclass(eq=False, repr=False)
class UIFlowStyle:
  bg_color: (int, int, int) = (30, 30, 30)
  grid_minor: (int, int, int) = (45, 45, 48)
  grid_major: (int, int, int) = (55, 55, 60)
  node_title: (int, int, int) = (0, 122, 204)
  node_body: (int, int, int) = (37, 37, 38)
  node_border: (int, int, int) = (60, 60, 60)
  node_selected: (int, int, int) = (255, 198, 0)
  text_color: (int, int, int) = (240, 240, 240)
  pin_label_color: (int, int, int) = (200, 200, 200)
  wire_exec: (int, int, int) = (220, 220, 220)
  wire_data: (int, int, int) = (100, 180, 255)
  grid_minor_step: int = 16
  grid_major_step: int = 128
  font_size: int = 15
  title_font_size: int = 16
  palette_font_size: int = 15
