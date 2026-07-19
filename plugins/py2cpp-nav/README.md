# Py2Cpp Navigation（VS Code）

在 **Python 源**与 **`generated/` 生成 C++** 之间提供符号级 **Go to Definition**（F12 / Ctrl+点击）双向跳转：

| 方向 | 典型场景 |
|------|----------|
| **Python → C++** | `class Foo` / `def bar` / 字段 → 对应 `.h` 声明或 `.inl`/`.cpp` 实现 |
| **C++ → Python** | `PyList::append`、`class ChrOrdTests` → `py2cpp/util/list.py` 或 `test/.../*.py` |

覆盖范围（索引 **v3**）：类 / 方法 / 字段 / `@property`·`@staticproperty`（含 setter）/ 模块函数 / `type` 别名 / `@enum` 成员 / `@union` `@variant` / `@delegate` / `@protocol`（仅 Python）/ `@mixin`（方法可附宿主实现）。不含函数体内逐行映射。标准库 `py2cpp/**` 与 `test/**`、`examples/**` 均支持；索引由译器写入，扩展只读 JSON。

完整方案（格式、覆盖矩阵、已决议开放问题）：[`docs/py2cpp-nav.md`](../../docs/py2cpp-nav.md)。

## 依赖

- VS Code / Cursor ≥ 1.85
- Python 3.10+（与 Py2Cpp 译器相同），仓库根可运行 `python main.py …`
- 工作区为 Py2Cpp 仓库根，或在设置中指定 `py2cpp-nav.repoRoot`
- 已至少翻译过一次目标模块（见下文「索引」）；全库标准库需 bootstrap

## 安装

### 从源码打包（仅需 Python，无需 npm）

```bat
cd plugins\py2cpp-nav
package.bat
```

或仓库根：

```bat
pkg-nav.bat
```

`package.py` 按 `.vscodeignore` 收集 `out/`、`package.json` 等，生成 `py2cpp-nav-0.1.0.vsix`。在 VS Code / Cursor 中选择 **Extensions → … → Install from VSIX…** 安装。

## 索引

翻译结束时，译器在 **`generated/.cache/nav/`** 写入/合并导航索引（勿手改）：

| 文件 | 内容 |
|------|------|
| `manifest.json` | 全库模块清单、各 shard 路径、`.h`/`.inl`/`.cpp` 路径 |
| `modules/<module_path>.json` | 符号表（路径与 Python 模块一致，如 `modules/py2cpp/util/list.json`） |

**首次使用 / 全量标准库跳转**（bootstrap，会更新大量 runtime shard）：

```bat
python main.py py2cpp\__init__.py -o generated --no-main
```

**单个测试/模块**（扩展保存时也会自动跑，见设置）：

```bat
python main.py test\concur\test_task.py -o generated
```

扩展监视 `generated/.cache/nav/**` 变更并自动 reload；保存 `py2cpp/`、`test/`、`examples/` 下的 `.py` 时默认防抖 1s 后调用 `main.py` 翻译当前文件并刷新索引。

## 使用

1. 安装扩展并重载窗口
2. 确保对应模块已翻译且 `generated/.cache/nav/manifest.json` 存在
3. 在 Python 或 `generated/**/*.h|cpp|inl` 上，光标置于类名/方法名/字段名，**F12** 或 **Ctrl+点击** 跳转
4. Python→C++ 默认优先 **实现**（`.inl` / 入口 `.cpp`），可在设置中改为声明（`.h`）或同时列出多个目标

未命中索引时不会拦截 clangd 等其它 C++ 定义 provider。

## 开发调试

1. 在 VS Code / Cursor 中打开 `plugins/py2cpp-nav`
2. 扩展源码为 **纯 JavaScript**（`out/*.js`），直接编辑即可，无需 TypeScript / npm 编译
3. 本目录 `package.json` 为 VS Code 扩展清单（非 Node 工程）；仓库根 `npm.autoDetect` 为 `off`，并已 `npm.exclude` 插件路径
4. 按 F5 启动 Extension Development Host
5. 在新窗口打开 Py2Cpp 仓库，打开 `test/` 或 `py2cpp/` 下文件验证跳转

打包：`python package.py` 或 `package.bat`（`package.json` 的 `scripts.package` 同义）。

## 命令

| 命令 | 说明 |
|------|------|
| **Py2Cpp: Translate Current File** | 对当前 `.py` 运行 `main.py` 并刷新导航索引 |
| **Py2Cpp: Rebuild Navigation Index** | 同上（需打开可翻译的 Python 源文件） |

## 设置

| 键 | 默认 | 说明 |
|----|------|------|
| `py2cpp-nav.pythonPath` | `python` | 运行 `main.py` 的 Python 可执行文件 |
| `py2cpp-nav.repoRoot` | （空） | 仓库根；空则自动查找含 `main.py` 的目录 |
| `py2cpp-nav.generatedDir` | `generated` | 生成物根目录（相对 `repoRoot`） |
| `py2cpp-nav.autoTranslate` | `onSave` | 保存 Python 时自动翻译；`off` 关闭 |
| `py2cpp-nav.translateDebounceMs` | `1000` | 自动翻译防抖（毫秒，≥200） |
| `py2cpp-nav.jumpPreference` | `implementation` | Python→C++：`implementation` / `declaration` / `both` |

`py2cpp/` 下模块翻译时扩展会附加 `--no-main`；`test/`、`examples/` 保留 `main()` 入口。

## 架构

```
out/extension.js  →  translateRunner.js  →  python main.py（仓库根）
                →  definitionProvider.js  →  indexStore.js
                                      ↓
                         generated/.cache/nav/*.json
                                      ↑
                         src/codegen/nav_index.py（译器写索引）
```

| 文件 | 作用 |
|------|------|
| `out/extension.js` | 激活、保存翻译调度、注册 DefinitionProvider |
| `out/translateRunner.js` | 调用 `main.py` 翻译当前模块 |
| `out/indexStore.js` | 加载 manifest 与 module shard |
| `out/definitionProvider.js` | Python ↔ C++ 符号解析与跳转 |
| `out/symbolParse.js` | 光标处符号/类上下文解析 |
| `out/util.js` | 仓库根探测、路径判定 |

## 范围与限制

- **含**：`generated/runtime` 标准库、`test/`、`examples/`、`py2cpp/` 用户可见符号
- **不含**：`templates/**`（请用 [py2cpp-template](../py2cpp-template/)）、函数体内任意行级映射、Rename/Reference
- 索引随翻译增量更新；未翻译过的模块无法跳转

译器索引实现见仓库根 `src/codegen/nav_index.py`。
