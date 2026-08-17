# 标准库链接模型：域库（`.lib` / 可选 `.dll`）与增量编译

> **状态**：方案定案文档（**尚未落地**）。目标：**编译效率优先**。  
> **受众**：改 `layout_emit` / `compile.py` / `build*.bat` / umbrella 的维护者。  
> **相关**：[参考手册 §链接模型](./参考手册.md)（现行 header-only）、[编码规范](./编码规范.md)、[codegen-templates.md](./codegen-templates.md)、[c-ffi-pyi.md](./c-ffi-pyi.md)。

---

## 1. 问题

现行测试/示例链接模型：

```text
test_foo.cpp
  └─ #include "py2cpp/minimal.h"
        └─ 大量 py2cpp/**/*.h → #include "*.inl"
              └─ 非模板 + 模板实现一并编进每个 exe
```

后果：

| 现象 | 原因 |
|------|------|
| 改一个小测例也「像全量编译」 | 每个 exe TU 重新编译整份标准库 `.inl` |
| `build_all` 墙钟时间随用例数近似线性放大 | N 个 exe × 同一份 runtime 实现 |
| `py2cpp.cpp` 几乎用不上 | 历史汇总 TU；与 `minimal.h` 同链会 **LNK2005** |

「编成 DLL」想解决的是：**稳定实现只编一次，测例只编自己的 TU + 链接**。  
这与 Unity「按程序集增量编译」同精神，**不是**「每个 `.py` / 每个生成文件一个 DLL」。

---

## 2. 目标与非目标

### 2.1 目标

1. **非模板**标准库实现进入 **若干静态库（`.lib`，首选）**；测例默认链这些库。  
2. **模板 / 必须头可见**的实现仍 **header-only**（`list` / `dict` / `str` / `Queue[T]` / `tuple` 等）。  
3. 按 **域（类似 Unity asmdef）** 切库，支持脏库重编，避免一改全库。  
4. 同一套库 TU 可后续产出 **`.dll` + import lib**（发布/多进程），不挡第一阶段。  
5. 保留可回滚路径：环境变量或开关切回纯 header-only（过渡期）。

### 2.2 非目标（明确不做）

| 项 | 说明 |
|----|------|
| 一文件一 DLL | 导出面、循环依赖、启动成本均不可接受 |
| 把全部模板搬进 DLL | C++ 无稳定「跨 DLL 模板 ABI」；需显式实例化白名单，成本高、收益窄 |
| 用 STL 容器换链接模型 | 与编码规范「不链接 STL 容器」冲突 |
| 手改 `generated/` 作为真相源 | 仍由译器生成 `.h` / `.inl` / `.cpp` |

---

## 3. 目标架构

```text
                    ┌──────────────────────────────────────┐
  minimal.h         │ 声明聚合 + 仅 header_only 模块的 .inl   │
                    │ （模板 / 必须可见定义）                 │
                    └──────────────────────────────────────┘
                                      │  #include（测例）
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
  py2cpp_core.lib              py2cpp_io.lib              py2cpp_concur.lib
  （非模板 builtins、            （file/path/@native 叶子、   （Thread/Lock/Event/
   operators 非模板重载、         TextIO 非模板…）             Future/Pool 非模板；
   refcount…）                                                Queue[T] 仍 header）
         │                            │                            │
         └──────────────┬─────────────┴─────────────┬──────────────┘
                        ▼                           ▼
                 py2cpp_sql.lib              （可选）sqlite3.obj
                 + third_party/sqlite3.c
                        │
                        ▼
              test_foo.cpp  ──link──►  test_foo.exe
              （只编译用户 TU + 链上列 lib）
```

**LNK2005 铁律**：某一非模板 `.inl` 的实现体，只能出现在 **恰好一个** 库 TU 中；测例 **不得** 再 `#include` 该实现 `.inl`。

---

## 4. 模块分类

在 `src/constant`（或等价表）为每个 `STDLIB_REL_PATHS` 模块标注：

| 类别 | 含义 | `.h` | 实现放置 |
|------|------|------|----------|
| **`header_only`** | 含模板类 / 定义必须对用户 TU 可见 | 声明 + 尾 `#include ".inl"` | 仅 `.inl`（现状） |
| **`library`** | 非模板自由函数与类方法可进库 | **仅声明** | `.inl` 由 **模块 `.cpp`** 单次 `#include`，链进 `.lib` |

判定启发式（落地时写成显式表，勿纯猜）：

