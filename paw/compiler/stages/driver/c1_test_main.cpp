// Native test-entry emit (flat c2_native amalgamation).
//   c1_test_main --out DIR tests/.../test_*.paw [...]
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
#include "frontend/type_parse.cpp"
#include "frontend/param_parse.cpp"
#include "frontend/stmt_parse.cpp"
#include "frontend/parser.cpp"
#include "mid/emit_cpp.cpp"

namespace fs = std::filesystem;

static std::string readFile(const char* path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return {};
  }
  std::string raw((std::istreambuf_iterator<char>(in)),
                  std::istreambuf_iterator<char>());
  std::string out;
  out.reserve(raw.size());
  for (char ch : raw) {
    if (ch != '\r') {
      out.push_back(ch);
    }
  }
  return out;
}

static void writeUtf8Codepoint(std::ofstream& out, int32_t cp) {
  if (cp < 0) {
    return;
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

/** ``tests/lang/test_empty_main.paw`` → ``tests/lang/test_empty_main``. */
static std::string modulePathOfTest(const std::string& path) {
  std::string s = path;
  for (char& c : s) {
    if (c == '\\') {
      c = '/';
    }
  }
  const char* marker = "tests/";
  const auto pos = s.find(marker);
  std::string rel = (pos == std::string::npos) ? s : s.substr(pos);
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

static std::string pyStrToStd(const PyStr& s) {
  std::string out;
  out.reserve(static_cast<size_t>(s.__len__()));
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    out.push_back(static_cast<char>(static_cast<int32_t>(s.__getitem__(i))));
  }
  return out;
}

static int emitOnePath(const char* pawPath, const std::string& outRoot, PyInt fileValue) {
  const std::string raw = readFile(pawPath);
  if (raw.empty()) {
    std::printf("FAIL read %s\n", pawPath);
    return 1;
  }
  const std::string mp = modulePathOfTest(pawPath);
  PyFileId fid{};
  fid.value = fileValue;
  PySyntaxModule mod = parseSource(PyStr(raw.c_str()), fid);
  PyEnumEmitState est = makeEnumEmitState();
  est.clear();
  est.registerModule(PyStr(stemOf(mp).c_str()), mod);
  const PyStr mps(mp.c_str());
  const PyStr hdr = emitModuleHeader(mod, mps, est);
  const PyStr cpp = emitModuleCpp(mod, mps, est);
  const std::string outBase = outRoot + "/" + mp;
  fs::create_directories(fs::path(outBase).parent_path());
  if (!writePyStrUtf8(outBase + ".h", hdr) || !writePyStrUtf8(outBase + ".cpp", cpp)) {
    std::printf("FAIL write %s\n", outBase.c_str());
    return 1;
  }
  std::printf("OK test-emit %s -> %s.{h,cpp} fn=%lld class=%lld\n", pawPath, outBase.c_str(),
              (long long)mod.functions.__len__(), (long long)mod.classes.__len__());

  // Relative imports: ``from .helper import …`` → also emit sibling ``helper.paw``.
  PyList<PyStr, 0> stems = listRelativeImportStems(mod);
  const std::string srcDir = dirOf(pawPath);
  const std::string mpDir = dirOf(mp);
  for (PyInt si = 0; si < stems.__len__(); si += 1) {
    const std::string relStem = pyStrToStd(stems.__getitem__(si));
    // Only same-dir single-segment helpers (``.helper`` → ``helper``).
    if (relStem.find('/') != std::string::npos || relStem.find('\\') != std::string::npos) {
      continue;
    }
    if (relStem.find("..") != std::string::npos) {
      continue;
    }
    const std::string depPaw = srcDir + "/" + relStem + ".paw";
    if (!fs::exists(depPaw)) {
      continue;
    }
    const std::string depMp = mpDir + "/" + relStem;
    const std::string depRaw = readFile(depPaw.c_str());
    if (depRaw.empty()) {
      std::printf("FAIL read dep %s\n", depPaw.c_str());
      return 1;
    }
    PyFileId dfid{};
    dfid.value = fileValue + 1000 + si;
    PySyntaxModule dmod = parseSource(PyStr(depRaw.c_str()), dfid);
    PyEnumEmitState dest = makeEnumEmitState();
    dest.clear();
    dest.registerModule(PyStr(relStem.c_str()), dmod);
    const PyStr dmps(depMp.c_str());
    const PyStr dhdr = emitModuleHeader(dmod, dmps, dest);
    const PyStr dcpp = emitModuleCpp(dmod, dmps, dest);
    const std::string depOut = outRoot + "/" + depMp;
    fs::create_directories(fs::path(depOut).parent_path());
    if (!writePyStrUtf8(depOut + ".h", dhdr) || !writePyStrUtf8(depOut + ".cpp", dcpp)) {
      std::printf("FAIL write dep %s\n", depOut.c_str());
      return 1;
    }
    std::printf("OK dep-emit %s -> %s.{h,cpp}\n", depPaw.c_str(), depOut.c_str());
  }
  return 0;
}

int main(int argc, char** argv) {
  std::string outDir;
  std::vector<const char*> paths;
  for (int i = 1; i < argc; i += 1) {
    const std::string a(argv[i]);
    if ((a == "--out" || a == "--test-out") && i + 1 < argc) {
      outDir = argv[++i];
    } else {
      paths.push_back(argv[i]);
    }
  }
  if (outDir.empty() || paths.empty()) {
    std::printf("usage: c1_test_main --out DIR tests/.../test_*.paw [...]\n");
    return 2;
  }
  fs::create_directories(outDir);
  PyInt fid = 1;
  for (const char* p : paths) {
    if (emitOnePath(p, outDir, fid) != 0) {
      return 1;
    }
    fid += 1;
  }
  return 0;
}
