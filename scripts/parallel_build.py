"""并行翻译+编译 test/examples（每 job 捕获输出，完成时整块打印，避免穿插）。"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MATCH_PY = SCRIPTS / "match_test_files.py"
LOG_DIR = ROOT / "generated" / ".build_logs"


@dataclass(frozen=True)
class Job:
  rel: str
  src_root: str
  expect_fail: bool = False


@dataclass
class JobResult:
  rel: str
  ok: bool
  seconds: float
  exit_code: int
  exe: str
  log_path: str
  message: str
  log_text: str


def _default_jobs() -> int:
  env = os.environ.get("PY2CPP_BUILD_JOBS")
  if env:
    try:
      return max(1, int(env))
    except ValueError:
      pass
  return 16


def _log_file_for(rel: str) -> Path:
  safe = rel.replace("\\", "__").replace("/", "__")
  LOG_DIR.mkdir(parents=True, exist_ok=True)
  return LOG_DIR / f"{safe}.log"


def _clean_msvc_obj(gen_dir: Path, rel: str) -> None:
  stem = Path(rel).stem
  objdir = gen_dir / Path(rel).parent
  for p in (
    objdir / f"{stem}.obj",
    objdir / f"{stem}__sqlite3.obj",
    gen_dir / f"{stem}.obj",
    ROOT / f"{stem}.obj",
  ):
    try:
      p.unlink()
    except FileNotFoundError:
      pass


def _job_deps_mtime(job: Job) -> list[Path]:
  """exe 增量跳过所依赖的路径。"""
  src = ROOT / job.src_root / job.rel.replace("/", os.sep)
  deps: list[Path] = [src]
  gen_cpp = ROOT / "generated" / job.src_root / Path(job.rel).with_suffix(".cpp")
  deps.append(gen_cpp)
  rt = ROOT / "generated" / "runtime"
  deps.append(rt / "py2cpp" / "minimal.h")
  fat = rt / "lib" / "py2cpp_runtime.lib"
  if fat.is_file():
    deps.append(fat)
  return deps


def _job_up_to_date(job: Job, exe: Path, extra: list[str]) -> bool:
  """源 / 生成 cpp / runtime 未变且已有 exe → 跳过翻译+编译。"""
  if job.expect_fail:
    return False
  if any(a == "--debug" or a.startswith("--debug") for a in extra):
    return False
  if os.environ.get("PY2CPP_FORCE_BUILD", "").strip() in ("1", "true", "yes"):
    return False
  if not exe.is_file():
    return False
  exe_m = exe.stat().st_mtime
  for dep in _job_deps_mtime(job):
    if not dep.is_file():
      return False
    if exe_m < dep.stat().st_mtime:
      return False
  return True


def _run_job(job: Job, extra: list[str]) -> JobResult:
  t0 = time.perf_counter()
  src = ROOT / job.src_root / job.rel.replace("/", os.sep)
  gen_dir = ROOT / "generated" / job.src_root
  exe = gen_dir / Path(job.rel).with_suffix(".exe")
  log_path = _log_file_for(f"{job.src_root}__{job.rel}")
  if _job_up_to_date(job, exe, extra):
    seconds = time.perf_counter() - t0
    msg = "skip (up-to-date)"
    log_path.write_text(msg + "\n", encoding="utf-8")
    return JobResult(
      rel=f"{job.src_root}/{job.rel}",
      ok=True,
      seconds=seconds,
      exit_code=0,
      exe=str(exe),
      log_path=str(log_path),
      message=msg,
      log_text=msg,
    )
  cmd = [
    sys.executable,
    str(ROOT / "main.py"),
    str(src.relative_to(ROOT)),
    "-o",
    "generated",
    "-c",
    "--compiler",
    "cl",
    "--exe",
    str(exe),
    *extra,
  ]
  proc = subprocess.run(
    cmd,
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
  )
  seconds = time.perf_counter() - t0
  _clean_msvc_obj(gen_dir, job.rel)
  log_text = ""
  if proc.stdout:
    log_text += proc.stdout
  if proc.stderr:
    if log_text and not log_text.endswith("\n"):
      log_text += "\n"
    log_text += proc.stderr
  log_path.write_text(log_text, encoding="utf-8")
  compile_ok = proc.returncode == 0 and exe.is_file()
  if job.expect_fail:
    ok = proc.returncode != 0
    message = "compile rejected as expected" if ok else "should NOT compile"
  else:
    ok = compile_ok
    if proc.returncode != 0:
      message = f"exit {proc.returncode}"
    elif not exe.is_file():
      message = "exe missing"
    else:
      message = "OK"
  return JobResult(
    rel=f"{job.src_root}/{job.rel}",
    ok=ok,
    seconds=seconds,
    exit_code=proc.returncode,
    exe=str(exe),
    log_path=str(log_path),
    message=message,
    log_text=log_text,
  )


def _job_path(job: Job) -> str:
  return f"{job.src_root}\\{job.rel.replace('/', os.sep)}"


def _print_job_report(job: Job, res: JobResult) -> None:
  path = _job_path(job)
  if job.expect_fail:
    print(f"=== expect compile FAIL: {path} ===")
  else:
    print(f"=== {path} ===")
  if res.log_text:
    print(res.log_text.rstrip())
  print(f"耗时: {path} {res.seconds:.2f}s（翻译+编译）")
  if job.expect_fail:
    if res.ok:
      print("OK: compile rejected as expected.")
    else:
      print(f"ERROR: {path} should NOT compile.")
  elif res.ok:
    print(f"OK: {res.exe}")
  elif res.exit_code != 0:
    print(f"ERROR: build failed (exit {res.exit_code})")
  else:
    print(f"WARNING: exe not found: {res.exe}")
  print()


def _list_all_tests() -> list[str]:
  test_dir = ROOT / "test"
  out: list[str] = []
  for path in sorted(test_dir.rglob("test_*.py")):
    parts = path.parts
    if "fail" in parts or "perf" in parts:
      continue
    if path.name.endswith("_fail.py"):
      continue
    out.append(str(path.relative_to(test_dir)))
  return out


def _list_fail_tests() -> list[str]:
  fail_dir = ROOT / "test" / "fail"
  return sorted(
    p.name for p in fail_dir.glob("test_*_fail.py") if p.is_file()
  )


def _match_tests(patterns: list[str]) -> list[str]:
  proc = subprocess.run(
    [sys.executable, str(MATCH_PY), *patterns],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
  )
  if proc.returncode != 0:
    return []
  return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def _parse_jobs_and_rest(argv: list[str]) -> tuple[int, list[str]]:
  jobs = _default_jobs()
  rest: list[str] = []
  i = 0
  while i < len(argv):
    arg = argv[i]
    if arg == "--jobs":
      jobs = max(1, int(argv[i + 1]))
      i += 2
      continue
    if arg.startswith("--jobs="):
      jobs = max(1, int(arg.split("=", 1)[1]))
      i += 1
      continue
    if arg == "--seq":
      jobs = 1
      i += 1
      continue
    rest.append(arg)
    i += 1
  return jobs, rest


def _split_patterns_and_extra(tail: list[str]) -> tuple[int, list[str], list[str]]:
  jobs_n, rest = _parse_jobs_and_rest(tail)
  patterns: list[str] = []
  extra: list[str] = []
  for arg in rest:
    if arg.startswith("-"):
      extra.append(arg)
    else:
      patterns.append(arg)
  return jobs_n, patterns, extra


def _print_batch_total(label: str, elapsed: float, jobs_n: int, count: int) -> None:
  if jobs_n > 1:
    print(
      f"耗时: {label} {elapsed:.2f}s（翻译+编译，{count} 个 job，{jobs_n} 路并行）"
    )
  else:
    print(f"耗时: {label} {elapsed:.2f}s（翻译+编译，{count} 个 job）")


def _run_jobs(jobs: list[Job], extra: list[str], jobs_n: int, label: str) -> int:
  if not jobs:
    print(f"ERROR: no {label} jobs.", file=sys.stderr)
    return 1
  total = len(jobs)
  print(f"[py2cpp] {label}: {total} job(s), parallel={jobs_n}")
  if not _cl_available():
    print(
      "NOTE: MSVC cl not on PATH. Run from x64 Native Tools Command Prompt "
      "or ensure scripts\\_init_msvc.bat ran.",
      file=sys.stderr,
    )
  t_batch = time.perf_counter()
  results: list[JobResult] = []
  if jobs_n <= 1:
    for job in jobs:
      res = _run_job(job, extra)
      _print_job_report(job, res)
      results.append(res)
  else:
    with ProcessPoolExecutor(max_workers=jobs_n) as pool:
      futures = {pool.submit(_run_job, job, extra): job for job in jobs}
      for fut in as_completed(futures):
        job = futures[fut]
        res = fut.result()
        _print_job_report(job, res)
        results.append(res)
  elapsed = time.perf_counter() - t_batch
  _print_batch_total(label, elapsed, jobs_n, total)
  failed = [r for r in results if not r.ok]
  if failed:
    print("FAILED builds:", end="")
    for r in failed:
      print(f" {r.rel.replace('/', os.sep)}", end="")
    print()
    return 1
  print(f"All {total} {label} job(s) succeeded.")
  return 0


def _cl_available() -> bool:
  from shutil import which
  return which("cl") is not None


def cmd_all(extra: list[str], jobs_n: int) -> int:
  rels = _list_all_tests()
  jobs = [Job(rel=rel, src_root="test") for rel in rels]
  return _run_jobs(jobs, extra, jobs_n, "build all tests")


def cmd_match(patterns: list[str], extra: list[str], jobs_n: int) -> int:
  rels = _match_tests(patterns)
  if not rels:
    print(f"ERROR: no test matched patterns: {patterns!r}", file=sys.stderr)
    return 1
  jobs = [Job(rel=rel, src_root="test") for rel in rels]
  return _run_jobs(jobs, extra, jobs_n, "build matched tests")


def cmd_fail(extra: list[str], jobs_n: int) -> int:
  rels = [f"fail/{name}" for name in _list_fail_tests()]
  jobs = [Job(rel=rel, src_root="test", expect_fail=True) for rel in rels]
  return _run_jobs(jobs, extra, jobs_n, "negative compile tests")


def cmd_files(rels: list[str], src_root: str, extra: list[str], jobs_n: int) -> int:
  jobs = [Job(rel=rel.replace("\\", "/"), src_root=src_root) for rel in rels]
  return _run_jobs(jobs, extra, jobs_n, f"build {src_root} files")


def main(argv: list[str] | None = None) -> int:
  args = list(argv if argv is not None else sys.argv[1:])
  if not args:
    print(
      "用法: parallel_build.py all|match|fail|files [--jobs N] [--seq] [main.py flags...]\n"
      "  match PATTERN [...]  同 build.bat\n"
      "  files --root test|examples REL [...]\n"
      "  默认并行 16；PY2CPP_BUILD_JOBS 可覆盖；--seq 强制串行",
      file=sys.stderr,
    )
    return 2
  mode = args[0]
  tail = args[1:]
  if mode == "all":
    jobs_n, extra = _parse_jobs_and_rest(tail)
    return cmd_all(extra, jobs_n)
  if mode == "match":
    jobs_n, patterns, extra = _split_patterns_and_extra(tail)
    if not patterns:
      print("ERROR: match 需要 PATTERN", file=sys.stderr)
      return 2
    return cmd_match(patterns, extra, jobs_n)
  if mode == "fail":
    jobs_n, extra = _parse_jobs_and_rest(tail)
    return cmd_fail(extra, jobs_n)
  if mode == "files":
    jobs_n, rest = _parse_jobs_and_rest(tail)
    src_root = "test"
    rels: list[str] = []
    extra: list[str] = []
    i = 0
    while i < len(rest):
      arg = rest[i]
      if arg == "--root":
        src_root = rest[i + 1]
        i += 2
        continue
      if arg.startswith("--root="):
        src_root = arg.split("=", 1)[1]
        i += 1
        continue
      if arg.startswith("-"):
        extra.append(arg)
        i += 1
        continue
      rels.append(arg)
      i += 1
    if not rels:
      print("ERROR: files 需要至少一个 REL 路径", file=sys.stderr)
      return 2
    return cmd_files(rels, src_root, extra, jobs_n)
  print(f"ERROR: unknown mode {mode!r}", file=sys.stderr)
  return 2


if __name__ == "__main__":
  raise SystemExit(main())
