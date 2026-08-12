# py2cpp.serde.yaml

`py2cpp.serde.yaml` 是 Py2Cpp 自有的 YAML 序列化模块。Python 3.13 标准库本身不包含 YAML，因此该模块提供面向配置文件和静态类型对象的轻量实现，API 参考常用 PyYAML 习惯并遵循 YAML 1.2 Core Schema 的常用子集。

## API

```python
from py2cpp.serde.yaml import Yaml

value: dict[str, int] = Yaml.loads[dict[str, int]]("a: 1\nb: 2\n")
text: str = Yaml.dumps(value)

items: list[int] = Yaml.load_string[list[int]](stream)
Yaml.dump(items, file)
```

本模块不提供全局 `load`/`dump` 函数，统一通过 `Yaml` 静态方法调用。`load`/`dump` 面向 `TextIOWrapper`，`load_string`/`dump_string` 面向 `StringIO`。

## 实现边界

解析阶段先将 YAML 规范化成 JSON 文本，再复用 `py2cpp.serde.json.Json` 的泛型解码器。因此基础标量、`list[T]`、`dict[str, T]` 以及已有 `@serializable` 数据类沿用 JSON 的类型映射和错误处理路径。`Yaml.dumps` 当前输出 JSON-compatible YAML（JSON 是 YAML 1.2 的合法子集），保证稳定、可被 YAML 1.2 解析器读取。

当前支持：

- block mapping 和 block sequence；
- flow mapping/sequence（简单嵌套结构）；
- `#` 注释、文档标记 `---`/`...`；
- null（`null`、`~`）、布尔、整数、浮点、`.inf`、`.nan`；
- 单引号、双引号及常用转义；
- literal `|` 与 folded `>` 多行字符串；
- `@serializable` 数据类通过 JSON bridge 读写。

当前不实现 YAML 标签、锚点/别名、复杂 key、二进制标签、自定义构造器和完整 YAML 1.2 指令集。遇到不支持的语法会抛出 `YamlScannerError`、`YamlParserError`、`YamlConstructorError` 或 `YamlRepresenterError`（均继承 `YamlError`）。