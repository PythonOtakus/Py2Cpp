"""解析成员访问级别并写入 ``ClassInfo.member_access``。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..analysis.access import (
  resolve_member_access,
  validate_module_friend_names,
  validate_no_external_protected_access,
)

if TYPE_CHECKING:
  from ..translator import Translator


def expand_member_access(translator: Translator) -> None:
  validate_module_friend_names(translator.classes)
  validate_no_external_protected_access(
    translator.classes,
    translator.module_functions,
    translator.module_asts,
    translator.import_bindings,
    module_debug_files=translator.module_debug_files,
  )
  resolve_member_access(
    translator.classes,
    translator.module_functions,
    translator.module_asts,
    translator.import_bindings,
  )
