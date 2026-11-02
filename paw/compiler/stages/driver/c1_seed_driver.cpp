// C1 seed driver: amalgamation of stage1 Mid seed + CLI.
//   c1_seed_driver --smoke
//   c1_seed_driver --emit-out DIR file.paw [...]
//   c1_seed_driver path/to/file.paw [...]
#include <cstdio>
#include <cstring>
#include <exception>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "compiler/paw/frontend/source.cpp"
#include "compiler/paw/frontend/tokens.cpp"
#include "compiler/paw/frontend/diagnostic.cpp"
#include "compiler/paw/frontend/syntax_nodes.cpp"
#include "compiler/paw/frontend/lexer.cpp"
#include "compiler/paw/frontend/parser.cpp"
#include "compiler/paw/mid/emit_cpp.cpp"
#include "compiler/paw/passes/check.cpp"

using compiler::paw::passes::check::checkOk;
using compiler::paw::mid::emit_cpp::PyEnumEmitState;
using compiler::paw::mid::emit_cpp::emitEnum;
using compiler::paw::mid::emit_cpp::emitModuleCpp;
using compiler::paw::mid::emit_cpp::emitModuleHeader;
using compiler::paw::mid::emit_cpp::emitReport;
using compiler::paw::mid::emit_cpp::listRelativeImportStems;
using compiler::paw::mid::emit_cpp::makeEnumEmitState;
using compiler::paw::frontend::parser::parseSource;
using compiler::paw::frontend::source::PyFileId;
using compiler::paw::frontend::syntax_nodes::PyEnumBundle;
using compiler::paw::frontend::syntax_nodes::PyEnumMember;
using compiler::paw::frontend::syntax_nodes::PyItemKindEnum;
using compiler::paw::frontend::syntax_nodes::PySyntaxModule;
using py2cpp::PyStr;

static const char* kSmokeSrc =
  "def foo(x: int) -> int:\n"
  "  return x\n"
  "\n"
  "def bar():\n"
  "  pass\n"
  "\n"
  "enum Color:\n"
  "  Red = 0\n"
  "  Blue = 1\n";

static std::string readFile(const char* path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error(std::string("cannot open: ") + path);
  }
  return std::string((std::istreambuf_iterator<char>(in)),
                     std::istreambuf_iterator<char>());
}

