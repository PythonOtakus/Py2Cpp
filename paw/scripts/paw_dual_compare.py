"""双实现对照：目录 1:1 + emitEnum + tokenize/parse/Mid dump + emit_cpp 规范化。

用法::

  python scripts/paw_dual_compare.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PY = ROOT / "compiler" / "py"
PAW = ROOT / "compiler" / "paw"
DUAL = ROOT / "compiler" / "dual"
PAIRS = DUAL / "pairs.json"
FIXTURE = DUAL / "fixtures" / "color_enum.json"
GOLDEN_ENUM = DUAL / "goldens" / "emit_enum_Color.txt"
GOLDEN_EMIT_CPP = DUAL / "goldens" / "emit_cpp_enum_color.txt"
GOLDEN_TOK = DUAL / "goldens" / "tokenize_assign.txt"
GOLDEN_PARSE = DUAL / "goldens" / "parse_enum_color.txt"
GOLDEN_MID = DUAL / "goldens" / "mid_enum_color.txt"
FIX_TOK = DUAL / "fixtures" / "tokenize_assign.txt"
FIX_PARSE = DUAL / "fixtures" / "parse_enum_color.txt"
PAW_EMIT_CPP = PAW / "mid" / "emit_cpp.paw"
LEXER_EXE = (
  ROOT / "compiler" / "stages" / "stage1" / "bin" / "c1_emit_lexer_run.exe"
)
PARSER_EXE = (
  ROOT / "compiler" / "stages" / "stage1" / "bin" / "c1_emit_parser_run.exe"
)
SEED_DRIVER = (
  ROOT / "compiler" / "stages" / "stage1" / "bin" / "c1_seed_driver.exe"
)
HOST_MID_EMIT_CPP = (
  ROOT
  / "compiler"
  / "stages"
  / "stage1"
  / "compiler"
  / "paw"
  / "mid"
  / "emit_cpp.cpp"
)

_OK_COMPARES = frozenset(
  {"emit_enum", "tokenize_dump", "parse_dump", "mid_dump", "emit_cpp_norm"}
)


def _repo_path(rel: str) -> Path:
  return ROOT / Path(*rel.split("/"))


def _tree_keys(root: Path) -> set[str]:
  out: set[str] = set()
  for p in root.rglob("*"):
    if not p.is_file() or "__pycache__" in p.parts:
      continue
    rel = p.relative_to(root)
    if rel.suffix == ".py":
      out.add(rel.with_suffix(".paw").as_posix())
    elif rel.suffix == ".paw":
      out.add(rel.as_posix())
    else:
      out.add(rel.as_posix())
  return out


def _check_tree_parity() -> list[str]:
  py_keys = _tree_keys(PY)
  paw_keys = _tree_keys(PAW)
  errs: list[str] = []
  for k in sorted(py_keys - paw_keys):
    errs.append(f"missing paw: {k}")
  for k in sorted(paw_keys - py_keys):
    errs.append(f"extra paw: {k}")
  for p in PAW.rglob("__init__.py"):
    errs.append(f"paw must use __init__.paw not .py: {p.relative_to(ROOT).as_posix()}")
  return errs


def _load_pairs() -> dict:
  data = json.loads(PAIRS.read_text(encoding="utf-8"))
  assert int(data.get("version", 0)) >= 2
  assert isinstance(data.get("pairs"), list)
  return data


def _check_pair_paths(data: dict) -> list[str]:
  errs: list[str] = []
  for p in data["pairs"]:
    paw = p.get("paw") or ""
    if paw and not _repo_path(paw).is_file():
      errs.append(f"missing paw: {paw}")
    for py in p.get("py") or []:
      if not _repo_path(py).is_file():
        errs.append(f"missing py: {py}")
  return errs


def _norm(s: str) -> str:
  lines = [ln.rstrip() for ln in s.replace("\r\n", "\n").split("\n")]
  while lines and lines[-1] == "":
    lines.pop()
  return "\n".join(lines) + "\n"


def _extract_dump(out: str, begin: str, end: str) -> str | None:
  a = out.find(begin)
  b = out.find(end)
  if a < 0 or b < 0 or b <= a:
    return None
  body = out[a + len(begin) : b]
  if body.startswith("\n"):
    body = body[1:]
  return body


def _emit_enum_from_fixture() -> str:
  from compiler.dual.emit_enum_fixture import EnumBundle, EnumMember, emitEnum

  raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
  en = EnumBundle(name=raw["name"])
  for m in raw["members"]:
    en.members.append(
      EnumMember(name=m["name"], valueSource=m.get("valueSource", ""))
    )
  return emitEnum(en)


def _check_emit_enum() -> list[str]:
  errs: list[str] = []
  got = _norm(_emit_enum_from_fixture())
  want = _norm(GOLDEN_ENUM.read_text(encoding="utf-8"))
  if got != want:
    errs.append("emit_enum fixture != golden")
  if "def emitEnum" not in PAW_EMIT_CPP.read_text(encoding="utf-8"):
    errs.append("emit_cpp.paw missing def emitEnum")
  if HOST_MID_EMIT_CPP.is_file():
    mid_txt = HOST_MID_EMIT_CPP.read_text(encoding="utf-8")
    if "emitEnum(" not in mid_txt and "PyStr emitEnum" not in mid_txt:
      errs.append("host Mid emit_cpp.cpp missing emitEnum")
  else:
    errs.append(
      f"skip host Mid: missing {HOST_MID_EMIT_CPP.relative_to(ROOT).as_posix()}"
    )
  return errs


def _check_tokenize_dump() -> list[str]:
  from compiler.dual.dump_fmt import dump_tokenize

  errs: list[str] = []
  src = FIX_TOK.read_text(encoding="utf-8")
  # fixtures may omit final newline; match C++ literal ``x = 1\n``
  if not src.endswith("\n"):
    src = src + "\n"
  got = _norm(dump_tokenize(src, file_value=0))
  want = _norm(GOLDEN_TOK.read_text(encoding="utf-8"))
  if got != want:
    errs.append("py tokenize != golden tokenize_assign.txt")
    errs.append("--- py ---")
    errs.append(got.rstrip("\n"))
    errs.append("--- want ---")
    errs.append(want.rstrip("\n"))
    return errs

  if not LEXER_EXE.is_file():
    errs.append(f"skip paw: missing {LEXER_EXE.relative_to(ROOT).as_posix()} (run c1_link)")
    return errs
  r = subprocess.run([str(LEXER_EXE)], capture_output=True, text=True, cwd=str(ROOT))
  if r.returncode != 0:
    errs.append(f"paw lexer exe rc={r.returncode}: {r.stdout}\n{r.stderr}")
    return errs
  dump = _extract_dump(r.stdout, "===TOKEN_DUMP===\n", "===END_DUMP===\n")
  if dump is None:
    errs.append("paw lexer stdout missing TOKEN_DUMP markers")
    return errs
  if _norm(dump) != want:
    errs.append("paw tokenize != golden")
    errs.append("--- paw ---")
    errs.append(_norm(dump).rstrip("\n"))
  return errs


def _check_parse_dump() -> list[str]:
  from compiler.dual.dump_fmt import dump_parse

  errs: list[str] = []
  src = FIX_PARSE.read_text(encoding="utf-8")
  if not src.endswith("\n"):
    src = src + "\n"
  got = _norm(dump_parse(src, file_value=0))
  want = _norm(GOLDEN_PARSE.read_text(encoding="utf-8"))
  if got != want:
    errs.append("py parse != golden parse_enum_color.txt")
    errs.append("--- py ---")
    errs.append(got.rstrip("\n"))
    errs.append("--- want ---")
    errs.append(want.rstrip("\n"))
    return errs

  if not PARSER_EXE.is_file():
    errs.append(f"skip paw: missing {PARSER_EXE.relative_to(ROOT).as_posix()} (run c1_link)")
    return errs
  r = subprocess.run([str(PARSER_EXE)], capture_output=True, text=True, cwd=str(ROOT))
  if r.returncode != 0:
    errs.append(f"paw parser exe rc={r.returncode}: {r.stdout}\n{r.stderr}")
    return errs
  dump = _extract_dump(r.stdout, "===PARSE_DUMP===\n", "===END_DUMP===\n")
  if dump is None:
    errs.append("paw parser stdout missing PARSE_DUMP markers")
    return errs
  if _norm(dump) != want:
    errs.append("paw parse != golden")
    errs.append("--- paw ---")
    errs.append(_norm(dump).rstrip("\n"))
  return errs


def _check_mid_dump() -> list[str]:
  from compiler.dual.dump_fmt import dump_mid

  errs: list[str] = []
  src = FIX_PARSE.read_text(encoding="utf-8")
  if not src.endswith("\n"):
    src = src + "\n"
  got = _norm(dump_mid(src, path="compiler/dual/fixtures/parse_enum_color"))
  want = _norm(GOLDEN_MID.read_text(encoding="utf-8"))
  if got != want:
    errs.append("py mid != golden mid_enum_color.txt")
    errs.append("--- py ---")
    errs.append(got.rstrip("\n"))
    errs.append("--- want ---")
    errs.append(want.rstrip("\n"))
    return errs

  if not PARSER_EXE.is_file():
    errs.append(f"skip paw: missing {PARSER_EXE.relative_to(ROOT).as_posix()}")
    return errs
  r = subprocess.run([str(PARSER_EXE)], capture_output=True, text=True, cwd=str(ROOT))
  if r.returncode != 0:
    errs.append(f"paw parser exe rc={r.returncode}")
    return errs
  dump = _extract_dump(r.stdout, "===MID_DUMP===\n", "===END_MID_DUMP===\n")
  if dump is None:
    errs.append("paw parser stdout missing MID_DUMP markers")
    return errs
  if _norm(dump) != want:
    errs.append("paw mid-shaped != golden")
    errs.append("--- paw ---")
    errs.append(_norm(dump).rstrip("\n"))
  return errs


def _check_emit_cpp_norm() -> list[str]:
  """D4+：Py Mid emit_cpp 与 Paw 宿主 Mid ``emit_cpp.paw::emitEnum`` 规范化一致。"""
  from compiler.dual.dump_fmt import dump_emit_enums_from_mid, normalize_emitted_enums

  errs: list[str] = []
  src = FIX_PARSE.read_text(encoding="utf-8")
  if not src.endswith("\n"):
    src = src + "\n"
  want = _norm(GOLDEN_EMIT_CPP.read_text(encoding="utf-8"))
  got_py = _norm(
    dump_emit_enums_from_mid(
      src,
      path="compiler/dual/fixtures/parse_enum_color",
      module_path="dual/fixtures/parse_enum_color",
    )
  )
  if got_py != want:
    errs.append("py Mid emit_cpp enums != golden emit_cpp_enum_color.txt")
    errs.append("--- py ---")
    errs.append(got_py.rstrip("\n"))
    errs.append("--- want ---")
    errs.append(want.rstrip("\n"))
    return errs

  fixture_n = _norm(normalize_emitted_enums(_emit_enum_from_fixture()))
  if fixture_n != want:
    errs.append("dual emit_enum_fixture normalized != emit_cpp golden")
    return errs

  if "def emitEnum" not in PAW_EMIT_CPP.read_text(encoding="utf-8"):
    errs.append("emit_cpp.paw missing def emitEnum")

  if not SEED_DRIVER.is_file():
    errs.append(
      f"skip paw: missing {SEED_DRIVER.relative_to(ROOT).as_posix()} (run c1_link)"
    )
    return errs
  r = subprocess.run(
    [str(SEED_DRIVER), "--emit-enum-dump"],
    capture_output=True,
    text=True,
    cwd=str(ROOT),
  )
  if r.returncode != 0:
    errs.append(f"paw seed_driver emit-enum-dump rc={r.returncode}: {r.stdout}\n{r.stderr}")
    return errs
  dump = _extract_dump(r.stdout, "===EMIT_DUMP===\n", "===END_EMIT_DUMP===\n")
  if dump is None:
    errs.append("paw seed_driver stdout missing EMIT_DUMP markers")
    return errs
  got_paw = _norm(normalize_emitted_enums(dump))
  if got_paw != want:
    errs.append("paw Mid emit_cpp.emitEnum != golden")
    errs.append("--- paw ---")
    errs.append(got_paw.rstrip("\n"))
  return errs


def _check_dual_ok_marked(data: dict) -> list[str]:
  errs: list[str] = []
  for p in data["pairs"]:
    if p.get("status") == "dual_ok":
      cmp = p.get("compare")
      if cmp not in _OK_COMPARES:
        errs.append(f"pair {p.get('id')}: dual_ok but unknown compare={cmp}")
  return errs


def main() -> int:
  fail = 0
  data = _load_pairs()
  for label, errs in (
    ("tree_parity", _check_tree_parity()),
    ("pair_paths", _check_pair_paths(data)),
    ("dual_ok_meta", _check_dual_ok_marked(data)),
    ("emit_enum", _check_emit_enum()),
    ("tokenize_dump", _check_tokenize_dump()),
    ("parse_dump", _check_parse_dump()),
    ("mid_dump", _check_mid_dump()),
    ("emit_cpp_norm", _check_emit_cpp_norm()),
  ):
    if errs:
      # missing exe → soft fail only if message starts with skip? User wants gate: require exe after c1_link.
      # Treat skip as FAIL so CI that only runs dual without c1 still reminds; after c1_link must be green.
      fail = 1
      print(f"FAIL {label}", flush=True)
      for e in errs:
        print(" ", e, flush=True)
    else:
      print(f"OK {label}", flush=True)

  dual_ok = [p["id"] for p in data["pairs"] if p.get("status") == "dual_ok"]
  print(f"dual_ok pairs: {', '.join(dual_ok) or '(none)'}", flush=True)
  if fail:
    print("FAIL paw_dual_compare", flush=True)
    return 1
  print("OK paw_dual_compare", flush=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
