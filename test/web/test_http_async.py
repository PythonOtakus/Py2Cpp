"""``py2cpp.web`` 异步 HTTP：真实 non-blocking socket roundtrip。"""

from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.client import AsyncClientSession
from py2cpp.web.http import ClientResponse, Request, Response, StatusCode
from py2cpp.web.server import AsyncServerMixin, RouteGetMeta


_PORT: int = 18131


class HelloAsyncApp(AsyncServerMixin):
  @RouteGetMeta("/hello")
  def hello(self, request: Request) -> Response:
    return new.text_response("hello-async", StatusCode.OK)


async def async_http_roundtrip() -> str:
  app: HelloAsyncApp = new()
  server_task: Task[None] = Task.create(app.serve_n("127.0.0.1", _PORT, 1))
  await Task.sleep(0)
  session: AsyncClientSession = new()
  resp: ClientResponse = await session.get(f"http://127.0.0.1:{_PORT}/hello")
  await server_task
  if resp.status != 200:
    return "bad-status"
  return resp.text()


class AsyncHttpRoundtripTests(TestCaseMixin):
  _test_tag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(async_http_roundtrip()), "hello-async")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iter_subclasses(sort_const="_test_tag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
