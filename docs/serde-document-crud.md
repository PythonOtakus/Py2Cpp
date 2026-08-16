# Serde `DocumentType`：部分访问与增删改查规范

> **状态**：P1 已落地（`JsonDocument` + **`JsonDocCursor` 懒节点** + 通用 **`__getattr__`/`set_field`** 派发）；非译期零成本 IIFE  
> **约束**：符合 [编码规范.md](./编码规范.md)；复用 `EncoderType`/`DecoderType`、`@serializable`；不引入 STL；**暂不支持动态路径**。

---

## 1. 目标

在 **不全量 `Json.loads` 建树** 的前提下，对持久化文档做 **查 / 增 / 改 / 删**，且：

1. **根类型 `T` 与全量 API 一致**（`Json.loads[T]` / `Json.load[T]` 同款 `T`）。
2. **字段链 / 下标写法与内存对象相同**（`doc.teams[0].name`，无 `get(path)`）。
3. **格式可扩展**：`DocumentType` 为 `@protocol`；JSON 首实现为 **`JsonDocument`**。
4. **全量读写命名与 `Json` 对齐**：`load()` / `dump()`（非 `materialize` / `snapshot`）。

---

## 2. 类型分层

```text
@protocol DocumentType          # 对外契约（无 C++ 类体）
       ↑ 结构实现
@JsonDocument[T]            # 具体类（JSON 后端；方法写在 json.py）
       ↓ __getattr__ / __getitem__
JsonDocCursor[T]            # 懒路径节点（持有 doc 指针 + steps）
       ↓
JsonDecoder + patch helper  # 格式相关（``json.py`` 纯 Python → ``json.inl``）
```

| 层 | 形态 | 说明 |
|----|------|------|
| **`DocumentType`** | `@protocol` | 仅 `...` 声明；供 `def f[D: DocumentType]` 约束；**不**作继承基类 |
| **`JsonDocument[T]`** | `@dataclass` + `@copyable` 具体类 | 唯一入口 `JsonDocument[T].open(path, mode)`（谁泛型谁传参）；持有 `text`/`dec`/dirty；`dump`/`commit`/`discard`/`__enter__` 等同模块实现 |
| **`JsonDocCursor[T]`** | `@dataclass` + `@copyable` | 懒节点：`__getattr__`/`__getitem__` 延长路径；`read_*`/`set_field`/`append`/`__delitem__` 调 ``json.py`` helper |

未来其它格式（示例）：

```text
YamlDocument[T]   # 平行 @dataclass + YamlDecoder backend，同样实现 DocumentType 方法集
```

同样实现 `DocumentType` 协议方法集，**不**扩展 `open_read` / `open_write` 等别名。

---

## 3. `DocumentType` 协议（唯一入口 + 与 Json 对称）

定义于 `py2cpp/serde/protocols.py`（与 `EncoderType` / `DecoderType` 并列）：

```python
@protocol
class DocumentType:
  """持久化文档的部分访问；具体实现如 ``JsonDocument``。"""

  @staticmethod
  def open[T](path: Path, mode: str = "r") -> Self: ...

  def load[T](self) -> T:
    """全量读入并解析为 ``T``（等价 ``Json.loads[T](全文)``）。"""
    ...

  def dump(self) -> str:
    """当前文档快照序列化为 ``str``（等价 ``Json.dumps`` 于当前视图）。"""
    ...

  def commit(self) -> None:
    """将 dirty 变更写回存储（原子替换）。"""
    ...

  def discard(self) -> None:
    """放弃未 ``commit`` 的内存变更。"""
    ...

  def __enter__(self) -> Self: ...

  def __exit__(self): ...
```

### 3.1 打开方式（仅此一种）

```python
from py2cpp.io.path import Path
from py2cpp.serde.json import JsonDocument

doc: JsonDocument[Org] = JsonDocument[Org].open(Path("org.json"), "r")
```

| 参数 | 语义 |
|------|------|
| `path` | `Path` 或 `str`（规范写法优先 `Path`） |
| `mode` | `"r"` 只读；`"r+"` 读写；`"w"` 截断写（与 `open` 子集一致，首版可实现 `r` / `r+`） |
| `T` | 根类型，与 `Json.loads[T]` / `Json.load[T]` **相同** |

**禁止**：`open_read` / `open_write` / `DocumentType.with_format(...)` 等第二入口。

### 3.2 `load` / `dump` 与全量 API 对照

