PY2CPP_IGNORE
#include "py2cpp/io/file.h"
#include "py2cpp/util/array.h"
#include "py2cpp/util/list.h"
#include "py2cpp/text/str.h"
PY2CPP_END

#include "ffi/crt/stdio.h"
#include "ffi/crt/string.h"
#include "ffi/crt/stat.h"
#include "ffi/crt/stdlib.h"
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include "ffi/windows/windows.h"
#include "ffi/crt/direct.h"
#include "ffi/crt/io.h"
#include "ffi/crt/utime.h"
#else
#include "ffi/posix/unistd.h"
#include "ffi/posix/dirent.h"
#include "ffi/crt/utime.h"
#include "ffi/crt/fcntl.h"
#include "ffi/crt/stdlib.h"
#endif

static PyStr _os_cbuf_to_pystr(const char* buf)
{
  if ((!buf))
  {
    return PyStr("");
  }
  int n = (int)strlen(buf);
  if (n <= 0)
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

static void _os_throw_oserror()
{
  throw PY2CPP_TYPE(PyOSError)();
}

static void _os_throw_filenotfound()
{
  throw PY2CPP_TYPE(PyFileNotFoundError)();
}

static int _os_stat_impl(const char* cpath, struct _stat& st)
{
#ifdef _WIN32
  return _stat(cpath, &st);
#else
  return stat(cpath, &st);
#endif
}

static PyBool _os_path_exists_impl(const char* cpath)
{
  struct _stat st;
  if (_os_stat_impl(cpath, st) != 0)
  {
    return false;
  }
  return true;
}

PY2CPP_BEGIN_SCOPE

CStat fs_stat(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  struct _stat st;
  if (_os_stat_impl(pbuf, st) != 0)
  {
    _os_throw_filenotfound();
  }
CStat out = CStat();
  out.stMode = (int)st.st_mode;
  out.stSize = (int)st.st_size;
  out.stMtime = (double)st.st_mtime;
  out.stAtime = (double)st.st_atime;
  out.stCtime = (double)st.st_ctime;
  out.stDev = (int)st.st_dev;
  out.stIno = (int)st.st_ino;
  return out;
}

CStat fs_lstat(const PyStr& path)
{
  return fs_stat(path);
}

PyStr fs_getCwd()
{
#ifdef _WIN32
  char buf[4096];
  if (_getcwd(buf, (int)sizeof(buf)) == nullptr)
  {
    _os_throw_oserror();
  }
  return _os_cbuf_to_pystr(buf);
#else
  char buf[4096];
  if (getCwd(buf, sizeof(buf)) == nullptr)
  {
    _os_throw_oserror();
  }
  return _os_cbuf_to_pystr(buf);
#endif
}

PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyStr)> fs_listDir(const PY2CPP_TYPE(PyStr)& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  PY2CPP_TYPE(PyList)<PY2CPP_TYPE(PyStr)> out;
#ifdef _WIN32
  char pattern[4096];
  snprintf(pattern, sizeof(pattern), "%s\\*", pbuf);
  WIN32_FIND_DATAA fd;
  HANDLE h = FindFirstFileA(pattern, &fd);
  if (h == INVALID_HANDLE_VALUE)
  {
    _os_throw_filenotfound();
  }
  do {
    const char* name = fd.cFileName;
    if ((strcmp(name, ".") != 0) && (strcmp(name, "..") != 0))
    {
      out.append(_os_cbuf_to_pystr(name));
    }
  } while (FindNextFileA(h, &fd));
  FindClose(h);
#else
  DIR* d = opendir(pbuf);
  if (!d)
  {
    _os_throw_filenotfound();
  }
  struct dirent* ent;
  while ((ent = readdir(d)) != nullptr)
  {
    const char* name = ent->d_name;
    if ((strcmp(name, ".") == 0) || (strcmp(name, "..") == 0))
    {
      continue;
    }
    out.append(_os_cbuf_to_pystr(name));
  }
  closedir(d);
#endif
  return out;
}

struct ScandirState
{
  PyStr path;
#ifdef _WIN32
  HANDLE handle;
  WIN32_FIND_DATAA data;
  PyBool pending;
#else
  DIR* dir;
#endif
};

