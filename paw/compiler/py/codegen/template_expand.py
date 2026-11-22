"""Shim parity with ``compiler/paw/codegen/template_expand.paw``.

生产展开仍走 ``host.codegen.expand_py2cpp_template``；Paw 冻结子集
``expandTemplateFrozen`` 供自举链 / 原生驱动。
"""
# Intentionally empty re-export surface — host owns full expand.
