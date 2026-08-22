"""``console.render``：样式、进度、日志与输出协调（``docs/console.md`` §5）。"""
from ..builtins import *
from ..io import TextIO
from ..system.time import monotonic, time
from ..text import str
from ..util.list import list

from .exceptions import RenderError
from .core import Console


@enum
class AnsiColorEnum:
  Default = 0
  Black = 30
  Red = 31
  Green = 32
  Yellow = 33
  Blue = 34
  Magenta = 35
  Cyan = 36
  White = 37


@enum
class LogLevelEnum:
  Debug = 10
  Info = 20
  Warn = 30
  Error = 40
  Critical = 50


@dataclass(frozen=True)
class Style:
  fg: AnsiColorEnum = AnsiColorEnum.Default
  bg: AnsiColorEnum = AnsiColorEnum.Default
  bold: bool = False
  dim: bool = False
  underline: bool = False
  reverse: bool = False


@dataclass(frozen=True)
class LogRecord:
  mono: float64
  wall: float64
  level: int
  logger: str
  message: str
  thread: str
  task: str
  source: str
  fields: str


def _ansiEnabledFor(stream: TextIO) -> bool:
  return Console.colorfulFor(stream.isAtty)


def paint(text: str, style: Style) -> str:
  """在不支持颜色的流上返回纯文本（默认 stdout）。"""
  stream: TextIO = Console.stdout
  if not _ansiEnabledFor(stream):
    return text
  codes: list[str] = []
  if style.bold:
    codes.append("1")
  if style.dim:
    codes.append("2")
  if style.underline:
    codes.append("4")
  if style.reverse:
    codes.append("7")
  if style.fg != AnsiColorEnum.Default:
    codes.append(str(int(style.fg)))
  if style.bg != AnsiColorEnum.Default:
    codes.append(str(int(style.bg) + 10))
  if not codes:
    return text
  seq: str = ""
  first: bool = True
  for c in codes:
    if not first:
      seq += ";"
    first = False
    seq += c
  return "\x1b[" + seq + "m" + text + "\x1b[0m"


@copyable
class _StreamCoordinator:
  """每目标流一个协调器：写行前擦除动态区，写完后按快照重绘。"""

  _dynamic: str = ""

  def setDynamic(self, text: str) -> None:
    self._dynamic = text

  def clearDynamic(self) -> None:
    self._dynamic = ""

  def writeLine(self, stream: TextIO, line: str) -> None:
    if self._dynamic:
      stream.write("\r\x1b[2K")
    stream.write(line)
    if not line.endsWith("\n"):
      stream.write("\n")
    if self._dynamic:
      stream.write(self._dynamic)
    stream.flush()

  def refresh(self, stream: TextIO) -> None:
    if self._dynamic:
      stream.write("\r\x1b[2K")
      stream.write(self._dynamic)
      stream.flush()


_stdoutCoord: _StreamCoordinator = new()


def _coordFor(_stream: TextIO) -> _StreamCoordinator:
  return _stdoutCoord


@dataclass
class _ProgressTask:
  name: str
  total: int
  nDone: int = 0


@uncopyable
class Progress:
  """多任务进度；TTY 原地刷新，非 TTY 降级；无隐藏刷新线程。"""

  _tasks: list[_ProgressTask]
  _active: bool = False

  def __init__(self):
    self._tasks = []

  def _out(self) -> TextIO:
    return Console.stdout

  def __enter__(self) -> Self:
    self._active = True
    return self

  def __exit__(self) -> None:
    self._active = False
    stream: TextIO = self._out()
    _coordFor(stream).clearDynamic()
    if _ansiEnabledFor(stream):
      stream.write("\r\x1b[2K")
      stream.flush()

  def addTask(self, name: str, total: int = 0) -> int:
    self._tasks.append(_ProgressTask(name, total, 0))
    self._redraw()
    return len(self._tasks) - 1

  def advance(self, task: int, amount: int = 1) -> None:
    if task < 0 or task >= len(self._tasks):
      raise RenderError()
    t: _ProgressTask = self._tasks[task]
    t.nDone += amount
    self._tasks[task] = t
    self._redraw()

  def update(self, task: int, nDone: int) -> None:
    if task < 0 or task >= len(self._tasks):
      raise RenderError()
    t: _ProgressTask = self._tasks[task]
    t.nDone = nDone
    self._tasks[task] = t
    self._redraw()

  def complete(self, task: int) -> None:
    if task < 0 or task >= len(self._tasks):
      raise RenderError()
    t: _ProgressTask = self._tasks[task]
    if t.total > 0:
      t.nDone = t.total
    self._tasks[task] = t
    self._redraw()

  def _redraw(self) -> None:
    if not self._active:
      return
    line: str = ""
    first: bool = True
    for t in self._tasks:
      if not first:
        line += " | "
      first = False
      if t.total > 0:
        pct: int = (t.nDone * 100) // t.total
        line += t.name + " " + str(t.nDone) + "/" + str(t.total) + " (" + str(pct) + "%)"
      else:
        line += t.name + " " + str(t.nDone)
    stream: TextIO = self._out()
    if _ansiEnabledFor(stream):
      _coordFor(stream).setDynamic(line)
      _coordFor(stream).refresh(stream)
    else:
      stream.write(line)
      stream.write("\n")
      stream.flush()


