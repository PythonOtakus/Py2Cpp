"""从 C 头文件经 libclang 生成 Py2Cpp 风格 ``.pyi``（``@native`` FFI 声明）。

CLI 入口：``scripts/gen_c_ffi.py``。规格见 ``docs/c-ffi-pyi.md``。
"""
from __future__ import annotations

import keyword
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
  from clang.cindex import (
    Config,
    CursorKind,
    Index,
    LinkageKind,
    TypeKind,
    TranslationUnit,
  )
except ImportError as e:  # pragma: no cover
  print(
    "ERROR: need `pip install clang libclang` (Python bindings + bundled libclang.dll).",
    file=sys.stderr,
  )
  raise SystemExit(2) from e


def _ensure_libclang() -> None:
  """定位 ``libclang.dll``（``pip install libclang`` 的 ``clang/native`` 或 LLVM 安装）。"""
  if Config.loaded:
    return
  candidates: list[Path] = []
  try:
    import clang as _clang_pkg

    native = Path(_clang_pkg.__file__).resolve().parent / "native" / "libclang.dll"
    candidates.append(native)
  except Exception:
    pass
  for base in (
    Path(r"C:\Program Files\LLVM\bin"),
    Path(r"C:\Program Files (x86)\LLVM\bin"),
  ):
    candidates.append(base / "libclang.dll")
  env = os.environ.get("LIBCLANG_PATH") or os.environ.get("LLVM_PATH")
  if env:
    p = Path(env)
    candidates.append(p if p.suffix.lower() == ".dll" else p / "libclang.dll")
    candidates.append(p / "bin" / "libclang.dll")
  for cand in candidates:
    if cand.is_file():
      Config.set_library_file(str(cand))
      return


_ensure_libclang()

REPO_ROOT = Path(__file__).resolve().parents[2]
FFI_ROOT = REPO_ROOT / "ffi"

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


# 旧前缀（兼容读旧 .pyi）；新导出名无下划线：``PyiSqlite3`` / ``pyiSqlite3Open``
PYI_PREFIX = "Pyi"
PYI_PREFIX_LEGACY = "Pyi_"

_PYI_ANN_BUILTINS = frozenset({
  "None",
  "int",
  "int64",
  "uint",
  "uint64",
  "uintptr",
  "float",
  "float64",
  "bool",
  "byte",
  "char",
  "str",
  "bytes",
  "CStr",
  "Self",
  "object",
})


def _is_c_ident(name: str | None) -> bool:
  return bool(name) and name.isidentifier()


def _split_camel_words(s: str) -> list[str]:
  """无下划线的 C 标识符分词（``GLFWwindow`` / ``XMLHttpRequest`` / ``CreateWindowExW``）。"""
  if not s:
    return []
  # ``GLFWwindow``：全大写缩写后直接小写（无中间 Pascal 大写）；勿与 ``XMLHttp`` 混淆。
  m = re.fullmatch(r"([A-Z]{2,})([a-z]+)", s)
  if m:
    return [m.group(1), m.group(2)]
  # 缩写后接 Pascal 词：``XML``+``Http``；勿把 ``DATA`` 拆成单字母。
  parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", s)
  return parts if parts else [s]


def _split_c_ident_words(c_name: str) -> list[str]:
  """C 标识符 → 词列表（去前导 ``_``；snake / SCREAMING / camel；尾缀 ``A``/``W`` 单独成词）。"""
  s = (c_name or "").lstrip("_")
  if not s:
    return []
  if "_" in s:
    parts = [p for p in s.split("_") if p]
  else:
    parts = _split_camel_words(s)
  # 全大写词以这些结尾时勿剥尾 ``A``/``W``（``OVERFLOW``≠``OVERFLO``+``W``）。
  _no_aw_peel_endings = (
    "FLOW", "WINDOW", "SHADOW", "FOLLOW", "YELLOW", "NARROW", "BORROW",
    "DRAW", "VIEW", "AREA", "DATA", "MEDIA", "INFO",
  )
  out: list[str] = []
  n = len(parts)
  for i, p in enumerate(parts):
    # 仅末段剥 WinAPI 宽窄后缀：``STATUSW``→``STATUS``+``W``。
    # 勿剥 ``DATA``/``MEDIA``/``ROW``（``DAT``+``A`` / ``RO``+``W``）；茎长 ≥6（``STATUS``）。
    stem = p[:-1]
    if (
      i == n - 1
      and len(stem) >= 6
      and p[-1] in "AW"
      and stem.isupper()
      and stem.isalpha()
      and not any(p.endswith(suf) for suf in _no_aw_peel_endings)
    ):
      out.append(stem)
      out.append(p[-1])
    else:
      out.append(p)
  return out


def _word_to_pascal_piece(word: str, *, is_last: bool) -> str:
  if not word:
    return ""
  if is_last and word in ("A", "W"):
    return word
  if word.isupper() and word.isalpha():
    return word.capitalize()
  # ``WIN32`` / ``UTF8`` / ``SHA256`` → ``Win32`` / ``Utf8`` / ``Sha256``
  if word.isupper() and word.isalnum() and any(c.isalpha() for c in word):
    runs = re.findall(r"[A-Z]+|[0-9]+", word)
    return "".join(r.capitalize() if r.isalpha() else r for r in runs)
  if word[0].islower():
    return word[0].upper() + word[1:]
  return word


def c_ident_to_pascal(c_name: str) -> str:
  """``_FOO_BAR`` / ``STATUSW`` / ``WIN32_DATA`` → ``FooBar`` / ``StatusW`` / ``Win32Data``。"""
  words = _split_c_ident_words(c_name)
  if not words:
    return "Anon"
  n = len(words)
  return "".join(_word_to_pascal_piece(w, is_last=(i == n - 1)) for i, w in enumerate(words))


def c_ident_to_camel(c_name: str) -> str:
  """结构体字段等：Pascal → 首字母小写（保留尾缀 ``A``/``W``）。"""
  pascal = c_ident_to_pascal(c_name)
  if not pascal:
    return "anon"
  return pascal[0].lower() + pascal[1:]


def pyi_type_export_name(c_name: str, *, is_enum: bool = False) -> str:
  """类型类名：``Pyi`` + Pascal；仅真正 C ``enum`` 加 ``Enum`` 后缀。"""
  if not c_name:
    return f"{PYI_PREFIX}Anon"
  if c_name.startswith(PYI_PREFIX) and len(c_name) > len(PYI_PREFIX) and c_name[len(PYI_PREFIX)].isupper():
    base = c_name
  elif c_name.startswith(PYI_PREFIX_LEGACY):
    base = PYI_PREFIX + c_ident_to_pascal(c_name[len(PYI_PREFIX_LEGACY):])
  else:
    base = PYI_PREFIX + c_ident_to_pascal(c_name)
  # 避免 ``_exception`` → ``PyiException`` 被 S47 误判为 Python 异常类
  if base.endswith("Exception") and not base.endswith("ExceptionRec"):
    base = f"{base}Rec"
  if is_enum and not base.endswith("Enum"):
    base += "Enum"
  return base


def pyi_func_export_name(c_name: str) -> str:
  """函数：``pyi`` + Pascal（``wglUseFontOutlinesA`` → ``pyiWglUseFontOutlinesA``）。"""
  if not c_name:
    return "pyiAnon"
  if c_name.startswith("pyi") and len(c_name) > 3:
    return c_name
  return "pyi" + c_ident_to_pascal(c_name)


def pyi_const_export_name(c_name: str) -> str:
  """模块常量：``PyiSqliteOk``（与类型同式 Pascal）。"""
  return pyi_type_export_name(c_name, is_enum=False)


def pyi_field_export_name(c_name: str) -> str:
  """结构体字段：规范 camelCase。"""
  py, _ = _py_ident(c_ident_to_camel(c_name))
  return py


