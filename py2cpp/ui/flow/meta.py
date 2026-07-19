"""蓝图节点方法级元数据（``@annotation``）。"""
from ...builtins import *


@annotation
@dataclass
class FlowNodeMeta:
  """可调用节点（Exec In/Out + 数据引脚；≈ UE BlueprintCallable）。"""

  title: str = ""
  category: str = ""
  hidden: bool = False
  inheritable: bool = True


@annotation
@dataclass
class FlowPureMeta:
  """纯节点（仅数据引脚；≈ UE BlueprintPure）。"""

  title: str = ""
  category: str = ""
  hidden: bool = False
  inheritable: bool = True


@annotation
@dataclass
class FlowEventMeta:
  """入口事件（仅 Exec Out；≈ UE Event BeginPlay）。"""

  title: str = ""
  category: str = "Events"
  hidden: bool = False
  inheritable: bool = True
