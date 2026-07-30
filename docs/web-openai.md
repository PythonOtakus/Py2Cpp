# py2cpp.web.openai 设计与实现计划

## 目标

`py2cpp.web.openai` 仍保持最简调用风格，不复刻完整 OpenAI Python SDK 资源树。

基础单轮接口继续保留：

```python
client: OpenAI = new(api_key="sk-test")
text: str = client.chat("gpt-test", "ping")

for token in client.chat_stream("gpt-test", "ping"):
  print(token)
```

新增长对话接口使用 `Conversation`，方法名仍是 `chat` / `chat_stream`：

```python
client: OpenAI = new(api_key="sk-test")
conv: Conversation = client.conversation("gpt-test", system="你是助手")

text1: str = conv.chat("第一轮问题")
text2: str = conv.chat("继续刚才的话题")

for token in conv.chat_stream("流式回答"):
  print(token)
```

异步接口继续保留：

```python
async_client: AsyncOpenAI = new(api_key="sk-test")
text: str = await async_client.chat("gpt-test", "ping")
```

`Conversation` 第一阶段先实现同步版本；异步长对话在 async stream 能力进一步稳定后补齐。`AsyncOpenAI.chat()` 遇到 `https://` 时复用通用 WinHTTP TLS request 路径。

## API 分层

### `OpenAI`

`OpenAI.chat(...)` 和 `OpenAI.chat_stream(...)` 继续走 OpenAI-compatible Chat Completions：

```text
POST {base_url}/chat/completions
```

这样保持与本地 fake server、OpenAI-compatible 服务、已有测试兼容。

### `Conversation`

`Conversation.chat(...)` 和 `Conversation.chat_stream(...)` 默认走 Responses API：

```text
POST {base_url}/responses
```

原因：

- 长对话需要 `previous_response_id` 这类服务端对话状态。
- MCP 调用属于工具调用能力，Responses API 更适合承载。
- 未来可自然扩展更多工具、结构化输出、审批流。

## TLS / HTTPS

`py2cpp.web` 必须支持真实 HTTPS，不能只依赖本地 HTTP fake server。

实现原则：

- TLS 放在通用 `py2cpp.web.client` / runtime 层，而不是写死到 `openai.py`。
- `ClientSession` 看到 `https://` 时自动走 TLS。
- `http://` 仍走现有 `TcpSocket`，保持本地 fake server 与现有测试稳定。
- Windows/MSVC 第一阶段使用 WinHTTP 原生 HTTPS；它提供系统证书校验、SNI、TLS 握手、请求发送、响应读取。
- 对外 API 不暴露 WinHTTP 细节。
- `ClientSession.stream_options()` 在 `https://` 下先由 WinHTTP 完整读取 TLS 响应体，再封装成 `ClientStreamResponse` 内存流；因此 OpenAI SSE 仍按 `for token in chat_stream(...)` 消费，但第一阶段不是网络句柄级逐块 yield。

新增内部接口：

```python
@native
def _https_request(method: str, url: UrlData, payload: bytes, timeout: float) -> ClientResponse: ...

@native
def _https_stream(method: str, url: UrlData, payload: bytes, timeout: float) -> ClientStreamResponse: ...
```

`RequestOptions.encode()` 仍负责生成 HTTP/1.1 request bytes；HTTPS native 层可以复用其中 headers/body，也可以直接从 `RequestOptions` 提取字段重新组包。第一阶段为了少侵入，优先传入已编码 payload，native 层解析 request line/header/body 后交给 WinHTTP。

## 长对话状态

新增：

```python
@copyable
class OpenAIMessage:
  role: str
  content: str

@refcount
class McpBase:
  label: str

  def append_tool(self, enc: JsonEncoder @ref) -> None: ...

  def call(self, args_json: str) -> str: ...

@refcount
class McpServer(McpBase):
  url: str
  require_approval: bool = False
  headers: dict[str, str] = {}

@refcount
class McpFuncCall(McpBase):
  name: str
  description: str
  parameters_json: str
  handler: Callable[[str], str]

@copyable
class Conversation:
  api_key: str
  base_url: str
  timeout: float
  default_headers: dict[str, str]
  model: str
  system: str
  messages: list[OpenAIMessage]
  summary: str
  last_response_id: str
  max_history_chars: int
  compress_target_chars: int
  mcps: list[McpBase]
```

字段含义：

- `messages`：本地最近消息窗口。
- `summary`：压缩后的旧上下文。
- `last_response_id`：Responses API 返回的 response id；后续请求带 `previous_response_id`。
- `max_history_chars`：超过该估算阈值触发压缩。
- `compress_target_chars`：压缩目标长度。
- `mcps`：统一的 MCP 工具列表，元素为 `McpBase`；`McpServer` 和 `McpFuncCall` 都通过 `@refcount` 多态保存。

## 对话压缩

压缩不依赖 tokenizer，第一阶段按字符数估算。

触发条件：

