"""``py2cpp.web.openai`` 最简 chat/chat_stream 辅助逻辑回归。"""
from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.openai import _build_chat_body, _chat_content, _iter_sse_tokens


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


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
