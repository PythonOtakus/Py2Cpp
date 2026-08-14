# `py2cpp.serde.html` 设计方案

> **状态**：设计阶段，尚未实现。  
> **实现文件**：仅 `py2cpp/serde/html.py`。  
> **参考方向**：借鉴 Beautiful Soup 的文档树、导航、搜索与修改体验；查询复用项目既有 [`select("路径")`](selector.md) 语法；复用 PyML 的变量、条件、循环、函数、inline fragment 与模块机制生成 HTML 结构。  
> **非目标**：浏览器 DOM、CSS 布局、JavaScript、网络加载、XPath、完整 HTML5 浏览器解析器。

## 1. 定位与目标

`py2cpp.serde.html` 是一个静态 HTML 文档树库：它能将 HTML 文本解析成可安全持有、查询和修改的节点树，也能将同一棵树稳定渲染为 HTML 文本。

它适用于：

- HTML 页面、报告、邮件与静态站点生成；
- 网页片段提取、清洗与重写；
- 配置化 UI / 文档生成；
- 以 PyML 编写结构、循环和条件后生成 HTML；
- 将 HTML 作为数据格式，而不是作为浏览器运行时。

首版必须做到：

1. 解析常用且轻度不规范的 HTML；
2. 提供 Beautiful Soup 风格的 `find`、`find_all`，以及项目既有 `select("路径")` 查询；
3. 支持节点导航、增删改换与文本提取；
4. 安全且稳定地渲染 HTML；
5. 让 PyML 只负责声明式构建，不在 HTML 内新增另一套模板语法；
6. 全部逻辑落在单个 `py2cpp/serde/html.py` 中，避免第一版过早拆包。

不支持：

- JavaScript 执行、事件、shadow DOM、iframe、cookie；
- CSS selector、XPath 或浏览器布局计算；
- HTML5 全部 insertion mode、foster parenting、foreign content；
- Beautiful Soup 的任意 callable / Python regex 搜索器；
- 不安全的隐式 raw HTML 注入；
- 运行时动态 descriptor、反射或字符串字段调度。

## 2. 文件结构与公开入口

只新增：

```text
py2cpp/serde/html.py
```

文件内部按逻辑段组织：

```text
异常与诊断
节点 kind 与内部存储
HtmlDocument / HtmlNode / HtmlFragment
Tokenizer
容错 tree builder
  Html selector backend（复用既有 selector parser / emitter）
节点修改与导航
HTML renderer / escaping
PyML 到 HTML tree 的适配
Html 静态入口
```

模块级只导出类型；操作入口统一属于 `Html`：

```python
from py2cpp.serde.html import Html

document = Html.parse(source)
fragment = Html.parse_fragment(source)

output: str = Html.render(document)
pretty: str = Html.render(document, pretty=True)

text = Html.text("hello")
comment = Html.comment("generated")
element = Html.element("div")
```

不保留全局 `parse`、`render`、`escape`、`unescape` 函数，避免与其它 serde 模块和用户工具函数冲突。

## 3. 文档树、所有权与节点句柄

HTML 节点天然具有 parent/child 双向关系。若 element 直接以强引用保存 parent 和 children，会形成引用计数环；若 parent 用裸指针，文档销毁后又可能悬空。因此采用“文档唯一所有权 + 节点 ID + 强文档句柄”的模型。

```text
HtmlDocument @refcount
  ├─ 节点 arena / pool
  ├─ root 节点 ID
  ├─ warnings
  └─ 所有节点的生命周期

HtmlNode
  ├─ 强持有 HtmlDocument
  └─ node_id: uint
```

`HtmlNode` 是可复制的轻量 handle。它不直接拥有 parent 或 child；每次导航都由 document 通过 node ID 查询。

优点：

- 局部返回、容器保存、跨函数传递节点都安全；
- document 活着时节点不会悬空；
- 删除节点后只标记 detached，旧 handle 的进一步树操作会抛 `HtmlTreeError`；
- 多个 node handle 的复制不重复复制 DOM 子树；
- 文档释放时，所有仍存活 node handle 因强持有 document 而保持安全。

内部节点状态可概念化为：

```python
@enum
class HtmlNodeKind:
  Document
  Element
  Text
  Comment
  Doctype


@dataclass
class HtmlNodeState:
  kind: HtmlNodeKind
  parent: int
  first_child: int
  last_child: int
  prev_sibling: int
  next_sibling: int
  attached: bool = True
```

element、text、comment、doctype 的具体 payload 可使用 `@union` 或内部平行表实现；公共 API 不暴露其内存布局。

## 4. 公共对象 API

### 4.1 `Html`

