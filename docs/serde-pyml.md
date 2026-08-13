# py2cpp.serde.pyml（PyML）设计

## 1. 目标与边界

`py2cpp.serde.pyml` 定义新的标记语言 **PyML**（Py2Cpp Markup Language），面向游戏配置、UI 主题、关卡参数与插件清单等存在重复和按环境差异生成的场景。PyML 是受限、确定性、Py2Cpp 风格的模板标记语言；它展开为普通 YAML，再交给 `py2cpp.serde.yaml.Yaml` 和 `py2cpp.serde.json.Json` 完成静态类型解码。

PyML 不是 Sass 方言，也不是可执行 Python：它只借用 Py2Cpp 的表达式、控制流与调用习惯，最后输出普通 YAML。`py2cpp.serde.yaml` 因此保持纯 YAML；PyML 不会改变 `Yaml.loads[T]` 的行为。

```text
.pyml / PyML 字符串
        │
        ▼
Pyml.expand(...)
  ├─ 指令树解析
  ├─ 作用域、表达式、可调用片段求值
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
- 不引入 CSS selector、媒体查询或 Sass 选择器语义；`@expand` 只表示容器值展开；
- 不改变 YAML anchor、alias、merge 的原有语义；
- 不构造循环对象图或跨文档 alias；
- 不让模板指令隐式出现在 `Yaml.loads[T]` 中；模板输入必须显式使用 `Pyml`。

## 2. 对外 API

所有 PyML API 属于 `Pyml` 类，不增加模块级函数。YAML 读写 API 仍只属于 `Yaml` 类。

```python
from py2cpp.serde.pyml import Pyml, PymlContext

expanded: str = Pyml.expand(source)
config: GameConfig = Pyml.loads[GameConfig](source)
config: GameConfig = Pyml.loads[GameConfig](source, context)
config: GameConfig = Pyml.load[GameConfig](file, context)
```

建议增加：

```python
@copyable
class PymlContext:
  # 模板根作用域中的只读宿主值。
  # set(name, value) 仅接受 YAML 标量、list、dict。
  ...

class PymlError(Exception):
  pass
```

语义：

- `Yaml.loads[T]` / `Yaml.load[T]`：只接受普通 YAML；
- `Pyml.expand(source[, context]) -> str`：只做 PyML 展开，返回普通 YAML；
- `Pyml.loads[T]`：先 `expand`，后调用 `Yaml.loads[T]`；
- `Pyml.load[T]`：读取文件后执行 `Pyml.loads[T]`；
- PyML 文件扩展名为 `.pyml`；`.yaml` / `.yml` 保持纯 YAML 的约定。

## 3. 基本语法

### 3.1 变量：`$name`

模板用户符号一律使用 `$` 前缀：变量、`@def` 标量函数、`@inline` 容器片段及其参数均如此；普通 YAML mapping key 不带 `$`。

```yaml
$asset_root: "assets/ui"
$scale: 2
$enabled: true
$presets:
  low: 512
  high: 2048
```

`$name: value` 的 `value` 按 YAML 字面量解析，不进入表达式求值：字符串、数值、bool、null、flow sequence、block mapping、anchor / alias 均按 YAML 原有规则处理。

变量读取只在模板表达式、f-string、动态 key、控制流、`@def` / `@inline` 参数中有效。普通 YAML 文本中的 `$name` 不自动替换。

`@from` 直接将导出的用户符号绑定到当前作用域；导入的变量、`@def` 函数和 `@inline` 容器片段均保持 `$` 前缀，例如 `$button("开始")`、`$config`。

### 3.2 表达式：`= expr`

等号只表示“此值必须按模板表达式求值”。字面量赋值**不写**等号。

```yaml
$asset_root: "assets/ui"       # YAML 字面量
$scale: 2                       # YAML 字面量
$size: = 256 * $scale           # 模板表达式
$scale: += 1                    # 模板增强赋值

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
- 标量函数 `$name(...)`，以及通过 `@from` 绑定到当前作用域的导入符号；
- f-string：`f"prefix_{$name}"`。

