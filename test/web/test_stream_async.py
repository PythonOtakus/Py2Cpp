from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.socket import AsyncTcpSocket
from py2cpp.web.stream import AsyncStreamReader, AsyncStreamWriter


_PORT: int = 18133


async def async_stream_server(listener: AsyncTcpSocket) -> None:
  conn: AsyncTcpSocket = await listener.accept()
  reader: AsyncStreamReader = new.from_socket(conn)
  writer: AsyncStreamWriter = new.from_socket(conn)
  data: bytes = await reader.readexactly(4)
  wrote: int = await writer.write(b"pong")
  await writer.drain()
  reader.close()
  writer.close()
  listener.close()


async def async_stream_roundtrip() -> str:
  listener: AsyncTcpSocket = new()
  listener.bind("127.0.0.1", _PORT)
  listener.listen(16)
  server_task: Task[None] = Task.create(async_stream_server(listener))
  await Task.sleep(0)
  client: AsyncTcpSocket = new()
  await client.connect("127.0.0.1", _PORT)
  reader: AsyncStreamReader = new.from_socket(client)
  writer: AsyncStreamWriter = new.from_socket(client)
  wrote: int = await writer.write(b"ping")
  await writer.drain()
  resp: bytes = await reader.readexactly(4)
  await server_task
  reader.close()
  writer.close()
  return resp.decode()


class AsyncStreamRoundtripTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(async_stream_roundtrip()), "pong")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
