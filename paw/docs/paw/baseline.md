# Paw P0 / 原生编译器冻结基线

更新 2026-11-02。对应 [parser-self-hosting.md](../parser-self-hosting.md) 与 **Paw 原生编译器方案（Syntax→HIR→MidIR）**。  
**语法已实现/未实现总表**：[syntax-inventory.md](./syntax-inventory.md)。

## 1. 语言身份

| 项 | 值 |
|---|---|
| 语言名 | Paw |
| 新方言扩展名 | `*.paw` |
| 兼容入口 | `*.py`（单向 adapter → 同一 Syntax）；FFI 为 `*.paw` |
| IDE 语言 id | `paw` |
| 宿主参考语法 | CPython 3.13 |
| Schema / frontend 版本 | `paw-frontend-0.3.0` |
| HIR / MidIR 版本 | `paw-hir-0.1.0` / `paw-mid-0.1.0` |
| Bootstrap 状态 | `c1-parse-emit-link-green`（smoke+span+diag+check+srcmgr+lexer+parser+`emitEnum`） |

## 2. Bootstrap profile（编译器实现语言子集）

自举源码（`compiler/paw/**/*.paw`）使用 **Paw 表面语法**，由宿主 C0 经 Syntax→HIR→MidIR 翻译：

- 显式类型注解、普通 `class` / `def`、`enum` / `type enum` / `record` / `ref class` / `final class`
- 方法修饰用 `override def` / `virtual def` / `static def` / `native def` 等关键字
- 委托：`delegate Name[T](...) -> R`（无体）；函数指针裸箭头；槽类型 `Callable[arrow]`
- 保留规范仍列为「保持」的装饰器（如 `@copyable`、`@immutable`、`@native_name`）
- **硬关键字**：`enum` / `union`（不可作标识符；声明写 `enum Name:` / `union Name:` / `type enum` / `type union`）
- **禁止**：`@override` / `@virtual` / `@enum` / `@union` / `@dataclass` / `@refcount` / `@staticmethod` / `@final` / `@abstract` / `@delegate` / `@native`（非 `@native_name`）等已迁出旧写法；禁 `Function[[…]]` / `Callable[[…]]`
- `list` / `dict`、显式循环、稳定字符串 ID
- **禁止**：动态 `getattr`/`setattr`、裸 `Any`、任意 `exec`/`eval`、异构变长 tuple、动态 import、隐含逃逸闭包

详见 [bootstrap_profile.md](../../compiler/bootstrap_profile.md)。

## 3. 语料清单

| 集合 | 约数 | 路径 |
|---|---:|---|
| 标准库 | 153 | `paw/**/*.paw` |
| 正向测试 | ~200 | `tests/**/test_*.paw`（排除 fail/perf） |
| 负向测试 | ~37 | `tests/**/*_fail.paw` |
| 示例 | 3 | `examples/**/*.py`（尚未硬切） |
| FFI 桩 | 34 | `ffi/**/*.paw` |
| Paw 高亮预览 | 1 | `lexer_preview.paw` |
| Seed | 8+ | `compiler/paw/**` 竖切（thin c1_emit nested；emitEnum 走宿主 Mid） |

生成/刷新计数：`python tools/paw_inventory_corpus.py`。  
stdlib mid-emit 覆盖：`python tools/paw_mid_emit_coverage.py`。

## 4. 支持分层（原生路径）

| 层 | 含义 | 首期范围 |
|---|---|---|
| L0 可解析 | 原生 Lexer/Parser 产出 `SyntaxModule`（无全文 rewrite） | 声明 A/B + import/def/`delegate`/`native`；其余 `OpaqueStmt` |
| L0+ 类型表面 | `TypeSyntax`（含裸箭头、`Callable[arrow]`、`T[:]`） | 与值下标、`a @ b` 分节点；见 [debridge-roadmap.md](./debridge-roadmap.md) |
| L1 可 lowering | Binder → HIR → MidIR → `ast_from_mid` | A/B 声明 + 结构化函数体（已无 span materialize） |
| L1+ mid-emit | `can_emit_mid` → `emit_cpp` 旁路 | seed 全量；stdlib 渐进 |
| L2 暂诊断未支持 | 解析可认、语义未接通 | 完整逃逸闭包、机器码后端、PEG 双前端、模板「任意 CPython」 |