禁止任意属性访问、任意函数调用、导入、lambda、生成器和副作用表达式；仅允许本节列出的标量函数、容器查询和控制流辅助函数。容器片段不可作为标量表达式调用。允许的上下文对象字段应由 `PymlContext` 白名单注册。

### 3.3 增强赋值

PyML 支持模板变量的增强赋值，右侧始终按表达式求值，不写额外的 `=`：

```yaml
$count: 0
$count: += 1
$count: *= 2

$name: "ui"
$name: += "_debug"

$items: ["core"]
$items: += ["diagnostics"]
```

首期支持 `+=`、`-=`、`*=`、`/=`、`%=`，其操作语义与对应的受限 Py2Cpp 表达式一致：

- 数值支持全部五种运算；
- `str` 支持 `+=`；
- `list` 支持与同元素类型 list 的 `+=`；
- 不支持的操作数类型组合、除以零和非整除的整数 `/=` 必须抛 `PymlError`；
- 增强赋值不会创建变量：当前作用域及其可见外层作用域均不存在 `$name` 时抛 `PymlError`；
- 命中外层变量时在当前子作用域创建遮蔽后的新绑定，不回写外层作用域。

### 3.4 作用域与赋值

`$name: value` 和 `$name: = expr` 都遵循同一条规则：当前作用域不存在变量时初始化，已存在时重新赋值。

- 文档根作用域：该文档全局可见；
- 可调用片段求值、`@if` 分支、`@for` 每轮：创建子作用域；
- 子作用域读取外层变量；
- 子作用域赋值默认只改子作用域，避免循环与片段调用污染调用方；

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

### 4.3 标量函数：`@def` 与 `@return`

`@def` 用于定义返回标量的用户函数，函数名及参数必须使用 `$` 前缀。`@return` 后直接写表达式，不写 `=`：

```yaml
@def $sum_to($n):
  $s: 0
  @for $i in range($n + 1):
    $s: += $i
  @return $s

total: = $sum_to(10)
```

标量函数的主体只允许局部变量声明/赋值、增强赋值、`@if`、`@for` 和 `@return`；不得直接输出 YAML mapping 或 sequence 节点，也不得使用 `@expand`。函数调用建立独立的调用作用域，局部变量与循环变量均不会泄漏到调用方。

为符合 Python 的函数局部作用域，`@if` 与 `@for` 的函数体共享当前函数调用作用域；因此示例中的 `$s: += $i` 会持续更新同一次调用内的 `$s`，而非每轮创建一个不可见副本。`@return` 会立即结束当前函数调用；若执行抵达函数末尾仍未返回、`@return` 出现在 `@def` 外部，或返回 list / mapping，则必须抛 `PymlError`。首期返回值限于 `str`、整数、浮点、bool 或 null。

标量函数与容器片段共用用户符号命名空间，不可同名。只有标量函数可出现在 `= expr`、条件、循环 iterable 与参数表达式中；容器片段只能作为 `@expand` 的操作数。

## 5. 容器组合：`@expand`

`@def` 保留给上一节的标量函数；可复用容器片段则以带 `$` 前缀的声明定义，并统一通过 `@expand` 写入目标容器：所在容器是 mapping 时执行 Python `dict.update` 的浅更新；所在容器是 sequence 时执行 Python `list.extend` 的按序插入。

### 5.1 容器片段：`@inline`

容器片段必须以 `@inline $name(args):` 声明，参数也必须带 `$` 前缀；调用采用受限 Py2Cpp / Python 习惯。它和 `@def` 一样可使用局部变量、增强赋值、`@if`、`@for`，但不使用也不允许 `@return`。执行结束后，主体中所有非 `$` 开头的 mapping 项或 list 项按源顺序组成结果容器；首个此类元素决定结果为 mapping 或 sequence，二者不可混用。

