#include "ffi/windows.h"

namespace py2cpp
{
  namespace console
  {
    namespace py_popen
    {

      inline HANDLE _winHandle(PyUIntPtr h)
      {
        return reinterpret_cast<HANDLE>(static_cast<uintptr_t>(h));
      }

      inline void _startupSetStdHandles(
        ::ffi::windows::PyiStartupinfoW& si,
        PyUIntPtr stdinH,
        PyUIntPtr stdoutH,
        PyUIntPtr stderrH)
      {
        si.hStdInput = _winHandle(stdinH);
        si.hStdOutput = _winHandle(stdoutH);
        si.hStdError = _winHandle(stderrH);
      }

      inline PyUIntPtr _processInfoProcessHandle(const ::ffi::windows::PyiProcessInformation& pi)
      {
        return static_cast<PyUIntPtr>(reinterpret_cast<uintptr_t>(pi.hProcess));
      }

      inline PyUIntPtr _processInfoThreadHandle(const ::ffi::windows::PyiProcessInformation& pi)
      {
        return static_cast<PyUIntPtr>(reinterpret_cast<uintptr_t>(pi.hThread));
      }

    } // namespace py_popen
  } // namespace console
} // namespace py2cpp
