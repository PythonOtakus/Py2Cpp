"""``py2cpp.web`` 异步 HTTP：真实 non-blocking socket roundtrip。"""

from py2cpp import *
from py2cpp.concur.task import Task
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.client import AsyncClientSession
from py2cpp.web.http import ClientResponse, Request, Response, StatusCodeEnum
from py2cpp.web.server import AsyncServerMixin, RouteGetMeta


_Port: int = 18131


class HelloAsyncApp(AsyncServerMixin):
  @RouteGetMeta("/hello")
  def hello(self, request: Request) -> Response:
    return new.textResponse("hello-async", StatusCodeEnum.Ok)


async def asyncHttpRoundtrip() -> str:
  app: HelloAsyncApp = new()
  serverTask: Task[None] = Task.create(app.serveN("127.0.0.1", _Port, 1))
  await Task.sleep(0)
  session: AsyncClientSession = new()
  resp: ClientResponse = await session.get(f"http://127.0.0.1:{_Port}/hello")
  await serverTask
  if resp.status != 200:
    return "bad-status"
  return resp.text()


class AsyncHttpRoundtripTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    self.assertEqual(Task.run(asyncHttpRoundtrip()), "hello-async")


def main():
  suite: TestSuite = new()
  for Class in TestCaseMixin.iterSubclasses(sortConst="_testTag"):
    suite.addTest(Class())
  return TextTestRunner().run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
