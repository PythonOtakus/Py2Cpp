"""MidIR 直读 passes（N3）。旧 ``src/passes`` 仍经 materialize AST。"""

from .apply_mid_decls import (
  apply_mid_class_flags,
  apply_mid_enum_flags,
  expand_enums_from_mid,
  nested_variant_classdefs_from_mid,
  record_field_specs_from_mid,
  register_module_from_mid,
)

__all__ = [
  "apply_mid_class_flags",
  "apply_mid_enum_flags",
  "expand_enums_from_mid",
  "nested_variant_classdefs_from_mid",
  "record_field_specs_from_mid",
  "register_module_from_mid",
]
