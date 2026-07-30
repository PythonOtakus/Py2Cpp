"""OpenAI-compatible 最简聊天客户端。"""
from ..builtins import *
from ..core.exceptions import Exception
from ..serde.json import JsonDecoder, JsonEncoder
from .client import AsyncClientSession, ClientSession
from .http import (
  ClientResponse,
  ClientStreamResponse,
  RequestOptions,
)


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


def _object_string_field(dec: JsonDecoder @ref, field: str) -> str:
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == field:
      return dec.load_str()
    dec.skip_value()
  return ""


def _first_choice_object_field_content(dec: JsonDecoder @ref, field: str) -> str:
  dec.begin_array()
  if dec.at_array_end():
    return ""
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == field:
      return _object_string_field(dec, "content")
    dec.skip_value()
  return ""


def _chat_content(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "content":
      return dec.load_str()
    if key == "choices":
      return _first_choice_object_field_content(dec, "message")
    dec.skip_value()
  return ""


def _delta_content(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "choices":
      return _first_choice_object_field_content(dec, "delta")
    dec.skip_value()
  return ""


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


def _raise_for_status_code(status: int) -> None:
  if status >= 200 and status < 300:
    return
  match status:
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
      if status >= 500:
        raise InternalServerError()
      raise APIError()


def _raise_for_status(resp: ClientResponse) -> None:
  _raise_for_status_code(resp.status)


def _raise_for_stream_status(resp: ClientStreamResponse) -> None:
  _raise_for_status_code(resp.status)


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
    resp: ClientStreamResponse = session.stream_options("POST", _endpoint(self.base_url), opts)
    _raise_for_stream_status(resp)
    while True:
      line: str = resp.readline()
      if line.startswith("data: "):
        payload: str = line[6:]
        if payload == "[DONE]":
          resp.close()
          return
        token: str = _delta_content(payload)
        if token:
          yield token


@copyable
class AsyncOpenAI:
  """最简异步 OpenAI-compatible 聊天客户端。"""

  api_key: str = ""
  base_url: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  default_headers: dict[str, str] = {}

  def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1", timeout: float = 60.0):
    self.api_key = api_key
    self.base_url = _normalize_base_url(base_url)
    self.timeout = timeout
    self.default_headers = {}

  async def chat(
    self,
    model: str,
    message: str,
    system: str = "",
    max_tokens: int = 0,
    temperature: float = -1.0,
  ) -> str:
    body: str = _build_chat_body(model, message, system, max_tokens, temperature, False)
    opts: RequestOptions = _request_options(self.api_key, self.default_headers, body, self.timeout)
    session: AsyncClientSession = new()
    resp: ClientResponse = await session.request_options("POST", _endpoint(self.base_url), opts)
    _raise_for_status(resp)
    return _chat_content(resp.text())
