import { parse } from '../vendor/gpu-lexer/index.mjs';

const vscode = acquireVsCodeApi();
const session = document.body.dataset.session;
const elements = Object.fromEntries(
    ["status", "details", "title", "summary", "code", "refresh", "restart"]
        .map((id) => [id, document.getElementById(id)]),
);
const types = new Set(["plain", "comment", "string", "number", "keyword", "type", "function", "constant", "operator"]);
const pending = new Map();
const queue = [];
let state = "starting";
let failure = "";
let running = false;
let revision = 0;

function send(message) {
    vscode.postMessage({ v: 1, ...message, session });
}

function errorText(error) {
    return error instanceof Error ? error.message : String(error);
}

function showStatus(label, detail, kind = "ready") {
    elements.status.textContent = label;
    elements.status.dataset.state = kind;
    elements.details.textContent = detail;
}

function showAvailability() {
    if (state === "unavailable") {
        showStatus("GPU 不可用", `${failure}。原编辑器的 TextMate 高亮可继续使用；可重启 GPU 后重试。`, "error");
    } else if (state === "starting") {
        showStatus("正在初始化 GPU", "正在本机执行探测推理，源码不会发送到远程服务器。", "busy");
    } else {
        showStatus("GPU 已就绪", "推理在本机 WebGPU 上运行。", "ready");
    }
}

function showDocument(metadata, elapsedMs, note) {
    elements.title.textContent = typeof metadata?.name === "string" ? metadata.name : "未命名文档";
    const version = Number.isInteger(metadata?.version) ? metadata.version : "—";
    const language = typeof metadata?.languageId === "string" ? metadata.languageId : "未知语言";
    const elapsed = elapsedMs === undefined ? "—" : `${elapsedMs.toFixed(1)} ms`;
    elements.summary.textContent = `${language} · 版本 ${version} · 推理耗时 ${elapsed}${note ? ` · ${note}` : ""}`;
}

function showPlain(source, metadata, note) {
    elements.code.textContent = source;
    showDocument(metadata, undefined, note);
}

function validateSpans(source, spans) {
    if (!Array.isArray(spans)) {
        throw new TypeError("GPU 返回的 spans 不是数组");
    }
    let end = 0;
    for (const span of spans) {
        if (!span || typeof span !== "object" || Array.isArray(span) || !types.has(span.type) ||
            !Number.isInteger(span.start) || !Number.isInteger(span.end) ||
            span.start < end || span.end < span.start || span.end > source.length) {
            throw new TypeError("GPU 返回了非法的 token 类型或 UTF-16 区间");
        }
        end = span.end;
    }
}

function showTokens(source, spans) {
    const fragment = document.createDocumentFragment();
    let offset = 0;
    for (const span of spans) {
        if (offset < span.start) {
            fragment.appendChild(document.createTextNode(source.slice(offset, span.start)));
        }
        if (span.end > span.start) {
            const token = document.createElement("span");
            token.className = `token-${span.type}`;
            token.textContent = source.slice(span.start, span.end);
            fragment.appendChild(token);
        }
        offset = span.end;
    }
    if (offset < source.length) {
        fragment.appendChild(document.createTextNode(source.slice(offset)));
    }
    elements.code.replaceChildren(fragment);
}

async function drain() {
    if (running || state !== "ready") {
        return;
    }
    running = true;
    try {
        while (queue.length > 0) {
            const task = queue.shift();
            if (task.cancelled) {
                continue;
            }
            const start = performance.now();
            if (task.revision === revision) {
                showStatus("正在推理", "请求依次执行；取消请求会丢弃结果，已提交的 GPU 工作仍会完成。", "busy");
            }
            try {
                const spans = await parse(task.source);
                if (task.cancelled) {
                    continue;
                }
                validateSpans(task.source, spans);
                const elapsedMs = performance.now() - start;
                if (task.revision === revision) {
                    showTokens(task.source, spans);
                    showDocument(task.document, elapsedMs, `${spans.length} 个区间`);
                    showAvailability();
                }
                send({ type: "result", id: task.id, spans, elapsedMs });
            } catch (error) {
                if (!task.cancelled) {
                    const message = errorText(error);
                    if (task.revision === revision) {
                        showPlain(task.source, task.document, "解析失败");
                        showStatus("GPU 解析失败", `${message}。原编辑器的 TextMate 高亮可继续使用。`, "error");
                    }
                    send({ type: "error", id: task.id, error: message });
                }
            } finally {
                pending.delete(task.id);
            }
        }
    } finally {
        running = false;
    }
}

function validId(id) {
    return (typeof id === "string" && id.length > 0) || (Number.isSafeInteger(id) && id >= 0);
}

window.addEventListener("message", ({ data }) => {
    if (!data || data.v !== 1 || data.session !== session) {
        return;
    }
    if (data.type === "preview" && typeof data.source === "string") {
        revision++;
        showPlain(data.source, data.document, state === "unavailable" ? "纯文本预览" : "等待解析");
        showAvailability();
    } else if (data.type === "cancel" && validId(data.id)) {
        const task = pending.get(data.id);
        if (task) {
            task.cancelled = true;
            const index = queue.indexOf(task);
            if (index !== -1) {
                queue.splice(index, 1);
                pending.delete(task.id);
            }
            if (task.revision === revision) {
                showDocument(task.document, undefined, "已取消");
                showStatus("请求已取消", "已提交的 GPU 工作完成后会丢弃结果。", "ready");
            }
        }
    } else if (data.type === "parse" && validId(data.id)) {
        if (typeof data.source !== "string" || pending.has(data.id)) {
            send({ type: "error", id: data.id, error: "非法源码或重复请求 ID" });
            return;
        }
        const preview = data.document?.preview !== false;
        if (preview) {
            revision++;
            showPlain(data.source, data.document, "等待解析");
        }
        if (state === "unavailable") {
            if (preview) {
                showDocument(data.document, undefined, "纯文本预览");
                showAvailability();
            }
            send({ type: "error", id: data.id, error: failure });
            return;
        }
        const task = { ...data, revision: preview ? revision : -1, cancelled: false };
        pending.set(task.id, task);
        queue.push(task);
        void drain();
    }
});

elements.refresh.addEventListener("click", () => send({ type: "refresh" }));
elements.restart.addEventListener("click", () => send({ type: "restart" }));

function finishInitialization(available, error) {
    if (state !== "starting") {
        return;
    }
    clearTimeout(initializationTimer);
    state = available ? "ready" : "unavailable";
    failure = available ? "" : errorText(error);
    showAvailability();
    send(available ? { type: "ready", available: true } : { type: "ready", available: false, error: failure });
    if (available) {
        void drain();
    } else {
        for (const task of queue.splice(0)) {
            pending.delete(task.id);
            if (!task.cancelled) {
                send({ type: "error", id: task.id, error: failure });
            }
        }
    }
}

showAvailability();
const initializationTimer = setTimeout(() => {
    finishInitialization(false, new Error("GPU 初始化超过 25 秒，请重启 GPU 后重试"));
}, 25000);
const probeSource = "const gpuLexerReady = 1;";
Promise.resolve().then(() => parse(probeSource)).then((spans) => {
    validateSpans(probeSource, spans);
    finishInitialization(true);
}).catch((error) => finishInitialization(false, error));