```python
if conv.history_chars() > conv.max_history_chars:
  conv.compress()
```

压缩策略：

1. 保留最近若干轮原文。
2. 旧消息合并成一段 `summary`。
3. 后续请求在 system 后追加 summary message。

第一阶段压缩方式采用“保守抽取式压缩”：

- 不调用模型另做摘要，避免压缩本身产生额外网络依赖。
- 旧消息按 `role: content` 拼接。
- 若超过 `compress_target_chars`，保留尾部窗口。

后续可加模型压缩：

```python
conv.compress_with_model(model="gpt-5-mini")
```

但不作为第一阶段默认行为。

## Responses 请求体

`Conversation.chat(message)` 生成：

```json
{
  "model": "gpt-test",
  "input": [
    {"role": "system", "content": "system..."},
    {"role": "system", "content": "Conversation summary:\n..."},
    {"role": "user", "content": "recent user..."},
    {"role": "assistant", "content": "recent assistant..."},
    {"role": "user", "content": "new message"}
  ],
  "previous_response_id": "resp_...",
  "tools": [
    {
      "type": "mcp",
      "server_label": "docs",
      "server_url": "https://example.com/mcp",
      "require_approval": "never"
    },
    {
      "type": "function",
      "name": "local_echo",
      "description": "本地函数工具",
      "parameters": "{}"
    }
  ],
  "stream": false
}
```

规则：

- `system` 非空才写 system。
- `summary` 非空才写 summary。
- `last_response_id` 非空才写 `previous_response_id`。
- `mcps` 非空才写 `tools`。
- `chat_stream()` 写 `"stream": true`。

## Responses 返回解析

需要支持两类响应：

### 非流式

优先解析：

- 顶层 `output_text`
- 或 `output[*].content[*].text`
- 同时读取顶层 `id` 更新 `last_response_id`

### 流式 SSE

至少识别：

- `response.output_text.delta`
- `response.completed`
- `response.failed`
- `response.output_item.done` / MCP tool 调用事件：第一阶段只记录，不暴露复杂对象

`Conversation.chat_stream()` 每个文本 delta 直接 `yield token`，最终更新 `last_response_id`。

## MCP 集成

第一阶段支持两类工具：

- `McpServer`：Remote MCP through Responses API。
- `McpFuncCall`：本地函数 MCP tool，安全持有 `Callable[[str], str]` handler；`call_mcp()` 按 `label` 查找并把 tool-call arguments JSON 传给 handler。

接口：

```python
server: McpServer = new()
server.label = "docs"
server.url = "https://example.com/mcp"
conv.add_mcp(server)

local: McpFuncCall = new()
local.label = "local"
local.name = "local_echo"
local.handler = lambda args_json: "{\"ok\":true}"
conv.add_mcp(local)

tool_result = conv.call_mcp("local", "{\"x\":1}")
conv.clear_mcp()
```

`require_approval` 映射：

- `False` → `"never"`
- `True` → `"always"`

后续可扩展：

- allowed tools
- headers
- approval 回调
- tool trace
- 将 Responses API 的 tool-call 事件自动分派到真正的 `McpFuncCall` handler

## 错误模型

保留：

```python
class OpenAIError(Exception): ...
class APIError(OpenAIError): ...
class BadRequestError(APIError): ...
class AuthenticationError(APIError): ...
class PermissionDeniedError(APIError): ...
class NotFoundError(APIError): ...
class RateLimitError(APIError): ...
class InternalServerError(APIError): ...
```

新增：

```python
class TLSUnavailableError(OpenAIError): ...
class ToolCallError(OpenAIError): ...
```

`TLSUnavailableError` 保留给 OpenAI 层后续细分错误使用。当前通用 web TLS backend 在 Windows/MSVC 下走 WinHTTP；其它平台暂抛通用 `OSError`。

## 测试

不访问真实 OpenAI API，默认仍用本地 fake server：

```bat
python main.py py2cpp\__init__.py -o generated --no-main
build.bat web/test_openai --seq
run.bat web/test_openai
```

新增测试：

- `_build_responses_body`：长对话 messages / summary / previous_response_id / MCP tools。
- `_response_text` / `_response_id`：Responses 非流式解析。
- `_responses_delta`：Responses SSE delta 解析。
- `Conversation.chat`：本地 HTTP fake server 验证多轮状态与压缩。
- `Conversation.chat_stream`：本地 HTTP fake server 验证 SSE。
- HTTPS/TLS：用 native 层单元或可控地址测试 URL 分流；真实网络测试不放入默认 run。

## 实现顺序

1. 文档更新。
2. 通用 HTTPS/TLS：`ClientSession` 在 `https://` 下走 WinHTTP native。
3. `openai.py` 增加 Responses body builder 和 parser。
4. `Conversation.chat`。
5. `Conversation.chat_stream`。
6. MCP tools JSON。
7. 压缩策略。
8. fake server 测试与 build/run 验证。
