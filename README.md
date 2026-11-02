# Py2Cpp Monorepo

根目录仅两个代码子树：

| 目录 | 说明 |
|------|------|
| **[paw/](paw/)** | Py2Cpp / Paw 译器、标准库、测试与自举（原仓库主体） |
| **[zeus/](zeus/)** | 基于 Paw 的轻量 3D 引擎（GLFW + OpenGL） |

## 快速开始（Paw）

```bat
cd paw
python main.py examples/example.py -o generated -c --compiler cl
build.bat
```

文档见 [paw/docs/参考手册.md](paw/docs/参考手册.md)、[paw/docs/编码规范.md](paw/docs/编码规范.md)。

## Zeus

```bat
zeus\build.bat
zeus\demo.bat
```

详见 [zeus/README.md](zeus/README.md)。Zeus 通过 `..\paw` 调用译器与 runtime。
