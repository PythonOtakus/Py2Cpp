# compiler/py/analysis — TypeNode / 符号表迁入（N3）

目标：去掉宿主 `src/analysis/type_node.py` 对 Python `Enum` / `dataclass` 运行时的硬依赖，使类型 IR 可被 bootstrap profile 编译。

| 现状（`src/analysis/type_node.py`） | 迁入步骤 |
|---|---|
| `TypeKind(Enum)` | 改为整型常量或 `@enum` |
| `@dataclass(frozen=True) TypeNode` | 改为普通 `@copyable` / 手写相等，或保留 dataclass 直至 C1 |
| 字符串反解析 | 优先 `TypeId` / MidIR 类型节点 |

Passes 契约见 [../sema/pass_bridge.md](../sema/pass_bridge.md)。生产路径已提供 `ParsedModule.mid` + `ast_from_mid`；**P5 已删** span materialize；下一步 passes 直接读 MidIR。
