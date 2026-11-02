// C1 thin reseed: use thin-emitted parser+emit_cpp to re-emit seed .paw → outDir.
// Gate for true C1→C2: thin stack must emit its own seed corpus.
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "frontend/source.cpp"
#include "frontend/tokens.cpp"
#include "frontend/diagnostic.cpp"
#include "frontend/syntax_nodes.cpp"
#include "frontend/lexer.cpp"
#include "frontend/parser.cpp"
#include "mid/emit_cpp.cpp"

namespace fs = std::filesystem;

static std::string readFile(const char* path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return {};
  }
  std::string raw((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
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

static void writeUtf8Codepoint(std::ofstream& out, int32_t cp) {
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

static bool writePyStrUtf8(const std::string& path, const PyStr& s) {
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    return false;
  }
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    writeUtf8Codepoint(out, static_cast<int32_t>(s.__getitem__(i)));
  }
  return static_cast<bool>(out);
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
    (pos == std::string::npos) ? stemOf(path) : s.substr(pos + 13);
  if (rel.size() >= 4 && rel.substr(rel.size() - 4) == ".paw") {
    rel = rel.substr(0, rel.size() - 4);
  }
  return rel;
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

static void registerRelativeImportEnums(PyEnumEmitState& est,
                                        const std::string& filePath,
                                        PySyntaxModule& mod, PyInt& nextFid) {
  const std::string dir = dirOf(filePath);
  const auto stems = listRelativeImportStems(mod);
  for (PyInt i = 0; i < stems.__len__(); i += 1) {
    const PyStr st = stems.__getitem__(i);
    std::string stemAscii;
    for (PyInt j = 0; j < st.__len__(); j += 1) {
      const int32_t cp = static_cast<int32_t>(st.__getitem__(j));
      if (cp >= 0 && cp < 128) {
        stemAscii.push_back(static_cast<char>(cp));
      }
    }
    if (stemAscii.empty()) {
      continue;
    }
    // ``../frontend/tokens`` → resolve under dir; flatten last segment for register.
    std::string depPath = dir + "/" + stemAscii + ".paw";
    std::string regStem = stemAscii;
    const auto slash = stemAscii.find_last_of('/');
    if (slash != std::string::npos) {
      regStem = stemAscii.substr(slash + 1);
    }
    const std::string raw = readFile(depPath.c_str());
    if (raw.empty()) {
      continue;
    }
    PyFileId fid{};
    fid.value = nextFid;
    nextFid += 1;
    PySyntaxModule dep = parseSource(PyStr(raw.c_str()), fid);
    est.registerModule(PyStr(regStem.c_str()), dep);
  }
}

static bool containsAscii(const PyStr& s, const char* lit) {
  return s.__contains__(PyStr(lit));
}

static int emitOne(const char* pawPath, const std::string& outDir, PyInt fileValue,
                   PyInt& nextFid) {
  const std::string raw = readFile(pawPath);
  if (raw.empty()) {
    std::printf("FAIL thin-reseed read %s\n", pawPath);
    return 1;
  }
  const std::string rel = relUnderPaw(pawPath);
  PyFileId fid{};
  fid.value = fileValue;
  PySyntaxModule mod = parseSource(PyStr(raw.c_str()), fid);
  PyEnumEmitState est = makeEnumEmitState();
  est.clear();
  est.registerModule(PyStr(stemOf(rel).c_str()), mod);
  registerRelativeImportEnums(est, pawPath, mod, nextFid);
  const PyStr mp(rel.c_str());
  const PyStr hdr = emitModuleHeader(mod, mp, est);
  const PyStr cpp = emitModuleCpp(mod, mp, est);
  if (hdr.__len__() < 20 || cpp.__len__() < 10) {
    std::printf("FAIL thin-reseed empty emit %s hdr=%lld cpp=%lld\n", pawPath,
                (long long)hdr.__len__(), (long long)cpp.__len__());
    return 1;
  }
  // Minimal fidelity gates per stem.
  if (rel.find("source") != std::string::npos) {
    if (!containsAscii(hdr, "class PySourceSpan") || !containsAscii(cpp, "makeSpan(")) {
      std::printf("FAIL thin-reseed source content\n");
      return 1;
    }
  }
  if (rel.find("emit_cpp") != std::string::npos) {
    if (!containsAscii(hdr, "emitEnum(") || !containsAscii(hdr, "emitModuleHeader(") ||
        !containsAscii(cpp, "_emitStmtSeq(")) {
      std::printf("FAIL thin-reseed emit_cpp content\n");
      return 1;
    }
  }
  if (rel.find("parser") != std::string::npos) {
    if (!containsAscii(hdr, "parseSource(") || !containsAscii(cpp, "_appendClass(")) {
      std::printf("FAIL thin-reseed parser content\n");
      return 1;
    }
  }
  const std::string outBase = outDir + "/" + rel;
  fs::create_directories(fs::path(outBase).parent_path());
  if (!writePyStrUtf8(outBase + ".h", hdr) || !writePyStrUtf8(outBase + ".cpp", cpp)) {
    std::printf("FAIL thin-reseed write %s\n", outBase.c_str());
    return 1;
  }
  std::printf("OK thin-reseed %s -> %s.{h,cpp} fn=%lld en=%lld class=%lld\n", pawPath,
              outBase.c_str(), (long long)mod.functions.__len__(),
              (long long)mod.enums.__len__(), (long long)mod.classes.__len__());
  return 0;
}

int main(int argc, char** argv) {
  if (argc < 3) {
    std::printf("usage: c1_thin_reseed_run --out DIR file.paw [...]\n");
    return 2;
  }
  std::string outDir;
  std::vector<const char*> paths;
  for (int i = 1; i < argc; i += 1) {
    const std::string a(argv[i]);
    if (a == "--out" && i + 1 < argc) {
      outDir = argv[++i];
    } else {
      paths.push_back(argv[i]);
    }
  }
  if (outDir.empty() || paths.empty()) {
    std::printf("FAIL need --out DIR and at least one .paw\n");
    return 2;
  }
  fs::create_directories(outDir);
  PyInt fid = 1;
  PyInt nextFid = 1000;
  for (const char* p : paths) {
    if (emitOne(p, outDir, fid, nextFid) != 0) {
      return 1;
    }
    fid += 1;
  }
  std::printf("OK c1_thin_reseed %zu modules -> %s\n", paths.size(), outDir.c_str());
  return 0;
}
