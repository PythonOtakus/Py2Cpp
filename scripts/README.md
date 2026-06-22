# scripts/

MSVC / 翻译构建与仓库维护脚本；在仓库根目录执行（脚本内会 `cd` 到根目录）。

## 构建（`.bat`）

| 脚本 | 说明 |
|------|------|
| `build_all.bat` | 全量集成测：bootstrap runtime + **并行**编译 `test/**/test_*.py`（跳过 `fail`/`perf`） |
| `build_protocol.bat` | 协议正向 + 负向 |
| `build_fail.bat` | 负向编译用例（并行） |
| `build.bat` | 按模式**并行**编译匹配用例（例：`build vararg`、`build spatial --jobs 8`） |
| `run.bat` | 同 `build.bat` 的 PATTERN，只运行已编译的 `generated\test\...\*.exe` |
| `build_perf_json.bat` | JSON 功能/性能用例 + CPython 基线对比 |
| `build.bat file` | 编译并运行 `test_file` |
| `run_core_tests.bat` | 在 `build_all` 后运行若干核心 stdlib `.exe` |

并行度：默认 **16**；可用 `PY2CPP_BUILD_JOBS` 或 `--jobs N` 覆盖；`--seq` 强制串行（`build.bat` / `build_all.bat` 透传）。各 job 在子进程内捕获输出，**完成时**按原 bat 格式整块打印（`=== test\… ===`、main.py 输出、耗时、OK/ERROR），避免多 job 输出穿插；完整 log 仍写入 `generated\.build_logs\`。

内部（由上述脚本 `call`）：

| 脚本 | 说明 |
|------|------|
| `_init_msvc.bat` | 探测并 `call vcvars64.bat` |
| `_clean_obj.bat` | 删除链接残留的 `.obj`（默认仅 STEM；bootstrap 用 `--global-py2cpp`） |
| `_build_timing.bat` / `_build_timing.py` | 耗时统计 |

## Python 工具

| 脚本 | 说明 |
|------|------|
| `parallel_build.py` | `build_all` / `build` / `build_fail` 的并行翻译+编译调度 |
| `match_test_files.py` | `build` / `run` 用的 `test_*.py` 路径匹配（子串 / `*` `?`） |
| `compare_json_perf.py` | `build_perf_json` 的 CPython JSON 性能基线 |
| `reorder_class_members.py` | 按 [编码规范 §4.3](../docs/编码规范.md#43-类体内成员顺序) 重排类体成员 |
| `scan_strict_violations.py` | bootstrap runtime 并收集 `--strict` 违规 |
| `_gen_compile_commands.bat` | 生成根目录 `compile_commands.json` / `compile_flags.txt`（`build*.bat` 结束时自动调用） |
| `gen_compile_commands.py` | 生成 `compile_commands.json`（`generated/**` + `templates/**`）与 `compile_flags.txt` |

仓库根目录保留同名转发（如 `build_all.bat` → `scripts\build_all.bat`），便于在根目录直接调用。
