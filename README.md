# Py2Cpp Monorepo

根目录两个产品子树（小写目录名）：

| 目录 | 说明 |
|------|------|
| **[paw/](paw/)** | 语言 / 译器 / 标准库 / 自举 |
| **[zeus/](zeus/)** | 基于 Paw 的轻量 3D 引擎 |

## Paw

```bat
cd paw
python main.py examples/example.py -o out -c --compiler cl
build.bat
```

详见 [paw/README.md](paw/README.md)、[paw/packaging/layout.md](paw/packaging/layout.md)。

## Zeus

```bat
zeus\build.bat
```

详见 [zeus/README.md](zeus/README.md)。依赖 `..\paw` 的 CLI 与 `out/runtime`。