@uncopyable
class Spinner:
  _frames: list[str]
  _index: int = 0
  _label: str

  def __init__(self, label: str = ""):
    self._label = label
    self._frames = ["|", "/", "-", "\\"]

  def _out(self) -> TextIO:
    return Console.stdout

  def tick(self) -> None:
    self._index = (self._index + 1) % len(self._frames)
    self.refresh()

  def refresh(self) -> None:
    frame: str = self._frames[self._index]
    text: str = frame + " " + self._label
    stream: TextIO = self._out()
    if _ansiEnabledFor(stream):
      _coordFor(stream).setDynamic(text)
      _coordFor(stream).refresh(stream)
    else:
      stream.write(text)
      stream.write("\n")
      stream.flush()


@uncopyable
class Status:
  _text: str

  def __init__(self, text: str = ""):
    self._text = text

  def _out(self) -> TextIO:
    return Console.stdout

  def update(self, text: str) -> None:
    self._text = text
    self.refresh()

  def refresh(self) -> None:
    stream: TextIO = self._out()
    if _ansiEnabledFor(stream):
      _coordFor(stream).setDynamic(self._text)
      _coordFor(stream).refresh(stream)
    else:
      stream.write(self._text)
      stream.write("\n")
      stream.flush()


@copyable
class Table:
  _headers: list[str]
  _rows: list[list[str]]
  _maxWidth: int

  def __init__(self, headers: list[str], maxWidth: int = 40):
    self._headers = headers
    self._rows = []
    self._maxWidth = maxWidth

  def addRow(self, cells: list[str]) -> None:
    self._rows.append(cells)

  def _clip(self, s: str) -> str:
    if len(s) <= self._maxWidth:
      return s
    return s[: self._maxWidth]

  def render(self) -> str:
    out: str = ""
    first: bool = True
    for h in self._headers:
      if not first:
        out += " | "
      first = False
      out += self._clip(h)
    if self._headers:
      out += "\n"
    for row in self._rows:
      first = True
      for cell in row:
        if not first:
          out += " | "
        first = False
        out += self._clip(cell)
      out += "\n"
    return out


@copyable
class TextFormatter:
  def formatLine(self, record: LogRecord) -> str:
    extra: str = " " + record.fields if record.fields else ""
    return "[" + str(record.level) + "] " + record.logger + ": " + record.message + extra


@uncopyable
class ConsoleSink:
  _formatter: TextFormatter
  _minLevel: int

  def __init__(self, level: int = 10):
    self._minLevel = level
    self._formatter = new()

  def _out(self) -> TextIO:
    return Console.stdout

  def emit(self, record: LogRecord) -> None:
    if record.level < self._minLevel:
      return
    line: str = self._formatter.formatLine(record)
    stream: TextIO = self._out()
    _coordFor(stream).writeLine(stream, line)

  def flush(self) -> None:
    self._out().flush()

  def close(self) -> None:
    self.flush()


@uncopyable
class FileSink:
  """追加写文件；每次 emit 打开—写入—关闭（避免持有不可赋值的 ``TextIO``）。"""

  _path: str
  _formatter: TextFormatter
  _minLevel: int

  def __init__(self, path: str, level: int = 10):
    self._path = path
    self._minLevel = level
    self._formatter = new()

  def emit(self, record: LogRecord) -> None:
    if record.level < self._minLevel:
      return
    line: str = self._formatter.formatLine(record)
    fp: TextIO = new(self._path, "a")
    fp.write(line)
    fp.write("\n")
    fp.flush()
    fp.close()

  def flush(self) -> None:
    return

  def close(self) -> None:
    return


@copyable
class MemorySink:
  records: list[LogRecord]
  _minLevel: int

  def __init__(self, level: int = 10):
    self.records = []
    self._minLevel = level

  def emit(self, record: LogRecord) -> None:
    if record.level < self._minLevel:
      return
    self.records.append(record)

  def flush(self) -> None:
    return

  def close(self) -> None:
    return


@copyable
class Logger:
  """显式构造；无全局 registry / ``get_logger``。默认不挂 ConsoleSink（由调用方 ``add_*``）。"""

  name: str
  level: int
  _memory: list[MemorySink]

  def __init__(self, name: str, level: int = 20):
    self.name = name
    self.level = level
    self._memory = []

  def setLevel(self, level: int) -> None:
    self.level = level

  def addMemorySink(self, sink: MemorySink) -> None:
    self._memory.append(sink)

  def _emit(self, level: int, message: str, fields: str) -> None:
    if level < self.level:
      return
    # 先构造记录再分发；``MemorySink`` 为 ``@copyable``：``list`` 下标取拷贝，须写回。
    rec: LogRecord = new(
      monotonic(),
      time(),
      level,
      self.name,
      message,
      "",
      "",
      "",
      fields,
    )
    n: int = len(self._memory)
    for i in range(n):
      m: MemorySink = self._memory[i]
      m.emit(rec)
      self._memory[i] = m

  def debug(self, message: str, fields: str = "") -> None:
    self._emit(10, message, fields)

  def info(self, message: str, fields: str = "") -> None:
    self._emit(20, message, fields)

  def warn(self, message: str, fields: str = "") -> None:
    self._emit(30, message, fields)

  def error(self, message: str, fields: str = "") -> None:
    self._emit(40, message, fields)

  def critical(self, message: str, fields: str = "") -> None:
    self._emit(50, message, fields)