**已废弃作生产步骤**：整文件 `rewrite_paw_to_legacy` / `paw_source_to_ast`。物化仍是 **MidIR → 程序化 `ast.Module`**（非全文改写）。检查：`python tools/paw_ast_ban_checklist.py`。

## 5. 可复现输出开关

| 项 | 约定 |
|---|---|
| 换行 | 生成物统一 `\n` |
| 路径 | manifest / SourceMap 使用相对仓库根的 posix 路径 |
| 时间戳 | 对比 stage manifest 前剔除或固定生成时间字段 |
| 缓存键 | `source_digest + dialect + schema_version`（见 `src/frontend/api.py`） |
| pickle | 生产路径禁止依赖；后续版本化显式格式 |

## 6. Schema 真相源

| 层 | 路径 |
|---|---|
| Syntax | [compiler/py/frontend/schema/syntax_nodes.md](../../compiler/py/frontend/schema/syntax_nodes.md) |
| HIR | [compiler/py/hir/schema.md](../../compiler/py/hir/schema.md) |
| MidIR | `compiler/py/mid/nodes.py`（随 N2 文档化） |

## 7. 自举还差什么（摘要）

| 项 | 状态 |
|---|---|
| seed MidIR 直 emit | **完成**（含 `hir/nodes`/`mid/nodes`/`emit_cpp`） |
| stdlib `can_emit_mid` | **153/153（100%）**（见 `tools/paw_mid_emit_coverage.py`） |
| `tests/` build-all | **155/155 绿**（2026-11-02） |
| 删除 `materialize_ast` | **已删**；mid_ok **默认空树** + 回填 |
| PRIMARY | 默认仅 `compiler/paw/**`；stdlib/test 需 `MID_PRIMARY=1` |
| passes 迁出 `ast.*` | 进行中（enum/record/union/protocol/mixin Mid；其余仍 C0） |
| 模板执行器去 CPython | 未完成 |
| 编译器源码 Paw 化（完整 S） | seed 竖切 + `emit-seed`→stage1；`compiler/**/*.py` 仍宿主 |
| C0 Mid 定点 | **绿**：stage1==stage2==stage3 seed `.h/.cpp`（同宿主三次 emit） |
| C1 parse→emit→run | **绿**：薄 mid_emit nested `c1_emit/<pkg>/…`；含薄 emit 全量 `emit_cpp.paw` + **D5/D6 薄 parse→emit** + **D7 薄 reseed** |
| Py×Paw dual | **D0–D7 绿**：含 seed 薄 C1→C2→C3 定点；[dual-impl.md](./dual-impl.md) |
| C1 thin check | **绿**：薄 emit `checkModule` 重名检测链跑 |
| 真 C1→C2→C3（seed 薄栈） | **绿**：`c2_thin`≡`c3_thin`（source/lexer/parser/emit_cpp/…）；C2 span/parser 竖切；门闩 `paw_stage1_c1_link.bat` + `paw_c2_c3_thin_reseed.bat` |
| 全量自举（完整 S / 模板离 CPython） | 未通：生产仍宿主 Mid；模板执行器仍 CPython |

## 8. 已知失败 / 延后

- stdlib / 测试经 `ast_module_from_mid` 供尚未迁完的 passes；见 [debridge-roadmap.md](./debridge-roadmap.md)
- 模板执行器仍依赖宿主 CPython（见 parser-self-hosting §5）
- GPU Host/CUDA 与 Paw 前端解耦，不阻塞本基线
