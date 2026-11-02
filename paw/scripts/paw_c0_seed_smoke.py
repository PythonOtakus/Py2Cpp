"""C0 编译 ``compiler/paw/*.paw`` 冒烟（自举种子）。

用法::

  python scripts/paw_c0_seed_smoke.py
  python scripts/paw_c0_seed_smoke.py --build
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "compiler" / "paw"


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument(
    "--build",
    action="store_true",
    help="经 build.bat 编译并运行（需 MSVC）",
  )
  ns = ap.parse_args()
  paws = sorted(p for p in SEED.rglob("*.paw") if p.is_file())
  if not paws:
    print("no seed .paw under compiler/paw/", flush=True)
    return 1
  if ns.build:
    patterns = " ".join(f"seed\\{p.stem}" for p in paws)
    # seed 不在 tests/；直接 main.py 译出后再提示用 build
    cmd = [
      sys.executable,
      str(ROOT / "main.py"),
      str(paws[0]),
      "-o",
      str(ROOT / "generated"),
      "--no-main",
    ]
    print("+", " ".join(cmd), flush=True)
    r = subprocess.call(cmd, cwd=str(ROOT))
    if r != 0:
      return r
    print("OK: translated", paws[0].name, flush=True)
    print("hint: add test harness under tests/ to build.bat-run", flush=True)
    return 0
  fail = 0
  for p in paws:
    cmd = [
      sys.executable,
      str(ROOT / "main.py"),
      str(p),
      "-o",
      str(ROOT / "generated"),
      "--no-main",
    ]
    print("+", p.name, flush=True)
    r = subprocess.call(cmd, cwd=str(ROOT))
    if r != 0:
      fail += 1
      print("FAIL", p, flush=True)
    else:
      print("OK ", p.name, flush=True)
  return 1 if fail else 0


if __name__ == "__main__":
  raise SystemExit(main())
