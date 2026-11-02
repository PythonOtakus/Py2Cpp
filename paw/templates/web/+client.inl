PY2CPP_IGNORE
#include "py2cpp/web/client.h"
#include "py2cpp/web/http.h"
#include "py2cpp/web/stream.h"
#include "py2cpp/text/bytes.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/array.h"
#include "py2cpp/core/exceptions.h"
PY2CPP_END

#include <string>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows.h"
#include "ffi/windows/winhttp.h"
#pragma comment(lib, "winhttp.lib")
#endif

static void _web_client_throw_oserror()
{
  throw PY2CPP_TYPE(PyOSError)();
}

static std::string _web_client_pybytes_to_string(const PyBytes& b)
{
  std::string out;
  PyInt n = b.__len__();
  if (n <= 0)
  {
    return out;
  }
  out.resize((size_t)n);
  for (PyInt i = 0; i < n; ++i)
  {
    out[(size_t)i] = (char)b.__getitem__(i);
  }
  return out;
}

static PyBytes _web_client_string_to_pybytes(const std::string& s)
{
  PyArray<PyByte> buf((PyInt)s.size());
  for (PyInt i = 0; i < (PyInt)s.size(); ++i)
  {
    buf.__setitem__(i, PyByte((unsigned char)s[(size_t)i]));
  }
  return PyBytes(buf);
}

static std::string _web_client_pystr_to_utf8(const PyStr& s)
{
  int n = s.__len__();
  if (n <= 0)
  {
    return std::string();
  }
  std::string buf;
  buf.resize((size_t)n + 1u, '\0');
  s.copyToSpanUtf8(PySpan<PyByte>((PyByte*)buf.data(), (PyInt)buf.size(), 1));
  return std::string(buf.c_str());
}

#ifdef _WIN32
static std::wstring _web_client_utf8_to_wide(const std::string& s)
{
  if (s.empty())
  {
    return std::wstring();
  }
  int need = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
  if (need <= 0)
  {
    need = MultiByteToWideChar(CP_ACP, 0, s.c_str(), (int)s.size(), nullptr, 0);
  }
  if (need <= 0)
  {
    _web_client_throw_oserror();
  }
  std::wstring out((size_t)need, L'\0');
  int wrote = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &out[0], need);
  if (wrote <= 0)
  {
    wrote = MultiByteToWideChar(CP_ACP, 0, s.c_str(), (int)s.size(), &out[0], need);
  }
  if (wrote <= 0)
  {
    _web_client_throw_oserror();
  }
  return out;
}

static std::string _web_client_wide_to_utf8(const wchar_t* ws)
{
  if (!ws)
  {
    return std::string();
  }
  int need = WideCharToMultiByte(CP_UTF8, 0, ws, -1, nullptr, 0, nullptr, nullptr);
  if (need <= 1)
  {
    return std::string();
  }
  std::string out((size_t)need - 1u, '\0');
  WideCharToMultiByte(CP_UTF8, 0, ws, -1, &out[0], need, nullptr, nullptr);
  return out;
}

static bool _web_client_header_skip(const std::string& key)
{
  return key == "Host" || key == "host" ||
         key == "Connection" || key == "connection" ||
         key == "Content-Length" || key == "content-length";
}

static std::string _web_client_headers_from_payload(const std::string& payload)
{
  size_t head_end = payload.find("\r\n\r\n");
  if (head_end == std::string::npos)
  {
    return std::string();
  }
  size_t line_start = payload.find("\r\n");
  if (line_start == std::string::npos || line_start >= head_end)
  {
    return std::string();
  }
  line_start += 2;
  std::string out;
  while (line_start < head_end)
  {
    size_t line_end = payload.find("\r\n", line_start);
    if (line_end == std::string::npos || line_end > head_end)
    {
      line_end = head_end;
    }
    std::string line = payload.substr(line_start, line_end - line_start);
    size_t colon = line.find(':');
    if (colon != std::string::npos)
    {
      std::string key = line.substr(0, colon);
      if (!_web_client_header_skip(key))
      {
        out += line;
        out += "\r\n";
      }
    }
    line_start = line_end + 2;
  }
  return out;
}

