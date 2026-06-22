# TypeNode：结构化类型 IR 迁移方案

Py2Cpp 译器将 Python 类型注解 lower 为 C++ 类型名。当前主路径是 **AST → C++ 字符串**，中间变换（`@boxing`、`Self`、条件别名匹配等）大量依赖字符串前缀/相等，易出现 `_Key` vs `Key` 一类漏判（见 `dict_entry.next` 修复）。

**TypeNode** 是在 AST 与 C++ 文本之间的 **不可变结构化 IR**：匹配、存储语义变换在树上完成；**仅 emit 边界** `render()` 成 C++ spellings。

相关文档：[type-conditional.md](./type-conditional.md)（条件别名）、[type-node.md](./type-node.md)（结构化 TypeNode IR）、[参考手册 §5](./参考手册.md)（类型注解策略）。

---

## 1. 三层模型

```text
ast.expr  ──parse_type_node──►  TypeNode（语义层）
                                    │
                              apply_storage（boxing / refcount / optional 内层）
                                    │
                              render(NamingPolicy) ──► "PyDictEntry<Key, Value>*"
```

| 层 | 职责 | 示例 |
|----|------|------|
| **语义 TypeNode** | 「是什么类型」 | `Template(py="dict_entry", cpp="PyDictEntry", [Key, Value])` |
| **Storage 变换** | 按 `ClassInfo` **身份**加指针 / `PyRefCount<>` | `@boxing` → `Pointer(inner)` |
| **Render** | 命名策略 → C++ 文本 | 模板头 `_Key`；类体 `Key`（`using Key = _Key`） |

**原则**：相等、结构匹配、storage 变换看 **结构 + ClassInfo**；只有 `render()` 关心最终字符串。

---

## 2. 模块布局

| 文件 | 职责 | Phase |
|------|------|-------|
| `src/analysis/type_node.py` | `TypeKind`、`TypeNode` ADT、工厂、`structural_match` | 0 |
| `src/analysis/type_render.py` | `NamingPolicy`、`render()` | 0 |
| `src/analysis/type_storage.py` | `apply_storage()` | 0 |
| `src/analysis/type_compat.py` | `type_node_from_cpp_string()`（过渡）、与 `ir.py` 谓词桥接 | 0 |
| `src/analysis/type_parse.py` | `parse_type_node()`（AST → TypeNode） | 0 起 |
| `src/analysis/type_pred.py` | TypeNode 结构谓词；`is_*_type(str \| TypeNode)` | 6 |

**暂不改**：`field_types` 存 TypeNode、emit 全量收口（Phase 1+）。

---

## 3. TypeNode 数据模型（Phase 0）

```python
class TypeKind(Enum):
  VOID, NEVER, SCALAR, TYPE_PARAM, SELF
  TEMPLATE, POINTER, OPTIONAL, REF, REFCOUNT
  ARRAY   # PyArray / stack_array / span；array_kind 区分

@dataclass(frozen=True)
class TypeNode:
  kind: TypeKind
  name: str = ""           # C++ 基名：PyInt、PyList
  py_name: str = ""        # 可选 Python 类名：list、dict_entry
  args: tuple[TypeNode, ...] = ()
  inner: TypeNode | None = None
  array_kind: str = "heap" # heap | stack | span | …
```

核心 API：

- `TypeNode.template(py_name, cpp_name, *args)`
- `TypeNode.pointer(inner)` / `optional(inner)` / `type_param(name)`
- `bind_self(host: TypeNode) -> TypeNode`
- `apply_storage(classes) -> TypeNode`（`type_storage.py`）
- `structural_match(pattern, wildcards) -> dict[str, TypeNode] | None`
- `render(policy: NamingPolicy) -> str`

### NamingPolicy

| 策略 | 形参命名 | 用途 |
|------|----------|------|
| `TEMPLATE_HEADER` | `T` → `_T`（`cpp_type_param_template_name`） | `template<>` 声明 |
| `CLASS_BODY` | 恒等 | 类内字段 / 方法（配合 `using Key = _Key`） |
| `STORAGE` | 同 CLASS_BODY | 参数、局部、字段存储类型 |