```yaml
@inline $button($text, $color: "#3b82f6"):
  text: = $text
  color: = $color
  padding: [12, 8]
  font:
    size: 16

@inline $base_plugins():
  - core
  - input
```

局部变量、条件和循环本身不形成结果元素；它们展开出的普通 key/value 或 `- item` 才形成结果。例如：

```yaml
@inline $enabled_plugins($debug):
  $base: ["core", "input"]
  @for $plugin in $base:
    - = $plugin
  @if $debug:
    - diagnostics

plugins:
  @expand $enabled_plugins(true)
```

`$base` 只是局部变量，不会出现在结果中；`$enabled_plugins(true)` 的值为 `["core", "input", "diagnostics"]`。

`@inline` 的执行作用域与 `@def` 相同：局部变量、分支和循环共享同一次调用作用域，且不会泄漏到调用方。`$` 开头的 mapping 项只作为局部变量绑定，绝不进入结果；条件和循环展开后产生的每个非 `$` 开头 mapping 项或每个 list 项，才按源顺序收集为结果。默认参数是 YAML 字面量时不写 `=`，需要计算时才写 `= expr`。调用参数在独立的子作用域中绑定，并捕获定义处词法作用域。

### 5.2 mapping 内部：`@expand expr`

`@expand` 是 mapping 子项位置的展开语句，必须与该字典的普通元素保持相同缩进。它的操作数必须求值为 mapping，并在出现位置按 Python `dict.update` 的**浅更新**语义写入当前字典。

```yaml
$button_defaults:
  color: "#3b82f6"
  padding: [12, 8]

confirm:
  @expand $button_defaults
  text: "确认"
  id: confirm_button
```

等价于：

```python
confirm = {**button_defaults, "text": "确认", "id": "confirm_button"}
```

`@expand` 不要求出现在最前面；顺序就是覆盖顺序：

```yaml
confirm:
  text: "本地文本"
  @expand $button_defaults
```

等价于：

```python
confirm = {"text": "本地文本", **button_defaults}
```

因此 `$button_defaults` 中的同名 `text` 会覆盖先前的本地 `text`。PyML 展开器按源顺序执行，并在输出普通 YAML 前折叠为唯一 key 的 mapping。

`@inline` 也可作为操作数：

```yaml
ui:
  start:
    @expand $button("开始")
    id: start_button
```

在 mapping 中，`@expand` 严格遵循 Python `dict.update`：同名字段一律由后写入的值整体覆盖；嵌套 mapping 不递归合并。需要组合嵌套 mapping 时，在该嵌套 mapping 内再次使用 `@expand`。

### 5.3 sequence 内部：`@expand expr`

`@expand` 是 sequence 子项位置的展开语句，必须与 `- item` 保持相同缩进。它的操作数必须求值为 list，并在出现位置按 Python `list.extend` 语义追加所有元素。

```yaml
plugins:
  - bootstrap
  @expand $base_plugins()
  - diagnostics
  - editor_tools
```

等价于：

```python
plugins = ["bootstrap", *base_plugins(), "diagnostics", "editor_tools"]
```

`@expand` 同样可出现在任意位置，且可以多次出现；每次都按源顺序插入列表元素。

### 5.4 共同规则

```text
<indent>@expand <expr>     # mapping 中展开 mapping；sequence 中展开 list
```

- `@expand` 的结果必须匹配当前容器：mapping 中必须是 mapping，sequence 中必须是 list；
- 操作数可为 `$value`、`@inline $name(args)` 的结果、无参 `@inline $name()` 的结果、受限下标访问，或通过 `@from` 绑定的导入符号；
- mapping 中，`@expand` 可与普通 `key: value` 任意交错；sequence 中，`@expand` 可与 `- value` 任意交错；
- 同一容器可多次使用 `@expand`，但 mapping 与 sequence 元素不可混用；
- `@expand` 标记不进入展开后的 YAML；
- 函数调用或容器组合出现递归链时抛 `PymlError`，显示例如 `$button() → $panel() → $button()` 的调用链；
- 普通 YAML `<<: *anchor` 保持独立语义，在 PyML 展开完成后才由 YAML parser 处理。
## 6. 模块导入

