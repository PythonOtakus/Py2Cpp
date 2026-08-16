"""py2cpp 内建：类型标记、内存 API、装饰器桩、new/len/print 等。

由 ``py2cpp/__init__.py`` 再导出；标准库子模块须 ``from ..builtins import *``（深度见编码规范 S27）。
"""
from __future__ import annotations

# py2cpp: strict-off

class char:
  """Unicode 码点（C++ ``PyChar``），用于 ``char[:]`` 等。"""

  pass


class byte:
  """单字节 0–255（C++ ``PyByte``，即 C++ ``char``）。"""

  pass


@native_name("CStr")
class CStr:
  """C 字符串指针（C++ ``typedef const char* CStr``），非 py2cpp ``str`` 类。"""

  pass


# 有符号 64 位整数（C++ ``PyInt64`` / ``int64_t``）
type int64 = int
# 无符号 32 位整数（C++ ``PyUInt`` / ``uint32_t``）
type uint = int
# 无符号 64 位整数（C++ ``PyUInt64`` / ``uint64_t``）
type uint64 = int
# 指针宽度无符号整数（C++ ``PyUPtr`` / ``uintptr_t``），存 ``void*`` / ``FILE*`` 等
type uintptr = int
# IEEE 754 双精度浮点（C++ ``PyFloat64`` / ``double``）
type float64 = float


class Pointer[Element]:
  """可空指针类型标记 → C++ ``T*``。"""

  pass


class Function:
  """C 函数指针类型标记 → ``Ret (*)(Args...)``；注解写 ``Function[[A, B], Ret]``。"""

  pass


class Callable:
  """可绑定槽位类型标记 → ``PyCallable<Ret, Args...>``；注解写 ``Callable[[A, B], Ret]``。"""

  pass


class Self:
  """``@staticproperty`` / 混入展开时表示当前类（翻译期替换为具体类名）。

  ``Self.getFieldType(field)`` 仅可用于会被 ``Self.iterFields`` 展开的混入方法；
  ``field`` 须在翻译期解析为当前宿主的字段名，调用会替换为该字段去除 ``@``
  标记后的基础类型注解。
  """

  @staticmethod
  def getFieldType(field):
    pass

  pass


class Super:
  """直接实体基类类型（严格等于译器注入的 ``type __base__``；对标 ``Self``）。"""

  pass


class VarStack:
  """翻译期 mixin 参数栈（``s.push`` / ``s.pop`` / ``s.top()`` + ``new(*s)`` / ``fn(*s)`` 由译器展开）。

  在 ``@mixin`` 方法内 ``vs: VarStack = new()`` 声明栈；``push``/``pop``/``*vs`` 须与声明同块作用域
  （``Self.iterFields`` / ``enumFields`` 循环体除外）；``top()`` 可读栈顶且可跨内层作用域；``pop`` 不回收编号。
  """

  def push(self, value) -> None:
    """``vs.push(expr)`` → 译器记录 ``__vs_{栈名}{序号} = expr``。"""
    pass

  def pop(self):
    """``x = vs.pop()`` / ``_: T = vs.pop()`` → 绑定栈顶临时变量。"""
    pass

  def top(self):
    """``vs.top()`` → 读栈顶、不 pop。"""
    pass


# ---------------------------------------------------------------------------
# 内存 API（C++ 实现见 ``refcount.h``；由翻译器生成调用，非运行时执行）
# ---------------------------------------------------------------------------


def alloc[Element]() -> Pointer[Element]:
  """``alloc<T>()`` 分配单个对象。"""
  return None


def free[Element](buf: Pointer[Element]) -> None:
  """``free<T>(buf)`` 释放单个对象。"""
  pass


def allocArray[Element](count: int) -> Pointer[Element]:
  """``allocArray<T>(count)`` 分配数组。"""
  return None


def allocRawArray[Element](count: int) -> Pointer[Element]:
  """``allocRawArray<T>(count)``：仅分配存储，不默认构造元素。"""
  return None


def freeArray[Element](buf: Pointer[Element]) -> None:
  """``freeArray<T>(buf)`` 释放 ``allocArray`` 的原始存储（须已对元素 ``destroy``）。"""
  pass


