PY2CPP_IGNORE
#include "py2cpp/sql/sqlite.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/list.h"
#include "py2cpp/core/optional.h"
#include "ffi/sqlite/sqlite3.h"
PY2CPP_END

#include <stdint.h>
#include <string.h>
// 尖括号：勿用引号，否则 MSVC 会经已打开的 ``ffi/sqlite/sqlite3.h`` 目录命中生成头（guard 已定义 → C API 被跳过）
#include <sqlite3.h>
// C 宏与 FFI 命名空间内 ``static PyInt SQLITE_*`` 同名；统一走 ``ffi_sql::``，避免宏被其它头清掉后裸名未声明
#ifdef SQLITE_OK
#undef SQLITE_OK
#endif
#ifdef SQLITE_ROW
#undef SQLITE_ROW
#endif
#ifdef SQLITE_DONE
#undef SQLITE_DONE
#endif

namespace ffi_sql = ::ffi::sqlite::sqlite3;

static void _sql_throw_operational()
{
  throw OperationalError();
}

static PyStr _sql_cbuf_to_pystr(const char* buf, int n)
{
  if ((!buf) || (n <= 0))
  {
    return PyStr("");
  }
  PY2CPP_TYPE(PyArray)<PyChar> codes(n);
  int i = 0;
  while ((i < n))
  {
    codes.__setitem__(i, (PyChar)(unsigned char)buf[i]);
    i = (i + 1);
  }
  return PyStr(codes);
}

static void _sql_bind_int_list(PyUInt64 stmt, const PY2CPP_TYPE(PyList)<PyInt>& params)
{
  int n = params.__len__();
  int i = 0;
  while ((i < n))
  {
    int v = params.__getitem__(i);
    if (ffi_sql::sqlite3_bind_int(stmt, i + 1, v) != ffi_sql::SQLITE_OK)
    {
      _sql_throw_operational();
    }
    i = (i + 1);
  }
}

static PyBool _sql_stmt_is_select(const char* sql)
{
  if (!sql)
  {
    return false;
  }
  const char* p = sql;
  while ((*p == ' ') || (*p == '\t') || (*p == '\n') || (*p == '\r'))
  {
    p = (p + 1);
  }
  if ((p[0] == 'S' || p[0] == 's') &&
      (p[1] == 'E' || p[1] == 'e') &&
      (p[2] == 'L' || p[2] == 'l') &&
      (p[3] == 'E' || p[3] == 'e') &&
      (p[4] == 'C' || p[4] == 'c') &&
      (p[5] == 'T' || p[5] == 't'))
      {
    return true;
  }
  return false;
}

static void _sql_pystr_to_cbuf(const PyStr& s, char* buf, int cap)
{
  int n = s.__len__();
  if (n >= cap)
  {
    n = cap - 1;
  }
  int i = 0;
  while ((i < n))
  {
    buf[i] = (char)(unsigned char)pychar_to_byte(s.__getitem__(i));
    i = (i + 1);
  }
  buf[n] = '\0';
}

static PyTuple<PyInt> _sql_row_int1(PyUInt64 stmt)
{
  int v = ffi_sql::sqlite3_column_int(stmt, 0);
  return PyTuple<PyInt>(v);
}


PySqliteConnection::PySqliteConnection()
{
  _db = 0;
  _closed = true;
}

PySqliteConnection::PySqliteConnection(PySqliteConnection&& other)
{
  _db = other._db;
  _closed = other._closed;
  other._db = 0;
  other._closed = true;
}

PySqliteConnection& PySqliteConnection::operator=(PySqliteConnection&& other)
{
  if (this != &other)
  {
    if ((_db != 0) && (!_closed))
    {
      ffi_sql::sqlite3_close(_db);
    }
    _db = other._db;
    _closed = other._closed;
    other._db = 0;
    other._closed = true;
  }
  return *this;
}

PySqliteConnection::~PySqliteConnection()
{
  if ((_db != 0) && (!_closed))
  {
    ffi_sql::sqlite3_close(_db);
    _db = 0;
    _closed = true;
  }
}

void PySqliteConnection::_open_impl(PyStr path)
{
  if ((_db != 0) && (!_closed))
  {
    ffi_sql::sqlite3_close(_db);
    _db = 0;
  }
  char pbuf[4096];
  _sql_pystr_to_cbuf(path, pbuf, (int)sizeof(pbuf));
  PyUInt64 db = 0;
  if (ffi_sql::sqlite3_open(pbuf, &db) != ffi_sql::SQLITE_OK)
  {
    if (db)
    {
      ffi_sql::sqlite3_close(db);
    }
    _sql_throw_operational();
  }
  _db = db;
  _closed = false;
}

void PySqliteConnection::close()
{
  if ((_db != 0) && (!_closed))
  {
    ffi_sql::sqlite3_close(_db);
    _db = 0;
  }
  _closed = true;
}

