# Paw / Py2Cpp

将受限子集的 Python 3 / Paw 源码静态翻译为 C++11。

本目录为 monorepo 中的语言产品根（并列 `../zeus`）。目录名均为小写。

## 快速开始

```bash
python main.py examples/example.py -o out -c --compiler cl
# 或：python -m cmd.paw examples/example.py -o out
build.bat
out\examples\example.exe
```

## 目录

| 路径 | 说明 |
|------|------|
| `cmd/paw/` | CLI（`python -m cmd.paw`） |
| `lib/paw/` | 标准库源（`from paw import *`） |
| `host/` | C0 宿主译器（自举完成前的生产路径） |
| `compiler/` | Paw 自举前端 / Mid / stages |
| `tests/` | 集成测试 |
| `examples/` | 示例 |
| `ffi/` | C FFI 声明 |
| `templates/` | 译器注入模板 |
| `tools/` | 构建与维护脚本（不进安装包） |
| `extensions/` | IDE 扩展 |
| `packaging/` | 安装前缀布局说明 |
| `include/` | 对外头文件安装位（预留） |
| `docs/` | 文档 |
| `out/` | 构建产物（勿手改、勿入库） |
| `third_party/` | 第三方 |

安装前缀约定见 [packaging/layout.md](packaging/layout.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [docs/参考手册.md](docs/参考手册.md) | 架构与排错 |
| [docs/编码规范.md](docs/编码规范.md) | 标准库写法 |
| [docs/paw/](docs/paw/) | 自举 / debridge |