**形参换名等价**：匹配时 `Key` 与 `_Key` 在同一 host 形参表下视为同一形参（`type_param_names_equivalent`）。

---

## 4. 与现有 IR 的关系

```text
ClassInfo / FunctionSig / TypeAliasInfo   ← AST，描述「谁有谁」
TypeNode                                  ← 类型表达式结构
TypePattern / ConditionalAliasPlan        ← 分派计划（Phase 2 起引用 TypeNode）
C++ 字符串                                ← 仅 render 产物
```

`TypeParser.parse_type()` **保留**；Phase 0 并行提供 `parse_type_node()`，单测断言：

```text
render(parse_type_node(ast)) == parse_type(ast)   # 语义层
render(apply_storage(parse_type_node(ast))) == parse_storage_type(ast)  # 存储层
```

---

## 5. 渐进迁移路线

### Phase 0 — 基础设施（当前）

- [x] 文档定案（本文）
- [x] `TypeNode` + `render` + `from_cpp_string`（`type_node.py` / `type_render.py` / `type_compat.py`）
- [x] `apply_storage` / `apply_full_storage` 与 `ClassInfo.apply_*_storage_cpp_type` 对齐（`type_storage.py`）
- [x] `structural_match_type_nodes`（Phase 0 子集）
- [x] `TypeParser.parse_type_node()` / `parse_storage_type_node()` + `src/tests/test_type_node.py`
- **零行为变化**：emit 仍读字符串

### Phase 1 — 分析层双写（已完成）

- [x] `ClassInfo.field_type_nodes` 与 `field_types` 同步（`_set_field_cpp_type`）
- [x] `MethodSig` / `FunctionSig` 的 `param_type_nodes` / `return_type_node`
- [x] `split_cpp_template` 统一到 `type_compat.py`

### Phase 2 — 匹配 / 分派（已完成）

- [x] `TypePattern.pattern_node`
- [x] `type_extract.try_match_pattern` 优先树匹配
- [x] `type_if._structural_type_match` 通配路径走 `structural_match_type_nodes`
- [x] `type_conditional._parse_conditional_pattern` 填充 `pattern_node`

### Phase 3 — emit 边界收口（已完成）

- [x] `src/analysis/type_emit.py`：`storage_cpp` / `class_decl_return_cpp` / `method_impl_return_cpp` / `field_decl_cpp` / `function_param_cpp_types`
- [x] `SignatureBuilder` 形参/返回 `TypeNode` 优先 AST（`_method_param_type_nodes` / `_return_type_node_from_*`）
- [x] `class_decl_emit` / `class_emit` / `call_emit` 经 `type_emit` 渲染
- [x] 单测：`param_type_nodes.render(CLASS_BODY) == param_types`
### Phase 4 — 逐步去字符串双写（已完成）

- [x] `type_emit` 扩展：`sig_return_storage_cpp` / `method_param_storage_cpp` / `method_param_types_map` / `field_storage_cpp` / `field_storage_values`
- [x] `class_emit` 作用域形参、`variadic_template` prescan 改走 TypeNode
- [x] `class_decl_emit` 属性 getter / 静态属性 / `__repr__` 声明改走 `class_decl_return_cpp`
- [x] `build_property_*_sig` 填充 `return_type_node` / `param_type_nodes`
- [x] `call_emit` / `subscript_emit` / `dunder_ops_emit` / `genexp_call_emit` 字段与签名返回改走 `type_emit`
- [x] `_reconcile_param_type_node`：形参 node 与 `_param_cpp_type` 对齐
- [x] `_set_field_cpp_type`：先写 `field_type_nodes`，字符串由 `storage_cpp(node)` 回写
- [x] `build_method_sig` / `build_function_sig` / `build_property_setter_sig`：`param_types` 由 `method_param_types_map` 同步
- [x] emit / passes / `translator.py` 直读改经 `type_emit` 或 `Translator._field_storage` / `_sig_*` 辅助

**仍保留**：`field_types` / `param_types` / `ret_lead` 作为 **render 缓存**（只写 node、读经 `type_emit`）；`__ann__*` 仍为 AST 占位。

