# `py2cpp.serde.protobuf` 设计方案

> **状态**：设计阶段，尚未实现。  
> **实现文件**：仅 `py2cpp/serde/protobuf.py`。  
> **范围**：静态 dataclass 消息到标准 Protocol Buffers binary wire format 的编码、解码与长度前缀帧；暂不支持 `.proto` 文件、`protoc`、descriptor、Google Protobuf C++ Runtime、gRPC。

## 1. 目标与定位

`py2cpp.serde.protobuf` 为 Py2Cpp 提供与其他 protobuf 实现互操作的二进制消息格式。它服务于网络协议、存档、资源数据、跨语言服务接口和后续 Zeus 的高频结构化数据，但不改变 Py2Cpp 自己的对象、容器、引用计数或 dataclass 模型。

模块必须满足：

- 输出符合 Protocol Buffers wire format；
- 可读取其他语言 protobuf 实现生成的兼容消息；
- 使用 Py2Cpp `@dataclass` 与字段 `@annotation` 描述 schema；
- 基于 `Self.iter_fields`、`Self.get_field_annotation`、`Self.get_field_type` 在翻译期展开，不依赖运行时字段反射；
- 不依赖 STL；
- 不依赖 Google Protobuf Runtime；
- 单一真相源为 `py2cpp/serde/protobuf.py`、必要模板、测试和本文档，禁止修改 `generated/`。

模块不追求完整复刻 `google.protobuf` 的动态 descriptor API。它是面向受限静态类型子集的 protobuf codec。

## 2. 文件与公开 API

首版只增加一个标准库文件：

```text
py2cpp/serde/protobuf.py
```

文件内按以下逻辑区域组织，不拆分 `wire.py`、`meta.py` 或子包：

```text
异常类型
WireType / ProtoScalar 枚举
ProtoFieldMeta 注解元数据
WireWriter / WireReader
Protobuf 静态入口
译期消息反射 mixin / helper
```

所有序列化入口属于 `Protobuf`，不保留模块级 `dumps`、`loads`、`dump`、`load`：

```python
from py2cpp.serde.protobuf import Protobuf

data: bytes = Protobuf.dumps(message)
message: Player = Protobuf.loads[Player](data)

Protobuf.dump(message, writer)
message: Player = Protobuf.load[Player](reader)

Protobuf.write_delimited(message, writer)
message: Player = Protobuf.read_delimited[Player](reader)
```

语义：

- `dumps` / `loads`：一条 message body；
- `dump` / `load`：对二进制 reader/writer 写入或读取一条 message body，不添加帧长度；
- `write_delimited` / `read_delimited`：以 varint 长度前缀包裹一条 message，适合 TCP、文件记录和自定义 RPC 帧；
- 泛型 `T` 必须为带 protobuf 字段注解的 `@dataclass`。

## 3. 消息 schema 写法

protobuf 字段必须显式指定 field number。字段号是 wire 兼容性契约，不能依赖 dataclass 声明顺序自动分配。

```python
from py2cpp import *
from py2cpp.serde.protobuf import ProtoFieldMeta, Protobuf

@dataclass
class Player:
  id: uint @ProtoFieldMeta(1) = 0
  name: str @ProtoFieldMeta(2) = ""
  score: int64 @ProtoFieldMeta(3) = 0
  tags: list[str] @ProtoFieldMeta(4) = []


player: Player = new(id=7, name="Alice", score=1200)
data: bytes = Protobuf.dumps(player)
decoded: Player = Protobuf.loads[Player](data)
```

`ProtoFieldMeta` 是项目现有字段注解机制中的 metadata class，定义形式为：

```python
@annotation
@dataclass
class ProtoFieldMeta:
  number: int
  scalar: ProtoScalar = ProtoScalar.Auto
  packed: bool = True
```

字段类型与元数据职责分离：

