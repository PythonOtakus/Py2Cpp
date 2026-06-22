"""将翻译生成的 C++ 源文件编译为目标文件或可执行文件。

支持 g++、clang++、MSVC（``cl``）；Windows 上 ``auto`` 可优先调用输出目录下的 ``build.bat``。
用户入口在 ``generated/<源路径>/``；标准库在 ``generated/runtime/``（含 ``py2cpp.cpp``）。
编译时会自动添加 ``-I`` 入口目录与 ``runtime`` 目录。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .emit.layout_config_emit import UMBRELLA_HEADER
from .translator import RUNTIME_CPP, RUNTIME_OUTPUT_SUBDIR, RUNTIME_PREFIX

REPO_ROOT = Path(__file__).resolve().parent.parent
SQLITE3_SOURCE = REPO_ROOT / "third_party" / "sqlite" / "sqlite3.c"
SQLITE_INCLUDE_DIR = REPO_ROOT / "third_party" / "sqlite"


def _source_text(source: Path) -> str:
  try:
    return source.read_text(encoding="utf-8")
  except OSError:
    return ""


def source_needs_sqlite(source: Path) -> bool:
  """翻译产物引用 ``sql/sqlite`` 时需链接 amalgamation。"""
  text = _source_text(source)
  if not text:
    return False
  markers = (
    "py2cpp/sql/sqlite",
    "SqliteConnection",
    "PySqliteConnection",
    "SqliteCursor",
    "sql::sqlite",
  )
  return any(m in text for m in markers)


def runtime_has_sqlite_inl(source: Path) -> bool:
  """``minimal.h`` → ``sql/sqlite.h`` → ``sqlite.inl`` 时任意 runtime 测试 TU 均需 sqlite 头/链。"""
  umbrella = Path(UMBRELLA_HEADER)
  for parent in source.parents:
    runtime_dir = parent / RUNTIME_OUTPUT_SUBDIR
    if (runtime_dir / umbrella).is_file():
      return (runtime_dir / "py2cpp/sql/sqlite.inl").is_file()
  return False


def needs_sqlite_build(source: Path) -> bool:
  return source_needs_sqlite(source) or runtime_has_sqlite_inl(source)


def discover_sqlite_extra_sources(source: Path) -> list[Path]:
  if not needs_sqlite_build(source):
    return []
  if SQLITE3_SOURCE.is_file():
    return [SQLITE3_SOURCE]
  return []


def _partition_sqlite_sources(sources: list[Path]) -> tuple[list[Path], list[Path]]:
  """将 ``sqlite3.c`` 与主 TU 拆开，避免并行编译时共写 ``sqlite3.obj``。"""
  sqlite = SQLITE3_SOURCE.resolve()
  core: list[Path] = []
  sqlite_sources: list[Path] = []
  for s in sources:
    if s.resolve() == sqlite:
      sqlite_sources.append(s)
    else:
      core.append(s)
  return core, sqlite_sources


def sqlite3_obj_path(primary: Path) -> Path:
  """每个测试 ``.cpp`` 独立 ``{stem}__sqlite3.obj``，供并行 ``build_all`` 使用。"""
  return primary.parent / f"{primary.stem}__sqlite3.obj"


def discover_sqlite_include_dirs(source: Path) -> list[Path]:
  if not needs_sqlite_build(source):
    return []
  if SQLITE_INCLUDE_DIR.is_dir():
    return [SQLITE_INCLUDE_DIR]
  return []


@dataclass
class CompileResult:
  """单次编译尝试的结果。"""

  ok: bool
  compiler: str
  artifact: Path | None
  stdout: str
  stderr: str


def default_exe_path(source: Path) -> Path:
  """根据源文件路径推导默认可执行文件路径。"""
  stem = source.with_suffix("")
  if sys.platform == "win32":
    return stem.with_suffix(".exe")
  return stem


def runtime_cpp_path(source: Path) -> Path | None:
  """查找标准库实现 ``runtime/py2cpp.cpp``（或同目录遗留的 ``py2cpp.cpp``）。"""
  if source.name == RUNTIME_CPP:
    return None
  same_dir = source.parent / RUNTIME_CPP
  if same_dir.is_file():
    return same_dir
  for parent in source.parents:
    candidate = parent / RUNTIME_OUTPUT_SUBDIR / RUNTIME_CPP
    if candidate.is_file():
      return candidate
  return None


def discover_include_dirs(source: Path, explicit: Path | None = None) -> list[Path]:
  """入口目录 + ``generated/runtime``（供 ``#include \"py2cpp/...\"``）。"""
  dirs: list[Path] = []

  def add(path: Path) -> None:
    resolved = path.resolve()
    if resolved not in dirs:
      dirs.append(resolved)

  if explicit is not None:
    add(explicit)
  add(source.parent)
  umbrella = Path(UMBRELLA_HEADER)
  for parent in source.parents:
    runtime_dir = parent / RUNTIME_OUTPUT_SUBDIR
    if (runtime_dir / RUNTIME_CPP).is_file() or (runtime_dir / umbrella).is_file():
      add(runtime_dir)
      break
  for inc in discover_sqlite_include_dirs(source):
    add(inc)
  return dirs


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
  # ``cl /utf-8`` 的诊断为 UTF-8；Windows 默认用系统 ANSI 解码会得到 ``?``
  encoding: str | None = None
  if sys.platform == "win32" and cmd and cmd[0] == "cl":
    encoding = "utf-8"
  return subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    encoding=encoding,
    errors="replace",
    cwd=str(cwd) if cwd else None,
  )


