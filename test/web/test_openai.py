"""``py2cpp.web.openai`` 最简 chat/chat_stream 辅助逻辑回归。"""
from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.http import ClientStreamResponse, Request, Response, StatusCode
from py2cpp.web.openai import (
  AsyncOpenAI,
  Conversation,
  McpBase,
  McpFuncCall,
  McpServer,
  OpenAI,
  OpenAIMessage,
  _build_chat_body,
  _build_responses_body,
  _chat_content,
  _delta_content,
  _iter_responses_sse_tokens,
  _iter_sse_tokens,
  _response_id,
  _response_text,
  _responses_delta,
)
from py2cpp.web.socket import AsyncTcpSocket
from py2cpp.web.stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


_CHAT_PORT: int = 18141


def _local_mcp_echo(args_json: str) -> str:
  return "echo:" + args_json


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


class OpenAIResponsesBodyTests(TestCaseMixin):
  _test_tag = 36

  @override
  def test(self):
    old_msg: OpenAIMessage = new("user", "old")
    answer_msg: OpenAIMessage = new("assistant", "answer")
    messages: list[OpenAIMessage] = [old_msg, answer_msg]
    mcp: McpServer = new()
    mcp.label = "docs"
    mcp.url = "https://example.com/mcp"
    fn: McpFuncCall = new()
    fn.label = "local"
    fn.name = "echo"
    fn.description = "Echo local args"
    fn.parameters_json = "{}"
    fn.handler = _local_mcp_echo
    mcps: list[McpBase] = [mcp, fn]
    body: str = _build_responses_body(
      "gpt-test",
      "system",
      "summary",
      messages,
      "next",
      "resp_1",
      mcps,
      32,
      0.25,
      True,
    )
    self.assertTrue('"model":"gpt-test"' in body)
    self.assertTrue('"previous_response_id":"resp_1"' in body)
    self.assertTrue('"max_output_tokens":32' in body)
    self.assertTrue('"stream":true' in body)
    self.assertTrue('"type":"mcp"' in body)
    self.assertTrue('"server_label":"docs"' in body)
    self.assertTrue('"require_approval":"never"' in body)
    self.assertTrue('"type":"function"' in body)
    self.assertTrue('"name":"echo"' in body)
    self.assertEqual(fn.call('{"x":1}'), 'echo:{"x":1}')
    self.assertTrue("Conversation summary" in body)


class OpenAIResponsesParseTests(TestCaseMixin):
  _test_tag = 37

  @override
  def test(self):
    raw: str = '{"id":"resp_1","output_text":"pong"}'
    self.assertEqual(_response_id(raw), "resp_1")
    self.assertEqual(_response_text(raw), "pong")
    nested: str = '{"output":[{"content":[{"type":"output_text","text":"he"},{"type":"output_text","text":"llo"}]}]}'
    self.assertEqual(_response_text(nested), "hello")
    self.assertEqual(_responses_delta('{"type":"response.output_text.delta","delta":"tok"}'), "tok")
    streamed: str = ""
    for token in _iter_responses_sse_tokens(
      'data: {"type":"response.output_text.delta","delta":"a"}\n\n'
      'data: {"type":"response.output_text.delta","delta":"b"}\n\n'
      'data: [DONE]\n\n'
    ):
      streamed += token
    self.assertEqual(streamed, "ab")


class OpenAIConversationLocalTests(TestCaseMixin):
  _test_tag = 38

  @override
  def test(self):
    client: OpenAI = new(base_url="http://127.0.0.1:1/v1")
    conv: Conversation = client.conversation("gpt-test", system="sys", max_history_chars=16, compress_target_chars=12)
    srv: McpServer = new()
    srv.label = "docs"
    srv.url = "https://example.com/mcp"
    conv.add_mcp(srv)
    fn: McpFuncCall = new()
    fn.label = "local"
    fn.name = "echo"
    fn.handler = _local_mcp_echo
    conv.add_mcp(fn)
    self.assertEqual(conv.model, "gpt-test")
    self.assertEqual(len(conv.mcps), 2)
    self.assertEqual(conv.call_mcp("local", '{"x":1}'), 'echo:{"x":1}')
    msg1: OpenAIMessage = new("user", "first")
    msg2: OpenAIMessage = new("assistant", "second")
    msg3: OpenAIMessage = new("user", "third")
    msg4: OpenAIMessage = new("assistant", "fourth")
    msg5: OpenAIMessage = new("user", "fifth")
    conv.messages.append(msg1)
    conv.messages.append(msg2)
    conv.messages.append(msg3)
    conv.messages.append(msg4)
    conv.messages.append(msg5)
    conv.compress()
    self.assertTrue(len(conv.summary) <= 12)
    self.assertEqual(len(conv.messages), 4)


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
