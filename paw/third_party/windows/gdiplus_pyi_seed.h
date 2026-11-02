/* Seed header for ``c_ffi_pyi`` only (GDI+ is C++ ``namespace``; cannot parse as C).
 * Glue still ``#include <gdiplus.h>`` via ``ffi_layout`` → ``gdiplus.h``.
 * Templates may use ``Gdiplus::`` after including ``"ffi/windows/gdiplus.h"``.
 */
#ifndef PY2CPP_GDIPLUS_PYI_SEED_H
#define PY2CPP_GDIPLUS_PYI_SEED_H

#include <windows.h>

typedef int GpStatus;
enum {
  Ok = 0,
  GenericError = 1,
};

typedef struct GdiplusStartupInput {
  UINT32 GdiplusVersion;
  void* DebugEventCallback;
  BOOL SuppressBackgroundThread;
  BOOL SuppressExternalCodecs;
} GdiplusStartupInput;

typedef struct GdiplusStartupOutput {
  void* NotificationHook;
  void* NotificationUnhook;
} GdiplusStartupOutput;

GpStatus WINAPI GdiplusStartup(
  ULONG_PTR* token,
  const GdiplusStartupInput* input,
  GdiplusStartupOutput* output
);
void WINAPI GdiplusShutdown(ULONG_PTR token);

#endif