static std::string _web_client_body_from_payload(const std::string& payload)
{
  size_t head_end = payload.find("\r\n\r\n");
  if (head_end == std::string::npos)
  {
    return std::string();
  }
  return payload.substr(head_end + 4);
}

static void _web_client_parse_raw_headers(PyClientResponse& resp, const std::wstring& raw)
{
  size_t start = 0;
  while (start < raw.size())
  {
    size_t end = raw.find(L"\r\n", start);
    if (end == std::wstring::npos)
    {
      end = raw.size();
    }
    if (end > start)
    {
      std::wstring line = raw.substr(start, end - start);
      size_t colon = line.find(L':');
      if (colon != std::wstring::npos)
      {
        std::wstring k = line.substr(0, colon);
        size_t val_start = colon + 1;
        while (val_start < line.size() && line[val_start] == L' ')
        {
          ++val_start;
        }
        std::wstring v = line.substr(val_start);
        resp.headers.__setitem__(
          PyStr(_web_client_wide_to_utf8(k.c_str()).c_str()),
          PyStr(_web_client_wide_to_utf8(v.c_str()).c_str()));
      }
    }
    start = end + 2;
  }
}

static PyClientResponse _web_client_https_request_winhttp(const PyStr& method, PyUrlData url, PyBytes payload, PyFloat timeout)
{
  std::string host_u8 = _web_client_pystr_to_utf8(url.host);
  std::string path_u8 = _web_client_pystr_to_utf8(url.path);
  std::string query_u8 = _web_client_pystr_to_utf8(url.query);
  if (!query_u8.empty())
  {
    path_u8 += "?";
    path_u8 += query_u8;
  }
  std::string method_u8 = _web_client_pystr_to_utf8(method);
  std::string payload_s = _web_client_pybytes_to_string(payload);
  std::string headers_s = _web_client_headers_from_payload(payload_s);
  std::string body_s = _web_client_body_from_payload(payload_s);

  std::wstring host_w = _web_client_utf8_to_wide(host_u8);
  std::wstring path_w = _web_client_utf8_to_wide(path_u8.empty() ? std::string("/") : path_u8);
  std::wstring method_w = _web_client_utf8_to_wide(method_u8);
  std::wstring headers_w = _web_client_utf8_to_wide(headers_s);

  HINTERNET session = WinHttpOpen(L"py2cpp.web/1.0",
                                  WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                  WINHTTP_NO_PROXY_NAME,
                                  WINHTTP_NO_PROXY_BYPASS,
                                  0);
  if (!session)
  {
    _web_client_throw_oserror();
  }
  if (timeout > 0.0f)
  {
    int ms = (int)(timeout * 1000.0f);
    WinHttpSetTimeouts(session, ms, ms, ms, ms);
  }

  HINTERNET connect = WinHttpConnect(session, host_w.c_str(), (INTERNET_PORT)url.port, 0);
  if (!connect)
  {
    WinHttpCloseHandle(session);
    _web_client_throw_oserror();
  }

  HINTERNET request = WinHttpOpenRequest(connect,
                                         method_w.c_str(),
                                         path_w.c_str(),
                                         nullptr,
                                         WINHTTP_NO_REFERER,
                                         WINHTTP_DEFAULT_ACCEPT_TYPES,
                                         WINHTTP_FLAG_SECURE);
  if (!request)
  {
    WinHttpCloseHandle(connect);
    WinHttpCloseHandle(session);
    _web_client_throw_oserror();
  }

  BOOL ok = WinHttpSendRequest(request,
                               headers_w.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : headers_w.c_str(),
                               headers_w.empty() ? 0 : (DWORD)-1L,
                               body_s.empty() ? WINHTTP_NO_REQUEST_DATA : (LPVOID)body_s.data(),
                               (DWORD)body_s.size(),
                               (DWORD)body_s.size(),
                               0);
  if (!ok || !WinHttpReceiveResponse(request, nullptr))
  {
    WinHttpCloseHandle(request);
    WinHttpCloseHandle(connect);
    WinHttpCloseHandle(session);
    _web_client_throw_oserror();
  }

  PyClientResponse resp = PyClientResponse();
  DWORD status = 0;
  DWORD status_len = sizeof(status);
  if (WinHttpQueryHeaders(request,
                          WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                          WINHTTP_HEADER_NAME_BY_INDEX,
                          &status,
                          &status_len,
                          WINHTTP_NO_HEADER_INDEX))
  {
    resp.status = (PyInt)status;
  }

  DWORD raw_len = 0;
  WinHttpQueryHeaders(request,
                      WINHTTP_QUERY_RAW_HEADERS_CRLF,
                      WINHTTP_HEADER_NAME_BY_INDEX,
                      nullptr,
                      &raw_len,
                      WINHTTP_NO_HEADER_INDEX);
  if (GetLastError() == ERROR_INSUFFICIENT_BUFFER && raw_len > 0)
  {
    std::wstring raw;
    raw.resize(raw_len / sizeof(wchar_t));
    if (WinHttpQueryHeaders(request,
                            WINHTTP_QUERY_RAW_HEADERS_CRLF,
                            WINHTTP_HEADER_NAME_BY_INDEX,
                            &raw[0],
                            &raw_len,
                            WINHTTP_NO_HEADER_INDEX))
    {
      _web_client_parse_raw_headers(resp, raw);
    }
  }

  std::string body;
  while (true)
  {
    DWORD avail = 0;
    if (!WinHttpQueryDataAvailable(request, &avail))
    {
      WinHttpCloseHandle(request);
      WinHttpCloseHandle(connect);
      WinHttpCloseHandle(session);
      _web_client_throw_oserror();
    }
    if (avail == 0)
    {
      break;
    }
    size_t old = body.size();
    body.resize(old + (size_t)avail);
    DWORD read = 0;
    if (!WinHttpReadData(request, &body[old], avail, &read))
    {
      WinHttpCloseHandle(request);
      WinHttpCloseHandle(connect);
      WinHttpCloseHandle(session);
      _web_client_throw_oserror();
    }
    body.resize(old + (size_t)read);
  }

  resp.body = _web_client_string_to_pybytes(body);
  WinHttpCloseHandle(request);
  WinHttpCloseHandle(connect);
  WinHttpCloseHandle(session);
  return resp;
}
#endif

PyClientResponse py2cpp::web::client::_httpsRequest(const PyStr& method, PyUrlData url, PyBytes payload, PyFloat timeout)
{
#ifdef _WIN32
  return _web_client_https_request_winhttp(method, url, payload, timeout);
#else
  _web_client_throw_oserror();
  return PyClientResponse();
#endif
}

PyClientStreamResponse py2cpp::web::client::_httpsStream(const PyStr& method, PyUrlData url, PyBytes payload, PyFloat timeout)
{
  PyClientResponse head = ::py2cpp::web::client::_httpsRequest(method, url, payload, timeout);
  if (head.headers.__contains__(PyStr("Transfer-Encoding")))
  {
    head.headers.__delitem__(PyStr("Transfer-Encoding"));
  }
  if (head.headers.__contains__(PyStr("transfer-encoding")))
  {
    head.headers.__delitem__(PyStr("transfer-encoding"));
  }
  PyStreamReader reader = PyStreamReader();
  reader.loadBytes(head.body);
  PyStreamWriter writer = PyStreamWriter::fromBuffer();
  return PyClientStreamResponse::fromHead(reader, writer, head);
}
