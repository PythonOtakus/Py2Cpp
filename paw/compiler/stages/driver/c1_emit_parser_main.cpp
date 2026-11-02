// Thin emit parser vertical + dual parse dump (D1) + Mid dump via paw bind (D2).
#include <cstdio>

#include "frontend/source.cpp"
#include "frontend/tokens.cpp"
#include "frontend/diagnostic.cpp"
#include "frontend/syntax_nodes.cpp"
#include "frontend/lexer.cpp"
#include "frontend/parser.cpp"
#include "hir/nodes.cpp"
#include "mid/nodes.cpp"
#include "sema/bind.cpp"

static void printAscii(const PyStr& s) {
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    const int32_t cp = static_cast<int32_t>(s.__getitem__(i));
    if (cp >= 32 && cp < 127) {
      std::printf("%c", static_cast<char>(cp));
    } else if (cp == 10) {
      std::printf("\n");
    }
  }
}

int main() {
  PyFileId fid{};
  fid.value = 0;
  PySyntaxModule mod =
    parseSource(PyStr("enum Color:\n  Red = 1\n  Blue = 2\n"), fid);
  if (mod.enums.__len__() < 1) {
    std::printf("FAIL parse enum count=%lld\n",
                static_cast<long long>(mod.enums.__len__()));
    return 1;
  }
  PyEnumBundle en = mod.enums.__getitem__(0);
  if (en.name != PyStr("Color")) {
    std::printf("FAIL enum name\n");
    return 1;
  }
  if (en.members.__len__() < 2) {
    std::printf("FAIL members count=%lld\n",
                static_cast<long long>(en.members.__len__()));
    return 1;
  }
  PyEnumMember m0 = en.members.__getitem__(0);
  if (m0.name != PyStr("Red")) {
    std::printf("FAIL member0 Red\n");
    return 1;
  }

  std::printf("===PARSE_DUMP===\n");
  for (PyInt ei = 0; ei < mod.enums.__len__(); ei += 1) {
    PyEnumBundle e = mod.enums.__getitem__(ei);
    std::printf("enum:");
    printAscii(e.name);
    std::printf("\n");
    for (PyInt mi = 0; mi < e.members.__len__(); mi += 1) {
      PyEnumMember m = e.members.__getitem__(mi);
      std::printf("member:");
      printAscii(m.name);
      std::printf("=");
      printAscii(m.valueSource);
      std::printf("\n");
    }
  }
  for (PyInt fi = 0; fi < mod.functions.__len__(); fi += 1) {
    PyFunctionBundle fn = mod.functions.__getitem__(fi);
    std::printf("fn:");
    printAscii(fn.name);
    std::printf("\n");
  }
  std::printf("===END_DUMP===\n");

  // D2: paw sema bind → MidModule dump（enum 竖切真 Mid）。
  PyHirModule hir = bindModule(mod, PyStr("compiler/dual/fixtures/parse_enum_color"));
  PyMidModule mid = lowerToMid(hir);
  PyStr midDump = dumpMidModule(mid);
  std::printf("===MID_DUMP===\n");
  printAscii(midDump);
  std::printf("===END_MID_DUMP===\n");
  std::printf("OK c1_emit_parser_main parse enum Color\n");

  // D6: class / record / def / const / import surface via thin parser.
  PySyntaxModule syn = parseSource(
    PyStr(
      "from .source import SourceSpan\n"
      "\n"
      "enum Color:\n"
      "  Red = 1\n"
      "  Blue = 2\n"
      "\n"
      "const MAX: int = 3\n"
      "\n"
      "class Point:\n"
      "  x: int = 0\n"
      "  y: int = 0\n"
      "  def sum(self) -> int:\n"
      "    return self.x + self.y\n"
      "\n"
      "record Box:\n"
      "  w: int = 1\n"
      "  h: int = 1\n"
      "\n"
      "def add(a: int, b: int) -> int:\n"
      "  return a + b\n"),
    fid);
  if (syn.enums.__len__() < 1 || syn.classes.__len__() < 2 ||
      syn.functions.__len__() < 1 || syn.imports.__len__() < 1) {
    std::printf(
      "FAIL D6 parse syntax enums=%lld classes=%lld fns=%lld imports=%lld\n",
      (long long)syn.enums.__len__(), (long long)syn.classes.__len__(),
      (long long)syn.functions.__len__(), (long long)syn.imports.__len__());
    for (PyInt ci = 0; ci < syn.classes.__len__(); ci += 1) {
      std::printf(" class:");
      printAscii(syn.classes.__getitem__(ci).name);
      std::printf(" record=%d fields=%lld\n",
                  (int)syn.classes.__getitem__(ci).isRecord,
                  (long long)syn.classes.__getitem__(ci).constFields.__len__());
    }
    return 1;
  }
  PyClassBundle pt = syn.classes.__getitem__(0);
  if (pt.name != PyStr("Point") || pt.constFields.__len__() < 2 ||
      pt.methods.__len__() < 1) {
    std::printf("FAIL D6 Point fields=%lld methods=%lld\n",
                (long long)pt.constFields.__len__(),
                (long long)pt.methods.__len__());
    return 1;
  }
  PyClassBundle box = syn.classes.__getitem__(1);
  if (box.name != PyStr("Box") || !box.isRecord) {
    std::printf("FAIL D6 Box record\n");
    return 1;
  }
  if (syn.functions.__getitem__(0).name != PyStr("add")) {
    std::printf("FAIL D6 add fn\n");
    return 1;
  }
  std::printf("OK c1_emit_parser_main D6 class/record/def/const/import\n");
  return 0;
}
