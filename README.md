# Py2Cpp

将受限子集的 Python 3 源码静态翻译为 C++11 可执行程序（标准库亦用 Python 描述并一并翻译，不依赖 STL）。

## 快速开始

```bash
python main.py examples/example.py -o generated -c --compiler cl
build_example.bat
generated\examples\example.exe
```

## 文档

| 文档 | 内容 |
|------|------|
| **[docs/参考手册.md](docs/参考手册.md)** | 架构、类型系统、`import` / 命名空间、`with` / `io`（`open`→`py_open`）、`@protocol` / `protocol_traits.h`、运算符与内置、标准库、构建与排错 |
| **[docs/编码规范.md](docs/编码规范.md)** | 标准库写法（`new` / `Self`）、生成器、协程、`with`、`io`、`import` 测试范本、避免手写 dunder |
| **[docs/c-ffi-pyi.md](docs/c-ffi-pyi.md)** | 第三方 C 头 → `ffi/**/*.pyi`（`Pyi_*`、glue、命名污染） |

### 常用构建

```bat
build_example.bat
build_all.bat
build.bat PATTERN [...]
run.bat PATTERN [...]
build_fail.bat
build_protocol.bat
ffi.bat third_party\sqlite\sqlite3.h
```

## 仓库结构

| 路径 | 说明 |
|------|------|
| `main.py` | CLI 入口 |
| `src/` | Python→C++ 翻译器 |
| `py2cpp/` | 标准库 Python 描述（域布局：`core/`、`util/`、`text/`、`io/` 等；译入 `generated/runtime/py2cpp/`） |
| `ffi/` | 第三方 C FFI `.pyi`（`ffi.bat` 生成，勿手改；译入 `generated/runtime/ffi/`） |
| `test/` | 集成测试（按域：`util/`、`text/`、`io/`、`sql/`、`web/`、`ui/`、`lang/`、`fail/`…） |
| `examples/` | 示例用户代码 |
| `generated/` | 默认翻译输出（勿手改）；测试 TU 通常只 `#include py2cpp/minimal.h`，**不**链 `py2cpp.cpp` |
| `docs/` | 项目文档 |
