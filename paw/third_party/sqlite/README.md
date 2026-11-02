# SQLite amalgamation（Py2Cpp 内嵌）

本目录 vendoring **SQLite amalgamation**，供 `py2cpp/sql/sqlite.py` 的 `@native` 叶子链接使用。

| 文件 | 说明 |
|------|------|
| `sqlite3.c` | 合并后的库实现（编译时作为额外 TU 链接） |
| `sqlite3.h` | 公开 C API |
| `sqlite3ext.h` | 扩展 API 头（加载扩展等；P0 可不启用） |

FFI 声明不写在本目录：生成到 **`ffi/sqlite/sqlite3.pyi`**（`ffi.bat` / `scripts/gen_c_ffi.py`；见 [docs/c-ffi-pyi.md](../../docs/c-ffi-pyi.md)）。

## 当前版本

- **SQLite 3.53.2**（amalgamation 包名 `3530200`）
- 下载页：<https://www.sqlite.org/download.html>
- 直链：<https://www.sqlite.org/2026/sqlite-amalgamation-3530200.zip>
- SHA3-256：`81142986038e18f96c4a54e1a72562ae17e502a916f2a7701eff43388cbf1a40`

## 升级步骤

1. 从官网下载新版 `sqlite-amalgamation-*.zip`
2. 解压后覆盖本目录的 `sqlite3.c` / `sqlite3.h` / `sqlite3ext.h`
3. 重生成 FFI 声明：`ffi third_party\sqlite\sqlite3.h`（写出 `ffi\sqlite\sqlite3.pyi`）
4. 更新本 README 的版本号与校验和
5. 重编 `test/sql/test_sqlite.py`（及依赖 SQL 的用例）

## 编译约定（实现 P0 时）

- 测试 / 示例链接：`compile.py` 的 `extra_sources` 传入 `third_party/sqlite/sqlite3.c`
- include 路径：`-I third_party/sqlite`（`sqlite.inl` 中 `#include "sqlite3.h"`）
- 建议预定义（MSVC）：`SQLITE_THREADSAFE=1`、`SQLITE_OMIT_LOAD_EXTENSION=1`（P0 不加载扩展）

未 vendoring `shell.c`（命令行 shell，非嵌入所需）。