def init[Element](ptr: Pointer[Element], *args) -> None:
  """``init<T>(ptr)`` 或 ``init<T>(ptr, args...)``：placement new。"""
  pass


def destroy[Element](ptr: Pointer[Element]) -> None:
  """``destroy<T>(ptr)`` 显式析构（不释放存储）。"""
  pass


def id[Element](x: Element) -> Pointer[Element]:
  """``id(x)``：取 ``x`` 的对象地址（C++ ``&x``；``@refcount`` 为 ``&(*x)``）。"""
  return None


def cast[Element](obj) -> Element:
  """``cast[T](obj)`` / ``cast(obj)``（类型由左侧/返回注解推断）→ ``static_cast``。"""
  return obj


# ---------------------------------------------------------------------------
# 翻译期装饰器（恒等；展开逻辑在 ``py2cpp/*.py`` 包内各模块）
# ---------------------------------------------------------------------------


def copyable(cls):
  """值语义：复制构造 + ``operator=(const T&)``。"""
  return cls


def final(clsOrMethod):
  """``@final class`` 不可继承；``@final def`` 不可覆盖；``name: T @final`` 为实例只读字段（译期识别 ``final`` 标记名）。"""
  return clsOrMethod


def uncopyable(cls):
  """不可复制：复制构造/赋值 ``= delete``；可移动（``T&&`` 构造/赋值，实现须在 C++/``@native`` 注入）。"""
  return cls


def union(cls):
  """Rust 式 ADT（``@variant`` 嵌套类 + ``Self.<Variant>(…)`` 构造；判别仅 ``match``）。隐式 ``@copyable``。"""
  return cls


def enum(cls=None, /, *, flag: bool = False):
  """整型 ``enum class``（``name = 1`` / ``name = ...`` 顺延；``flag=True`` 时 ``...`` 为下一 2 的幂）。

  默认 ``int`` 底层；可单继承其它 ``@enum``。``@enum`` 无参时作装饰器；``flag`` 仅翻译期标记。
  """
  if cls is None:
    def _wrap(c):
      return c
    return _wrap
  return cls


class _EnumMroDec:
  """``@enum.mro`` 翻译期标记；``base=…`` 写在类参数 ``class E(base=…):``。"""

  @native
  def __call__(self, cls=None, /):
    ...


enum.mro = _EnumMroDec()


class _UnionMroDec:
  """``@union.mro`` 翻译期标记；``base=…`` 写在类参数 ``class U(base=…):``。"""

  @native
  def __call__(self, cls=None, /):
    ...


union.mro = _UnionMroDec()


def variant(cls):
  """``@union`` 内的变体嵌套类（不单独生成 C++ 类型）。"""
  return cls


def serializable(cls):
  """编译期为 ``@dataclass`` / ``@union`` 生成 ``serialize[T: EncoderType]`` / ``deserialize[T: DecoderType]``。"""
  return cls


class const:
  """类型注解标记：``name: T @const = v`` → C++ ``static constexpr`` 成员（非实例字段默认）。"""


class optional:
  """类型注解标记：``name: T @optional = v`` → 不参与 ``__init__`` 形参（默认在构造体内初始化）；
  ``new(kw=…)`` / ``assign`` 关键字仍可赋值；``@dataclass(order=True)`` 时亦不参与 ``__cmp__``。"""


class ref:
  """类型注解标记：``T @ref`` → C++ ``T&``（可变引用；形参/返回值/局部绑定，勿按值拷贝）。"""


class lazy:
  """类型注解标记：``T @lazy`` → 形参 ``PyCallable<T>`` supplier（first-touch memo 求值）。

  与 ``@ref`` 可叠用（``T @ref @lazy``）；默认 ``None`` 表示未传 supplier（``_func == nullptr``）；
  非 ``None`` 默认值在函数入口填充 supplier。调用点实参一律包零参 lambda；同名 lazy 形参透传 supplier。
  """


class thread_local:
  """类型注解标记：``name: T @thread_local = v`` → C++ ``static thread_local`` 类字段。

  该字段按线程隔离存储；通过 ``Self.name`` / ``Class.name`` 访问，不能作为实例普通成员。
  """


