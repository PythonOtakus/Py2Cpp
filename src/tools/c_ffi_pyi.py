"""从 C 头文件经 libclang 生成 Py2Cpp 风格 ``.pyi``（``@native`` FFI 声明）。

CLI 入口：``scripts/gen_c_ffi.py``。规格见 ``docs/c-ffi-pyi.md``。
"""
from __future__ import annotations

import keyword
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
  from clang.cindex import (
    CursorKind,
    Index,
    LinkageKind,
    TypeKind,
    TranslationUnit,
  )
except ImportError as e:  # pragma: no cover
  print("ERROR: need `pip install clang` (libclang Python bindings).", file=sys.stderr)
  raise SystemExit(2) from e

REPO_ROOT = Path(__file__).resolve().parents[2]
FFI_ROOT = REPO_ROOT / "ffi"

from ..constant.ffi_layout import ffi_opaque_py_name  # noqa: E402

# 空/属性类宏：不发射为 Python 常量
_SKIP_MACRO_NAMES = frozenset({
  "SQLITE_EXTERN",
  "SQLITE_API",
  "SQLITE_CDECL",
  "SQLITE_APICALL",
  "SQLITE_STDCALL",
  "SQLITE_CALLBACK",
  "SQLITE_SYSAPI",
  "SQLITE_DEPRECATED",
  "SQLITE_EXPERIMENTAL",
  "SQLITE_ATOMIC",
  "WINAPI",
  "APIENTRY",
  "APIPRIVATE",
  "CALLBACK",
  "NEAR",
  "FAR",
  "PASCAL",
  "CDECL",
  "STDCALL",
  "DECLSPEC_IMPORT",
  "DECLSPEC_EXPORT",
  "DECLSPEC_NORETURN",
  "DECLSPEC_ALIGN",
  "FORCEINLINE",
  "OPTIONAL",
  "IN",
  "OUT",
  "CONST",
  "VOID",
  "BOOL",
  "TRUE",
  "FALSE",
  "NULL",
  "UNICODE",
  "_UNICODE",
  "WIN32_LEAN_AND_MEAN",
  "NOMINMAX",
  "STRICT",
})

_SKIP_MACRO_PREFIXES = (
  "__",
  "_MSC_",
  "_M_",
  "_WIN32",
  "_WIN64",
  "RC_INVOKED",
)


@dataclass
class OpaqueType:
  """``c_name`` 为 C 标签；``.pyi`` 写 ``type {py_name} = uint64``（``*_h`` 后缀）。"""

  c_name: str

  @property
  def py_name(self) -> str:
    return ffi_opaque_py_name(self.c_name)


@dataclass
class ConstDef:
  name: str
  py_name: str
  native: str | None
  ann: str
  value: str


@dataclass
class ParamDef:
  py_name: str
  ann: str


@dataclass
class FuncDef:
  c_name: str
  py_name: str
  ret: str
  params: list[ParamDef] = field(default_factory=list)
  comment: str = ""


@dataclass
class FfiModel:
  opaques: list[OpaqueType] = field(default_factory=list)
  consts: list[ConstDef] = field(default_factory=list)
  funcs: list[FuncDef] = field(default_factory=list)


def default_pyi_path(header: Path, *, repo_root: Path | None = None) -> Path:
  """由 C/C++ 头路径推导默认 ``.pyi`` 输出路径。

  - 仓库内 ``third_party/.../foo.h`` → ``ffi/.../foo.pyi``（去掉 ``third_party/`` 前缀）
  - 仓库内其它相对路径 ``a/b.h`` → ``ffi/a/b.pyi``
  - 仓库外系统头（如 SDK ``windows.h``）→ ``ffi/<stem>.pyi``（如 ``ffi/windows.pyi``）
  """
  root = (repo_root or REPO_ROOT).resolve()
  header = header.resolve()
  try:
    rel = header.relative_to(root / "third_party")
    return FFI_ROOT / rel.with_suffix(".pyi")
  except ValueError:
    pass
  try:
    rel = header.relative_to(root)
    return FFI_ROOT / rel.with_suffix(".pyi")
  except ValueError:
    pass
  # 系统头：统一小写 stem，避免 Windows.h → ffi/Windows.pyi
  return FFI_ROOT / f"{header.stem.lower()}.pyi"


