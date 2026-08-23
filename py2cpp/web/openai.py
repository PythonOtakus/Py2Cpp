"""OpenAI-compatible 最简聊天客户端。"""
from ..builtins import *
from ..core.exceptions import Exception, ValueError
from ..serde.json import JsonDecoder, JsonEncoder
from .client import AsyncClientSession, ClientSession
from .http import (
  ClientResponse,
  ClientStreamResponse,
  RequestOptions,
  reasonPhrase,
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


_DefaultUserAgent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"


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
  def appendTool(self, enc: JsonEncoder @ref) -> None:
    raise ToolCallError()

  @virtual
  def call(self, argsJson: str) -> str:
    raise ToolCallError()
    return ""


@refcount
class McpServer(McpBase):
  """Remote MCP server 配置。"""

  url: str = ""
  requireApproval: bool = False
  headers: dict[str, str] = {}

  @override
  def appendTool(self, enc: JsonEncoder @ref) -> None:
    enc.beginObject()
    enc.dumpFieldStr("type", "mcp")
    enc.dumpFieldStr("server_label", self.label)
    enc.dumpFieldStr("server_url", self.url)
    if self.requireApproval:
      enc.dumpFieldStr("requireApproval", "always")
    else:
      enc.dumpFieldStr("requireApproval", "never")
    if self.headers:
      enc.dumpKey("headers")
      enc.beginObject()
      for k in self.headers:
        enc.dumpFieldStr(k, self.headers[k])
      enc.endObject()
    enc.endObject()


@refcount
class McpFuncCall(McpBase):
  """本地函数 MCP tool；持有真实 Callable handler。"""

  name: str = ""
  description: str = ""
  parametersJson: str = ""
  handler: Callable[[str], str] = new()

  @override
  def appendTool(self, enc: JsonEncoder @ref) -> None:
    enc.beginObject()
    enc.dumpFieldStr("type", "function")
    if self.name:
      enc.dumpFieldStr("name", self.name)
    else:
      enc.dumpFieldStr("name", self.label)
    if self.description:
      enc.dumpFieldStr("description", self.description)
    if self.parametersJson:
      enc.dumpFieldStr("parameters", self.parametersJson)
    enc.endObject()

  @override
  def call(self, argsJson: str) -> str:
    return self.handler(argsJson)


@immutable
def _normalizeBaseUrl(baseUrl: str) -> str:
  if baseUrl.endsWith("/"):
    return baseUrl[:-1]
  return baseUrl


@immutable
def _looksLikeUrl(text: str) -> bool:
  return text.startsWith("http://") or text.startsWith("https://")


@immutable
def _looksLikeApiKey(text: str) -> bool:
  return text.startsWith("sk-")


@immutable
def _endpoint(baseUrl: str) -> str:
  return f"{_normalizeBaseUrl(baseUrl)}/chat/completions"


@immutable
def _responsesEndpoint(baseUrl: str) -> str:
  return f"{_normalizeBaseUrl(baseUrl)}/responses"


@immutable
def _requestOptions(
  apiKey: str,
  defaultHeaders: dict[str, str],
  body: str,
  timeout: float,
) -> RequestOptions:
  headers: dict[str, str] = {}
  for k in defaultHeaders:
    headers[k] = defaultHeaders[k]
  if "User-Agent" not in headers and "user-agent" not in headers:
    headers["User-Agent"] = _DefaultUserAgent
  headers["Accept"] = "application/json"
  headers["Content-Type"] = "application/json"
  if apiKey:
    headers["Authorization"] = f"Bearer {apiKey}"
  return new(headers=headers, data=body.encode(), timeout=timeout)


@immutable
def _appendMessage(enc: JsonEncoder @ref, role: str, content: str) -> None:
  enc.beginObject()
  enc.dumpFieldStr("role", role)
  enc.dumpFieldStr("content", content)
  enc.endObject()


@immutable
def _appendOpenaiMessage(enc: JsonEncoder @ref, msg: OpenAIMessage) -> None:
  _appendMessage(enc, msg.role, msg.content)


@immutable
def _buildChatBody(
  model: str,
  message: str,
  system: str,
  maxTokens: int,
  temperature: float,
  stream: bool,
) -> str:
  enc: JsonEncoder = new()
  enc.beginObject()
  enc.dumpFieldStr("model", model)
  if maxTokens > 0:
    enc.dumpFieldInt("maxTokens", maxTokens)
  if temperature >= 0.0:
    enc.dumpKey("temperature")
    enc.dumpFloat(temperature)
  if stream:
    enc.dumpFieldBool("stream", True)
  enc.dumpKey("messages")
  enc.beginArray()
  if system:
    _appendMessage(enc, "system", system)
  _appendMessage(enc, "user", message)
  enc.endArray()
  enc.endObject()
  return enc.take()


@immutable
def _buildResponsesBody(
  model: str,
  system: str,
  summary: str,
  messages: list[OpenAIMessage],
  message: str,
  lastResponseId: str,
  mcps: list[McpBase],
  maxTokens: int,
  temperature: float,
  stream: bool,
) -> str:
  enc: JsonEncoder = new()
  enc.beginObject()
  enc.dumpFieldStr("model", model)
  if maxTokens > 0:
    enc.dumpFieldInt("max_output_tokens", maxTokens)
  if temperature >= 0.0:
    enc.dumpKey("temperature")
    enc.dumpFloat(temperature)
  if lastResponseId:
    enc.dumpFieldStr("previous_response_id", lastResponseId)
  if stream:
    enc.dumpFieldBool("stream", True)
  enc.dumpKey("input")
  enc.beginArray()
  if system:
    _appendMessage(enc, "system", system)
  if summary:
    _appendMessage(enc, "system", f"Conversation summary:\n{summary}")
  for msg in messages:
    _appendOpenaiMessage(enc, msg)
  _appendMessage(enc, "user", message)
  enc.endArray()
  if mcps:
    enc.dumpKey("tools")
    enc.beginArray()
    for mcp in mcps:
      mcp.appendTool(enc)
    enc.endArray()
  enc.endObject()
  return enc.take()


def _objectStringField(dec: JsonDecoder @ref, field: str) -> str:
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == field:
      mark: int = dec.mark()
      try:
        return dec.loadStr()
      except ValueError:
        dec.restore(mark)
        dec.skipValue()
        return ""
    dec.skipValue()
  return ""


def _loadOptionalStr(dec: JsonDecoder @ref) -> str:
  mark: int = dec.mark()
  try:
    return dec.loadStr()
  except ValueError:
    dec.restore(mark)
    dec.skipValue()
    return ""


def _skipArrayComma(dec: JsonDecoder @ref) -> None:
  dec.skipSpaces()
  if dec.pos < len(dec.s) and dec.s[dec.pos] == ord(","):
    dec.pos += 1


def _contentArrayText(dec: JsonDecoder @ref) -> str:
  out: str = ""
  dec.beginArray()
  while not dec.atArrayEnd():
    _skipArrayComma(dec)
    dec.beginRootObject()
    while not dec.atObjectEnd():
      key: str = dec.loadKey()
      if key == "text":
        out += _loadOptionalStr(dec)
      else:
        dec.skipValue()
  return out


def _outputItemText(dec: JsonDecoder @ref) -> str:
  out: str = ""
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == "content":
      out += _contentArrayText(dec)
    else:
      dec.skipValue()
  return out


def _outputArrayText(dec: JsonDecoder @ref) -> str:
  out: str = ""
  dec.beginArray()
  while not dec.atArrayEnd():
    _skipArrayComma(dec)
    out += _outputItemText(dec)
  return out


def _firstChoiceObjectFieldContent(dec: JsonDecoder @ref, field: str) -> str:
  dec.beginArray()
  if dec.atArrayEnd():
    return ""
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == field:
      return _objectStringField(dec, "content")
    dec.skipValue()
  return ""


def _responseId(rawJson: str) -> str:
  return _objectStringField(JsonDecoder.fromText(rawJson), "id")


def _responseText(rawJson: str) -> str:
  dec: JsonDecoder = new.fromText(rawJson)
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == "output_text":
      return _loadOptionalStr(dec)
    if key == "output":
      return _outputArrayText(dec)
    dec.skipValue()
  return ""


def _chatContent(rawJson: str) -> str:
  dec: JsonDecoder = new.fromText(rawJson)
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == "content":
      return _loadOptionalStr(dec)
    if key == "choices":
      return _firstChoiceObjectFieldContent(dec, "message")
    dec.skipValue()
  return ""


def _responsesDelta(rawJson: str) -> str:
  dec: JsonDecoder = new.fromText(rawJson)
  typ: str = ""
  delta: str = ""
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == "type":
      typ = _loadOptionalStr(dec)
    elif key == "delta":
      delta = _loadOptionalStr(dec)
    else:
      dec.skipValue()
  if typ == "response.output_text.delta":
    return delta
  if not typ and delta:
    return delta
  return ""


def _responsesCompletedId(rawJson: str) -> str:
  dec: JsonDecoder = new.fromText(rawJson)
  typ: str = ""
  rid: str = ""
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == "type":
      typ = _loadOptionalStr(dec)
    elif key == "response":
      rid = _objectStringField(dec, "id")
    else:
      dec.skipValue()
  if typ == "response.completed":
    return rid
  return ""


def _deltaContent(rawJson: str) -> str:
  dec: JsonDecoder = new.fromText(rawJson)
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    if key == "choices":
      return _firstChoiceObjectFieldContent(dec, "delta")
    dec.skipValue()
  return ""


def _iterSseTokens(text: str) -> GeneratorType[str, None, None]:
  lines: list[str] = text.splitLines()
  for line in lines:
    if line.startsWith("data: "):
      payload: str = line[6:]
      if payload == "[DONE]":
        return
      token: str = _deltaContent(payload)
      if token:
        yield token


def _iterResponsesSseTokens(text: str) -> GeneratorType[str, None, None]:
  lines: list[str] = text.splitLines()
  for line in lines:
    if line.startsWith("data: "):
      payload: str = line[6:]
      if payload == "[DONE]":
        return
      token: str = _responsesDelta(payload)
      if token:
        yield token


def _raiseForStatusCode(status: int) -> None:
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
def _statusOk(status: int) -> bool:
  return status >= 200 and status < 300


@immutable
def _shortErrorBody(body: str) -> str:
  text: str = body.replace("\r", " ")
  text = text.replace("\n", " ")
  if len(text) > 512:
    return text[:512]
  return text


@immutable
def _statusErrorText(status: int, body: str) -> str:
  out: str = f"HTTP {status} {reasonPhrase(status)}"
  detail: str = _shortErrorBody(body)
  if detail:
    out = f"{out}: {detail}"
  return out


@immutable
def _responseErrorText(resp: ClientResponse) -> str:
  return _statusErrorText(resp.status, resp.text())


def _streamErrorText(resp: ClientStreamResponse) -> str:
  return _statusErrorText(resp.status, resp.text())


def _raiseForStatus(resp: ClientResponse) -> None:
  _raiseForStatusCode(resp.status)


def _raiseForStreamStatus(resp: ClientStreamResponse) -> None:
  _raiseForStatusCode(resp.status)


@refcount
class _OpenAIState:
  """``OpenAI`` / ``Conversation`` 共享状态；生成器复制客户端时仍能回写错误信息。"""

  lastError: str = ""


@copyable
@dataclass(eq=False, repr=False)
class Conversation:
  """长对话客户端；方法名保持 ``chat`` / ``chatStream``。"""

  apiKey: str = ""
  baseUrl: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  defaultHeaders: dict[str, str] @optional = {}
  model: str = ""
  system: str = ""
  _state: _OpenAIState @optional = new()
  messages: list[OpenAIMessage] @optional = []
  summary: str = ""
  lastResponseId: str = ""
  maxHistoryChars: int = 12000
  compressTargetChars: int = 4000
  mcps: list[McpBase] @optional = []

  def __post_init__(self):
    if _looksLikeUrl(self.apiKey) and not _looksLikeUrl(self.baseUrl):
      oldKey: str = self.apiKey
      self.apiKey = self.baseUrl
      self.baseUrl = oldKey
    self.baseUrl = _normalizeBaseUrl(self.baseUrl)

  @property
  def lastError(self) -> str:
    return self._state.lastError

  @property.setter
  def lastError(self, value: str) -> None:
    self._state.lastError = value

  def useState(self, state: _OpenAIState) -> None:
    self._state = state

  def addMcp(self, mcp: McpBase) -> None:
    self.mcps.append(mcp)

  def clearMcp(self) -> None:
    self.mcps.clear()

  def callMcp(self, label: str, argsJson: str) -> str:
    for mcp in self.mcps:
      if mcp.label == label:
        return mcp.call(argsJson)
    raise ToolCallError()
    return ""

  def historyChars(self) -> int:
    total: int = len(self.system) + len(self.summary)
    for msg in self.messages:
      total += len(msg.role) + len(msg.content) + 2
    return total

  def compress(self) -> None:
    n: int = len(self.messages)
    if n <= 4:
      return
    keepFrom: int = n - 4
    old: str = self.summary
    for i in range(keepFrom):
      msg: OpenAIMessage = self.messages[i]
      line: str = f"{msg.role}: {msg.content}\n"
      old += line
    if len(old) > self.compressTargetChars:
      old = old[len(old) - self.compressTargetChars :]
    recent: list[OpenAIMessage] = []
    for i in range(keepFrom, n):
      recent.append(self.messages[i])
    self.summary = old
    self.messages = recent

  def _maybeCompress(self) -> None:
    if self.historyChars() > self.maxHistoryChars:
      self.compress()

  def _options(self, body: str) -> RequestOptions:
    return _requestOptions(self.apiKey, self.defaultHeaders, body, self.timeout)

  def chat(self, message: str, maxTokens: int = 0, temperature: float = -1.0) -> str:
    self.lastError = ""
    self._maybeCompress()
    body: str = _buildResponsesBody(
      self.model,
      self.system,
      self.summary,
      self.messages,
      message,
      self.lastResponseId,
      self.mcps,
      maxTokens,
      temperature,
      False,
    )
    opts: RequestOptions = self._options(body)
    session: ClientSession = new()
    resp: ClientResponse = session.requestOptions("POST", _responsesEndpoint(self.baseUrl), opts)
    if not _statusOk(resp.status):
      self.lastError = _responseErrorText(resp)
    _raiseForStatus(resp)
    raw: str = resp.text()
    text: str = _responseText(raw)
    rid: str = _responseId(raw)
    if rid:
      self.lastResponseId = rid
    userMsg: OpenAIMessage = new("user", message)
    assistantMsg: OpenAIMessage = new("assistant", text)
    self.messages.append(userMsg)
    self.messages.append(assistantMsg)
    self._maybeCompress()
    return text

  def chatStream(self, message: str, maxTokens: int = 0, temperature: float = -1.0) -> GeneratorType[str, None, None]:
    self.lastError = ""
    self._maybeCompress()
    body: str = _buildResponsesBody(
      self.model,
      self.system,
      self.summary,
      self.messages,
      message,
      self.lastResponseId,
      self.mcps,
      maxTokens,
      temperature,
      True,
    )
    opts: RequestOptions = self._options(body)
    session: ClientSession = new()
    resp: ClientStreamResponse = session.streamOptions("POST", _responsesEndpoint(self.baseUrl), opts)
    if not _statusOk(resp.status):
      self.lastError = _streamErrorText(resp)
    _raiseForStreamStatus(resp)
    text: str = ""
    rid: str = ""
    while True:
      line: str = resp.readLine()
      if line.startsWith("data: "):
        payload: str = line[6:]
        if payload == "[DONE]":
          resp.close()
          userMsg: OpenAIMessage = new("user", message)
          assistantMsg: OpenAIMessage = new("assistant", text)
          self.messages.append(userMsg)
          self.messages.append(assistantMsg)
          if rid:
            self.lastResponseId = rid
          self._maybeCompress()
          return
        doneId: str = _responsesCompletedId(payload)
        if doneId:
          rid = doneId
        token: str = _responsesDelta(payload)
        if token:
          text += token
          yield token


@copyable
@dataclass(eq=False, repr=False)
class OpenAI:
  """最简 OpenAI-compatible 聊天客户端。"""

  apiKey: str = ""
  baseUrl: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  defaultHeaders: dict[str, str] @optional = {}
  _state: _OpenAIState @optional = new()

  def __post_init__(self):
    if _looksLikeUrl(self.apiKey) and not _looksLikeUrl(self.baseUrl):
      oldKey: str = self.apiKey
      self.apiKey = self.baseUrl
      self.baseUrl = oldKey
    self.baseUrl = _normalizeBaseUrl(self.baseUrl)

  @property
  def lastError(self) -> str:
    return self._state.lastError

  @property.setter
  def lastError(self, value: str) -> None:
    self._state.lastError = value

  def conversation(
    self,
    model: str,
    system: str = "",
    maxHistoryChars: int = 12000,
    compressTargetChars: int = 4000,
  ) -> Conversation:
    conv: Conversation = new(
      apiKey=self.apiKey,
      baseUrl=self.baseUrl,
      timeout=self.timeout,
      defaultHeaders={},
    )
    for k in self.defaultHeaders:
      conv.defaultHeaders[k] = self.defaultHeaders[k]
    conv.useState(self._state)
    conv.model = model
    conv.system = system
    conv.maxHistoryChars = maxHistoryChars
    conv.compressTargetChars = compressTargetChars
    return conv

  def chat(
    self,
    model: str,
    message: str,
    system: str = "",
    maxTokens: int = 0,
    temperature: float = -1.0,
  ) -> str:
    self.lastError = ""
    body: str = _buildChatBody(model, message, system, maxTokens, temperature, False)
    opts: RequestOptions = _requestOptions(self.apiKey, self.defaultHeaders, body, self.timeout)
    session: ClientSession = new()
    resp: ClientResponse = session.requestOptions("POST", _endpoint(self.baseUrl), opts)
    if not _statusOk(resp.status):
      self.lastError = _responseErrorText(resp)
    _raiseForStatus(resp)
    return _chatContent(resp.text())

  def chatStream(
    self,
    model: str,
    message: str,
    system: str = "",
    maxTokens: int = 0,
    temperature: float = -1.0,
  ) -> GeneratorType[str, None, None]:
    self.lastError = ""
    body: str = _buildChatBody(model, message, system, maxTokens, temperature, True)
    opts: RequestOptions = _requestOptions(self.apiKey, self.defaultHeaders, body, self.timeout)
    session: ClientSession = new()
    resp: ClientStreamResponse = session.streamOptions("POST", _endpoint(self.baseUrl), opts)
    if not _statusOk(resp.status):
      self.lastError = _streamErrorText(resp)
    _raiseForStreamStatus(resp)
    while True:
      line: str = resp.readLine()
      if line.startsWith("data: "):
        payload: str = line[6:]
        if payload == "[DONE]":
          resp.close()
          return
        token: str = _deltaContent(payload)
        if token:
          yield token


@copyable
@dataclass(eq=False, repr=False)
class AsyncOpenAI:
  """最简异步 OpenAI-compatible 聊天客户端。"""

  apiKey: str = ""
  baseUrl: str = "https://api.openai.com/v1"
  timeout: float = 60.0
  defaultHeaders: dict[str, str] @optional = {}
  _state: _OpenAIState @optional = new()

  def __post_init__(self):
    if _looksLikeUrl(self.apiKey) and not _looksLikeUrl(self.baseUrl):
      oldKey: str = self.apiKey
      self.apiKey = self.baseUrl
      self.baseUrl = oldKey
    self.baseUrl = _normalizeBaseUrl(self.baseUrl)

  @property
  def lastError(self) -> str:
    return self._state.lastError

  @property.setter
  def lastError(self, value: str) -> None:
    self._state.lastError = value

  async def chat(
    self,
    model: str,
    message: str,
    system: str = "",
    maxTokens: int = 0,
    temperature: float = -1.0,
  ) -> str:
    self.lastError = ""
    body: str = _buildChatBody(model, message, system, maxTokens, temperature, False)
    opts: RequestOptions = _requestOptions(self.apiKey, self.defaultHeaders, body, self.timeout)
    session: AsyncClientSession = new()
    resp: ClientResponse = await session.requestOptions("POST", _endpoint(self.baseUrl), opts)
    if not _statusOk(resp.status):
      self.lastError = _responseErrorText(resp)
    _raiseForStatus(resp)
    return _chatContent(resp.text())
