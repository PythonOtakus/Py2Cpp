# py2cpp.serde.yaml 模板扩展设计

## 1. 目标与边界

`py2cpp.serde.yaml` 现有职责是把 YAML 1.2 常用子集规范化为 JSON，再通过 `py2cpp.serde.json.Json` 解码为静态类型对象。本设计在其上增加一个**受限、确定性、Py2Cpp 风格的模板预处理层**，面向游戏配置、UI 主题、关卡参数、插件清单等存在重复和按平台差异生成的场景。

模板层不是 Sass 方言，也不是可执行 Python：它只借用 Py2Cpp 的表达式、控制流与调用习惯，最后输出普通 YAML。模板展开完成后继续走现有 YAML parser 和 JSON bridge；不会改变 `Yaml.loads[T]` 的纯 YAML 行为。

```text
.yamlpp / 模板字符串
        │
        ▼
Yaml.expand(...)
  ├─ 指令树解析
  ├─ 作用域、表达式、模板调用
  └─ 输出普通 YAML
        │
        ▼
现有 _YamlParser
        │
        ▼
Json.loads[T]
```

### 不做的事情

- 不执行任意 Python / Py2Cpp 函数，不提供 `eval`；
- 不引入 CSS selector、媒体查询、Sass `@mixin` / `@include` / `@extend` / `@use` 命名；
- 不改变 YAML anchor、alias、merge 的原有语义；
- 不构造循环对象图或跨文档 alias；
- 不让模板指令隐式出现在 `Yaml.loads[T]` 中。

## 2. 对外 API

所有 API 仍只属于 `Yaml` 类，不增加模块级 `load` / `dump` 函数。

```python
from py2cpp.serde.yaml import Yaml, YamlContext

expanded: str = Yaml.expand(source)
config: GameConfig = Yaml.loads_template[GameConfig](source)
config: GameConfig = Yaml.loads_template[GameConfig](source, context)
config: GameConfig = Yaml.load_template[GameConfig](file, context)
```

建议增加：

```python
@copyable
class YamlContext:
  # 模板根作用域中的只读宿主值。
  # set(name, value) 仅接受 YAML 标量、list、dict。
  ...

class YamlTemplateError(YamlError):
  pass
```

语义：

- `Yaml.loads[T]` / `Yaml.load[T]`：只接受普通 YAML；
- `Yaml.expand(source[, context]) -> str`：只做模板展开，返回普通 YAML；
- `Yaml.loads_template[T]`：先 `expand`，后 `loads[T]`；
- `Yaml.load_template[T]`：读取文件后执行 `loads_template[T]`；
- 模板文件推荐扩展名 `.yamlpp`；`.yaml` / `.yml` 保持纯 YAML 的约定。

## 3. 基本语法

### 3.1 变量：`$name`

模板变量使用 `$` 前缀，与普通 YAML mapping key 明确区分。

```yaml
$asset_root: "assets/ui"
$scale: 2
$enabled: true
$presets:
  low: 512
  high: 2048
```

`$name: value` 的 `value` 按 YAML 字面量解析，不进入表达式求值：字符串、数值、bool、null、flow sequence、block mapping、anchor / alias 均按 YAML 原有规则处理。

变量读取只在模板表达式、f-string、动态 key、控制流、模板参数中有效。普通 YAML 文本中的 `$name` 不自动替换。

### 3.2 表达式：`= expr`

等号只表示“此值必须按模板表达式求值”。字面量赋值**不写**等号。

```yaml
$asset_root: "assets/ui"       # YAML 字面量
$scale: 2                       # YAML 字面量
$size: = 256 * $scale           # 模板表达式

window:
  width: = 320 * $scale
  visible: = $enabled and $scale > 0
  icon: = f"{$asset_root}/icon.png"
```

mapping 的动态 key 使用 `= expr:`：

```yaml
$platform: "windows"

builds:
  = $platform:
    executable: "game.exe"
```

表达式采用受限 Py2Cpp 风格：

- `$name` 变量引用；
- 字符串、整数、浮点、布尔、null、list、dict 字面量；
- `+`、`-`、`*`、`/`、`%`；
- `==`、`!=`、`<`、`<=`、`>`、`>=`；
- `and`、`or`、`not`；
- 条件表达式 `a if condition else b`；
- 下标、`.items()`、`.keys()`、`.values()`、`len(...)`、`range(...)`；
- f-string：`f"prefix_{$name}"`。

