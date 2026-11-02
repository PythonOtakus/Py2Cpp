"""Wall-clock helper for ``scripts/build_*.bat`` (``start`` / ``end``)."""
from __future__ import annotations

import os
import sys
import time

_KIND_SUFFIX = {
  "translate": "（仅翻译）",
  "compile": "（仅编译）",
  "build": "（翻译+编译）",
}


def main() -> int:
  if len(sys.argv) < 2:
    print(
      "usage: _build_timing.py start | end [label] [translate|compile]",
      file=sys.stderr,
    )
    return 1
  cmd = sys.argv[1].lower()
  if cmd == "start":
    print(time.perf_counter())
    return 0
  if cmd == "end":
    raw = os.environ.get("BUILD_T0", "0")
    try:
      t0 = float(raw)
    except ValueError:
      t0 = 0.0
    elapsed = time.perf_counter() - t0
    label = sys.argv[2] if len(sys.argv) > 2 else ""
    kind = sys.argv[3].lower() if len(sys.argv) > 3 else "build"
    suffix = _KIND_SUFFIX.get(kind, _KIND_SUFFIX["build"])
    if label:
      print(f"耗时: {label} {elapsed:.2f}s{suffix}")
    else:
      print(f"耗时: {elapsed:.2f}s{suffix}")
    return 0
  print(f"unknown command: {cmd}", file=sys.stderr)
  return 1


if __name__ == "__main__":
  raise SystemExit(main())
