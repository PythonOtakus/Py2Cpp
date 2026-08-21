# `py2cpp.console` 命令行应用库设计

> **状态**：设计规格，尚未实现。  
> **目标**：为 Py2Cpp 原生可执行程序提供统一的命令行参数解析、终端输入输出与渲染、日志、外部命令和后台任务能力。  
> **相关模块**：`py2cpp.system`、`py2cpp.io`、`py2cpp.concur.thread`、`py2cpp.concur.task`。

## 1. 定位与边界

`py2cpp.console` 是命令行应用的上层标准库。它处理参数、终端输出、进度展示、日志、子进程与后台命令等通常需要一起使用的能力，服务于构建工具、测试工具、Web 示例，以及后续 Zeus 的工程初始化、资源构建、shader 编译和插件工具调用。

它不替代底层系统库：

- 文件、目录、路径、环境变量和时间仍归 `py2cpp.io` 与 `py2cpp.system`；
- 线程、原子、队列与协程调度仍归 `py2cpp.concur`；
- 图形窗口、控件和编辑器 UI 仍归 `py2cpp.ui` 与 Zeus；
- 不以完整复刻 CPython 的 `argparse`、`logging`、`subprocess`、`curses` 为目标。

为避免 API 分散，只保留三个子模块：

```text
py2cpp/console/
  __init__.py       # stdin/stdout/stderr、常用再导出、轻量终端入口
  parse.py          # 参数、子命令、帮助与强类型转换
  render.py         # 样式、终端渲染、进度、日志
  task.py           # 外部进程、管道、后台命令任务
```

| 模块 | 负责 | 不负责 |
|---|---|---|
| `console` 根模块 | 标准流、终端能力查询、常用再导出 | 参数解析、进度状态、进程生命周期 |
| `parse` | CLI 解析、usage、help、子命令 | 动态任意对象绑定、完整 CPython action 系统 |
| `render` | 样式、日志、表格、进度与动态区域协调 | 进程控制、文件系统操作 |
| `task` | 外部进程、管道、超时、退出状态 | 协程调度器、默认 shell 解释 |

## 2. 包根：标准流与公共入口

`py2cpp.console` 根模块拥有 `stdin`、`stdout`、`stderr`，不再另设 `terminal` 子模块：

```python
from py2cpp.console import stdin, stdout, stderr

line: str = stdin.readLine()
stdout.write("ready\n")
stderr.write("warning\n")
stdout.flush()
```

三者为稳定的文本流对象，首版最少支持：

- `read()`、`readLine()`、`readLines()`；
- `write()`、`writeLines()`、`flush()`；
- `isAtty` property；
- 作为 `with` 资源使用时，不关闭进程真实的标准句柄。

包根还提供少量公共便利入口：

```python
from py2cpp.console import terminal_size, supports_color
from py2cpp.console import ArgumentParserMixin, Progress

width, height = terminal_size()
enabled: bool = supports_color()
```

`terminal_size() -> tuple[int, int]` 返回列数和行数。`supports_color(stream=stdout) -> bool` 综合 TTY、环境变量和用户禁用设置判断是否允许颜色。光标控制、ANSI 编码和动态区域协调属于 `render` 的内部能力，不在包根暴露低层 API。

## 3. 总体原则

### 3.1 默认安全地执行命令

推荐接口接收“可执行文件 + 参数列表”，不经 shell：

```python
from py2cpp.console import stdout
from py2cpp.console.task import Console

result = Console.run(["asset_compiler", "--input", source], capture_output=True, check=True)
stdout.write(result.stdout)
```

字符串命令仅在显式 `shell=True`、`Console.system()` 或 `Console.popen()` 时经过 shell。参数数组绝不能通过字符串拼接后交给 shell。

### 3.2 无 TTY 时保持正确

重定向输出、CI 环境或显式禁用颜色时：

- 样式退化为纯文本；
- 进度与 spinner 不输出 ANSI 控制序列；
- 日志可直接写入文件或重定向流；
- 静态表格仍输出稳定、可读的文本。

