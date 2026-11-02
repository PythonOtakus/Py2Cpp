"""``py2cpp/concur/parallel`` 译器约定。"""

CONCUR_PARALLEL_MODULE = "py2cpp/concur/parallel"
PRANGE_TRANSLATION_ONLY_FUNCS = frozenset({"prange"})
PRANGE_SCHEDULES = frozenset({"static", "dynamic", "guided"})
REDUCTION_OPS = frozenset({"+", "-", "*", "&", "|", "^"})
