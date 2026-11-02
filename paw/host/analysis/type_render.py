"""TypeNode → C++ 文本：命名策略（模板头 ``_Key`` vs 类体 ``Key``）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .ir import cpp_type_param_template_name


@dataclass(frozen=True)
class NamingPolicy:
  """形参与其它标识符在 render 时的拼写策略。"""

  type_param: Callable[[str], str]

  def format_type_param(self, name: str) -> str:
    return self.type_param(name)


def _identity_type_param(name: str) -> str:
  return name


TEMPLATE_HEADER = NamingPolicy(type_param=cpp_type_param_template_name)
CLASS_BODY = NamingPolicy(type_param=_identity_type_param)
STORAGE = CLASS_BODY
