from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.socket import AsyncTcpSocket


_PORT: int = 18132


async def async_socket_server(listener: AsyncTcpSocket) -> None:
  conn: AsyncTcpSocket = await listener.accept()
  buf: byte[:] = new(4)
  got: int = await conn.recv(buf, 4)
  await conn.send_all(b"pong")
  conn.close()
  listener.close()


async def async_socket_roundtrip() -> str:
  listener: AsyncTcpSocket = new()
  listener.bind("127.0.0.1", _PORT)
  listener.listen(16)
  server_task: Task[None] = Task.create(async_socket_server(listener))
  await Task.sleep(0)
  client: AsyncTcpSocket = new()
  await client.connect("127.0.0.1", _PORT)
  await client.send_all(b"ping")
  buf: byte[:] = new(4)
  got: int = await client.recv(buf, 4)
  await server_task
  client.close()
  if got != 4:
    return f"got-{got}"
  data: bytes = bytes(buf)
  return data.decode()


class AsyncSocketRoundtripTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(async_socket_roundtrip()), "pong")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