- 模块内存在 **带类型参数的类**（`list`、`dict`、`Queue`…）→ 默认 `header_only`（整模块或拆「模板类 header / 非模板 companion library」——第一版整模块 header_only 更简单）。  
- 无模板、以 `@native` 叶子 + 普通类为主（`concur/thread` 中非 `Queue` 部分、`system/time`、`io/file`…）→ `library`。  
- `operators`：模板重载留头；`pow(PyInt,…)` 等非模板重载可进 `core` 库（若拆文件有成本，第一版可整份 operators 暂留 header）。

### 4.1 第一刀域库划分（P2）

| 产物 | 大致模块 / 内容 | 备注 |
|------|-----------------|------|
| `py2cpp_core.lib` | builtins 非模板、`refcount`、小工具、适合进库的 operators 非模板部分 | 几乎每个测例都链 |
| `py2cpp_io.lib` | `io/file`、path 叶子、`py_open` 等 | 重叶子 |
| `py2cpp_concur.lib` | Thread / Lock / RLock / Condition / Event / Semaphore / Barrier / Future / ThreadPool / `atomic` 非模板；**`Queue[T]` 不进库** | 实现量大 |
| `py2cpp_sql.lib` | `sql/sqlite` 包装 + 链 `third_party/sqlite/sqlite3.c` | 已独立 |
| （暂缓） | `text` / `ui` / `web` / `serde` 等模板占比高的域 | P2 之后按需再拆 |

P1 可先落 **单一胖库** `py2cpp_runtime.lib`（上述 library 模块全进一个 `.lib`），再拆域。

### 4.2 用户代码（可选后续）

用户包可按目录成 `myapp.lib`（多 `.py` → 多 `.cpp` → 一库），主程序只编入口 TU。与标准库域库同一套 `compile.py` 规则即可扩展，**不**纳入 P0–P2 必做。

---

## 5. 生成物与译器改动

### 5.1 `library` 模块

| 文件 | 内容 |
|------|------|
| `generated/runtime/py2cpp/<path>.h` | 类/函数声明；**不**在头尾 include 实现 `.inl` |
| `generated/runtime/py2cpp/<path>.inl` | 实现体（与现相同，可含 templates 注入） |
| `generated/runtime/py2cpp/<path>.cpp` | **新建**：`#include "py2cpp/<path>.inl"`（或相对路径约定），作为库 TU |

### 5.2 `header_only` 模块

维持现状：`.h` 在合适位置 `#include` 同模块 `.inl`（模板实例化可见）。

### 5.3 `minimal.h` / umbrella

- 继续 `#include` 各模块 **`.h`**。  
- 对 `library` 模块：**禁止** 再把实现 `.inl` 拉进 umbrella 路径（否则测例又内联一份 → LNK2005 或失去增量收益）。  
- 模板模块行为不变。

### 5.4 关键代码路径（落地时改）

| 区域 | 职责 |
|------|------|
| `src/constant/…` | 模块 → `header_only` / `library`；域 → 库名映射 |
| `src/emit/layout_emit.py` | 按类别决定是否在 `.h` 尾 include `.inl`；写出库用 `.cpp` |
| `src/codegen/umbrella_gen.py` | umbrella 只聚合声明头；库列表元数据可写旁路文件供 `compile.py` 读 |
| `src/compile.py` | 编 `.lib`；测例链路追加 `.lib`；sqlite 仍按需 |
| `scripts/build.bat` / `build_all.bat` / `_bootstrap_runtime.bat` | bootstrap 后编库；mtime 跳过；脏库重编 |

---

## 6. 编译与链接（MSVC 优先）

### 6.1 编库（示意）

```bat
REM 每个 library 模块一个 obj，再 lib 合并（或按域分批）
cl /c /EHsc /std:c++14 /utf-8 /I generated\runtime ^
  generated\runtime\py2cpp\concur\thread.cpp ^
  /Fo:generated\runtime\obj\concur_thread.obj
lib /OUT:generated\runtime\lib\py2cpp_concur.lib generated\runtime\obj\concur_*.obj
```

### 6.2 编测例（示意）

```bat
cl /EHsc /std:c++14 /utf-8 /I generated\runtime ^
  generated\test\concur\test_thread.cpp ^
  /Fe:generated\test\concur\test_thread.exe ^
  /link generated\runtime\lib\py2cpp_core.lib ^
        generated\runtime\lib\py2cpp_concur.lib
```

依赖闭包：测例 import 闭包触及的域库都要链上（可由译器写 `*.link.json` 或粗粒度「测试默认链 core+io+concur+sql」起步）。

### 6.3 可选 DLL（P3）

- 同一批 `.obj`：`cl /LD … /Fe:py2cpp_concur.dll` + 生成 `.lib`（import）。  
- 符号：`PY2CPP_API`（`dllexport` / `dllimport`）挂在 **非模板** 导出声明上；模板类 **不** 走导出。  
- 开发迭代默认仍用 **静态 `.lib`**（无 DLL 搜索路径与 CRT 一致性负担）。

