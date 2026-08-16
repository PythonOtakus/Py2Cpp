"""``@mixin`` 译器约定常量（供 ``passes/`` 与 ``py2cpp/reflect/mixin.py`` 共用，勿拉取包根 ``__init__``）。"""

ITER_SUBCLASSES = "iterSubclasses"
ITER_SUBCLASSES_SORT_CONST = "sortConst"
MIXIN_METHODS_NOT_INLINED = frozenset({ITER_SUBCLASSES})
