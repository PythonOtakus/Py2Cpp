"""``py2cpp.web.openai`` 最简 chat/chat_stream 辅助逻辑回归。"""
from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.http import ClientStreamResponse, Request, Response, StatusCode
from py2cpp.web.openai import AsyncOpenAI, _build_chat_body, _chat_content, _delta_content, _iter_sse_tokens
from py2cpp.web.socket import AsyncTcpSocket
from py2cpp.web.stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


_CHAT_PORT: int = 18141


class OpenAIChatBodyTests(TestCaseMixin):
  _test_tag = 10

  @override
  def test(self):
    body: str = _build_chat_body("gpt-test", "ping", "be brief", 16, 0.5, False)
    self.assertTrue('"model":"gpt-test"' in body)
    self.assertTrue('"role":"system"' in body)
    self.assertTrue('"role":"user"' in body)
    self.assertTrue('"max_tokens":16' in body)
    self.assertTrue('"temperature":0.5' in body)
    self.assertFalse('"stream":true' in body)

    stream_body: str = _build_chat_body("gpt-test", "ping", "", 0, -1.0, True)
    self.assertTrue('"stream":true' in stream_body)
    self.assertFalse('"role":"system"' in stream_body)


class OpenAIChatParseTests(TestCaseMixin):
  _test_tag = 20

  @override
  def test(self):
    text: str = _chat_content('{"choices":[{"message":{"content":"pong"}}]}')
    self.assertEqual(text, "pong")
    top: str = _chat_content('{"content":"pong-top"}')
    self.assertEqual(top, "pong-top")
    nested: str = _chat_content('{"id":"x","choices":[{"index":0,"message":{"role":"assistant","content":"nested"}}]}')
    self.assertEqual(nested, "nested")


class OpenAIStreamParseTests(TestCaseMixin):
  _test_tag = 30

  @override
  def test(self):
    streamed: str = ""
    for token in _iter_sse_tokens(
      'data: {"choices":[{"delta":{"content":"pong"}}]}\n\n'
      'data: {"choices":[{"delta":{"content":"-stream"}}]}\n\n'
      'data: [DONE]\n\n'
    ):
      streamed += token
    self.assertEqual(streamed, "pong-stream")


class OpenAIDeltaParseTests(TestCaseMixin):
  _test_tag = 35

  @override
  def test(self):
    token: str = _delta_content('{"id":"x","choices":[{"index":0,"delta":{"content":"tok"}}]}')
    self.assertEqual(token, "tok")


class ClientStreamChunkedLineTests(TestCaseMixin):
  _test_tag = 40

  @override
  def test(self):
    raw: bytes = (
      b"HTTP/1.1 200 OK\r\n"
      b"Transfer-Encoding: chunked\r\n"
      b"\r\n"
      b"b\r\n"
      b"data: one\n\n"
      b"\r\n"
      b"b\r\n"
      b"data: two\n\n"
      b"\r\n"
      b"0\r\n"
      b"\r\n"
    )
    reader: StreamReader = new()
    reader.load_bytes(raw)
    writer: StreamWriter = new.from_buffer()
    resp: ClientStreamResponse = new.from_streams(reader, writer)
    self.assertEqual(resp.status, 200)
    self.assertEqual(resp.readline(), "data: one")
    self.assertEqual(resp.readline(), "")
    self.assertEqual(resp.readline(), "data: two")


async def _serve_openai_chat(listener: AsyncTcpSocket) -> None:
  conn: AsyncTcpSocket = await listener.accept()
  reader: AsyncStreamReader = new.from_socket(conn)
  writer: AsyncStreamWriter = new.from_socket(conn)
  req: Request = await new.read_async(reader)
  resp: Response = new.text_response('{"choices":[{"message":{"content":"pong-async"}}]}', StatusCode.OK)
  await resp.write_async(writer)
  reader.close()
  writer.close()
  listener.close()


async def _async_chat_roundtrip() -> str:
  listener: AsyncTcpSocket = new()
  listener.bind("127.0.0.1", _CHAT_PORT)
  listener.listen(16)
  server_task: Task[None] = Task.create(_serve_openai_chat(listener))
  await Task.sleep(0)
  client: AsyncOpenAI = new(base_url=f"http://127.0.0.1:{_CHAT_PORT}/v1")
  text: str = await client.chat("gpt-test", "ping")
  await server_task
  return text


class AsyncOpenAIChatTests(TestCaseMixin):
  _test_tag = 50

  @override
  def test(self):
    self.assertEqual(Task.run(_async_chat_roundtrip()), "pong-async")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