def pyi_export_name(c_name: str) -> str:
  """默认按**类型**导出名（注解改写 / 结构体类）；函数/常量请用专用入口。"""
  return pyi_type_export_name(c_name)


def pyi_c_name_from_export(py_name: str) -> str:
  """尽力从导出名还原（优先依赖 ``@native_name``；本函数仅剥离已知前缀启发式）。"""
  if py_name.startswith(PYI_PREFIX_LEGACY):
    return py_name[len(PYI_PREFIX_LEGACY):]
  if py_name.startswith("pyi") and len(py_name) > 3 and py_name[3].isupper():
    return py_name[3:]
  if py_name.startswith(PYI_PREFIX) and len(py_name) > len(PYI_PREFIX) and py_name[len(PYI_PREFIX)].isupper():
    return py_name[len(PYI_PREFIX):]
  return py_name


def _rewrite_identifiers_in_ann(ann: str, known: set[str]) -> str:
  def repl(m: re.Match[str]) -> str:
    w = m.group(0)
    if w in _PYI_ANN_BUILTINS or w in ("Self", "Function", "Pointer"):
      return w
    if w in known and _is_c_ident(w):
      return pyi_type_export_name(w)
    return w

  return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", repl, ann)


def _shorten_c_type_comment(detail: str) -> str:
  """去掉 clang ``unnamed at C:\\…\\file.h:line`` 绝对路径，保留简短描述。"""
  s = detail.strip()
  if not s:
    return "unknown"
  s = re.sub(
    r"\bunnamed (?:struct|union|enum) at [^:]+:\d+:\d+",
    "unnamed",
    s,
    flags=re.IGNORECASE,
  )
  s = re.sub(r"\bat [A-Za-z]:\\[^\)]+", "at <sdk>", s)
  s = re.sub(r"\s+", " ", s).strip()
  if len(s) > 120:
    s = s[:117] + "..."
  return s


def _is_valid_pyi_ann(ann: str) -> bool:
  """注解须为合法 Python 类型表达式（禁止 clang spelling / 空格路径）。"""
  a = ann.strip()
  if not a:
    return False
  if a in _PYI_ANN_BUILTINS or a == "Self":
    return True
  if a.startswith(PYI_PREFIX) and a.isidentifier():
    return True
  if a.startswith("Pointer[") and a.endswith("]"):
    return _is_valid_pyi_ann(a[len("Pointer[") : -1])
  if a.startswith("Function["):
    return True
  return False


def _sanitize_pyi_ann(ann: str, cmt: str = "") -> tuple[str, str]:
  """非法注解 → ``None`` + ``C: …`` 注释。"""
  if _is_valid_pyi_ann(ann):
    return ann, cmt
  detail = ann if ann and ann != "None" else (cmt or "unknown")
  if detail.startswith("C:"):
    detail = detail[2:].strip()
  if detail.startswith("unmapped:"):
    detail = detail[len("unmapped:") :].strip()
  return "None", f"C: {_shorten_c_type_comment(detail)}"


def _cursor_doc(cursor) -> str:
  """从 libclang cursor 取 C 注释并转为 Python docstring 正文（无三引号）。"""
  try:
    raw = cursor.raw_comment
  except Exception:
    raw = None
  try:
    brief = cursor.brief_comment
  except Exception:
    brief = None
  return doxygen_to_python_docstring(raw, brief) or ""


def _clean_doxygen_refs(text: str) -> str:
  """``@ref Name`` / ``[text](@ref x)`` → 纯文本；去掉多余反引号包裹的简单标识。"""
  s = text
  s = re.sub(r"\[([^\]]+)\]\(@ref\s+[^)]+\)", r"\1", s)
  s = re.sub(r"@ref\s+(\w+)", r"\1", s)
  return s


def _unwrap_c_comment(raw: str) -> str:
  """剥 ``/*! … */`` / ``/** … */`` / ``//`` 行前缀。"""
  lines_out: list[str] = []
  for line in raw.splitlines():
    ln = line
    ln = re.sub(r"^\s*/\*+[!]?", "", ln)
    ln = re.sub(r"\*/\s*$", "", ln)
    ln = re.sub(r"^\s*//+!?\s?", "", ln)
    # `` *  @param`` → ``@param``（剥 ``*`` 后吃掉全部前导空白）
    ln = re.sub(r"^\s*\*\s*", "", ln)
    ln = ln.strip()
    lines_out.append(ln)
  return "\n".join(lines_out).strip()


_DOXY_SECTION_TAGS = {
  "errors": "Errors",
  "error": "Errors",
  "thread_safety": "Thread safety",
  "threadsafety": "Thread safety",
  "sa": "See also",
  "see": "See also",
  "since": "Since",
  "note": "Note",
  "remark": "Note",
  "remarks": "Note",
  "warning": "Warning",
  "bug": "Bug",
  "todo": "Todo",
  "pointer_lifetime": "Pointer lifetime",
  "reentrancy": "Reentrancy",
}


def doxygen_to_python_docstring(
  raw: str | None,
  brief: str | None = None,
) -> str | None:
  """Doxygen / 块注释 → PEP 257 风格正文（Google 小节：Args / Returns / …）。"""
  brief_s = (brief or "").strip()
  if not raw and not brief_s:
    return None
  body = _unwrap_c_comment(raw) if raw else ""
  body = _clean_doxygen_refs(body)

  # 去掉独立 @ingroup / @ingroup* 行（分类标签，对 Python 文档无用）
  body = re.sub(r"(?m)^\s*@ingroup\w*\s+\S+\s*$", "", body)

  params: list[tuple[str, str]] = []
  returns = ""
  sections: list[tuple[str, str]] = []
  desc_chunks: list[str] = []

  # 按 @tag 切块（保留顺序）
  parts = re.split(r"(?m)^\s*(?=@\w+)", body) if body else []
  for part in parts:
    part = part.strip()
    if not part:
      continue
    m = re.match(
      r"@param(?:\[[^\]]*\])?\s+(\w+)\s+(.*)",
      part,
      flags=re.DOTALL,
    )
    if m:
      params.append((m.group(1), re.sub(r"\s+", " ", m.group(2).strip())))
      continue
    m = re.match(r"@returns?\s+(.*)", part, flags=re.DOTALL | re.IGNORECASE)
    if m:
      returns = re.sub(r"\s+", " ", m.group(1).strip())
      continue
    m = re.match(r"@brief\s+(.*)", part, flags=re.DOTALL | re.IGNORECASE)
    if m:
      b = re.sub(r"\s+", " ", m.group(1).strip())
      if b and not brief_s:
        brief_s = b
      elif b and brief_s and b != brief_s:
        desc_chunks.append(b)
      continue
    m = re.match(r"@(\w+)\s*(.*)", part, flags=re.DOTALL)
    if m:
      tag = m.group(1).lower()
      rest = re.sub(r"\s+", " ", m.group(2).strip())
      if tag in ("xmlns", "ingroup*", "xmlnsname", "code", "endcode", "callback_signature") or tag.startswith("glfw"):
        continue
      title = _DOXY_SECTION_TAGS.get(tag)
      if title and rest:
        sections.append((title, rest))
      elif title and not rest:
        continue
      elif rest:
        desc_chunks.append(rest)
      continue
    # 无 tag 的前言 = 详述
    cleaned = re.sub(r"\n{3,}", "\n\n", part).strip()
    if cleaned:
      desc_chunks.append(cleaned)

  if not brief_s and desc_chunks:
    # 取第一段作 brief
    first = desc_chunks[0]
    if "\n\n" in first:
      brief_s, rest0 = first.split("\n\n", 1)
      brief_s = re.sub(r"\s+", " ", brief_s.strip())
      desc_chunks[0] = rest0.strip()
    else:
      brief_s = re.sub(r"\s+", " ", first.strip())
      desc_chunks = desc_chunks[1:]

  out_lines: list[str] = []
  if brief_s:
    out_lines.append(brief_s)
  for chunk in desc_chunks:
    chunk = chunk.strip()
    if not chunk:
      continue
    # 段落内换行压成空格；保留空行分段
    for para in re.split(r"\n\s*\n", chunk):
      para = re.sub(r"\s*\n\s*", " ", para.strip())
      if not para:
        continue
      # GLFW 等常把 brief 再写一遍作首段 → 去重
      if brief_s and para == brief_s:
        continue
      if brief_s and para.startswith(brief_s + " "):
        para = para[len(brief_s) :].lstrip()
        if not para:
          continue
      if out_lines:
        out_lines.append("")
      out_lines.append(para)

  if params:
    if out_lines:
      out_lines.append("")
    out_lines.append("Args:")
    for pname, pdesc in params:
      out_lines.append(f"  {pname}: {pdesc}")
  if returns:
    if out_lines:
      out_lines.append("")
    out_lines.append("Returns:")
    out_lines.append(f"  {returns}")
  for title, text in sections:
    if out_lines:
      out_lines.append("")
    out_lines.append(f"{title}:")
    out_lines.append(f"  {text}")

  doc = "\n".join(out_lines).strip()
  if not doc:
    return None
  # 避免破坏三引号
  doc = doc.replace('"""', "'''")
  return doc


