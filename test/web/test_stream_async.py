from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.socket import AsyncTcpSocket
from py2cpp.web.stream import AsyncStreamReader, AsyncStreamWriter


_Port: int = 18133


async def asyncStreamServer(listener: AsyncTcpSocket) -> None:
  conn: AsyncTcpSocket = await listener.accept()
  reader: AsyncStreamReader = new.fromSocket(conn)
  writer: AsyncStreamWriter = new.fromSocket(conn)
  data: bytes = await reader.readExactly(4)
  wrote: int = await writer.write(b"pong")
  await writer.drain()
  reader.close()
  writer.close()
  listener.close()


async def asyncStreamRoundtrip() -> str:
  listener: AsyncTcpSocket = new()
  listener.bind("127.0.0.1", _Port)
  listener.listen(16)
  serverTask: Task[None] = Task.create(asyncStreamServer(listener))
  await Task.sleep(0)
  client: AsyncTcpSocket = new()
  await client.connect("127.0.0.1", _Port)
  reader: AsyncStreamReader = new.fromSocket(client)
  writer: AsyncStreamWriter = new.fromSocket(client)
  wrote: int = await writer.write(b"ping")
  await writer.drain()
  resp: bytes = await reader.readExactly(4)
  await serverTask
  reader.close()
  writer.close()
  return resp.decode()


class AsyncStreamRoundtripTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(asyncStreamRoundtrip()), "pong")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
