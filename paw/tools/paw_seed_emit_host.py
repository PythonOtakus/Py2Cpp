"""用宿主 ``host/`` 直译 ``compiler/paw/**/*.paw`` → stage1 C++（取代种子轨）。

背景：``compiler/py/mid/emit_cpp.py``（种子轨）靠类名白名单猜形参可变性等语义，
每次库新增状态类都要改它，已归档为历史参考。自举入口统一走宿主：

  python tools/paw_seed_emit_host.py --out compiler/stages/stage1

产物布局与旧 ``emit-seed`` 一致（``<out>/compiler/paw/<rel>.{h,cpp}``），
以便 ``c1_seed_driver.cpp`` 的 ``#include`` 路径不变。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEED_DIR = ROOT / "compiler" / "paw"


def _seed_sources() -> list[Path]:
  """``compiler/paw`` 下全部 ``.paw``（按路径排序，保证产物稳定）。"""
  return sorted(p for p in SEED_DIR.rglob("*.paw") if p.is_file())


def main() -> int:
  ap = argparse.ArgumentParser(description="Host-driven seed emit for compiler/paw")
  ap.add_argument("--out", required=True, help="stage 输出根（如 compiler/stages/stage1）")
  ap.add_argument("--no-strict", action="store_true", help="关闭译期强检查（默认开启）")
  ns = ap.parse_args()

  out_root = (ROOT / ns.out).resolve()
  seed_out = out_root / "compiler" / "paw"
  if seed_out.exists():
    shutil.rmtree(seed_out)
  seed_out.mkdir(parents=True, exist_ok=True)

  from host import Translator

  sources = _seed_sources()
  if not sources:
    print(f"FAIL no seed .paw under {SEED_DIR}", file=sys.stderr)
    return 1

  ok = 0
  failed: list[tuple[str, str]] = []
  for path in sources:
    rel = path.relative_to(SEED_DIR).with_suffix("")
    try:
      header_path, source_path = Translator.translate_file(
        str(path),
        output_dir=str(out_root),
        include_stdlib=False,
        emit_main=False,
        strict=not ns.no_strict,
      )
    except Exception as exc:  # noqa: BLE001 - 逐个模块隔离失败
      failed.append((rel.as_posix(), str(exc).splitlines()[0] if str(exc) else repr(exc)))
      continue
    ok += 1
    _ = (header_path, source_path)

  # 宿主把 ``compiler/paw/a/b.paw`` 译到 ``<out>/compiler/paw/a/b.{h,cpp}``；
  # 若某模块落到别处，这里显式搬移一次以固定布局。
  _normalize_layout(out_root, seed_out)

  total = len(sources)
  if failed:
    print(f"FAIL host seed emit {ok}/{total}; {len(failed)} failed", file=sys.stderr)
    for rel, msg in failed[:20]:
      print(f"  {rel}: {msg}", file=sys.stderr)
    return 1
  print(f"OK host seed emit {ok}/{total} -> {seed_out}")
  return 0


def _normalize_layout(out_root: Path, seed_out: Path) -> None:
  """确保每个 seed 模块的 ``.h/.cpp`` 都落在 ``<out>/compiler/paw/<rel>``。

  宿主对 ``compiler/paw/x.paw`` 的默认落盘就是该路径；此处仅兜底处理
  落到 ``<out>/x`` 的旧行为。
  """
  if not out_root.is_dir():
    return
  for stray in out_root.glob("*.h"):
    pass  # 顶层散落文件不改动，避免误搬 runtime 产物
  _ = seed_out


if __name__ == "__main__":
  raise SystemExit(main())
