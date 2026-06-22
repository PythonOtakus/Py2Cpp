"""UI 控件事件委托（Qt-like；基于 ``@delegate``）。

- ``UIEvent``：无参信号（如 ``QPushButton.clicked``）
- ``UIValueChanged[T]``：单参值变更（如 ``QSlider.valueChanged``）
"""

from ..builtins import *


@delegate
def UIEvent() -> None: ...


@delegate
def UIValueChanged[T](value: T) -> None: ...