def _emit_docstring_lines(doc: str, indent: str = "  ") -> list[str]:
  """``indent\"\"\"…\"\"\"`` 多行块（PEP 257：收尾引号独占一行）。"""
  doc = doc.strip("\n")
  if not doc:
    return []
  lines = doc.split("\n")
  if len(lines) == 1 and "\\" not in lines[0]:
    return [f'{indent}"""{lines[0]}"""']
  out = [f'{indent}"""']
  for ln in lines:
    out.append(f"{indent}{ln}" if ln else "")
  out.append(f'{indent}"""')
  return out


@dataclass
class FieldDef:

  name: str  # Python 侧 camelCase
  ann: str
  comment: str = ""
  c_name: str = ""  # 原 C 字段名；与 name 不同时写 ``@native_name``


@dataclass
class StructDef:
  """C ``struct``/``union`` → ``@native`` 类；类名 = 结构体定义名（匿名 typedef 用 typedef 名）。

  ``c_cpp_path``：C++ 中的限定名（嵌套如 ``sqlite3_index_info::sqlite3_index_orderby``），
  写入 ``@native_name`` / ``using Pyi_X = ::path``。
  """

  c_name: str
  incomplete: bool
  is_union: bool = False
  fields: list[FieldDef] = field(default_factory=list)
  c_cpp_path: str = ""
  doc: str = ""


@dataclass
class EnumDef:
  """C ``enum`` → 空 ``@native`` 类（方案 A）；C++ ``using Pyi_E = ::E``。"""

  c_name: str
  c_cpp_path: str = ""
  doc: str = ""


@dataclass
class TypeAliasDef:
  """``typedef struct A B`` → ``type B = A``（``.pyi`` 仅声明）。"""

  py_name: str
  target: str


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
  comment: str = ""  # 类型映射旁注（少用）
  doc: str = ""  # Python docstring 正文（无三引号）
  variadic: bool = False  # C ``...`` → ``*_``（TypeVarTuple 形参包）


@dataclass
class FfiModel:
  structs: list[StructDef] = field(default_factory=list)
  enums: list[EnumDef] = field(default_factory=list)
  aliases: list[TypeAliasDef] = field(default_factory=list)
  consts: list[ConstDef] = field(default_factory=list)
  funcs: list[FuncDef] = field(default_factory=list)


# UCRT / CRT 裸名（``ffi stdio`` → ucrt/stdio.h → ``ffi/crt/stdio.pyi``）
_CRT_BARE_NAMES = frozenset({
  "stdio",
  "stdio.h",
  "string",
  "string.h",
  "math",
  "math.h",
  "time",
  "time.h",
  "stdlib",
  "stdlib.h",
  "errno",
  "errno.h",
  "stdint",
  "stdint.h",
  "float",
  "float.h",
  "stdarg",
  "stdarg.h",
  "stddef",
  "stddef.h",
  "ctype",
  "ctype.h",
  "wchar",
  "wchar.h",
  "assert",
  "assert.h",
  "locale",
  "locale.h",
  "signal",
  "signal.h",
  "setjmp",
  "setjmp.h",
  "fenv",
  "fenv.h",
  "inttypes",
  "inttypes.h",
  "uchar",
  "uchar.h",
  "wctype",
  "wctype.h",
  "corecrt",
  "corecrt.h",
})


def windows_sdk_include_bucket(header: Path) -> str | None:
  """若头位于 Windows Kits ``Include/<ver>/<bucket>/…``，返回 ``um``/``shared``/``ucrt``/``winrt``。"""
  header = header.resolve()
  ver = windows_sdk_version_root(header)
  if ver is None:
    return None
  try:
    rel = header.relative_to(ver.resolve())
  except ValueError:
    return None
  if not rel.parts:
    return None
  top = rel.parts[0].lower()
  if top in {"um", "shared", "ucrt", "winrt"}:
    return top
  return None


