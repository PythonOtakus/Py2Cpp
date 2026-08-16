# JSON `loads` RapidJSON 档优化方案

> **状态**：实现中（阶段 0–2 已完成，阶段 3 部分落地）  
> **目标 workload**：`loads[list[User]]`（`test/perf/test_json_serde.py`，n=2000，payload ≈ 85–95 KB）  
> **约束**：符合 [编码规范.md](./编码规范.md)；不引入 STL / 第三方 JSON 库；不手改 `generated/`；用户 Python API（`loads` / `@serializable`）不变。

### 实现进度（2026-05-27）

| 阶段 | 内容 | 状态 | 实测 / 备注 |
|------|------|------|-------------|
| **0** | perf 基线、`test_json` 乱序键 | ✅ | `scripts/build_perf_json.bat` 全绿 |
| **PR-A** | `mark`/`restore`、`_src_view`、`loadStrSpan`、`skipEmptyArray`；`str.from_codes_span` | ✅ | `py2cpp/serde/json.py`、`py2cpp/text/str.py` |
| **PR-B** | `_schema_deserialize_eligible`、有序 `deserialize` + `restore` 回退 | ✅ | `test/serde/test_json.py` 含 `reordered` |
| **PR-C** | `_fast_load_list_*` + `_JsonLoads<PyList<User>>` 特化 | ✅ | `serializable.py` → 用户模块 `.inl` |
| **3** | C++ 快路径 `from_codes_span`/`skipEmptyArray`；`new` 收尾（Python 有序路径） | 🔄 | C++ 仍 `User(…)+tags` 赋值 |
| **3-span** | `JsonDecoder.srcLen`/`srcChar`；热路径读 `_src`；`list[User]` 生成改 `srcChar` | ✅ | 见上 |
| **3-inline** | C++ 有序解析：内联 ``"k":`` / ``,\"k\":``、内联 `true`/`[]`、去 `tryMatchKey`/`beginRootObject` 冗余 | ✅ | 见上 |
| **3-append** | `list.append`/`_insertNew` 形参 `const T&`；空 `tags` 跳过 `_u.tags` 赋值；`__forceinline` 解析函数 | ✅ | `loads list[User]` **~8.2 ms**（约 **2.6×** 基线） |
| **3-fix** | `skipEmptyArray` 用 `in "[` / `in "]"`（勿 `== "["` → C++ `PyStr` 比较会崩） | ✅ | `py2cpp/serde/json.py` |
| **3-mega** | mega-loop 内联 2000× 对象体；`name_seg` + `assign_from_codes_span` 减 PyStr 双拷贝 | ✅ | `loads list[User]` **~7.9 ms**（约 **2.7×** 基线） |
| **4a** | 档 A：`asciiBytes` + `list[int]` SwAR（不绑 `list[User]`） | ✅ | `list[int]` 50k ~9.4 ms |
| **4b** | `serdePushSlot` 原位 `init` + `assign_from_codes_span`； ctor 用 `(id_v,\"\",active_v)` | ✅ | `loads list[User]` **~7.8 ms** |
| **4c** | `loadStrSpan` 引号 SwAR（修 ``i+k``）；`list[str]` ``serdePushSlot``；`list[int]` push 槽 | ✅ | `py2cpp/serde/json.py` |
| **4d** | 纯 ``int`` dataclass（``Ticker``）``serdePushSlot`` + ``init`` | ✅ | `serializable.py` |
| **4 arena** | `PyArena` + `acquire`/`release` + `adopt_codes_buf`；`loads` 启 `strArena` | ✅ | 见上 |
| **4 arena-2** | `span.at()` + `memory.copyBuf`（``memcpy``）；`reserve(sl/2)` | ✅ | 见 perf |
| **PR-0** | 零拷贝 ASCII bind（``PyChar`` 视图、无 packed 分配）、``loads`` 入口 ``try_bind``、按 ``T`` 条件 ``strArena`` | ✅ | 大 payload 省 O(n) 拷贝 + arena 固定开销 |
| **PR-1** | ``list[int|str]`` ASCII 叶子 + ``load_list_*_ascii_loop``（C++ 内联 push/skip；ref = 纯 Python 组合） | ✅ | ``loads list[int]`` 50k **~26 ms**；``loads list[str]`` 20k **~20 ms** |
| **PR-2** | 恢复 ``serializable`` ``_fast_load_list_*`` + ``_json_loads_list_element<Cls>`` 特化（用户模块 ``.inl``） | ✅ | ``loads list[User]`` 2k **~9.3 ms** |
| **strict 原子化** | 去掉 composite ``_json_read_list_*``；``loads`` 容器为 Python 组合 + 叶子 ``@native`` | ✅ | 见 [编码规范 §9.4](./编码规范.md#94-native-原子化基础设施) |
| **PR-P2** | ``dict[str,str]`` ASCII 叶子 + ``dict._index`` 用 ``hash(key)`` | ✅ | ``loads dict[str,str]`` 5k **~150 ms** |
| **PR-P3** | ``dict`` ``setCapacity`` 预分配；``dict[str,varint|float]`` ASCII 叶子循环 | ✅ | 减 rehash；varint/float 镜像 int/str |
| **译器单测** | `src/tests/test_serializable_schema.py` | ⏸ | 未开始 |

**MSVC（`scripts/build_perf_json.bat`）**：`test_json` 7/7；`test_json_serde` 含 `Ticker`/`MiniUser`/`loads list[int|str]` 等对照用例。

**perf 对照结构**（`test/perf/test_json_serde.py`）：

| 用例 | 优势来源 |
|------|----------|
| `loads list[int]` n=50000 | `_loadListIntAt` + ``load_list_int_ascii_loop`` + SwAR |
| `loads list[str]` n=20000 | ``load_list_str_ascii_loop`` + ``strAssignFromSeg`` |
| `loads list[Ticker]` n=20k | 纯 int mega-loop，无 ``PyStr`` |
| `loads list[MiniUser]` n=2k | 无 ``name``/``tags``，对比 ``User`` |
| `loads list[User]` n=2k | 全字段 + ``assign_from_codes_span`` |

| 指标 | 基线（文档） | 当前 |
|------|--------------|------|
| `loads list[User]` n=2000 | ~21 ms | **~9.3 ms**（PR-2 mega-loop + arena） |
| `loads list[MiniUser]` n=2000 | — | **~5.6 ms**（无 ``name``/``tags``） |
| `loads list[Ticker]` n=20000 | — | **~90 ms**（纯 int 行；generic ``deserialize``） |
| `loads list[int]` n=50000 | ~9.4 ms（旧 mega） | **~26 ms**（strict 原子化 + ``ascii_loop``） |
| `loads list[str]` n=20000 | — | **~20 ms**（``ascii_loop`` + push 槽） |
| `dumps list[User]` n=2000 | — | ~6.8 ms |

**3-mega** 已达标阶段 2 粗估（~4–6 ms）；距阶段 3 目标（~1–3 ms）仍差约 3×。**4a–4 arena-2** 已落地（``memcpy``；单块 bump+adopt 受 ``PyStr`` 所有权约束，二期未采用）。下一步：``new`` 收尾、``assign_from_codes_span`` 全局 ``memcpy``。

**约束**：C++ 内联键路径假定 **`dumps` 紧凑形态**（无键间空白）；乱序/带缩进仍走 Python `deserialize` + `restore` 回退。

**验证命令**：

```bat
scripts\build_perf_json.bat
```

---

## 1. 目标定义

| 档位 | 端到端耗时（85 KB） | 有效吞吐 | 说明 |
|------|---------------------|----------|------|
| **当前** | ~21 ms | ~0.004 GB/s | 通用 `deserialize` × 2000 |
| **阶段 1–2** | ~4–8 ms | ~0.01–0.02 GB/s | 有序 schema + `list[User]` 特化 |
| **阶段 3** | **~1–3 ms** | **~0.03–0.08 GB/s** | + `new` 收尾、空 `tags`、`append` 优化 |
| **RapidJSON 档（本方案务实目标）** | **0.3–1.0 ms** | **~0.08–0.3 GB/s** | + **`span[char]` 热路径**、延迟 `PyStr` 物化 |
| RapidJSON SAX 纯扫（参照） | ~0.12 ms | ~0.7 GB/s | 不建 `User` / `PyStr` / `PyList` |

在保留 **`PyStr` / `PyList` / `@copyable` `User`** 语义的前提下，**0.1 ms 极难**；本方案以 **~1 ms 可交付、~0.3 ms 可冲刺** 为验收区间。

---

## 2. 现状与瓶颈

### 2.1 调用链

```text
loads<PyList<User>>(js)
  → JsonDecoder::fromText(s) + arena 预分配
  → Json::loads<T> → __py2cpp_type_if_loads_*_pick<T>::__call__
       → 分支示例：
            T is list[int]     → _json_read_list_int(dec)
            T is list[...]       → _json_read_list_serializable<T::Element>(dec)
                                 （@serializable 有序快路径：template<> 特化同函数）
            else               → _json_loads_generic<T>(dec)  // T::deserialize
  → _json_release_loads(dec)
```

实现位置：

| 组件 | 路径 |
|------|------|
| 列表反序列化 | `py2cpp/serde/json.py` → `Json.loads` 类型 if + `@native` `_json_read_list_*` |
| 对象反序列化 | `src/passes/serializable.py` → `_emit_dataclass_serializable` + `_json_read_list_serializable<>` 特化 |
| 解码器 | `py2cpp/serde/json.py` → `JsonDecoder` |
| 参照快路径 | `py2cpp/serde/json.py` → `_loadListIntAsciiLoop` / `parseIntAtAscii` |

### 2.2 与 RapidJSON 的差距来源

| 因素 | RapidJSON SAX | Py2Cpp 当前 |
|------|---------------|-------------|
| 结构表示 | 事件流 / 跳过未读字段 | 每对象 `while` 键试探 |
| 字符串 | 常指向输入 buffer | 每字段 `PyStr` 堆分配 |
| 扫描接口 | `const char*` 指针 | `PyStr[pos]` 经 `PyChar` |
| 数组 | 单循环 + 内联解析 | `beginArray` + 静态方法调用 |
| 绑定 | 手写 handler 写 struct | 通用 `deserialize` |

---

## 3. 核心设计：`span[char]` 作为 `string_view`

### 3.1 项目已有能力（复用，不新造轮子）

| Python | C++ | 语义 |
|--------|-----|------|
| `span[T]` | `PySpan<T>` | 非拥有视图；`ptr` + `length` + `step` |
| `s.view` | `parent.view()` | `list` / `array` / `StackArray` 的连续区间 |
| `char` | `PyChar` | Unicode 码点单元（JSON 子集为 ASCII 时与字节 1:1） |
| `str.data` | `PyArray<PyChar>` | `PyStr` 底层缓冲 |

规范见 [编码规范.md §5.1](./编码规范.md)：**视图** `s.view` / `s.view[i:j]`，下标相对 span 起点。

**本方案约定**：在 JSON 解码热路径中，`span[char]` 等价于 C++ `string_view` 的角色——**指向 `JsonDecoder` 输入文本的码点缓冲的子区间，不拥有内存**。

### 3.2 生命周期与所有权

```text
loads(js)
  js: PyStr  （拥有 data: char[:]）
  JsonDecoder
    s: str              # 保留，对外/Python 语义不变
    _src: span[char]    # dec.s.data.view，自 fromText 起有效
    pos: int            # 相对 _src 起点的逻辑下标（与现 pos 一致）
```

| 规则 | 说明 |
|------|------|
| `_src` 有效期 | 仅当 `dec.s` 存活且 `data` 未被变异；`loads` 单次解析内满足 |
| 禁止 | 把 `_src` 子 span 存进长期 `User` 字段（`name` 仍为 `PyStr`） |
| 物化时机 | 写入 `str` 字段、需要 `==`/`hash`、转义解码完成时，才 `PyStr.fromSpan`（见 §3.4） |

### 3.3 `JsonDecoder` 增量字段（基础设施）

在 `py2cpp/serde/json.py` 中扩展（**不改变** `loads` / `load` 签名）：

```python
class JsonDecoder:
  s: str
  pos: int
  _src: span[char]  # fromText 时: self._src = self.s.data.view

  def mark(self) -> int: ...
  def restore(self, m: int) -> None: ...

  @immutable
  def _sliceAt(self, start: int, end: int) -> span[char]:
    """半开区间 [start, end)，相对 _src 逻辑下标。"""
    ...

  def loadStrSpan(self) -> span[char]:
    """无转义：返回引号内 ASCII/码点视图；有转义则走慢路径并物化 PyStr。"""
    ...

  def skipEmptyArray(self) -> None:
    """`[]` 原位跳过，避免 list 解析循环。"""
    ...
```

C++ 生成形态：`PySpan<PyChar>`；热路径用 `dec._src[k]` / `dec._sliceAt(start, end)`，**避免** `dec.s[dec.pos]` 反复经 `PyStr::__getitem__`。

### 3.4 `PyStr` 物化策略（其它类型不变）

| 场景 | 策略 |
|------|------|
| `name: str` 无转义 | `loadStrSpan()` → `str` 构造自 `char[:]` 拷贝或 `PyStr(codes_slice)`（在 `text/str.py` 增 **一处** `from_codes_span` 类方法，供 serde 复用） |
| 有 `\u` / `\"` | 仍 `loadStringSlow()`，行为与现网一致 |
| `tryMatchKey` | 仍在 JSON 缓冲上原位比；可选：对 `expected` 用 `expected.data.view` 与 `_src` 逐 `PyChar` 比较 |
| `int` / `bool` | 在 `_src` 上 `parseIntAt` / `parseBoolAt`，不建临时 `PyStr` token |

**不改为** `std::string_view`；**不**让业务代码看见 `span[char]`（仅 `JsonDecoder` 与生成代码内部）。

---

## 4. 分阶段实施方案

### 阶段 0：基线与可观测（必做）

| 项 | 内容 |
|----|------|
| 记录 | `len(js)`、loads/dumps ms、MB/s（已有 `_printRow`） |
| 可选 | 拆分 bench：`loads[User]`×2000 vs `loads list[User]` |
| 译器测 | `src/tests/test_serializable_schema.py` 断言生成片段 |

---

### 阶段 1：有序 schema `deserialize` + `mark`/`restore`

**目标**：单对象 ~2×；乱序/未知键回退通用路径。

| 改动 | 文件 |
|------|------|
| `mark` / `restore` | `py2cpp/serde/json.py` |
| `_schema_deserialize_eligible` | `src/passes/serializable.py` |
| 生成 `deserialize`：`mark` → `_deserialize_ordered` → 失败 `restore` → `_deserialize_generic` | 同上 |
| `_deserialize_generic` | 现有 `while` + `tryMatchKey` + `skipField` |

**有序路径（`User`）**：字段顺序与 `serialize` 一致：`id` → `name` → `active` → `tags`；每步后 `atObjectEnd()` 可提前 `return new(...)`。

**`span[char]` 在本阶段**：`fromText` 初始化 `_src`；`tryMatchKey` / `parseIntAt` 优先读 `_src`（叶子在 `py2cpp/serde/json.py` + `util/memory` 的 `@native`）。

**验收**：`test/serde/test_json.py` 全绿 + 乱序键用例 1 条。

**预期**：~21 ms → ~8–10 ms（仅对象层，未改 list 特化）。

---

### 阶段 2：`loads[list[User]]` 模板特化 + 数组快路径

**目标**：对齐 `_fast_load_list_int_dec`，去掉 2000× `User::deserialize` 入口。

| 生成物（用户 `.cpp`） | 说明 |
|----------------------|------|
| `_json_parse_user_ordered(JsonDecoder&)` | 阶段 1 有序体，供数组循环调用 |
| `_fast_load_list_user_dec(JsonDecoder&)` | 扫 `[` / `]`，`setCapacity`，循环 `_json_parse_user_ordered` |
| `template<> _JsonLoads<PyList<Ns::User>>::go` | 特化于 `py2cpp::serde::json`，用户 TU 可见主模板 |

**注意**：`User` / `__json_key_User_*` 在用户命名空间，由 `serializable` pass 按模块生成（非 codegen 注入）。

**`span[char]`**：数组循环内对象解析全程 `_src` + `pos`，与 int 快路径一样减少 `beginArray` API 层开销。

**验收**：`test/perf/test_json_serde.py`；`loads<PyList<User>>` 写法不变。

**预期**：累计 ~4–6 ms。

---

### 阶段 3：热路径减负（逼近 RapidJSON 绑定档）

#### 3a. 收尾统一 `new`

`serializable.py` 生成 `return new(id=..., name=..., ...)`，消除 `User(0,…) + 逐字段赋值`。

#### 3b. 空 `tags: []` 快路径

perf 数据 `"tags":[]`：有序路径在 `tags` 处调用 `skipEmptyArray()`（基于 `_src` 上 `pos` 见 `[` 后 `]`）。

#### 3c. 有序路径减少 `tryMatchKey`

确认 `,` 后下一键；首键仍 `tryMatchKey`；后续可用 `expect_key` + 常量比较（键字面量在 JSON 缓冲的 `_src` 段上）。

#### 3d. `list` 追加优化

查 `py2cpp/util/list.py`：若可 **原位构造** / 减少 `append` 拷贝，在基础设施层扩展；生成代码向 `set_item` / 槽位写入靠拢。

#### 3e. `span[char]` 延迟物化（本阶段重点）

| 字段类型 | 热路径 |
|----------|--------|
| `str` | `loadStrSpan` → 仅物化一次 `PyStr` |
| `list[str]` 空 | `skipEmptyArray` |
| `list[str]` 非空 | 仍 `loadListStrValue`（可二期对 ASCII 无转义用 span） |

**预期**：累计 **~1–3 ms**。

---

### 阶段 4（可选）：冲 ~0.3–1 ms

| 项 | 内容 | 风险 |
|----|------|------|
| 单函数 `loads list[User]` | pass 生成 mega-loop，内联 int/bool/空 tags | 与 `JsonDecoder` 分叉，须 mark 回退 |
| `parse_int` SwAR | `py2cpp/serde/json.py` + `util/memory.loadU64Le` | 中等 |
| loads 级 arena | ✅ `PyArena::acquire` + `adopt_codes_buf`；`span.at()` + `memcpy`（arena-2） | 单块 bump+adopt 需 finalize，暂未做 |

**暂不实现**：simdjson 链接、全局 `PyStr` 改 view 语义。

---

## 5. `span[char]` 与现有 API 对照

| 操作 | 当前 | 优化后（热路径） |
|------|------|------------------|
| 空白跳过 | `self.s[self.pos]` | `_src[self.pos]` 或 `_json_dec_skip_ws` 读 `PySpan` |
| 键匹配 | `tryMatchKey` 比 `PyStr` | 比 `_src` 段；`expected` 可比 `expected.data.view` |
| 无转义字符串 | `loadStr` → slice `PyStr` | `loadStrSpan` → 一次拷贝到 `PyStr` |
| 整数 | `parseIntAt` 扫 `self.s` | 扫 `_src` |
| mark/restore | 无 | `pos` 整数即可（`_src` 基址不变） |

**译器**：若 `JsonDecoder._src` 为私有字段，pass 生成代码仍通过 `decoder.skipSpaces()` 等公有方法访问；**禁止**业务 `@serializable` 类直接持有 `span[char]`。

---

## 6. 文件与 PR 切分

```text
PR-A  基础设施
      py2cpp/serde/json.py       _src, mark/restore, loadStrSpan, skipEmptyArray
      py2cpp/text/str.py         from_codes_span（或等价，单点）
      py2cpp/util/memory.py      loadU64Le 等 @native 叶子

PR-B  Schema 双路径
      src/passes/serializable.py  ordered + generic；_schema_deserialize_eligible
      test/serde/test_json.py      乱序键 / 缺字段 / 未知键
      src/tests/test_serializable_schema.py

PR-C  list[User] 特化 + 阶段 3
      serializable.py             _fast_load_list_* + _JsonLoads 特化生成
      test/perf/test_json_serde.py  可选阈值 assert（Release）
      docs/参考手册.md            §10.1 快路径与回退语义（对外行为不变则简述）

bootstrap（改标准库后）:
      python main.py py2cpp\__init__.py -o generated --no-main

验证:
      test/serde/test_json.py
      scripts/build_perf_json.bat  或 build_all.bat
```

---

## 7. 性能预期（`loads list[User]` n=2000）

| 阶段 | 耗时（粗估） | 累计加速 | `span[char]` 贡献 |
|------|--------------|----------|-------------------|
| 基线 | ~21 ms | 1× | — |
| 1 有序 deserialize | ~8–10 ms | ~2× | 低（扫缓冲方式变） |
| 2 list 特化 | ~4–6 ms | ~4× | 中 |
| 3 new/空 tags/append/延迟 PyStr | **~1–3 ms** | **~7–20×** | **高** |
| 4 可选 | **~0.3–1 ms** | **~20–70×** | 高 |

---

## 8. 语义与兼容性

| 场景 | 行为 |
|------|------|
| `dumps(u)` 再 `loads` | 走 ordered 快路径 |
| 键顺序与 `serialize` 不同 | `restore` → generic `while` |
| 未知键 | generic `skipField` |
| 缺字段 | 默认值 + `new` |
| 输入含转义 Unicode | `loadStringSlow`，与现网一致 |
| `loads` Python 签名 | **不变** |

---

## 9. 明确不做

- 引入 simdjson / RapidJSON / nlohmann 链接  
- 使用 `std::string_view` 或 STL 容器  
- 仅 `ordered_load=True` 且不支持乱序（默认 **try ordered + restore**）  
- 业务代码使用 `span[char]` 或专用 `_fast_loads_*` API  
- 手改 `generated/`  
- 为 perf 修改 `@copyable` / `User` 内存布局  

---

## 10. 实现后自检清单（py2cpp-design）

| 项 | 检查 |
|----|------|
| 范式 | pass 生成仍用 `new`；无业务手写 dunder |
| 复用 | `span`/`str.data.view`/`tryMatchKey`/`parseIntAt`；无重复扫串 helper |
| 切片/布尔 | `s[:k]`、`not s` |
| 冲突 | Win 宏、`@native` 签名与 `JsonDecoder&` 一致 |
| 验证 | bootstrap + `test_json` + perf MSVC 全绿 |

---

## 11. 参考

- 仓库内：`py2cpp/serde/json.py`（`JsonDecoder` / `Json.loads`）、`src/passes/serializable.py`（`@serializable` 生成）  
- 仓库内：`py2cpp/util/span.py`、`docs/编码规范.md` §5.1  
- 外部：[simdjson On-Demand 论文](https://arxiv.org/html/2312.17149v3)、[json_benchmark_results](https://github.com/simdjson/json_benchmark_results)  

---

*文档版本：2026-05-27；实现进度见文首「实现进度」表。*
