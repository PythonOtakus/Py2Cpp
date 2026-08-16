"""UI 控件事件委托（Qt-like；基于 ``@delegate``）。

- ``UIEventDelegate``：无参信号（如 ``QPushButton.clicked``）
- ``UIValueChangedDelegate[T]``：单参值变更（如 ``QSlider.valueChanged``）
"""

from ..builtins import *


@delegate
def UIEventDelegate() -> None: ...


@delegate
def UIValueChangedDelegate[T](value: T) -> None: ...