def _which(name: str) -> str | None:
  return shutil.which(name)


def _links_runtime_cpp(source: Path) -> bool:
  """测试/示例入口通过 ``py2cpp.h`` 拉入 ``*.inl``；再链接 ``py2cpp.cpp`` 会重复定义。"""
  if source.name == RUNTIME_CPP:
    return False
  parts = source.resolve().parts
  # ``test/``、``examples/`` 与集成测相同：仅 ``py2cpp.h`` + ``*.inl``，勿链 runtime TU
  if "test" in parts or "examples" in parts:
    return False
  return True


def _all_sources(source: Path, extra_sources: list[Path] | None) -> list[Path]:
  primary = source.resolve()
  extras = [p.resolve() for p in (extra_sources or [])]
  for p in discover_sqlite_extra_sources(primary):
    if p not in extras:
      extras.append(p)
  runtime = runtime_cpp_path(primary)
  if (
    runtime
    and runtime not in extras
    and runtime != primary
    and _links_runtime_cpp(primary)
  ):
    extras.append(runtime)
  return [primary, *extras]


def source_uses_openmp(source: Path) -> bool:
  """生成 ``.cpp`` 是否含 OpenMP pragma。"""
  try:
    text = source.read_text(encoding="utf-8")
  except OSError:
    return False
  return "#pragma omp" in text


def compile_command(
  source: Path,
  *,
  include_dir: Path | None = None,
  compiler: str = "auto",
  exe: Path | None = None,
  obj_only: bool = False,
  std: str = "c++11",
  extra_sources: list[Path] | None = None,
  openmp: bool | None = None,
) -> list[str] | list[list[str]] | None:
  """构造编译命令；无法识别编译器时返回 ``None``。"""
  all_sources = _all_sources(source, extra_sources)
  core, sqlite_srcs = _partition_sqlite_sources(all_sources)
  inc_dirs = [str(p) for p in discover_include_dirs(source, include_dir)]
  inc_flags = [f"-I{d}" for d in inc_dirs]
  out_exe = (exe or default_exe_path(source)).resolve()
  use_openmp = openmp
  if use_openmp is None:
    use_openmp = any(source_uses_openmp(s) for s in all_sources)
  sqlite_obj = sqlite3_obj_path(source) if sqlite_srcs else None

  def gpp_sqlite_compile_cmd(tool: str) -> list[str]:
    omp = ["-fopenmp"] if use_openmp else []
    return [
      tool,
      f"-std={std}",
      "-Wall",
      "-Wextra",
      "-c",
      *omp,
      *inc_flags,
      "-o",
      str(sqlite_obj),
      str(SQLITE3_SOURCE.resolve()),
    ]

  def gpp_like(tool: str) -> list[str] | list[list[str]]:
    omp = ["-fopenmp"] if use_openmp else []
    if obj_only:
      cmds = [ [*([tool, f"-std={std}", "-Wall", "-Wextra", "-c", *omp, *inc_flags]), str(s)] for s in core ]
      if sqlite_obj is not None:
        cmds.append(gpp_sqlite_compile_cmd(tool))
      return cmds
    if sqlite_obj is not None:
      return [
        gpp_sqlite_compile_cmd(tool),
        [
          tool,
          f"-std={std}",
          "-Wall",
          "-Wextra",
          *omp,
          "-o",
          str(out_exe),
          *inc_flags,
          *[str(s) for s in core],
          str(sqlite_obj),
        ],
      ]
    return [
      tool,
      f"-std={std}",
      "-Wall",
      "-Wextra",
      *omp,
      "-o",
      str(out_exe),
      *inc_flags,
      *[str(s) for s in core],
    ]

  cl_link_objs = [sqlite_obj] if sqlite_obj is not None and not obj_only else None

  if compiler == "g++":
    return gpp_like("g++") if _which("g++") else None
  if compiler == "clang++":
    return gpp_like("clang++") if _which("clang++") else None
  if compiler == "cl":
    return (
      _cmd_msvc_cl(
        core, inc_dirs, out_exe, obj_only, std,
        use_openmp=use_openmp, link_objs=cl_link_objs,
      )
      if _which("cl")
      else None
    )

  if compiler == "msvc" or (compiler == "auto" and sys.platform == "win32"):
    cmd = _cmd_msvc_cl(
      core, inc_dirs, out_exe, obj_only, std,
      use_openmp=use_openmp, link_objs=cl_link_objs,
    )
    if cmd and _which("cl"):
      return cmd
  if compiler in ("auto", "g++"):
    cmd = gpp_like("g++")
    if _which("g++"):
      return cmd
  if compiler in ("auto", "clang++"):
    cmd = gpp_like("clang++")
    if _which("clang++"):
      return cmd
  if compiler == "auto":
    cmd = _cmd_msvc_cl(
      core, inc_dirs, out_exe, obj_only, std,
      use_openmp=use_openmp, link_objs=cl_link_objs,
    )
    if cmd and _which("cl"):
      return cmd
  return None