static PyBool _scandir_is_dot(const char* name)
{
  return (strcmp(name, ".") == 0) || (strcmp(name, "..") == 0);
}

static void _scandir_state_close(ScandirState* st)
{
  if (!st)
  {
    return;
  }
#ifdef _WIN32
  if (st->handle != INVALID_HANDLE_VALUE)
  {
    FindClose(st->handle);
    st->handle = INVALID_HANDLE_VALUE;
  }
  st->pending = false;
#else
  if (st->dir)
  {
    closedir(st->dir);
    st->dir = nullptr;
  }
#endif
}

static ScandirState* _scandir_state_open(const PyStr& pathname)
{
  char pbuf[4096];
  pathname.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  ScandirState* st = new ScandirState();
  st->path = pathname;
#ifdef _WIN32
  char pattern[4096];
  snprintf(pattern, sizeof(pattern), "%s\\*", pbuf);
  st->handle = FindFirstFileA(pattern, &st->data);
  if (st->handle == INVALID_HANDLE_VALUE)
  {
    delete st;
    _os_throw_filenotfound();
  }
  st->pending = true;
#else
  st->dir = opendir(pbuf);
  if (!st->dir)
  {
    delete st;
    _os_throw_filenotfound();
  }
#endif
  return st;
}

PyScandirIterator::PyScandirIterator(PyStr pathname)
{
  this->_path = pathname;
  this->_state = 0;
  ScandirState* st = _scandir_state_open(pathname);
  this->_state = (PyUPtr)(uintptr_t)st;
}

PyScandirIterator::PyScandirIterator(PyScandirIterator&& other)
  : _path(other._path), _state(other._state)
{
  other._state = 0;
}

PyScandirIterator& PyScandirIterator::operator=(PyScandirIterator&& other)
{
  if (this != &other)
  {
    this->close();
    this->_path = other._path;
    this->_state = other._state;
    other._state = 0;
  }
  return *this;
}

PyScandirIterator::~PyScandirIterator()
{
  this->close();
}

void PyScandirIterator::close()
{
  ScandirState* st = (ScandirState*)(uintptr_t)this->_state;
  if (st)
  {
    _scandir_state_close(st);
    delete st;
    this->_state = 0;
  }
}

PyScandirIterator& PyScandirIterator::__iter__()
{
  return *this;
}

PyIterResult<PyDirEntry, PyNone> PyScandirIterator::__next__()
{
  ScandirState* st = (ScandirState*)(uintptr_t)this->_state;
  if (!st)
  {
    return (PyIterResult<PyDirEntry, PyNone>::Return)(PyNone());
  }
#ifdef _WIN32
  for (;;)
  {
    if (!st->pending)
    {
      return (PyIterResult<PyDirEntry, PyNone>::Return)(PyNone());
    }
    char name_buf[260];
    strncpy(name_buf, st->data.cFileName, sizeof(name_buf) - 1);
    name_buf[sizeof(name_buf) - 1] = '\0';
    st->pending = (FindNextFileA(st->handle, &st->data) != 0);
    if (!_scandir_is_dot(name_buf))
    {
      PyStr ent_name = _os_cbuf_to_pystr(name_buf);
      PyStr full = path::join(st->path, ent_name);
      return (PyIterResult<PyDirEntry, PyNone>::Yield)(PyDirEntry(ent_name, full));
    }
    if (!st->pending)
    {
      return (PyIterResult<PyDirEntry, PyNone>::Return)(PyNone());
    }
  }
#else
  struct dirent* ent;
  while ((ent = readdir(st->dir)) != nullptr)
  {
    const char* name = ent->d_name;
    if (_scandir_is_dot(name))
    {
      continue;
    }
    PyStr ent_name = _os_cbuf_to_pystr(name);
    PyStr full = path::join(st->path, ent_name);
    return (PyIterResult<PyDirEntry, PyNone>::Yield)(PyDirEntry(ent_name, full));
  }
  _scandir_state_close(st);
  return (PyIterResult<PyDirEntry, PyNone>::Return)(PyNone());
#endif
}