- 字段类型决定默认 protobuf 类型类别；
- `number` 决定 wire field number；
- `scalar` 仅在默认映射不够表达时覆盖编码规则；
- `packed` 只影响 repeated 数值字段的写法；解码器始终同时接受 packed 和 unpacked。

字段名只服务 Py2Cpp 源码，不进入 protobuf wire format；重命名字段不会影响兼容性，变更 field number 或 wire 类型则会影响兼容性。

## 4. 标量与 wire 类型

### 4.1 Wire 类型

```python
@enum
class WireType:
  Varint = 0
  Fixed64 = 1
  LengthDelimited = 2
  Fixed32 = 5
```

tag 的计算规则严格遵循 protobuf：

```text
tag = (field_number << 3) | wire_type
```

field number 只能为 `1..536870911`，并保留 protobuf 禁用区间 `19000..19999`。违反时应在 schema 严格检查期拒绝。

### 4.2 自动类型映射

P0 支持：

| Py2Cpp 字段类型 | 默认 protobuf 语义 | wire type |
|---|---|---|
| `bool` | `bool` | varint |
| `int` | `int32` | varint |
| `uint` | `uint32` | varint |
| `int64` | `int64` | varint |
| `uint64` | `uint64` | varint |
| `float` / `float64` | `double` | fixed64 |
| `str` | UTF-8 string | length-delimited |
| `bytes` | bytes | length-delimited |
| `@enum` | enum numeric value | varint |
| `list[T]` | repeated T | 由元素类型决定 |
| protobuf dataclass | embedded message | length-delimited |

整数 wire 编码使用 64 位 protobuf varint，不使用 `numeric.varint` 的任意精度值模型。

### 4.3 `ProtoScalar` 覆盖

基础 Python 类型不能表达 protobuf 的全部数值编码差异，故提供：

```python
@enum
class ProtoScalar:
  Auto
  Int32
  Int64
  UInt32
  UInt64
  SInt32
  SInt64
  Fixed32
  Fixed64
  SFixed32
  SFixed64
  Float
  Double
  String
  Bytes
```

示例：

```python
@dataclass
class Sample:
  normal: int @ProtoFieldMeta(1) = 0
  zigzag: int @ProtoFieldMeta(2, scalar=ProtoScalar.SInt32) = 0
  fixed: uint @ProtoFieldMeta(3, scalar=ProtoScalar.Fixed32) = 0
```

`scalar` 改变 protobuf 编码规则，不改变 Py2Cpp 的字段存储类型。若指定类型与字段类型不兼容，应为严格翻译错误。

## 5. 静态反射与翻译期展开

protobuf 是新静态字段反射 API 的直接使用者。消息 codec 在概念上按如下方式展开：

```python
for field in Self.iter_fields[ProtoFieldMeta]():
  meta = Self.get_field_annotation[ProtoFieldMeta](field)

  if Self.get_field_type(field) is int:
    ...
  elif Self.get_field_type(field) is str:
    ...
```

对：

```python
@dataclass
class Player:
  id: uint @ProtoFieldMeta(1) = 0
  name: str @ProtoFieldMeta(2) = ""
```

翻译期生成等价的直接成员操作：

```python
if message.id != 0:
  writer.write_tag(1, WireType.Varint)
  writer.write_varint_u32(message.id)

if message.name:
  writer.write_tag(2, WireType.LengthDelimited)
  writer.write_string(message.name)
```

实现约束：

- `Self.iter_fields[ProtoFieldMeta]()` 保留字段声明顺序；
- `Self.get_field_annotation[ProtoFieldMeta](field)` 读取 `number/scalar/packed`；
- `Self.get_field_type(field)` 返回去除所有 `@` 标记后的真实基础类型；
- `Self.get_field_type(field) is int` 等比较在翻译期折叠；
- `getattr` / `setattr` 的字段名由现有静态反射折叠为直接成员访问；
- 不生成运行时 descriptor、字符串字段表或哈希查找。