---

## 7. 分阶段落地

### P0 — 不改生成模型，立刻见效

| 项 | 说明 |
|----|------|
| mtime 跳过 | `build.bat`：源 `.py`、已生成 `.cpp`、依赖的 runtime 头/库未变 → 跳过该 exe |
| 可选 PCH | MSVC `/Yc`/`/Yu` 对 `minimal.h`（或瘦声明伞头） |

**验收**：连续两次同 pattern `build.bat`，第二次明显更快或跳过。

### P1 — 胖库 `py2cpp_runtime.lib`

| 项 | 说明 |
|----|------|
| 标注 `library` 模块 | 显式表 |
| 生成模块 `.cpp` | `#include` 对应 `.inl` |
| `.h` 不再拉实现 inl | 仅 `library` |
| bootstrap 后编胖库 | 测例默认链接 |
| 开关 | 如 `PY2CPP_HEADER_ONLY=1` 恢复旧路径（过渡） |

**验收**：

1. `build.bat concur/test_thread`（或一组代表测例）全绿。  
2. 只改 `test/.../test_*.py` 时，不重编胖库（或库 mtime 不变），测例 TU 编译时间明显下降。  
3. 改某一 `library` 模块 Python 源 → 重编库 + 重链相关 exe，**不必**每个 exe 重编译整份旧 inl。

### P2 — 按域拆库

按 §4.1 拆 `core` / `io` / `concur` / `sql`；`build.bat` 只重编脏域库。

**验收**：改 `concur/thread.py` 只触达 `py2cpp_concur.lib` + 依赖它的 exe。

### P3 — 可选 DLL

同 TU 出 DLL；文档补充部署（旁路 DLL、`PATH`、`/MD` 一致）。**非编译效率主路径。**

---

## 8. 预期收益与边界

| 场景 | 预期 |
|------|------|
| 改用户测例 | 主要编测例 TU + 链接（秒级～十余秒，视机器） |
| 改 `library` 标准库模块 | 重编对应 `.lib` + 重链，而非 N×全量 inl |
| 改 `header_only` 模板（`list`/`str`…） | 仍可能大面积重编（头依赖未变） |
| `build_all` 冷启动 | 仍要编齐库 + 各 exe；热路径与增量改测例受益最大 |

---

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LNK2005（inl 进库又进测例） | umbrella / `.h` 对 `library` 禁止 include 实现 inl；单测检查生成头 |
| 漏链库 | 粗粒度默认全链域库，或生成 link 清单 |
| 模板误标 `library` | 分类表 code review + 编译失败即改回 `header_only` |
| MSVC 与 clang 差异 | 先 Windows `cl`；其它编译器 P1 后再接 |
| 过渡痛苦 | `PY2CPP_HEADER_ONLY` 回滚；文档标明默认模式 |

---

## 10. 与现行文档的关系

| 文档 | 关系 |
|------|------|
| [参考手册](./参考手册.md)「链接模型（测试）」 | **现行**为 header-only；落地后该节改为「默认链域库 + 模板仍 header」，并链到本文 |
| [codegen-templates.md](./codegen-templates.md) | `@native` / `+*.inl` 注入目标仍是模块 `.inl`；库 TU 只是「谁 include 这份 inl」 |
| [c-ffi-pyi.md](./c-ffi-pyi.md) | FFI 空 allowlist 仍为 `#include <c_header>` 中转；sqlite glue 可进 `py2cpp_sql.lib` |

---

## 11. 验收清单（落地 PR 用）

```text
[ ] 模块分类表已入库（header_only / library + 域）
[ ] library 模块：.h 无实现 inl；存在 .cpp 单次 include .inl
[ ] minimal.h / umbrella 不把 library 实现 inl 拉进测例
[ ] bootstrap 产出 .lib（P1 胖库或 P2 域库）
[ ] compile.py / build.bat 测例默认链接；HEADER_ONLY 可回滚
[ ] P0 mtime 跳过可用
[ ] 代表测例（containers / path / thread / sqlite）MSVC 全绿
[ ] 参考手册链接模型节已更新并指向本文
[ ] 未手改 generated/ 作为提交真相源
```

---

## 12. 决议摘要

| 项 | 决议 |
|----|------|
| 产物优先级 | **`.lib` 优先**；DLL 可选（P3） |
| 切分粒度 | **按域**，禁止一文件一 DLL |
| 模板 | **留 header-only** |
| 实施顺序 | **P0 → P1 胖库 → P2 域库 → P3 DLL** |
| 效率优先 | 是；发布形态不挡 P1/P2 |