| 全量（现有） | DocumentType | 语义 |
|--------------|----------|------|
| `Json.loads[T](s)` | `doc.load()` | 全量解析 → `T`（`doc` 已注解 `JsonDocument[T]`） |
| `Json.load[T](fp)` | `JsonDocument[T].open(path, "r").load()` | 读文件 + 全量 |
| `Json.dumps(obj)` | `doc.dump()` | 序列化当前内容 |
| `Json.dump(obj, fp)` | `doc.commit()` 或 `open(..., "w")` + 写 | 持久化 |

### 3.3 事务

```python
with JsonDocument[Org].open(path, "r+") as doc:
  doc.title = "acme"
  doc.teams[0].members.append(u)
# 正常 `__exit__` → `commit()`；异常 → `discard()`（不写回）
```

显式：

```python
doc.commit()
doc.discard()
```

---

## 4. 增删改查语法（Pythonic，无动态路径）

**暂不支持** `doc.get[V](["a", 0, "b"])` 及任意 runtime path。  
导航 **仅** 静态字段链 + 整型下标（由 `T` 的类型结构决定，译期可解析）。

已物化的 ``@dataclass`` / ``list`` 根对象可用 **`select("…")`** 按路径 **只读** 选取（译期内联，**恒** ``list[T]``）；单元素静态链 ``doc.teams[0].name`` 等价于 ``select`` 返回长度 1 的 ``list``。详规见 [selector.md](./selector.md)；``JsonDocument`` lazy 导航的 ``select`` backend 为后续 G2。

### 4.1 查（Read）

```python
with JsonDocument[Org].open(path) as doc:
  name: str = doc.teams[0].members[0].name   # 懒读，不建整棵 Org
  n: int = doc.teams[0].members[0].id
```

根为同质容器：

```python
doc: JsonDocument[list[int]] = JsonDocument[list[int]].open(path)
x: int = doc[42]
```

全量：

```python
org: Org = doc.load[Org]()
```

### 4.2 改（Update）

```python
doc.teams[0].members[0].name = "alice"
doc[42] = 99
```

`mode="r"` 时赋值：**编译期或运行期错误**（首版至少运行期 `OSError` / 专用异常）。

### 4.3 增（Create）

```python
doc.teams[0].members.append(new(id=3, name="eve"))
doc.meta = new(version=2)          # 对象新字段（patch 插入）
```

### 4.4 删（Delete）

```python
del doc.teams[0].members[1]
del doc.deprecated_field
```

增删改 **不** 引入 `doc.update` / `doc.remove` 等新动词；沿用赋值、`del`、`list.append` 等 Python 原生语句。

---

## 5. `JsonDocument`

### 5.1 模块位置

| 文件 | 内容 |
|------|------|
| `py2cpp/serde/protocols.py` | `@protocol DocumentType` |
| `py2cpp/serde/json.py` | `@dataclass JsonDocument[T]`、`JsonDocCursor[T]`、`JsonDocStepUnion` |
| `py2cpp/serde/json.py` | ``JsonDocument`` / ``JsonDocCursor`` navigate / patch / commit（纯 Python，译器生成 ``json.inl``） |
| `src/translator.py` | 通用 **`__getattr__` 派发**、`set_field` 赋值、`JsonDocCursor`→标量 **`read_*` 强制**（非 JSON 特判 pass） |

### 5.2 形态（规范 Python）

```python
@protocol
class DocumentType:
  ...

@copyable
@dataclass
class JsonDocument[T]:
  path: str
  mode: str
  text: str
  orig: str
  dec: JsonDecoder = new()
  writable: bool = False
  dirty: bool = False

  @staticmethod
  def open(path: str, mode: str = "r") -> Self: ...

  def load[T](self) -> T: ...
  def dump(self) -> str: ...
  def commit(self) -> None: ...
  def discard(self) -> None: ...
  def __enter__(self) -> Self: ...
  def __exit__(self) -> None: ...

  def __getattr__(self, name: str) -> JsonDocCursor[T]: ...
```

**写法约束**（编码规范）：

- 用户侧仍写 **`doc.teams[0].name`**；译器对未知字段走 **`__getattr__`/`__getitem__`**，运行时为轻量 **`JsonDocCursor`**（非译期 IIFE 零成本）。
- `JsonDocument`/`JsonDocCursor` 的 dunder 为协议面，由标准库声明 + `@native` 实现（非业务手写 dunder）。
- 辅助状态用 `@dataclass` 字段，默认值 `new()` 须有左侧注解。
- 无 STL；patch I/O 走 `io` C 层 + `io.file.replace`。