### Phase 5 — 缓存同步与残余收口（已完成）

- [x] `sync_sig_cache` / `collect_sig_type_texts`：手动改 node 后与头文件依赖扫描统一入口
- [x] `build_*_sig` 末尾统一 `sync_sig_cache`（含 static property getter 补 `return_type_node`）
- [x] 属性 backing 字段 / getter 返回补丁改经 `method_param_storage_cpp` + `sync_sig_cache`
- [x] 模块函数头依赖、`static_method_uses_class_type_param`、strict_style、setitem 声明改经 `type_emit`

### Phase 6 — 结构谓词替代字符串分析（已完成，129/129）

**目标**：`is_cpp_*` / 前缀相等 → `type_pred` 在 `TypeNode` 上判 ``kind`` / ``py_name`` / ``array_kind``；调用方可传 **字符串或 node**（node 优先，避免反解析）。

**剥离语义**（对齐旧 ``strip_cpp_ref`` / 字符串前缀）：

| 谓词族 | 剥除 | 不剥除 |
|--------|------|--------|
| 标量 ``is_char_type`` 等 | ``&`` | ``*``、``Optional``、``RefCount`` |
| 容器 ``is_list_type`` 等 | ``&`` | ``*``、包装层 |
| ``is_optional_type`` | ``*`` / ``&`` | ``Optional`` 本体 |
| ``peel_storage``（内层提取） | ``*`` / ``&`` / ``Optional`` / ``RefCount`` | — |

- [x] `type_pred.py`：容器 / 标量 / 数组 / 托管 / invokable / erased-protocol / callable（函数指针）
- [x] `type_extract.py`：``optional`` / ``refcount`` / ``single_template_inner`` / ``template_inner_text`` / ``template_fixed_inners``
- [x] `type_emit`：``field_type_node`` / ``param_type_node`` / ``sig_return_type_node`` / ``render_type_like`` / ``type_to_cpp_text``
- [x] 核心 ``is_cpp_*`` 与 ``cpp_*_elem_type`` / ``cpp_dict_type_args`` 等委托 ``type_pred`` / ``type_extract``
- [x] emit 热路径（``class_emit`` 协程默认构造、``translator`` 擦除协议赋值）改经 node 谓词
- [x] `build-all.bat` **129/129**

**仍保留（有意）**：``cpp_template_inner_args`` 为字符串切分原语；函数指针暂无 ``TypeNode`` 形态（``is_callable_type`` 仅字符串 / render 文本）。``is_invokable_type`` 已于 Phase 9 迁入 ``type_pred``。

### Phase 7 — 删除 `is_cpp_*` façade，emit 只认 node（已完成，129/129）

- [x] 删除 ``ir.py`` 中 ``is_cpp_*`` / ``cpp_*_elem`` 薄包装；内部经 ``_type_pred()`` / ``_type_extract()`` 懒加载
- [x] ``type_emit``：``field_type_node`` / ``param_type_node`` / ``sig_return_type_node`` 不再 ``coerce_type_node`` 回退
- [x] ``type_pred`` 补数组组合谓词（``is_char_heap_array_type`` 等）；``type_extract`` 公开容器/协议提取别名
- [x] 全仓库 emit / passes / translator 改 ``from ..analysis.type_pred import …``（``scripts/migrate_type_pred.py`` + 手修）
- [x] ``build-all.bat`` **129/129**

### Phase 8a — 清除 `ir` re-export，import 直引 `type_pred` / `type_extract`（已完成，129/129）

