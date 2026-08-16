from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.socket import AsyncTcpSocket


_Port: int = 18132


async def asyncSocketServer(listener: AsyncTcpSocket) -> None:
  conn: AsyncTcpSocket = await listener.accept()
  buf: byte[:] = new(4)
  got: int = await conn.recv(buf, 4)
  await conn.sendAll(b"pong")
  conn.close()
  listener.close()


async def asyncSocketRoundtrip() -> str:
  listener: AsyncTcpSocket = new()
  listener.bind("127.0.0.1", _Port)
  listener.listen(16)
  serverTask: Task[None] = Task.create(asyncSocketServer(listener))
  await Task.sleep(0)
  client: AsyncTcpSocket = new()
  await client.connect("127.0.0.1", _Port)
  await client.sendAll(b"ping")
  buf: byte[:] = new(4)
  got: int = await client.recv(buf, 4)
  await serverTask
  client.close()
  if got != 4:
    return f"got-{got}"
  data: bytes = bytes(buf)
  return data.decode()


class AsyncSocketRoundtripTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(asyncSocketRoundtrip()), "pong")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