void PySqliteConnection::commit()
{
  if ((_closed) || (_db == 0))
  {
    _sql_throw_operational();
  }
  if (ffi_sql::sqlite3_get_autocommit(_db))
  {
    return;
  }
  c_str err = nullptr;
  if (ffi_sql::sqlite3_exec(_db, "COMMIT", 0, 0, &err) != ffi_sql::SQLITE_OK)
  {
    if (err)
    {
      ffi_sql::sqlite3_free((PyUPtr)(uintptr_t)err);
    }
    _sql_throw_operational();
  }
}

void PySqliteConnection::rollback()
{
  if ((_closed) || (_db == 0))
  {
    _sql_throw_operational();
  }
  if (ffi_sql::sqlite3_get_autocommit(_db))
  {
    return;
  }
  c_str err = nullptr;
  if (ffi_sql::sqlite3_exec(_db, "ROLLBACK", 0, 0, &err) != ffi_sql::SQLITE_OK)
  {
    if (err)
    {
      ffi_sql::sqlite3_free((PyUPtr)(uintptr_t)err);
    }
    _sql_throw_operational();
  }
}

PySqliteConnection PySqliteConnection::open(PyStr path)
{
  PySqliteConnection conn;
  conn._open_impl(path);
  return conn;
}

PySqliteCursor PySqliteConnection::execute(PY2CPP_TYPE(PyStr) sql, const PY2CPP_TYPE(PyList)<PyInt>& params)
{
  if ((_closed) || (_db == 0))
  {
    _sql_throw_operational();
  }
  char sbuf[8192];
  _sql_pystr_to_cbuf(sql, sbuf, (int)sizeof(sbuf));
  PyUInt64 stmt = 0;
  if (ffi_sql::sqlite3_prepare_v2(_db, sbuf, -1, &stmt, nullptr) != ffi_sql::SQLITE_OK)
  {
    _sql_throw_operational();
  }
  _sql_bind_int_list(stmt, params);
  PyBool is_sel = _sql_stmt_is_select(sbuf);
  if (!is_sel)
  {
    int rc = ffi_sql::sqlite3_step(stmt);
    if ((rc != ffi_sql::SQLITE_DONE) && (rc != ffi_sql::SQLITE_ROW))
    {
      ffi_sql::sqlite3_finalize(stmt);
      _sql_throw_operational();
    }
    ffi_sql::sqlite3_finalize(stmt);
    return PySqliteCursor((unsigned long long)0);
  }
  return PySqliteCursor(stmt);
}

void PySqliteConnection::executemany(PY2CPP_TYPE(PyStr) sql, const PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyList)<PyInt>>& seq)
{
  int n = seq.__len__();
  int i = 0;
  while ((i < n))
  {
    const PY2CPP_TYPE(PyList)<PyInt>& row = seq.__getitem__(i);
    this->execute(sql, row);
    i = (i + 1);
  }
}

PySqliteCursor::PySqliteCursor(unsigned long long stmt)
{
  _stmt = stmt;
  _done = (stmt == 0);
}

PySqliteCursor::PySqliteCursor(PySqliteCursor&& other)
{
  _stmt = other._stmt;
  _done = other._done;
  other._stmt = 0;
  other._done = true;
}

PySqliteCursor& PySqliteCursor::operator=(PySqliteCursor&& other)
{
  if (this != &other)
  {
    if (_stmt != 0)
    {
      ffi_sql::sqlite3_finalize(_stmt);
    }
    _stmt = other._stmt;
    _done = other._done;
    other._stmt = 0;
    other._done = true;
  }
  return *this;
}

PySqliteCursor::~PySqliteCursor()
{
  if (_stmt != 0)
  {
    ffi_sql::sqlite3_finalize(_stmt);
    _stmt = 0;
  }
}

PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>> PySqliteCursor::fetchone()
{
  if ((_done) || (_stmt == 0))
  {
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
  }
  int rc = ffi_sql::sqlite3_step(_stmt);
  if (rc == ffi_sql::SQLITE_ROW)
  {
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::Some(_sql_row_int1(_stmt));
  }
  if (rc == ffi_sql::SQLITE_DONE)
  {
    _done = true;
    ffi_sql::sqlite3_finalize(_stmt);
    _stmt = 0;
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
  }
  _sql_throw_operational();
  return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
}

PY2CPP_TYPE(PyList)<PyTuple<PyInt>> PySqliteCursor::fetchall()
{
  PY2CPP_TYPE(PyList)<PyTuple<PyInt>> out;
  if ((_done) || (_stmt == 0))
  {
    return out;
  }
  while (true)
  {
    int rc = ffi_sql::sqlite3_step(_stmt);
    if (rc == ffi_sql::SQLITE_ROW)
    {
      out.append(_sql_row_int1(_stmt));
      continue;
    }
    if (rc == ffi_sql::SQLITE_DONE)
    {
      break;
    }
    _sql_throw_operational();
  }
  _done = true;
  ffi_sql::sqlite3_finalize(_stmt);
  _stmt = 0;
  return out;
}

PY2CPP_BEGIN_SCOPE

PySqliteConnection connect(const PyStr& path)
{
  return PySqliteConnection::open(path);
}

PY2CPP_END_SCOPE
