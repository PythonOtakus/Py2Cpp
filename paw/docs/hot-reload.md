# 代码热更（进程内卸装 DLL）

> **状态**：**方案已定，未实现**（后续另开落地 PR）。  
> **受众**：译器链接模型、宿主 exe、用户工程 DLL 边界的维护者。  
> **相关**：[runtime-libs.md](./runtime-libs.md)（编译效率：`.lib` / 可选 **P3 链接期 DLL**）、[参考手册 §链接模型](./参考手册.md)、[zeus-engine.md Phase 5](../zeus/docs/zeus-engine.md#phase-5--插件--mcp)。

本文是 **进程内代码热更** 的单一真相源。它与「测例少编译」不是同一条线。

---

## 1. 为何不能 `reload` 一份 `.py`

Py2Cpp 把受限 Python **静态**译成 C++11 再链接。进程里 **没有** CPython 解释器，不能 `importlib.reload`。

运行中要换逻辑，只能：**把可替换代码编成可卸载映像，宿主 `FreeLibrary` 后再 `LoadLibrary`。**

---

## 2. 三种「热」不要混

| 形态 | 含义 | 状态 |
|------|------|------|
| **A. 快迭代** | 改 `.py` → 少翻译、少编译 → **重启 exe** | ✅ 已有：P0 stamp、P1 胖库、P1.5 叶子增量 bootstrap（改一叶子 `.py` 目标 &lt;30s） |
| **B. 进程内代码热更** | 宿主不退出，卸/装 **业务 DLL** | 📋 本文方案；**未实现** |
| **C. 数据热更** | 只重载场景 / PyML / JSON，代码不变 | 与代码热更无关；资源管线可单独做 |

下文只谈 **B**。

[runtime-libs.md **P3**](./runtime-libs.md#63-可选-dllp3链接期) 是同一批 `.obj` 再出 `py2cpp_*.dll` + **链接期** import lib，解决「实现编一次、多 exe 去链」，**卸不掉**，**不是**热更。热更要运行时 `LoadLibrary` + **函数表**，不要 `dllimport` 把符号钉进宿主。

---

## 3. 目标架构

```text
host.exe          永不卸载：消息循环、窗口、GLFW/OpenGL、线程、
                  py2cpp_runtime.lib / header-only 模板
    │  LoadLibrary / GetProcAddress / FreeLibrary
    ▼
game.dll          可替换：用户/关卡/玩法；只经 C 函数表与宿主通话
```

粒度是 **一个业务程序集（一份 DLL）**，不是每个 `.py` 一份 DLL（与 [runtime-libs.md §2.2](./runtime-libs.md#22-非目标明确不做) 一致）。

### 3.1 导出面（建议）

DLL 只导出 **非模板、C 布局** 入口，例如：

| 符号 | 职责 |
|------|------|
| `on_load(HostApi*)` | 注册 tick / 命令；禁止把宿主对象的 C++ 虚表存进 DLL 静态区后跨卸载使用 |
| `on_tick(dt)` / `on_command(...)` | 帧逻辑；指针只在本次映像寿命内有效 |
| `on_unload()` | 停线程、解注册、释放 DLL 堆上对象；返回后宿主才 `FreeLibrary` |

`HostApi` 是宿主填好的 **函数指针表**（C ABI），不是把 `list[T]` / `PyStr` 等模板类型写进导出签名。

Python 侧：用户模块写规范 Python；译器或薄 `@native` 叶子只负责把上述三个符号编进 `/LD` DLL。业务逻辑仍在 Python 组合层。

### 3.2 热更步骤（开发期）

1. 用户改业务 `.py`，增量翻译 + 只链 **game.dll**（宿主 exe 不重编）。  
2. 宿主收到「映像已就绪」（文件监视或手动）：调 `on_unload` → `FreeLibrary` → 换文件（Windows 常需改名/副本来避开文件锁）→ `LoadLibrary` → `on_load`。  
3. 改 **标准库 / 译器 / `templates/` / FFI**：**重启宿主**。这些不在热更 DLL 里。

---

## 4. 硬约束

1. **模板留 header-only**（`list` / `dict` / `str` / `Queue[T]` / `tuple`…）。无稳定跨 DLL 模板 ABI；DLL 与 exe 各实例化一份，不能当同一类型热换。  
2. **禁止一文件一 DLL**。导出面、环依赖、启动成本不可接受。  
3. 热更 DLL **只**导出非模板 C 入口；不得把 `WndProc`、线程、单例、`function`/`delegate` 留在旧映像再卸载。  
4. **标准库自身不热更。** `py2cpp_runtime` 留在宿主。  
5. Windows 先行（`LoadLibraryW` / `FreeLibrary`）。POSIX `dlopen`/`dlclose` 另议。  
6. 与 **P2 域库 / P3 链接期 DLL** 解耦：热更是另一条产品线，不挡、也不依赖「测例链 `.lib`」先拆完。

---

## 5. 状态策略

卸载前堆上的业务对象会失效。两条路，落地时二选一（见 §8 待定）：

| 策略 | 行为 |
|------|------|
| **丢状态** | 开发期默认可接受：热更后场景回默认 / 重新 `on_load` |
| **序列化往返** | `on_unload` 前把宿主拥有的文档（`.zas` / `@serializable` JSON）导出，新 DLL `on_load` 再灌入 |

宿主持有的窗口、GL 上下文、文件句柄 **不**进 DLL，热更后继续用。

---

## 6. 与 Zeus 插件的关系

[Zeus Phase 5](../zeus/docs/zeus-engine.md#phase-5--插件--mcp)（插件 manifest、`on_load`/`on_unload`、MCP）**仍暂不做**。

若以后做插件，应 **复用本文的 DLL 寿命规则**（C 函数表、卸载顺序），不要再造第二套卸装协议。热更宿主不必等于编辑器插件系统：最小热更可以是「Editor 或 demo 作 host.exe + 一份 `jump.dll`」。

---

## 7. 暂不实现

| 项 | 说明 |
|----|------|
| 落地代码 | 译器 `/LD`、函数表、监视重载循环 — **后续 PR** |
| Live++ / MSVC `/hotpatch` | 不在本仓库发明函数级热补丁 |
| 模板类进 DLL | 见 §4 |
| 一文件一 DLL | 见 §4 |
| `py2cpp/` 标准库热更 | 改 runtime 仍重启 |
| 链接期 P3 `dllimport` 冒充热更 | 见 §2 |
| 完整 Zeus 插件 + MCP | 仍 Phase 5 暂不做 |

---

## 8. 待定（落地前再对齐）

| 点 | 候选 |
|----|------|
| 第一只宿主 | Zeus Editor / `zeus\demo.bat` / 普通 `UIApp` / 任意用户 exe |
| 热更范围 | 仅用户工程（`zeus/src`、业务包）— **推荐** |
| 状态 | 先丢状态，还是必须 `.zas` 往返 |
| 触发 | 手动快捷键 vs 监视 `game.dll` mtime |
| CRT | 宿主与 DLL 必须同一 `/MD`（或约定的同一运行库） |

---

## 9. 落地时建议改哪些文件（备忘，现不改）

| 层 | 路径 |
|----|------|
| 文档 | 本文；[参考手册](./参考手册.md) 链到本文；[runtime-libs.md](./runtime-libs.md) 标明 P3 ≠ 热更 |
| 编译 | `src/compile.py` / `build*.bat`：用户模块可选 `/LD` 出 DLL，宿主不静态链该 TU |
| 标准库 | 薄宿主 API（`LoadLibrary` 叶子走现有 `ffi/windows`，组合层纯 Python） |
| 示例 | 最小 `host.py` + `game.py` 测例：改 game 后不杀 host 即可换逻辑 |
| 测例 | 进程内：load → tick → unload → load 第二次；断言旧函数指针不可再用 |

未落地前 **禁止**手改 `generated/` 假装已有热更。