必要时可使用受限的 codec mixin，让 `Protobuf.dumps[T]()` 将 `Self` 绑定为 T；不应为 protobuf 新增与既有 `@annotation` 平行的专用反射系统。

## 6. WireReader 与 WireWriter

`protobuf.py` 内定义两个低层状态对象；它们只处理字节、tag 和 wire value，不知道 dataclass schema。

```python
@dataclass
class WireWriter:
  _buf: byte[:] = []

  def write_tag(self, number: int, wire: WireType) -> None: ...
  def write_varint_u64(self, value: uint64) -> None: ...
  def write_fixed32(self, value: uint) -> None: ...
  def write_fixed64(self, value: uint64) -> None: ...
  def write_bytes(self, value: bytes) -> None: ...
  def write_string(self, value: str) -> None: ...


@dataclass
class WireReader:
  _data: bytes = b""
  _at: int = 0
  _limit: int = 0

  def read_tag(self) -> tuple[int, WireType]: ...
  def read_varint_u64(self) -> uint64: ...
  def read_fixed32(self) -> uint: ...
  def read_fixed64(self) -> uint64: ...
  def read_bytes(self) -> bytes: ...
  def skip_value(self, wire: WireType) -> None: ...
```

实现规则：

- varint 最多 10 字节；超长、截断或第十字节越界必须报错；
- fixed32/fixed64 读取必须检查剩余长度；
- length-delimited 读取必须检查长度溢出、剩余输入和最大字段长度；
- 嵌套 message 用 reader 子范围限制，禁止越过父范围；
- 设置最大 message size、最大 field length、最大递归深度；
- 所有读取用偏移 cursor，避免递归层中反复复制 bytes；
- 性能热点如 varint、fixed load/store、buffer grow 可后续下沉 native 模板，但 schema 与状态机保持 Python 描述。

## 7. 编码与解码语义

### 7.1 默认值

P0 采用 proto3 风格默认值省略：

| 字段 | 默认值 | 默认是否写出 |
|---|---:|---|
| 整数 / enum | `0` | 否 |
| bool | `False` | 否 |
| float | `0.0` | 否 |
| str | `""` | 否 |
| bytes | `b""` | 否 |
| repeated list | 空 | 否 |
| optional embedded message | `None` | 否 |

普通 proto3 标量字段不区分“未出现”和“出现但为默认值”。presence 语义、proto3 optional 与复杂嵌套 optional 留到 P1。

### 7.2 repeated 与 packed

`list[T] @ProtoFieldMeta(...)` 表示 repeated 字段。

- repeated 数值字段默认写 packed；
- `ProtoFieldMeta(packed=False)` 强制写 unpacked；
- 解码器必须同时接受 packed 与 unpacked 表示；
- string、bytes、embedded message 的 repeated 字段始终逐项 length-delimited；
- singular 字段重复出现时后值覆盖前值；repeated 按 wire 读取顺序 append。

### 7.3 未知字段

P0 解码器必须能跳过未知字段，维持前向兼容：

```python
reader.skip_value(wire_type)
```

P0 不保留未知字段原始字节；decode 再 encode 时未知字段会丢失。P1 可增加内部 `UnknownProtoFields` 容器实现保留，但在该能力落地前不得提供误导性的 `preserve_unknown` 开关。

### 7.4 错误与 wire 不匹配

推荐异常层级：

```text
ProtobufError
├─ ProtoEncodeError
├─ ProtoDecodeError
├─ ProtoWireError
├─ ProtoTruncatedError
├─ ProtoSizeLimitError
└─ ProtoSchemaError
```

错误包含 message 类型、字段号、wire type、输入偏移和可用的字段名。wire type 与 schema 不匹配、非法 tag、截断、非法 UTF-8、长度超限均不得静默容忍。

## 8. P0 schema 严格检查

`Protobuf.dumps[T]()` / `loads[T]()` 使用前，翻译期必须检查：

