"""``py2cpp.console`` 包根：``Console`` 与常用再导出。

设计见 ``docs/console.md``。``Console`` 实现在 ``core``；标准流经 ``Console.stdio`` 绑定，``owns=False``。
"""
from ..builtins import *

from .core import Console
from .exceptions import (
  ArgumentError,
  ConsoleError,
  RenderError,
  TaskError,
  TaskExitError,
  TaskStartError,
  TaskTimeoutError,
)
from .popen import Pipe, Popen, ProcessResult
from .parse import ArgumentParserMixin, FlagArgMeta, OptArgMeta, PosArgMeta