```python
class Html:
  @staticmethod
  def parse(source: str, strict: bool = False) -> HtmlDocument: ...

  @staticmethod
  def parse_fragment(source: str, context_tag: str = "") -> HtmlFragment: ...

  @staticmethod
  def render(document: HtmlDocument, pretty: bool = False, indent: int = 2) -> str: ...

  @staticmethod
  def text(value: str) -> HtmlNode: ...

  @staticmethod
  def comment(value: str) -> HtmlNode: ...

  @staticmethod
  def element(tag: str, attrs: dict[str, str] = {}) -> HtmlNode: ...

  @staticmethod
  def from_pyml(source: str, context: dict[str, str] = {}) -> HtmlDocument: ...
```

`Html.parse` 返回完整 document；`parse_fragment` 返回可插入任意 element 的 fragment；`from_pyml` 先经 PyML 展开成受限 HTML node schema，再构造 document。

### 4.2 `HtmlDocument`

```python
class HtmlDocument:
  @property
  def root(self) -> HtmlNode: ...

  @property
  def warnings(self) -> list[HtmlWarning]: ...

  def find(self, tag: str = "", id: str = "", class_name: str = "") -> HtmlNode @optional: ...
  def find_all(
    self,
    tag: str = "",
    id: str = "",
    class_name: str = "",
    limit: int = 0,
  ) -> list[HtmlNode]: ...
```

### 4.3 `HtmlNode`

```python
class HtmlNode:
  @property
  def kind(self) -> HtmlNodeKind: ...

  @property
  def parent(self) -> HtmlNode @optional: ...

  @property
  def children(self) -> list[HtmlNode]: ...

  @property
  def tag(self) -> str: ...

  @property
  def attrs(self) -> dict[str, str]: ...

  @property
  def value(self) -> str: ...

  @property
  def text(self) -> str: ...

  @property
  def html(self) -> str: ...

  def attr(self, name: str, default: str = "") -> str: ...
  def has_attr(self, name: str) -> bool: ...
  def set_attr(self, name: str, value: str) -> None: ...
  def del_attr(self, name: str) -> None: ...

  def find(self, tag: str = "", id: str = "", class_name: str = "") -> HtmlNode @optional: ...
  def find_all(self, tag: str = "", id: str = "", class_name: str = "", limit: int = 0) -> list[HtmlNode]: ...

  def append(self, child: HtmlNode) -> HtmlNode: ...
  def prepend(self, child: HtmlNode) -> HtmlNode: ...
  def insert_before(self, node: HtmlNode) -> HtmlNode: ...
  def insert_after(self, node: HtmlNode) -> HtmlNode: ...
  def replace_with(self, node: HtmlNode) -> HtmlNode: ...
  def remove(self) -> None: ...
  def unwrap(self) -> None: ...
```

`tag`、`attrs` 只适用于 element；`value` 只适用于 text/comment/doctype。对错误 node kind 调用这些 API 必须抛 `HtmlTreeError`，不能悄悄返回空字符串掩盖错误。

## 5. 查询模型

### 5.1 `find` 与 `find_all`

提供受限、静态类型友好的 Beautiful Soup 风格查询：

```python
article = document.find("article", class_name="post")
links = document.find_all("a", class_name="download")
hero = document.find(id="hero")
```

首版只支持：

- tag 名精确匹配；
- `id` 精确匹配；
- 单一 class token 匹配；
- 可选 limit；
- document 或 node 后代范围搜索。

不支持任意 Python callable、混合类型 filter、动态 regex 或 Beautiful Soup 的 `class_` 兼容命名。结构化路径、索引、过滤和投影统一使用下节的项目 `select` 语法。

### 5.2 复用项目 `select("路径")` 语法

HTML 不引入 CSS selector，也不实现 selector 字符串的 runtime parser 或 matcher。查询调用严格复用 [selector.md](selector.md) 中唯一的语言级形态：

```python
links: list[HtmlNode] = document.select(
  ".root.children[:]{.tag == 'a' and .attrs['href'] != ''}"
)
hrefs: list[str] = document.select(
  ".root.children[:]{.tag == 'a'}.attrs['href']"
)
first_link: HtmlNode = links[0]
```

这里的 `select` 不在 `HtmlDocument` 或 `HtmlNode` 生成真实成员函数：调用点必须是一个字符串字面量，翻译器以 receiver 的静态类型选择 HTML backend，并将既有 `SelectorPlan` 直接内联为节点遍历代码。因此：