命令行程序不能依赖真实 ANSI 终端才可运行。

### 3.3 一个流，一个输出协调器

日志和动态进度条不能各自直接写 `stdout`。每个目标流有一个内部协调器：写普通行前擦除动态区域，写入完整行后按最新快照重绘动态区域。锁仅覆盖状态快照与实际写出，不能覆盖进程等待、网络 I/O 或用户回调。

### 3.4 Python 描述策略，模板实现平台叶子

Python 源码负责参数校验、状态机、格式化与组合；C++ / 模板仅负责无法进一步拆分的终端模式、Unicode 控制台输出、进程创建、pipe、等待和终端尺寸。真相源只改 `py2cpp/`、`src/`、`templates/`、`test/`、`docs/`，禁止修改 `generated/`。

### 3.5 复用现有并发基础

- `render` 的公开更新操作可跨线程调用，最终写终端始终串行；
- 异步日志使用 `concur.thread.Queue[LogRecord]`；
- 同步 `Console.run()` 阻塞调用线程；
- 未来异步子进程必须建立在真实 non-blocking pipe 与 `Task` readiness 上，不能用 `Task.runThread()` 伪装非阻塞 I/O。

## 4. `console.parse`：命令行解析

### 4.1 目标 API

首版直接以 `@dataclass` 字段与既有 `@annotation` 元数据声明参数类别；不再以逐条 `add_argument()` 作为主 API：

```python
from py2cpp import *
from py2cpp.console.parse import (
  ArgumentParserMixin,
  FlagArgMeta,
  OptArgMeta,
  PosArgMeta,
)

@dataclass
class BuildArgs(ArgumentParserMixin):
  source: str @PosArgMeta(help="资源源目录")

  output: str @OptArgMeta(short="-o", help="输出目录") = "build"
  jobs: int @OptArgMeta(short="-j", choices=(1, 2, 4, 8), help="并行构建数") = 1
  release: bool @FlagArgMeta(help="启用发布构建") = False

args: BuildArgs = new.parse()
```

宿主须显式继承 ``ArgumentParserMixin``。赋值处按 S0303–S0307 写 ``new.parse()`` / ``new.parse(argv)``（语义即 ``BuildArgs.parse``）。默认读取进程参数；传入 ``argv`` 供测试和嵌入式程序使用。参数来源需由最小 `py2cpp.system.sys.argv` 支持，该能力与本模块同时实施。勿写 ``ArgumentParserMixin.parse[T]``。

`PosArgMeta`、`OptArgMeta`、`FlagArgMeta` 都是 `@annotation` + `@dataclass` 元数据类，字段注解必须遵循项目既有的 `Type @Meta(...)` 写法。字段名始终是 Python `snake_case`；长选项由字段名自动转换为 kebab-case，例如 `asset_root` 对应 `--asset-root`。短选项只由 `short` 指定，避免再引入重复表达同一名称的 `dest` 或 `long`。

| 元数据 | 字段约束 | 命令行形式 |
|---|---|---|
| `PosArgMeta` | 具备解析器的值类型；首版无默认值 | 按字段声明顺序的位置参数 |
| `OptArgMeta` | 非 `bool` 的值类型；有默认值或 `@optional` | `--field-name VALUE`，可选 `short` |
| `FlagArgMeta` | 严格仅 `bool` | 默认 `False` 时为 `--field-name`；默认 `True` 且 `negated=True` 时为 `--no-field-name` |

同一字段至多出现一个参数类别 Meta。`OptArgMeta.short` 必须形如 `-x` 且在同一 parser 内唯一；派生长选项也必须唯一。`choices` 是固定 tuple 元数据，而非可变 list。

