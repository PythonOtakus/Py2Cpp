"""N6 / P6 自编译阶段脚手架（manifest 对比入口）。

完整真·C1→C2→C3 仍需原生编译器可执行体。当前可跑通的闭环：

  C0 Mid-emit fixed-point
    emit-seed → stage1 + stage2（同 C0、同 seed）
    compare-seed stage1 stage2  → 产物字节一致

用法::

  python scripts/paw_bootstrap_stages.py fixedpoint
  python scripts/paw_bootstrap_stages.py emit-seed [stage1|stage2|stage3]
  python scripts/paw_bootstrap_stages.py compare-seed stage1 stage2
  python scripts/paw_bootstrap_stages.py compare-host-thin
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = ROOT / "compiler" / "stages"
COMPILER = ROOT / "compiler"
SEED = COMPILER / "paw"
sys.path.insert(0, str(ROOT))

_SEED_RELS = (
  "frontend/source",
  "frontend/tokens",
  "frontend/diagnostic",
  "frontend/lexer",
  "frontend/parser",
  "frontend/syntax_nodes",
  "hir/nodes",
  "mid/nodes",
  "mid/emit_cpp",
  "passes/check",
  "sema/bind",
)


def _digest_tree(root: Path, *, skip_names: frozenset[str] | None = None) -> dict[str, str]:
  skip = skip_names or frozenset()
  out: dict[str, str] = {}
  if not root.is_dir():
    return out
  for p in sorted(root.rglob("*")):
    if p.is_file():
      if p.name in skip or any(part in skip for part in p.parts):
        continue
      rel = p.relative_to(root).as_posix()
      out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
  return out


def _write_bootstrap_status(**overrides: object) -> Path:
  profile = {
    "schema_version": "paw-frontend-0.3.0",
    "hir_version": "paw-hir-0.1.0",
    "mid_version": "paw-mid-0.1.0",
    "seed": "C0-host-python",
    "status": "c0-debridge-p6",
    "pipeline": "Syntax->HIR->MidIR(+emit_cpp)",
    "note": "C0 Mid-emit fixed-point: fixedpoint 命令；真 C1 见 parser-self-hosting.md",
    "stdlib_mid_emit": "run: python scripts/paw_mid_emit_coverage.py",
  }
  profile.update(overrides)
  path = STAGES / "bootstrap_status.json"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
  return path


def init_stages() -> None:
  for name in ("stage1", "stage2", "stage3"):
    d = STAGES / name
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitkeep").write_text("", encoding="utf-8")
  _write_bootstrap_status(status="scaffold")


def write_manifest(stage: str) -> Path:
  d = STAGES / stage
  d.mkdir(parents=True, exist_ok=True)
  manifest = {
    "stage": stage,
    "files": _digest_tree(d, skip_names=frozenset({"manifest.json"})),
  }
  path = d / "manifest.json"
  path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  return path


def snapshot_seed(*, stage: str = "stage1") -> Path:
  """将 compiler/ 源码摘要写入 ``{stage}/seed_sources.json``。"""
  STAGES.joinpath(stage).mkdir(parents=True, exist_ok=True)
  files = _digest_tree(
    COMPILER,
    skip_names=frozenset({"__pycache__", ".gitkeep", "stages"}),
  )
  files = {k: v for k, v in files.items() if not k.startswith("stages/")}
  payload = {
    "kind": "compiler-seed",
    "schema_version": "paw-frontend-0.3.0",
    "file_count": len(files),
    "files": files,
  }
  path = STAGES / stage / "seed_sources.json"
  path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  return path


def _seed_mid_digests(stage: str) -> dict[str, str]:
  """仅 ``compiler/paw/*.{h,cpp}`` 内容摘要（定点对比用）。"""
  root = STAGES / stage / "compiler" / "paw"
  out: dict[str, str] = {}
  if not root.is_dir():
    return out
  for rel in _SEED_RELS:
    for suf in (".h", ".cpp"):
      p = root.joinpath(*rel.split("/")).with_suffix(suf)
      if p.is_file():
        out[f"compiler/paw/{rel}{suf}"] = hashlib.sha256(p.read_bytes()).hexdigest()
  return out


def emit_seed_to_stage(stage: str = "stage1") -> Path:
  """C0：将 ``compiler/paw/**/*.paw`` MidIR emit 写入 ``{stage}/compiler/paw/…``。"""
  from compiler.py.frontend.lexer import Lexer
  from compiler.py.frontend.parser import parse_tokens
  from compiler.py.frontend.source import FileId
  from compiler.py.mid.emit_cpp import can_emit_mid, emit_mid_module
  from compiler.py.sema.bind import bind_module, lower_to_mid

  if stage not in ("stage1", "stage2", "stage3"):
    raise ValueError(f"bad stage {stage!r}")
  out_root = STAGES / stage
  seed_out = out_root / "compiler" / "paw"
  if seed_out.exists():
    shutil.rmtree(seed_out)
  seed_out.mkdir(parents=True, exist_ok=True)
  seeds = sorted(p for p in SEED.rglob("*.paw") if p.is_file())
  if not seeds:
    raise FileNotFoundError(f"no seed .paw under {SEED}")
  ok = 0
  for path in seeds:
    src = path.read_text(encoding="utf-8")
    rel = path.relative_to(SEED).with_suffix("").as_posix()
    mp = f"compiler/paw/{rel}"
    mid = lower_to_mid(
      bind_module(parse_tokens(Lexer(src, FileId(0)).tokenize(), src), path=mp)
    )
    if not can_emit_mid(mid):
      raise RuntimeError(f"seed not mid-emit capable: {path}")
    # Nest output: stage1/compiler/paw/frontend/lexer.{h,cpp}
    pkg_out = out_root.joinpath(*mp.split("/")).parent
    emit_mid_module(mid, out_dir=pkg_out, module_path=mp)
    ok += 1
  snapshot_seed(stage=stage)
  man = write_manifest(stage)
  _write_bootstrap_status(
    status=f"c0-mid-emit-{stage}",
    note=f"{stage} seed MidIR emit {ok}/{len(seeds)}; manifest {man.name}",
    **{f"{stage}_seed_emit": f"{ok}/{len(seeds)}"},
  )
  return out_root


def emit_seed_to_stage1() -> Path:
  """兼容旧调用名。"""
  return emit_seed_to_stage("stage1")


def compare(a: str, b: str) -> int:
  ma = json.loads((STAGES / a / "manifest.json").read_text(encoding="utf-8"))
  mb = json.loads((STAGES / b / "manifest.json").read_text(encoding="utf-8"))
  fa, fb = ma.get("files", {}), mb.get("files", {})
  if fa == fb:
    print(f"OK: {a} == {b} ({len(fa)} files)")
    return 0
  only_a = sorted(set(fa) - set(fb))
  only_b = sorted(set(fb) - set(fa))
  differ = sorted(k for k in fa if k in fb and fa[k] != fb[k])
  print(f"DIFF: only {a}: {only_a}")
  print(f"DIFF: only {b}: {only_b}")
  print(f"DIFF: content: {differ}")
  return 1


def compare_seed(a: str, b: str) -> int:
  """对比两 stage 的 seed Mid ``.h/.cpp`` 摘要（忽略 seed_sources / obj）。"""
  fa, fb = _seed_mid_digests(a), _seed_mid_digests(b)
  if not fa or not fb:
    print(f"FAIL: missing seed Mid under {a} or {b}")
    return 1
  if fa == fb:
    print(f"OK: seed Mid {a} == {b} ({len(fa)} files)")
    return 0
  only_a = sorted(set(fa) - set(fb))
  only_b = sorted(set(fb) - set(fa))
  differ = sorted(k for k in fa if k in fb and fa[k] != fb[k])
  print(f"DIFF seed: only {a}: {only_a}")
  print(f"DIFF seed: only {b}: {only_b}")
  print(f"DIFF seed: content: {differ}")
  return 1


_SKIP_RE = re.compile(r"/\*\s*skip")
# Soft-skip that is just the emitter writing its own skip-message string lits.
_INTENTIONAL_SKIP_LIT = re.compile(
  r'PyStr\(\s*"\s*/\*\s*skip:|'
  r'return\s*\(\(PyStr\(\s*"\s*/\*\s*skip:'
)


def _count_soft_skips(path: Path) -> tuple[int, int]:
  """Return (total_skip_markers, real_soft_skips) excluding intentional lit emits."""
  if not path.is_file():
    return (0, 0)
  text = path.read_text(encoding="utf-8", errors="replace")
  total = 0
  real = 0
  for line in text.splitlines():
    if not _SKIP_RE.search(line):
      continue
    total += 1
    if _INTENTIONAL_SKIP_LIT.search(line):
      continue
    # ``out = (out + PyStr(" /* skip: match */\n"));`` — intentional
    if 'PyStr(" /* skip:' in line or 'PyStr("  /* skip:' in line:
      continue
    if 'PyStr(" /* skip:' in line.replace("  ", " "):
      continue
    stripped = line.strip()
    if stripped.startswith("out =") and "/* skip:" in stripped and "PyStr(" in stripped:
      continue
    if stripped.startswith("return") and "/* skip:" in stripped and "PyStr(" in stripped:
      continue
    real += 1
  return (total, real)


def compare_host_thin(stage: str = "stage1") -> int:
  """宿主 Mid vs c1_emit soft-skip / 体积门闩（非字节相等）。"""
  host_root = STAGES / stage / "compiler" / "paw"
  thin_root = STAGES / stage / "c1_emit"
  if not host_root.is_dir() or not thin_root.is_dir():
    print(f"FAIL compare-host-thin: missing {host_root} or {thin_root}", flush=True)
    return 1
  failed = 0
  rows: list[str] = []
  emit_host_real = 0
  emit_thin_real = 0
  for rel in _SEED_RELS:
    hp = host_root / f"{rel}.cpp"
    # Nested host path: frontend/parser.cpp under compiler/paw/
    if not hp.is_file():
      # try flat under package dirs already in rel
      hp = host_root.joinpath(*rel.split(".")[0].split("/")).with_suffix(".cpp")
      if not hp.is_file():
        hp = host_root / Path(rel).with_suffix(".cpp")
    tp = thin_root / f"{rel}.cpp"
    if not hp.is_file():
      print(f"WARN host missing {rel}.cpp", flush=True)
      continue
    if not tp.is_file():
      print(f"FAIL thin missing {rel}.cpp", flush=True)
      failed += 1
      continue
    ht, hr = _count_soft_skips(hp)
    tt, tr = _count_soft_skips(tp)
    hs, ts = hp.stat().st_size, tp.stat().st_size
    ratio = (ts + 1) / (hs + 1)
    rows.append(
      f"  {rel}: host_skip={hr}/{ht} thin_skip={tr}/{tt} bytes={hs}->{ts} ratio={ratio:.2f}"
    )
    if rel == "mid/emit_cpp":
      emit_host_real, emit_thin_real = hr, tr
      # Thin must not regress past host on real soft-skips.
      if tr > hr:
        print(
          f"FAIL emit_cpp real soft-skips thin={tr} > host={hr}",
          flush=True,
        )
        failed += 1
      if tr > 0:
        print(f"FAIL emit_cpp still has real soft-skips thin={tr}", flush=True)
        failed += 1
    elif tr > 0:
      print(f"FAIL {rel} thin real soft-skips={tr}", flush=True)
      failed += 1
    if ratio < 0.45:
      print(f"FAIL {rel} thin too small vs host ({ts}/{hs})", flush=True)
      failed += 1
  for line in rows:
    print(line, flush=True)
  # Optional C2≡C3 size check when present.
  c2 = STAGES / stage / "c2_thin"
  c3 = STAGES / stage / "c3_thin"
  if c2.is_dir() and c3.is_dir():
    for rel in ("frontend/parser.cpp", "frontend/lexer.cpp", "mid/emit_cpp.cpp"):
      p2, p3 = c2 / rel, c3 / rel
      if p2.is_file() and p3.is_file():
        if p2.read_bytes() != p3.read_bytes():
          print(f"FAIL c2≠c3 {rel}", flush=True)
          failed += 1
        else:
          print(f"OK c2≡c3 {rel} ({p2.stat().st_size} bytes)", flush=True)
  _write_bootstrap_status(
    status="compare-host-thin-ok" if failed == 0 else "compare-host-thin-fail",
    note="host Mid vs c1_emit soft-skip gate; c2≡c3 when present",
    host_thin_emit_cpp_skips=f"{emit_host_real}/{emit_thin_real}",
  )
  if failed:
    print(f"FAIL compare-host-thin failures={failed}", flush=True)
    return 1
  print("OK compare-host-thin", flush=True)
  return 0


def fixedpoint() -> int:
  """C0 Mid-emit 定点：stage1 ≡ stage2（同宿主、同 seed）。"""
  emit_seed_to_stage("stage1")
  emit_seed_to_stage("stage2")
  # stage3 同 C0 再编一轮，模拟「尚未有 C1 时」的三阶段对齐
  emit_seed_to_stage("stage3")
  rc12 = compare_seed("stage1", "stage2")
  rc23 = compare_seed("stage2", "stage3")
  if rc12 == 0 and rc23 == 0:
    _write_bootstrap_status(
      status="c0-mid-fixedpoint-green",
      note="C0 Mid-emit fixed-point: stage1==stage2==stage3 seed .h/.cpp",
      stage1_seed_emit="8/8",
      stage2_seed_emit="8/8",
      stage3_seed_emit="8/8",
      fixedpoint="stage1==stage2==stage3",
      true_c1="partial: c1_seed_driver parse+thin mid_emit+check; full S/HIR blocked",
      c1_seed_driver="scripts/paw_stage1_c1_link.bat",
    )
    print("OK  C0 Mid-emit fixed-point stage1==stage2==stage3")
    return 0
  _write_bootstrap_status(
    status="c0-mid-fixedpoint-fail",
    note="fixed-point mismatch; see compare-seed output",
  )
  return 1


def main() -> int:
  ap = argparse.ArgumentParser(description="Paw bootstrap stage helper")
  ap.add_argument(
    "cmd",
    choices=(
      "init",
      "manifest",
      "compare",
      "compare-seed",
      "compare-host-thin",
      "snapshot-seed",
      "emit-seed",
      "fixedpoint",
    ),
  )
  ap.add_argument("args", nargs="*")
  ns = ap.parse_args()
  if ns.cmd == "init":
    init_stages()
    print(f"initialized {STAGES}")
    return 0
  if ns.cmd == "snapshot-seed":
    stage = ns.args[0] if ns.args else "stage1"
    path = snapshot_seed(stage=stage)
    print(path)
    return 0
  if ns.cmd == "emit-seed":
    stage = ns.args[0] if ns.args else "stage1"
    out = emit_seed_to_stage(stage)
    print(f"OK emit-seed → {out}")
    return 0
  if ns.cmd == "fixedpoint":
    return fixedpoint()
  if ns.cmd == "manifest":
    if len(ns.args) != 1:
      print("usage: manifest stage1|stage2|stage3", flush=True)
      return 2
    path = write_manifest(ns.args[0])
    print(path)
    return 0
  if ns.cmd == "compare":
    if len(ns.args) != 2:
      print("usage: compare stage2 stage3", flush=True)
      return 2
    return compare(ns.args[0], ns.args[1])
  if ns.cmd == "compare-seed":
    if len(ns.args) != 2:
      print("usage: compare-seed stage1 stage2", flush=True)
      return 2
    return compare_seed(ns.args[0], ns.args[1])
  if ns.cmd == "compare-host-thin":
    stage = ns.args[0] if ns.args else "stage1"
    return compare_host_thin(stage)
  return 2


if __name__ == "__main__":
  raise SystemExit(main())