static void writeUtf8Codepoint(std::ofstream& out, int32_t cp) {
  if (cp < 0) {
    throw std::runtime_error("negative codepoint in emit output");
  }
  if (cp <= 0x7F) {
    out.put(static_cast<char>(cp));
  } else if (cp <= 0x7FF) {
    out.put(static_cast<char>(0xC0 | ((cp >> 6) & 0x1F)));
    out.put(static_cast<char>(0x80 | (cp & 0x3F)));
  } else if (cp <= 0xFFFF) {
    out.put(static_cast<char>(0xE0 | ((cp >> 12) & 0x0F)));
    out.put(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
    out.put(static_cast<char>(0x80 | (cp & 0x3F)));
  } else {
    out.put(static_cast<char>(0xF0 | ((cp >> 18) & 0x07)));
    out.put(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
    out.put(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
    out.put(static_cast<char>(0x80 | (cp & 0x3F)));
  }
}

static void writePyStrUtf8(const std::string& path, const PyStr& s) {
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    throw std::runtime_error("cannot write: " + path);
  }
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    const PyChar ch = s.__getitem__(i);
    writeUtf8Codepoint(out, static_cast<int32_t>(ch));
  }
}

static std::string stemOf(const std::string& path) {
  std::string s = path;
  for (char& c : s) {
    if (c == '\\') {
      c = '/';
    }
  }
  const auto slash = s.find_last_of('/');
  const auto base = (slash == std::string::npos) ? s : s.substr(slash + 1);
  const auto dot = base.find_last_of('.');
  return (dot == std::string::npos) ? base : base.substr(0, dot);
}

/** ``compiler/paw/frontend/lexer.paw`` → ``frontend/lexer`` (under paw). */
static std::string relUnderPaw(const std::string& path) {
  std::string s = path;
  for (char& c : s) {
    if (c == '\\') {
      c = '/';
    }
  }
  const char* marker = "compiler/paw/";
  const auto pos = s.find(marker);
  std::string rel =
    (pos == std::string::npos) ? stemOf(path) : s.substr(pos + std::strlen(marker));
  if (rel.size() >= 4 && rel.substr(rel.size() - 4) == ".paw") {
    rel = rel.substr(0, rel.size() - 4);
  }
  return rel;
}

/** ``compiler/paw/frontend/lexer.paw`` → ``compiler/paw/frontend/lexer``. */
static std::string modulePathOf(const std::string& path) {
  return std::string("compiler/paw/") + relUnderPaw(path);
}

/** ``compiler/paw/frontend/lexer`` → ``frontend/lexer``. */
static std::string emitRelOfModulePath(const std::string& modulePath) {
  const char* marker = "compiler/paw/";
  if (modulePath.rfind(marker, 0) == 0) {
    return modulePath.substr(std::strlen(marker));
  }
  return stemOf(modulePath);
}

static std::string dirOf(const std::string& path) {
  std::string s = path;
  for (char& c : s) {
    if (c == '\\') {
      c = '/';
    }
  }
  const auto slash = s.find_last_of('/');
  if (slash == std::string::npos) {
    return ".";
  }
  return s.substr(0, slash);
}

static void registerParsedEnums(PyEnumEmitState& est, const std::string& stem,
                                PySyntaxModule& mod) {
  est.registerModule(PyStr(stem.c_str()), mod);
}

static void registerRelativeImportEnums(PyEnumEmitState& est,
                                        const std::string& filePath,
                                        PySyntaxModule& mod, PyInt& nextFid) {
  const std::string dir = dirOf(filePath);
  const auto stems = listRelativeImportStems(mod);
  for (PyInt i = 0; i < stems.__len__(); i += 1) {
    const PyStr st = stems.__getitem__(i);
    std::string stemAscii;
    for (PyInt j = 0; j < st.__len__(); j += 1) {
      const PyChar ch = st.__getitem__(j);
      const int32_t cp = static_cast<int32_t>(ch);
      if (cp < 0 || cp > 127) {
        continue;
      }
      stemAscii.push_back(static_cast<char>(cp));
    }
    if (stemAscii.empty()) {
      continue;
    }
    const std::string depPath = dir + "/" + stemAscii + ".paw";
    try {
      const std::string raw = readFile(depPath.c_str());
      PyFileId fid{};
      fid.value = nextFid;
      nextFid += 1;
      PySyntaxModule dep = parseSource(PyStr(raw.c_str()), fid);
      registerParsedEnums(est, stemAscii, dep);
    } catch (const std::exception&) {
      // Missing dep .paw: leave unregistered; emit keeps attrs unrewritten.
    }
  }
}

static bool containsAscii(const PyStr& s, const char* needle) {
  const PyStr n(needle);
  return s.__contains__(n);
}

static int parseOne(const char* label, const PyStr& src, PyInt fileValue,
                    bool require_smoke_shape) {
  PyFileId fid{};
  fid.value = fileValue;
  PySyntaxModule mod = parseSource(src, fid);
  const PyInt n_fn = mod.functions.__len__();
  const PyInt n_en = mod.enums.__len__();
  const PyInt n_cl = mod.classes.__len__();
  const PyInt n_it = mod.items.__len__();
  PyInt n_opaque = 0;
  for (PyInt i = 0; i < n_it; i += 1) {
    if (mod.items.__getitem__(i).kind == PyItemKindEnum::Opaque) {
      n_opaque += 1;
    }
  }
  std::printf(
    "OK parse %s fn=%lld en=%lld class=%lld items=%lld opaque=%lld\n",
    label,
    static_cast<long long>(n_fn),
    static_cast<long long>(n_en),
    static_cast<long long>(n_cl),
    static_cast<long long>(n_it),
    static_cast<long long>(n_opaque));
  if (!checkOk(mod)) {
    std::printf("FAIL check duplicate names: %s\n", label);
    return 1;
  }
  if (require_smoke_shape && (n_fn < 2 || n_en < 1 || n_it < 3)) {
    std::printf("FAIL smoke shape\n");
    return 1;
  }
  if (n_it < 1) {
    std::printf("FAIL empty module: %s\n", label);
    return 1;
  }
  return 0;
}

static int emitOne(const char* label, const PyStr& src, const std::string& modulePath,
                   const std::string& outDir, PyInt fileValue, bool require_smoke,
                   const char* sourcePath) {
  PyFileId fid{};
  fid.value = fileValue;
  PySyntaxModule mod = parseSource(src, fid);
  PyEnumEmitState est = makeEnumEmitState();
  est.clear();
  const std::string stem = stemOf(modulePath);
  registerParsedEnums(est, stem, mod);
  PyInt depFid = fileValue + 1000;
  if (sourcePath != nullptr) {
    registerRelativeImportEnums(est, sourcePath, mod, depFid);
  }
  const PyStr mp(modulePath.c_str());
  const PyStr hdr = emitModuleHeader(mod, mp, est);
  const PyStr cpp = emitModuleCpp(mod, mp, est);
  if (require_smoke) {
    if (!containsAscii(hdr, "enum class PyColor") || !containsAscii(hdr, "PyInt foo(") ||
        !containsAscii(hdr, "PyInt x") || !containsAscii(cpp, "return x;") ||
        !containsAscii(cpp, "void bar(")) {
      std::printf("FAIL emit smoke content\n");
      return 1;
    }
  }
  if (modulePath.size() >= 7 &&
      modulePath.compare(modulePath.size() - 7, 7, "/source") == 0) {
    if (!containsAscii(hdr, "class PyFileId") ||
        !containsAscii(hdr, "class PySourceSpan") ||
        !containsAscii(hdr, "class PySourceManager") ||
        !containsAscii(cpp, "makeSpan(") ||
        !containsAscii(cpp, "this->_files")) {
      std::printf("FAIL emit source content\n");
      return 1;
    }
  }
  if (modulePath.size() >= 7 &&
      modulePath.compare(modulePath.size() - 7, 7, "/tokens") == 0) {
    if (!containsAscii(hdr, "enum class PyTokenKindEnum") ||
        containsAscii(hdr, "= ...") ||
        !containsAscii(hdr, "PyTokenKindEnum kind") ||
        !containsAscii(hdr, "#include \"source.h\"")) {
      std::printf("FAIL emit tokens content\n");
      return 1;
    }
  }
  if (modulePath.find("diagnostic") != std::string::npos) {
    if (!containsAscii(hdr, "#include \"source.h\"") ||
        !containsAscii(hdr, "class PyDiagnostic") ||
        !containsAscii(hdr, "PySourceSpan span") ||
        !containsAscii(cpp, "makeDiagnostic(") ||
        !containsAscii(cpp, "formatDiagnostic(") ||
        !containsAscii(cpp, "__o.hasSpan")) {
      std::printf("FAIL emit diagnostic content\n");
      return 1;
    }
  }
  if (modulePath.size() >= 5 &&
      modulePath.compare(modulePath.size() - 5, 5, "check") == 0) {
    if (!containsAscii(hdr, "#include \"../frontend/syntax_nodes.h\"") ||
        !containsAscii(hdr, "checkOk(")) {
      std::printf("FAIL emit check content\n");
      return 1;
    }
  }
  if (modulePath.find("lexer") != std::string::npos) {
    if (!containsAscii(hdr, "class PyLexer") ||
        !containsAscii(cpp, "tokenize(") || !containsAscii(cpp, "while (true)")) {
      std::printf("FAIL emit lexer content\n");
      return 1;
    }
  }
  if (modulePath.find("parser") != std::string::npos) {
    if (!containsAscii(hdr, "parseSource(") ||
        !containsAscii(cpp, "parseTokens(") ||
        !containsAscii(hdr, "#include \"lexer.h\"")) {
      std::printf("FAIL emit parser content\n");
      return 1;
    }
  }
  if (modulePath.find("mid/emit_cpp") != std::string::npos ||
      modulePath.find("mid\\emit_cpp") != std::string::npos) {
    if (!containsAscii(hdr, "emitEnum(") || !containsAscii(hdr, "emitModuleHeader(")) {
      std::printf("FAIL emit emit_cpp content\n");
      return 1;
    }
  }
  const std::string emitRel = emitRelOfModulePath(modulePath);
  const std::string outBase = outDir + "/" + emitRel;
  const auto slash = emitRel.find_last_of('/');
  if (slash != std::string::npos) {
    std::filesystem::create_directories(outDir + "/" + emitRel.substr(0, slash));
  }
  writePyStrUtf8(outBase + ".h", hdr);
  writePyStrUtf8(outBase + ".cpp", cpp);
  const PyStr rep = emitReport(mod);
  std::printf("OK emit %s -> %s/{%s.h,%s.cpp} report_len=%lld\n",
              label, outDir.c_str(), emitRel.c_str(), emitRel.c_str(),
              static_cast<long long>(rep.__len__()));
  return 0;
}

static int runSmoke() {
  if (parseOne("smoke", PyStr(kSmokeSrc), 1, true) != 0) {
    return 1;
  }
  return 0;
}

static int runSmokeEmit(const std::string& outDir) {
  if (runSmoke() != 0) {
    return 1;
  }
  return emitOne("smoke", PyStr(kSmokeSrc), "compiler/paw/frontend/smoke", outDir, 1, true,
                 nullptr);
}

static int runFiles(const std::vector<const char*>& paths) {
  int rc = 0;
  PyInt fid = 1;
  for (const char* path : paths) {
    try {
      std::string raw = readFile(path);
      if (parseOne(path, PyStr(raw.c_str()), fid, false) != 0) {
        rc = 1;
      }
    } catch (const std::exception& ex) {
      std::printf("FAIL parse %s: %s\n", path, ex.what());
      rc = 1;
    }
    fid += 1;
  }
  return rc;
}

static int runEmitFiles(const std::string& outDir,
                        const std::vector<const char*>& paths) {
  int rc = 0;
  PyInt fid = 1;
  for (const char* path : paths) {
    try {
      std::string raw = readFile(path);
      const std::string mp = modulePathOf(path);
      if (emitOne(path, PyStr(raw.c_str()), mp, outDir, fid, false, path) != 0) {
        rc = 1;
      }
    } catch (const std::exception& ex) {
      std::printf("FAIL emit %s: %s\n", path, ex.what());
      rc = 1;
    }
    fid += 1;
  }
  return rc;
}

/** D4+：宿主 Mid ``emit_cpp.paw::emitEnum``（取消 thin ``emit_enum_min`` 例外）。 */
static int runEmitEnumDump() {
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
  if (!containsAscii(out, "enum class PyColor") ||
      !containsAscii(out, "Red = 1") ||
      !containsAscii(out, "Blue = 2")) {
    std::printf("FAIL emitEnum content\n");
    return 1;
  }
  std::printf("===EMIT_DUMP===\n");
  for (PyInt i = 0; i < out.__len__(); i += 1) {
    const int32_t cp = static_cast<int32_t>(out.__getitem__(i));
    if (cp >= 32 && cp < 127) {
      std::printf("%c", static_cast<char>(cp));
    } else if (cp == 10) {
      std::printf("\n");
    }
  }
  std::printf("===END_EMIT_DUMP===\n");
  std::printf("OK c1_seed_driver emitEnum Color (Mid emit_cpp)\n");
  return 0;
}

int main(int argc, char** argv) {
  try {
    std::string emitOut;
    std::vector<const char*> paths;
    bool wantSmoke = false;
    bool wantEmitEnumDump = false;
    for (int i = 1; i < argc; i += 1) {
      std::string a(argv[i]);
      if (a == "--smoke") {
        wantSmoke = true;
        continue;
      }
      if (a == "--emit-enum-dump") {
        wantEmitEnumDump = true;
        continue;
      }
      if (a == "--emit-out") {
        if (i + 1 >= argc) {
          std::printf("FAIL usage: --emit-out DIR\n");
          return 2;
        }
        emitOut = argv[++i];
        continue;
      }
      paths.push_back(argv[i]);
    }
    if (argc <= 1) {
      wantSmoke = true;
    }
    if (wantEmitEnumDump) {
      return runEmitEnumDump();
    }
    if (!emitOut.empty()) {
      if (wantSmoke && paths.empty()) {
        return runSmokeEmit(emitOut);
      }
      if (wantSmoke && runSmoke() != 0) {
        return 1;
      }
      return runEmitFiles(emitOut, paths);
    }
    if (wantSmoke && runSmoke() != 0) {
      return 1;
    }
    if (paths.empty()) {
      return 0;
    }
    return runFiles(paths);
  } catch (const std::exception& ex) {
    std::printf("FAIL c1_seed_driver exception: %s\n", ex.what());
    return 2;
  } catch (...) {
    std::printf("FAIL c1_seed_driver unknown exception\n");
    return 3;
  }
}