def find_windows_sdk_um_windows_h() -> Path | None:
  """返回最新 Windows Kits ``um/windows.h``，找不到则 ``None``。"""
  bases = [
    Path(r"C:\Program Files (x86)\Windows Kits\10\Include"),
    Path(r"C:\Program Files\Windows Kits\10\Include"),
  ]
  hits: list[Path] = []
  for base in bases:
    if base.is_dir():
      hits.extend(base.glob("*/um/windows.h"))
  if not hits:
    return None
  return sorted(hits)[-1]


def resolve_header_path(header: Path | str) -> Path:
  """解析 ``--header``：存在则用之；``windows.h`` / ``windows`` 则查找 SDK。"""
  p = Path(header)
  if p.is_file():
    return p.resolve()
  key = p.name.lower() if p.name else str(header).lower()
  if key in {"windows.h", "windows"}:
    found = find_windows_sdk_um_windows_h()
    if found is None:
      raise FileNotFoundError(
        "windows.h not found under Windows Kits; pass a full path with --header"
      )
    return found.resolve()
  raise FileNotFoundError(f"header not found: {header}")


def windows_sdk_version_root(header: Path) -> Path | None:
  """若 ``header`` 位于 ``.../Include/<ver>/...``，返回该 ``<ver>`` 目录。"""
  header = header.resolve()
  for parent in header.parents:
    if parent.name.lower() == "include" and parent.parent.name.lower().startswith("windows kits"):
      # header = Include/ver/um/windows.h → ver is parent of um
      pass
    # .../Include/10.0.x/um/windows.h
    if parent.parent.name.lower() == "include":
      # parent is 10.0.x
      um = parent / "um"
      shared = parent / "shared"
      if um.is_dir() and (um / "windows.h").is_file():
        return parent
  # walk up looking for um/windows.h sibling structure
  for parent in header.parents:
    if (parent / "um" / "windows.h").is_file() and (parent / "shared").is_dir():
      return parent
  return None


def default_clang_args(header: Path) -> list[str]:
  """按头文件位置给出默认 libclang 参数（Win SDK 自动补全）。"""
  header = header.resolve()
  args: list[str] = []
  ver = windows_sdk_version_root(header)
  if ver is not None or header.name.lower() == "windows.h":
    if ver is None:
      wh = find_windows_sdk_um_windows_h()
      ver = windows_sdk_version_root(wh) if wh else None
    args.extend([
      "--target=x86_64-pc-windows-msvc",
      "-fms-extensions",
      "-fms-compatibility",
      "-fms-compatibility-version=19.30",
      "-DWIN32",
      "-D_WIN32",
      "-D_WIN64",
      "-DUNICODE",
      "-D_UNICODE",
      "-DWIN32_LEAN_AND_MEAN",
      "-DNOMINMAX",
      "-DSTRICT",
    ])
    if ver is not None:
      for sub in ("um", "shared", "ucrt", "winrt"):
        d = ver / sub
        if d.is_dir():
          args.append(f"-I{d}")
  return args


def _collect_roots(header: Path) -> list[Path]:
  """传递 include 收集时允许的文件根目录列表。"""
  header = header.resolve()
  roots: list[Path] = []
  ver = windows_sdk_version_root(header)
  if ver is not None:
    roots.append(ver.resolve())
  try:
    roots.append((REPO_ROOT / "third_party").resolve())
  except Exception:
    pass
  roots.append(header.parent.resolve())
  # 去重保序
  out: list[Path] = []
  seen: set[Path] = set()
  for r in roots:
    if r not in seen:
      seen.add(r)
      out.append(r)
  return out