def dataclass(
  cls=None,
  /,
  *,
  init: bool = True,
  repr: bool = True,
  eq: bool = True,
  order: bool = False,
  frozen: bool = False,
  kwOnly: bool = False,
  slots: bool = False,
):
  """数据类（翻译期展开 ``__init__`` / ``__eq__`` / ``__repr__`` / ``__cmp__``，见 ``passes/dataclass_expand.py``）。

  ``order=True`` 且未写 ``eq`` 时默认 ``eq=False``（仅 ``__cmp__``）；需 ``__eq__`` 时显式 ``eq=True``。
  """
  if cls is None:

    def wrap(c):
      return c

    return wrap
  return cls


def descriptor(cls):
  """描述符类不生成 C++，``__get__`` / ``__set__`` 内联到宿主类。"""
  return cls


def annotation(
  cls=None,
  /,
  *,
  inheritable: bool = False,
  repeatable: bool = False,
):
  """字段/方法注解类 ``Type @Annotation``，不生成 C++（见 ``passes/annotation_options.py``）。"""
  if cls is None:

    def wrap(c):
      return c

    return wrap
  return cls


def mixin(cls):
  """混入类，不生成 C++。``iterSubclasses`` 等见 ``mixin.py``（译器展开，勿拉入翻译闭包）。"""
  return cls


def refcount(cls):
  """``A(...)`` → ``makeRefCount<A>(...)``；类体由语义生成，见 ``refcount_emit``。"""
  return cls


def boxing(cls):
  """堆上单对象（无引用计数）：``A(...)`` / ``A[T](...)`` → ``new A<...>(...)``。

  用于哈希桶节点、链表节点等。注解 ``Node[T]`` 即 ``Node<T>*``（勿写 ``Pointer[Node[T]]``）；
  无参新建 ``node: Node[T] = new()`` → ``new Node<T>()``；释放用 ``destroy`` + ``free``。
  与 ``@refcount``、``@copyable`` 互斥。
  """
  return cls


def protocol(cls):
  """协议/概念：不生成实例类；产出 SFINAE traits 头（``T: Protocol`` 约束函数模板）。"""
  return cls


def immutable(method):
  """成员函数翻译为 C++ ``const`` 方法（只读 ``this``；与 ``@final`` 方法/字段无关）。"""
  return method


def noexcept(func):
  """函数/方法体 ``raise`` → ``Result::Err``、``return`` → ``Result::Ok``；C++ 签名加 ``noexcept``。

  对外返回 ``Result[T, E]``（``E`` 由函数体内 ``raise`` 静态收集）；用户仍写 ``-> T``。
  不接受参数（勿 ``@noexcept(...)``）。
  """
  return func


def native(func):
  """实现由 C++/手写 ``codegen/*_cpp.py`` 注入；译器只生成声明，不向 ``.inl`` 写入 Python 函数体。

  函数体统一写 ``...``（勿 ``pass`` / ``return`` 占位）。
  """
  return func


def native_name(cppName: str):
  """Python 名 → C++ 名：类（``@native_name(\"PyFoo\")`` / ``@native_name(\"Py*\")``）或模块函数（``@native_name(\"math_*\")``）。"""
  def deco(cls):
    return cls
  return deco


def global_call(cppNameOrFunc=None):
  """包根内建：调用点生成 ``::cppName(...)``。

  与 Python 函数同名时用 ``@global_call`` / ``@global_call(\"py_*\")``；C++ 名与符号名不同时写完整名（如 ``@global_call(\"py_time\")``）。
  """
  def deco(func):
    return func
  if callable(cppNameOrFunc):
    return deco(cppNameOrFunc)
  return deco


@global_call("py_*")
def virtual(method):
  """成员函数翻译为 C++ ``virtual``（用于基类可覆盖方法）。"""
  return method


def abstract(method):
  """纯虚成员；体须 ``...``；隐含 ``virtual``，``.h`` 声明 ``= 0``（``.inl`` 无实现）。"""
  return method


def override(method):
  """成员函数翻译为 C++ ``override``（用于派生类覆盖）。"""
  return method


def overload(func):
  """``@overload``：同名方法须全部标注；``pass`` → 空 C++ 函数体，有语句 → 正常生成实现。"""
  return func