- 不接受变量、字符串拼接或 f-string 作为路径；
- 始终沿用现有 `.field`、`[index]`、`[slice]`、`['key']`、`{expr}` filter、投影、`?`、绑定和 `@sort` / `@group` / `@count` 的语义与诊断；
- 常规 `select` 结果仍是 `list[T]`，不提供 HTML 专属 `select_one`；需要单项时显式索引结果；
- 路径中的 HTML 公开字段为 `HtmlDocument.root`、`HtmlNode.parent`、`HtmlNode.children`、`HtmlNode.tag`、`HtmlNode.attrs`、`HtmlNode.value`、`HtmlNode.text` 与 `HtmlNode.html`；属性访问使用 `.attrs['href']`；
- `find` / `find_all` 保留为真实的便利方法，但不属于 selector DSL。

实现只扩展现有 `src/passes/selector_parse.py` 已产生的 `SelectorPlan` 的 emitter backend：为 `HtmlDocument` / `HtmlNode` receiver 增加 HTML 节点遍历与 handle 保活分支。不得在 `py2cpp/serde/html.py` 再写第二套 selector parser、CSS AST、matcher 或字符串解释器。

HTML backend 必须保持 selector.md 的编译期校验、类型推导与错误信息；`children` 遍历的结果按 document order 保持稳定。`parent` 是可选单节点，须经现有 `?` 可选导航规则处理。

## 6. HTML 解析

解析流水线：

```text
HTML source
  → tokenizer
  → tree builder / 常用容错恢复
  → HtmlDocument node storage
```

### 6.1 Tokenizer

P0 必须识别：

- doctype；
- 开始 tag 与结束 tag；
- 单引号、双引号、无引号属性；
- boolean attribute；
- text；
- `<!-- comment -->`；
- 命名与数字 character reference；
- `script` / `style` raw-text；
- `title` / `textarea` RCDATA；
- 常见 void tag。

void tag 固定表：

```text
area base br col embed hr img input link meta param source track wbr
```

void tag 不接受 child；渲染时不写结束 tag。

### 6.2 容错 tree builder

P0 采用确定的常用恢复规则，不宣称完整浏览器行为：

- 未匹配结束 tag：忽略并记录 warning；
- 文档结束时自动关闭仍在 stack 中的 element；
- 新 `li` 自动关闭前一个 `li`；
- `p` 遇 block element 自动关闭；
- `tr` / `td` / `th` 使用常见自动闭合；
- 孤立 text 加入当前 element 或 document root；
- 多个 document root element 保留为 document children，不隐式插入 `html/head/body`。

`strict=False` 默认尽量恢复并收集 `HtmlWarning`；`strict=True` 在截断 comment、非法属性引号、无法恢复 tag 和非法实体等情况抛 `HtmlParseError`。

不在首版支持 template element、SVG/MathML foreign content、完整 table foster parenting 或全部 HTML5 insertion mode。

## 7. 渲染、转义与安全

默认渲染：

- text node 转义 `&`、`<`、`>`；
- 属性值统一双引号，额外转义 `"`；
- comment 输出 `<!-- ... -->`；
- void tag 不输出 closing tag；
- 正常 element 输出 `<tag>...</tag>`；
- 属性按插入顺序写出，便于稳定 snapshot 测试；
- `pretty=False` 输出紧凑且稳定；
- `pretty=True` 按 `indent` 格式化；
- script/style raw-text 内容不被文本缩进或实体重写。

安全原则：

```python
node.append(Html.text(user_input))     # 安全：渲染时转义
```

P0 不提供隐式 raw HTML 插入。若未来增加 `append_raw_html`，必须是显式危险 API，解析 fragment 后插入，而不是将字符串直接拼接到 renderer 输出。

## 8. PyML 集成

PyML 是 HTML 的声明式构建前端，而不是 HTML 内嵌模板语言。HTML 模块不新增 `{{...}}`、`{% if %}` 或另一套 macro/loop/import 语法。

`Html.from_pyml` 的处理流程：

```text
PyML source
  → 既有变量、@if、@for、@def、@inline、@expand、@from 展开
  → 受限 HTML tree schema
  → HtmlDocument
  → Html.render
```

建议的 PyML node schema：

```yaml
tag: main
id: app
class: page
attrs:
  data-theme: dark
children:
  - tag: h1
    text: $title
  - tag: ul
    children:
      @for $item in $items:
        - tag: li
          text: $item
  - comment: generated by pyml
```

规则：

| key | 语义 |
|---|---|
| `tag` | element 名称 |
| `text` | text node，与 `tag` / `comment` 互斥 |
| `comment` | comment node，与 `tag` / `text` 互斥 |
| `id` | `id` 快捷属性 |
| `class` | `class` 快捷属性 |
| `attrs` | 其他字符串属性 mapping |
| `children` | 子 node 列表 |

