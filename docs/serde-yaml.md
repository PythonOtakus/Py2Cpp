# py2cpp.serde.yaml

`py2cpp.serde.yaml` 为 Py2Cpp 提供静态类型 YAML 配置读写。Python 3.13 标准库本身不含 YAML；此模块将 YAML 先规范化为 JSON，再复用 `py2cpp.serde.json.Json` 的泛型解码、`@serializable` 与错误路径。

## API

```python
from py2cpp.serde.yaml import Yaml

config: dict[str, int] = Yaml.loads[dict[str, int]]("a: 1\nb: 2\n")
documents: list[dict[str, int]] = Yaml.loadsAll[dict[str, int]](source)
text: str = Yaml.dumps(config)

item: dict[str, int] = Yaml.load[dict[str, int]](file)
items: list[dict[str, int]] = Yaml.loadAll[dict[str, int]](file)
Yaml.dump(config, file)
```

没有模块级 `load` / `dump` 函数；所有入口均属于 `Yaml`。`load` / `loadAll` / `dump` 接受 `TextIOWrapper`，`loadString` / `loadAllString` / `dumpString` 接受 `StringIO`。

## 已支持的 YAML 输入

- block mapping 与 block sequence，可任意嵌套；
- flow sequence 与 JSON-compatible flow YAML；
- `#` 注释、`---` / `...` 多文档标记，以及跳过 `%YAML` 等指令行；
- Core Schema 常用标量：`null` / `~`、布尔、带正负号整数、浮点、`.inf`、`.nan`；
- 单引号、双引号与 `\n` / `\r` / `\t` / `\"` / `\\` 转义；
- `|` / `>` 块标量及 `-`、`+` chomping 指示符；
- 标准标量标签 `!!str`、`!!int`、`!!float`、`!!bool`；
- anchors / aliases（`&name`、`*name`）与 mapping merge（`<<: *base`、`<<: [*a, *b]`）；
- JSON bridge 的递归泛型容器，例如 `dict[str, dict[str, int]]` 与 `list[list[int]]`。

`Yaml.dumps` 输出 JSON-compatible YAML；JSON 是 YAML 1.2 的合法子集，因此输出稳定且可由标准 YAML 解析器读取。

## 有意限制

该实现面向静态配置，不构造通用 YAML 图：复杂 key（`? key`）、循环 alias、别名共享对象身份、二进制与时间戳构造器、锚点跨文档引用、完整 flow mapping，以及任意自定义 tag 构造器会抛出 YAML 异常或不被接受。非标准单值局部 tag 仅作为值标签剥离后按基础标量处理，不注册对象构造器。

异常类型为 `YamlScannerError`、`YamlParserError`、`YamlConstructorError`、`YamlRepresenterError`，均继承 `YamlError`。