def default_pyi_path(header: Path, *, repo_root: Path | None = None) -> Path:
  """由 C/C++ 头路径推导默认 ``.pyi`` 输出路径。

  - 仓库内 ``third_party/.../foo.h`` → ``ffi/.../foo.pyi``（去掉 ``third_party/`` 前缀）
  - 仓库内其它相对路径 ``a/b.h`` → ``ffi/a/b.pyi``
  - Windows Kits ``um``/``shared``/``winrt`` → ``ffi/windows/<stem>.pyi``（如 ``windows.h`` → ``ffi/windows/windows.pyi``）
  - Windows Kits ``ucrt`` → ``ffi/crt/<stem>.pyi``（如 ``stdio.h`` → ``ffi/crt/stdio.pyi``）
  - 其它系统头 → ``ffi/<stem>.pyi``
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
  stem = header.stem.lower()
  bucket = windows_sdk_include_bucket(header)
  if bucket == "ucrt":
    return FFI_ROOT / "crt" / f"{stem}.pyi"
  if bucket in {"um", "shared", "winrt"}:
    return FFI_ROOT / "windows" / f"{stem}.pyi"
  return FFI_ROOT / f"{stem}.pyi"


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


def find_ucrt_header(name: str) -> Path | None:
  """返回最新 Windows Kits ``ucrt/<name>``（如 ``stdio.h`` / ``sys/stat.h``）。"""
  rel = name.replace("\\", "/")
  if not rel.lower().endswith(".h"):
    rel = f"{rel}.h"
  rel_l = rel.lower()
  bases = [
    Path(r"C:\Program Files (x86)\Windows Kits\10\Include"),
    Path(r"C:\Program Files\Windows Kits\10\Include"),
  ]
  hits: list[Path] = []
  for base in bases:
    if not base.is_dir():
      continue
    for ver in base.iterdir():
      if not ver.is_dir():
        continue
      cand = ver / "ucrt" / rel_l
      if cand.is_file():
        hits.append(cand)
  if not hits:
    return None
  return sorted(set(hits))[-1]


def find_windows_sdk_um_header(name: str) -> Path | None:
  """最新 Kits ``um/<name>``（如 ``WinSock2.h``）。"""
  rel = name.replace("\\", "/")
  if not rel.lower().endswith(".h"):
    rel = f"{rel}.h"
  wh = find_windows_sdk_um_windows_h()
  if wh is None:
    return None
  ver = windows_sdk_version_root(wh)
  if ver is None:
    return None
  for cand in (ver / "um" / rel, ver / "um" / rel.lower(), ver / "shared" / rel):
    if cand.is_file():
      return cand.resolve()
  # 大小写不敏感扫描
  um = ver / "um"
  if um.is_dir():
    target = Path(rel).name.lower()
    for p in um.rglob("*"):
      if p.is_file() and p.name.lower() == target:
        return p.resolve()
  return None


def find_windows_sdk_um_gl_h() -> Path | None:
  """返回最新 Windows Kits ``um/gl/GL.h``（固定功能 OpenGL），找不到则 ``None``。"""
  bases = [
    Path(r"C:\Program Files (x86)\Windows Kits\10\Include"),
    Path(r"C:\Program Files\Windows Kits\10\Include"),
  ]
  hits: list[Path] = []
  for base in bases:
    if base.is_dir():
      hits.extend(base.glob("*/um/gl/GL.h"))
      hits.extend(base.glob("*/um/gl/gl.h"))
  if not hits:
    return None
  return sorted(hits)[-1]


def resolve_header_path(header: Path | str) -> Path:
  """解析 ``--header``：存在则用之；``windows`` / ``gl`` / CRT 裸名则查找 SDK。"""
  p = Path(header)
  if p.is_file():
    return p.resolve()
  key = str(header).replace("\\", "/").lower().strip()
  name = p.name.lower() if p.name else key
  if key in {"windows.h", "windows"} or name in {"windows.h", "windows"}:
    found = find_windows_sdk_um_windows_h()
    if found is None:
      raise FileNotFoundError(
        "windows.h not found under Windows Kits; pass a full path with --header"
      )
    return found.resolve()
  if key in {"gl", "gl.h", "gl/gl.h"} or name in {"gl.h", "gl"}:
    found = find_windows_sdk_um_gl_h()
    if found is None:
      raise FileNotFoundError(
        "GL/gl.h not found under Windows Kits; pass a full path with --header"
      )
    return found.resolve()
  # ``ffi stdio`` / ``crt/stdio`` / ``stdio.h`` / ``sys/stat`` → UCRT
  crt_key = key
  if crt_key.startswith("crt/"):
    crt_key = crt_key[4:]
  _CRT_EXTRA = {
    "signal", "signal.h", "fcntl", "fcntl.h", "direct", "direct.h", "io", "io.h",
    "sys/stat", "sys/stat.h", "sys/utime", "sys/utime.h", "utime", "utime.h",
  }
  if crt_key in _CRT_BARE_NAMES or crt_key in _CRT_EXTRA or name in _CRT_BARE_NAMES or name in _CRT_EXTRA:
    found = find_ucrt_header(crt_key if (crt_key in _CRT_BARE_NAMES or crt_key in _CRT_EXTRA) else name)
    if found is None:
      raise FileNotFoundError(
        f"UCRT header not found for {header!r}; pass a full path with --header"
      )
    return found.resolve()
  # Windows um 子系统头裸名：``winsock2`` / ``commctrl`` …
  _UM_BARE = {
    "winsock2", "winsock2.h", "ws2tcpip", "ws2tcpip.h",
    "commctrl", "commctrl.h", "commdlg", "commdlg.h",
    "shellapi", "shellapi.h", "gdiplus", "gdiplus.h",
    "objidl", "objidl.h", "winhttp", "winhttp.h",
  }
  if key in _UM_BARE or name in _UM_BARE:
    found = find_windows_sdk_um_header(key if key in _UM_BARE else name)
    if found is None:
      raise FileNotFoundError(
        f"Windows um header not found for {header!r}; pass a full path with --header"
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
  hname = header.name.lower()
  if ver is not None or hname in {"windows.h", "gl.h"}:
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
    # GL/gl.h 依赖 WINGDIAPI/APIENTRY（通常由 windows.h 提供）；单独解析时给桩
    if hname == "gl.h":
      args.extend([
        "-DWINGDIAPI=",
        "-DAPIENTRY=__stdcall",
      ])
  return args


def _collect_roots(header: Path) -> list[Path]:
  """传递 include 收集时允许的文件根目录列表。"""
  header = header.resolve()
  roots: list[Path] = []
  bucket = windows_sdk_include_bucket(header)
  ver = windows_sdk_version_root(header)
  if bucket == "ucrt" and ver is not None:
    # CRT：仅收集 ucrt 树，避免把 um/shared 一并扫进来
    ucrt = ver / "ucrt"
    if ucrt.is_dir():
      roots.append(ucrt.resolve())
  elif ver is not None:
    # Win32 um/shared/winrt：勿把 ucrt 一并扫入（否则 windows.pyi 吸走 CRT 类型名，
    # 与 ``ffi/crt/*`` 在 ``tr.classes`` 里撞名，stdio 头会误 ``#include`` windows）
    if bucket in {"um", "shared", "winrt"}:
      for sub in ("um", "shared", "winrt"):
        d = ver / sub
        if d.is_dir():
          roots.append(d.resolve())
    else:
      roots.append(ver.resolve())
  try:
    roots.append((REPO_ROOT / "third_party").resolve())
  except Exception:
    pass
  try:
    roots.append((REPO_ROOT / "zeus" / "third_party").resolve())
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
    if decl.kind in (CursorKind.STRUCT_DECL, CursorKind.UNION_DECL):
      return not any(True for _ in decl.get_children() if _.kind == CursorKind.FIELD_DECL)
    return False
  decl = t.get_declaration()
  if decl is None:
    return True
  if decl.kind not in (CursorKind.STRUCT_DECL, CursorKind.UNION_DECL):
    return False
  return not any(c.kind == CursorKind.FIELD_DECL for c in decl.get_children())


def _record_name(t) -> str | None:
  """具名 struct/union 标签；匿名（clang ``unnamed at …`` spelling）→ ``None``。"""
  t = _canonical(t)
  decl = t.get_declaration()
  if decl is not None and _is_c_ident(decl.spelling):
    return decl.spelling
  sp = _type_spelling(t)
  m = re.match(r"(?:const\s+)?(?:struct|union)\s+(\w+)\s*$", sp)
  if m and _is_c_ident(m.group(1)):
    return m.group(1)
  if t.kind == TypeKind.TYPEDEF:
    tn = t.get_declaration().spelling or ""
    return tn if _is_c_ident(tn) else None
  return None


def _enum_tag_name(t) -> str | None:
  """具名 enum 标签；匿名 → ``None``。"""
  t = _canonical(t)
  if t.kind != TypeKind.ENUM:
    return None
  decl = t.get_declaration()
  if decl is not None and _is_c_ident(decl.spelling):
    return decl.spelling
  return None


def _record_cpp_path(cursor) -> str:
  """嵌套 ``struct`` 的 C++ 限定名（``Outer::Inner``）；顶层为标签名。

  C 中嵌套 tag 的 ``semantic_parent`` 常为翻译单元（文件作用域），但 ``#include`` 进 C++ 后
  嵌套类型落在外层类内，故必须走 ``lexical_parent``。
  """
  parts: list[str] = []
  cur = cursor
  while cur is not None:
    try:
      kind = cur.kind
    except Exception:
      break
    if kind == CursorKind.TRANSLATION_UNIT:
      break
    if kind in (CursorKind.STRUCT_DECL, CursorKind.UNION_DECL):
      sp = cur.spelling or ""
      if sp and sp.isidentifier():
        parts.append(sp)
    try:
      nxt = cur.lexical_parent
    except Exception:
      break
    if nxt is None or nxt == cur:
      break
    cur = nxt
  if not parts:
    return cursor.spelling or ""
  return "::".join(reversed(parts))


def _record_decl_cursor(t):
  t = _canonical(t)
  decl = t.get_declaration()
  if decl is not None and decl.kind in (CursorKind.STRUCT_DECL, CursorKind.UNION_DECL):
    return decl
  return None


class TypeMapper:
  def __init__(self) -> None:
    # c_name → StructDef（收集中可变）
    self.structs: dict[str, StructDef] = {}
    # c_name → EnumDef
    self.enums: dict[str, EnumDef] = {}
    # typedef 名 → 目标结构体/枚举类名（无 Pyi_ 前缀）
    self.aliases: dict[str, str] = {}
    self._collecting: set[str] = set()

  def note_struct(
    self,
    name: str,
    *,
    incomplete: bool,
    is_union: bool = False,
    fields: list[FieldDef] | None = None,
    c_cpp_path: str | None = None,
    doc: str = "",
  ) -> None:
    if not _is_c_ident(name):
      return
    path = (c_cpp_path or name).strip() or name
    if not _is_c_ident(path.split("::")[-1]):
      path = name
    prev = self.structs.get(name)
    if prev is None:
      self.structs[name] = StructDef(
        c_name=name,
        incomplete=incomplete,
        is_union=is_union,
        fields=list(fields or []),
        c_cpp_path=path,
        doc=doc,
      )
      return
    if not prev.c_cpp_path or path.count("::") < prev.c_cpp_path.count("::"):
      prev.c_cpp_path = path
    if doc and not prev.doc:
      prev.doc = doc
    if prev.incomplete and not incomplete:
      prev.incomplete = False
      prev.is_union = is_union
      if fields:
        prev.fields = list(fields)
    elif not prev.fields and fields:
      prev.fields = list(fields)
      prev.incomplete = incomplete

  def note_enum(self, name: str, *, c_cpp_path: str | None = None, doc: str = "") -> None:
    if not _is_c_ident(name):
      return
    path = (c_cpp_path or name).strip() or name
    if "::" in path and not all(_is_c_ident(p) for p in path.split("::")):
      path = name
    prev = self.enums.get(name)
    if prev is None:
      self.enums[name] = EnumDef(c_name=name, c_cpp_path=path, doc=doc)
      return
    if not prev.c_cpp_path or path.count("::") < prev.c_cpp_path.count("::"):
      prev.c_cpp_path = path
    if doc and not prev.doc:
      prev.doc = doc

  def note_alias(self, py_name: str, target: str) -> None:
    if (
      py_name
      and target
      and py_name != target
      and _is_c_ident(py_name)
      and _is_c_ident(target)
    ):
      self.aliases[py_name] = target

  def known_type_names(self) -> set[str]:
    return set(self.structs) | set(self.enums) | set(self.aliases)

  def _map_function_proto(self, t) -> tuple[str, str]:
    """C 函数类型或函数指针 → ``Function[[Args…], Ret]``（``void`` 返回为 ``None``）。"""
    t = _canonical(t)
    if t.kind == TypeKind.POINTER:
      return self._map_function_proto(t.get_pointee())
    if t.kind == TypeKind.TYPEDEF:
      return self._map_function_proto(_canonical(t))
    if t.kind == TypeKind.ELABORATED:
      can = _canonical(t)
      if can is not t:
        return self._map_function_proto(can)
    if t.kind != TypeKind.FUNCTIONPROTO:
      return "uintptr", "not-fn"
    try:
      result = t.get_result()
    except Exception:
      result = None
    if result is None or result.kind == TypeKind.VOID:
      ret_py = "None"
    else:
      ret_py, _ = self.map(result, is_return=True)
      if ret_py == "None":
        ret_py = "None"
    arg_anns: list[str] = []
    try:
      args_types = list(t.argument_types())
    except Exception:
      args_types = []
    for at in args_types:
      if at.kind == TypeKind.VOID:
        continue
      a, _ = self.map(at, is_return=False)
      arg_anns.append(a)
    args_body = ", ".join(arg_anns)
    return f"Function[[{args_body}], {ret_py}]", "fn ptr"

  def _ensure_record_from_type(self, t) -> str | None:
    """登记结构体并返回 Python 类型名（优先 typedef 名，否则 tag）。"""
    t0 = t
    if t.kind == TypeKind.TYPEDEF:
      tname = t.get_declaration().spelling or ""
      if not _is_c_ident(tname):
        tname = ""
      can = _canonical(t)
      rn = _record_name(can)
      decl = _record_decl_cursor(can)
      incomplete = _is_incomplete_record(can)
      is_union = bool(decl and decl.kind == CursorKind.UNION_DECL)
      path = _record_cpp_path(decl) if decl is not None else None
      if rn:
        self.note_struct(rn, incomplete=incomplete, is_union=is_union, c_cpp_path=path)
        if tname and tname != rn:
          self.note_alias(tname, rn)
          return pyi_export_name(tname)
        return pyi_export_name(rn)
      if tname:
        # 匿名 struct/union 的 typedef
        fields = self._collect_fields(decl) if decl and not incomplete else []
        self.note_struct(
          tname,
          incomplete=incomplete or not fields,
          is_union=is_union,
          fields=fields,
          c_cpp_path=tname,
        )
        return pyi_export_name(tname)
      return None
    rn = _record_name(t0)
    if not rn:
      return None
    decl = _record_decl_cursor(t0)
    incomplete = _is_incomplete_record(t0)
    is_union = bool(decl and decl.kind == CursorKind.UNION_DECL)
    fields = self._collect_fields(decl) if decl and not incomplete else []
    path = _record_cpp_path(decl) if decl is not None else rn
    self.note_struct(
      rn,
      incomplete=incomplete or is_union or not fields,
      is_union=is_union,
      fields=[] if (incomplete or is_union) else fields,
      c_cpp_path=path,
    )
    return pyi_export_name(rn)

  def _ensure_enum_from_type(self, t) -> str | None:
    """登记枚举并返回 Python 类型名（优先 typedef 公开名，否则 enum 标签）。"""
    if t is None:
      return None
    if t.kind == TypeKind.TYPEDEF:
      tname = t.get_declaration().spelling or ""
      if not _is_c_ident(tname):
        return None
      can = _canonical(t)
      if can.kind != TypeKind.ENUM:
        return None
      tag = _enum_tag_name(can)
      if tag:
        self.note_enum(tag)
        if tname != tag:
          self.note_alias(tname, tag)
          return pyi_export_name(tname)
        return pyi_export_name(tag)
      # typedef enum { … } Name
      self.note_enum(tname, c_cpp_path=tname)
      return pyi_export_name(tname)
    if t.kind == TypeKind.ELABORATED:
      sp = (_type_spelling(t) or "").strip()
      can = _canonical(t)
      if can.kind == TypeKind.ENUM:
        tag = _enum_tag_name(can)
        if _is_c_ident(sp) and sp not in ("enum",):
          if tag and tag != sp:
            self.note_enum(tag)
            self.note_alias(sp, tag)
            return pyi_export_name(sp)
          self.note_enum(sp)
          return pyi_export_name(sp)
        if tag:
          self.note_enum(tag)
          return pyi_export_name(tag)
      decl = t.get_declaration()
      if decl is not None and decl.kind == CursorKind.TYPEDEF_DECL:
        return self._ensure_enum_from_type(decl.type)
      return self._ensure_enum_from_type(can) if can is not t else None
    tag = _enum_tag_name(t)
    if tag:
      self.note_enum(tag)
      return pyi_export_name(tag)
    return None

  def _add_enum_constants(
    self,
    enum_decl,
    *,
    enum_py: str,
    resolved_consts: dict[str, ConstDef],
    seen_consts: set[str],
  ) -> None:
    if enum_decl is None or not enum_py:
      return
    for ch in enum_decl.get_children():
      if ch.kind != CursorKind.ENUM_CONSTANT_DECL:
        continue
      c_name = ch.spelling or ""
      if not _is_c_ident(c_name):
        continue
      try:
        val = int(ch.enum_value)
      except Exception:
        continue
      py_name = pyi_const_export_name(c_name)
      seen_consts.add(c_name)
      resolved_consts[c_name] = ConstDef(
        name=c_name,
        py_name=py_name,
        native=c_name,
        ann=enum_py,
        value=str(val),
      )

  def _collect_fields(self, decl) -> list[FieldDef]:
    if decl is None:
      return []
    key = decl.spelling or f"anon@{id(decl)}"
    if key in self._collecting:
      return []
    self._collecting.add(key)
    try:
      out: list[FieldDef] = []
      for ch in decl.get_children():
        if ch.kind != CursorKind.FIELD_DECL:
          continue
        fname = ch.spelling or ""
        if not fname or not fname.isidentifier():
          continue
        try:
          if ch.is_bitfield():
            continue
        except Exception:
          pass
        ann, cmt = self.map(ch.type, is_return=False)
        known = self.known_type_names()
        ann2 = _rewrite_identifiers_in_ann(ann, known)
        ann2, cmt2 = _sanitize_pyi_ann(ann2, cmt)
        c_fname = fname
        py_fname = pyi_field_export_name(c_fname)
        out.append(FieldDef(name=py_fname, ann=ann2, comment=cmt2, c_name=c_fname))
      return out
    finally:
      self._collecting.discard(key)

  def map(self, t, *, is_return: bool = False) -> tuple[str, str]:
    """返回 (annotation, optional_comment)。"""
    if t is None:
      return "uintptr", "null type"

    k = t.kind
    if k == TypeKind.VOID:
      return "None", ""

    # MSVC/SDK 常把 typedef 别名标成 ELABORATED（如 GLfloat / 枚举 typedef）
    if k == TypeKind.ELABORATED:
      en = self._ensure_enum_from_type(t)
      if en:
        return en, ""
      can = _canonical(t)
      if can.kind == TypeKind.RECORD or _is_incomplete_record(can):
        py = self._ensure_record_from_type(t)
        if py:
          return py, ""
        # 匿名嵌套 union/struct：合法字段用 None
        sp = _type_spelling(t) or _type_spelling(can)
        kind_word = "union" if "union" in sp.lower() else "struct"
        return "None", f"C: unnamed {kind_word}"
      if can is not t and can.kind != TypeKind.ELABORATED:
        return self.map(can, is_return=is_return)

    if k == TypeKind.TYPEDEF:
      name = t.get_declaration().spelling or ""
      can = _canonical(t)
      if name in ("sqlite3_int64", "sqlite_int64"):
        return "int64", ""
      if name in ("sqlite3_uint64", "sqlite_uint64"):
        return "uint64", ""
      if name in ("sqlite3_filename",):
        return "CStr", ""
      # Win32 句柄 / void* 宽度别名（函数指针 FARPROC/PROC 等走 Function，不在此列）
      if name in (
        "HANDLE", "HWND", "HINSTANCE", "HMODULE", "HICON", "HCURSOR", "HBRUSH",
        "HDC", "HMENU", "HBITMAP", "HFONT", "HPEN", "HRGN", "HTREEITEM",
        "HGLOBAL", "HLOCAL", "HKEY", "HMONITOR", "HDESK", "HWINSTA",
        "PVOID", "LPVOID", "LPCVOID",
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
      if can.kind == TypeKind.ENUM:
        py = self._ensure_enum_from_type(t)
        if py:
          return py, ""
      if can.kind == TypeKind.POINTER and can.get_pointee().kind == TypeKind.FUNCTIONPROTO:
        return self._map_function_proto(can.get_pointee())
      if can.kind == TypeKind.FUNCTIONPROTO:
        return self._map_function_proto(can)
      if can.kind in (TypeKind.RECORD, TypeKind.ELABORATED) or _is_incomplete_record(can):
        py = self._ensure_record_from_type(t)
        if py:
          return py, ""
      return self.map(can, is_return=is_return)

    if k in (TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE):
      pointee = t.get_pointee()
      pk = pointee.kind
      if pk == TypeKind.FUNCTIONPROTO or (
        pk == TypeKind.TYPEDEF and _canonical(pointee).kind == TypeKind.FUNCTIONPROTO
      ):
        return self._map_function_proto(pointee)
      if pk == TypeKind.ELABORATED:
        can_p = _canonical(pointee)
        if can_p.kind == TypeKind.FUNCTIONPROTO or (
          can_p.kind == TypeKind.POINTER
          and can_p.get_pointee().kind == TypeKind.FUNCTIONPROTO
        ):
          return self._map_function_proto(can_p)
      psp = _type_spelling(pointee).replace("const ", "").strip()
      if pk in (TypeKind.CHAR_S, TypeKind.CHAR_U, TypeKind.SCHAR, TypeKind.UCHAR):
        return "CStr", ""
      if psp in ("char", "signed char", "unsigned char", "WCHAR", "wchar_t"):
        return "CStr", ""
      if pk == TypeKind.VOID:
        return "uintptr", ""
      if pk == TypeKind.TYPEDEF:
        tname = pointee.get_declaration().spelling or ""
        if tname in ("WCHAR", "CHAR", "TCHAR"):
          return "CStr", ""
      # GLfloat* / GLdouble* 等：ELABORATED/TYPEDEF 标量先映成 Pointer[float]/Pointer[float64]
      if pk in (TypeKind.TYPEDEF, TypeKind.ELABORATED):
        inner_ann, inner_cmt = self.map(pointee, is_return=False)
        if inner_ann.startswith("Function["):
          return inner_ann, inner_cmt
        if inner_ann in (
          "float",
          "float64",
          "int",
          "int64",
          "uint",
          "uint64",
          "uintptr",
          "bool",
          "byte",
          "char",
        ):
          return f"Pointer[{inner_ann}]", inner_cmt
        if inner_ann.startswith("Pointer[") or (
          inner_ann.isidentifier() and not inner_ann.startswith("Function")
        ):
          return f"Pointer[{inner_ann}]", inner_cmt
      if pk in (TypeKind.RECORD, TypeKind.ELABORATED, TypeKind.TYPEDEF) or _is_incomplete_record(pointee):
        inner = _canonical(pointee)
        if inner.kind == TypeKind.POINTER:
          # T** → Pointer[Pointer[T]]
          inner_ann, inner_cmt = self.map(pointee, is_return=False)
          return f"Pointer[{inner_ann}]", inner_cmt or "out ptr"
        py = self._ensure_record_from_type(pointee)
        if py:
          return f"Pointer[{py}]", ""
        if pk == TypeKind.TYPEDEF:
          ann, cmt = self.map(pointee, is_return=False)
          if ann.startswith("Function["):
            return ann, cmt
          if ann in ("uintptr", "uint64") or ann.isidentifier() or ann.startswith("Pointer["):
            return f"Pointer[{ann}]", cmt
        return "uintptr", "opaque*"
      inner_ann, cmt = self.map(pointee, is_return=False)
      if inner_ann == "None":
        return "uintptr", cmt
      if inner_ann.startswith("Function["):
        return inner_ann, cmt
      return f"Pointer[{inner_ann}]", cmt

    if k == TypeKind.FUNCTIONPROTO:
      return self._map_function_proto(t)

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
    if k == TypeKind.FLOAT:
      return "float", ""
    if k in (TypeKind.DOUBLE, TypeKind.LONGDOUBLE):
      return "float64", ""
    if k == TypeKind.ENUM:
      py = self._ensure_enum_from_type(t)
      if py:
        return py, ""
      return "None", "C: unnamed enum"
    if k in (TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY, TypeKind.VARIABLEARRAY):
      elem = t.element_type
      ann, cmt = self.map(elem, is_return=False)
      ann, cmt = _sanitize_pyi_ann(ann, cmt or "array")
      if ann == "None":
        return "None", cmt or "C: array"
      return f"Pointer[{ann}]", cmt or "array"
    if k == TypeKind.RECORD:
      py = self._ensure_record_from_type(t)
      if py:
        return py, ""
      sp = _type_spelling(t)
      kind_word = "union" if "union" in sp.lower() else "struct"
      return "None", f"C: unnamed {kind_word}"

    sp = _type_spelling(t)
    if "va_list" in sp:
      return "uintptr", "va_list"
    return "None", f"C: {_shorten_c_type_comment(sp or k.name)}"


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
  # 单标识符别名：#define GLFW_MOUSE_BUTTON_LEFT GLFW_MOUSE_BUTTON_1
  if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cleaned) and cleaned != name:
    return "alias", cleaned
  return None


def _resolve_macro_aliases(
  pending: list[tuple[str, str, str | None]],
  resolved: dict[str, ConstDef],
) -> None:
  """把 ``alias`` 宏解析到已有数值常量；多轮直到不动。"""
  progress = True
  while progress and pending:
    progress = False
    still: list[tuple[str, str, str | None]] = []
    for name, ref, native in pending:
      if name in resolved:
        continue
      target = resolved.get(ref)
      if target is None:
        still.append((name, ref, native))
        continue
      py_name = pyi_const_export_name(name)
      resolved[name] = ConstDef(
        name=name,
        py_name=py_name,
        native=name if native is None else native,
        ann=target.ann,
        value=target.value,
      )
      progress = True
    pending[:] = still


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
    # sqlite amalgamation：不传递；Win32 / UCRT：传递（UCRT 根已限 ucrt/，见 _collect_roots）
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
  resolved_consts: dict[str, ConstDef] = {}
  alias_pending: list[tuple[str, str, str | None]] = []

  for c in tu.cursor.walk_preorder():
    if not _file_in_scope(c.location.file, header, roots, include_deps=include_deps):
      continue
    kind = c.kind

    if kind in (CursorKind.STRUCT_DECL, CursorKind.UNION_DECL) and _is_c_ident(c.spelling):
      incomplete = _is_incomplete_record(c.type)
      is_union = kind == CursorKind.UNION_DECL
      fields: list[FieldDef] = []
      if not incomplete and not is_union:
        fields = mapper._collect_fields(c)
      # union / 无字段 → 空 @native 类（类体 ...）
      as_empty = incomplete or is_union or not fields
      mapper.note_struct(
        c.spelling,
        incomplete=as_empty,
        is_union=is_union,
        fields=[] if as_empty else fields,
        c_cpp_path=_record_cpp_path(c),
        doc=_cursor_doc(c),
      )
      continue

    if kind == CursorKind.ENUM_DECL and _is_c_ident(c.spelling):
      mapper.note_enum(
        c.spelling,
        c_cpp_path=_record_cpp_path(c) or c.spelling,
        doc=_cursor_doc(c),
      )
      mapper._add_enum_constants(
        c,
        enum_py=pyi_type_export_name(c.spelling, is_enum=True),
        resolved_consts=resolved_consts,
        seen_consts=seen_consts,
      )
      continue

    if kind == CursorKind.TYPEDEF_DECL and _is_c_ident(c.spelling):
      can = _canonical(c.type)
      if can.kind == TypeKind.ENUM:
        enum_py = mapper._ensure_enum_from_type(c.type)
        enum_decl = can.get_declaration()
        if enum_py and enum_decl is not None:
          mapper._add_enum_constants(
            enum_decl,
            enum_py=enum_py,
            resolved_consts=resolved_consts,
            seen_consts=seen_consts,
          )
      elif can.kind in (TypeKind.RECORD, TypeKind.ELABORATED) or _is_incomplete_record(can):
        mapper._ensure_record_from_type(c.type)
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
      _base, _ = _py_ident(name)
      py_name = pyi_const_export_name(_base if _base == name else name)
      # 常量始终保留 C 宏名供 #undef / 文档
      native = name
      if ann == "alias":
        alias_pending.append((name, val, native))
        continue
      resolved_consts[name] = ConstDef(
        name=name, py_name=py_name, native=native, ann=ann, value=val
      )
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
    py_name = pyi_func_export_name(c_name)
    ret_ann, ret_cmt = mapper.map(c.result_type, is_return=True)
    ret_ann, ret_cmt = _sanitize_pyi_ann(ret_ann, ret_cmt)
    params: list[ParamDef] = []
    used: set[str] = set()
    for i, arg in enumerate(c.get_arguments()):
      raw = arg.spelling or f"arg{i}"
      pann, pc = mapper.map(arg.type, is_return=False)
      pann, _ = _sanitize_pyi_ann(pann, pc)
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
          pann, pc = mapper.map(at, is_return=False)
          pann, _ = _sanitize_pyi_ann(pann, pc)
          params.append(ParamDef(py_name=f"arg{i}", ann=pann))
    is_variadic = False
    try:
      if c.type.kind == TypeKind.FUNCTIONPROTO and c.type.is_function_variadic():
        is_variadic = True
    except Exception:
      is_variadic = False
    model.funcs.append(
      FuncDef(
        c_name=c_name,
        py_name=py_name,
        ret=ret_ann,
        params=params,
        comment=ret_cmt,
        doc=_cursor_doc(c),
        variadic=is_variadic,
      )
    )

  _resolve_macro_aliases(alias_pending, resolved_consts)
  # 确保 alias 目标结构体/枚举已登记
  for _alias, target in list(mapper.aliases.items()):
    if target not in mapper.structs and target not in mapper.enums:
      mapper.note_struct(target, incomplete=True)
  # 枚举常量注解优先 typedef 公开名（``typedef enum _E {…} E`` → ``Pyi_E``）
  tag_to_public: dict[str, str] = {}
  for alias, target in mapper.aliases.items():
    if target in mapper.enums and alias not in mapper.enums:
      tag_to_public.setdefault(target, alias)
  for const in resolved_consts.values():
    if not const.ann.startswith(PYI_PREFIX):
      continue
    tag = pyi_c_name_from_export(const.ann)
    pub = tag_to_public.get(tag)
    if pub:
      const.ann = pyi_export_name(pub)
  model.structs = sorted(mapper.structs.values(), key=lambda s: s.c_name)
  model.enums = sorted(mapper.enums.values(), key=lambda e: e.c_name)
  model.aliases = [
    TypeAliasDef(py_name=pyi_type_export_name(a), target=pyi_type_export_name(tgt))
    for a, tgt in sorted(mapper.aliases.items())
    if tgt in mapper.structs or tgt in mapper.enums or _is_c_ident(tgt)
  ]
  # 同 py 导出名（``OVERFLOW``/``_OVERFLOW`` → ``PyiOverflow``）保留首次（优先无前导 ``_``）
  by_py_const: dict[str, ConstDef] = {}
  for const in sorted(
    resolved_consts.values(),
    key=lambda c: (c.py_name, 0 if not c.name.startswith("_") else 1, c.name),
  ):
    by_py_const.setdefault(const.py_name, const)
  model.consts = sorted(by_py_const.values(), key=lambda x: x.name)
  model.funcs.sort(key=lambda x: x.c_name)
  return model


def _rewrite_self_ann(ann: str, c_name: str) -> str:
  """同类字段注解：``Pointer[PyiFoo]`` / ``PyiFoo`` → ``Self``（满足 S15）。"""
  if not c_name:
    return ann
  py = pyi_type_export_name(c_name)
  ann = re.sub(rf"\b{re.escape(py)}\b", "Self", ann)
  ann = re.sub(rf"\b{re.escape(c_name)}\b", "Self", ann)
  return ann


def _render_struct(st: StructDef) -> list[str]:
  py_cls = pyi_type_export_name(st.c_name)
  native = st.c_cpp_path or st.c_name
  lines: list[str] = [
    "@native",
    f'@native_name("{native}")',
    f"class {py_cls}:",
  ]
  if st.doc:
    lines.extend(_emit_docstring_lines(st.doc))
  if st.incomplete or not st.fields:
    kind = "union" if st.is_union else "incomplete struct"
    lines.append(f"  ...  # C {kind}")
    return lines
  for fd in st.fields:
    ann = _rewrite_self_ann(fd.ann, st.c_name)
    ann, cmt_body = _sanitize_pyi_ann(ann, fd.comment)
    cmt = f"  # {cmt_body}" if cmt_body else ""
    c_field = fd.c_name or fd.name
    if c_field != fd.name:
      lines.append(f'  {fd.name}: {ann} @native_name("{c_field}"){cmt}')
    else:
      lines.append(f"  {fd.name}: {ann}{cmt}")
  return lines


def _render_enum(en: EnumDef) -> list[str]:
  py_cls = pyi_type_export_name(en.c_name, is_enum=True)
  native = en.c_cpp_path or en.c_name
  lines = [
    "@native",
    f'@native_name("{native}")',
    f"class {py_cls}:",
  ]
  if en.doc:
    lines.extend(_emit_docstring_lines(en.doc))
  lines.append("  ...  # C enum")
  return lines


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
    "# Structs / unions（模块名 Pyi…；@native_name 为 C 标签；C++ using 别名，不生成新 struct）",
    "# ---------------------------------------------------------------------------",
    "",
  ]
  for st in model.structs:
    lines.extend(_render_struct(st))
    lines.append("")
  if model.enums:
    lines.extend([
      "# ---------------------------------------------------------------------------",
      "# Enums（空 @native 类；C++ using PyiE = ::E；成员见 Constants；类名带 Enum 后缀）",
      "# ---------------------------------------------------------------------------",
      "",
    ])
    for en in model.enums:
      lines.extend(_render_enum(en))
      lines.append("")
  if model.aliases:
    lines.extend([
      "# ---------------------------------------------------------------------------",
      "# Typedef aliases（type PyiAlias = PyiStructTag / PyiEnumTag）",
      "# ---------------------------------------------------------------------------",
      "",
    ])
    for al in model.aliases:
      lines.append(f"type {al.py_name} = {al.target}")
    lines.append("")

  lines.extend([
    "# ---------------------------------------------------------------------------",
    "# Constants（#define 与 enum 成员；@native_name 为 C 宏名）",
    "# ---------------------------------------------------------------------------",
    "",
  ])
  for c in model.consts:
    ann, _ = _sanitize_pyi_ann(c.ann, "")
    if c.native and c.native != c.py_name:
      lines.append(f'{c.py_name}: {ann} @native_name("{c.native}") = {c.value}')
    else:
      lines.append(f"{c.py_name}: {ann} = {c.value}")
  if model.consts:
    lines.append("")

  lines.extend([
    "# ---------------------------------------------------------------------------",
    "# Functions",
    "# ---------------------------------------------------------------------------",
    "",
  ])
  # 同 py 导出名（如 ``_chdir``/``chdir`` → ``pyiChdir``）须全部 ``@overload``（S17）
  py_name_counts: dict[str, int] = {}
  for fn in model.funcs:
    py_name_counts[fn.py_name] = py_name_counts.get(fn.py_name, 0) + 1
  for fn in model.funcs:
    if py_name_counts.get(fn.py_name, 0) > 1:
      lines.append("@overload")
    lines.append("@native")
    lines.append(f'@native_name("{fn.c_name}")')
    args = ", ".join(f"{p.py_name}: {p.ann}" for p in fn.params)
    if fn.variadic:
      args = f"{args}, *_" if args else "*_"
    comment = f"  # {fn.comment}" if fn.comment else ""
    lines.append(f"def {fn.py_name}({args}) -> {fn.ret}:{comment}")
    if fn.doc:
      lines.extend(_emit_docstring_lines(fn.doc))
    lines.append("  ...")
    lines.append("")

  lines.append(
    f"# stats: structs={len(model.structs)} enums={len(model.enums)} "
    f"aliases={len(model.aliases)} consts={len(model.consts)} funcs={len(model.funcs)}"
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
    if "class PyiSqlite3:" not in text:
      errs.append("missing @native class PyiSqlite3")
    if '@native_name("sqlite3")' not in text:
      errs.append("sqlite3 class must keep @native_name")
    if "Pointer[PyiSqlite3]" not in text:
      errs.append("sqlite3* should map to Pointer[PyiSqlite3]")
    if "PyiSqliteOk" not in text:
      errs.append("constants must use Pyi PascalCase (PyiSqliteOk)")
    if "type sqlite3_h =" in text or "class sqlite3_h" in text:
      errs.append("legacy *_h handle alias must not appear")
  else:
    names = {f.c_name for f in model.funcs}
    hname = header.name.lower()
    bucket = windows_sdk_include_bucket(header)
    if hname in {"glfw3.h"}:
      if len(model.funcs) < 50:
        errs.append(f"too few funcs for glfw3.h: {len(model.funcs)}")
      for need in ("glfwInit", "glfwCreateWindow", "glfwPollEvents", "glfwTerminate"):
        if need not in names:
          errs.append(f"missing function {need}")
      const_names = {c.name for c in model.consts}
      if "GLFW_MOUSE_BUTTON_LEFT" not in const_names:
        errs.append("missing alias const GLFW_MOUSE_BUTTON_LEFT")
      if "class PyiGlfwWindow:" not in text:
        errs.append("missing @native class PyiGlfwWindow")
      if "Pointer[PyiGlfwWindow]" not in text:
        errs.append("GLFWwindow* should map to Pointer[PyiGlfwWindow]")
      if "GLFWwindow_h" in text:
        errs.append("legacy GLFWwindow_h must not appear")
    elif hname in {"gl.h"}:
      if len(model.funcs) < 30:
        errs.append(f"too few funcs for GL/gl.h: {len(model.funcs)}")
      for need in ("glClear", "glBegin", "glVertex3d", "glMatrixMode"):
        if need not in names:
          errs.append(f"missing function {need}")
      if "GL_TRIANGLES" not in {c.name for c in model.consts}:
        errs.append("missing GL_TRIANGLES")
    elif bucket == "ucrt" or "third_party/posix" in str(header).replace("\\", "/").lower() or (
      "posix" in str(header).replace("\\", "/").lower() and "third_party" in str(header).replace("\\", "/").lower()
    ):
      # CRT / POSIX stub：函数量远小于 Win32 伞头
      if len(model.funcs) < 1 and len(model.aliases) < 1 and len(model.structs) < 1:
        errs.append(f"too few symbols for CRT/POSIX header {hname}: funcs={len(model.funcs)}")
      crt_any: dict[str, tuple[str, ...]] = {
        "stdio.h": ("printf", "fopen", "fread", "sprintf", "fwrite"),
        "string.h": ("memcpy", "strlen", "memcmp", "strcpy", "memmove", "strcmp"),
        "math.h": ("sin", "cos", "sqrt", "fabs", "pow", "floor"),
        "time.h": ("time", "difftime", "_time64", "clock", "mktime"),
        "stdlib.h": ("malloc", "free", "abort", "_malloc_base", "exit", "atoi"),
      }
      need = crt_any.get(hname, ())
      if need and not (names & set(need)):
        errs.append(f"CRT header {hname} missing any of {need}")
    elif "gdiplus_pyi_seed" in hname or "third_party/windows" in str(header).replace("\\", "/").lower():
      # C++ API seed：仅保证 glue 能挂 ``#include <gdiplus.h>``
      if "GdiplusStartup" not in names and len(model.funcs) < 1:
        errs.append(f"seed header {hname} missing GdiplusStartup / funcs")
    elif bucket in {"um", "shared"} and hname != "windows.h":
      # Win32 子系统头（winsock2 / commctrl …）：可远小于伞头
      if len(model.funcs) < 1 and len(model.structs) < 1 and len(model.consts) < 1:
        errs.append(f"too few symbols for Win32 header {hname}")
    else:
      # Win32 / 通用：至少要有一批函数
      if len(model.funcs) < 100:
        errs.append(f"too few funcs for non-sqlite header: {len(model.funcs)}")
      # windows.h 伞头应带上 CreateWindowExW 或 MessageBoxW 等
      if hname == "windows.h":
        if not ({"MessageBoxW", "CreateWindowExW", "GetMessageW"} & names):
          errs.append(
            "windows.h pyi missing core UI symbols (MessageBoxW/CreateWindowExW/GetMessageW)"
          )
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
    f"[gen_c_ffi] structs={len(model.structs)} enums={len(model.enums)} "
    f"aliases={len(model.aliases)} consts={len(model.consts)} funcs={len(model.funcs)}"
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