def delegate(func):
  """``@delegate``：C# 风格多播委托类型（``+=`` / ``-=`` / ``operator()``）。"""
  return func


def context(func):
  """``@context``：翻译期上下文工厂（``passes/decorators.py``）。

  - 顶层 ``yield`` 之前/之后为 enter/exit；可作 ``@sample`` 装饰器或 ``with sample:`` 内联。
  - 无顶层 ``yield`` 时与 ``@decorator`` 相同（整段替换被装饰函数体）。
  - 其它 ``with`` 对象仍走 ``__enter__`` / ``__exit__``。
  - ``__func__.__name__``：``with`` 内联时为 ``\"<with context>\"``；作装饰器时为被装饰函数名。
  详见 ``docs/参考手册.md`` §8.6。
  """
  return func


def decorator(func):
  """``@decorator``：翻译期包装工厂；体内 ``yield`` 表示调用被装饰函数（``*_impl``）。

  勿写 ``__func__(...)``；``__func__.__name__`` 为被装饰函数名。详见 ``docs/参考手册.md`` §8.6。
  """
  return func


class staticproperty:
  """类静态属性 → C++ ``static {name}__get()`` / ``static {name}__set(…)``；可写属性配 ``@staticproperty.setter``。

  赋值后回调用 ``@staticproperty.postsetter``（合成 setter 并在赋值后调 ``{name}__postset``；类型由 ``value: T`` 推断）。
  方法体内 ``Self.__value__`` 指存储字段 ``{name}__value``（与实例 ``@property`` 规则相同）。
  """

  def __init__(self, fget):
    self.fget = fget

  @staticmethod
  def setter(fset):
    """``@staticproperty.setter def name(value: T)`` → ``static void name__set(T value)``。"""
    return fset

  @staticmethod
  def postsetter(fpost):
    """``@staticproperty.postsetter def name(value: T)`` → 合成 ``name__set`` + ``name__postset(value)``。"""
    return fpost


# ---------------------------------------------------------------------------
# 迭代与内置函数（``IteratorElementType`` / ``IterableType`` 见 ``util.protocols``）
# ---------------------------------------------------------------------------

from .util.protocols import IterableType, IteratorElementType


def len(obj) -> int:
  return obj.__len__()


class _MacroProbe:
  """``"NAME" in __macro__`` 编译期占位（非运行时容器）。"""


__macro__: _MacroProbe = _MacroProbe()


@global_call("py_*")
def abs(x):
  if x < 0:
    return -x
  return x


@global_call("py_*")
def __cmp__(a, b) -> int:
  """三值比较（``-1`` / ``0`` / ``1``）；标量 ``<``/``>``，类实例委托 ``a.__cmp__(b)``。"""
  if a < b:
    return -1
  if a > b:
    return 1
  return 0


@global_call
def __mod__(a, b):
  """取模：标量 ``::__mod__``；``str % tuple`` → ``::__mod__(fmt, makeTuple(...))``；其它类型 SFINAE 转发 ``__mod__``/``__rmod__``。"""
  return a.__mod__(b)


@global_call
def __truediv__(a, b):
  """真除（Python 3 语义，**非** C++ ``/``）；转发 ``__truediv__``/``__rtruediv__``。"""
  return a.__truediv__(b)


@global_call
def __floordiv__(a, b):
  """地板除；转发 ``__floordiv__``/``__rfloordiv__``。"""
  return a.__floordiv__(b)


@global_call
def chr(i: int) -> str:
  """码点 → 单字符 ``str``。"""
  return ""


@global_call
def ord(c: str) -> char:
  """单字符 ``str`` 字面量 → ``char``（仅 ``ord('x')``；变量用 ``int(c)`` / ``char(s[i])``）。"""
  return char(0)


