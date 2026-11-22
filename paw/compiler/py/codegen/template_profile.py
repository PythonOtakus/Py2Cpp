"""Shim: production template profile remains ``host.codegen.template_profile``.

Dual tree_parity expects ``compiler/py/codegen/template_profile.py`` ↔
``compiler/paw/codegen/template_profile.paw``.
"""
from host.codegen.template_profile import *  # noqa: F403
