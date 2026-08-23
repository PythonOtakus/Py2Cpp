# 回归测试报告（2026-08-23）

本次回归覆盖近期译器改动：**`__py2cpp_*` 临时变量命名统一**、**`return new(kw=…)` 脱糖**、**VarStack 逻辑栈 `__py2cpp_vs_*` 命名对齐**。

| 项 | 值 |
|----|-----|
| 环境 | Windows 10，VS 2022 Community，`python 3.13` |
| 工作目录 | 仓库根 `Py2Cpp/` |
| Bootstrap | `python main.py py2cpp\__init__.py -o generated --no-main` |
| 全量编译 | `build-all.bat`（`scripts\parallel_build.py`，16 路并行） |
| 全量运行 | `run.bat *` |
| 译器单测（抽样） | `pytest src/tests/test_strict_style.py src/tests/test_kwargs_return_new.py` |

原始日志：`generated\.build_logs\build_all_latest.log`、`generated\.build_logs\run_all_latest.log`。

---

## 1. 汇总

| 阶段 | 总数 | 通过 | 失败 | 耗时（约） |
|------|------|------|------|------------|
| Bootstrap | 1 | 1 | 0 | 6 min |
| `build-all.bat` 编译 | 148 | 130 | 18 | 28.5 min |
| `run.bat *` 运行 | 148 | 124 | 24 | 29 s |
| `pytest` strict_style + kwargs_return_new | 266 | 265 | 1 | 62 min |

说明：`run` 失败 24 项中 **18 项无 exe**（与编译失败一致）；**6 项** 已编译但运行时失败。

---

## 2. 与本次改动相关的通过项

以下用例验证 **`return new(kw=…)`**、**`__py2cpp_opts*`**、**`__py2cpp_with_*`** 等命名与生成逻辑，**编译与运行均通过**：

| 用例 | 编译 | 运行 |
|------|------|------|
| `test/lang/test_kwargs_options.py` | OK | OK |
| `test/concur/test_task.py` | OK | OK |
| `test/web/test_openai.py` | OK | OK |
| `test/ui/test_widget.py` | OK | OK |
| `test/ui/test_flow.py` | OK | OK |

译器单测（快速抽样，非全量 strict_style）：

| 命令 | 结果 |
|------|------|
| `pytest src/tests/test_patterns.py src/tests/test_kwargs_return_new.py src/tests/test_try_emit.py src/tests/test_property_receiver.py` | 25 passed |
| `pytest src/tests/test_varstack.py src/tests/test_expand_iter_fields_loops.py` | 14 passed |

---

## 3. `build-all.bat` 编译失败（18）

| 用例 | 典型 MSVC / 译器错误（摘要） |
|------|------------------------------|
| `test/alg/test_chunk_deque.py` | `chunk_deque.inl`：`_block_size` 非成员、`__reversed__` / `splice` 生成语法错误（`C2059`/`C2440`） |
| `test/design/test_ecs.py` | `ecs.inl`：`PyECSComponentTableQuery` 初始化列表与指针形参不匹配（`C2440`） |
| `test/lang/test_build.py` | `viaBuild` 未声明（`build` 表达式生成） |
| `test/lang/test_final.py` | （见 `build_all_latest.log`） |
| `test/lang/test_proxy.py` | （见日志） |
| `test/lang/test_selector.py` | （见日志） |
| `test/lang/test_selector_post.py` | （见日志） |
| `test/lang/test_try.py` | `ExcTypeUnion` 非 `exceptions` 成员；`__py2cpp_exc_kinds*` 静态表类型未解析 |
| `test/lang/test_type_if.py` | `PyListElemOf` 未声明；`type if` 生成头/体不一致 |
| `test/lang/test_type_base.py` | （见日志） |
| `test/lang/test_varstack.py` | 泛型 mixin `lerpPair`：`Scalar` 未声明（`C2065`），与 `__py2cpp_vs_*` 命名无关 |
| `test/math/test_cmath.py` | （见日志） |
| `test/math/test_stat.py` | （见日志） |
| `test/math/test_linalg.py` | （见日志） |
| `test/serde/test_json.py` | `@serializable` 类型无默认构造（`C2512`） |
| `test/serde/test_json_document.py` | 同上 `PyUser` / `PyTeam` / `PyOrg` 默认构造 |
| `test/spatial/test_transform.py` | （见日志） |
| `test/util/test_dict.py` | `dict.inl`：`PyFrozenDictKeyIterator` 无法接受 `PyFrozenDict*`（`C2440`） |

---

## 4. `run.bat *` 运行失败

### 4.1 无 exe（18，与 §3 一致）

`alg/test_chunk_deque`、`design/test_ecs`、`lang/test_build`、`lang/test_final`、`lang/test_proxy`、`lang/test_selector`、`lang/test_selector_post`、`lang/test_try`、`lang/test_type_base`、`lang/test_type_if`、`lang/test_varstack`、`math/test_cmath`、`math/test_linalg`、`math/test_stat`、`serde/test_json`、`serde/test_json_document`、`spatial/test_transform`、`util/test_dict`。

### 4.2 有 exe 但运行失败（6）

| 用例 | 退出码 | 说明 |
|------|--------|------|
| `test/concur/test_process.py` | `-1073740791` (`0xC0000409`) | 栈缓冲区溢出；建议 `--debug` + `dbg.log` |
| `test/console/test_render.py` | `-1073740791` | 同上 |
| `test/math/test_math.py` | `1` | unittest 断言失败 |
| `test/spatial/test_color.py` | `1` | unittest 断言失败 |
| `test/spatial/test_game_math.py` | `1` | unittest 断言失败 |
| `test/util/test_memory.py` | `1` | `MemoryAppendCharsTests` 断言失败 |

---

## 5. 译器单测 `pytest`（strict_style + kwargs_return_new）

```
265 passed, 1 failed
```

| 失败用例 | 原因 |
|----------|------|
| `StrictStyleTests::test_s0310_allows_new_temp_with_mutation` | 期望对 `p = new(); p.x = 1; return p` 报 **S0311**，实际未抛出 `TranslationError`（`new()` + 字段赋值 + `return` 路径未纳入 S0311） |

`test_kwargs_return_new.py` 全部通过。

---

## 6. 后续建议（按优先级）

1. **S0311**：补全 `new()` → 改字段 → `return` 的严格风格检测（修复 §5 失败单测）。
2. **`test/lang/test_try`**：`ExcTypeUnion` / `except*` 生成与 runtime 头文件对齐。
3. **`test/lang/test_varstack`**：泛型 mixin 中 `Scalar` 注解在 VarStack 展开后的 C++ 类型绑定。
4. **运行时崩溃**：`concur/test_process`、`console/test_render` 优先 `build.bat … --debug` 定位。
5. **标准库生成物**：`chunk_deque`、`dict`、`ecs`、`serde/json` 等失败项按根因修 `py2cpp/` 或模板，勿手改 `generated/`。

---

## 7. 复现命令

```bat
python main.py py2cpp\__init__.py -o generated --no-main
build-all.bat
run.bat *
pytest src/tests/test_strict_style.py src/tests/test_kwargs_return_new.py -q
```
