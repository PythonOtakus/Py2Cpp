"""``check_strict_style`` 翻译期强检查。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.translation_error import TranslationError
from src.translator import Translator


class StrictStyleTests(unittest.TestCase):
  def _translate(self, body: str, *, strict: bool = True) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      Translator.translate_file(
        str(py),
        output_dir=str(out / "generated"),
        include_stdlib=True,
        strict=strict,
      )

  def _expect_strict_fail(self, body: str, rule: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
          include_stdlib=True,
          strict=True,
        )
      self.assertIn(f"[{rule}]", str(ctx.exception))

  def test_s0404_rejects_optional_outside_dataclass(self):
    self._expect_strict_fail(
      """@copyable
class Opt:
  xs: list[int] @optional = []
""",
      "S0404",
    )

  def test_s0101_rejects_dunder_call(self):
    self._expect_strict_fail(
      """def main():
  xs: list[int] = [1]
  return xs.__len__()
""",
      "S0101",
    )

  def test_s0101_rejects_dunder_inside_dunder_body(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

  def __copy__(self, other: Self):
    self.n = other.__len__()

def main():
  a: Box = new()
  b: Box = new()
  b.__copy__(a)
  return b.n
""",
      "S0101",
    )

  def test_s0101_allows_global_cmp_only(self):
    self._translate(
      """class Pair:
  a: int = 0
  b: int = 0

  def __cmp__(self, other: Self) -> int:
    c: int = __cmp__(self.a, other.a)
    if c:
      return c
    return __cmp__(self.b, other.b)

def main():
  p: Pair = new(a=1, b=2)
  q: Pair = new(a=1, b=3)
  return __cmp__(p, q)
"""
    )

  def test_s0101_allows_super_init_in_subclass_init(self):
    self._translate(
      """class Base:
  n: int

  def __init__(self, n: int = 0):
    self.n = n


class Derived(Base):
  def __init__(self, n: int = 0):
    super.__init__(n)


def main():
  d: Derived = new(3)
  return d.n
"""
    )

  def test_s0101_allows_self_init_forward_in_overload(self):
    self._translate(
      """class Pair:
  a: int
  b: int

  @overload
  def __init__(self, a: int):
    self.__init__(a, 0)

  @overload
  def __init__(self, a: int, b: int):
    self.a = a
    self.b = b


def main():
  p: Pair = new(1)
  return p.a + p.b
"""
    )

  def test_s0101_rejects_self_init_outside_init(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

  def bump(self):
    self.__init__(0)


def main():
  b: Box = new()
  b.bump()
  return b.n
""",
      "S0101",
    )

  def test_s0101_rejects_cmp_attribute(self):
    self._expect_strict_fail(
      """class Pair:
  a: int = 0

  def __cmp__(self, other: Self) -> int:
    return self.a.__cmp__(other.a)
""",
      "S0101",
    )

  def test_s0101_rejects_aenter_attribute_in_user_code(self):
    self._expect_strict_fail(
      """class CM:
  async def __aenter__(self) -> int:
    return 0

  async def __aexit__(self):
    return None

def main():
  cm: CM = new()
  return cm.__aenter__()
""",
      "S0101",
    )

  def test_s0101_allows_await_attribute_in_user_code(self):
    self._translate(
      """class AwaitableBox:
  def __await__(self) -> int:
    return 1

def main():
  box: AwaitableBox = new()
  aw = box.__await__()
  return aw
"""
    )

  def test_s0101_allows_copy_in_non_copyable(self):
    self._translate(
      """class Box:
  n: int = 0

  def __copy__(self, other: Self):
    self.n = other.n

  @immutable
  def copy(self) -> Self:
    out: Self = new()
    out.__copy__(self)
    return out

def main():
  a: Box = new(n=7)
  return a.copy().n
"""
    )

  def test_s0101_rejects_copy_in_copyable(self):
    self._expect_strict_fail(
      """@copyable
class Box:
  n: int = 0

  def __copy__(self, other: Self):
    self.n = other.n

  @immutable
  def copy(self) -> Self:
    out: Self = new()
    out.__copy__(self)
    return out

def main():
  a: Box = new(n=7)
  return a.copy().n
""",
      "S0101",
    )

  def test_s0101_allows_move_in_copyable(self):
    self._translate(
      """@copyable
class Node:
  n: int = 0

  def __move__(self, other: Self):
    self.n = other.n
    other.n = 0

  def take_from(self, other: Self) -> None:
    self.n = other.n
    other.n = 0

def main():
  a: Node = new(n=1)
  b: Node = new()
  b.take_from(a)
  return b.n
"""
    )

  def test_s0101_rejects_move_in_non_copyable(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

  def __move__(self, other: Self):
    self.n = other.n
    other.n = 0

  def take_from(self, other: Self) -> None:
    self.__move__(other)

def main():
  a: Box = new(n=1)
  b: Box = new()
  b.take_from(a)
  return b.n
""",
      "S0101",
    )

  def test_s0102_rejects_empty_list_factory(self):
    self._expect_strict_fail(
      """def main():
  xs: list[int] = list()
  return len(xs)
""",
      "S0301",
    )

  def test_s0303_rejects_deque_empty_new(self):
    self._expect_strict_fail(
      """def main():
  q: deque[int] = new()
  return len(q)
""",
      "S0303",
    )

  def test_s0303_rejects_delegate_explicit_ctor(self):
    self._expect_strict_fail(
      """@delegate
def FuncDelegate[T](x: T) -> T: ...

def main():
  d: FuncDelegate[int] = FuncDelegate[int]()
  return 0
""",
      "S0303",
    )

  def test_s0303_allows_deque_new_maxlen(self):
    self._translate(
      """def main():
  q: deque[int] = new(2)
  q.append(1)
  return len(q)
"""
    )

  def _strict_fail_message(self, body: str, rule: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
          include_stdlib=True,
          strict=True,
        )
      self.assertIn(f"[{rule}]", str(ctx.exception))
      return str(ctx.exception)

  def test_s0101_message_suggests_len_builtin(self):
    msg = self._strict_fail_message(
      """def main():
  xs: list[int] = [1]
  return xs.__len__()
""",
      "S0101",
    )
    self.assertIn("len(x)", msg)
    self.assertIn("例如", msg)

  def test_s0302_message_suggests_aug_assign(self):
    msg = self._strict_fail_message(
      """def main():
  n: int = 0
  n = n + 1
  return n
""",
      "S0704",
    )
    self.assertIn("+=", msg)
    self.assertIn("n = n +", msg)

  def test_s0704_message_suggests_imatmul_aug_assign(self):
    msg = self._strict_fail_message(
      """class M:
  def __matmul__(self, other: Self) -> Self:
    return self

  def step(self, other: Self) -> None:
    p: Self = self
    p = p @ other

def main():
  a: M = new()
  b: M = new()
  a.step(b)
  return 0
""",
      "S0704",
    )
    self.assertIn("@=", msg)
    self.assertIn("p = p @", msg)

  def test_s0303_message_suggests_not_seq(self):
    msg = self._strict_fail_message(
      """def main():
  xs: list[int] = []
  if len(xs) == 0:
    return 1
  return 0
""",
      "S0701",
    )
    self.assertIn("not xs", msg)
    self.assertIn("len(xs) == 0", msg)

  def test_s0103_rejects_user_ctor_in_init(self):
    self._expect_strict_fail(
      """class Box:
  def __init__(self, n: int):
    self.n: int = n

def main():
  b: Box = Box()
  return b.n
""",
      "S0303",
    )

  def test_s0103_rejects_new_in_call_arg(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

def use(b: Box) -> int:
  return b.n

def main():
  return use(new(n=1))
""",
      "S0307",
    )

  def test_s0103_allows_cls_in_call_arg(self):
    self._translate(
      """class Box:
  n: int = 0

def use(b: Box) -> int:
  return b.n

def main():
  return use(Box(n=1))
"""
    )

  def test_s0103_rejects_new_when_literal(self):
    self._expect_strict_fail(
      """def main():
  xs: list[int] = new()
  return len(xs)
""",
      "S0303",
    )

  def test_s0103_rejects_new_empty_str(self):
    self._expect_strict_fail(
      """def main():
  s: str = new("")
  return len(s)
""",
      "S0303",
    )

  def test_s0103_rejects_empty_set_factory(self):
    self._expect_strict_fail(
      """def main():
  s: set[int] = set()
  return len(s)
""",
      "S0303",
    )

  def test_s0103_allows_empty_set_new(self):
    self._translate(
      """def main():
  return len(set[int]())
"""
    )

  def test_s0303_allows_async_desugar_ctor_in_coroutine(self):
    """协程脱糖可翻译；``*_coroutine`` 体内 ``__aenter__``/``__aexit__``/``__await__`` 由 S0101 脱糖豁免。"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        """from py2cpp import *

class SimpleAsyncCM:
  async def __aenter__(self) -> int:
    return 1

  async def __aexit__(self):
    return None

async def use_async_with() -> int:
  cm: SimpleAsyncCM = new()
  async with cm as v:
    return v

def main() -> int:
  return 0
""",
        encoding="utf-8",
      )
      Translator.translate_file(
        str(py),
        output_dir=str(out / "generated"),
        include_stdlib=False,
        strict=True,
      )

  def test_s0103_rejects_self_with_args_when_ann_self(self):
    self._expect_strict_fail(
      """class Holder:
  data: int = 0

  def __init__(self, data: int):
    self.data = data

  def dup(self) -> Self:
    out: Self = Self(1)
    return out

def main():
  h: Holder = new(data=0)
  return h.dup().data
""",
      "S0304",
    )

  def test_s0103_allows_new_with_args_when_ann_self(self):
    self._translate(
      """class Holder:
  data: int

  def __init__(self, data: int):
    self.data = data

  def dup(self) -> Self:
    return new(1)

def main():
  h: Holder = new(data=0)
  return h.dup().data
"""
    )

  def test_s0103_rejects_new_in_aug_assign(self):
    body = """class Holder:
  data: int = 0

  def __init__(self, data: int):
    self.data = data

  def mix(self, ch: int) -> Self:
    out: Self = new()
    out += new(ch)
    return out

def main():
  h: Holder = new(data=0)
  return h.mix(1).data
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
          include_stdlib=True,
          strict=True,
        )
    msg = str(ctx.exception)
    self.assertIn("[S0305]", msg)
    self.assertIn("增强赋值", msg)
    self.assertIn("Self(...)", msg)
    self.assertIn("out += Self", msg)

  def test_s0103_rejects_new_in_return_binop(self):
    body = """class Holder:
  def join(self, tail: int) -> Self:
    head: Self = new()
    return head + new(tail)

def main():
  h: Holder = new()
  return 0
"""
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(f"from py2cpp import *\n\n{body}", encoding="utf-8")
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
          include_stdlib=True,
          strict=True,
        )
    msg = str(ctx.exception)
    self.assertIn("[S0306]", msg)
    self.assertIn("二元表达式", msg)
    self.assertIn("return out + Self", msg)

  def test_s0103_allows_self_in_aug_assign(self):
    self._translate(
      """class Holder:
  data: int

  def __init__(self, data: int):
    self.data = data

  def mix(self, ch: int) -> Self:
    out: Self = new(0)
    out += Self(ch)
    return out

def main():
  h: Holder = new(data=0)
  return h.mix(1).data
"""
    )

  def test_s0103_allows_self_in_return_binop(self):
    self._translate(
      """class Holder:
  data: int

  def __init__(self, data: int):
    self.data = data

  def join(self, tail: int) -> Self:
    head: Self = new(0)
    return head + Self(tail)

def main():
  h: Holder = new(data=1)
  return h.join(2).data
"""
    )

  def test_s0306_allows_explicit_cls_in_binop(self):
    self._translate(
      """from py2cpp.spatial.rotator import Quaternion
from py2cpp.spatial.vector import Vector3

def main() -> int:
  q: Quaternion = new(1.0, 0.0, 0.0, 0.0)
  v: Vector3 = q * Vector3(1.0, 0.0, 0.0)
  return 0 if almost(v.x, 1.0) else 1
"""
    )

  def test_s0306_rejects_new_staticproperty_in_binop(self):
    self._expect_strict_fail(
      """from py2cpp.spatial.rotator import Quaternion
from py2cpp.spatial.vector import Vector3

def main() -> int:
  q: Quaternion = new(1.0, 0.0, 0.0, 0.0)
  v: Vector3 = q * new.right
  return 0
""",
      "S0306",
    )

  def test_s0103_self_annotation_empty_self_rejected(self):
    self._expect_strict_fail(
      """class Holder:
  def blank(self) -> Self:
    return Self()

def main():
  h: Holder = new()
  return 0
""",
      "S0304",
    )

  def test_s0103_self_annotation_empty_new_ok(self):
    self._translate(
      """class Holder:
  def blank(self) -> Self:
    return new()

def main():
  h: Holder = new()
  return 0
"""
    )

  def test_s0304_rejects_subscript_ctor_with_typed_return(self):
    self._expect_strict_fail(
      """class box_iterator:
  data: int = 0

  def __init__(self, box: Box):
    self.data = box.data

class Box:
  data: int = 0

  def __iter__(self) -> box_iterator:
    return box_iterator(self)

def main():
  b: Box = new()
  return b.data
""",
      "S0304",
    )

  def test_s0304_rejects_items_view_ctor_with_typed_return(self):
    self._expect_strict_fail(
      """class items_view:
  pass

class Mapping:
  def items(self) -> items_view:
    return items_view(self)

def main():
  m: Mapping = new()
  return 0
""",
      "S0304",
    )

  def test_s0304_rejects_pool_slot_loc_ctor_with_typed_ann(self):
    self._expect_strict_fail(
      """class PoolSlotLoc:
  block: int = 0
  offset: int = 0

  def __init__(self, block: int, offset: int):
    self.block = block
    self.offset = offset

def main():
  loc: PoolSlotLoc = PoolSlotLoc(-1, -1)
  return loc.block
""",
      "S0304",
    )

  def test_s0309_rejects_redundant_cast_subscript(self):
    self._expect_strict_fail(
      """from py2cpp import *

@refcount
class Base:
  pass

@refcount
class Derived(Base):
  pass

def narrow(slot: Base) -> None:
  d: Derived @ref = cast[Derived](slot)
""",
      "S0309",
    )

  def test_s0309_allows_cast_shorthand(self):
    self._translate(
      """from py2cpp import *

@refcount
class Base:
  pass

@refcount
class Derived(Base):
  pass

def narrow(slot: Base) -> None:
  d: Derived @ref = cast(slot)
"""
    )

  def test_s0501_rejects_private_field_accessor_pair(self):
    self._expect_strict_fail(
      """@copyable
class Box:
  _kind: int = 0

  def kind(self) -> int:
    return self._kind

  def setKind(self, kind: int) -> None:
    self._kind = kind

def main():
  b: Box = new()
  b.setKind(1)
  return b.kind()
""",
      "S0501",
    )

  def test_s0501_allows_property_accessor(self):
    self._translate(
      """@copyable
class Box:
  _kind: int = 0

  @property
  def kind(self) -> int:
    return self._kind

  @property.setter
  def kind(self, kind: int) -> None:
    self._kind = kind

def main():
  b: Box = new()
  b.kind = 1
  return b.kind
"""
    )

  def test_s0501_allows_getter_without_setter(self):
    self._translate(
      """@copyable
class Box:
  _done: bool = False

  def markDone(self) -> None:
    self._done = True

  def isDone(self) -> bool:
    return self._done

def main():
  b: Box = new()
  b.markDone()
  return b.isDone()
"""
    )

  def test_s0501_rejects_get_set_named_pair(self):
    self._expect_strict_fail(
      """@copyable
class Box:
  _value: int = 0

  def getValue(self) -> int:
    return self._value

  def setValue(self, value: int) -> None:
    self._value = value

def main():
  b: Box = new()
  b.setValue(1)
  return b.getValue()
""",
      "S0501",
    )

  def test_s0501_rejects_is_set_named_pair(self):
    self._expect_strict_fail(
      """@copyable
class Box:
  _done: bool = False

  def isDone(self) -> bool:
    return self._done

  def setDone(self, done: bool) -> None:
    self._done = done

def main():
  b: Box = new()
  b.setDone(True)
  return b.isDone()
""",
      "S0501",
    )

  def test_s0501_allows_setter_with_extra_param(self):
    self._translate(
      """@copyable
class Store:
  _data: dict[str, int] = {}

  def getValue(self, name: str) -> int:
    return self._data[name]

  def setValue(self, name: str, value: int) -> None:
    self._data[name] = value

def main():
  s: Store = new()
  s.setValue("x", 1)
  return s.getValue("x")
"""
    )

  def test_s0502_rejects_assign_then_callback_property(self):
    self._expect_strict_fail(
      """@copyable
class Panel:
  _title: str = ""
  rev: int = 0

  def _sync(self) -> None:
    self.rev += 1

  @property
  def title(self) -> str:
    return self._title

  @property.setter
  def title(self, value: str) -> None:
    self._title = value
    self._sync()

def main():
  p: Panel = new()
  p.title = "hi"
  return p.rev
""",
      "S0502",
    )

  def test_s0502_allows_postsetter(self):
    self._translate(
      """@copyable
class Panel:
  rev: int = 0

  def _sync(self) -> None:
    self.rev += 1

  @property.postsetter
  def title(self, value: str) -> None:
    self._sync()

def main():
  p: Panel = new()
  p.title = "hi"
  return p.rev
"""
    )

  def test_s0502_allows_pure_property_setter(self):
    self._translate(
      """@copyable
class Box:
  _kind: int = 0

  @property
  def kind(self) -> int:
    return self._kind

  @property.setter
  def kind(self, kind: int) -> None:
    self._kind = kind

def main():
  b: Box = new()
  b.kind = 1
  return b.kind
"""
    )

  def test_s0502_allows_delegate_setter(self):
    """``self._reserve(value)`` / ``if`` 分支赋值等非顶层 assign+callback 豁免。"""
    self._translate(
      """@copyable
class Buffer:
  _capacity: int = 0

  def _reserve(self, capacity: int) -> None:
    if capacity > self._capacity:
      self._capacity = capacity

  @property
  def capacity(self) -> int:
    return self._capacity

  @property.setter
  def capacity(self, value: int) -> None:
    self._reserve(value)

def main():
  b: Buffer = new()
  b.capacity = 8
  return b.capacity
"""
    )

  def test_s0502_allows_conditional_assign_setter(self):
    self._translate(
      """@copyable
class Table:
  _capacity: int = 8
  _size: int = 0

  @property
  def capacity(self) -> int:
    return self._capacity

  @property.setter
  def capacity(self, value: int) -> None:
    if value < 8:
      value = 8
    if value <= self._capacity:
      return
    if self._size == 0:
      self._capacity = value

def main():
  t: Table = new()
  t.capacity = 16
  return t.capacity
"""
    )

  def test_s0303_rejects_empty_frozendict_new(self):
    self._expect_strict_fail(
      """def main():
  fd: frozendict[int, int] = new()
  return 0
""",
      "S0303",
    )

  def test_s0301_rejects_empty_frozendict_factory(self):
    self._expect_strict_fail(
      """def main():
  fd: frozendict[int, int] = frozendict()
  return 0
""",
      "S0301",
    )

  def test_s0304_allows_new_with_single_arg_copy(self):
    """注解目标类 + ``new(src)``（非空容器字面量）应通过 strict 且可翻译。"""
    self._translate(
      """class slot_loc:
  a: int
  b: int

  def __init__(self, a: int, b: int):
    self.a = a
    self.b = b

def main():
  hit: slot_loc = new(1, 2)
  dup: slot_loc = new(hit)
  return dup.a
"""
    )

  def test_s0304_allows_new_self_with_typed_return(self):
    self._translate(
      """class box_iterator:
  data: int

  def __init__(self, box: Box):
    self.data = box.data

class Box:
  data: int = 0

  def __iter__(self) -> box_iterator:
    return new(self)

def main():
  b: Box = new()
  return b.data
"""
    )

  def test_s0304_rejects_self_static_factory_with_self_ann(self):
    self._expect_strict_fail(
      """class Mat:
  a: int = 0
  b: int = 0

  def __init__(self, a: int, b: int):
    self.a = a
    self.b = b

  @staticmethod
  def from_parts(a: int, b: int) -> Self:
    return new(a, b)

  def make(self) -> Self:
    m: Self = Self.from_parts(1, 2)
    return m

def main():
  x: Mat = new()
  return x.make()
""",
      "S0304",
    )

  def test_s0304_allows_new_static_factory_with_self_ann(self):
    self._translate(
      """class Mat:
  a: int
  b: int

  def __init__(self, a: int, b: int):
    self.a = a
    self.b = b

  @staticmethod
  def from_parts(a: int, b: int) -> Self:
    return new(a, b)

  def make(self) -> Self:
    return new.from_parts(1, 2)

def main():
  x: Mat = new(0, 0)
  return x.make()
"""
    )

  def test_s0304_rejects_self_staticproperty(self):
    self._expect_strict_fail(
      """class Mat:
  @staticproperty
  def zero() -> Self:
    return new()

  def make(self) -> Self:
    return Self.zero

def main():
  x: Mat = new()
  return x.make()
""",
      "S0304",
    )

  def test_s0304_allows_new_staticproperty(self):
    self._translate(
      """class Mat:
  @staticproperty
  def zero() -> Self:
    return new()

  def make(self) -> Self:
    return new.zero

def main():
  x: Mat = new()
  return x.make()
"""
    )

  def test_s0304_allows_self_staticproperty_when_ann_is_not_host(self):
    self._translate(
      """class Mat:
  @staticproperty
  def helpText() -> str:
    return "usage"

  def make(self) -> str:
    usage: str = Self.helpText
    return usage

def main():
  x: Mat = new()
  return x.make()
"""
    )

  def test_s0103_self_annotation_empty_str_literal_rejected(self):
    self._expect_strict_fail(
      """class Holder:
  def blank(self) -> Self:
    return ""

def main():
  h: Holder = new()
  return 0
""",
      "S0304",
    )

  def test_s0103_str_class_allows_empty_literal_with_self_return(self):
    self._translate(
      """class str:
  def blank(self) -> Self:
    return ""

def main():
  return 0
"""
    )

  def test_s0103_list_class_allows_literal_with_self_return(self):
    self._translate(
      """class list[Element]:
  def blank(self) -> Self:
    return []

  def dup(self, other: Self) -> Self:
    return [*self, *other]

def main():
  return 0
"""
    )

  def test_s0103_list_class_rejects_empty_new_with_self_return(self):
    self._expect_strict_fail(
      """class list[Element]:
  def blank(self) -> Self:
    return new()

def main():
  return 0
""",
      "S0303",
    )

  def test_s0103_rejects_self_when_literal(self):
    self._expect_strict_fail(
      """class Holder:
  def build(self) -> list[int]:
    scratch: list[int] = Self()
    return scratch

def main():
  h: Holder = new()
  return len(h.build())
""",
      "S0303",
    )

  def test_s0103_rejects_new_on_self_field_assign(self):
    self._expect_strict_fail(
      """@copyable
class Grid:
  adj: list[list[int]]

  def reset(self) -> None:
    self.adj = new()

def main():
  g: Grid = new()
  g.reset()
  return len(g.adj)
""",
      "S0303",
    )

  def test_s0103_rejects_new_on_other_field_assign(self):
    self._expect_strict_fail(
      """@copyable
class Grid:
  adj: list[list[int]]

  def __move__(self, other: Self) -> None:
    other.adj = new()

def main():
  g: Grid = new()
  return 0
""",
      "S0303",
    )

  def test_s0103_allows_literal_on_other_field_assign(self):
    self._translate(
      """@copyable
class Grid:
  adj: list[list[int]]

  def __move__(self, other: Self) -> None:
    other.adj = []

def main():
  g: Grid = new()
  return 0
"""
    )

  def test_s0303_rejects_len_eq_zero(self):
    self._expect_strict_fail(
      """def main():
  s: str = "ab"
  if len(s) == 0:
    return 0
  return 1
""",
      "S0701",
    )

  def test_s0308_rejects_zero_lower_slice(self):
    self._expect_strict_fail(
      """def main():
  s: str = "abcd"
  return s[0:2]
""",
      "S0702",
    )

  def test_s0602_rejects_same_class_name_in_expr(self):
    self._expect_strict_fail(
      """class Point:
  x: int = 0
  y: int = 0

  @staticmethod
  def _sqr_length(v: Self) -> int:
    return v.x * v.x + v.y * v.y

  def dist_sq(self) -> int:
    return Point._sqr_length(self)

  @staticproperty
  def zero() -> Self:
    return new(0, 0)

  def make_zero(self) -> Self:
    return Point.zero
""",
      "S0602",
    )

  def test_s0602_allows_self_static_in_expr(self):
    self._translate(
      """class Point:
  x: int = 0
  y: int = 0

  @staticmethod
  def _sqr_length(v: Self) -> int:
    return v.x * v.x + v.y * v.y

  def length_plus_one(self) -> int:
    n: int = Self._sqr_length(self)
    return n + 1

  @staticproperty
  def zero() -> Self:
    return new(0, 0)

  def make_zero(self) -> Self:
    return new.zero
"""
    )

  def test_s0602_rejects_len_minus_k_subscript(self):
    self._expect_strict_fail(
      """def main():
  path: list[int] = []
  path.append(0)
  return path[len(path) - 1]
""",
      "S0703",
    )

  def test_disabled_when_not_strict(self):
    self._translate(
      """def main():
  xs: list[int] = list()
  return xs.__len__()
""",
      strict=False,
    )

  def test_allows_new_and_not_empty(self):
    self._translate(
      """class Box:
  def __init__(self, n: int):
    self.n: int = n

def main():
  b: Box = new(1)
  s: str = ""
  if not s:
    return b.n
  return s[:2]
"""
    )

  def test_s0701_rejects_self_field_ann_outside_init(self):
    self._expect_strict_fail(
      """class Box:
  def __init__(self, n: int):
    self.n: int = n

  def reset(self) -> None:
    self.n: int = 0

def main():
  b: Box = new(1)
  b.reset()
  return b.n
""",
      "S0601",
    )

  def test_s0702_rejects_class_name_annotation(self):
    self._expect_strict_fail(
      """class Point:
  def copy(self) -> Point:
    out: Point = new(0, 0)
    return out

def main():
  p: Point = new(1, 2)
  q: Point = p.copy()
  return q.copy().x
""",
      "S0602",
    )

  def test_s0702_allows_self_in_class_body(self):
    self._translate(
      """class Point:
  x: int = 0
  y: int = 0

  def copy(self) -> Self:
    return new(self.x, self.y)

def main():
  p: Point = new(1, 2)
  q: Point = p.copy()
  return q.x
"""
    )

  def test_s0702_allows_other_type_param_same_template(self):
    self._translate(
      """
class Box[Element]:
  def pair[Item](self, other: Box[Item] @ref) -> int:
    return 0

def main():
  a: Box[int] = new()
  b: Box[int] = new()
  _ = 0
  return a.pair(b)
"""
    )

  def test_s0602_allows_other_generic_instantiation(self):
    self._translate(
      """from py2cpp import *

class Task[Element]:
  @staticmethod
  def sleep() -> Task[None]:
    return new()

  @staticmethod
  def gather[Item](*items: Task[Item][:]) -> Task[list[Item]]:
    return new()

def main():
  Task[int].sleep()
  return 0
"""
    )

  def test_s0602_rejects_same_class_type_param_in_annotation(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Task[Element]:
  def copy(self) -> Task[Element]:
    out: Task[Element] = new()
    return out

def main():
  t: Task[int] = new()
  return t.copy()
""",
      "S0602",
    )

  def test_s0703_rejects_duplicate_without_overload(self):
    self._expect_strict_fail(
      """def foo(x: int) -> int:
  return x

def foo(y: str) -> str:
  return y

def main():
  return foo(1)
""",
      "S1001",
    )

  def test_s0703_allows_all_overload(self):
    self._translate(
      """class Scaler:
  base: int = 1

  @overload
  def scale(self) -> int:
    return self.base

  @overload
  def scale(self, factor: int) -> int:
    return self.base * factor

def main():
  s: Scaler = new()
  return s.scale(2)
"""
    )

  def test_s1002_allows_shadow_without_base_virtual(self):
    self._translate(
      """class Base:
  def foo(self) -> int:
    return 0

class Child(Base):
  def foo(self) -> int:
    return 1

def main():
  c: Child = new()
  return c.foo()
"""
    )

  def test_s1002_rejects_missing_override_on_virtual_base(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Base:
  @virtual
  def foo(self) -> int:
    return 0

class Child(Base):
  def foo(self) -> int:
    return 1

def main():
  c: Child = new()
  return c.foo()
""",
      "S1002",
    )

  def test_s1002_allows_override_without_base_virtual(self):
    self._translate(
      """from py2cpp import *

class Base:
  def foo(self) -> int:
    return 0

class Child(Base):
  @override
  def foo(self) -> int:
    return 1

def main():
  c: Child = new()
  return c.foo()
"""
    )

  def test_s0704_allows_both_override_and_virtual(self):
    self._translate(
      """from py2cpp import *

class Base:
  @virtual
  def foo(self) -> int:
    return 0

class Child(Base):
  @override
  def foo(self) -> int:
    return 1

def main():
  c: Child = new()
  return c.foo()
"""
    )

  def test_s1002_rejects_missing_override_on_abstract_base(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Base:
  @abstract
  def foo(self) -> int:
    ...

class Child(Base):
  def foo(self) -> int:
    return 1

def main():
  c: Child = new()
  return c.foo()
""",
      "S1002",
    )

  def test_s1002_rejects_missing_override_on_abstract_chain(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Base:
  @abstract
  def foo(self) -> int:
    ...

class Mid(Base):
  @override
  def foo(self) -> int:
    return 0

class Child(Mid):
  def foo(self) -> int:
    return 1

def main():
  c: Child = new()
  return c.foo()
""",
      "S1002",
    )

  def test_s1002_rejects_missing_override_on_static_protocol_impl(self):
    self._expect_strict_fail(
      """from py2cpp import *

@protocol
class IParsableType:
  @staticmethod
  @abstract
  def parse(s: str) -> Self: ...

class Widget:
  @staticmethod
  def parse(s: str) -> Self:
    return new(0)

def try_parse[T: IParsableType](s: str) -> T:
  return T.parse(s)

def main():
  w: Widget = try_parse[Widget]("1")
  return 0
""",
      "S1002",
    )

  def test_s1002_rejects_missing_override_on_static_inherit_chain(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Base:
  @staticmethod
  @override
  def tag() -> str:
    return "base"

class Child(Base):
  @staticmethod
  def tag() -> str:
    return "child"

def main():
  return Child.tag()
""",
      "S1002",
    )

  def test_s1003_rejects_virtual_and_final(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Box:
  @virtual
  @final
  def value(self) -> int:
    return 0

def main():
  b: Box = new()
  return b.value()
""",
      "S1003",
    )

  def test_s1003_rejects_abstract_and_virtual(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Base:
  @abstract
  @virtual
  def foo(self) -> int:
    ...

def main():
  pass
""",
      "S1003",
    )

  def test_s1003_allows_final_alone(self):
    self._translate(
      """from py2cpp import *

class Box:
  @final
  def value(self) -> int:
    return 0

def main():
  b: Box = new()
  return b.value()
"""
    )


  def test_s0705_rejects_explicit_memory_type_arg(self):
    self._expect_strict_fail(
      """class Widget:
  pass

def drop(p: Pointer[Widget]) -> None:
  destroy[Widget](p)
""",
      "S0308",
    )

  def test_s0705_allows_deduced_memory_calls(self):
    self._translate(
      """class Widget:
  pass

def drop(p: Pointer[Widget]) -> None:
  destroy(p)
  free(p)
"""
    )

  def test_s0706_rejects_outermost_tuple_subscript(self):
    self._expect_strict_fail(
      """def pair() -> tuple[int, int]:
  return (1, 2)
""",
      "S0603",
    )

  def test_s0706_allows_tuple_inside_generic(self):
    self._translate(
      """def rows() -> list[tuple[int, int]]:
  out: list[tuple[int, int]] = []
  return out
"""
    )

  def test_s0706_allows_parenthesized_tuple_type(self):
    self._translate(
      """def pair() -> (int, int):
  return (1, 2)
"""
    )

  def test_s0601_rejects_push_back_def_only(self):
    self._expect_strict_fail(
      """class Box:
  def push_back(self, x: int) -> None:
    pass
""",
      "S0102",
    )

  def test_s0601_rejects_leading_underscore_push_back_def(self):
    msg = self._strict_fail_message(
      """class Box:
  def _push_back(self, x: int) -> None:
    pass
""",
      "S0102",
    )
    self.assertIn("push_back", msg)
    self.assertIn("前导 `_`", msg)

  def test_s0601_allows_leading_underscore_reserve_def(self):
    self._translate(
      """class Buf:
  def _reserve(self, n: int) -> None:
    pass
"""
    )

  def test_s0102_allows_rect_contains_and_size(self):
    self._translate(
      """class Rect:
  @property
  def size(self) -> int:
    return 0

  def contains(self, point: int) -> bool:
    return True
"""
    )

  def test_s0102_rejects_contains_outside_rect(self):
    self._expect_strict_fail(
      """class Box:
  def contains(self, x: int) -> bool:
    return True
""",
      "S0102",
    )

  def test_s0601_allows_cpp_style_method_call(self):
    self._translate(
      """class Box:
  def append(self, x: int) -> None:
    pass

def use(b: Box) -> None:
  b.push_back(1)
"""
    )

  def test_s0601_allows_reserve_on_buffer(self):
    self._translate(
      """class Buf:
  def reserve(self, n: int) -> None:
    pass

def grow(b: Buf) -> None:
  b.reserve(8)
"""
    )

  def test_s0102_rejects_resize_def(self):
    self._expect_strict_fail(
      """class Buf:
  def resize(self, n: int) -> None:
    pass
""",
      "S0102",
    )

  def test_s0102_allows_reshape_def(self):
    self._translate(
      """class Buf:
  def reshape(self, n: int) -> None:
    pass
"""
    )

  def test_s1004_rejects_unused_header_type_param(self):
    self._expect_strict_fail(
      """def bad[Nav, Node: DictKeyType](nav: NavigatableType[Node], start: Node) -> Node:
  return start
""",
      "S1004",
    )

  def test_s1004_allows_navigatable_node_pattern(self):
    self._translate(
      """def ok[Node: DictKeyType](nav: NavigatableType[Node], start: Node) -> Node:
  return start
""",
    )

  def test_s1001_rejects_ascending_while_index_plus(self):
    self._expect_strict_fail(
      """def scan(n: int) -> int:
  i: int = 0
  s: int = 0
  while i < n:
    s += i
    i += 1
  return s
""",
      "S0705",
    )

  def test_s1001_rejects_descending_while_index_minus(self):
    msg = self._strict_fail_message(
      """def down(n: int) -> int:
  i: int = n
  s: int = 0
  while i > 0:
    s += i
    i -= 2
  return s
""",
      "S0705",
    )
    self.assertIn("range", msg)

  def test_s1001_rejects_lte_while_index_plus(self):
    self._expect_strict_fail(
      """def walk(stop: int) -> None:
  i: int = 0
  while i <= stop:
    i += 1
""",
      "S0705",
    )

  def test_s0705_allows_while_with_extra_index_assign(self):
    self._translate(
      """def mixed(n: int) -> None:
  i: int = 0
  while i < n:
    if i % 2 == 0:
      i += 2
    else:
      i += 1
"""
    )

  def test_s0705_allows_while_with_index_reassign(self):
    self._translate(
      """def scan(n: int) -> None:
  i: int = 0
  while i < n:
    j: int = i + 1
    i = j
"""
    )

  def test_s1001_allows_while_cur_is_not_none(self):
    self._translate(
      """class Node:
  next: Pointer[Self]

def walk(head: Pointer[Node]) -> None:
  cur: Pointer[Node] = head
  while cur is not None:
    cur = cur.next
"""
    )

  def test_s1001_allows_dual_pointer_reverse(self):
    self._translate(
      """def swap_pair(a: list[int]) -> None:
  lo: int = 0
  hi: int = len(a) - 1
  while lo < hi:
    t: int = a[lo]
    a[lo] = a[hi]
    a[hi] = t
    lo += 1
    hi -= 1
"""
    )

  def test_s1001_allows_negative_step_plus_on_gt(self):
    self._translate(
      """def rev(stop: int, step: int) -> None:
  i: int = 10
  while i > stop:
    i += step
"""
    )

  def test_s1002_rejects_range_zero_start(self):
    self._expect_strict_fail(
      """def walk(n: int) -> int:
  s: int = 0
  for i in range(0, n):
    s += i
  return s
""",
      "S0706",
    )

  def test_s1002_allows_range_with_step(self):
    self._translate(
      """def stride(n: int) -> int:
  s: int = 0
  for i in range(0, n, 2):
    s += i
  return s
"""
    )

  def test_s1002_allows_range_single_arg(self):
    self._translate(
      """def count(n: int) -> int:
  t: int = 0
  for i in range(n):
    t += 1
  return t
"""
    )

  def test_s1002_rejects_range_zero_start_step_one(self):
    self._expect_strict_fail(
      """def every(n: int) -> int:
  s: int = 0
  for i in range(0, n, 1):
    s += i
  return s
""",
      "S0706",
    )

  def test_s1002_rejects_range_nonzero_start_step_one(self):
    msg = self._strict_fail_message(
      """def slice_sum(a: int, b: int) -> int:
  s: int = 0
  for i in range(a, b, 1):
    s += i
  return s
""",
      "S0706",
    )
    self.assertIn("range(a, b, 1)", msg)
    self.assertIn("range(a, b)", msg)

  def test_s1002_allows_range_two_arg_nonzero_start(self):
    self._translate(
      """def slice_sum(a: int, b: int) -> int:
  s: int = 0
  for i in range(a, b):
    s += i
  return s
"""
    )

  def test_s0103_rejects_self_static_forward(self):
    self._expect_strict_fail(
      """from py2cpp import *

class Point:
  @staticmethod
  def _sqr_length(v: Self) -> int:
    return v.x * v.x + v.y * v.y

  def sqr_length(self) -> int:
    return Self._sqr_length(self)
""",
      "S0103",
    )

  def test_s0103_allows_self_static_with_extra_logic(self):
    self._translate(
      """from py2cpp import *

class Point:
  x: int = 0
  y: int = 0

  @staticmethod
  def _sqr_length(v: Self) -> int:
    return v.x * v.x + v.y * v.y

  def total_sq(self) -> int:
    sq: int = Self._sqr_length(self)
    return sq + 1
"""
    )

  def test_s0103_rejects_method_param_shuffle(self):
    self._expect_strict_fail(
      """class Box:
  def run(self, a: int, b: int, c: int) -> int:
    return self.compute(c, a, b)

  def compute(self, x: int, y: int, z: int) -> int:
    return x + y + z
""",
      "S0103",
    )

  def test_s0103_rejects_module_global_shuffle(self):
    self._expect_strict_fail(
      """def pick(a: int, b: int) -> int:
  return choose(b, a)

def choose(x: int, y: int) -> int:
  return x - y
""",
      "S0103",
    )

  def test_s0103_allows_method_with_extra_logic(self):
    self._translate(
      """class Box:
  def run(self, a: int, b: int) -> int:
    return self.compute(a + b, b)

  def compute(self, x: int, y: int) -> int:
    return x + y
"""
    )

  def test_s0103_rejects_expr_forward_without_return(self):
    self._expect_strict_fail(
      """class Log:
  def emit(self, msg: str) -> None:
    self.write(msg)

  def write(self, text: str) -> None:
    pass
""",
      "S0103",
    )

  def test_s0801_rejects_three_consecutive_if_same_subject(self):
    self._expect_strict_fail(
      """def pick(x: int) -> int:
  if x == 1:
    return 10
  if x == 2:
    return 20
  if x == 3:
    return 30
  return 0
""",
      "S0801",
    )

  def test_s0801_rejects_if_elif_chain_same_subject(self):
    self._expect_strict_fail(
      """def pick(x: int) -> int:
  if x == 1:
    return 10
  elif x == 2:
    return 20
  elif x in {3, 4}:
    return 30
  return 0
""",
      "S0801",
    )

  def test_s0801_allows_two_branches(self):
    self._translate(
      """def pick(x: int) -> int:
  if x == 1:
    return 10
  elif x == 2:
    return 20
  return 0
"""
    )

  def test_s0801_allows_three_branches_different_subjects(self):
    self._translate(
      """def pick(x: int, y: int) -> int:
  if x == 1:
    return 10
  if y == 2:
    return 20
  if x == 3:
    return 30
  return 0
"""
    )

  def test_s0801_allows_and_suffix_on_compare(self):
    self._translate(
      """def pick(x: int, ok: bool) -> int:
  if x == 1 and ok:
    return 10
  if x == 2 and ok:
    return 20
  return 0
"""
    )

  def test_s0801_rejects_three_with_and_suffix(self):
    self._expect_strict_fail(
      """def pick(x: int, ok: bool) -> int:
  if x == 1 and ok:
    return 10
  if x == 2 and ok:
    return 20
  if x == 3 and ok:
    return 30
  return 0
""",
      "S0801",
    )

  def test_s0801_allows_three_if_rhs_is_variable(self):
    self._translate(
      """def pick(x: int, a: int, b: int, c: int) -> int:
  if x == a:
    return 10
  if x == b:
    return 20
  if x == c:
    return 30
  return 0
"""
    )

  def test_s0801_rejects_three_if_rhs_ord_single_char(self):
    self._expect_strict_fail(
      """def pick(c: int) -> int:
  if c == ord("a"):
    return 1
  if c == ord("b"):
    return 2
  if c == ord("c"):
    return 3
  return 0
""",
      "S0801",
    )

  def test_s0801_allows_non_literal_rhs_chain(self):
    self._translate(
      """def pick(c: int, a: int, b: int, d: int) -> int:
  if c == a:
    return 1
  if c == b:
    return 2
  if c == d:
    return 3
  return 0
"""
    )

  def test_s0802_rejects_eq_or_chain_int_literals(self):
    self._expect_strict_fail(
      """def pick(x: int) -> bool:
  return x == 1 or x == 2 or x == 3
""",
      "S0802",
    )

  def test_s0802_rejects_eq_or_chain_char_string_hint(self):
    self._expect_strict_fail(
      """def pick(c: char) -> bool:
  return c == ord("a") or c == ord("b")
""",
      "S0802",
    )
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        "from py2cpp import *\n\n"
        "def pick(c: char) -> bool:\n"
        '  return c == ord("a") or c == ord("b")\n',
        encoding="utf-8",
      )
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
          include_stdlib=True,
          strict=True,
        )
      self.assertIn('in "ab"', str(ctx.exception))

  def test_s0802_allows_different_subjects(self):
    self._translate(
      """def pick(x: int, y: int) -> bool:
  return x == 1 or y == 2
"""
    )

  def test_s0802_allows_single_eq(self):
    self._translate(
      """def pick(x: int) -> bool:
  return x == 1
"""
    )

  def test_s0802_rejects_ne_and_chain(self):
    self._expect_strict_fail(
      """def ok(x: int) -> bool:
  return x != 1 and x != 2 and x != 3
""",
      "S0802",
    )

  def test_s0802_rejects_ne_and_chain_char_string_hint(self):
    with tempfile.TemporaryDirectory() as tmp:
      out = Path(tmp)
      py = out / "mod.py"
      py.write_text(
        "from py2cpp import *\n\n"
        "def ok(c: char) -> bool:\n"
        '  return c != ord("a") and c != ord("b")\n',
        encoding="utf-8",
      )
      with self.assertRaises(TranslationError) as ctx:
        Translator.translate_file(
          str(py),
          output_dir=str(out / "generated"),
          include_stdlib=True,
          strict=True,
        )
      self.assertIn('not in "ab"', str(ctx.exception))

  def test_s0802_allows_ne_and_different_subjects(self):
    self._translate(
      """def ok(x: int, y: int) -> bool:
  return x != 1 and y != 2
"""
    )

  def test_s0901_rejects_char_eq_single_char_literal(self):
    self._expect_strict_fail(
      """def ok(ch: char) -> bool:
  return ch == 'a'
""",
      "S0901",
    )

  def test_s0901_rejects_char_ne_single_char_literal(self):
    self._expect_strict_fail(
      """def ok(ch: char) -> bool:
  return ch != 'a'
""",
      "S0901",
    )

  def test_s0901_allows_ord_single_char(self):
    self._translate(
      """def ok(ch: char) -> bool:
  return ch == ord('a')
"""
    )

  def test_s0901_allows_compare_in_match_case_body(self):
    self._translate(
      """def ok(ch: char) -> bool:
  match ch:
    case 'a':
      return ch == 'a'
    case _:
      return False
  return False
"""
    )

  def test_s0901_rejects_compare_in_match_guard(self):
    self._expect_strict_fail(
      """def ok(ch: char) -> bool:
  match ch:
    case 'a' if ch == 'b':
      return True
    case _:
      return False
  return False
""",
      "S0901",
    )

  def test_s0901_allows_ord_in_match_guard(self):
    self._translate(
      """def ok(ch: char) -> bool:
  match ch:
    case 'a' if ch == ord('b'):
      return True
    case _:
      return False
  return False
"""
    )

  def test_s0901_allows_char_in_string_literal(self):
    self._translate(
      """def ok(ch: char) -> bool:
  return ch in "ab"
"""
    )

  def test_s0902_rejects_ord_on_variable(self):
    self._expect_strict_fail(
      """def bad(c: char) -> char:
  return ord(c)
""",
      "S0902",
    )

  def test_s0902_rejects_ord_on_str_index(self):
    self._expect_strict_fail(
      """def bad(s: str) -> char:
  return ord(s[0])
""",
      "S0902",
    )

  def test_s0902_allows_ord_single_char_literal(self):
    self._translate(
      """def ok() -> char:
  return ord('a')
"""
    )

  def test_s0903_rejects_primitive_convert_temp(self):
    self._expect_strict_fail(
      """def bad(x: int) -> int:
  n: int = int(x)
  return n
""",
      "S0903",
    )

  def test_s0903_allows_unannotated_convert_temp(self):
    self._translate(
      """def ok(x: int) -> int:
  n = int(x)
  return n
"""
    )

  def test_s0903_allows_reassigned_convert_temp(self):
    self._translate(
      """def ok(x: int, i: int) -> int:
  j: int = int(x)
  j = min(j, i)
  return j
"""
    )

  def test_s0903_allows_non_pure_ctor_rhs(self):
    self._translate(
      """def ok(ch: str) -> int:
  d: int = int(ch) - ord('0')
  return d
"""
    )

  def test_s0310_rejects_new_type_context_temp_call_arg(self):
    self._expect_strict_fail(
      """@union
class CmdUnion:
  @variant
  class Go:
    n: int

def take(c: CmdUnion) -> int:
  return 0

def bad() -> int:
  c: Cmd = new.Go(1)
  return take(c)
""",
      "S0310",
    )

  def test_s0310_allows_union_variant_in_call_arg(self):
    self._translate(
      """@union
class CmdUnion:
  @variant
  class Go:
    n: int

def take(c: CmdUnion) -> int:
  return 0

def ok() -> int:
  return take(CmdUnion.Go(1))
"""
    )

  def test_s0310_rejects_new_type_context_temp_assign(self):
    self._expect_strict_fail(
      """@copyable
class Point:
  x: int = 0

@copyable
class Box:
  item: Point = new()

  def __init__(self):
    sp: Point = new()
    self.item = sp
""",
      "S0310",
    )

  def test_s0310_rejects_new_type_context_temp_return(self):
    self._expect_strict_fail(
      """@copyable
class Point:
  x: int = 0

def bad() -> Point:
  p: Point = new()
  return p
""",
      "S0310",
    )

  def test_s0310_allows_new_temp_with_mutation(self):
    self._translate(
      """@copyable
class Point:
  x: int = 0

def ok() -> Point:
  p: Point = new()
  p.x = 1
  return p
"""
    )

  def test_s0310_allows_direct_field_new(self):
    self._translate(
      """@copyable
class Point:
  x: int = 0

@copyable
class Box:
  item: Point

  def __init__(self):
    self.item = new()
"""
    )

  def test_s0310_allows_explicit_cls_in_call_arg(self):
    self._translate(
      """@copyable
class Point:
  x: int = 0

def take(p: Point) -> int:
  return p.x

def ok() -> int:
  return take(Point())
"""
    )

  def test_s0310_allows_new_temp_before_cleanup_return(self):
    self._translate(
      """@copyable
class Resp:
  n: int = 0

  @staticmethod
  def read() -> Self:
    return new()

def close() -> None:
  pass

def ok() -> Resp:
  resp: Resp = new.read()
  close()
  return resp
"""
    )

  def test_s0901_ignores_str_compare(self):
    self._translate(
      """def ok(s: str) -> bool:
  return s == 'a'
"""
    )

  def test_s0803_rejects_match_without_default(self):
    self._expect_strict_fail(
      """def pick(x: int) -> int:
  match x:
    case 0:
      return 1
    case 1:
      return 2
  return 0
""",
      "S0803",
    )

  def test_s0803_allows_match_ending_with_wildcard(self):
    self._translate(
      """def pick(x: int) -> int:
  match x:
    case 0:
      return 1
    case _:
      return 0
  return 0
"""
    )

  def test_s0803_allows_exhaustive_union_without_wildcard(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class A:
    x: int

  @variant
  class B:
    pass

def f(u: UUnion) -> int:
  match u:
    case new.A(x):
      return x
    case new.B:
      return 0
  return 0
"""
    )

  def test_s0803_rejects_wildcard_guard_as_last_case(self):
    self._expect_strict_fail(
      """def pick(x: int) -> int:
  match x:
    case 0:
      return 1
    case _ if x > 0:
      return 2
  return 0
""",
      "S0803",
    )

  def test_s0803_allows_exhaustive_enum_without_wildcard(self):
    self._translate(
      """@enum
class ColorEnum:
  RED = 0
  GREEN = 1
  BLUE = 2

def f(c: ColorEnum) -> int:
  match c:
    case ColorEnum.RED:
      return 0
    case ColorEnum.GREEN:
      return 1
    case ColorEnum.BLUE:
      return 2
  return 0
"""
    )

  def test_s0803_allows_enum_or_pattern_without_wildcard(self):
    self._translate(
      """@enum
class ColorEnum:
  RED = 0
  GREEN = 1

def f(c: ColorEnum) -> int:
  match c:
    case ColorEnum.RED | ColorEnum.GREEN:
      return 0
  return 0
"""
    )

  def test_s0803_rejects_partial_enum_without_wildcard(self):
    self._expect_strict_fail(
      """@enum
class ColorEnum:
  RED = 0
  GREEN = 1

def f(c: ColorEnum) -> int:
  match c:
    case ColorEnum.RED:
      return 0
  return 0
""",
      "S0803",
    )

  def test_s0805_rejects_optional_some_match_pattern(self):
    self._expect_strict_fail(
      """from py2cpp.core.optional import Optional

def f(opt: Optional[int]) -> int:
  match opt:
    case Optional.Some(v):
      return v
    case None:
      return -1
""",
      "S0805",
    )

  def test_s0805_rejects_optional_none_union_match_pattern(self):
    self._expect_strict_fail(
      """from py2cpp.core.optional import Optional

def f(opt: Optional[int]) -> int:
  match opt:
    case Optional.None_:
      return -1
    case v:
      return v
""",
      "S0805",
    )

  def test_s0805_allows_optional_sugar_match(self):
    self._translate(
      """from py2cpp.core.optional import Optional

def f(opt: Optional[int]) -> int:
  match opt:
    case None:
      return -1
    case v:
      return v
"""
    )

  def test_s0805_rejects_optional_eq_none(self):
    self._expect_strict_fail(
      """from py2cpp.core.optional import Optional

def f(opt: Optional[int]) -> int:
  if opt == None:
    return -1
  return opt.value
""",
      "S0805",
    )

  def test_s0805_allows_optional_is_none(self):
    self._translate(
      """from py2cpp.core.optional import Optional

def f(opt: Optional[int]) -> int:
  if opt is None:
    return -1
  if opt is not None:
    return opt.value
  return 0
"""
    )

  def test_s0805_rejects_optional_some_ctor(self):
    self._expect_strict_fail(
      """from py2cpp.core.optional import Optional

def f(v: int) -> Optional[int]:
  return Optional[int].Some(v)
""",
      "S0805",
    )

  def test_s0805_rejects_optional_none_ctor(self):
    self._expect_strict_fail(
      """from py2cpp.core.optional import Optional

def f() -> Optional[int]:
  return Optional[int].None_()
""",
      "S0805",
    )

  def test_s0805_allows_optional_assign_sugar(self):
    self._translate(
      """from py2cpp.core.optional import Optional

def f(v: int) -> Optional[int]:
  out: Optional[int] = v
  empty: Optional[int] = None
  return out if v else empty
"""
    )

  def test_s0401_rejects_dataclass_container_default_without_optional(self):
    self._expect_strict_fail(
      """@dataclass
class Box:
  items: list[int] = []
""",
      "S0401",
    )

  def test_s0401_allows_dataclass_container_default_with_optional(self):
    self._translate(
      """@dataclass
class Box:
  items: list[int] @optional = []
  name: str
"""
    )

  def test_s0402_rejects_empty_dataclass(self):
    self._expect_strict_fail(
      """@dataclass
class Empty:
  pass
""",
      "S0402",
    )

  def test_s0402_rejects_all_optional_dataclass(self):
    self._expect_strict_fail(
      """@dataclass
class AllOpt:
  items: list[int] @optional = []
  tags: list[str] @optional = []
""",
      "S0402",
    )

  def test_s0402_allows_required_with_optional_fields(self):
    self._translate(
      """@dataclass
class Box:
  name: str
  items: list[int] @optional = []
"""
    )

  def test_s0403_rejects_final_optional_same_field(self):
    self._expect_strict_fail(
      """class Box:
  v: int @final @optional = 0
""",
      "S0403",
    )

  def test_s0403_rejects_frozen_dataclass_optional(self):
    self._expect_strict_fail(
      """@dataclass(frozen=True)
class FrozenBox:
  key: int
  extra: int @optional = 99
""",
      "S0403",
    )

  def test_s0403_allows_frozen_dataclass_without_optional(self):
    self._translate(
      """@dataclass(frozen=True)
class FrozenPoint:
  x: int
  y: int = 0
"""
    )

  def test_s0803_rejects_enum_member_case_with_guard_for_exhaustive(self):
    self._expect_strict_fail(
      """@enum
class ColorEnum:
  RED = 0
  GREEN = 1

def f(c: ColorEnum) -> int:
  match c:
    case ColorEnum.RED if True:
      return 0
    case ColorEnum.GREEN:
      return 1
  return 0
""",
      "S0803",
    )

  def test_s0803_allows_union_with_guard_if_still_exhaustive(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class A:
    x: int

  @variant
  class B:
    pass

def f(u: UUnion) -> int:
  match u:
    case new.A(x) if x > 0:
      return x
    case new.A(x):
      return 0
    case new.B:
      return -1
  return 0
"""
    )

  def test_s0803_allows_union_partial_field_bind_exhaustive(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class Pair:
    a: int
    b: int

def f(u: UUnion) -> int:
  match u:
    case new.Pair(a):
      return a
  return 0
"""
    )

  def test_s0803_rejects_union_missing_variant_without_wildcard(self):
    self._expect_strict_fail(
      """@union
class UUnion:
  @variant
  class A:
    x: int

  @variant
  class B:
    pass

def f(u: UUnion) -> int:
  match u:
    case new.A(x):
      return x
  return 0
""",
      "S0803",
    )

  def test_s0803_allows_union_empty_parens_full_bind(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class Pair:
    a: int
    b: int

def f(u: UUnion) -> int:
  match u:
    case new.Pair():
      return 0
  return 0
"""
    )

  def test_s0803_allows_union_kwd_full_bind(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class Pair:
    a: int
    b: int

def f(u: UUnion) -> int:
  match u:
    case new.Pair(a=a, b=b):
      return a + b
  return 0
"""
    )

  def test_s0803_rejects_union_literal_positional_for_exhaustive(self):
    self._expect_strict_fail(
      """@union
class UUnion:
  @variant
  class Pair:
    a: int
    b: int

def f(u: UUnion) -> int:
  match u:
    case new.Pair(a, 1):
      return a
  return 0
""",
      "S0803",
    )

  def test_s0803_rejects_union_literal_kwd_for_exhaustive(self):
    self._expect_strict_fail(
      """@union
class UUnion:
  @variant
  class Pair:
    a: int
    b: int

def f(u: UUnion) -> int:
  match u:
    case new.Pair(a=1, b=b):
      return b
  return 0
""",
      "S0803",
    )

  def test_s0804_rejects_wide_union_case_before_literal(self):
    self._expect_strict_fail(
      """@union
class UUnion:
  @variant
  class Move:
    x: int
    y: int

def f(u: UUnion) -> int:
  match u:
    case new.Move(x, _):
      return x
    case new.Move(0, y):
      return y
  return 0
""",
      "S0804",
    )

  def test_s0804_allows_literal_before_wide_union_case(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class Move:
    x: int
    y: int

def f(u: UUnion) -> int:
  match u:
    case new.Move(0, y):
      return y
    case new.Move(x, _):
      return x
  return 0
"""
    )

  def test_s0804_ignores_shadow_when_earlier_has_guard(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class Move:
    x: int
    y: int

def f(u: UUnion) -> int:
  match u:
    case new.Move(x, _) if x != 0:
      return x
    case new.Move(0, y):
      return y
    case new.Move(x, y):
      return 0
  return 0
"""
    )

  def test_s0804_rejects_catchall_before_literal_same_variant(self):
    self._expect_strict_fail(
      """@union
class UUnion:
  @variant
  class Move:
    x: int
    y: int

def f(u: UUnion) -> int:
  match u:
    case new.Move(x, y):
      return x + y
    case new.Move(0, y):
      return y
  return 0
""",
      "S0804",
    )

  def test_s0804_rejects_interleaved_variant_cases(self):
    self._expect_strict_fail(
      """@union
class UUnion:
  @variant
  class Move:
    x: int

  @variant
  class Write:
    s: str

def f(u: UUnion) -> int:
  match u:
    case new.Move(x):
      return x
    case new.Write(s):
      return len(s)
    case new.Move(y):
      return y
  return 0
""",
      "S0804",
    )

  def test_s0804_allows_contiguous_same_variant_cases(self):
    self._translate(
      """@union
class UUnion:
  @variant
  class Move:
    x: int

  @variant
  class Write:
    s: str

def f(u: UUnion) -> int:
  match u:
    case new.Move(1):
      return 1
    case new.Move(2):
      return 2
    case new.Move(x):
      return x
    case new.Write(s):
      return len(s)
  return 0
"""
    )


  def test_s1005_rejects_reverse_self_dunder(self):
    self._expect_strict_fail(
      """class Num:
  def __add__(self, other: Self) -> Self:
    return other

  def __radd__(self, other: Self) -> Self:
    return self + other

def main():
  a: Num = new()
  b: Num = new()
  return a + b
""",
      "S1005",
    )

  def test_s1005_rejects_reverse_rmatmul_self(self):
    self._expect_strict_fail(
      """class Mat:
  def __matmul__(self, other: Self) -> Self:
    return other

  def __rmatmul__(self, other: Self) -> Self:
    return other @ self

def main():
  a: Mat = new()
  b: Mat = new()
  return a @ b
""",
      "S1005",
    )

  def test_s1005_allows_reverse_scalar_dunder(self):
    self._translate(
      """class Row:
  def __rmul__(self, n: int) -> Self:
    return self

def main() -> Row:
  return new()
"""
    )

  def test_s0106_rejects_translator_only_method(self):
    self._expect_strict_fail(
      """class Box:
  def build(self) -> None:
    pass

def main():
  b: Box = new()
""",
      "S0106",
    )

  def test_s0106_rejects_translator_only_field(self):
    self._expect_strict_fail(
      """class Box:
  select: int = 0

def main():
  b: Box = new()
""",
      "S0106",
    )

  def test_s0106_allows_copy_from(self):
    self._translate(
      """class Box:
  def copy_from(self, other: Self) -> None:
    pass

def main():
  b: Box = new()
"""
    )

  def test_s0201_allows_unittest_submodule_import(self):
    self._translate(
      """from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner

class T(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    pass

def main():
  return TextTestRunner().run(TestSuite())
"""
    )

  def test_s0201_rejects_unittest_submodule_override(self):
    self._expect_strict_fail(
      """from py2cpp import *
from py2cpp.test.unittest import override

class T(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    pass

def main():
  return 0
""",
      "S0201",
    )

  def test_s0201_rejects_named_py2cpp_import(self):
    self._expect_strict_fail(
      """from py2cpp import override

class Base:
  @override
  def foo(self) -> int:
    return 0

def main():
  return 0
""",
      "S0201",
    )

  def test_s0201_allows_io_submodule_import(self):
    self._translate(
      """from py2cpp import *
from py2cpp.io import open, StringIO

def main():
  sio: StringIO = new()
  return len(sio.value)
"""
    )


  def test_s1102_rejects_pynone_annotation(self):
    self._expect_strict_fail(
      """def gen() -> GeneratorType[int, PyNone, PyNone]:
  yield 1

def main():
  return 0
""",
      "S1102",
    )

  def test_s1102_allows_none_annotation(self):
    self._translate(
      """def gen() -> GeneratorType[int, None, None]:
  yield 1

def main():
  return 0
"""
    )

  def test_s1201_rejects_for_yield_delegation(self):
    self._expect_strict_fail(
      """def gen(xs: list[int]) -> GeneratorType[int, None, None]:
  for x in xs:
    yield x

def main():
  return 0
""",
      "S1201",
    )

  def test_s1201_allows_yield_from(self):
    self._translate(
      """def gen(xs: list[int]) -> GeneratorType[int, None, None]:
  yield from xs

def main():
  return 0
"""
    )

  def test_s1201_allows_for_else_yield(self):
    self._translate(
      """def gen() -> GeneratorType[int, None, None]:
  for i in range(3):
    yield i
  else:
    yield 100

def main():
  return 0
"""
    )

  def test_s1201_exempts_async_generator(self):
    self._translate(
      """async def gen(xs: list[int]):
  for x in xs:
    yield x

def main():
  return 0
"""
    )

  def test_s0104_rejects_enum_without_enum_suffix(self):
    self._expect_strict_fail(
      """@enum
class Mode:
  Off = 0
  On = 1

def main():
  return int(Mode.On)
""",
      "S0104",
    )

  def test_s0104_rejects_flag_without_flag_suffix(self):
    self._expect_strict_fail(
      """@enum(flag=True)
class Perm:
  Read = 1
  Write = 2

def main():
  return int(Perm.Read)
""",
      "S0104",
    )

  def test_s0104_rejects_protocol_without_type_suffix(self):
    self._expect_strict_fail(
      """@protocol
class Sized:
  def __len__(self) -> int: ...

def main():
  return 0
""",
      "S0104",
    )

  def test_s0104_rejects_boxing_without_unsafe_suffix(self):
    self._expect_strict_fail(
      """@boxing
class Cell:
  def __init__(self, n: int = 0):
    self.n: int = n

def main():
  return 0
""",
      "S0104",
    )

  def test_s0104_allows_cpython_exception_names(self):
    self._translate(
      """class StopIteration(Exception):
  pass

class ExceptionGroup(Exception):
  pass

def main():
  return 0
"""
    )

  def test_s0104_rejects_union_without_union_suffix(self):
    self._expect_strict_fail(
      """@union
class Message:
  @variant
  class Quit:
    pass

def main():
  return 0
""",
      "S0104",
    )

  def test_s0104_allows_result_optional_iter_result(self):
    self._translate(
      """def take(r: Result[int, str], o: Optional[int], ir: IterResult[int, None]) -> int:
  return 0

def main():
  return 0
"""
    )

  def test_s0104_rejects_exception_without_error_suffix(self):
    self._expect_strict_fail(
      """class Boom(Exception):
  pass

def main():
  raise Boom()
""",
      "S0104",
    )

  def test_s0104_allows_enum_and_protocol_suffixes(self):
    self._translate(
      """@enum
class ModeEnum:
  Off = 0
  On = 1

def main():
  return int(ModeEnum.On)
"""
    )

  def test_s0104_rejects_delegate_without_delegate_suffix(self):
    self._expect_strict_fail(
      """@delegate
def UIEvent() -> None: ...

def main():
  return 0
""",
      "S0104",
    )

  def test_s0104_allows_delegate_suffix(self):
    self._translate(
      """@delegate
def UIEventDelegate() -> None: ...

def main():
  d: UIEventDelegate = new()
  return 0
"""
    )

  def test_s0105_rejects_single_letter_class_type_param(self):
    self._expect_strict_fail(
      """class Box[T]:
  value: T = new()

def main():
  return 0
""",
      "S0105",
    )

  def test_s0105_rejects_letter_digit_class_type_param(self):
    self._expect_strict_fail(
      """class Box[T1]:
  value: T1 = new()

def main():
  return 0
""",
      "S0105",
    )

  def test_s0105_allows_semantic_class_type_param(self):
    self._translate(
      """class Box[Element]:
  value: Element

  def __init__(self, value: Element):
    self.value = value

def main():
  b: Box[int] = new(1)
  return b.value
"""
    )

  def test_s0105_allows_short_function_type_param(self):
    self._translate(
      """def identity[T](x: T) -> T:
  return x

def main():
  return identity(1)
"""
    )

  def test_s0405_rejects_class_default_and_init_assign(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

  def __init__(self, n: int):
    self.n = n

def main():
  b: Box = new(1)
  return b.n
""",
      "S0405",
    )

  def test_s0405_rejects_augassign_in_init(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

  def __init__(self):
    self.n += 1

def main():
  b: Box = new()
  return b.n
""",
      "S0405",
    )

  def test_s0405_rejects_conditional_assign_in_init(self):
    self._expect_strict_fail(
      """class Box:
  n: int = 0

  def __init__(self, n: int):
    if n:
      self.n = n

def main():
  b: Box = new(1)
  return b.n
""",
      "S0405",
    )

  def test_s0405_rejects_subclass_assign_of_base_default(self):
    self._expect_strict_fail(
      """class Base:
  n: int = 0

class Derived(Base):
  def __init__(self, n: int):
    self.n = n

def main():
  d: Derived = new(1)
  return d.n
""",
      "S0405",
    )

  def test_s0405_allows_class_default_without_init_assign(self):
    self._translate(
      """class Box:
  n: int = 0

  def __init__(self):
    pass

def main():
  b: Box = new()
  return b.n
"""
    )

  def test_s0405_allows_init_assign_without_class_default(self):
    self._translate(
      """class Box:
  n: int

  def __init__(self, n: int):
    self.n = n

def main():
  b: Box = new(1)
  return b.n
"""
    )

  def test_s0405_allows_init_ann_assign_without_class_default(self):
    self._translate(
      """class Box:
  def __init__(self, n: int):
    self.n: int = n

def main():
  b: Box = new(1)
  return b.n
"""
    )

  def test_s0405_allows_copy_assign_with_class_default(self):
    self._translate(
      """class Box:
  n: int = 0

  def __copy__(self, other: Self):
    self.n = other.n

  @immutable
  def copy(self) -> Self:
    out: Self = new()
    out.__copy__(self)
    return out

def main():
  a: Box = new()
  return a.copy().n
"""
    )

  def test_s0405_allows_dataclass_field_default(self):
    self._translate(
      """@dataclass
class Point:
  x: int = 0
  y: int = 0

def main():
  p: Point = new(1, 2)
  return p.x + p.y
"""
    )


if __name__ == "__main__":
  unittest.main()