`parse()` 与 `@staticproperty helpText` 写在 mixin 内，用 `Self.iterFields`、`Self.getFieldAnnotation[*ArgMeta](field)`、`Self.getFieldType(field)` 与 `Self.getFieldDefault(field)` 译期展开；不由 pass 按字段生成方法体。读取帮助写 `BuildArgs.helpText`（勿 `helpText()`）；类内赋值类型为 `str` 时写 `Self.helpText`（`new` 指赋值左侧类型，勿 `new.helpText`）。`FlagArgMeta` 标在非 `bool`、`OptArgMeta` 标在 `bool`、位置参数带默认值、选项冲突、或未继承 mixin 等情形均应为严格翻译错误，而非运行时错误。

### 4.2 首版行为与限制

- `PosArgMeta` 位置参数、`OptArgMeta` 短/长选项和 `FlagArgMeta` 布尔 flag；
- dataclass 默认值、`@optional`、`choices` 与 `int` / `float` / `str` / `bool` 转换；
- `--` 停止选项解析；
- `-abc` 仅在 a/b/c 全部是 flag 时视为组合短选项；
- 子命令拥有独立 parser；
- 自动 usage/help，`--help` 成功退出；
- 解析错误包含参数名和原始输入，打印简短 usage，退出码为 `2`。

首版不实现 CPython 动态 `Action`、任意 `nargs`、嵌套互斥组、文件类型参数和自动补全脚本。显式逐条 builder API 如确有需求，可在 `parse[T]()` 之上以受限补充形式实现，但不得成为新的主语义来源。

## 5. `console.render`：样式、动态显示与日志

`render` 合并样式、终端渲染和日志概念。三者都以“将信息可靠呈现到一个文本流”为边界；合并后，日志和动态显示可天然共用同一个输出协调器。

### 5.1 样式

```python
from py2cpp.console import stdout
from py2cpp.console.render import Color, Style, paint

error = Style(fg=Color.RED, bold=True)
stdout.write(paint("构建失败", error))
```

`Style` 是 `@dataclass(frozen=True)` 值类型，支持前景/背景色、粗体、弱化、下划线、反色与 reset。首版支持标准 16 色；256 色和 RGB 仅在终端能力允许时启用。

样式编码发生在写流边界：`paint()` 在不支持颜色的流上返回纯文本。业务代码不应长期保存自行拼接的 ANSI 字符串。

### 5.2 Progress、Spinner、Status、Table

```python
from py2cpp.console.render import Progress

with Progress() as progress:
  task = progress.add_task("编译 shader", total=100)
  for item in items:
    compile(item)
    progress.advance(task)
```

首版 `Progress` 支持：

- 多任务、可选总量、`advance()` / `update()` / `complete()`；
- 已完成/总数、百分比、耗时、速率与紧凑进度条；
- 上下文退出时清理动态区域、恢复光标；
- TTY 内原地刷新，非 TTY 自动降级；
- 可指定目标流，默认 `console.stdout`；
- 同一实例允许跨线程更新。

`Spinner` 用于未知总量任务，由 `tick()` / `refresh()` 推进；`Status` 用于短生命周期状态；`Table` 用于静态标题、对齐和最大宽度截断。首版不启动隐藏刷新线程，调用方显式更新或刷新，保证测试确定性。

### 5.3 日志

```python
from py2cpp.console.render import LogLevelEnum, Logger

log = Logger("asset.build", level=LogLevelEnum.INFO)
log.info("开始构建", source=source, jobs=jobs)
log.error("构建失败", code=result.returnCode, output=result.stderr)
```

`LogRecord` 为不可变 `@dataclass(frozen=True)`，至少包含单调时间、墙钟时间、等级、logger 名、消息、线程名 / 当前 Task 标识、可选源位置和静态可表示的键值字段。

首版提供：

- `debug/info/warn/error/critical`；
- `Logger(...)` 显式构造、`set_level()`、`add_sink()`；
- `ConsoleSink`（经输出协调器）、`FileSink`（默认无色）、`MemorySink`（测试）；
- 稳定文本 `TextFormatter`。