模块使用 Python 风格的模块路径按符号导入，也不接受字符串文件路径。

```yaml
@from .ui.button import $button, $button_style as $primary_button_style
@from .game.defaults import $config as $default_config

ui:
  start:
    @expand $button("开始")
    style: = $primary_button_style
    id: start_button

game:
  @expand $default_config()
  title: "默认游戏"
```

导入语法为：

```text
@from [.]name(.name)* import $name [as $alias] (, $name [as $alias])*
@from [.]name(.name)* import *
```

规则：

- `.ui.buttons` 是相对当前 PyML 模块所在包的导入；例如当前模块为 `game.main` 时，它解析为 `game.ui.buttons`；
- `..shared.colors` 允许向上一级包，再导入 `shared.colors`；不得越过配置模块根；
- `ui.buttons` 是从 `PymlContext.module_root` 解析的绝对逻辑模块路径；
- 规范逻辑模块路径的 `.` 映射为目录分隔符，末段映射为 `.pyml` 文件，例如 `game.ui.buttons` → `game/ui/buttons.pyml`；
- 显式导入支持逗号分隔的多个名称；每个 `$name` 可选写作 `$name as $alias`。源名称与别名均必须带 `$`；
- 显式导入将模块根层导出绑定到当前作用域；导出可以是变量、`@def` 标量函数或 `@inline` 容器片段；使用 `as` 时只绑定别名；
- `import *` 将该模块全部根层导出绑定到当前作用域，且必须单独使用，不能与显式名称或 `as` 混用；
- 导入后的绑定名与当前作用域或同一文档先前导入的符号重名时抛 `PymlError`，不允许覆盖；
- 一个模块只展开一次并按规范模块路径缓存；
- 检测导入环，并在异常中给出完整模块链，例如 `game.main → game.ui.buttons → game.main`；
- 文件 IO 只在 `Pyml.load` / `Pyml.expand_file` 路径启用；字符串 `Pyml.loads` 只有在 `PymlContext` 同时提供当前模块名、`module_root` 和允许根目录时才允许 `@from`。

`PymlContext` 需要增加模块解析信息：

```python
@copyable
class PymlContext:
  module_name: str = ""
  module_root: Path = Path()
  allowed_root: Path = Path()
```

路径解析必须先将 Python 模块路径标准化为逻辑模块名，再映射到文件系统；禁止接受 `../`、反斜杠、盘符、绝对路径或扩展名作为 `@from` 的输入。
## 7. 解析与实现架构

在 `py2cpp/serde/pyml.py` 中分层实现，复用现有 `_strip_comment`、缩进分析、引用处理和 YAML parser；不在 `serde.json` 中增加模板语义。

```text
Pyml
 ├─ expand(source, context) -> str
 ├─ loads[T](source, context) -> T
 └─ load[T](fp, context) -> T

_PymlLexer
 ├─ 保留缩进、行列、字符串、注释边界
 └─ 识别 $name、= expr、@if/@for/@expand/@from

_PymlParser
 └─ 以缩进构造模板节点树

_PymlExprParser / _PymlExprEvaluator
 ├─ 受限表达式 AST
 ├─ 变量与上下文读取
 └─ 无副作用求值

_PymlExpander
 ├─ Scope 链
 ├─ 可调用片段与组合调用链
 ├─ 条件、循环、容器组合
 └─ 输出普通 YAML 行列表
```

实现必须先得到“普通 YAML 字符串”，再调用既有 `_YamlParser.parse()`；不直接把模板节点混入 `_YamlParser` 的 JSON 规范化流程。

## 8. 错误模型与诊断

