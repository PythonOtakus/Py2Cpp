// Single-TU runner for thin mid_emit diagnostic (needs span_tokens.h).
#include <cstdio>

#include "frontend/source.cpp"
#include "frontend/diagnostic.cpp"

static bool pyStrEqAscii(const PyStr& s, const char* ascii) {
  const PyStr want(ascii);
  return s == want;
}

int main() {
  PyDiagnostic d0 = makeDiagnosticNoSpan(PyStr("E001"), PyStr("boom"));
  if (d0.hasSpan) {
    std::printf("FAIL makeDiagnosticNoSpan hasSpan\n");
    return 1;
  }
  if (!pyStrEqAscii(d0.code, "E001") || !pyStrEqAscii(d0.message, "boom")) {
    std::printf("FAIL makeDiagnosticNoSpan fields\n");
    return 1;
  }
  PyStr f0 = formatDiagnostic(d0);
  if (!pyStrEqAscii(f0, "E001: boom")) {
    std::printf("FAIL formatDiagnostic no-span\n");
    return 1;
  }
  PySourceSpan sp = makeSpan(1, 2, 5);
  PyDiagnostic d1 = makeDiagnostic(PyStr("E002"), PyStr("bad"), sp);
  if (!d1.hasSpan) {
    std::printf("FAIL makeDiagnostic hasSpan\n");
    return 1;
  }
  PyStr f1 = formatDiagnostic(d1);
  // Must contain code/message; span coords if body emit succeeded.
  if (!f1.__contains__(PyStr("E002: bad"))) {
    std::printf("FAIL formatDiagnostic with-span prefix\n");
    return 1;
  }
  std::printf("OK c1_emit_diag_main format+new\n");
  return 0;
}