@global_call
def divmod(a: int, b: int) -> (int, int):
  """``(a // b, a % b)``（对齐 CPython ``divmod``）。"""
  return (a // b, a % b)


@global_call
def pow(base, exp, mod: int = 0):
  """全局 ``pow``：两参数 ``base**exp``；三参数模幂（含 ``pow(3, -1, 5)`` 逆元）。"""
  if mod:
    return base.__pow__(exp, mod)
  return base ** exp


@global_call
def modmul(a, b, mod):
  """``(a * b) % mod``（Python 语义；积在取模前按 ``T`` 拓宽）。"""
  return a.__modmul__(b, mod)


def iter(obj):
  return obj.__iter__()


def next(it):
  return it.__next__()


def aiter(obj):
  return obj.__aiter__()


def anext(it):
  return it.__anext__()


def reversed(obj):
  return obj.__reversed__()


def repr(obj) -> str:
  return obj.__repr__()


@global_call
def hash(obj) -> int:
  return obj.__hash__()


def __contains__(container, item) -> bool:
  return container.__contains__(item)


def new(*args):
  """由注解/返回类型推断的构造：``x: T = new(...)`` 等价于 ``T(...)``。

  静态工厂/方法：``x: JsonDocument[Org] = new.open(...)`` 等价于 ``JsonDocument[Org].open(...)``；
  ``@union`` 变体：``x: Message = new.Quit()`` / ``new.Move(1, 2)`` 等价于 ``Message.Quit()`` / ``Message.Move(1, 2)``（须左侧注解或 ``return`` 返回类型）。
  ``match`` 主体为 ``@union`` 时优先 ``case new.Variant(...):`` 勿 ``case Union.Variant(...):``（S06b）。

  字符串用 ``\"...\"`` 字面量，容器空表用 ``[]``/``{}``（``deque``/``frozendict``/``dict``/``frozenlist`` 等勿无参 ``new()``；``deque`` 有界用 ``new(maxLen)``）；元组用 ``(a, b)``；拷贝/迭代器/view 等字面量无法表达时用 ``new(...)``（勿 ``Cls(...)``，S06b）；注解 ``Self`` 见 S06。
  """
  pass


class ZipIterator[ItL: IteratorElementType, ItR: IteratorElementType]:
  def __init__(self, left: ItL, right: ItR):
    self._left: ItL = iter(left)
    self._right: ItR = iter(right)

  def __iter__(self):
    return self

  def __next__(self) -> (ItL.Element, ItR.Element):
    a = next(self._left)
    b = next(self._right)
    return (a, b)


def zip[ItL: IteratorElementType, ItR: IteratorElementType](left: ItL, right: ItR):
  """与 Python ``zip(left, right)`` 一致：接受可 IterableType 对象，在内部 ``iter()``。"""
  return ZipIterator(left, right)


class EnumerateIterator[Element]:
  def __init__(self, iterable: Element, start: int = 0):
    self._iter = iter(iterable)
    self._index: int = start

  def __iter__(self):
    return self

  def __next__(self) -> (int, Element):
    value: Element = next(self._iter)
    out: (int, Element) = (self._index, value)
    self._index += 1
    return out


def enumerate[Element](xs: IterableType[Element], start: int = 0):
  return EnumerateIterator(xs, start)


@overload
def inlineRange(stop: int):
  """编译期定界 ``for``；参数顺序同 ``range``，由译器完全展开循环体。

  边界须为外层 ``inlineRange`` 循环变量、``Self._dim`` 等 ``@const``、字面量
  及其一元/二元嵌套（``inlineRange(k + 1, Self._dim)`` 等）。
  循环体内不支持 ``break`` / ``continue``；主要用于 ``@mixin``（``expand_inline_range``）。
  """
  ...


@overload
def inlineRange(start: int, stop: int, step: int = 1):
  ...


def format(value, formatSpec: str = "") -> str:
  """``format(value, formatSpec)`` → ``value.__format__(formatSpec)``（对齐 CPython）。"""
  pass


@global_call("py_*")
def input[Element = str](prompt: str = "") -> Element:
  """内置 input。

  ``input()`` / ``input[str]()`` 读取 stdin 一行并去掉行尾换行；``input[int]()``
  等标量特化走 C 层扫描（如 ``scanf("%d", &x)``）；未读到任何字符即 EOF 时抛 ``EOFError``。
  """
  return cast[Element](prompt)


def print(*args, sep: CStr = " ", end: CStr = "\n", flush: bool = False):
  """内置 print：普通实参 ``str(...)`` 后 ``fprintf``；f-string 实参 ``PyStr::format``（见 ``_emit_print``）。"""
  pass

