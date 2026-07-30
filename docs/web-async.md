# py2cpp.web 异步接口设计

## 目标

`py2cpp.web` 的异步接口基于真正的 non-blocking socket，而不是把同步 HTTP 包进 `Task.run_thread()`。异步接口与同步接口放在同一模块文件中：

- `py2cpp.web.socket`
- `py2cpp.web.stream`
- `py2cpp.web.http`
- `py2cpp.web.client`
- `py2cpp.web.server`

不新增 `py2cpp.web.async_*` 文件。

## 底层机制

`TcpSocket` 保留原有同步 API，并新增 non-blocking 叶子能力：

- `set_blocking(blocking)`
- `connect_ex(host, port)`
- `finish_connect()`
- `accept_nonblocking()`
- `send_range_nonblocking(buf, start, end)`
- `recv_nonblocking(buf, cap)`
- `fileno()`

`Task` 调度器新增：

- `Task.wait_read(handle)`
- `Task.wait_write(handle)`

第一版 readiness 后端使用 `select()` 零超时轮询。Windows 下用 WinSock `select()`，POSIX 下用 fd `select()`。后续可以在不改变上层 API 的前提下升级为 IOCP / epoll / kqueue。

## 对外 API

### socket

`AsyncTcpSocket` 是 `TcpSocket` 的协作式异步包装：

- `await sock.connect(host, port)`
- `await sock.accept()`
- `await sock.recv(buf, cap)`
- `await sock.send_all(data)`
- `bind()` / `listen()` / `close()`

### stream

`AsyncStreamReader` / `AsyncStreamWriter` 镜像同步 `StreamReader` / `StreamWriter`：

- `await reader.readexactly(n)`
- `await reader.readuntil(sep)`
- `await writer.write(data)`
- `await writer.drain()`

### HTTP

HTTP 解析仍是纯 Python 组合逻辑：

- `await Request.read_async(reader)`
- `await ClientResponse.read_async(reader)`
- `await response.write_async(writer)`

### client / server

新增：

- `AsyncClientSession`
- `AsyncServer`
- `AsyncServerMixin`

`AsyncServer.serve_n(host, port, count)` 用于测试或嵌入式驱动；`serve_forever(host, port)` 用于常驻服务循环。

## 当前边界

- 当前仅支持 HTTP/1.1 短连接模型，和同步 `ClientSession` / `Server` 一致。
- 当前 socket readiness 是 select-based，不是 OS 专用高性能事件循环。
- 当前没有 TLS、连接池、keep-alive、chunked transfer。
- 当前 async server 按连接顺序处理；后续可在 `serve_forever` 内用 `Task.create()` 并发处理连接。
