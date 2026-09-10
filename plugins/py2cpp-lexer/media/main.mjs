const vscode = acquireVsCodeApi();
const session = document.body.dataset.session;
const elements = Object.fromEntries(
    ["status", "details", "title", "summary", "code", "refresh", "restart"]
        .map((id) => [id, document.getElementById(id)]),
);
const types = new Set(["plain", "comment", "string", "number", "keyword", "type", "function", "constant", "operator"]);

function send(message) {
    vscode.postMessage({ v: 1, ...message, session });
}

function showStatus(label, detail, kind = "ready") {
    elements.status.textContent = label;
    elements.status.dataset.state = kind;
    elements.details.textContent = detail;
}

function showAvailability(snapshot) {
    const failure = typeof snapshot.error === "string" ? snapshot.error : "";
    const backend = typeof snapshot.backend === "string" && snapshot.backend ? `（${snapshot.backend}）` : "";
    if (snapshot.enabled === false || snapshot.state === "disabled") {
        showStatus("GPU 高亮已禁用", "在设置中启用 Py2Cpp Lexer 后，后台 GPU 将自动提供编辑器高亮。", "disabled");
    } else if (snapshot.state === "unavailable") {
        showStatus("GPU 不可用", `${failure ? `${failure}。` : ""}暂用 TextMate 基础高亮；可重启后台 GPU 后重试。`, "error");
    } else if (snapshot.state === "starting") {
        showStatus("正在初始化后台 GPU", "正在本机加载模型并执行探测推理；关闭预览不会中断初始化，源码仅在本地处理。", "busy");
    } else if (snapshot.state === "busy" || snapshot.pending === true) {
        showStatus("后台 GPU 正在推理", `推理在本机 GPU${backend} 上运行；关闭预览不影响编辑器高亮。`, "busy");
    } else if (failure) {
        showStatus("GPU 解析失败", `${failure}。后台会话保留，可刷新后重试。`, "error");
    } else if (snapshot.state === "ready") {
        showStatus("后台 GPU 已就绪", `编辑器使用本机 GPU${backend} 高亮；关闭预览后继续运行，源码仅在本地处理。`);
    } else {
        showStatus("正在连接后台 GPU", "此标签页仅显示后台高亮结果；关闭预览不影响编辑器高亮。", "busy");
    }
}

function showDocument(metadata, elapsedMs, note) {
    elements.title.textContent = typeof metadata?.name === "string" ? metadata.name : "未命名文档";
    const version = Number.isSafeInteger(metadata?.version) && metadata.version >= 0 ? metadata.version : "—";
    const language = typeof metadata?.languageId === "string" ? metadata.languageId : "未知语言";
    const elapsed = Number.isFinite(elapsedMs) && elapsedMs >= 0 ? `${elapsedMs.toFixed(1)} ms` : "—";
    elements.summary.textContent = `${language} · 版本 ${version} · 推理耗时 ${elapsed}${note ? ` · ${note}` : ""}`;
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

function showSnapshot(snapshot) {
    showAvailability(snapshot);
    if (typeof snapshot.source !== "string") {
        elements.code.textContent = "";
        elements.title.textContent = "打开代码文件以预览";
        elements.summary.textContent = "";
        return;
    }
    const note = typeof snapshot.note === "string" ? snapshot.note : "";
    elements.code.textContent = snapshot.source;
    if (snapshot.spans === undefined) {
        showDocument(snapshot.document, snapshot.elapsedMs, note || (snapshot.pending ? "等待解析" : "纯文本预览"));
        return;
    }
    try {
        validateSpans(snapshot.source, snapshot.spans);
        showTokens(snapshot.source, snapshot.spans);
        showDocument(snapshot.document, snapshot.elapsedMs, note || `${snapshot.spans.length} 个区间`);
    } catch (error) {
        showDocument(snapshot.document, undefined, "纯文本预览");
        showStatus("GPU 结果无效", `${error.message}；仅显示原始源码，可刷新后台 GPU 后重试。`, "error");
    }
}

window.addEventListener("message", ({ data }) => {
    if (!data || data.v !== 1 || data.session !== session || data.type !== "snapshot" ||
        !data.snapshot || typeof data.snapshot !== "object" || Array.isArray(data.snapshot)) {
        return;
    }
    showSnapshot(data.snapshot);
});

elements.refresh.addEventListener("click", () => send({ type: "refresh" }));
elements.restart.addEventListener("click", () => send({ type: "restart" }));

// The extension owns inference. A ready handshake requests the latest snapshot,
// including after a reload, instead of relying on messages sent before startup.
send({ type: "ready" });
