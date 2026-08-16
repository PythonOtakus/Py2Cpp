"""``py2cpp.web`` 同步 HTTP 报文与服务器分派（内存流，无真实 socket）。"""

from py2cpp import *
from py2cpp.test.unittest import TestCaseMixin, TestSuite, TextTestRunner
from py2cpp.web.http import (
  StatusCodeEnum,
  Request,
  RequestOptions,
  Response,
  ClientResponse,
)
from py2cpp.web.server import RouteGetMeta, ServerMixin
from py2cpp.web.stream import StreamReader, StreamWriter
from py2cpp.web.url import UrlData, mergeQuery


class ParseUrlTests(TestCaseMixin):
  _testTag = 1

  @override
  def test(self):
    pu = UrlData.parse("http://127.0.0.1:8080/hello?x=1")
    self.assertEqual(pu.host, "127.0.0.1")
    self.assertEqual(pu.port, 8080)
    self.assertEqual(pu.path, "/hello")
    self.assertEqual(pu.query, "x=1")
    merged: str = mergeQuery("x=1", {"y": "2"})
    self.assertEqual(merged, "x=1&y=2")


class HttpRoundtripTests(TestCaseMixin):
  _testTag = 10

  @override
  def test(self):
    opts: RequestOptions = new(headers={"User-Agent": "py2cpp-test"})
    pu = UrlData.parse("http://127.0.0.1/ping")
    raw: bytes = opts.encode("GET", pu)
    reader: StreamReader = new()
    reader.loadBytes(raw)
    req: Request = new.read(reader)
    self.assertEqual(req.method, "GET")
    self.assertEqual(req.path, "/ping")
    self.assertEqual(req.host(), "127.0.0.1")
    self.assertEqual(req.headers["User-Agent"], "py2cpp-test")

    resp: Response = new.textResponse("pong", StatusCodeEnum.Ok)
    writer: StreamWriter = new.fromBuffer()
    resp.write(writer)
    out: bytes = writer.takeBytes()
    r2: StreamReader = new()
    r2.loadBytes(out)
    got = ClientResponse.read(r2)
    self.assertEqual(got.status, 200)
    self.assertEqual(got.text(), "pong")


class RequestOptionsParamsTests(TestCaseMixin):
  _testTag = 15

  @override
  def test(self):
    opts: RequestOptions = new(params={"q": "hi", "page": "1"})
    pu = UrlData.parse("http://127.0.0.1/search?x=1")
    raw: bytes = opts.encode("GET", pu)
    reader: StreamReader = new()
    reader.loadBytes(raw)
    req: Request = new.read(reader)
    self.assertEqual(req.path, "/search?x=1&q=hi&page=1")


class RequestOptionsCookiesAuthTests(TestCaseMixin):
  _testTag = 17

  @override
  def test(self):
    opts: RequestOptions = new(cookies={"sid": "abc"}, timeout=5.0)
    opts.auth.user = "alice"
    opts.auth.password = "secret"
    self.assertEqual(opts.timeout, 5.0)
    pu = UrlData.parse("http://127.0.0.1/api")
    raw: bytes = opts.encode("GET", pu)
    reader: StreamReader = new()
    reader.loadBytes(raw)
    req: Request = new.read(reader)
    self.assertEqual(req.headers["Cookie"], "sid=abc")
    self.assertEqual(req.headers["Authorization"], "Basic YWxpY2U6c2VjcmV0")


class HelloApp(ServerMixin):
  @RouteGetMeta("/hello")
  def hello(self, request: Request) -> Response:
    return new.textResponse("hello", StatusCodeEnum.Ok)


class ServerDispatchTests(TestCaseMixin):
  _testTag = 20

  @override
  def test(self):
    app: HelloApp = new()
    pu = UrlData.parse("http://localhost/hello")
    opts: RequestOptions = new()
    raw: bytes = opts.encode("GET", pu)
    reader: StreamReader = new()
    reader.loadBytes(raw)
    writer: StreamWriter = new.fromBuffer()
    app.handleStreams(reader, writer)
    out: bytes = writer.takeBytes()
    r2: StreamReader = new()
    r2.loadBytes(out)
    got = ClientResponse.read(r2)
    self.assertEqual(got.status, 200)
    self.assertEqual(got.text(), "hello")


def main():
  suite: TestSuite = new()
  suite.addTest(ParseUrlTests())
  suite.addTest(HttpRoundtripTests())
  suite.addTest(RequestOptionsParamsTests())
  suite.addTest(RequestOptionsCookiesAuthTests())
  suite.addTest(ServerDispatchTests())
  runner: TextTestRunner = new()
  return runner.run(suite)


if __name__ == "__main__":
  raise SystemExit(main())