`Logger` 不维护按名称缓存的全局 registry，也不提供 `get_logger()`；名称仅用于记录分类和输出。Logger 的生命周期、sink 组合与关闭均由创建者显式持有和管理。以后增加基于 `serde.json.Json` 的 `JsonFormatter` 与基于 `Queue[LogRecord]` 的 `AsyncSink`。异步 sink 必须定义 flush、关闭和背压/丢弃策略。日志不引入 printf 式动态格式化；使用 f-string 或 `format()` 写消息，结构化信息单独传字段。

## 6. `console.task`：进程、管道和后台命令

`task` 指外部命令及其输出、退出和后台生命周期，不是新的协程调度器。该名称使 CLI 中“启动、观察、等待、取消一项外部任务”保持统一。

### 6.1 推荐 API

```python
from py2cpp.console import stdout
from py2cpp.console.task import Console

result = Console.run(
  ["tool", "--input", source],
  cwd=work_dir,
  env=environment,
  capture_output=True,
  timeout=30.0,
  check=True,
)
stdout.write(result.stdout)
```

```python
@dataclass(frozen=True)
class CompletedTask:
  args: list[str]
  returnCode: int
  stdout: str
  stderr: str
```

`check=True` 且退出码非零时抛出 `TaskExitError`，异常持有 `CompletedTask`，调用者可继续读取 stdout/stderr 作诊断。

### 6.2 Task 与兼容接口

```python
from py2cpp.console.task import Console, Task, Pipe

code: int = Console.system("git status")
reader = Console.popen("git rev-parse --show-toplevel")
root: str = reader.read()

task = Task(["tool", "--watch"], stdout=Pipe, stderr=Pipe)
task.start()
code = task.wait(timeout=10.0)
```

- `Task`：推荐的低层进程对象，接收 `list[str]`；
- `Console.run`：推荐的一站式同步接口；
- `Console.system(command: str) -> int`：显式 shell 兼容入口，返回规范化退出码；
- `Console.popen(command: str, mode: str = "r")`：显式 shell 单向文本管道，首版仅 `"r"` / `"w"`。

`Console` 定义在 `py2cpp.console.task`。`run`、`system`、`popen` 仅作为该类的静态方法存在，不保留模块级函数，也不从 `py2cpp.system` 或 `py2cpp.console` 包根导出；shell 语义因此在调用点可见。

### 6.3 必须保证的语义

- Windows：`CreateProcessW`、UTF-16 命令行、受控 handle 继承与退出码；
- POSIX：安全的 `posix_spawn` 或 `fork/exec`、fd 重定向和 wait status；
- 支持 `cwd`、明确 `env`、UTF-8 文本解码与可配置错误策略；
- stdin/stdout/stderr 支持继承、丢弃、`Pipe` 或文件；
- 支持 `poll()`、`wait(timeout)`、`terminate()`、`kill()`；
- `Task.communicate()` 与 `Console.run(capture_output=True)` 必须并发排空 stdout/stderr，避免 pipe 缓冲区写满死锁；
- 区分启动失败、超时、外部终止和非零退出。

首版不支持进程组、PTY、Windows Job Object、进程树杀死和任意二进制 stdin 流。后续异步版本在 `concur.task` 已支持真实 pipe readiness 后增加；它必须是真正的 non-blocking pipe，不能用 `Task.runThread()` 包装同步读取。

## 7. 平台、编码和异常

首要目标为 Windows + MSVC，同时保持 Linux/macOS + GCC/Clang 的公共语义一致。Python API 不泄露 `HANDLE`、fd、`DWORD`、`errno` 等平台类型。

文本默认 UTF-8。Windows native 层使用 Unicode API 与 UTF-16 边界转换，禁止依赖活动 ANSI 代码页。表格显示宽度首版可做保守的 ASCII/宽字符估算；完整 Unicode grapheme 宽度计算后续独立演进。

建议异常层级：

```text
ConsoleError
├─ ArgumentError
├─ RenderError
└─ TaskError
   ├─ TaskStartError
   ├─ TaskTimeoutError
   └─ TaskExitError
```

