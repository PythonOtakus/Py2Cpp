"""Python dunder 名 → C++ ``operator`` 映射表。"""

BINARY_DUNDER_TO_CPP_OP: dict[str, str] = {
  "__add__": "+",
  "__sub__": "-",
  "__mul__": "*",
  "__truediv__": "/",
  "__floordiv__": "/",
  "__mod__": "%",
  "__lshift__": "<<",
  "__rshift__": ">>",
  "__or__": "|",
  "__xor__": "^",
  "__and__": "&",
  "__eq__": "==",
  "__ne__": "!=",
  "__lt__": "<",
  "__le__": "<=",
  "__gt__": ">",
  "__ge__": ">=",
}

BINARY_DUNDER_TO_REVERSE: dict[str, str] = {
  "__add__": "__radd__",
  "__sub__": "__rsub__",
  "__mul__": "__rmul__",
  "__truediv__": "__rtruediv__",
  "__floordiv__": "__rfloordiv__",
  "__mod__": "__rmod__",
  "__lshift__": "__rlshift__",
  "__rshift__": "__rrshift__",
  "__or__": "__ror__",
  "__xor__": "__rxor__",
  "__and__": "__rand__",
}

BINARY_DUNDER_TO_INPLACE: dict[str, str] = {
  "__add__": "__iadd__",
  "__sub__": "__isub__",
  "__mul__": "__imul__",
  "__truediv__": "__itruediv__",
  "__floordiv__": "__ifloordiv__",
  "__mod__": "__imod__",
  "__lshift__": "__ilshift__",
  "__rshift__": "__irshift__",
  "__or__": "__ior__",
  "__xor__": "__ixor__",
  "__and__": "__iand__",
}

UNARY_DUNDER_TO_CPP_OP: dict[str, str] = {
  "__neg__": "-",
  "__pos__": "+",
  "__invert__": "~",
}

COMPARE_DUNDERS: frozenset[str] = frozenset(
  k for k, op in BINARY_DUNDER_TO_CPP_OP.items() if op in ("==", "!=", "<", "<=", ">", ">=")
)

SKIP_OPERATOR_DUNDERS: frozenset[str] = frozenset({
  "__mod__",
  "__truediv__",
  "__floordiv__",
})
