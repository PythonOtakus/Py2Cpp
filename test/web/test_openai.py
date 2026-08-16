"""``py2cpp.web.openai`` 最简 chat/chatStream 辅助逻辑回归。"""
from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.http import ClientResponse, ClientStreamResponse, Request, RequestOptions, Response, StatusCodeEnum
from py2cpp.web.openai import (
  AsyncOpenAI,
  Conversation,
  McpBase,
  McpFuncCall,
  McpServer,
  OpenAI,
  OpenAIMessage,
  _buildChatBody,
  _buildResponsesBody,
  _chatContent,
  _deltaContent,
  _iterResponsesSseTokens,
  _iterSseTokens,
  _responseId,
  _responseText,
  _responsesDelta,
  _requestOptions,
  _statusErrorText,
)
from py2cpp.web.socket import AsyncTcpSocket
from py2cpp.web.stream import AsyncStreamReader, AsyncStreamWriter, StreamReader, StreamWriter


_ChatPort: int = 18141


def _localMcpEcho(argsJson: str) -> str:
  return "echo:" + argsJson


class OpenAIChatBodyTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    body: str = _buildChatBody("gpt-test", "ping", "be brief", 16, 0.5, False)
    self.assertTrue('"model":"gpt-test"' in body)
    self.assertTrue('"role":"system"' in body)
    self.assertTrue('"role":"user"' in body)
    self.assertTrue('"maxTokens":16' in body)
    self.assertTrue('"temperature":0.5' in body)
    self.assertFalse('"stream":true' in body)

    streamBody: str = _buildChatBody("gpt-test", "ping", "", 0, -1.0, True)
    self.assertTrue('"stream":true' in streamBody)
    self.assertFalse('"role":"system"' in streamBody)


class OpenAIChatParseTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    text: str = _chatContent('{"choices":[{"message":{"content":"pong"}}]}')
    self.assertEqual(text, "pong")
    top: str = _chatContent('{"content":"pong-top"}')
    self.assertEqual(top, "pong-top")
    nested: str = _chatContent('{"id":"x","choices":[{"index":0,"message":{"role":"assistant","content":"nested"}}]}')
    self.assertEqual(nested, "nested")


class OpenAIStreamParseTests(TestCaseMixin):
  _testTag = 30

  @override
  def test(self):
    streamed: str = ""
    for token in _iterSseTokens(
      'data: {"choices":[{"delta":{"content":"pong"}}]}\n\n'
      'data: {"choices":[{"delta":{"content":"-stream"}}]}\n\n'
      'data: [DONE]\n\n'
    ):
      streamed += token
    self.assertEqual(streamed, "pong-stream")


class OpenAIDeltaParseTests(TestCaseMixin):
  _testTag = 35

  @override
  def test(self):
    token: str = _deltaContent('{"id":"x","choices":[{"index":0,"delta":{"content":"tok"}}]}')
    self.assertEqual(token, "tok")


