from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner


@refcount
class RefAsyncState:
  _value: int = 0
  _buf: byte[:] = b""

  def setValue(self, value: int) -> None:
    self._value = value

  async def valueAfterTick(self) -> int:
    await Task.sleep(0)
    return self._value

  async def bytesAfterTick(self) -> bytes:
    await Task.sleep(0)
    local: byte[:] = new(4)
    for i in range(4):
      local[i] = byte(65 + i)
    self._buf = local
    return bytes(self._buf)


async def refcountAsyncRoundtrip() -> int:
  st: RefAsyncState = new()
  st.setValue(41)
  got: int = await st.valueAfterTick()
  return got + 1


async def refcountAsyncBytesRoundtrip() -> str:
  st: RefAsyncState = new()
  got: bytes = await st.bytesAfterTick()
  return got.decode()


class RefcountAsyncMethodTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(refcountAsyncRoundtrip()), 42)


class RefcountAsyncBytesTests(TestCaseMixin):
  _testTag = 2

  @override
  def test(self):
    self.assertEqual(Task.run(refcountAsyncBytesRoundtrip()), "ABCD")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
