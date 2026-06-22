"""``PyGenerator[Y,S,R]`` 擦除：形参/字段/``@virtual`` 返回；``-> Generator`` 仍为具体 ``*_generator``。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


def gen_pair() -> Generator[int, None, None]:
  yield 1
  yield 2


def sum_gen(g: Generator[int, None, None]) -> int:
  s: int = 0
  for x in g:
    s += x
  return s


@copyable
class GenHolder:
  g: Generator[int, None, None]

  def store(self, src: Generator[int, None, None]) -> None:
    self.g = src

  def sum_stored(self) -> int:
    s: int = 0
    for x in self.g:
      s += x
    return s


class GenStreamBase:
  @virtual
  def stream(self) -> Generator[int, None, None]:
    yield 0


@copyable
class GenStreamA(GenStreamBase):
  @override
  def stream(self) -> Generator[int, None, None]:
    yield 10
    yield 20


def sum_override_stream(a: GenStreamA) -> int:
  s: int = 0
  for x in a.stream():
    s += x
  return s


class GenEraseParamTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(sum_gen(gen_pair()), 3)


class GenEraseFieldTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    h: GenHolder = new()
    h.store(gen_pair())
    self.assertEqual(h.sum_stored(), 3)


class GenEraseOverrideTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    a: GenStreamA = new()
    self.assertEqual(sum_override_stream(a), 30)


def main() -> int:
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
