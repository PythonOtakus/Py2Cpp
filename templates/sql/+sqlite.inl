PY2CPP_IGNORE
#include "py2cpp/sql/sqlite.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/list.h"
#include "py2cpp/core/optional.h"
#include "ffi/sqlite/sqlite3.h"
PY2CPP_END

// 第三方 C 头仅由 ffi glue（``generated/runtime/ffi/sqlite/sqlite3.*``）``#include <sqlite3.h>``；
// 业务模板禁止直导。``stdint``/``string`` 暂仍直导，待 ``ffi/crt/*`` 叶子迁移后去掉。
#include <cstdint>
#include "ffi/crt/string.h"
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
  throw PyOperationalError();
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

static void _sql_bind_int_list(struct sqlite3_stmt* stmt, const PY2CPP_TYPE(PyList)<PyInt>& params)
{
  int n = params.__len__();
  int i = 0;
  while ((i < n))
  {
    int v = params.__getitem__(i);
    if (ffi_sql::pyiSqlite3BindInt(stmt, i + 1, v) != ffi_sql::PyiSqliteOk)
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

static PyTuple<PyInt> _sql_row_int1(struct sqlite3_stmt* stmt)
{
  int v = ffi_sql::pyiSqlite3ColumnInt(stmt, 0);
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
      ffi_sql::pyiSqlite3Close(_db);
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
    ffi_sql::pyiSqlite3Close(_db);
    _db = 0;
    _closed = true;
  }
}

void PySqliteConnection::_openImpl(PyStr path)
{
  if ((_db != 0) && (!_closed))
  {
    ffi_sql::pyiSqlite3Close(_db);
    _db = 0;
  }
  char pbuf[4096];
  _sql_pystr_to_cbuf(path, pbuf, (int)sizeof(pbuf));
  struct sqlite3* db = nullptr;
  if (ffi_sql::pyiSqlite3Open(pbuf, &db) != ffi_sql::PyiSqliteOk)
  {
    if (db)
    {
      ffi_sql::pyiSqlite3Close(db);
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
    ffi_sql::pyiSqlite3Close(_db);
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
  if (ffi_sql::pyiSqlite3GetAutocommit(_db))
  {
    return;
  }
  CStr err = nullptr;
  if (ffi_sql::pyiSqlite3Exec(_db, "COMMIT", 0, 0, &err) != ffi_sql::PyiSqliteOk)
  {
    if (err)
    {
      ffi_sql::pyiSqlite3Free((PyUPtr)(uintptr_t)err);
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
  if (ffi_sql::pyiSqlite3GetAutocommit(_db))
  {
    return;
  }
  CStr err = nullptr;
  if (ffi_sql::pyiSqlite3Exec(_db, "ROLLBACK", 0, 0, &err) != ffi_sql::PyiSqliteOk)
  {
    if (err)
    {
      ffi_sql::pyiSqlite3Free((PyUPtr)(uintptr_t)err);
    }
    _sql_throw_operational();
  }
}

PySqliteConnection PySqliteConnection::open(PyStr path)
{
  PySqliteConnection conn;
  conn._openImpl(path);
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
  struct sqlite3_stmt* stmt = 0;
  if (ffi_sql::pyiSqlite3PrepareV2(_db, sbuf, -1, &stmt, nullptr) != ffi_sql::PyiSqliteOk)
  {
    _sql_throw_operational();
  }
  _sql_bind_int_list(stmt, params);
  PyBool is_sel = _sql_stmt_is_select(sbuf);
  if (!is_sel)
  {
    int rc = ffi_sql::pyiSqlite3Step(stmt);
    if ((rc != ffi_sql::PyiSqliteDone) && (rc != ffi_sql::PyiSqliteRow))
    {
      ffi_sql::pyiSqlite3Finalize(stmt);
      _sql_throw_operational();
    }
    ffi_sql::pyiSqlite3Finalize(stmt);
    return PySqliteCursor(nullptr);
  }
  return PySqliteCursor(stmt);
}

void PySqliteConnection::executeMany(PY2CPP_TYPE(PyStr) sql, const PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyList)<PyInt>>& seq)
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

PySqliteCursor::PySqliteCursor(struct sqlite3_stmt* stmt)
{
  _stmt = stmt;
  _done = (stmt == nullptr);
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
      ffi_sql::pyiSqlite3Finalize(_stmt);
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
    ffi_sql::pyiSqlite3Finalize(_stmt);
    _stmt = 0;
  }
}

PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>> PySqliteCursor::fetchOne()
{
  if ((_done) || (_stmt == 0))
  {
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
  }
  int rc = ffi_sql::pyiSqlite3Step(_stmt);
  if (rc == ffi_sql::PyiSqliteRow)
  {
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::Some(_sql_row_int1(_stmt));
  }
  if (rc == ffi_sql::PyiSqliteDone)
  {
    _done = true;
    ffi_sql::pyiSqlite3Finalize(_stmt);
    _stmt = 0;
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
  }
  _sql_throw_operational();
  return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
}

PY2CPP_TYPE(PyList)<PyTuple<PyInt>> PySqliteCursor::fetchAll()
{
  PY2CPP_TYPE(PyList)<PyTuple<PyInt>> out;
  if ((_done) || (_stmt == 0))
  {
    return out;
  }
  while (true)
  {
    int rc = ffi_sql::pyiSqlite3Step(_stmt);
    if (rc == ffi_sql::PyiSqliteRow)
    {
      out.append(_sql_row_int1(_stmt));
      continue;
    }
    if (rc == ffi_sql::PyiSqliteDone)
    {
      break;
    }
    _sql_throw_operational();
  }
  _done = true;
  ffi_sql::pyiSqlite3Finalize(_stmt);
  _stmt = 0;
  return out;
}

PY2CPP_BEGIN_SCOPE

PySqliteConnection connect(const PyStr& path)
{
  return PySqliteConnection::open(path);
}

PY2CPP_END_SCOPE