错误信息必须包含用户可操作上下文：参数名与原始输入、命令及参数、工作目录、超时与 stderr 摘要，不能只暴露系统错误码。

## 8. 分期、依赖与验收

| 阶段 | 内容 | 前置依赖 | 验收结果 |
|---|---|---|---|
| P0a | 包根标准流、TTY/尺寸、样式 | `io`、`system.environ` | TTY、重定向和无色输出均正确 |
| P0b | `parse` | 最小 `system.sys.argv` | 参数、flag、子命令、help、错误码通过测试 |
| P0c | `Console.run/system/popen`、`Task` | Windows/POSIX 进程模板叶子 | 参数列表安全、shell 边界明确、超时、双 pipe 捕获稳定 |
| P1a | `render` 日志 sink | 包根流、样式 | 日志和动态区域不会相互破坏 |
| P1b | Progress / Spinner / Status / Table | `concur.thread.Queue` | 多任务、无 TTY 降级、异常恢复光标 |
| P1c | AsyncSink | `concur.thread.Queue` | 多线程压测无交错，可 flush 和关闭 |
| P2 | 异步外部 Task | `concur.task` pipe readiness | 真实非阻塞 stdout/stderr 流读取 |

## 9. 测试策略

新增：

```text
test/console/
  test_parse.py
  test_render.py
  test_task.py
```

- `test_parse.py`：各类型、默认值、重复/缺失/未知参数、`--`、子命令、help 和错误退出；
- `test_render.py`：使用内存流模拟 TTY/非 TTY，验证样式降级、进度输出序列、光标恢复、日志等级、sink 顺序和跨线程写入；
- `test_task.py`：含空格与 Unicode 的参数、cwd、环境覆盖、分离/合并 stdout/stderr、非零退出、启动失败、超时与终止。

进程测试必须使用受控的仓库内帮助程序或测试二进制本身，不能依赖 Git、Python 安装、网络或开发机 shell 配置。并发测试只使用事件、读到输出和单调截止时间，不使用固定 `sleep`；所有子进程和 pipe 都必须在 `finally` 或上下文退出中回收。

## 10. 完整使用示例

```python
from py2cpp import *
from py2cpp.console import Progress
from py2cpp.console.parse import ArgumentParserMixin, FlagArgMeta, OptArgMeta, PosArgMeta
from py2cpp.console.render import Logger
from py2cpp.console.task import Console

def main() -> int:
    @dataclass
    class BuildArgs(ArgumentParserMixin):
      source: str @PosArgMeta(help="资源源目录")
      jobs: int @OptArgMeta(short="-j", choices=(1, 2, 4, 8)) = 1
      release: bool @FlagArgMeta() = False

    args: BuildArgs = new.parse()
    log = Logger("asset-build")
  log.info("开始构建", source=args.source, jobs=args.jobs, release=args.release)

  with Progress() as progress:
    work = progress.add_task("构建中", total=1)
    result = Console.run(
      ["asset_compiler", "--source", args.source, "--jobs", str(args.jobs)],
      capture_output=True,
    )
    progress.complete(work)

  if result.returnCode != 0:
    log.error("构建失败", code=result.returnCode, output=result.stderr)
    return result.returnCode
  log.info("构建完成")
  return 0
```

此示例的所有用户可见行为都必须由三个 `test/console` 测试文件覆盖；终端渲染、日志协调和平台进程细节不得泄漏到业务代码。

## 11. 明确延后或不做

- 不实现 curses、终端鼠标和全屏 TUI；未来另立 `console.tui` 设计；
- 不复刻 CPython 的动态扩展体系；
- 不默认执行 shell；
- 不推荐 `Console.system()` / `Console.popen()` 取代 `Console.run()`；
- 不以隐藏刷新线程或伪异步 pipe 增加不确定性；
- 不在 `console` 重复实现 Path、环境变量、队列、JSON 或 YAML。
