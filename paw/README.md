# Paw / Py2Cpp

将受限子集的 Python 3 源码静态翻译为 C++11 可执行程序（标准库亦用 Python 描述并一并翻译，不依赖 STL）。

本目录为 monorepo 中的 **Paw** 工程根（与并列的 `../zeus` 相对）。

## 快速开始

```bash
python main.py examples/example.py -o generated -c --compiler cl
build.bat
generated\examples\example.exe
```

## 文档

| 文档 | 内容 |
|------|------|
| **[docs/参考手册.md](docs/参考手册.md)** | 架构、类型系统、标准库、构建与排错 |
| **[docs/编码规范.md](docs/编码规范.md)** | 标准库写法与测试范本 |
| **[docs/c-ffi-pyi.md](docs/c-ffi-pyi.md)** | 第三方 C 头 → `ffi/**/*.pyi` |
| **[docs/paw/](docs/paw/)** | 自举 / debridge / 语法清单 |

### 常用构建

```bat
build.bat PATTERN [...]
run.bat PATTERN [...]
build-all.bat
ffi.bat third_party\sqlite\sqlite3.h
```

## 目录

| 路径 | 说明 |
|------|------|
| `main.py` | CLI 入口 |
| `src/` | Python→C++ 翻译器 |
| `py2cpp/` | 标准库 Python 描述 |
| `compiler/` | Paw 自举前端 / Mid / stages |
| `ffi/` | 第三方 C FFI `.pyi` |
| `test/` | 集成测试 |
| `examples/` | 示例 |
| `generated/` | 默认翻译输出（勿手改） |
| `docs/` | 项目文档 |
