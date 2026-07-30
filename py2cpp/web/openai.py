"""OpenAI-compatible 最简聊天客户端。"""
from ..builtins import *
from ..core.exceptions import Exception
from ..serde.json import JsonDecoder, JsonEncoder
from .client import ClientSession
from .http import ClientResponse, RequestOptions


class OpenAIError(Exception):
  """``py2cpp.web.openai`` 异常基类。"""

  pass


class APIError(OpenAIError):
  """OpenAI-compatible HTTP API 返回非 2xx。"""

  pass


class BadRequestError(APIError):
  pass


class AuthenticationError(APIError):
  pass


class PermissionDeniedError(APIError):
  pass


class NotFoundError(APIError):
  pass


class RateLimitError(APIError):
  pass


class InternalServerError(APIError):
  pass


@immutable
def _normalize_base_url(base_url: str) -> str:
  if base_url.endswith("/"):
    return base_url[:-1]
  return base_url


@immutable
def _endpoint(base_url: str) -> str:
  return f"{_normalize_base_url(base_url)}/chat/completions"


@immutable
def _request_options(
  api_key: str,
  default_headers: dict[str, str],
  body: str,
  timeout: float,
) -> RequestOptions:
  headers: dict[str, str] = {}
  for k in default_headers:
    headers[k] = default_headers[k]
  headers["Accept"] = "application/json"
  headers["Content-Type"] = "application/json"
  if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
  return new(headers=headers, data=body.encode(), timeout=timeout)


@immutable
def _append_message(enc: JsonEncoder @ref, role: str, content: str) -> None:
  enc.begin_object()
  enc.dump_field_str("role", role)
  enc.dump_field_str("content", content)
  enc.end_object()


@immutable
def _build_chat_body(
  model: str,
  message: str,
  system: str,
  max_tokens: int,
  temperature: float,
  stream: bool,
) -> str:
  enc: JsonEncoder = new()
  enc.begin_object()
  enc.dump_field_str("model", model)
  if max_tokens > 0:
    enc.dump_field_int("max_tokens", max_tokens)
  if temperature >= 0.0:
    enc.dump_key("temperature")
    enc.dump_float(temperature)
  if stream:
    enc.dump_field_bool("stream", True)
  enc.dump_key("messages")
  enc.begin_array()
  if system:
    _append_message(enc, "system", system)
  _append_message(enc, "user", message)
  enc.end_array()
  enc.end_object()
  return enc.take()


@immutable
def _json_string_after(raw_json: str, marker: str) -> str:
  pos: int = raw_json.find(marker)
  if pos < 0:
    return ""
  start: int = pos + len(marker)
  tail: str = raw_json[start:]
  dec: JsonDecoder = new.from_text(tail)
  return dec.load_str()


@immutable
def _top_string_field(raw_json: str, field: str) -> str:
  marker: str = f'"{field}":'
  return _json_string_after(raw_json, marker)


@immutable
def _json_string_after_any(raw_json: str, first: str, second: str) -> str:
  value: str = _json_string_after(raw_json, first)
  if value:
    return value
  if second:
    return _json_string_after(raw_json, second)
  return ""


@immutable
def _chat_content(raw_json: str) -> str:
  return _json_string_after_any(raw_json, '"content":', '')


@immutable
def _delta_content(raw_json: str) -> str:
  return _json_string_after_any(raw_json, '"delta":{"content":', '"content":')


def _iter_sse_tokens(text: str) -> Generator[str, None, None]:
  lines: list[str] = text.splitlines()
  for line in lines:
    if line.startswith("data: "):
      payload: str = line[6:]
      if payload == "[DONE]":
        return
      token: str = _delta_content(payload)
      if token:
        yield token


def _raise_for_status(resp: ClientResponse) -> None:
  if resp.status >= 200 and resp.status < 300:
    return
  match resp.status:
    case 400:
      raise BadRequestError()
    case 401:
      raise AuthenticationError()
    case 403:
      raise PermissionDeniedError()
    case 404:
      raise NotFoundError()
    case 429:
      raise RateLimitError()
    case _:
      if resp.status >= 500:
        raise InternalServerError()
      raise APIError()


@copyable
class OpenAI:
  """最简 OpenAI-compatible 聊天客户端。"""

  api_key: str = ""
  base_url: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  default_headers: dict[str, str] = {}

  def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1", timeout: float = 60.0):
    self.api_key = api_key
    self.base_url = _normalize_base_url(base_url)
    self.timeout = timeout
    self.default_headers = {}

  def chat(
    self,
    model: str,
    message: str,
    system: str = "",
    max_tokens: int = 0,
    temperature: float = -1.0,
  ) -> str:
    body: str = _build_chat_body(model, message, system, max_tokens, temperature, False)
    opts: RequestOptions = _request_options(self.api_key, self.default_headers, body, self.timeout)
    session: ClientSession = new()
    resp: ClientResponse = session.request_options("POST", _endpoint(self.base_url), opts)
    _raise_for_status(resp)
    return _chat_content(resp.text())

  def chat_stream(
    self,
    model: str,
    message: str,
    system: str = "",
    max_tokens: int = 0,
    temperature: float = -1.0,
  ) -> Generator[str, None, None]:
    body: str = _build_chat_body(model, message, system, max_tokens, temperature, True)
    opts: RequestOptions = _request_options(self.api_key, self.default_headers, body, self.timeout)
    session: ClientSession = new()
    resp: ClientResponse = session.request_options("POST", _endpoint(self.base_url), opts)
    _raise_for_status(resp)
    yield from _iter_sse_tokens(resp.text())