def _file_in_scope(cursor_file: object | None, header: Path, roots: list[Path], *, include_deps: bool) -> bool:
  if cursor_file is None:
    return False
  try:
    p = Path(str(cursor_file)).resolve()
  except OSError:
    return False
  if not include_deps:
    return p == header.resolve()
  if p == header.resolve():
    return True
  for root in roots:
    try:
      p.relative_to(root)
      return True
    except ValueError:
      continue
  return False


def _py_ident(name: str) -> tuple[str, str | None]:
  """返回 (python_name, native_name|None)。"""
  if not name:
    return "_anon", None
  if name.isidentifier() and not keyword.iskeyword(name):
    return name, None
  base = re.sub(r"[^0-9A-Za-z_]", "_", name)
  if not base:
    base = "_anon"
  if base[0].isdigit():
    base = f"_{base}"
  alias = base
  if not alias.isidentifier() or keyword.iskeyword(alias):
    alias = f"{alias}_"
  while keyword.iskeyword(alias) or not alias.isidentifier():
    alias = f"{alias}_"
  if alias == name:
    return name, None
  return alias, name


def _canonical(t):
  try:
    return t.get_canonical()
  except Exception:
    return t


def _type_spelling(t) -> str:
  try:
    return (t.spelling or "").strip()
  except Exception:
    return ""


def _is_incomplete_record(t) -> bool:
  t = _canonical(t)
  if t.kind not in (TypeKind.RECORD, TypeKind.ELABORATED):
    decl = t.get_declaration()
    if decl is None or not decl.kind:
      return False
    if decl.kind == CursorKind.STRUCT_DECL:
      return not any(True for _ in decl.get_children() if _.kind == CursorKind.FIELD_DECL)
    return False
  decl = t.get_declaration()
  if decl is None:
    return True
  if decl.kind != CursorKind.STRUCT_DECL and decl.kind != CursorKind.UNION_DECL:
    return False
  return not any(c.kind == CursorKind.FIELD_DECL for c in decl.get_children())


def _record_name(t) -> str | None:
  t = _canonical(t)
  decl = t.get_declaration()
  if decl is not None and decl.spelling:
    return decl.spelling
  sp = _type_spelling(t)
  m = re.match(r"(?:const\s+)?(?:struct|union)\s+(\w+)", sp)
  if m:
    return m.group(1)
  if t.kind == TypeKind.TYPEDEF:
    return t.get_declaration().spelling or None
  return None


