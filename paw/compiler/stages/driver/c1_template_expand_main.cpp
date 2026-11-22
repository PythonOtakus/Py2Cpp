// Native frozen template expand (BEGIN/ECHO/EVAL + for-list).
//   c1_template_expand_main --in FILE --out FILE
// Rejects PY2CPP_EXEC / PY2CPP_BEGIN(def) (still host; ~test showcase only).
#include <cstdio>
#include <fstream>
#include <string>

#include "codegen/template_profile.cpp"
#include "codegen/template_eval.cpp"
#include "codegen/template_expand.cpp"

// Thin mid_emit of codegen/* is flat (no compiler::paw::codegen namespace).
using paw::PyStr;

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

static bool writeUtf8(const std::string& path, const PyStr& s) {
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    return false;
  }
  for (PyInt i = 0; i < s.__len__(); i += 1) {
    const int32_t cp = static_cast<int32_t>(s.__getitem__(i));
    if (cp < 0) {
      return false;
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
  return static_cast<bool>(out);
}

static bool containsAscii(const std::string& s, const char* needle) {
  return s.find(needle) != std::string::npos;
}

static bool pathLooksLike(const char* path, const char* needle) {
  std::string p = path;
  for (char& c : p) {
    if (c == '\\') {
      c = '/';
    }
  }
  return p.find(needle) != std::string::npos;
}

// 对位 host/constant/stdlib_modules.py::UMBRELLA_MSVC_UNDEF_MACROS*
static void seedMsvcUndefLists(PyListCtx& listCtx) {
  listCtx.start(PyStr("msvc_undef_macros_early"));
  listCtx.add(PyStr("Yield"));
  listCtx.add(PyStr("Return"));

  listCtx.start(PyStr("msvc_undef_macros"));
  const char* macros[] = {
      "isascii", "parent",  "suffix",  "environ", "date",   "time",
      "hour",    "minute",  "second",  "min",     "max",    "unlink",
      "remove",  "rename",  "replace", "small",   "stat",   "S_IFMT",
      "S_IFDIR", "S_IFCHR", "S_IFBLK", "S_IFREG", "S_IFIFO", "S_IFLNK",
      "S_IFSOCK","stdin",   "stdout",  "stderr",  "popen",  "OPAQUE",
      "Yield",   "Return",
  };
  for (const char* m : macros) {
    listCtx.add(PyStr(m));
  }
}

static void seedEmptyUmbrellaEcho(PyStringCtx& strCtx) {
  strCtx.put(PyStr("ctx_DebugBlock"), PyStr(""));
  strCtx.put(PyStr("ctx_UmbrellaBodyBefore"), PyStr(""));
  strCtx.put(PyStr("ctx_UmbrellaBodyMid"), PyStr(""));
  strCtx.put(PyStr("ctx_UmbrellaBodyIoLate"), PyStr(""));
}

int main(int argc, char** argv) {
  const char* inPath = nullptr;
  const char* outPath = nullptr;
  for (int i = 1; i < argc; i += 1) {
    const std::string a = argv[i];
    if (a == "--in" && i + 1 < argc) {
      inPath = argv[++i];
    } else if (a == "--out" && i + 1 < argc) {
      outPath = argv[++i];
    }
  }
  if (inPath == nullptr || outPath == nullptr) {
    std::printf("usage: c1_template_expand_main --in FILE --out FILE\n");
    return 2;
  }
  const std::string raw = readFile(inPath);
  if (raw.empty()) {
    std::printf("FAIL read %s\n", inPath);
    return 1;
  }
  if (containsAscii(raw, "PY2CPP_EXEC") ||
      containsAscii(raw, "PY2CPP_BEGIN(def") ||
      containsAscii(raw, "PY2CPP_BEGIN( def")) {
    std::printf("SKIP host-only EXEC/def: %s\n", inPath);
    return 3;
  }
  try {
    PyEvalCtx intCtx{};
    PyStringCtx strCtx{};
    PyListCtx listCtx{};
    if (pathLooksLike(inPath, "minimal.h")) {
      seedMsvcUndefLists(listCtx);
      seedEmptyUmbrellaEcho(strCtx);
    }
    const PyStr expanded =
        expandTemplateFrozen(PyStr(raw.c_str()), intCtx, strCtx, listCtx);
    if (!writeUtf8(outPath, expanded)) {
      std::printf("FAIL write %s\n", outPath);
      return 1;
    }
    std::printf("OK frozen-expand %s -> %s\n", inPath, outPath);
    return 0;
  } catch (const std::exception& e) {
    std::printf("FAIL expand %s: %s\n", inPath, e.what());
    return 1;
  }
}
