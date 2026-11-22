"""原生测例批跑：列表与 parallel_build._list_all_tests 一致；译码经 c1_test_main.exe。

两阶段：串行 emit（避免 exe 文件锁），并行 cl+run。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from parallel_build import _list_all_tests  # noqa: E402

BIN = ROOT / "compiler" / "stages" / "stage1" / "bin"
C1_TEST = BIN / "c1_test_main.exe"
RUNTIME_LIB = ROOT / "out" / "runtime" / "lib" / "py2cpp_runtime.lib"
# One shared amalgamation obj for all parallel links (avoid N× cl races on sqlite3.c).
SHARED_SQLITE_OBJ = ROOT / "out" / "runtime" / "lib" / "sqlite3.obj"
SQLITE3_C = ROOT / "third_party" / "sqlite" / "sqlite3.c"
LOG_DIR = ROOT / "out" / ".native_build_logs"


def _run(
  cmd: list[str],
  env: dict[str, str],
  lines: list[str],
  timeout_sec: float | None = None,
) -> int:
  last_err = ""
  for attempt in range(5):
    try:
      p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
      )
      lines.append("$ " + " ".join(str(c) for c in cmd))
      if p.stdout:
        lines.append(p.stdout)
      if p.stderr:
        lines.append(p.stderr)
      return p.returncode
    except subprocess.TimeoutExpired as e:
      lines.append("$ " + " ".join(str(c) for c in cmd))
      lines.append(f"TimeoutExpired after {timeout_sec}s")
      if e.stdout:
        lines.append(e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", "replace"))
      if e.stderr:
        lines.append(e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", "replace"))
      return 124
    except OSError as e:
      last_err = str(e)
      time.sleep(0.5 * (attempt + 1))
  lines.append("$ " + " ".join(str(c) for c in cmd))
  lines.append(f"OSError after retry: {last_err}")
  return 127


def _emit_one(rel: str, env: dict[str, str]) -> tuple[str, bool, str]:
  src = ROOT / "tests" / rel.replace("/", os.sep)
  log_path = LOG_DIR / (rel.replace("\\", "__").replace("/", "__") + ".log")
  LOG_DIR.mkdir(parents=True, exist_ok=True)
  lines: list[str] = []
  if not src.is_file():
    msg = f"missing {src}"
    log_path.write_text(msg, encoding="utf-8")
    return rel, False, msg
  rc = _run([str(C1_TEST), "--out", "out", str(src)], env, lines)
  log_path.write_text("\n".join(lines), encoding="utf-8")
  if rc != 0:
    return rel, False, "emit fail"
  stem_cpp = ROOT / "out" / "tests" / Path(rel).with_suffix(".cpp")
  if not stem_cpp.is_file():
    return rel, False, "missing cpp"
  return rel, True, "emitted"


def _cl_run_one(rel: str, env: dict[str, str]) -> tuple[str, bool, str, float]:
  t0 = time.perf_counter()
  log_path = LOG_DIR / (rel.replace("\\", "__").replace("/", "__") + ".log")
  lines: list[str] = []
  if log_path.is_file():
    lines.append(log_path.read_text(encoding="utf-8", errors="replace"))
  stem_cpp = ROOT / "out" / "tests" / Path(rel).with_suffix(".cpp")
  stem_exe = stem_cpp.with_suffix(".exe")
  obj = stem_cpp.with_suffix(".obj")
  out_dir = stem_cpp.parent
  # Amalgamate sibling helper.cpp into the test TU (single TU; avoid LNK2005).
  try:
    main_txt = stem_cpp.read_text(encoding="utf-8", errors="replace")
    for dep in sorted(out_dir.glob("*.cpp")):
      if dep.resolve() == stem_cpp.resolve() or dep.name.startswith("test_"):
        continue
      inc = f'#include "{dep.name}"'
      if inc not in main_txt:
        main_txt = main_txt + "\n" + inc + "\n"
        stem_cpp.write_text(main_txt, encoding="utf-8")
  except OSError:
    pass
  # Prefer shared sqlite3.obj (built once in main). Never compile sqlite3.c here
  # under the parallel pool — that races (PDB/tmp) and yields false "sqlite3 cl fail".
  sqlite_extra: list[str] = []
  shared_sql = env.get("PAW_NATIVE_SQLITE_OBJ", "").strip()
  if shared_sql:
    if not Path(shared_sql).is_file():
      log_path.write_text("\n".join(lines + [f"missing shared sqlite obj: {shared_sql}"]), encoding="utf-8")
      return rel, False, "sqlite3 cl fail", time.perf_counter() - t0
    sqlite_extra.append(shared_sql)
  elif SHARED_SQLITE_OBJ.is_file():
    sqlite_extra.append(str(SHARED_SQLITE_OBJ))
  elif SQLITE3_C.is_file():
    log_path.write_text(
      "\n".join(lines + ["sqlite3.c present but shared obj missing; run via paw_native_build_all.bat"]),
      encoding="utf-8",
    )
    return rel, False, "sqlite3 cl fail", time.perf_counter() - t0
  link_cmd = [
    "cl",
    "/nologo",
    "/EHsc",
    "/utf-8",
    "/std:c++17",
    f"/I{ROOT / 'out' / 'runtime'}",
    f"/I{ROOT / 'third_party' / 'sqlite'}",
    f"/I{out_dir}",
    f"/Fo:{obj}",
    f"/Fe:{stem_exe}",
    str(stem_cpp),
    "/link",
    "/STACK:8388608",
    str(RUNTIME_LIB),
  ]
  link_cmd.extend(sqlite_extra)
  rc = _run(link_cmd, env, lines)
  if rc != 0:
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return rel, False, "cl fail", time.perf_counter() - t0
  # 防 ProcessPool / 异步测例挂死拖垮整批（默认 60s）
  run_to = float(env.get("PAW_NATIVE_RUN_TIMEOUT", "60"))
  rc = _run([str(stem_exe)], env, lines, timeout_sec=run_to)
  log_path.write_text("\n".join(lines), encoding="utf-8")
  ok = rc == 0
  if rc == 124:
    return rel, False, "run timeout", time.perf_counter() - t0
  return rel, ok, ("ok" if ok else f"run exit {rc}"), time.perf_counter() - t0


def main() -> int:
  jobs_n = int(os.environ.get("PY2CPP_BUILD_JOBS", "8"))
  args = sys.argv[1:]
  if args and args[0] == "--jobs":
    jobs_n = int(args[1])
    args = args[2:]
  if args:
    rels = [a.replace("\\", "/") for a in args]
  else:
    rels = [r.replace("\\", "/") for r in _list_all_tests()]

  env = os.environ.copy()
  if not env.get("VCINSTALLDIR"):
    print("WARN: VCINSTALLDIR unset; cl may fail — run via paw_native_build_all.bat", flush=True)

  if not C1_TEST.is_file():
    print(f"FAIL missing {C1_TEST}", flush=True)
    return 1
  if not RUNTIME_LIB.is_file():
    print(f"FAIL missing {RUNTIME_LIB}", flush=True)
    return 1

  # Build shared sqlite3.obj once for all parallel link steps.
  if SQLITE3_C.is_file():
    sql_obj = SHARED_SQLITE_OBJ
    sql_obj.parent.mkdir(parents=True, exist_ok=True)
    need_sql = (not sql_obj.is_file()) or (
      sql_obj.stat().st_mtime < SQLITE3_C.stat().st_mtime
    )
    if need_sql:
      print(f"=== build shared {sql_obj.relative_to(ROOT)} ===", flush=True)
      lines_sql: list[str] = []
      rc_sql = _run(
        [
          "cl",
          "/nologo",
          "/O2",
          "/c",
          "/DSQLITE_THREADSAFE=1",
          "/DSQLITE_OMIT_LOAD_EXTENSION=1",
          f"/I{ROOT / 'third_party' / 'sqlite'}",
          f"/Fo:{sql_obj}",
          str(SQLITE3_C),
        ],
        env,
        lines_sql,
      )
      if rc_sql != 0:
        print("FAIL shared sqlite3.obj", flush=True)
        print("\n".join(lines_sql), flush=True)
        return 1
    else:
      print(f"=== reuse shared {sql_obj.relative_to(ROOT)} ===", flush=True)
    env["PAW_NATIVE_SQLITE_OBJ"] = str(sql_obj)

  print(f"=== phase1 emit ({len(rels)} tests, sequential) ===", flush=True)
  t_batch = time.perf_counter()
  emitted: list[str] = []
  fail: list[tuple[str, str]] = []
  for rel in rels:
    r, ok, msg = _emit_one(rel, env)
    if ok:
      emitted.append(r)
      print(f"[EMIT] {r}", flush=True)
    else:
      fail.append((r, msg))
      print(f"[FAIL] {r} {msg}", flush=True)

  print(f"=== phase2 cl+run ({len(emitted)} tests, jobs={jobs_n}) ===", flush=True)
  ok_n = 0
  with ThreadPoolExecutor(max_workers=max(1, jobs_n)) as ex:
    futs = {ex.submit(_cl_run_one, rel, env): rel for rel in emitted}
    for fut in as_completed(futs):
      rel, ok, msg, sec = fut.result()
      mark = "OK" if ok else "FAIL"
      print(f"[{mark}] {rel} ({sec:.1f}s) {msg}", flush=True)
      if ok:
        ok_n += 1
      else:
        fail.append((rel, msg))

  elapsed = time.perf_counter() - t_batch
  total = len(rels)
  print(
    f"\n=== native build_all: {ok_n}/{total} ok in {elapsed:.1f}s; fail={len(fail)} ===",
    flush=True,
  )
  for rel, msg in fail[:50]:
    print(f"  FAIL {rel}: {msg}", flush=True)
  if len(fail) > 50:
    print(f"  ... +{len(fail) - 50} more", flush=True)
  return 0 if not fail else 1


if __name__ == "__main__":
  raise SystemExit(main())
