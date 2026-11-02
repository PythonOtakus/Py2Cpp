// An isolated ordinary Node process owns WebGPU. The preview never owns a device.
const session = process.argv[2];
const types = new Set(["plain", "comment", "string", "number", "keyword", "type", "function", "constant", "operator"]);
const queue = [];
const pending = new Map();
let device;
let gpu;
let parse;
let running = false;
let stopping = false;
let ready = false;

function errorText(error) {
  return error instanceof Error ? error.message : String(error);
}

function send(message, callback) {
  if (!process.connected) return shutdown();
  try {
    process.send({ v: 1, session, ...message }, (error) => {
      if (error) shutdown();
      else callback?.();
    });
  } catch { shutdown(); }
}

function shutdown() {
  if (stopping) return;
  stopping = true;
  ready = false;
  pending.clear();
  queue.length = 0;
  const ownedDevice = device;
  device = undefined;
  try { ownedDevice?.destroy(); } catch { /* The driver may have already lost it. */ }
  gpu = undefined;
  delete globalThis.navigator;
  // The upstream module retains its device and internal buffer cache. Exiting
  // also frees those native references without changing the vendored model.
  process.exit(0);
}

function fatal(error) {
  if (stopping) return;
  ready = false;
  send({ type: "fatal", error: errorText(error) }, shutdown);
  setTimeout(shutdown, 100).unref();
}

function validateSpans(source, spans) {
  if (!Array.isArray(spans)) throw new TypeError("GPU spans must be an array");
  let previous = 0;
  for (const span of spans) {
    if (!span || typeof span !== "object" || !types.has(span.type) ||
        !Number.isSafeInteger(span.start) || !Number.isSafeInteger(span.end) ||
        span.start < previous || span.end < span.start || span.end > source.length) {
      throw new TypeError("GPU returned invalid token types or UTF-16 ranges");
    }
    previous = span.end;
  }
}

function hardwareAdapter(adapter) {
  const info = adapter.info;
  const fallback = info?.isFallbackAdapter ?? adapter.isFallbackAdapter;
  const description = [info?.vendor, info?.architecture, info?.device, info?.description].filter(Boolean).join(" ");
  if (fallback !== false || /swiftshader|lavapipe|llvmpipe|software|microsoft basic render|\bwarp\b/i.test(description)) {
    throw new Error("A hardware GPU adapter is required; software/fallback adapters are not used");
  }
  return info?.device || info?.description || info?.vendor || "hardware GPU";
}

async function initialize() {
  if (process.versions?.electron) {
    throw new Error("The GPU worker requires ordinary Node.js; select a Node executable instead of an Electron editor executable");
  }
  const { create, globals } = await import("../vendor/webgpu/index.js");
  Object.assign(globalThis, globals);
  // This Dawn build's Windows FXC path cannot compile all model shaders.
  // Vulkan is preferred there; D3D12 remains a fallback for other driver builds.
  const backends = process.platform === "darwin" ? ["metal"] :
    process.platform === "win32" ? ["vulkan", "d3d12"] : ["vulkan"];
  const failures = [];
  for (const backend of backends) {
    let candidate;
    try {
      gpu = create([`backend=${backend}`]);
      const adapter = await gpu.requestAdapter({ powerPreference: "high-performance", forceFallbackAdapter: false });
      if (!adapter) throw new Error("No compatible GPU adapter");
      const adapterName = hardwareAdapter(adapter);
      candidate = await adapter.requestDevice({
        requiredFeatures: adapter.features.has("shader-f16") ? ["shader-f16"] : [],
        requiredLimits: {
          maxBufferSize: adapter.limits.maxBufferSize,
          maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize,
        },
      });
      device = candidate;
      candidate.lost.then((info) => {
        if (device === candidate && !stopping) fatal(`GPU device lost: ${info.message || info.reason}`);
      }, (error) => { if (device === candidate) fatal(error); });
      // Supplying the already-owned device lets us observe loss and destroy it
      // without adding an API or changing any bytes of the upstream model.
      Object.defineProperty(globalThis, "navigator", { configurable: true, value: { gpu: {
        requestAdapter: async () => ({
          features: candidate.features,
          limits: candidate.limits,
          requestDevice: async () => candidate,
        }),
      } } });
      const moduleUrl = new URL("../vendor/gpu-lexer/index.mjs", import.meta.url);
      moduleUrl.searchParams.set("backend", backend);
      const model = await import(moduleUrl.href);
      const probe = "def gpuLexerReady(x: int) -> int:\n    return x + 1\n";
      const spans = await model.parse(probe);
      validateSpans(probe, spans);
      if (spans.length === 0) throw new Error("GPU probe returned no tokens");
      parse = model.parse;
      ready = true;
      send({ type: "ready", available: true, backend: `${backend} · ${adapterName}` });
      return;
    } catch (error) {
      failures.push(`${backend}: ${errorText(error)}`);
      if (device === candidate) device = undefined;
      try { candidate?.destroy(); } catch { /* Failed initialization already lost the device. */ }
      gpu = undefined;
    }
  }
  throw new Error(failures.join("; "));
}

async function drain() {
  if (running || !ready || stopping) return;
  running = true;
  try {
    while (queue.length && ready && !stopping) {
      const task = queue.shift();
      if (task.cancelled) continue;
      const started = performance.now();
      try {
        const spans = await parse(task.source);
        if (task.cancelled || stopping || !ready) continue;
        validateSpans(task.source, spans);
        send({ type: "result", id: task.id, spans, elapsedMs: performance.now() - started });
      } catch (error) {
        if (!task.cancelled && !stopping) send({ type: "error", id: task.id, error: errorText(error) });
      } finally {
        pending.delete(task.id);
      }
    }
  } finally {
    running = false;
  }
}

process.on("message", (message) => {
  if (!message || message.v !== 1 || message.session !== session || stopping) return;
  if (message.type === "stop") return shutdown();
  if (!Number.isSafeInteger(message.id) || message.id < 0) return;
  if (message.type === "cancel") {
    const task = pending.get(message.id);
    if (task) {
      task.cancelled = true;
      const index = queue.indexOf(task);
      if (index !== -1) { queue.splice(index, 1); pending.delete(task.id); }
    }
  } else if (message.type === "parse") {
    if (!ready || typeof message.source !== "string" || message.source.length > 1000000 || pending.has(message.id)) {
      send({ type: "error", id: message.id, error: "GPU is not ready, source exceeds the limit, or request ID is duplicated" });
      return;
    }
    const task = { id: message.id, source: message.source, cancelled: false };
    pending.set(task.id, task);
    queue.push(task);
    void drain();
  }
});

process.on("disconnect", shutdown);
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
process.on("uncaughtException", fatal);
process.on("unhandledRejection", fatal);

if (!process.send || !session) process.exit(1);
initialize().catch((error) => {
  send({ type: "ready", available: false, error: errorText(error) }, shutdown);
});