void fs_mkdir(const PyStr& path, PyInt mode)
{
  (void)mode;
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  if (_mkdir(pbuf) != 0)
  {
    _os_throw_oserror();
  }
#else
  if (mkdir(pbuf, (mode_t)mode) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_remove(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  if ((::remove(pbuf)) != 0)
  {
    _os_throw_oserror();
  }
}

void fs_rmdir(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  if (_rmdir(pbuf) != 0)
  {
    _os_throw_oserror();
  }
#else
  if (rmdir(pbuf) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_replace(const PyStr& src, const PyStr& dst)
{
  char sbuf[4096];
  char dbuf[4096];
  src.copyToSpan(PySpan<PyByte>((PyByte*)sbuf, (PyInt)sizeof(sbuf), 1));
  dst.copyToSpan(PySpan<PyByte>((PyByte*)dbuf, (PyInt)sizeof(dbuf), 1));
#ifdef _WIN32
  if (MoveFileExA(sbuf, dbuf, MOVEFILE_REPLACE_EXISTING) == 0)
  {
    _os_throw_oserror();
  }
#else
  if (rename(sbuf, dbuf) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_rename(const PyStr& src, const PyStr& dst)
{
  char sbuf[4096];
  char dbuf[4096];
  src.copyToSpan(PySpan<PyByte>((PyByte*)sbuf, (PyInt)sizeof(sbuf), 1));
  dst.copyToSpan(PySpan<PyByte>((PyByte*)dbuf, (PyInt)sizeof(dbuf), 1));
#ifdef _WIN32
  if (MoveFileExA(sbuf, dbuf, 0) == 0)
  {
    _os_throw_oserror();
  }
#else
  if (rename(sbuf, dbuf) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_chdir(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  if (_chdir(pbuf) != 0)
  {
    _os_throw_oserror();
  }
#else
  if (chdir(pbuf) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

PyBool fs_access(const PyStr& path, PyInt mode)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  return (_access(pbuf, mode) == 0);
#else
  return (access(pbuf, mode) == 0);
#endif
}

void fs_chmod(const PyStr& path, PyInt mode)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  if (_chmod(pbuf, mode) != 0)
  {
    _os_throw_oserror();
  }
#else
  if (chmod(pbuf, (mode_t)mode) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_applyUtime(const PyStr& path, double atime, double mtime)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  struct _utimbuf tb;
  tb.actime = (time_t)atime;
  tb.modtime = (time_t)mtime;
  if (::_utime(pbuf, &tb) != 0)
  {
    _os_throw_oserror();
  }
#else
  struct utimbuf tb;
  tb.actime = (time_t)atime;
  tb.modtime = (time_t)mtime;
  if (::utime(pbuf, &tb) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_link(const PyStr& src, const PyStr& dst)
{
  char sbuf[4096];
  char dbuf[4096];
  src.copyToSpan(PySpan<PyByte>((PyByte*)sbuf, (PyInt)sizeof(sbuf), 1));
  dst.copyToSpan(PySpan<PyByte>((PyByte*)dbuf, (PyInt)sizeof(dbuf), 1));
#ifdef _WIN32
  if (CreateHardLinkA(dbuf, sbuf, NULL) == 0)
  {
    _os_throw_oserror();
  }
#else
  if (link(sbuf, dbuf) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

void fs_symlink(const PyStr& src, const PyStr& dst)
{
  char sbuf[4096];
  char dbuf[4096];
  src.copyToSpan(PySpan<PyByte>((PyByte*)sbuf, (PyInt)sizeof(sbuf), 1));
  dst.copyToSpan(PySpan<PyByte>((PyByte*)dbuf, (PyInt)sizeof(dbuf), 1));
#ifdef _WIN32
  if (CreateSymbolicLinkA(dbuf, sbuf, 0) == 0)
  {
    _os_throw_oserror();
  }
#else
  if (symlink(sbuf, dbuf) != 0)
  {
    _os_throw_oserror();
  }
#endif
}

PyStr fs_readLink(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  HANDLE h = CreateFileA(pbuf, GENERIC_READ, (FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE),
    NULL, OPEN_EXISTING, (FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS), NULL);
  if (h == INVALID_HANDLE_VALUE)
  {
    _os_throw_oserror();
  }
  char target[4096];
  DWORD ret = 0;
  if (GetFinalPathNameByHandleA(h, target, (DWORD)sizeof(target), FILE_NAME_NORMALIZED) == 0)
  {
    CloseHandle(h);
    _os_throw_oserror();
  }
  CloseHandle(h);
  (void)ret;
  return _os_cbuf_to_pystr(target);
#else
  char buf[4096];
  ssize_t n = readlink(pbuf, buf, sizeof(buf) - 1);
  if (n < 0)
  {
    _os_throw_oserror();
  }
  buf[n] = '\0';
  return _os_cbuf_to_pystr(buf);
#endif
}

void fs_unlink(const PyStr& path)
{
fs_remove(path);
}

PyBool path::exists(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  return _os_path_exists_impl(pbuf);
}

PyBool path::isFile(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  struct _stat st;
  if (_os_stat_impl(pbuf, st) != 0)
  {
    return false;
  }
#ifdef _WIN32
  return ((st.st_mode & _S_IFREG) != 0);
#else
  return S_ISREG(st.st_mode);
#endif
}

PyBool path::isDir(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  struct _stat st;
  if (_os_stat_impl(pbuf, st) != 0)
  {
    return false;
  }
#ifdef _WIN32
  return ((st.st_mode & _S_IFDIR) != 0);
#else
  return S_ISDIR(st.st_mode);
#endif
}

PyBool path::lExists(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
  return _os_path_exists_impl(pbuf);
}

PyBool path::isLink(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  DWORD attr = GetFileAttributesA(pbuf);
  if (attr == INVALID_FILE_ATTRIBUTES)
  {
    return false;
  }
  if ((attr & FILE_ATTRIBUTE_REPARSE_POINT) == 0)
  {
    return false;
  }
  WIN32_FIND_DATAA fd;
  HANDLE h = FindFirstFileA(pbuf, &fd);
  if (h == INVALID_HANDLE_VALUE)
  {
    return false;
  }
  FindClose(h);
  return (fd.dwReserved0 == IO_REPARSE_TAG_SYMLINK);
#else
  struct _stat st;
  if (_os_stat_impl(pbuf, st) != 0)
  {
    return false;
  }
  return S_ISLNK(st.st_mode);
#endif
}

PyBool path::isJunction(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  DWORD attr = GetFileAttributesA(pbuf);
  if (attr == INVALID_FILE_ATTRIBUTES)
  {
    return false;
  }
  if ((attr & FILE_ATTRIBUTE_REPARSE_POINT) == 0)
  {
    return false;
  }
  WIN32_FIND_DATAA fd;
  HANDLE h = FindFirstFileA(pbuf, &fd);
  if (h == INVALID_HANDLE_VALUE)
  {
    return false;
  }
  FindClose(h);
  return (fd.dwReserved0 == IO_REPARSE_TAG_MOUNT_POINT);
#else
  (void)pbuf;
  return false;
#endif
}

PyBool path::isDevDrive(const PyStr& path)
{
  (void)path;
  return false;
}

PyStr path::realPath(const PyStr& path)
{
  char pbuf[4096];
  path.copyToSpan(PySpan<PyByte>((PyByte*)pbuf, (PyInt)sizeof(pbuf), 1));
#ifdef _WIN32
  char outbuf[4096];
  DWORD n = GetFullPathNameA(pbuf, (DWORD)sizeof(outbuf), outbuf, NULL);
  if (n == 0 || n >= sizeof(outbuf))
  {
    _os_throw_oserror();
  }
  return _os_cbuf_to_pystr(outbuf);
#else
  char outbuf[4096];
  if (realPath(pbuf, outbuf) == NULL)
  {
    _os_throw_oserror();
  }
  return _os_cbuf_to_pystr(outbuf);
#endif
}

PyInt path::getSize(const PyStr& path)
{
  return fs_stat(path).stSize;
}

PyFloat64 path::getMtime(const PyStr& path)
{
  return fs_stat(path).stMtime;
}

PyFloat64 path::getAtime(const PyStr& path)
{
  return fs_stat(path).stAtime;
}

PyFloat64 path::getCtime(const PyStr& path)
{
  return fs_stat(path).stCtime;
}

PyStr path::_pathGetcwd()
{
  return fs_getCwd();
}

PyInt path::_pathStatDev(const PyStr& path)
{
  return fs_stat(path).stDev;
}

PyInt path::_pathStatIno(const PyStr& path)
{
  return fs_stat(path).stIno;
}

PY2CPP_END_SCOPE