def _prepare_windows_link_exe(exe: Path) -> None:
  """Windows 链接前释放目标 exe（避免 LNK1104：进程仍占用时无法覆盖）。"""
  try:
    exe.unlink()
  except FileNotFoundError:
    return
  except OSError:
    if sys.platform != "win32":
      return
    subprocess.run(
      ["taskkill", "/F", "/IM", exe.name],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      check=False,
    )
    try:
      exe.unlink()
    except OSError:
      pass


def _msvc_std_flag(std: str) -> str:
  """MSVC 不支持 ``/std:c++11``，与 C++11 目标对齐时使用 ``/std:c++14``。"""
  flag = std if std.startswith("/std:") else f"/std:{std}"
  if flag in ("/std:c++11", "/std:gnu++11"):
    return "/std:c++14"
  return flag


def _msvc_object_file_flags(sources: list[Path]) -> list[str]:
  """MSVC 默认把 ``.obj`` 写到 cwd；并行编译时同名 stem 会 Permission denied。

  单 TU → ``/Fo`` 指向与 ``.cpp`` 同目录的 ``.obj``；同目录多 TU → ``/Fo`` 目录。
  """
  if not sources:
    return []
  resolved = [s.resolve() for s in sources]
  if len(resolved) == 1:
    return [f"/Fo{resolved[0].with_suffix('.obj')}"]
  parents = {s.parent for s in resolved}
  if len(parents) == 1:
    return [f"/Fo{next(iter(parents))}\\"]
  return [f"/Fo{resolved[0].parent}\\"]


def cleanup_msvc_objects(sources: list[Path], *, primary: Path | None = None) -> None:
  """删除 MSVC ``cl`` 链接后残留的 ``.obj``（含 ``py2cpp.cpp`` → ``py2cpp.obj``）。"""
  stems = {src.stem for src in sources}
  stems.add(Path(RUNTIME_CPP).stem)
  dirs: set[Path] = {src.parent.resolve() for src in sources}
  dirs.add(Path.cwd().resolve())
  anchor = (primary or (sources[0] if sources else None))
  if anchor is not None:
    anchor = anchor.resolve()
    for inc in discover_include_dirs(anchor):
      dirs.add(Path(inc).resolve())
    runtime = runtime_cpp_path(anchor)
    if runtime is not None:
      dirs.add(runtime.parent.resolve())
    if anchor.name == RUNTIME_CPP:
      dirs.add(anchor.parent.resolve())
    sq_obj = sqlite3_obj_path(anchor)
    if sq_obj.is_file():
      try:
        sq_obj.unlink()
      except OSError:
        pass
  for directory in dirs:
    for stem in stems:
      obj = directory / f"{stem}.obj"
      if obj.is_file():
        try:
          obj.unlink()
        except OSError:
          pass


def _cmd_msvc_cl_sqlite_compile(
  include_dirs: list[str],
  obj_path: Path,
  std: str,
) -> list[str]:
  std_flag = _msvc_std_flag(std)
  cmd = ["cl", "/nologo", "/EHsc", "/utf-8", std_flag, "/c"]
  cmd.append("/DSQLITE_THREADSAFE=1")
  cmd.append("/DSQLITE_OMIT_LOAD_EXTENSION=1")
  for inc in include_dirs:
    cmd.append(f"/I{inc}")
  cmd.append(f"/Fo{obj_path}")
  cmd.append(str(SQLITE3_SOURCE.resolve()))
  return cmd


