"""AST 驱动的 C++ 生成：循环、调用、下标、字面量、类体/声明、推导式、f-string 等。

本目录模块均以 ``*_emit.py`` 命名（``layout_config_emit`` 等为共享常量/写盘辅助）。
``templates/**`` 展开与 runtime 固定产物在 ``src/codegen/``（``expand_py2cpp_template``、``*_gen.py``）。
"""
