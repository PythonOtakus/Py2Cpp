"""标准库 Python / C++ 类名字面量表。"""

HOST_BOUND_ITERATOR_VIEW_EXCLUDE_PY: frozenset[str] = frozenset({
  "str_iterator",
  "str_reverse_iterator",
  "tuple_iterator",
  "stack_array_iterator",
  "range_iterator",
  "zip_iterator",
  "enumerate_iterator",
})

HOST_BOUND_ITERATOR_VIEW_EXTRA_CPP: frozenset[str] = frozenset({
  "ECSComponentTableIterator",
})

CPP_TEMPLATE_PREFIX_OVERRIDES: dict[str, str] = {
  "Counter": "Counter<",
  "ChunkDeque": "ChunkDeque<",
}

ECS_QUERY_CLASS = "ECSComponentTableQuery"
ECS_QUERY_OWNER_FIELDS: dict[str, int] = {"_lead": 0, "_other": 1}
ECS_QUERY_OWNER_PARAMS: dict[str, int] = {"lead": 0, "other": 1}

ITERATOR_CTOR_SELF_AS_THIS: frozenset[str] = frozenset({
  "list",
  "deque",
  "set",
  "py_set",
  "frozenlist",
  "frozendict",
  "ECSComponentTable",
  "ChunkDeque",
})
