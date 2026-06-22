"""py2cpp 集成测试包（``scripts/build_all.bat`` 递归 ``test/**/test_*.py``）。

目录与 ``py2cpp/<域>/`` 对齐：``test/<域>/test_<模块>.py`` 对应 ``py2cpp/<域>/<模块>.py``；
子包同理（如 ``test/io/file/test_file.py`` ↔ ``py2cpp/io/file/__init__.py``）。

| 目录 | 对应标准库 |
|------|------------|
| ``text/`` | ``py2cpp/text/`` |
| ``util/`` | ``py2cpp/util/``（含 ``pool``、``misc``） |
| ``io/`` | ``py2cpp/io/``（``test_io.py``） |
| ``io/file/`` | ``py2cpp/io/file/``、``io/file/path`` |
| ``system/`` | ``py2cpp/system/``（``time``、``datetime``） |
| ``serde/`` | ``py2cpp/serde/`` |
| ``core/`` | ``py2cpp/core/`` |
| ``design/`` | ``py2cpp/design/`` |
| ``alg/`` | ``py2cpp/alg/`` |
| ``math/`` | ``py2cpp/math/`` |
| ``numeric/`` | ``py2cpp/numeric/`` |
| ``ui/`` | ``py2cpp/ui/`` |
| ``concur/`` | ``py2cpp/concur/`` |
| ``misc/`` | 内建冒烟、字面量查表、全局 ``pow`` 等 |
| ``lang/`` | 语言特性 |
| ``import_tests/`` | ``import`` / 模块命名空间 |
| ``perf/`` | 性能基准（默认不进 ``build_all.bat``） |
| ``fail/`` | 负向编译（``build_fail.bat``） |
from py2cpp import *
