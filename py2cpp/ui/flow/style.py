"""蓝图画布主题。"""
from ...builtins import *


@dataclass(eq=False, repr=False)
class UIFlowStyle:
  bgColor: (int, int, int) = (30, 30, 30)
  gridMinor: (int, int, int) = (45, 45, 48)
  gridMajor: (int, int, int) = (55, 55, 60)
  nodeTitle: (int, int, int) = (0, 122, 204)
  nodeBody: (int, int, int) = (37, 37, 38)
  nodeBorder: (int, int, int) = (60, 60, 60)
  nodeSelected: (int, int, int) = (255, 198, 0)
  textColor: (int, int, int) = (240, 240, 240)
  pinLabelColor: (int, int, int) = (200, 200, 200)
  wireExec: (int, int, int) = (220, 220, 220)
  wireData: (int, int, int) = (100, 180, 255)
  gridMinorStep: int = 16
  gridMajorStep: int = 128
  fontSize: int = 15
  titleFontSize: int = 16
  paletteFontSize: int = 15