1. T 为 `@dataclass`；
2. 参与编码的每个字段恰有一个 `ProtoFieldMeta`；未标注字段不参与 protobuf；
3. field number 合法、唯一且不落入保留区间；
4. `ProtoFieldMeta.scalar` 与 `Self.get_field_type(field)` 兼容；
5. `packed=True` 仅用于 repeated 数值、bool 或 enum；
6. `list[T]` 的元素类型属于支持集合；
7. embedded message 类型也满足 protobuf dataclass schema；
8. 禁止递归值类型无 optional/引用边界；
9. 不支持的 `dict`、`@union`、复杂 Optional、裸 `object` 等类型必须在翻译期说明原因并拒绝。

这些检查应由 protobuf 专用展开/严格检查完成，不应放宽现有 dataclass、字段注解或类型系统规则。

## 9. 分期范围

### P0：可互操作基础

- `WireType`、`ProtoScalar`、`ProtoFieldMeta`；
- varint、zigzag、fixed32、fixed64、length-delimited；
- scalar、enum、str、bytes；
- embedded dataclass message；
- repeated 与 packed；
- 默认值省略；
- 未知字段跳过；
- `dumps/loads` 与 delimited framing；
- schema 严格检查、大小/深度限制、完整错误路径。

### P1：高级 schema

- `@optional` presence；
- protobuf map-entry 形式的 `dict[K, V]`；
- 复用项目 `@union` 的 protobuf oneof；
- unknown field 原始字节保留；
- 更完整的 float32/float64 区分。

### 明确不做

- `.proto` 解析或生成；
- 调用 `protoc`；
- descriptor set；
- Google Protobuf Runtime FFI；
- gRPC / HTTP2；
- proto2 required、extension、dynamic message；
- 任意 schema 演化自动迁移。

以后如果确实需要 `.proto`，应另立生成工具设计：开发期 `.proto` 或 descriptor 生成 `@dataclass + ProtoFieldMeta` 的 Py2Cpp 源码；生成出的程序和本模块运行时仍不得依赖 `protoc` 或 Google Runtime。

## 10. 测试方案

新增：

```text
test/serde/
  test_protobuf_wire.py
  test_protobuf_message.py
  test_protobuf_repeated.py
  test_protobuf_nested.py
  test_protobuf_compat.py
  test_protobuf_fail.py
```

必须覆盖：

- tag 与 field number 边界；
- 64 位 varint、zigzag、fixed32/fixed64；
- 空消息和默认值省略；
- signed/unsigned 边界；
- UTF-8 string 与任意 bytes；
- nested message 与深度限制；
- packed / unpacked repeated 数值字段互读；
- enum；
- 未知字段跳过；
- 非法 wire type、截断、超长 varint、长度溢出、字段号冲突；
- schema 严格检查错误；
- 固定 protobuf canonical byte fixture 的双向兼容；
- delimited framing 的连续多 message 读取。

兼容测试必须提交固定 golden bytes；普通回归不得依赖网络、Python `protobuf` 包、本机 `protoc` 或 Google Runtime。可另设非默认开发审计脚本，以官方实现复核 fixture，但不进入主构建路径。

## 11. 推荐实施顺序

```text
1. protobuf.py 骨架：异常、枚举、ProtoFieldMeta、bytes cursor
2. WireWriter / WireReader：tag、varint、zigzag、fixed、长度限制
3. scalar + dataclass singular 字段的静态展开
4. nested message、默认值省略、未知字段跳过
5. repeated + packed、delimited framing
6. schema 严格检查、错误路径与 golden compatibility 测试
7. P1 optional/map/oneof/unknown preservation（另行设计后实施）
```

P0 完成标准是：不需要 `.proto`、`protoc` 或 Google Runtime，即可用单个 `py2cpp/serde/protobuf.py` 对一组静态 dataclass 消息进行稳定、可诊断且与标准 protobuf wire format 兼容的二进制编解码。
