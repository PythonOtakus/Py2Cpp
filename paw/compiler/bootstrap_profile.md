# Bootstrap profile（P4 / P5）

编译器实现源码必须可被 seed（C0 / 现有 Py2Cpp）翻译。更新 2026-11-01。

## 允许

- 模块级 `import` / `from … import`（静态可解析）；`__all__` 导出表可保留为 opaque
- Paw 声明：`class` / `def` / `enum` / `type enum` / `record` / `union` / `ref class` / `final class` / `frozen` / `ordered`
- `delegate Name[T](...) -> R`（无体）；`native def` / `native class`（方法无体、类保留体）
- 类型：裸箭头 `(A)->R` / `T->R`（Function）；`Callable[arrow]`（PyCallable）；`T[:]`
- 方法修饰：`override def` / `virtual def` / `static def` / `native def` 等；保留装饰器：`@copyable` / `@immutable` / `@native_name` 等（规范「保持」项）
- 显式注解、`list`/`dict`、`for`/`while`/`if`/`match`（已支持子集）；`self.x: T = v` 注解赋值
- `raise` / `return` / `pass` / `...` 存根

## 禁止（须改写或待特性）

- `@override` / `@virtual` / `@abstract` / `@final` / `@enum` / `@dataclass` / `@refcount` / `@staticmethod` / `@delegate` / `@native`（非 `@native_name`）
- `Function[[…], R]` / `Callable[[…], R]`（改用箭头表面）
- `getattr` / `setattr` / `hasattr` 动态协议
- `exec` / `eval` / 任意 Python callable 作模板 helper
- `Options(**dict)` 式异构 kwargs
- `x in (a, b, c)` 若目标后端拒绝则改 `==` 链或显式集合
- 逃逸闭包、返回局部 lambda（未实现前）

## 迁移顺序

1. `compiler/py/frontend` 保持本 profile，用 C0 编译为 C1 组件
2. 语义 / emit / 模板 helper 逐模块迁入后仍遵守本表
3. seed 已用 Paw 表面语法；后续闭环对同一 `*.paw` 语料做 C1→C2→C3
4. P5：已删 `materialize_ast`；`ast_from_mid` 覆盖 stdlib/test/seed → passes 迁 MidIR