禁止任意属性访问、任意函数调用、导入、lambda、生成器和副作用表达式。允许的上下文对象字段应由 `YamlContext` 白名单注册。

### 3.3 作用域与赋值

`$name: value` 和 `$name: = expr` 都遵循同一条规则：当前作用域不存在变量时初始化，已存在时重新赋值。

- 文档根作用域：该文档全局可见；
- `@def` 调用、`@if` 分支、`@for` 每轮：创建子作用域；
- 子作用域读取外层变量；
- 子作用域赋值默认只改子作用域，避免循环与模板调用污染调用方；
- 如后续确有需要，再单独设计显式的 `@setglobal`，首期不提供隐式向上写入。

## 4. Py2Cpp 风格控制流

`@` 仅是 YAML 文件中识别模板节点的前缀；后半部分采用 Python / Py2Cpp 控制流风格。

### 4.1 条件

```yaml
$debug: true

plugins:
  - core
  @if $debug:
    - diagnostics
  @else:
    - release_metrics
```

支持：

```yaml
@if expr:
@elif expr:
@else:
```

分支指令只能作为完整 mapping 或 sequence 节点出现，不能嵌入 scalar。

### 4.2 循环

```yaml
$platforms: ["windows", "linux"]

builds:
  @for $platform in $platforms:
    = $platform:
      executable: = "game.exe" if $platform == "windows" else "game"
```

支持 Py2Cpp 常用形态：

```yaml
@for $i in range(1, 4):
@for $name, $size in $presets.items():
@for $value in $values:
```

不使用 Sass 的 `from ... through ...`、list separator 或 map loop 特殊规则。循环变量每轮局部绑定，循环体输出按原顺序拼接到当前 mapping 或 sequence。

## 5. 可复用子树

### 5.1 `@def` 与 `@apply`

`@def` 定义 YAML 子树模板，`@apply` 在当前位置展开它。名称、参数调用和关键字参数使用 Py2Cpp / Python 习惯；模板变量仍使用 `$` 前缀。

```yaml
@def button($text, $color: "#3b82f6"):
  text: = $text
  color: = $color
  padding: [12, 8]
  font:
    size: 16

ui:
  start_button:
    @apply button("开始")
  exit_button:
    @apply button("退出", "#ef4444")
```

规则：

- `@def` 只能位于文档根 mapping；
- `@apply` 只能作为完整节点，模板结果必须能合并到当前位置；
- 参数默认值若是字面量按 YAML 字面量规则读取；若要计算，写 `$param: = expr`；
- 支持位置参数和关键字参数，但不支持 `*args`、`**kwargs`；
- 模板捕获定义处词法作用域，调用参数在新子作用域内覆盖捕获变量；
- 维护调用栈，检测 `A → B → A` 等递归展开并抛 `YamlTemplateError`。

### 5.2 深合并：`@merge`

`@merge` 是模板阶段的配置复用，不等同于 YAML 的 `<<`。它接受已展开的 mapping 路径并执行深合并。

```yaml
$button_defaults:
  padding: [12, 8]
  font:
    size: 16
    weight: bold

ui:
  confirm:
    @merge $button_defaults
    text: "确认"
    font:
      color: white
```

结果：

```yaml
ui:
  confirm:
    padding: [12, 8]
    text: "确认"
    font:
      size: 16
      weight: bold
      color: white
```

合并规则：

1. mapping 与 mapping：递归合并；
2. 当前节点值覆盖被合并节点值；
3. scalar 与 sequence：整体覆盖，不做元素级合并；
4. 可写多个 `@merge`，按出现顺序处理，后合并者优先；
5. 检测 `$` 变量 / 模板对象的间接循环。

普通 YAML `<<: *anchor` 保持在展开后由现有 YAML parser 按原语义处理。

## 6. 模块导入

模块使用 Python 风格的 `@import`，不用 Sass `@use` / `@forward`。

```yaml
@import "ui/buttons.yamlpp" as buttons
@import "game/defaults.yamlpp" as defaults

ui:
  start:
    @apply buttons.button("开始")

game:
  @merge defaults.config
```

模块规则：

- 路径必须为相对路径，标准化后不得逃出调用方配置根目录；
- 一个模块只展开一次并缓存；
- 导入绑定仅暴露模块的显式导出名称；
- 首期导出约定为根层 `@def` 与 `$name`；
- 检测导入环，并在异常中给出完整 `A.yamlpp → B.yamlpp → A.yamlpp` 链；
- 文件 IO 只在 `load_template` / `expand_file` 路径启用；字符串 `loads_template` 不隐式允许 import，除非提供了基准路径与允许根目录。