新增 `PymlError(Exception)`，至少记录：

- 文件路径（字符串模板可记为 `<string>`）；
- 行号、列号；
- 当前指令与原始行；
- 可调用片段与容器组合调用链；
- `@from` 导入链；
- 变量、可调用片段、模块或容器组合目标名称。

典型错误：

- 未定义 `$name`；
- `= expr` 使用了不允许的语法或类型；
- `@if` / `@for` 子树缩进非法；
- 可调用片段的参数数量、名称或类型不匹配；
- 递归可调用片段或容器组合；
- `@expand` 的结果与当前 mapping / sequence 容器类型不匹配；
- 动态 key 求值后不是 scalar；
- 相对模块导入越过允许根目录，或模块路径不符合 Python 路径语法；
- 模块导入环。

## 9. 实施阶段

### 阶段 0：稳定 YAML 基座

- 补齐并回归 flow mapping、复杂引用字符串、错误位置；
- 确保 anchors / aliases / merge、多文档、块标量与递归 JSON 容器的现有测试稳定；
- 不在模板层绕过 YAML parser 已知问题。

### 阶段 1：表达式和变量

- `PymlContext`；
- `$x: literal`、`$x: = expr`、`$x: += expr` 等增强赋值、`key: = expr`、`= expr:`；
- 受限表达式 AST 与 f-string；
- `Pyml.expand` 与 `Pyml.loads[T]`。

### 阶段 2：条件与循环

- `@if` / `@elif` / `@else`；
- `@for $x in iterable`、`range`、`.items()` 解包；
- 子作用域与循环输出顺序。

### 阶段 3：可调用片段与容器组合

- `@def $name(args):` 标量函数及 `@inline $name(args):` 容器片段定义；
- 参数、默认值、关键字参数、词法作用域；
- 容器内部 `@expand expr` 的 mapping / sequence 分派与调用环检测。

### 阶段 4：模块

- `@from .package.module import $x, $y as $w` / `import *`、模块路径解析与根目录限制；
- 缓存、显式导出、导入环诊断；
- `Pyml.load` 文件入口。

### 阶段 5：工程化

- 格式化后的展开 YAML 输出；
- 文档、示例和性能基准；
- 错误定位与 stack trace 完整性。

## 10. 测试矩阵

新增 `test/serde/test_pyml.py`，覆盖：

- `$x: literal`、`$x: = expr` 与 `$x: += expr` 等增强赋值的区分；
- 表达式值、动态 key、f-string、非法表达式；
- 根作用域、分支作用域、循环作用域、遮蔽，以及增强赋值不回写外层作用域；
- `@if` / `@elif` / `@else` 的 mapping、sequence 子树；
- `@for` 的 list、dict `.items()`、`range`、解包与空迭代；
- `@def $name(args):` 标量函数与 `@inline $name(args):` 容器片段的默认参数、关键字参数、嵌套调用与递归诊断；
- 标量函数的局部变量、循环累积、提前 `@return`、缺少返回、返回容器与函数外 `@return` 的诊断；
- 容器内部 `@expand expr` 的按序浅覆盖或按序插入、类型不匹配、动态 key 与调用环；
- `@from .package.module import $x, $y as $w` / `import *` 的相对/绝对解析、缓存、别名绑定、导入冲突、模块根越界拒绝与导入环；
- 展开后 YAML 与 `@serializable`、嵌套 `dict` / `list` JSON bridge 的集成；
- 纯 `Yaml.loads[T]` 遇到 PyML 指令必须失败；`Pyml.loads[T]` 才允许展开。

每个阶段完成后必须执行 runtime bootstrap，并至少运行：

```bat
build serde\test_yaml.py serde\test_pyml.py serde\test_json.py --seq
run serde\test_yaml.py serde\test_pyml.py serde\test_json.py
```

涉及类型条件分派时，额外运行：

```bat
build lang\test_type_if.py --seq
run lang\test_type_if.py
```
