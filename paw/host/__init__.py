"""Paw 宿主译器（C0）：标准库在 ``lib/paw/``，输出默认 ``out/``。

目录
----
- ``lib/paw/``：标准库源（``from paw import *``）
- ``host/analysis/``：IR、模式、语义分析
- ``host/passes/``：装饰器 / 混入 / match 等 AST 展开
- ``host/codegen/``：f-string、内建 C++ 片段生成
- ``host/translator.py``：主翻译器
- ``host/compile.py``：可选 C++ 编译

公开 API
--------
- ``Translator``：翻译入口；用户脚本 → ``out/<源路径>/``，运行时 → ``out/runtime/``。
- ``compile_cpp``：可选编译生成的 ``.cpp``。
- ``GENERATED_DIR``：默认输出目录名（``"out"``）。
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