class TypeMapper:
  def __init__(self) -> None:
    self.opaques: dict[str, None] = {}

  def note_opaque(self, name: str) -> None:
    if name and name.isidentifier():
      self.opaques[name] = None

  def map(self, t, *, is_return: bool = False) -> tuple[str, str]:
    """返回 (annotation, optional_comment)。"""
    if t is None:
      return "uintptr", "null type"

    k = t.kind
    if k == TypeKind.VOID:
      return "None", ""

    if k == TypeKind.TYPEDEF:
      name = t.get_declaration().spelling or ""
      can = _canonical(t)
      if name in ("sqlite3_int64", "sqlite_int64"):
        return "int64", ""
      if name in ("sqlite3_uint64", "sqlite_uint64"):
        return "uint64", ""
      if name in ("sqlite3_filename",):
        return "c_str", ""
      # Win32 常见句柄 / 指针宽度别名
      if name in (
        "HANDLE", "HWND", "HINSTANCE", "HMODULE", "HICON", "HCURSOR", "HBRUSH",
        "HDC", "HMENU", "HBITMAP", "HFONT", "HPEN", "HRGN", "HTREEITEM",
        "HGLOBAL", "HLOCAL", "HKEY", "HMONITOR", "HDESK", "HWINSTA",
        "PVOID", "LPVOID", "LPCVOID", "FARPROC", "NEARPROC", "PROC",
        "WPARAM", "LPARAM", "LRESULT", "ULONG_PTR", "LONG_PTR", "UINT_PTR",
        "DWORD_PTR", "SIZE_T", "SSIZE_T", "INT_PTR",
      ):
        return "uintptr", name
      if name in ("DWORD", "UINT", "ULONG", "BOOL", "BYTE", "WORD", "SHORT", "USHORT", "INT", "LONG"):
        if name in ("BYTE",):
          return "int", name
        if name in ("DWORD", "UINT", "ULONG"):
          return "uint", name
        return "int", name
      if can.kind == TypeKind.POINTER and can.get_pointee().kind == TypeKind.FUNCTIONPROTO:
        return "uintptr", f"fn typedef {name}"
      if can.kind == TypeKind.FUNCTIONPROTO:
        return "uintptr", f"fn typedef {name}"
      if name and _is_incomplete_record(can):
        self.note_opaque(name)
        return ffi_opaque_py_name(name), ""
      return self.map(can, is_return=is_return)

    if k in (TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE):
      pointee = t.get_pointee()
      pk = pointee.kind
      if pk == TypeKind.FUNCTIONPROTO or (
        pk == TypeKind.TYPEDEF and _canonical(pointee).kind == TypeKind.FUNCTIONPROTO
      ):
        return "uintptr", "fn ptr"
      psp = _type_spelling(pointee).replace("const ", "").strip()
      if pk in (TypeKind.CHAR_S, TypeKind.CHAR_U, TypeKind.SCHAR, TypeKind.UCHAR):
        return "c_str", ""
      if psp in ("char", "signed char", "unsigned char", "WCHAR", "wchar_t"):
        return "c_str", ""
      if pk == TypeKind.VOID:
        return "uintptr", ""
      if pk == TypeKind.TYPEDEF:
        tname = pointee.get_declaration().spelling or ""
        if tname in ("WCHAR", "CHAR", "TCHAR"):
          return "c_str", ""
      if pk in (TypeKind.RECORD, TypeKind.ELABORATED, TypeKind.TYPEDEF) or _is_incomplete_record(pointee):
        rn = _record_name(pointee)
        if rn:
          self.note_opaque(rn)
        inner = _canonical(pointee)
        if inner.kind == TypeKind.POINTER:
          return "Pointer[uint64]", "out handle"
        if rn:
          return ffi_opaque_py_name(rn), ""
        # typedef HANDLE* etc.
        if pk == TypeKind.TYPEDEF:
          ann, cmt = self.map(pointee, is_return=False)
          if ann in ("uintptr", "uint64") or ann.isidentifier():
            return f"Pointer[{ann}]", cmt
        return "uint64", "opaque*"
      inner_ann, cmt = self.map(pointee, is_return=False)
      if inner_ann == "None":
        return "uintptr", cmt
      return f"Pointer[{inner_ann}]", cmt

    if k == TypeKind.FUNCTIONPROTO:
      return "uintptr", "fn"

    if k in (TypeKind.BOOL,):
      return "bool", ""
    if k in (TypeKind.CHAR_S, TypeKind.SCHAR, TypeKind.CHAR_U, TypeKind.UCHAR, TypeKind.WCHAR):
      return "int", ""
    if k in (TypeKind.SHORT, TypeKind.INT, TypeKind.LONG, TypeKind.LONGLONG):
      try:
        bits = t.get_size() * 8
      except Exception:
        bits = 32
      if bits >= 64:
        return "int64", ""
      return "int", ""
    if k in (TypeKind.USHORT, TypeKind.UINT, TypeKind.ULONG, TypeKind.ULONGLONG):
      try:
        bits = t.get_size() * 8
      except Exception:
        bits = 32
      if bits >= 64:
        return "uint64", ""
      return "uint", ""
    if k in (TypeKind.FLOAT, TypeKind.DOUBLE, TypeKind.LONGDOUBLE):
      return "float64", ""
    if k == TypeKind.ENUM:
      return "int", "enum"
    if k in (TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY, TypeKind.VARIABLEARRAY):
      elem = t.element_type
      ann, cmt = self.map(elem, is_return=False)
      return f"Pointer[{ann}]", cmt or "array"
    if k in (TypeKind.RECORD, TypeKind.ELABORATED):
      rn = _record_name(t)
      if rn:
        self.note_opaque(rn)
        return ffi_opaque_py_name(rn), "by-value record→handle alias"
      return "uint64", "record"

    sp = _type_spelling(t)
    if "va_list" in sp:
      return "uintptr", "va_list"
    return "uintptr", f"unmapped:{sp or k.name}"


