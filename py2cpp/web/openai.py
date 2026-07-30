"""OpenAI-compatible 最简聊天客户端。"""
from ..builtins import *
from ..core.exceptions import Exception, ValueError
from ..serde.json import JsonDecoder, JsonEncoder
from .client import AsyncClientSession, ClientSession
from .http import (
  ClientResponse,
  ClientStreamResponse,
  RequestOptions,
  reason_phrase,
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


class TLSUnavailableError(OpenAIError):
  pass


class ToolCallError(OpenAIError):
  pass


_DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"


@copyable
@dataclass(eq=False, repr=False)
class OpenAIMessage:
  """Responses/Conversation 本地消息。"""

  role: str = ""
  content: str = ""


@refcount
class McpBase:
  """MCP tool 语义基类。"""

  label: str = ""

  @virtual
  def append_tool(self, enc: JsonEncoder @ref) -> None:
    raise ToolCallError()

  @virtual
  def call(self, args_json: str) -> str:
    raise ToolCallError()
    return ""


@refcount
class McpServer(McpBase):
  """Remote MCP server 配置。"""

  url: str = ""
  require_approval: bool = False
  headers: dict[str, str] = {}

  @override
  def append_tool(self, enc: JsonEncoder @ref) -> None:
    enc.begin_object()
    enc.dump_field_str("type", "mcp")
    enc.dump_field_str("server_label", self.label)
    enc.dump_field_str("server_url", self.url)
    if self.require_approval:
      enc.dump_field_str("require_approval", "always")
    else:
      enc.dump_field_str("require_approval", "never")
    if self.headers:
      enc.dump_key("headers")
      enc.begin_object()
      for k in self.headers:
        enc.dump_field_str(k, self.headers[k])
      enc.end_object()
    enc.end_object()


@refcount
class McpFuncCall(McpBase):
  """本地函数 MCP tool；持有真实 Callable handler。"""

  name: str = ""
  description: str = ""
  parameters_json: str = ""
  handler: Callable[[str], str] = new()

  @override
  def append_tool(self, enc: JsonEncoder @ref) -> None:
    enc.begin_object()
    enc.dump_field_str("type", "function")
    if self.name:
      enc.dump_field_str("name", self.name)
    else:
      enc.dump_field_str("name", self.label)
    if self.description:
      enc.dump_field_str("description", self.description)
    if self.parameters_json:
      enc.dump_field_str("parameters", self.parameters_json)
    enc.end_object()

  @override
  def call(self, args_json: str) -> str:
    return self.handler(args_json)


@immutable
def _normalize_base_url(base_url: str) -> str:
  if base_url.endswith("/"):
    return base_url[:-1]
  return base_url


@immutable
def _looks_like_url(text: str) -> bool:
  return text.startswith("http://") or text.startswith("https://")


@immutable
def _looks_like_api_key(text: str) -> bool:
  return text.startswith("sk-")


@immutable
def _endpoint(base_url: str) -> str:
  return f"{_normalize_base_url(base_url)}/chat/completions"


@immutable
def _responses_endpoint(base_url: str) -> str:
  return f"{_normalize_base_url(base_url)}/responses"


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
  if "User-Agent" not in headers and "user-agent" not in headers:
    headers["User-Agent"] = _DEFAULT_USER_AGENT
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
def _append_openai_message(enc: JsonEncoder @ref, msg: OpenAIMessage) -> None:
  _append_message(enc, msg.role, msg.content)


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
def _build_responses_body(
  model: str,
  system: str,
  summary: str,
  messages: list[OpenAIMessage],
  message: str,
  last_response_id: str,
  mcps: list[McpBase],
  max_tokens: int,
  temperature: float,
  stream: bool,
) -> str:
  enc: JsonEncoder = new()
  enc.begin_object()
  enc.dump_field_str("model", model)
  if max_tokens > 0:
    enc.dump_field_int("max_output_tokens", max_tokens)
  if temperature >= 0.0:
    enc.dump_key("temperature")
    enc.dump_float(temperature)
  if last_response_id:
    enc.dump_field_str("previous_response_id", last_response_id)
  if stream:
    enc.dump_field_bool("stream", True)
  enc.dump_key("input")
  enc.begin_array()
  if system:
    _append_message(enc, "system", system)
  if summary:
    _append_message(enc, "system", f"Conversation summary:\n{summary}")
  for msg in messages:
    _append_openai_message(enc, msg)
  _append_message(enc, "user", message)
  enc.end_array()
  if mcps:
    enc.dump_key("tools")
    enc.begin_array()
    for mcp in mcps:
      mcp.append_tool(enc)
    enc.end_array()
  enc.end_object()
  return enc.take()


def _object_string_field(dec: JsonDecoder @ref, field: str) -> str:
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == field:
      mark: int = dec.mark()
      try:
        return dec.load_str()
      except ValueError:
        dec.restore(mark)
        dec.skip_value()
        return ""
    dec.skip_value()
  return ""


def _load_optional_str(dec: JsonDecoder @ref) -> str:
  mark: int = dec.mark()
  try:
    return dec.load_str()
  except ValueError:
    dec.restore(mark)
    dec.skip_value()
    return ""


def _skip_array_comma(dec: JsonDecoder @ref) -> None:
  dec.skip_spaces()
  if dec.pos < len(dec.s) and dec.s[dec.pos] == ord(","):
    dec.pos += 1


def _content_array_text(dec: JsonDecoder @ref) -> str:
  out: str = ""
  dec.begin_array()
  while not dec.at_array_end():
    _skip_array_comma(dec)
    dec.begin_root_object()
    while not dec.at_object_end():
      key: str = dec.load_key()
      if key == "text":
        out += _load_optional_str(dec)
      else:
        dec.skip_value()
  return out


def _output_item_text(dec: JsonDecoder @ref) -> str:
  out: str = ""
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "content":
      out += _content_array_text(dec)
    else:
      dec.skip_value()
  return out


def _output_array_text(dec: JsonDecoder @ref) -> str:
  out: str = ""
  dec.begin_array()
  while not dec.at_array_end():
    _skip_array_comma(dec)
    out += _output_item_text(dec)
  return out


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


def _response_id(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  return _object_string_field(dec, "id")


def _response_text(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "output_text":
      return _load_optional_str(dec)
    if key == "output":
      return _output_array_text(dec)
    dec.skip_value()
  return ""


def _chat_content(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "content":
      return _load_optional_str(dec)
    if key == "choices":
      return _first_choice_object_field_content(dec, "message")
    dec.skip_value()
  return ""


def _responses_delta(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  typ: str = ""
  delta: str = ""
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "type":
      typ = _load_optional_str(dec)
    elif key == "delta":
      delta = _load_optional_str(dec)
    else:
      dec.skip_value()
  if typ == "response.output_text.delta":
    return delta
  if not typ and delta:
    return delta
  return ""


def _responses_completed_id(raw_json: str) -> str:
  dec: JsonDecoder = new.from_text(raw_json)
  typ: str = ""
  rid: str = ""
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    if key == "type":
      typ = _load_optional_str(dec)
    elif key == "response":
      rid = _object_string_field(dec, "id")
    else:
      dec.skip_value()
  if typ == "response.completed":
    return rid
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


def _iter_responses_sse_tokens(text: str) -> Generator[str, None, None]:
  lines: list[str] = text.splitlines()
  for line in lines:
    if line.startswith("data: "):
      payload: str = line[6:]
      if payload == "[DONE]":
        return
      token: str = _responses_delta(payload)
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


@immutable
def _status_ok(status: int) -> bool:
  return status >= 200 and status < 300


@immutable
def _short_error_body(body: str) -> str:
  text: str = body.replace("\r", " ")
  text = text.replace("\n", " ")
  if len(text) > 512:
    return text[:512]
  return text


@immutable
def _status_error_text(status: int, body: str) -> str:
  out: str = f"HTTP {status} {reason_phrase(status)}"
  detail: str = _short_error_body(body)
  if detail:
    out = f"{out}: {detail}"
  return out


@immutable
def _response_error_text(resp: ClientResponse) -> str:
  return _status_error_text(resp.status, resp.text())


def _stream_error_text(resp: ClientStreamResponse) -> str:
  return _status_error_text(resp.status, resp.text())


def _raise_for_status(resp: ClientResponse) -> None:
  _raise_for_status_code(resp.status)


def _raise_for_stream_status(resp: ClientStreamResponse) -> None:
  _raise_for_status_code(resp.status)


@refcount
class _OpenAIState:
  """``OpenAI`` / ``Conversation`` 共享状态；生成器复制客户端时仍能回写错误信息。"""

  last_error: str = ""


@copyable
@dataclass(eq=False, repr=False)
class Conversation:
  """长对话客户端；方法名保持 ``chat`` / ``chat_stream``。"""

  api_key: str = ""
  base_url: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  default_headers: dict[str, str] @optional = {}
  model: str = ""
  system: str = ""
  _state: _OpenAIState @optional = new()
  messages: list[OpenAIMessage] @optional = []
  summary: str = ""
  last_response_id: str = ""
  max_history_chars: int = 12000
  compress_target_chars: int = 4000
  mcps: list[McpBase] @optional = []

  def __post_init__(self):
    if _looks_like_url(self.api_key) and not _looks_like_url(self.base_url):
      old_key: str = self.api_key
      self.api_key = self.base_url
      self.base_url = old_key
    self.base_url = _normalize_base_url(self.base_url)

  @property
  def last_error(self) -> str:
    return self._state.last_error

  @property.setter
  def last_error(self, value: str) -> None:
    self._state.last_error = value

  def use_state(self, state: _OpenAIState) -> None:
    self._state = state

  def add_mcp(self, mcp: McpBase) -> None:
    self.mcps.append(mcp)

  def clear_mcp(self) -> None:
    self.mcps.clear()

  def call_mcp(self, label: str, args_json: str) -> str:
    for mcp in self.mcps:
      if mcp.label == label:
        return mcp.call(args_json)
    raise ToolCallError()
    return ""

  def history_chars(self) -> int:
    total: int = len(self.system) + len(self.summary)
    for msg in self.messages:
      total += len(msg.role) + len(msg.content) + 2
    return total

  def compress(self) -> None:
    n: int = len(self.messages)
    if n <= 4:
      return
    keep_from: int = n - 4
    old: str = self.summary
    for i in range(keep_from):
      msg: OpenAIMessage = self.messages[i]
      line: str = f"{msg.role}: {msg.content}\n"
      old += line
    if len(old) > self.compress_target_chars:
      old = old[len(old) - self.compress_target_chars :]
    recent: list[OpenAIMessage] = []
    for i in range(keep_from, n):
      recent.append(self.messages[i])
    self.summary = old
    self.messages = recent

  def _maybe_compress(self) -> None:
    if self.history_chars() > self.max_history_chars:
      self.compress()

  def _options(self, body: str) -> RequestOptions:
    return _request_options(self.api_key, self.default_headers, body, self.timeout)

  def chat(self, message: str, max_tokens: int = 0, temperature: float = -1.0) -> str:
    self.last_error = ""
    self._maybe_compress()
    body: str = _build_responses_body(
      self.model,
      self.system,
      self.summary,
      self.messages,
      message,
      self.last_response_id,
      self.mcps,
      max_tokens,
      temperature,
      False,
    )
    opts: RequestOptions = self._options(body)
    session: ClientSession = new()
    resp: ClientResponse = session.request_options("POST", _responses_endpoint(self.base_url), opts)
    if not _status_ok(resp.status):
      self.last_error = _response_error_text(resp)
    _raise_for_status(resp)
    raw: str = resp.text()
    text: str = _response_text(raw)
    rid: str = _response_id(raw)
    if rid:
      self.last_response_id = rid
    user_msg: OpenAIMessage = new("user", message)
    assistant_msg: OpenAIMessage = new("assistant", text)
    self.messages.append(user_msg)
    self.messages.append(assistant_msg)
    self._maybe_compress()
    return text

  def chat_stream(self, message: str, max_tokens: int = 0, temperature: float = -1.0) -> Generator[str, None, None]:
    self.last_error = ""
    self._maybe_compress()
    body: str = _build_responses_body(
      self.model,
      self.system,
      self.summary,
      self.messages,
      message,
      self.last_response_id,
      self.mcps,
      max_tokens,
      temperature,
      True,
    )
    opts: RequestOptions = self._options(body)
    session: ClientSession = new()
    resp: ClientStreamResponse = session.stream_options("POST", _responses_endpoint(self.base_url), opts)
    if not _status_ok(resp.status):
      self.last_error = _stream_error_text(resp)
    _raise_for_stream_status(resp)
    text: str = ""
    rid: str = ""
    while True:
      line: str = resp.readline()
      if line.startswith("data: "):
        payload: str = line[6:]
        if payload == "[DONE]":
          resp.close()
          user_msg: OpenAIMessage = new("user", message)
          assistant_msg: OpenAIMessage = new("assistant", text)
          self.messages.append(user_msg)
          self.messages.append(assistant_msg)
          if rid:
            self.last_response_id = rid
          self._maybe_compress()
          return
        done_id: str = _responses_completed_id(payload)
        if done_id:
          rid = done_id
        token: str = _responses_delta(payload)
        if token:
          text += token
          yield token


@copyable
@dataclass(eq=False, repr=False)
class OpenAI:
  """最简 OpenAI-compatible 聊天客户端。"""

  api_key: str = ""
  base_url: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  default_headers: dict[str, str] @optional = {}
  _state: _OpenAIState @optional = new()

  def __post_init__(self):
    if _looks_like_url(self.api_key) and not _looks_like_url(self.base_url):
      old_key: str = self.api_key
      self.api_key = self.base_url
      self.base_url = old_key
    self.base_url = _normalize_base_url(self.base_url)

  @property
  def last_error(self) -> str:
    return self._state.last_error

  @property.setter
  def last_error(self, value: str) -> None:
    self._state.last_error = value

  def conversation(
    self,
    model: str,
    system: str = "",
    max_history_chars: int = 12000,
    compress_target_chars: int = 4000,
  ) -> Conversation:
    conv: Conversation = new()
    conv.api_key = self.api_key
    conv.base_url = self.base_url
    conv.timeout = self.timeout
    conv.default_headers = {}
    for k in self.default_headers:
      conv.default_headers[k] = self.default_headers[k]
    conv.use_state(self._state)
    conv.model = model
    conv.system = system
    conv.max_history_chars = max_history_chars
    conv.compress_target_chars = compress_target_chars
    return conv

  def chat(
    self,
    model: str,
    message: str,
    system: str = "",
    max_tokens: int = 0,
    temperature: float = -1.0,
  ) -> str:
    self.last_error = ""
    body: str = _build_chat_body(model, message, system, max_tokens, temperature, False)
    opts: RequestOptions = _request_options(self.api_key, self.default_headers, body, self.timeout)
    session: ClientSession = new()
    resp: ClientResponse = session.request_options("POST", _endpoint(self.base_url), opts)
    if not _status_ok(resp.status):
      self.last_error = _response_error_text(resp)
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
    self.last_error = ""
    body: str = _build_chat_body(model, message, system, max_tokens, temperature, True)
    opts: RequestOptions = _request_options(self.api_key, self.default_headers, body, self.timeout)
    session: ClientSession = new()
    resp: ClientStreamResponse = session.stream_options("POST", _endpoint(self.base_url), opts)
    if not _status_ok(resp.status):
      self.last_error = _stream_error_text(resp)
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
@dataclass(eq=False, repr=False)
class AsyncOpenAI:
  """最简异步 OpenAI-compatible 聊天客户端。"""

  api_key: str = ""
  base_url: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  default_headers: dict[str, str] @optional = {}
  _state: _OpenAIState @optional = new()

  def __post_init__(self):
    if _looks_like_url(self.api_key) and not _looks_like_url(self.base_url):
      old_key: str = self.api_key
      self.api_key = self.base_url
      self.base_url = old_key
    self.base_url = _normalize_base_url(self.base_url)

  @property
  def last_error(self) -> str:
    return self._state.last_error

  @property.setter
  def last_error(self, value: str) -> None:
    self._state.last_error = value

  async def chat(
    self,
    model: str,
    message: str,
    system: str = "",
    max_tokens: int = 0,
    temperature: float = -1.0,
  ) -> str:
    self.last_error = ""
    body: str = _build_chat_body(model, message, system, max_tokens, temperature, False)
    opts: RequestOptions = _request_options(self.api_key, self.default_headers, body, self.timeout)
    session: AsyncClientSession = new()
    resp: ClientResponse = await session.request_options("POST", _endpoint(self.base_url), opts)
    if not _status_ok(resp.status):
      self.last_error = _response_error_text(resp)
    _raise_for_status(resp)
    return _chat_content(resp.text())
