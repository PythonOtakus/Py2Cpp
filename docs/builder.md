# Build DSL（`Type.build("…")`）

> **状态**：**F1 已实现**（``@dataclass`` / ``list[T]`` 内存图；``JsonDocument`` ⏳ 未做）  
> **与 `select` 分工**：``select`` 只读导航；``build`` 自顶向下构造对象图。

---

## 1. 入口

| 调用 | 返回类型 | 串形态 |
|------|----------|--------|
| ``Org.build("…")`` | ``Org`` | struct 根：字段段 |
| ``list[Team].build("…")`` | ``list[Team]`` | **必须** ``[:N] > …`` 起头 |

- 译期脱糖；**无** C++ ``build`` 成员（``TRANSLATOR_ONLY_METHODS``）。
- 类型由调用点推断；串内**不写**类型名。
- 未提及字段 → 与 ``new()`` 默认一致。

---

## 2. EBNF

```ebnf
build_spec   := struct_body | list_root

list_root    := "[:"
                count
                "]"
                index_bind?
                ">"
                struct_body

struct_body  := segment ( "," segment )*

segment      := assign
              | struct_descent
              | list_descent

assign       := ident "=" value

struct_descent
             := ident ">" struct_body

list_descent := ident "[:"
                count
                "]"
                index_bind?
                ">"
                struct_body

index_bind   := ":" ws? "$" ident

value        := string_lit | number_lit | bool_lit | "None"
              | index_ref
              | "{" expr "}"

index_ref    := "$" ident

count        := non_negative_integer
```

---

## 3. 语义要点

### 3.1 List 段 ``field[:N] > body``

- 精确构造 **N** 个元素；``body`` 为**单模板**，译期展开 N 次 ``new`` + 填字段 + ``append``。
- 首版**仅** ``[:N]``；**不支持** ``field[0] >`` 单下标。
- ``members[:0] >`` 合法（空 list）。

### 3.2 Struct 段 ``field > body``

- 进入非 list 字段，递归填 ``body``；无下标。

### 3.3 下标绑定 ``[:N]: $i > …``

- ``$i`` = 循环变量，范围 **0 .. N−1**（与 ``range(N)`` 一致）。
- 可用 ``score=$i``（字段须为 ``int``/``int64``）或 ``{prefix + str($i)}``。
- 内层 ``[:M]: $j >`` 可嵌套；外层 ``$i`` 仍可见。

### 3.4 赋值 ``value``

- 字符串须**引号**；数字 / ``True`` / ``False`` / ``None``；``{expr}`` 为 Py2Cpp 表达式。

---

## 4. 示例

```python
org: Org = Org.build(
  'teams[:1] > name="alpha", min_score=5, '
  'members[:2] > score=10,name="amy"'
)

teams: list[Team] = list[Team].build('[:2]: $i > name={str($i)}')

org: Org = Org.build(
  'teams[:3]: $i > name={prefix + str($i)}, min_score=$i'
)
```

---

## 5. 实现位置

| 组件 | 路径 |
|------|------|
| 解析 | ``src/passes/build_parse.py`` |
| 类型 walk | ``src/analysis/build_types.py`` |
| 内联 emit | ``src/emit/build_emit.py`` |
| 触发 | ``call_emit.try_emit_build_call``、``visit_AnnAssign`` |
| 单测 | ``src/tests/test_build_*.py`` |
| 集成测 | ``test/lang/test_build.py`` |

---

## 6. 首版不做

- ``field[0] >`` 单下标 list 段  
- 串内写类型名、``build[Org](…)`` 全局形式  
- ``JsonDocument`` / 非 dataclass backend  
- 同一 ``[:N] >`` 内 N 个**不同**模板（须用 ``$i`` 或手写 ``append``）
