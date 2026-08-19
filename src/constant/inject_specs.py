"""``@native`` / codegen ``.inl`` 注入规格（模块路径 + impl 键或 ``+*.inl`` 模板）。"""

PASTE_BEFORE_SPECS: tuple[tuple[str, str], ...] = ()

# 尚未迁 ``templates/**/+*.inl`` 的模块仍用 ``*_cpp.py`` impl 键。
PASTE_AFTER_SPECS: tuple[tuple[str, str], ...] = (
  ("core/exceptions", "exceptions_group"),
)

CLASS_PASTE_SPECS: dict[str, tuple[str, ...]] = {}

# 类级 inject 模板：``~`` 片段或 ``+stem`` 无法映射模块时在此登记（须同时在 ``CLASS_PASTE_MODULE_REL``）。
CLASS_PASTE_TEMPLATE_SPECS: dict[str, tuple[str, ...]] = {
  "PyDelegate": ("core/~delegate_class.inl",),
}

CLASS_PASTE_MODULE_REL: dict[str, str] = {
  "PyDelegate": "core/delegate",
}

# 这些 ``+*.inl`` 改注入模块 ``.h``（库 TU 跳过非模板 ``.inl`` 时仍须可见）。
PASTE_AFTER_TO_HEADER_MODULE_RELS = frozenset({"text/bytes"})

# codegen 完整实现模板：由 ``layout_emit`` 等直接 ``expand_template`` 写盘，无 ``py2cpp/`` 模块、不参与 paste/inject 发现。
CODEGEN_STANDALONE_TEMPLATE_RELS: frozenset[str] = frozenset({
  "operators.h",
  "operators.inl",
  "char.h",
  "byte.h",
  "c_str.h",
  "py_types.h",
  "member_access.h",
  "debug.inl",
  "minimal.h",
  "core/exception_group_fallback.inl",
})

# 兼容旧名（paste 发现等仍 import 此符号）
CODEGEN_INJECT_TEMPLATE_RELS = CODEGEN_STANDALONE_TEMPLATE_RELS