- [x] 删除 ``ir.py`` 末尾 ``type_pred`` / ``type_extract`` re-export 块
- [x] ``analyzer`` 顶层谓词改 ``from .type_pred import …``；lazy import 清扫
- [x] ``translator`` / ``emit/*`` / ``passes/*`` / ``test_type_node`` 剩余 lazy import 改直引
- [x] ``build-all.bat`` **129/129** 验证通过

### Phase 8c — result / complex 谓词迁入 `type_pred`（已完成，129/129）

- [x] ``type_pred`` 新增 ``is_iter_result_type`` / ``is_fault_result_type`` / ``is_complex_type``（支持 ``str | TypeNode``）
- [x] 删除 ``ir.py`` 中 ``is_cpp_result_type`` / ``is_cpp_fault_result_type`` / ``is_cpp_complex_type``
- [x] ``translator`` / ``emit/*`` 改直引 ``type_pred``
- [x] ``build-all.bat`` **129/129** 验证

### Phase 8b — 字符串缓存只读化（已完成，129/129）

- [x] ``type_emit``：读路径只认 ``field_type_nodes`` / ``param_type_nodes`` / ``return_type_node``，不回退 ``field_types`` / ``param_types`` / ``ret_lead``
- [x] ``write_field_storage`` + ``sync_sig_cache``：渲染缓存唯一写入口
- [x] ``field_ann_ast``：``__ann__*`` AST 占位与 C++ 缓存分离
- [x] ``move_state`` 注入 ``__moved__`` 改经 ``write_field_storage``
- [x] ``build-all.bat`` **129/129** 验证

### Phase 9 — `field_ann_ast` 统一 + `is_invokable_type` 迁入 `type_pred`（已完成，129/129）

- [x] 全仓库 ``field_types.get(f"__ann__{…}")`` 改 ``field_ann_ast(info, field)``（唯一实现留在 ``type_emit``）
- [x] ``type_pred`` 新增 ``is_invokable_type``（``str | TypeNode``；``Function`` / ``Callable`` / ``Delegate`` / 带 ``__call__`` 类）
- [x] 删除 ``ir.py`` 中 ``is_invokable_type``；``call_emit`` 改直引 ``type_pred``
- [x] ``test_type_node`` 增加 ``test_invokable_type_predicate``
- [x] ``build-all.bat`` **129/129** 验证

**仍故意留在 `ir`**：``cpp_template_inner_args`` 等 C++ 文本切分原语；``format_cpp_callable_var_decl``（``is_callable_type`` 依赖，无 TypeNode 形态）。

### Phase 10 — passes/emit 字段 C++ 读路径收口（已完成，129/129）

- [x] ``class_decl_emit._generator_has_embedded_container`` 改 ``field_storage_values``（不再扫 ``field_types.values()``）
- [x] ``field_properties`` / ``descriptors`` / ``move_state`` / ``mixins`` 字段迁移改 ``field_ann_ast`` + ``write_field_storage``
- [x] ``test_type_node`` 增加 ``test_field_storage_values_node_only``
- [x] ``build-all.bat`` **129/129** 验证

### Phase 11 — `write_field_ann_ast` + 早期 pass / `ClassInfo` 解析收口（已完成，129/129）

- [x] ``type_emit`` 新增 ``write_field_ann_ast`` / ``clear_field_ann_ast``（``__ann__*`` 唯一写口，与 ``field_ann_ast`` 成对）
- [x] ``ir.ClassInfo`` 字段登记、``dataclass_expand``、``enum_expand`` / ``class_type_if`` 清空改经 ``write_field_*``
- [x] ``analyzer.resolve_class_field_types`` 解析后 ``clear_field_ann_ast``
- [x] passes 残余 ``__ann__`` 直写改 ``write_field_ann_ast``
- [x] ``test_type_node`` 增加 ``test_write_field_ann_ast_roundtrip``
- [x] ``build-all.bat`` **129/129** 验证

### Phase 12 — 签名/工具链读路径收口（已完成，129/129）

- [x] ``nav_index`` 私有字段过滤改 ``field_ann_ast`` + ``field_storage_cpp``
- [x] ``mixins`` 不再复制 mixin 的 stale ``field_types`` C++ 字符串缓存
- [x] 译器单测改经 ``sig_return_storage_cpp`` 断言返回类型
- [x] ``test_type_node`` 增加 ``test_sig_return_storage_cpp_ignores_stale_ret_lead``
- [x] ``build-all.bat`` **129/129** 验证

### Phase 13 — 签名 node-first：返回类型 AST 优先 + 缓存由 sync 填充（已完成，129/129）

- [x] ``SignatureBuilder`` 新增 ``_return_type_node_from_*_annotation``（注解 AST → ``TypeNode``，与 ``ret_lead`` reconcile）
- [x] ``build_method_sig`` / ``build_function_sig`` / property getter/setter：``ret_lead``/``param_types`` 空壳 + ``sync_sig_cache`` 填充
- [x] ``test_type_node`` 增加 ``test_return_type_node_from_method_annotation``
- [x] ``build-all.bat`` **129/129** 验证

### Phase 14 — ``FUNCTION_PTR`` TypeNode + 可调用谓词 node 化（已完成）

- [x] ``TypeKind.FUNCTION_PTR`` + ``TypeNode.function_ptr`` + ``render`` / ``structural_match``
- [x] ``type_node_from_cpp_string`` 解析 ``Ret (*)(Args…)``（``split_cpp_param_list``）
- [x] ``is_callable_type(TypeNode)``；``format_callable_var_decl_from_node``（``ir.py``）
- [x] 单测：函数指针 roundtrip + ``is_callable_type`` / ``is_invokable_type`` on node

### Phase 15 — 字段 C++ 字符串缓存移除（已完成）

- [x] ``write_field_storage`` 仅写 ``field_type_nodes``；``field_types`` 只保留 ``__ann__*`` AST 占位
- [x] ``field_storage_cpp`` / emit 读路径已只认 node（stale ``field_types[field]`` 不再写入）

### Phase 16 — type-if 匹配优先 ``pattern_node``（已完成）

- [x] ``_type_matches_pattern``：``pattern_node`` 存在时用 ``structural_match_type_nodes`` / ``type_nodes_equal``，不再二次 ``from_cpp_string(pattern)``

### Phase 17 — 分析层 node-first 续（已完成）

- [x] ``_parse_ann_storage_type_node``（注解 AST → 存储 ``TypeNode``）
- [x] ``resolve_class_field_types`` 主路径：AST → node，``resolve_self`` 分歧时才字符串桥接
- [x] ``_function_param_type_nodes`` 不再依赖 ``format_function_params`` 的 ``param_types`` 中间 dict
- [x] ``class_type_if._resolve_spec_field_types`` 改 ``_parse_ann_storage_type_node``

**仍保留的字符串层（emit 边界 / 刻意）**：

| 层 | 说明 |
|----|------|
| ``MethodSig/FunctionSig.ret_lead`` / ``param_types`` | ``sync_sig_cache`` 渲染缓存；读路径经 ``type_emit`` 只认 node |
| ``translator.scope.param_types`` / ``var_types`` | ``bind_scope_var`` / ``bind_scope_param`` 双写；读经 ``scope_storage_cpp`` |
| ``type_node_from_cpp_string`` | slice/stack 数组、条件别名、WeakRef/Generator 等特殊 C++ 片段 |
| ``parse_type_node`` 回退 | 复杂 AST（``IterResult``/``Result``/``slice[T]``/NTTP 等）仍 ``_UseCppStringBridge`` |

### Phase 18 — AST 直 lower + refcount node 化（已完成）

- [x] ``type_parse_ast.py``：``parse_type_node_direct``（Name/Subscript/Tuple/Optional/Function/Callable/Pointer…）
- [x] ``parse_type_node`` / ``parse_storage_type_node`` 优先直 lower，失败回退 ``parse_type`` + ``from_cpp_string``
- [x] ``apply_refcount_storage_type_node``；``apply_full_storage_type_node`` 全程 TypeNode（无 refcount 字符串 roundtrip）
- [x] 单测：多注解 parity + storage parity

### Phase 19 — emit 作用域 ``param_type_nodes``（已完成）

- [x] ``Scope.param_type_nodes`` / ``var_type_nodes``；``bind_scope_param`` / ``scope_storage_cpp``
- [x] ``class_emit`` / ``translator`` 模块函数入口双写 node
- [x] ``class_type_if`` / ``genexp_call_emit`` 形参入口 ``bind_scope_param``

### Phase 20 — 作用域读路径 node-first（已完成）

- [x] ``lookup_scope_storage_cpp`` / ``lookup_scope_type_node`` / ``scope_binding_storage_cpp`` / ``scope_has_param``
- [x] ``translator`` 读路径经 ``_scope_storage`` / ``_scope_type_node``（不再直读 ``var_types`` / ``param_types``）
- [x] emit 热路径（``call_emit`` / ``subscript_emit`` / ``literal_ctor_emit`` / ``loops_emit`` / ``lazy_param_emit`` / ``variadic_template_emit`` / ``delegate_emit`` / ``raise_emit`` / ``builtin_aggregate_emit``）经 ``scope_storage_cpp`` 或 ``scope_binding_storage_cpp``
- [x] 单测：``TestTypeNodePhase20ScopeStorage``（stale 字符串缓存 vs node 优先）

### Phase 21 — 作用域写入双写 + 迁移收官（已完成）

- [x] ``bind_scope_var`` / ``bind_scope_vararg`` / ``scope_type_node_from_cpp``：局部/推断类型写入双写 ``var_type_nodes``
- [x] ``bind_scope_param`` 统一经 ``bind_scope_var``；``snapshot_scope_type_bindings`` / ``restore_scope_type_bindings``
- [x] 全仓库 ``scope.var_types[…] =`` 直写改 ``bind_scope_var``（``moved_use_check`` 分析 pass 除外）
- [x] ``scope_all_storage_bindings`` 替代 ``param_types`` ∪ ``var_types`` 字符串合并
- [x] ``build-all.bat`` **129/129**

---

## 5.1 迁移完成态（2026-06）

**单一真相源**：``TypeNode``（``field_type_nodes`` / ``param_type_nodes`` / ``return_type_node`` / ``scope.*_type_nodes``）。

**仍保留的 C++ 字符串**（仅 **render 缓存** 或 **不可结构化** 形态，**禁止**作为读路径主源）：

| 层 | 说明 |
|----|------|
| ``MethodSig/FunctionSig.ret_lead`` / ``param_types`` | ``sync_sig_cache`` 由 node 渲染；读经 ``type_emit`` |
| ``Scope.var_types`` / ``param_types`` | ``bind_scope_var`` / ``bind_scope_param`` 同步；读经 ``scope_storage_cpp`` |
| ``field_types`` | 仅 ``__ann__*`` AST 占位 |
| ``type_node_from_cpp_string`` | 桥接：slice/stack 数组、条件别名、WeakRef/Generator 等 |
| ``parse_type_node`` 回退 | ``IterResult``/``Result``/``slice[T]``/NTTP 等 ``_UseCppStringBridge`` |
| ``auto`` / 空类型 | 无 ``TypeNode``；读路径字符串 fallback |

**无后续 Phase**：新类型能力直接在 ``TypeNode`` / ``type_parse_ast`` 扩展，勿再引入平行字符串类型表。

---

## 6. 暂不实现

- 表达式级完整类型推断（超出现有 `decltype` 链）
- 用户可见 Python / 标准库 API 变更
- 运行时 TypeNode

---

## 7. 验证

Phase 0 译器单测：

```bat
python -m unittest src.tests.test_type_node src.tests.test_boxing_storage -q
```

Phase 1+ 触达集成测：

```bat
build.bat lang/test_type_if util/test_dict --seq
```

---

## 8. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-15 | 初稿：三层模型、模块布局、Phase 0–3 |
| 2026-06-19 | Phase 3 完成：``type_emit``、emit 收口、``type_node_from_cpp_string`` 引用修复 |
| 2026-06-19 | Phase 6 启动：``type_pred``、核心 ``is_cpp_*`` 委托、``field_type_node`` |
| 2026-06-19 | Phase 6 核心：`type_pred` 剥离语义对齐 ``strip_cpp_ref``；``build-all`` 129/129 |
| 2026-06-19 | Phase 6 续：invokable 谓词、`type_extract` 提取 API、`param_type_node` |
| 2026-06-19 | Phase 6 完成：erased/callable 谓词、dict 提取、emit 热路径 node 化 |
| 2026-06-15 | Phase 7：删除 ``is_cpp_*`` façade；``type_emit`` 只读 node；``type_pred``/``type_extract`` 为公开 API |