def _macro_literal(tokens: list[str]) -> tuple[str, str] | None:
  """对象宏 tokens（含宏名）→ (ann, value_repr) 或 None。"""
  if len(tokens) < 2:
    return None
  name = tokens[0]
  body = tokens[1:]
  if not body:
    return None
  if body[0] == "(":
    return None
  text = "".join(body).strip()
  if not text or text in ("extern",):
    return None
  if name in _SKIP_MACRO_NAMES:
    return None
  if any(name.startswith(p) for p in _SKIP_MACRO_PREFIXES):
    return None
  if (text.startswith('"') and text.endswith('"')) or (text.startswith('L"') and text.endswith('"')):
    if text.startswith("L"):
      text = text[1:]
    return "str", text
  cleaned = text.replace(" ", "")
  m = re.fullmatch(r"([+-]?(?:0x[0-9A-Fa-f]+|\d+))(?:[uU]?[lL]{0,2}|[lL]{0,2}[uU]?)?", cleaned)
  if m:
    return "int", m.group(1)
  if re.fullmatch(r"[+-]?(?:0x[0-9A-Fa-f]+|\d+)", cleaned):
    return "int", cleaned
  return None


def _want_const_name(name: str, *, sqlite_mode: bool) -> bool:
  if sqlite_mode:
    return name.startswith("SQLITE_")
  if not name or not name[0].isalpha() and name[0] != "_":
    return False
  if name in _SKIP_MACRO_NAMES:
    return False
  if any(name.startswith(p) for p in _SKIP_MACRO_PREFIXES):
    return False
  return True