### 5.3 `JsonDocCursor[T]`（懒节点）

- **`JsonDocument.__getattr__(name)`** → 根 cursor（追加字段步）
- **`cursor[i]` / `cursor.field`** → 延长 `steps`
- **读**：`readStr()` / `readInt()` / `readBool()`（赋值/`assertEqual` 对标量时译器插入 `.read_*()`）
- **改**：`cursor.field = v` → **`set_field`**
- **删**：`del cursor[i]`
- **增**：`cursor.append(item)`（list 末级）

**静态路径限制**：路径步在运行期由 `steps` 记录；首版仍要求 **字面量字段名 + 整型下标**（与 P0 相同，不支持 `doc.data[key]` 动态键）。

---

## 6. 后端与复用

| 能力 | 复用 |
|------|------|
| 扫描 / 跳过 | `JsonDecoder.skipValue` / `skipField` / `tryMatchKey` |
| 读子树 | `load_*` / `User.deserialize(dec)` |
| 写片段 | `Json.dumps` / `JsonEncoder` / `util.memory.fastEncode` |
| 全量 `load()` | 现有 `Json.loads` 类型 if 链 |
| patch 提交 | ``json.py``：``Path.writeText`` + ``io.file.replace``（原子替换） |

首版存储假定：**紧凑 JSON**（`indent==0`、键无转义）；pretty / 乱序键 **回退** `load()` + 内存改 + `commit()` 整文件写（行为正确，性能不保证）。

---

## 7. 与 `Json.load` 委托的关系

当前 `Json.load[T](fp)` 为 `Json.loads[T](fp.read())`（一行委托）。

`JsonDocument` **独立**于 `Json.load`：

- 点查 / 增量：`JsonDocument[T].open(path, mode)`（**禁止** `JsonDocument.open[T](…)`）
- 全量一次：`doc.load()`（`doc: JsonDocument[T]`）或继续可用 `Json.load[T](fp)`（小文件、测试）

二者 **`load[T]()` 返回类型相同**（`T`），测试可对照。

---

## 8. 错误语义（首版）

| 情况 | 行为 |
|------|------|
| 路径不存在（`"r"`） | `FileNotFoundError` |
| 只读 `mode` 下赋值 / `del` | `OSError` 或 `UnsupportedOperation` |
| JSON 语法错误 | `JSONDecodeError`（与 `loads` 一致） |
| 静态路径类型不匹配 | 编译期 / `deserialize` 失败 |
| `commit` 失败 | 原文件保留；临时文件清理 |

---

## 9. 测试矩阵（实现后）

| 用例 | 文件 |
|------|------|
| 只读字段链 | `test/serde/test_json_document.py` |
| `r+` 改字段 + `commit` + 再 `load` 验证 | 同上 |
| `append` / `del` | 同上 |
| `load()` ≡ `Json.loads` | 同上 |
| `dump()` ≡ `Json.dumps`（无 dirty 时） | 同上 |
| 大文件 `read(-1)` 前置 | `test/io/` + document |

结构：`TestCaseMixin` + `override def test`（编码规范 §10）。

---

## 10. 分期实现

| 阶段 | 内容 |
|------|------|
| **P0** | `TextIOWrapper.read(-1)` EOF；`DocumentType` 协议 + `JsonDocument.open` + `load()` ≡ `loads` |
| **P1** | 只读字段链（`View` + `@serializable` codegen）；`dump()` |
| **P2** | `r+` 增删改 + `commit` / `with` |
| **P3** | sidecar 索引、perf |

**暂不实现**（本规范范围外）：

- 动态路径 `get[V](list[...])`
- `open_read` / `open_write` 等别名
- `LinesDocument` / NDJSON（另文档）
- 非 JSON `SerdeFormat`
- JSON 大于 RAM 的流式解析

---

## 11. 文档同步

实现落地时更新：

- [参考手册.md](./参考手册.md) §10.1 `serde`
- [编码规范.md](./编码规范.md) §8.1 模块对照（`serde/document`、`JsonDocument`）

---

*版本：2026-05-19；以 `py2cpp/serde/protocols.py`、`py2cpp/serde/json.py` 为实现准绳。*
