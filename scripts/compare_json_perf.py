#!/usr/bin/env python3
"""CPython ``json.dumps`` 基线（与 ``test/perf/test_json_serde.py`` 规模对齐）。"""
import json
import time

_SIZE_INT = 50000
_SIZE_STR = 20000
_SIZE_NESTED = 5000
_SIZE_TAGS = 10000
_SIZE_LIST_USER = 2000


def _bench(label: str, n: int, obj) -> None:
    t0 = time.perf_counter()
    s = json.dumps(obj)
    elapsed = time.perf_counter() - t0
    mb = (len(s) / 1048576.0) / elapsed if elapsed > 0 else 0.0
    print(f"  [CPython] {label} n={n}  time={elapsed*1000:.3f}ms  out={len(s)}  ~{mb:.2f} MB/s")


def main() -> None:
    print("CPython json.dumps baseline")
    _bench("list[int]", 10000, list(range(10000)))
    _bench("list[int]", _SIZE_INT, list(range(_SIZE_INT)))
    _bench("list[str]", _SIZE_STR, ["item"] * _SIZE_STR)
    _bench(
        "dict[str,int]",
        _SIZE_NESTED,
        {f"k{i}": i for i in range(_SIZE_NESTED)},
    )
    _bench(
        "NestedDoc-like",
        _SIZE_NESTED,
        {
            "id": 42,
            "counts": list(range(_SIZE_NESTED)),
            "labels": {f"f{i}": "v" for i in range(_SIZE_NESTED)},
        },
    )
    _bench(
        "User(tags)-like",
        _SIZE_TAGS,
        {"id": 1, "name": "bench", "active": True, "tags": ["tag"] * _SIZE_TAGS},
    )
    _bench(
        "Event.Tick-like",
        2000,
        {"tag": "Tick", "payload": {"seq": 9, "values": list(range(2000))}},
    )
    _bench(
        "list[User]-like",
        _SIZE_LIST_USER,
        [
            {"id": i, "name": "u", "active": True, "tags": []}
            for i in range(_SIZE_LIST_USER)
        ],
    )


if __name__ == "__main__":
    main()