def collect_model(
  header: Path,
  clang_args: list[str] | None = None,
  *,
  include_deps: bool | None = None,
) -> FfiModel:
  header = header.resolve()
  sqlite_mode = "sqlite" in header.name.lower()
  if include_deps is None:
    include_deps = not sqlite_mode

  args = list(default_clang_args(header))
  # 用户/调用方额外参数追加在后（可覆盖 -I）
  if clang_args:
    args.extend(clang_args)
  if not any(a.startswith("-I") for a in args):
    args.extend(["-I", str(header.parent)])
  args = ["-x", "c", "-std=c11", *args]

  roots = _collect_roots(header)
  print(f"[gen_c_ffi] include_deps={include_deps} roots={len(roots)}", file=sys.stderr)

  index = Index.create()
  tu = index.parse(
    str(header),
    args=args,
    options=TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
  )
  fatals = [d for d in tu.diagnostics if d.severity >= 3]
  if fatals:
    for d in fatals[:20]:
      print(f"clang: {d}", file=sys.stderr)
    raise SystemExit(f"libclang parse failed: {len(fatals)} error(s)")

  mapper = TypeMapper()
  model = FfiModel()
  seen_funcs: set[str] = set()
  seen_consts: set[str] = set()

  for c in tu.cursor.walk_preorder():
    if not _file_in_scope(c.location.file, header, roots, include_deps=include_deps):
      continue
    kind = c.kind

    if kind == CursorKind.STRUCT_DECL and c.spelling:
      if _is_incomplete_record(c.type):
        mapper.note_opaque(c.spelling)
      continue

    if kind == CursorKind.TYPEDEF_DECL and c.spelling:
      can = _canonical(c.type)
      if _is_incomplete_record(can) or (
        can.kind == TypeKind.RECORD and _is_incomplete_record(can)
      ):
        mapper.note_opaque(c.spelling)
      continue

    if kind == CursorKind.MACRO_DEFINITION:
      name = c.spelling or ""
      if not _want_const_name(name, sqlite_mode=sqlite_mode):
        continue
      if name in seen_consts:
        continue
      toks = [t.spelling for t in c.get_tokens()]
      lit = _macro_literal(toks)
      if lit is None:
        continue
      ann, val = lit
      seen_consts.add(name)
      py_name, native = _py_ident(name)
      model.consts.append(ConstDef(name=name, py_name=py_name, native=native, ann=ann, value=val))
      continue

    if kind != CursorKind.FUNCTION_DECL:
      continue
    if c.is_definition() and c.linkage == LinkageKind.INTERNAL:
      continue
    c_name = c.spelling or ""
    if not c_name or c_name in seen_funcs:
      continue
    # 跳过明显的 C++ 修饰 / 匿名
    if c_name.startswith("operator"):
      continue
    seen_funcs.add(c_name)
    py_name, _ = _py_ident(c_name)
    ret_ann, ret_cmt = mapper.map(c.result_type, is_return=True)
    params: list[ParamDef] = []
    used: set[str] = set()
    for i, arg in enumerate(c.get_arguments()):
      raw = arg.spelling or f"arg{i}"
      pann, _pc = mapper.map(arg.type, is_return=False)
      pname, _ = _py_ident(raw)
      base = pname
      n = 2
      while pname in used:
        pname = f"{base}{n}"
        n += 1
      used.add(pname)
      params.append(ParamDef(py_name=pname, ann=pann))
    if not params and c.type.kind == TypeKind.FUNCTIONPROTO:
      args_types = list(c.type.argument_types())
      if args_types and not (
        len(args_types) == 1 and args_types[0].kind == TypeKind.VOID
      ):
        for i, at in enumerate(args_types):
          pann, _ = mapper.map(at, is_return=False)
          params.append(ParamDef(py_name=f"arg{i}", ann=pann))
    model.funcs.append(
      FuncDef(
        c_name=c_name,
        py_name=py_name,
        ret=ret_ann,
        params=params,
        comment=ret_cmt,
      )
    )

  model.opaques = [OpaqueType(n) for n in sorted(mapper.opaques)]
  model.consts.sort(key=lambda x: x.name)
  model.funcs.sort(key=lambda x: x.c_name)
  return model


def render_pyi(header: Path, model: FfiModel) -> str:
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  rel: Path | str = header
  try:
    rel = header.resolve().relative_to(REPO_ROOT)
  except ValueError:
    rel = str(header.resolve())
  src = rel.as_posix() if isinstance(rel, Path) else rel
  lines: list[str] = [
    "# AUTO-GENERATED by src.tools.c_ffi_pyi — DO NOT EDIT",
    f"# Source: {src}",
    f"# Generated: {now}",
    "# Spec: docs/c-ffi-pyi.md",
    "",
    "from py2cpp.builtins import *",
    "",
    "# ---------------------------------------------------------------------------",
    "# Opaque handles (incomplete struct → *_h alias = uint64; C tag in comment)",
    "# ---------------------------------------------------------------------------",
    "",
  ]
  for op in model.opaques:
    lines.append(f"type {op.py_name} = uint64  # C: {op.c_name}")
  if model.opaques:
    lines.append("")

  lines.extend([
    "# ---------------------------------------------------------------------------",
    "# Constants (#define)",
    "# ---------------------------------------------------------------------------",
    "",
  ])
  for c in model.consts:
    if c.native:
      lines.append(f"# C: {c.native}")
    lines.append(f"{c.py_name}: {c.ann} = {c.value}")
  if model.consts:
    lines.append("")

  lines.extend([
    "# ---------------------------------------------------------------------------",
    "# Functions",
    "# ---------------------------------------------------------------------------",
    "",
  ])
  for fn in model.funcs:
    lines.append("@native")
    lines.append(f'@native_name("{fn.c_name}")')
    args = ", ".join(f"{p.py_name}: {p.ann}" for p in fn.params)
    comment = f"  # {fn.comment}" if fn.comment else ""
    lines.append(f"def {fn.py_name}({args}) -> {fn.ret}:{comment}")
    lines.append("  ...")
    lines.append("")

  lines.append(
    f"# stats: opaques={len(model.opaques)} consts={len(model.consts)} funcs={len(model.funcs)}"
  )
  lines.append("")
  return "\n".join(lines)