def _cmd_msvc_cl(
  sources: list[Path],
  include_dirs: list[str],
  exe: Path,
  obj_only: bool,
  std: str,
  *,
  use_openmp: bool = False,
  link_objs: list[Path] | None = None,
) -> list[str]:
  std_flag = _msvc_std_flag(std)
  # ``/utf-8``：源文件与执行字符集均为 UTF-8（编译期中文 static_assert 等）
  cmd = ["cl", "/nologo", "/EHsc", "/utf-8", std_flag]
  if any(needs_sqlite_build(s) for s in sources) or link_objs:
    cmd.append("/DSQLITE_THREADSAFE=1")
    cmd.append("/DSQLITE_OMIT_LOAD_EXTENSION=1")
  if use_openmp:
    cmd.append("/openmp")
  for inc in include_dirs:
    cmd.append(f"/I{inc}")
  cmd.extend(_msvc_object_file_flags(sources))
  cmd.extend(str(s) for s in sources)
  if link_objs:
    cmd.extend(str(p) for p in link_objs)
  if obj_only:
    cmd.append("/c")
    return cmd
  cmd.append(f"/Fe:{exe}")
  return cmd


def try_build_bat(source: Path) -> CompileResult | None:
  """若输出目录存在 build.bat 且源文件为 py2cpp.cpp，则调用之。"""
  bat = source.parent / "build.bat"
  if not bat.is_file() or source.name != "py2cpp.cpp":
    return None
  r = _run(["cmd", "/c", str(bat)], cwd=source.parent)
  cleanup_msvc_objects([source.resolve()], primary=source)
  obj = source.with_suffix(".obj")
  return CompileResult(
    ok=r.returncode == 0,
    compiler="msvc (build.bat)",
    artifact=obj if obj.is_file() else None,
    stdout=r.stdout or "",
    stderr=r.stderr or "",
  )


def compile_cpp(
  source: Path,
  *,
  include_dir: Path | None = None,
  compiler: str = "auto",
  exe: Path | None = None,
  obj_only: bool = False,
  std: str = "c++11",
  extra_sources: list[Path] | None = None,
  openmp: bool | None = None,
) -> CompileResult:
  """编译 ``source`` 指向的翻译产物；失败时 ``ok`` 为 ``False``。"""
  source = source.resolve()
  sources = _all_sources(source, extra_sources)
  if compiler in ("auto", "msvc"):
    bat_result = try_build_bat(source)
    if bat_result is not None:
      return bat_result

  tried: list[str] = []
  order = [compiler] if compiler != "auto" else ["g++", "clang++", "cl"]
  for name in order:
    cmd = compile_command(
      source,
      include_dir=include_dir,
      compiler=name,
      exe=exe,
      obj_only=obj_only,
      std=std,
      extra_sources=extra_sources,
      openmp=openmp,
    )
    if not cmd:
      continue
    tried.append(name)
    if name == "cl" and not obj_only:
      link_exe = (exe or default_exe_path(source)).resolve()
      if sys.platform == "win32":
        _prepare_windows_link_exe(link_exe)
    try:
      _, sqlite_srcs = _partition_sqlite_sources(sources)
      if name == "cl" and sqlite_srcs and not obj_only:
        inc_dirs = [str(p) for p in discover_include_dirs(source, include_dir)]
        sqlite_obj = sqlite3_obj_path(source)
        r_sq = _run(_cmd_msvc_cl_sqlite_compile(inc_dirs, sqlite_obj, std))
        if r_sq.returncode != 0:
          return CompileResult(
            ok=False,
            compiler=name,
            artifact=None,
            stdout=r_sq.stdout or "",
            stderr=r_sq.stderr or "",
          )
      if isinstance(cmd, list) and cmd and isinstance(cmd[0], list):
        last: subprocess.CompletedProcess[str] | None = None
        for part in cmd:
          last = _run(part)
          if last.returncode != 0:
            break
        r = last or subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
      else:
        r = _run(cmd)
    except FileNotFoundError:
      continue
    artifact: Path | None
    if obj_only:
      artifact = source.with_suffix(".obj" if name == "cl" else ".o")
    else:
      artifact = (exe or default_exe_path(source)).resolve()
    ok = r.returncode == 0
    if name == "cl":
      cleanup_msvc_objects(sources, primary=source)
    return CompileResult(
      ok=ok,
      compiler=name,
      artifact=artifact if ok and (artifact.exists() if artifact else False) else None,
      stdout=r.stdout or "",
      stderr=r.stderr or "",
    )

  return CompileResult(
    ok=False,
    compiler=",".join(tried) or compiler,
    artifact=None,
    stdout="",
    stderr="未在 PATH 中找到可用的 C++ 编译器",
  )