class OpenAIResponsesBodyTests(TestCaseMixin):
  _testTag = 36

  @override
  def test(self):
    oldMsg: OpenAIMessage = new("user", "old")
    answerMsg: OpenAIMessage = new("assistant", "answer")
    messages: list[OpenAIMessage] = [oldMsg, answerMsg]
    mcp: McpServer = new()
    mcp.label = "docs"
    mcp.url = "https://example.com/mcp"
    fn: McpFuncCall = new()
    fn.label = "local"
    fn.name = "echo"
    fn.description = "Echo local args"
    fn.parametersJson = "{}"
    fn.handler = _localMcpEcho
    mcps: list[McpBase] = [mcp, fn]
    body: str = _buildResponsesBody(
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
    self.assertTrue('"requireApproval":"never"' in body)
    self.assertTrue('"type":"function"' in body)
    self.assertTrue('"name":"echo"' in body)
    self.assertEqual(fn.call('{"x":1}'), 'echo:{"x":1}')
    self.assertTrue("Conversation summary" in body)


class OpenAIResponsesParseTests(TestCaseMixin):
  _testTag = 37

  @override
  def test(self):
    raw: str = '{"id":"resp_1","output_text":"pong"}'
    self.assertEqual(_responseId(raw), "resp_1")
    self.assertEqual(_responseText(raw), "pong")
    nested: str = '{"output":[{"content":[{"type":"output_text","text":"he"},{"type":"output_text","text":"llo"}]}]}'
    self.assertEqual(_responseText(nested), "hello")
    self.assertEqual(_responsesDelta('{"type":"response.output_text.delta","delta":"tok"}'), "tok")
    streamed: str = ""
    for token in _iterResponsesSseTokens(
      'data: {"type":"response.output_text.delta","delta":"a"}\n\n'
      'data: {"type":"response.output_text.delta","delta":"b"}\n\n'
      'data: [DONE]\n\n'
    ):
      streamed += token
    self.assertEqual(streamed, "ab")


class OpenAIErrorTextTests(TestCaseMixin):
  _testTag = 39

  @override
  def test(self):
    msg: str = _statusErrorText(401, '{"error":{"message":"bad key"}}')
    self.assertTrue("HTTP 401 Unauthorized" in msg)
    self.assertTrue("bad key" in msg)


class OpenAIRequestHeadersTests(TestCaseMixin):
  _testTag = 41

  @override
  def test(self):
    headers: dict[str, str] = {}
    opts: RequestOptions = _requestOptions("sk-test", headers, "{}", 1.0)
    self.assertTrue("Mozilla/5.0" in opts.headers["User-Agent"])
    self.assertEqual(opts.headers["Authorization"], "Bearer sk-test")
    custom: dict[str, str] = {"User-Agent": "custom-client"}
    opts2: RequestOptions = _requestOptions("sk-test", custom, "{}", 1.0)
    self.assertEqual(opts2.headers["User-Agent"], "custom-client")


class OpenAIConversationLocalTests(TestCaseMixin):
  _testTag = 38

  @override
  def test(self):
    client: OpenAI = new(baseUrl="http://127.0.0.1:1/v1")
    conv: Conversation = client.conversation("gpt-test", system="sys", maxHistoryChars=16, compressTargetChars=12)
    srv: McpServer = new()
    srv.label = "docs"
    srv.url = "https://example.com/mcp"
    conv.addMcp(srv)
    fn: McpFuncCall = new()
    fn.label = "local"
    fn.name = "echo"
    fn.handler = _localMcpEcho
    conv.addMcp(fn)
    self.assertEqual(conv.model, "gpt-test")
    self.assertEqual(len(conv.mcps), 2)
    self.assertEqual(conv.callMcp("local", '{"x":1}'), 'echo:{"x":1}')
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
  _testTag = 40

  @override
  def test(self):
    raw: bytes = (
      b"HTTP/1.1 200 Ok\r\n"
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
    reader.loadBytes(raw)
    writer: StreamWriter = new.fromBuffer()
    resp: ClientStreamResponse = new.fromStreams(reader, writer)
    self.assertEqual(resp.status, 200)
    self.assertEqual(resp.readLine(), "data: one")
    self.assertEqual(resp.readLine(), "")
    self.assertEqual(resp.readLine(), "data: two")


class ClientStreamTextTests(TestCaseMixin):
  _testTag = 45

  @override
  def test(self):
    reader: StreamReader = new()
    reader.loadBytes(b"plain body")
    writer: StreamWriter = new.fromBuffer()
    head: ClientResponse = new(status=401)
    resp: ClientStreamResponse = new.fromHead(reader, writer, head)
    self.assertEqual(resp.text(), "plain body")


async def _serveOpenaiChat(listener: AsyncTcpSocket) -> None:
  conn: AsyncTcpSocket = await listener.accept()
  reader: AsyncStreamReader = new.fromSocket(conn)
  writer: AsyncStreamWriter = new.fromSocket(conn)
  req: Request = await new.readAsync(reader)
  resp: Response = new.textResponse('{"choices":[{"message":{"content":"pong-async"}}]}', StatusCodeEnum.Ok)
  await resp.writeAsync(writer)
  reader.close()
  writer.close()
  listener.close()


async def _asyncChatRoundtrip() -> str:
  listener: AsyncTcpSocket = new()
  listener.bind("127.0.0.1", _ChatPort)
  listener.listen(16)
  serverTask: Task[None] = Task.create(_serveOpenaiChat(listener))
  await Task.sleep(0)
  client: AsyncOpenAI = new(baseUrl=f"http://127.0.0.1:{_ChatPort}/v1")
  text: str = await client.chat("gpt-test", "ping")
  await serverTask
  return text


class AsyncOpenAIChatTests(TestCaseMixin):
  _testTag = 50

  @override
  def test(self):
    self.assertEqual(Task.run(_asyncChatRoundtrip()), "pong-async")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
