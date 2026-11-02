// Thin emit source vertical (add/get/spanOf).
#include <cstdio>

#include "frontend/source.cpp"

int main() {
  PySourceManager sm{};
  PySourceFile a = sm.add(PyStr("a.paw"), PyStr("x=1"), PyStr("d0"));
  PySourceFile b = sm.add(PyStr("b.paw"), PyStr("y=2"), PyStr("d1"));
  PySourceFile a2 = sm.add(PyStr("a.paw"), PyStr("ignored"), PyStr("dx"));
  if (a.fileId.value != 0 || b.fileId.value != 1) {
    std::printf("FAIL fileId assign\n");
    return 1;
  }
  if (a2.fileId.value != 0 || a2.text != PyStr("x=1")) {
    std::printf("FAIL add dedupe by path\n");
    return 1;
  }
  PySourceFile g = sm.get(b.fileId);
  if (g.path != PyStr("b.paw") || g.text != PyStr("y=2")) {
    std::printf("FAIL get\n");
    return 1;
  }
  PySourceSpan sp = sm.spanOf(a.fileId, 0, 3);
  if (sp.fileId.value != 0 || sp.start != 0 || sp.end != 3) {
    std::printf("FAIL spanOf\n");
    return 1;
  }
  bool threw = false;
  try {
    (void)sm.spanOf(a.fileId, 5, 2);
  } catch (const paw::core::exceptions::PyValueError&) {
    threw = true;
  } catch (...) {
    std::printf("FAIL spanOf bad range wrong exception\n");
    return 1;
  }
  if (!threw) {
    std::printf("FAIL spanOf bad range no throw\n");
    return 1;
  }
  std::printf("OK c1_emit_srcmgr_main add+get+spanOf\n");
  return 0;
}
