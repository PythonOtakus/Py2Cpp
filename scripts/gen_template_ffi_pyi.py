#!/usr/bin/env python3
"""一次性：生成模板迁移所需的全部 ``ffi/**/*.pyi``（勿手写）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.tools.c_ffi_pyi import generate_pyi  # noqa: E402

# Win32 子系统头单独解析时需预包含 windows.h（否则缺 HWND/DWORD 等基类型）
_WIN_SUBSYSTEM_PREINCLUDE = ["-include", "windows.h"]

# (header, include_deps, clang_args, out|None)
JOBS: list[tuple[str, bool | None, list[str] | None, Path | None]] = [
  # CRT（stdint/stdarg/float/math → 模板改用 cstdint/cstdarg/cfloat/cmath，不强制进模板映射）
  ("stdio", True, None, None),
  ("string", True, None, None),
  ("math", True, None, None),  # 可选声明面；模板直导改 <cmath>
  ("time", True, None, None),
  ("stdlib", True, None, None),
  ("errno", True, None, None),
  ("signal", True, None, None),
  ("fcntl", True, None, None),
  ("direct", True, None, None),
  ("io", True, None, None),
  ("sys/stat", True, None, None),
  ("sys/utime", True, None, None),
  # Win32
  ("windows", True, None, None),
  ("winsock2", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  ("ws2tcpip", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  ("commctrl", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  ("commdlg", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  ("shellapi", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  # GDI+ 为 C++ namespace：seed 头生成声明面；glue 仍 #include <gdiplus.h>
  (
    "third_party/windows/gdiplus_pyi_seed.h",
    False,
    _WIN_SUBSYSTEM_PREINCLUDE,
    ROOT / "ffi" / "windows" / "gdiplus.pyi",
  ),
  ("objidl", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  ("winhttp", False, _WIN_SUBSYSTEM_PREINCLUDE, None),
  # POSIX stubs
  ("third_party/posix/unistd.h", False, None, None),
  ("third_party/posix/pthread.h", False, None, None),
  ("third_party/posix/dirent.h", False, None, None),
  ("third_party/posix/sys/types.h", False, None, None),
  ("third_party/posix/sys/socket.h", False, None, None),
  ("third_party/posix/sys/select.h", False, None, None),
  ("third_party/posix/sys/wait.h", False, None, None),
  ("third_party/posix/sys/ioctl.h", False, None, None),
  ("third_party/posix/sys/syscall.h", False, None, None),
  ("third_party/posix/netinet/in.h", False, None, None),
  ("third_party/posix/arpa/inet.h", False, None, None),
  # sqlite（已有；重生成保持一致）
  ("third_party/sqlite/sqlite3.h", False, None, None),
]


def main() -> int:
  failed = 0
  for header, deps, extra, out in JOBS:
    print("=" * 60)
    try:
      rc = generate_pyi(header, include_deps=deps, clang_args=extra, out=out)
    except SystemExit as e:
      code = e.code
      rc = int(code) if isinstance(code, int) else 1
      print(f"FAIL(exception): {header}: {e}", file=sys.stderr)
    if rc != 0:
      print(f"FAIL: {header}", file=sys.stderr)
      failed += 1
  print("=" * 60)
  print(f"done; failed={failed}/{len(JOBS)}")
  return 1 if failed else 0


if __name__ == "__main__":
  raise SystemExit(main())