未知 key、互斥 node kind 同时出现、非字符串属性值、void tag 带 children 都是 `HtmlPymlError`。`text` 永远作为文本转义，不是 raw HTML。

容器复用、循环、条件、函数和 import 全部继续使用 PyML 的既有 `@inline`、`@expand`、`@def`、`@for`、`@if`、`@from`；HTML 不重复实现。

## 9. 异常与诊断

```text
HtmlError
├─ HtmlParseError
├─ HtmlTreeError
├─ HtmlRenderError
└─ HtmlPymlError
```

HTML `select("路径")` 的语法、类型和可选导航错误继续由既有 selector pass 在翻译期报告，不转换为 `HtmlError`。非 strict 解析诊断：

```python
@dataclass(frozen=True)
class HtmlWarning:
  offset: int
  line: int
  column: int
  message: str
```

`HtmlDocument.warnings` 保存恢复记录。错误或 warning 信息尽量包含输入 offset、line、column、tag/selector 片段和上下文，禁止只输出模糊的“parse failed”。

## 10. 严格约束与资源限制

为防止不可信 HTML 导致内存和时间失控，解析与生成内部保留以下限制：

- 最大输入长度；
- 最大节点数；
- 最大 element nesting depth；
- 最大 attribute 数和单一属性长度；
- PyML 到 HTML 的最大展开节点数。

既有 `select` 的路径长度、计划复杂度和结果规模继续由 selector 编译期展开策略约束，不在 HTML 模块另建 `HtmlSelectOptions` 或 runtime selector 限制。解析选项若需公开，必须采用不可变 `HtmlParseOptions`，不应新增大量松散 bool 参数。

## 11. 分期

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0a | document 所有权、节点 ID、程序化建树、基础 renderer | 可安全建树、复制 handle、删除节点、稳定输出 |
| P0b | tokenizer、attribute、entity、text/comment/doctype、void tag | 常见 HTML 文本可 parse/render |
| P0c | 容错恢复、strict/warning、导航和 text 提取 | 不规范 list/p/table 片段行为稳定 |
| P0d | `find/find_all` 与既有 selector 的 HTML backend | HTML 路径导航、过滤、投影和可选访问回归通过 |
| P0e | `Html.from_pyml` | PyML 条件、循环、inline fragment 能生成安全 DOM |
| P1 | fragment context、显式 raw fragment API | 复杂抓取和模板需求 |
| P2 | 有真实需求时再补部分 HTML5 recovery、SVG/MathML | 不影响 P0/P1 API |

## 12. 测试方案

新增：

```text
test/serde/
  test_html_parse.py
  test_html_tree.py
  test_html_select.py
  test_html_render.py
  test_html_pyml.py
  test_html_fail.py
```

必须覆盖：

- element、text、comment、doctype、void tag；
- 单/双/无引号属性与 boolean attribute；
- 命名与数字 entity；
- script/style raw-text、title/textarea RCDATA；
- 截断 comment/tag、未闭合 tag、常见自动闭合、strict mode；
- parent/children/sibling 导航；
- append/prepend/insert/replace/remove/unwrap；
- `find/find_all`；
- `HtmlDocument` / `HtmlNode` 上的 selector literal 静态内联，覆盖字段、索引、slice、dict key、filter、projection、optional、绑定与既有后处理；
- CSS selector 文本被明确拒绝，且没有 `HtmlNode.select` / `HtmlDocument.select` runtime 方法；
- 文本和属性转义、pretty/compact 稳定渲染；
- detached node 错误；
- PyML 变量、函数、循环、条件、inline fragment 到 HtmlDocument；
- 节点、深度和既有 selector 的编译期诊断。

测试 fixture 固定在仓库内，不依赖网络、浏览器、Beautiful Soup 或任何第三方 HTML parser。兼容性判断以本文规格和 renderer snapshot 为准，而不是以某个浏览器的全部容错行为为准。

## 13. 结论

第一版的完整数据流是：

```text
HTML source
  → Html.parse
  → HtmlDocument / HtmlNode
  → find / select / tree mutation
  → Html.render

PyML source
  → PyML 既有展开
  → Html.from_pyml
  → 同一 HtmlDocument / HtmlNode
  → Html.render
```

Beautiful Soup 风格保留在“树、简单查询、修改”的易用 API；项目既有 selector DSL 负责“编译期结构路径查询”；PyML 保留在“声明、复用、条件、循环”的模板层。HTML 模块只承担 DOM、解析和安全渲染，并为通用 selector 提供 backend；这三层职责不重叠。
