"""去桥验收：compiler/paw 全部 mid-emit + Translator Mid PRIMARY 端到端。

用法（仓库根）::
  python tools/paw_debridge_accept.py

``PY2CPP_NO_MATERIALIZE`` / seed 默认 PRIMARY 见 ``src/tests/test_paw_debridge_p1_p3.py``。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from compiler.py.frontend.lexer import Lexer
from compiler.py.frontend.parser import parse_tokens
from compiler.py.frontend.source import FileId
from compiler.py.frontend.syntax_nodes import ClassDecl, FieldDecl
from compiler.py.mid.emit_cpp import can_emit_mid, emit_mid_module
from compiler.py.sema.bind import bind_module, lower_to_mid


def _check_seed_mid_emit(out: Path) -> list[str]:
  errs: list[str] = []
  seed = ROOT / "compiler" / "paw"
  paths = sorted(p for p in seed.rglob("*.paw") if p.is_file())
  if not paths:
    return ["no seed *.paw"]
  for path in paths:
    src = path.read_text(encoding="utf-8")
    syntax = parse_tokens(Lexer(src, FileId(0)).tokenize(), src)
    for item in syntax.items:
      if isinstance(item, ClassDecl):
        for mem in item.members:
          if isinstance(mem, FieldDecl) and not mem.name:
            errs.append(f"{path.name}: empty FieldDecl")
    rel = path.relative_to(ROOT).with_suffix("").as_posix()
    hir = bind_module(syntax, path=rel)
    mid = lower_to_mid(hir)
    if not can_emit_mid(mid):
      errs.append(f"{rel}: can_emit_mid=False")
      continue
    pkg_out = (out.joinpath(*rel.split("/"))).parent
    h, c = emit_mid_module(mid, out_dir=pkg_out, module_path=rel)
    if not h.exists() or not c.exists():
      errs.append(f"{rel}: emit missing files")
  return errs


def _check_seed_translator_primary(out: Path) -> list[str]:
  """端到端：默认 PRIMARY+NO_MATERIALIZE 下 Translator 产出 MidIR emit。"""
  from host.frontend.api import clear_parse_cache
  from host.translator import Translator

  errs: list[str] = []
  clear_parse_cache()
  seed = ROOT / "compiler" / "paw"
  for path in sorted(p for p in seed.rglob("*.paw") if p.is_file()):
    rel = path.relative_to(ROOT).with_suffix("").as_posix()
    try:
      _h, cpp = Translator.translate_file(
        str(path),
        str(out),
        include_stdlib=False,
        emit_main=False,
        strict=False,
      )
    except Exception as e:
      errs.append(f"{rel}: translate {type(e).__name__}: {e}")
      continue
    text = Path(cpp).read_text(encoding="utf-8")
    if not text.startswith("// MidIR emit"):
      errs.append(f"{rel}: not MidIR emit ({cpp})")
    if "namespace compiler" not in text or "namespace paw" not in text:
      errs.append(f"{rel}: missing nested ns")
  return errs


def _check_c0_mid_fixedpoint() -> list[str]:
  """C0 Mid-emit 定点：stage1==stage2==stage3 seed ``.h/.cpp``。"""
  from scripts.paw_bootstrap_stages import fixedpoint

  if fixedpoint() != 0:
    return ["C0 Mid-emit fixed-point failed (stage1/2/3 seed mismatch)"]
  return []


def _check_c1_seed_link() -> list[str]:
  """stage1 seed → 链 ``c1_seed_driver.exe``：smoke + 自解析 ``compiler/paw/*.paw``。"""
  bat = ROOT / "tools" / "paw_stage1_c1_link.bat"
  r = subprocess.run(
    ["cmd", "/c", str(bat)],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
  )
  if r.returncode != 0:
    tail = (r.stdout or "")[-2000:] + (r.stderr or "")[-1000:]
    return [f"C1 seed driver failed (rc={r.returncode})\n{tail}"]
  return []


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument("--out", type=Path, default=ROOT / "out" / "mid_emit_accept")
  ap.add_argument(
    "--skip-translate",
    action="store_true",
    help="只跑 can_emit_mid/emit，跳过 Translator PRIMARY",
  )
  ap.add_argument(
    "--skip-fixedpoint",
    action="store_true",
    help="跳过 C0 Mid-emit stage1==stage2==stage3 定点",
  )
  ap.add_argument(
    "--skip-c1-link",
    action="store_true",
    help="跳过 stage1→c1_seed_driver smoke+self-parse 竖切",
  )
  args = ap.parse_args()
  errs = _check_seed_mid_emit(args.out)
  n = len(list((ROOT / "compiler" / "paw").rglob("*.paw")))
  if errs:
    print("FAIL mid-emit")
    for e in errs:
      print(" ", e)
    return 1
  print(f"OK  seed mid-emit {n}/{n}")
  if not args.skip_translate:
    t_out = args.out.parent / "mid_emit_accept_translate"
    if t_out.exists():
      shutil.rmtree(t_out)
    terrs = _check_seed_translator_primary(t_out)
    if terrs:
      print("FAIL translator PRIMARY")
      for e in terrs:
        print(" ", e)
      return 1
    print(f"OK  seed translator PRIMARY {n}/{n}")
  if not args.skip_fixedpoint:
    ferrs = _check_c0_mid_fixedpoint()
    if ferrs:
      print("FAIL C0 Mid fixed-point")
      for e in ferrs:
        print(" ", e)
      return 1
    print(f"OK  C0 Mid fixed-point stage1==stage2==stage3 ({n}/{n})")
  if not args.skip_c1_link:
    cerrs = _check_c1_seed_link()
    if cerrs:
      print("FAIL C1 seed link+run")
      for e in cerrs:
        print(" ", e)
      return 1
    print("OK  C1 seed driver parse+emit+run")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
