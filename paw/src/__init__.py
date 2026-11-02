"""py2cpp 包：Python 标准库描述 + Python→C++11 翻译器。

目录
----
- 仓库根 ``py2cpp/``：标准库 Python 描述（翻译为 ``generated/runtime/py2cpp/*.h``）
- ``analysis/``：IR、模式、语义分析
- ``passes/``：装饰器 / 混入 / match 等 AST 展开
- ``codegen/``：f-string、内建 C++ 片段生成
- ``translator.py``：主翻译器
- ``compile.py``：可选 C++ 编译

公开 API
--------
- ``Translator``：翻译入口类；用户脚本 → ``generated/<源路径>/``，运行时 → ``generated/runtime/``。
- ``compile_cpp``：可选地编译生成的 ``.cpp``（见 ``compile`` 子模块）。
- ``GENERATED_DIR``：默认输出目录名（``"generated"``）。
"""

from .compile import CompileResult, compile_cpp
from .translator import GENERATED_DIR, RUNTIME_OUTPUT_SUBDIR, Translator

__all__ = [
  "Translator",
  "GENERATED_DIR",
  "RUNTIME_OUTPUT_SUBDIR",
  "compile_cpp",
  "CompileResult",
]