def run_checks(model: FfiModel, text: str, *, header: Path) -> list[str]:
  errs: list[str] = []
  sqlite_mode = "sqlite" in header.name.lower()
  if "@native" not in text or "@native_name" not in text:
    errs.append("output missing @native / @native_name")
  if "from py2cpp.builtins import *" not in text:
    errs.append("missing builtins import")
  if len(model.funcs) < 1:
    errs.append(f"too few funcs: {len(model.funcs)}")
  if sqlite_mode:
    if len(model.funcs) < 50:
      errs.append(f"too few funcs: {len(model.funcs)}")
    for need in (
      "sqlite3_open",
      "sqlite3_prepare_v2",
      "sqlite3_step",
      "sqlite3_close",
      "sqlite3_finalize",
    ):
      if need not in {f.c_name for f in model.funcs}:
        errs.append(f"missing function {need}")
    if "SQLITE_OK" not in {c.name for c in model.consts}:
      errs.append("missing SQLITE_OK")
    if "type sqlite3_h = uint64" not in text:
      errs.append("missing opaque alias type sqlite3_h")
    if re.search(r"(?m)^type sqlite3 = uint64", text):
      errs.append("opaque alias must not reuse C tag name sqlite3")
  else:
    # Win32 / 通用：至少要有一批函数
    if len(model.funcs) < 100:
      errs.append(f"too few funcs for non-sqlite header: {len(model.funcs)}")
    # windows.h 伞头应带上 CreateWindowExW 或 MessageBoxW 等
    names = {f.c_name for f in model.funcs}
    if header.name.lower() == "windows.h":
      if not ({"MessageBoxW", "CreateWindowExW", "GetMessageW"} & names):
        errs.append("windows.h pyi missing core UI symbols (MessageBoxW/CreateWindowExW/GetMessageW)")
  return errs


def strip_generated_timestamp(text: str) -> str:
  return "\n".join(ln for ln in text.splitlines() if not ln.startswith("# Generated:"))


def generate_pyi(
  header: Path | str,
  *,
  out: Path | None = None,
  clang_args: list[str] | None = None,
  check: bool = False,
  include_deps: bool | None = None,
) -> int:
  """解析 ``header`` 并写出 ``.pyi``；成功返回 0。"""
  try:
    header_path = resolve_header_path(header)
  except FileNotFoundError as e:
    print(f"ERROR: {e}", file=sys.stderr)
    return 1

  out_path = out or default_pyi_path(header_path)

  print(f"[gen_c_ffi] parse {header_path}")
  print(f"[gen_c_ffi] out   {out_path}")
  model = collect_model(
    header_path,
    clang_args=list(clang_args or []),
    include_deps=include_deps,
  )
  text = render_pyi(header_path, model)
  print(
    f"[gen_c_ffi] opaques={len(model.opaques)} consts={len(model.consts)} funcs={len(model.funcs)}"
  )

  errs = run_checks(model, text, header=header_path)
  if errs:
    for e in errs:
      print(f"CHECK FAIL: {e}", file=sys.stderr)
    return 1

  if check and out_path.is_file():
    old = out_path.read_text(encoding="utf-8")
    if strip_generated_timestamp(old) != strip_generated_timestamp(text):
      print(f"CHECK FAIL: {out_path} differs from regenerated content", file=sys.stderr)
      return 1
    print(f"[gen_c_ffi] check OK (matches {out_path})")
    return 0

  out_path.parent.mkdir(parents=True, exist_ok=True)
  out_path.write_text(text, encoding="utf-8", newline="\n")
  print(f"[gen_c_ffi] wrote {out_path} ({len(text)} bytes)")
  if check:
    print("[gen_c_ffi] check OK (fresh write + validations)")
  return 0
