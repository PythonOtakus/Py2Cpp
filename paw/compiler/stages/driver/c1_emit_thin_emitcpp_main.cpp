// Thin-emitted mid/emit_cpp vertical (D4++ → D5 parse→emit).
#include <cstdio>
#include <fstream>
#include <string>

#include "frontend/source.cpp"
#include "frontend/tokens.cpp"
#include "frontend/diagnostic.cpp"
#include "frontend/syntax_nodes.cpp"
#include "frontend/lexer.cpp"
#include "frontend/parser.cpp"
#include "mid/emit_cpp.cpp"

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

static std::string toUtf8(const PyStr& s) {
  std::string out;
  out.reserve(static_cast<size_t>(s.__len__()));
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    const int32_t cp = static_cast<int32_t>(s.__getitem__(i));
    if (cp >= 0 && cp < 128) {
      out.push_back(static_cast<char>(cp));
    }
  }
  return out;
}

static bool writeUtf8(const std::string& path, const PyStr& s) {
  std::ofstream f(path, std::ios::binary);
  if (!f) {
    return false;
  }
  const std::string u = toUtf8(s);
  f.write(u.data(), static_cast<std::streamsize>(u.size()));
  return static_cast<bool>(f);
}

static std::string readFile(const char* path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return {};
  }
  std::string raw((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
  // Thin lexer is LF-oriented; normalize CRLF from Windows checkouts.
  std::string out;
  out.reserve(raw.size());
  for (size_t i = 0; i < raw.size(); i += 1) {
    if (raw[i] == '\r') {
      continue;
    }
    out.push_back(raw[i]);
  }
  return out;
}

static int checkEmitEnum() {
  PyEnumBundle en{};
  en.name = PyStr("Color");
  PyEnumMember m0{};
  m0.name = PyStr("Red");
  m0.valueSource = PyStr("1");
  PyEnumMember m1{};
  m1.name = PyStr("Blue");
  m1.valueSource = PyStr("2");
  (void)(en.members.append(m0));
  (void)(en.members.append(m1));
  const PyStr out = emitEnum(en);
  if (!out.__contains__(PyStr("enum class PyColor")) ||
      !out.__contains__(PyStr("Red = 1")) ||
      !out.__contains__(PyStr("Blue = 2"))) {
    std::printf("FAIL thin emit_cpp.emitEnum content\n");
    printAscii(out);
    return 1;
  }
  std::printf("OK c1_emit_thin_emitcpp_main emitEnum Color\n");
  return 0;
}

static int checkEmitModuleEnumOnly() {
  PySyntaxModule mod{};
  PyEnumBundle en{};
  en.name = PyStr("Color");
  PyEnumMember m0{};
  m0.name = PyStr("Red");
  m0.valueSource = PyStr("1");
  PyEnumMember m1{};
  m1.name = PyStr("Blue");
  m1.valueSource = PyStr("2");
  (void)(en.members.append(m0));
  (void)(en.members.append(m1));
  (void)(mod.enums.append(en));
  PyEnumEmitState st = makeEnumEmitState();
  const PyStr path = PyStr("compiler/paw/mid/fixture_color");
  const PyStr hdr = emitModuleHeader(mod, path, st);
  const PyStr cpp = emitModuleCpp(mod, path, st);
  if (!hdr.__contains__(PyStr("enum class PyColor")) ||
      !hdr.__contains__(PyStr("#ifndef"))) {
    std::printf("FAIL thin emitModuleHeader enum-only\n");
    printAscii(hdr);
    return 1;
  }
  if (!cpp.__contains__(PyStr("#include")) ||
      !cpp.__contains__(PyStr("fixture_color"))) {
    std::printf("FAIL thin emitModuleCpp enum-only\n");
    printAscii(cpp);
    return 1;
  }
  std::printf("OK c1_emit_thin_emitcpp_main emitModule enum-only Color\n");
  return 0;
}

static int checkEmitModuleFunctionsHand() {
  PySyntaxModule mod{};
  PyFunctionBundle foo{};
  foo.name = PyStr("foo");
  foo.paramsSource = PyStr("x: int");
  foo.returnSource = PyStr("int");
  foo.bodySource = PyStr("return x");
  PyFunctionBundle add1{};
  add1.name = PyStr("add1");
  add1.paramsSource = PyStr("x: int");
  add1.returnSource = PyStr("int");
  add1.bodySource = PyStr("y: int = x + 1\nreturn y");
  PyFunctionBundle pick{};
  pick.name = PyStr("pick");
  pick.paramsSource = PyStr("x: int");
  pick.returnSource = PyStr("int");
  pick.bodySource = PyStr("if x > 0:\n  return x\nelse:\n  return 0");
  (void)(mod.functions.append(foo));
  (void)(mod.functions.append(add1));
  (void)(mod.functions.append(pick));
  PyEnumEmitState st = makeEnumEmitState();
  const PyStr path = PyStr("compiler/paw/mid/fixture_foo");
  const PyStr hdr = emitModuleHeader(mod, path, st);
  const PyStr cpp = emitModuleCpp(mod, path, st);
  if (!hdr.__contains__(PyStr("PyInt foo(PyInt x)")) ||
      !hdr.__contains__(PyStr("PyInt add1(PyInt x)")) ||
      !hdr.__contains__(PyStr("PyInt pick(PyInt x)"))) {
    std::printf("FAIL thin emitModuleHeader functions\n");
    printAscii(hdr);
    return 1;
  }
  if (!cpp.__contains__(PyStr("return x")) ||
      !cpp.__contains__(PyStr("PyInt y = (x + 1)")) ||
      !cpp.__contains__(PyStr("return y")) ||
      !cpp.__contains__(PyStr("if (")) ||
      !cpp.__contains__(PyStr("return 0"))) {
    std::printf("FAIL thin emitModuleCpp functions\n");
    printAscii(cpp);
    return 1;
  }
  std::printf("OK c1_emit_thin_emitcpp_main emitModule functions (hand)\n");
  return 0;
}

static bool emitLooksRunnable(const PyStr& hdr, const PyStr& cpp) {
  return hdr.__contains__(PyStr("PyInt foo(PyInt x)")) &&
         hdr.__contains__(PyStr("PyInt add1(PyInt x)")) &&
         hdr.__contains__(PyStr("PyInt pick(PyInt x)")) &&
         cpp.__contains__(PyStr("return x")) &&
         cpp.__contains__(PyStr("PyInt y = (x + 1)")) &&
         cpp.__contains__(PyStr("if (")) &&
         cpp.__contains__(PyStr("return 0"));
}

static int checkParseEmitFixture(const char* fixturePath, const char* outDir) {
  const std::string raw = readFile(fixturePath);
  if (raw.empty()) {
    std::printf("FAIL read fixture %s\n", fixturePath);
    return 1;
  }
  PyFileId fid{};
  fid.value = 42;
  PySyntaxModule mod = parseSource(PyStr(raw.c_str()), fid);
  if (mod.functions.__len__() < 3) {
    std::printf("FAIL parse fixture functions=%lld items=%lld rawLen=%zu\n",
                (long long)mod.functions.__len__(),
                (long long)mod.items.__len__(), raw.size());
    for (PyInt ii = 0; ii < mod.items.__len__(); ii += 1) {
      std::printf(" itemKind=%d opaque=\n",
                  (int)mod.items.__getitem__(ii).kind);
      printAscii(mod.items.__getitem__(ii).opaqueSource);
      std::printf("\n");
    }
    return 1;
  }
  PyEnumEmitState st = makeEnumEmitState();
  const PyStr path = PyStr("compiler/paw/mid/fixture_foo");
  const PyStr hdr = emitModuleHeader(mod, path, st);
  const PyStr cpp = emitModuleCpp(mod, path, st);
  if (!emitLooksRunnable(hdr, cpp)) {
    std::printf("FAIL thin parse→emit fixture content\n");
    std::printf("===HDR===\n");
    printAscii(hdr);
    std::printf("===CPP===\n");
    printAscii(cpp);
    return 1;
  }
  if (outDir != nullptr && outDir[0] != '\0') {
    const std::string base = std::string(outDir) + "/mid/fixture_foo";
    if (!writeUtf8(base + ".h", hdr) || !writeUtf8(base + ".cpp", cpp)) {
      std::printf("FAIL write thin fixture_foo (parse)\n");
      return 1;
    }
  }
  std::printf("===THIN_PARSE_HDR===\n");
  printAscii(hdr);
  std::printf("===END_THIN_PARSE_HDR===\n");
  std::printf("===THIN_PARSE_CPP===\n");
  printAscii(cpp);
  std::printf("===END_THIN_PARSE_CPP===\n");
  std::printf("OK c1_emit_thin_emitcpp_main parse→emit fixture_foo.paw\n");
  return 0;
}

static int checkParseEmitSyntax(const char* fixturePath) {
  const std::string raw = readFile(fixturePath);
  if (raw.empty()) {
    std::printf("FAIL read syntax fixture %s\n", fixturePath);
    return 1;
  }
  PyFileId fid{};
  fid.value = 7;
  PySyntaxModule mod = parseSource(PyStr(raw.c_str()), fid);
  if (mod.enums.__len__() < 1 || mod.classes.__len__() < 2 ||
      mod.functions.__len__() < 1) {
    std::printf(
      "FAIL parse syntax fixture enums=%lld classes=%lld fns=%lld\n",
      (long long)mod.enums.__len__(), (long long)mod.classes.__len__(),
      (long long)mod.functions.__len__());
    return 1;
  }
  PyEnumEmitState st = makeEnumEmitState();
  const PyStr path = PyStr("compiler/paw/mid/fixture_syntax");
  const PyStr hdr = emitModuleHeader(mod, path, st);
  const PyStr cpp = emitModuleCpp(mod, path, st);
  if (!hdr.__contains__(PyStr("enum class PyColor")) ||
      !hdr.__contains__(PyStr("class PyPoint")) ||
      !hdr.__contains__(PyStr("class PyBox")) ||
      !hdr.__contains__(PyStr("PyInt add("))) {
    std::printf("FAIL thin parse→emit syntax header\n");
    printAscii(hdr);
    return 1;
  }
  if (!cpp.__contains__(PyStr("PyInt add(")) ||
      !cpp.__contains__(PyStr("return (a + b)"))) {
    std::printf("FAIL thin parse→emit syntax cpp\n");
    printAscii(cpp);
    return 1;
  }
  std::printf("OK c1_emit_thin_emitcpp_main parse→emit fixture_syntax.paw\n");
  return 0;
}

int main(int argc, char** argv) {
  const char* outDir = nullptr;
  const char* fixturePath = "compiler/stages/fixtures/fixture_foo.paw";
  for (int i = 1; i < argc; i += 1) {
    const std::string a(argv[i]);
    if (a == "--write-out" && i + 1 < argc) {
      outDir = argv[++i];
    } else if (a == "--fixture" && i + 1 < argc) {
      fixturePath = argv[++i];
    }
  }
  if (checkEmitEnum() != 0) {
    return 1;
  }
  if (checkEmitModuleEnumOnly() != 0) {
    return 1;
  }
  if (checkEmitModuleFunctionsHand() != 0) {
    return 1;
  }
  if (checkParseEmitFixture(fixturePath, outDir) != 0) {
    return 1;
  }
  if (checkParseEmitSyntax("compiler/stages/fixtures/fixture_syntax.paw") != 0) {
    return 1;
  }
  return 0;
}
