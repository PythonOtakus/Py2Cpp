from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@refcount
class RefAsyncState:
  _value: int = 0
  _buf: byte[:] = b""

  def set_value(self, value: int) -> None:
    self._value = value

  async def value_after_tick(self) -> int:
    await Task.sleep(0)
    return self._value

  async def bytes_after_tick(self) -> bytes:
    await Task.sleep(0)
    local: byte[:] = new(4)
    for i in range(4):
      local[i] = byte(65 + i)
    self._buf = local
    return bytes(self._buf)


async def refcount_async_roundtrip() -> int:
  st: RefAsyncState = new()
  st.set_value(41)
  got: int = await st.value_after_tick()
  return got + 1


async def refcount_async_bytes_roundtrip() -> str:
  st: RefAsyncState = new()
  got: bytes = await st.bytes_after_tick()
  return got.decode()


class RefcountAsyncMethodTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(refcount_async_roundtrip()), 42)


class RefcountAsyncBytesTests(TestCaseMixin):
  _test_tag = 2

  @override
  def test(self):
    self.assertEqual(Task.run(refcount_async_bytes_roundtrip()), "ABCD")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
