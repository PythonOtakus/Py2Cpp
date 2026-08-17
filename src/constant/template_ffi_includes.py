"""``templates/**`` 直导 A/B 头 → ``ffi/…`` 映射（T26 + 迁移）。

A+B：第三方 / Windows SDK / CRT·UCRT / POSIX（``#else`` 分支）。
**不**含 C++ STL（``type_traits`` / ``atomic`` / ``utility`` / ``cstdint`` / ``string`` 等）。
"""
from __future__ import annotations

import re
from functools import lru_cache

# 系统头（小写、无路径前缀变体已归一）→ ``#include "ffi/….h"`` 相对 ``generated/runtime``
_TEMPLATE_SYSTEM_HEADER_TO_FFI: dict[str, str] = {
  # CRT / UCRT
  "stdio.h": "ffi/crt/stdio.h",
  "string.h": "ffi/crt/string.h",
  "stdlib.h": "ffi/crt/stdlib.h",
  # math.h → <cmath>（见 _C_TO_CXX_HEADER）；勿经 ffi/crt/math，避免 py_types↔math 环
  "time.h": "ffi/crt/time.h",
  "errno.h": "ffi/crt/errno.h",
  "signal.h": "ffi/crt/signal.h",
  "fcntl.h": "ffi/crt/fcntl.h",
  "direct.h": "ffi/crt/direct.h",
  "io.h": "ffi/crt/io.h",
  "sys/stat.h": "ffi/crt/stat.h",
  "sys/utime.h": "ffi/crt/utime.h",
  "utime.h": "ffi/crt/utime.h",
  # Windows SDK
  "windows.h": "ffi/windows/windows.h",
  "winsock2.h": "ffi/windows/winsock2.h",
  "ws2tcpip.h": "ffi/windows/ws2tcpip.h",
  "commctrl.h": "ffi/windows/commctrl.h",
  "commdlg.h": "ffi/windows/commdlg.h",
  "shellapi.h": "ffi/windows/shellapi.h",
  "gdiplus.h": "ffi/windows/gdiplus.h",
  "objidl.h": "ffi/windows/objidl.h",
  "winhttp.h": "ffi/windows/winhttp.h",
  # 第三方
  "sqlite3.h": "ffi/sqlite/sqlite3.h",
  # POSIX（``third_party/posix`` 生成声明面；glue 仍 ``#include <…>``）
  "unistd.h": "ffi/posix/unistd.h",
  "pthread.h": "ffi/posix/pthread.h",
  "dirent.h": "ffi/posix/dirent.h",
  "sys/types.h": "ffi/posix/sys/types.h",
  "sys/socket.h": "ffi/posix/sys/socket.h",
  "sys/select.h": "ffi/posix/sys/select.h",
  "sys/wait.h": "ffi/posix/sys/wait.h",
  "sys/ioctl.h": "ffi/posix/sys/ioctl.h",
  "sys/syscall.h": "ffi/posix/sys/syscall.h",
  "netinet/in.h": "ffi/posix/netinet/in.h",
  "arpa/inet.h": "ffi/posix/arpa/inet.h",
}

# C 头 → C++ 包装头（允许直导 STL，不走 ffi）
_C_TO_CXX_HEADER: dict[str, str] = {
  "stdint.h": "cstdint",
  "stdarg.h": "cstdarg",
  "float.h": "cfloat",
  "math.h": "cmath",  # INFINITY/isnan/sin；与 cstdint 同类，打断 py_types↔ffi/crt/math 环
}

# C++ STL / 语言设施：允许模板直导
_ALLOWED_CPP_STL_HEADERS: frozenset[str] = frozenset({
  "atomic",
  "chrono",
  "cmath",
  "condition_variable",
  "cstdint",
  "cstdarg",
  "cfloat",
  "mutex",
  "thread",
  "type_traits",
  "utility",
  "string",  # C++ ``<string>``，非 ``string.h``
})

_INCLUDE_RE = re.compile(
  r'^[ \t]*#[ \t]*include[ \t]*([<"])([^>"]+)[>"]',
  re.MULTILINE,
)


def normalize_system_header(header: str) -> str:
  h = header.replace("\\", "/").strip().lower()
  if h.startswith("./"):
    h = h[2:]
  return h


def ffi_include_for_system_header(header: str) -> str | None:
  """若须经 ffi 中转，返回 ``ffi/….h``；C→C++ 包装返回 ``cstdint`` 等；否则 ``None``。"""
  h = normalize_system_header(header)
  if h in _C_TO_CXX_HEADER:
    return _C_TO_CXX_HEADER[h]
  return _TEMPLATE_SYSTEM_HEADER_TO_FFI.get(h)


def is_forbidden_template_ab_include(header: str) -> bool:
  """T26：禁止的 A/B 直导（已有 ffi 映射或未登记的系统头，且非 STL）。"""
  h = normalize_system_header(header)
  if h in _ALLOWED_CPP_STL_HEADERS:
    return False
  if h in _C_TO_CXX_HEADER:
    return True  # 须改写为 cstdint 等，禁止再写 stdint.h
  if h.startswith("py2cpp/") or h.startswith("ffi/"):
    return False
  if "/" not in h and h.endswith(".h") and h in {
    "py_types.h", "char.h", "member_access.h",
  }:
    return False
  if h in _TEMPLATE_SYSTEM_HEADER_TO_FFI:
    return True
  # 尖括号风格的未知系统头（无扩展名的 STL 已在允许集）
  if "." in h or "/" in h:
    return True
  return False


@lru_cache(maxsize=1)
def ffi_modules_required_by_templates() -> tuple[str, ...]:
  """bootstrap 须始终翻译的 ffi module_path（由映射表推导）。"""
  mods: set[str] = set()
  for ffi_h in _TEMPLATE_SYSTEM_HEADER_TO_FFI.values():
    # ffi/crt/stdio.h → ffi/crt/stdio
    rel = ffi_h[:-2] if ffi_h.endswith(".h") else ffi_h
    mods.add(rel.replace("\\", "/"))
  return tuple(sorted(mods))


def iter_include_headers_in_text(text: str) -> list[tuple[int, str, str]]:
  """``(lineno, quote_or_angle, header)``。"""
  out: list[tuple[int, str, str]] = []
  for i, line in enumerate(text.splitlines(), start=1):
    m = _INCLUDE_RE.match(line)
    if not m:
      continue
    out.append((i, m.group(1), m.group(2).strip()))
  return out