## 7. 解析与实现架构

在 `py2cpp/serde/yaml.py` 中分层实现，复用现有 `_strip_comment`、缩进分析、引用处理和 YAML parser；不在 `serde.json` 中增加模板语义。

```text
Yaml
 ├─ expand(source, context) -> str
 ├─ loads_template[T](source, context) -> T
 └─ load_template[T](fp, context) -> T

_YamlTemplateLexer
 ├─ 保留缩进、行列、字符串、注释边界
 └─ 识别 $name、= expr、@if/@for/@def/@apply/@merge/@import

_YamlTemplateParser
 └─ 以缩进构造模板节点树

_YamlExprParser / _YamlExprEvaluator
 ├─ 受限表达式 AST
 ├─ 变量与上下文读取
 └─ 无副作用求值

_YamlTemplateExpander
 ├─ Scope 链
 ├─ def / apply 调用栈
 ├─ 条件、循环、深合并
 └─ 输出普通 YAML 行列表
```

实现必须先得到“普通 YAML 字符串”，再调用既有 `_YamlParser.parse()`；不直接把模板节点混入 `_YamlParser` 的 JSON 规范化流程。

## 8. 错误模型与诊断

新增 `YamlTemplateError(YamlError)`，至少记录：

- 文件路径（字符串模板可记为 `<string>`）；
- 行号、列号；
- 当前指令与原始行；
- `@apply` 调用栈；
- `@import` 导入链；
- 变量、模板、模块或合并目标名称。

典型错误：

- 未定义 `$name`；
- `= expr` 使用了不允许的语法或类型；
- `@if` / `@for` 子树缩进非法；
- `@apply` 参数数量、名称或类型不匹配；
- 递归 `@apply`；
- `@merge` 目标不是 mapping；
- 动态 key 求值后不是 scalar；
- 相对 import 越过允许根目录；
- 模块导入环。

## 9. 实施阶段

### 阶段 0：稳定 YAML 基座

- 补齐并回归 flow mapping、复杂引用字符串、错误位置；
- 确保 anchors / aliases / merge、多文档、块标量与递归 JSON 容器的现有测试稳定；
- 不在模板层绕过 YAML parser 已知问题。

### 阶段 1：表达式和变量

- `YamlContext`；
- `$x: literal`、`$x: = expr`、`key: = expr`、`= expr:`；
- 受限表达式 AST 与 f-string；
- `Yaml.expand` 与 `Yaml.loads_template[T]`。

### 阶段 2：条件与循环

- `@if` / `@elif` / `@else`；
- `@for $x in iterable`、`range`、`.items()` 解包；
- 子作用域与循环输出顺序。

### 阶段 3：复用和深合并

- `@def` / `@apply`；
- 参数、默认值、关键字参数、词法作用域；
- `@merge` 与循环检测。

### 阶段 4：模块

- `@import`、基准路径、根目录限制；
- 缓存、显式导出、导入环诊断；
- `load_template` 文件入口。

### 阶段 5：工程化

- 格式化后的展开 YAML 输出；
- 文档、示例和性能基准；
- 错误定位与 stack trace 完整性。

## 10. 测试矩阵

新增 `test/serde/test_yaml_template.py`，覆盖：

- `$x: literal` 与 `$x: = expr` 的区分；
- 表达式值、动态 key、f-string、非法表达式；
- 根作用域、分支作用域、循环作用域和遮蔽；
- `@if` / `@elif` / `@else` 的 mapping、sequence 子树；
- `@for` 的 list、dict `.items()`、`range`、解包与空迭代；
- `@def` / `@apply` 的默认参数、关键字参数、嵌套调用与递归诊断；
- `@merge` 的深合并、优先级、非 mapping 目标和循环；
- `@import` 的正常路径、缓存、越界拒绝、导入环；
- 展开后 YAML 与 `@serializable`、嵌套 `dict` / `list` JSON bridge 的集成；
- 纯 `Yaml.loads[T]` 遇到模板指令必须失败，不得静默展开。

每个阶段完成后必须执行 runtime bootstrap，并至少运行：

```bat
build serde\test_yaml.py serde\test_yaml_template.py serde\test_json.py --seq
run serde\test_yaml.py serde\test_yaml_template.py serde\test_json.py
```

涉及类型条件分派时，额外运行：

```bat
build lang\test_type_if.py --seq
run lang\test_type_if.py
```