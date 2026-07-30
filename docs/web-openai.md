# py2cpp.web.openai 最简接口方案

## 目标

`py2cpp.web.openai` 不做完整 OpenAI Python SDK 复刻，只提供足够直接的最小聊天接口：

```python
client: OpenAI = new(api_key="sk-test", base_url="http://127.0.0.1:18141/v1")
text: str = client.chat("gpt-test", "ping")

for token in client.chat_stream("gpt-test", "ping"):
  print(token)
```

这次不保留 `client.responses.create(...)`、`client.chat.completions.create(...)`、`OpenAIResponse`、`ChatCompletion`、资源类和异步客户端等过度封装。

## 当前范围

第一阶段实现：

- `OpenAI`
- `OpenAI.chat(model, message, system="", max_tokens=0, temperature=-1.0) -> str`
- `OpenAI.chat_stream(model, message, system="", max_tokens=0, temperature=-1.0) -> Iterator[str]`
- API key、`base_url`、timeout、默认 headers
- JSON 请求与响应解析
- 基础错误类型
- 本地 fake server 测试

第一阶段暂不实现：

- TLS/HTTPS。当前 `py2cpp.web.ClientSession` 只建立普通 TCP 连接；真实 `https://api.openai.com/v1` 需要后续 TLS。
- SDK 资源树。
- tool calling、multimodal、文件上传、分页等完整 API。
- 异步 `AsyncOpenAI`。
- 自动重试。

## HTTP 映射

`chat()` 使用 OpenAI-compatible Chat Completions 路径：

```text
POST {base_url}/chat/completions
```

请求体：

```json
{
  "model": "gpt-test",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "ping"}
  ],
  "max_tokens": 128,
  "temperature": 0.2
}
```

`system` 非空才写入 system message；`max_tokens > 0`、`temperature >= 0.0` 时才写入对应字段。

返回解析：

- 优先读取 `choices[0].message.content`
- 兼容读取顶层 `"content"`

## streaming

`chat_stream()` 使用同一路径，并在请求体加入：

```json
"stream": true
```

第一阶段按固定 `Content-Length` 响应体解析 SSE 文本：

```text
data: {"choices":[{"delta":{"content":"he"}}]}

data: {"choices":[{"delta":{"content":"llo"}}]}

data: [DONE]
```

每个 `delta.content` 作为一个 token yield。后续如果 `py2cpp.web` 支持真正增量读取和 chunked transfer，再把这里改成真正边读边产出。

## 错误模型

保留基础异常：

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

状态码映射：

- `400` → `BadRequestError`
- `401` → `AuthenticationError`
- `403` → `PermissionDeniedError`
- `404` → `NotFoundError`
- `429` → `RateLimitError`
- `>= 500` → `InternalServerError`
- 其它非 2xx → `APIError`

## 验证

不访问真实 OpenAI API，只使用本地 fake server：

```bat
python main.py py2cpp\__init__.py -o generated --no-main
build.bat web/test_openai --seq
run.bat web/test_openai
```

