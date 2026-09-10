# Py2Cpp Lexer（VS Code）

将 [gpu-lexer](https://gpu-lexer.vercel.app/) **0.0.2** 封装为本地 VS Code / Cursor 插件：在 GPU 面板预览任意语言，并为 Py2Cpp 语言模式提供编辑器高亮。库代码、模型权重和 WGSL 均已随包收录，运行时不需要 npm、Python、CDN 或网络服务。

## 安装和使用

1. 从 **Extensions → … → Install from VSIX…** 安装本目录的 `py2cpp-lexer-0.1.0.vsix`。
2. 打开代码文件，执行 **Py2Cpp Lexer: Open GPU Highlight Preview**。右侧面板初始化 WebGPU 后，随当前代码文件和编辑内容更新。
3. `.py2` 默认使用 **Py2Cpp** 语言模式；GPU 面板就绪后同时获得编辑器着色。新装扩展不会自动弹出面板，可点击状态栏 **Py2Cpp Lexer** 启动。
4. 对普通 `.py` 或其他文件，执行 **Enable GPU Highlighting for Current File** 临时切换到 Py2Cpp 语言模式；可用 **Restore Previous Language Mode** 恢复本次窗口会话记录的原模式。

**只打开预览**不会改变原文件的语言模式。切换语言会影响该文件原有的 Python/Pylance 等语言服务；扩展不会全局重设 `.py` 关联或抢占 Python 的语义高亮 provider。需要长期关联时可自行配置 `files.associations`，例如将 `*.py2` 关联到 `py2cpp`。

GPU 会话属于 Webview 面板。切到别的标签页时会保留会话；关闭面板即释放会话并清除 GPU tokens。多文件共享一个推理会话，不为每个编辑器创建模型。远程工作区使用客户端 UI 扩展宿主与本机 GPU。

## 依赖与边界

- VS Code / Cursor ≥ 1.85；GPU 路径还要求当前编辑器的 Electron、显卡驱动和硬件加速支持 WebGPU。最低编辑器版本不保证机器一定有可用 GPU。
- 面板通过一次真实、非空 `parse()` 探针显示就绪状态。没有 WebGPU、GPU 初始化失败或请求超时时显示原因；可运行 **Restart GPU Session** 重试。
- `.py2` 同时带有 TextMate 基础高亮，GPU 面板未打开或不可用时仍可编辑。基础规则覆盖 Python 及拟议的 `enum`、`type match`、`property`、`inline`、`?.`、`=>` 等拼法，不提供编译器语法验证。
- gpu-lexer 是实验性的模型分类器，可能把标识符或新语法分错。它不提供 AST、类型检查、补全或诊断，也不表示本项目编译器已经支持设计文档中的新语法。
- 文件大小上限按 UTF-16 单元计算，默认 200,000；超限文件保留基础高亮，不发送 GPU 请求。中文、emoji 和 CRLF 均按 VS Code 的 UTF-16 位置转换；GPU 多行区间会拆分为单行语义 token。
- 源文件只通过本地扩展宿主与本地 Webview 通信，不执行用户源码，不写回源文件，不加载远程模型或上传代码。Webview 渲染使用文本节点，源码不会被当成 HTML 执行。

## 命令与设置

所有命令均以 **Py2Cpp Lexer:** 开头：

| 命令 | 用途 |
|---|---|
| Open GPU Highlight Preview | 打开 GPU 会话和当前文件预览 |
| Enable GPU Highlighting for Current File | 当前文件切换到 Py2Cpp 模式并开启 GPU |
| Restore Previous Language Mode | 恢复本次会话记录的原语言模式 |
| Refresh Highlighting | 重新计算当前文件 |
| Restart GPU Session | 释放旧会话并重新初始化 GPU |

| 设置 | 默认值 | 含义 |
|---|---|---|
| `py2cpp-lexer.enabled` | `true` | 是否启用 GPU 高亮/自动预览 |
| `py2cpp-lexer.debounceMs` | `250` | 编辑防抖，50–3000 ms |
| `py2cpp-lexer.maxDocumentCharacters` | `200000` | 单文件 UTF-16 长度上限，1000–1000000 |
| `py2cpp-lexer.requestTimeoutMs` | `15000` | 请求超时，1000–60000 ms；初始化上限为 30 秒 |

**Output → Py2Cpp Lexer** 显示 GPU/文件高亮错误。已取消或旧版本的结果会被丢弃；取消不会中断已经提交到 GPU 的工作。

## 打包和验证

与其他 Py2Cpp 插件一致，源代码是直接维护的 JavaScript，不要求 TypeScript 或 npm 编译。Python 3.10+ 仅用于离线打包：

```bat
pkg-lexer.bat
```

或在插件目录执行 `package.bat` / `python package.py`；支持 `--out-dir`。输出 `py2cpp-lexer-0.1.0.vsix`，包含完整 `out/`、`media/`、`syntaxes/`、`vendor/` 及许可证。

Node 单元测试：

```bat
node --test plugins/py2cpp-lexer/tests/*.test.js
```

单元测试覆盖区间转换、换行/Unicode、消息路由、取消/超时和 Webview 状态；真实 WebGPU 还需在 Extension Development Host 内验证。调试时以本目录作为 `--extensionDevelopmentPath` 启动编辑器，运行上述命令。

集成测试入口为 `tests/extensionHost.js`，可用编辑器 CLI 的 `--extensionTestsPath` 指定；建议另设临时 `--user-data-dir` 和 `--extensions-dir`。测试报告写入仓库 `.cache/py2cpp-lexer/extension-host-results.json`，测试使用未保存文档，不修改项目源文件。

2026-09-10 已在 Windows 的 Cursor（VS Code API 1.105.1）中验证实际模型推理、编辑器 Semantic Tokens、中文/emoji/CRLF 位置、编辑后更新、语言模式切换/恢复和 GPU 重启；VSIX 另在临时扩展目录完成安装。基础 grammar 通过实际 TextMate/Oniguruma 加载。这些结果不代表所有显卡或最低版本编辑器均具备 WebGPU。

## 实现与第三方代码

`out/extension.js` 管理编辑器版本与防抖；`out/gpuPanel.js` 建立限定本地资源的 Webview；`media/main.mjs` 调用原库 `parse()`，安全渲染预览；`out/semanticTokens.js` 转为 VS Code Semantic Tokens。库的九种分类映射到主题 token，`constant` 对应 `variable.readonly`。

`vendor/gpu-lexer/provenance.json` 固定发布包 SHA-512 与文件 SHA-256。上游 `dist/index.js` 仅改扩展名为 `index.mjs`，内容不变；所有模型数据内嵌其中。上游许可证声明及作者归属见 [第三方说明](./vendor/gpu-lexer/NOTICE.md)。插件自身采用 MIT。
