PY2CPP_IGNORE
#include "py2cpp/sql/sqlite.h"
#include "py2cpp/text/str.h"
#include "py2cpp/util/list.h"
#include "py2cpp/core/optional.h"
PY2CPP_END

#include <stdint.h>
#include <string.h>
#include "sqlite3.h"

static void _sql_throw_operational()
{
  throw OperationalError();
}

static sqlite3* _sql_db_ptr(unsigned long long v)
{
  return (sqlite3*)(uintptr_t)v;
}

static sqlite3_stmt* _sql_stmt_ptr(unsigned long long v)
{
  return (sqlite3_stmt*)(uintptr_t)v;
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

static void _sql_bind_int_list(sqlite3_stmt* stmt, const PY2CPP_TYPE(PyList)<PyInt>& params)
{
  int n = params.__len__();
  int i = 0;
  while ((i < n))
  {
    int v = params.__getitem__(i);
    if (sqlite3_bind_int(stmt, i + 1, v) != SQLITE_OK)
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

static PyTuple<PyInt> _sql_row_int1(sqlite3_stmt* stmt)
{
  int v = sqlite3_column_int(stmt, 0);
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
      sqlite3_close(_sql_db_ptr(_db));
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
    sqlite3_close(_sql_db_ptr(_db));
    _db = 0;
    _closed = true;
  }
}

void PySqliteConnection::_open_impl(PyStr path)
{
  if ((_db != 0) && (!_closed))
  {
    sqlite3_close(_sql_db_ptr(_db));
    _db = 0;
  }
  char pbuf[4096];
  _sql_pystr_to_cbuf(path, pbuf, (int)sizeof(pbuf));
  sqlite3* db = nullptr;
  if (sqlite3_open(pbuf, &db) != SQLITE_OK)
  {
    if (db)
    {
      sqlite3_close(db);
    }
    _sql_throw_operational();
  }
  _db = (unsigned long long)(uintptr_t)db;
  _closed = false;
}

void PySqliteConnection::close()
{
  if ((_db != 0) && (!_closed))
  {
    sqlite3_close(_sql_db_ptr(_db));
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
  sqlite3* db = _sql_db_ptr(_db);
  if (sqlite3_get_autocommit(db))
  {
    return;
  }
  char* err = nullptr;
  if (sqlite3_exec(db, "COMMIT", nullptr, nullptr, &err) != SQLITE_OK)
  {
    if (err)
    {
      sqlite3_free(err);
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
  sqlite3* db = _sql_db_ptr(_db);
  if (sqlite3_get_autocommit(db))
  {
    return;
  }
  char* err = nullptr;
  if (sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, &err) != SQLITE_OK)
  {
    if (err)
    {
      sqlite3_free(err);
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
  sqlite3_stmt* stmt = nullptr;
  if (sqlite3_prepare_v2(_sql_db_ptr(_db), sbuf, -1, &stmt, nullptr) != SQLITE_OK)
  {
    _sql_throw_operational();
  }
  _sql_bind_int_list(stmt, params);
  PyBool is_sel = _sql_stmt_is_select(sbuf);
  if (!is_sel)
  {
    int rc = sqlite3_step(stmt);
    if ((rc != SQLITE_DONE) && (rc != SQLITE_ROW))
    {
      sqlite3_finalize(stmt);
      _sql_throw_operational();
    }
    sqlite3_finalize(stmt);
    return PySqliteCursor((unsigned long long)0);
  }
  return PySqliteCursor((unsigned long long)(uintptr_t)stmt);
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
      sqlite3_finalize(_sql_stmt_ptr(_stmt));
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
    sqlite3_finalize(_sql_stmt_ptr(_stmt));
    _stmt = 0;
  }
}

PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>> PySqliteCursor::fetchone()
{
  if ((_done) || (_stmt == 0))
  {
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::None_();
  }
  sqlite3_stmt* stmt = _sql_stmt_ptr(_stmt);
  int rc = sqlite3_step(stmt);
  if (rc == SQLITE_ROW)
  {
    return PY2CPP_TYPE(PyOptional)<PyTuple<PyInt>>::Some(_sql_row_int1(stmt));
  }
  if (rc == SQLITE_DONE)
  {
    _done = true;
    sqlite3_finalize(stmt);
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
  sqlite3_stmt* stmt = _sql_stmt_ptr(_stmt);
  while (true)
  {
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_ROW)
    {
      out.append(_sql_row_int1(stmt));
      continue;
    }
    if (rc == SQLITE_DONE)
    {
      break;
    }
    _sql_throw_operational();
  }
  _done = true;
  sqlite3_finalize(stmt);
  _stmt = 0;
  return out;
}

PY2CPP_BEGIN_SCOPE

PySqliteConnection connect(const PyStr& path)
{
  return PySqliteConnection::open(path);
}

PY2CPP_END_SCOPE
