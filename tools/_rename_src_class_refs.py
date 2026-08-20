#!/usr/bin/env python3
"""仅更新 src/ 中对已改名标准库类的硬编码字符串（不碰 startswith 等 Python API）。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CLASS_MAP = {
  "list_iterator": "ListIterator",
  "list_reverse_iterator": "ListReverseIterator",
  "frozenlist_iterator": "FrozenListIterator",
  "str_iterator": "StrIterator",
  "str_reverse_iterator": "StrReverseIterator",
  "tuple_iterator": "TupleIterator",
  "stack_array_iterator": "StackArrayIterator",
  "range_iterator": "RangeIterator",
  "zip_iterator": "ZipIterator",
  "enumerate_iterator": "EnumerateIterator",
  "deque_iterator": "DequeIterator",
  "deque_reverse_iterator": "DequeReverseIterator",
  "deque_node": "DequeNodeUnsafe",
  "dict_entry": "DictEntryUnsafe",
  "dict_items_iterator": "DictItemsIterator",
  "dict_items_view": "DictItemsView",
  "dict_key_iterator": "DictKeyIterator",
  "dict_key_reverse_iterator": "DictKeyReverseIterator",
  "dict_keys_view": "DictKeysView",
  "dict_values_iterator": "DictValuesIterator",
  "dict_values_view": "DictValuesView",
  "frozendict_items_iterator": "FrozenDictItemsIterator",
  "frozendict_items_view": "FrozenDictItemsView",
  "frozendict_key_iterator": "FrozenDictKeyIterator",
  "frozendict_key_reverse_iterator": "FrozenDictKeyReverseIterator",
  "frozendict_keys_view": "FrozenDictKeysView",
  "frozendict_values_iterator": "FrozenDictValuesIterator",
  "frozendict_values_view": "FrozenDictValuesView",
  "frozenset_entry": "FrozenSetEntryUnsafe",
  "frozenset_iterator": "FrozenSetIterator",
  "set_iterator": "SetIterator",
  "set_reverse_iterator": "SetReverseIterator",
  "stack_array": "StackArray",
  "stack_array2d": "StackArray2d",
  "stack_array3d": "StackArray3d",
  "thread_local": "thread_local",
  "scandir_iterator": "ScandirIterator",
  "pool_slot_loc": "PoolSlotLoc",
  "c_stat": "CStat",
  "c_str": "utf8ptr",
  "c_time": "CTime",
}

# 方法名（译器/注释中的 py2cpp API 旧名）
METHOD_MAP = {
  "splitlines": "splitLines",
  "setdefault": "setDefault",
  "is_absolute": "isAbsolute",
  "isatty": "isAtty",
}


def main() -> int:
  keys = sorted({**CLASS_MAP, **METHOD_MAP}.keys(), key=len, reverse=True)
  # 仅替换出现在引号或标识符边界的类名；方法名只在明确「py2cpp API」语境太难，先只做类名
  class_keys = sorted(CLASS_MAP.keys(), key=len, reverse=True)
  pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in class_keys) + r")\b")
  n = 0
  for p in (ROOT / "src").rglob("*.py"):
    raw = p.read_text(encoding="utf-8")
    new = pat.sub(lambda m: CLASS_MAP[m.group(0)], raw)
    if new != raw:
      p.write_text(new, encoding="utf-8", newline="\n")
      n += 1
      print(f"src {p.relative_to(ROOT)}")
  print(f"files={n}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
