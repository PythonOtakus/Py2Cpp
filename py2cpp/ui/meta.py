"""Panel 字段元数据（``@annotation`` / ``*Meta``）。"""
from ..builtins import *


@annotation
class UIInvisibleMeta:
  """不参与 ``draw_panel``；可与其它 ``@`` 叠用。"""


@annotation
@dataclass
class UILabelMeta:
  """覆盖显示标签；``name @UILabelMeta("显示名")``；用 ``Self.get_annotation[UILabelMeta](field)`` 读取 ``.text``。"""

  text: str


@annotation
@dataclass
class UISliderMeta:
  """整型滑条；``hp: int @UISliderMeta(0, 100)``；可与 ``@UILabelMeta`` 叠用。"""

  lo: int
  hi: int


@annotation
@dataclass
class UIButtonMeta:
  """方法级按钮；``@UIButtonMeta()`` 标签为方法名；``@UIButtonMeta("保存")`` 覆盖。"""

  label: str = ""
