# Py2Cpp Lexer（VS Code）

将 [gpu-lexer](https://gpu-lexer.vercel.app/) **0.0.2** 封装为本地 VS Code / Cursor 插件：为 Py2Cpp 语言模式自动提供后台 GPU 主高亮，并可打开独立预览。库代码、模型权重、WGSL 和 Dawn WebGPU 运行时均随包收录；Windows x64 还内置官方 Node.js 运行时及 Vulkan loader，运行时不需要 npm、Python、CDN 或网络服务。

## 安装和使用

1. 从 **Extensions → … → Install from VSIX…** 安装本目录的 `py2cpp-lexer-0.2.0.vsix`；更新后按提示重新加载编辑器窗口。
2. 打开 `.py2` 文件，默认使用 **Py2Cpp** 语言模式，并自动启动后台 GPU 高亮。无需打开预览，启动完成后状态栏显示 **Py2Cpp GPU**。
3. 执行 **Py2Cpp Lexer: Open GPU Highlight Preview** 可查看当前文件的同一份推理结果。打开、隐藏、关闭预览均不改变 `.py2` 的 GPU 会话或已生成的高亮；关闭后继续编辑仍会重新推理。
4. 对普通 `.py` 或其他文件，执行 **Enable GPU Highlighting for Current File** 临时切换到 Py2Cpp 语言模式；可用 **Restore Previous Language Mode** 恢复本次窗口会话记录的原模式。

**只打开预览**不会改变原文件的语言模式。切换语言会影响该文件原有的 Python/Pylance 等语言服务；扩展不会全局重设 `.py` 关联或抢占 Python 的语义高亮 provider。需要长期关联时可自行配置 `files.associations`，例如将 `*.py2` 关联到 `py2cpp`。

GPU 会话属于独立的普通 Node 子进程，Webview 只显示结果。多文件共享一个推理会话，不为每个编辑器创建模型；关闭最后一个 Py2Cpp 文档和预览、禁用 GPU、退出扩展或显式重启时释放会话。普通 Python 文件只有显式打开预览或切换语言后才交给本插件处理。远程工作区使用客户端 UI 扩展宿主与本机 GPU。

## 依赖与边界

- VS Code / Cursor ≥ 1.85；Windows x64 使用随包 Node.js **24.19.0** 和 Dawn **webgpu 0.6.0**，需要支持 Vulkan 的实际显卡及驱动。后台运行不依赖 Webview 的 WebGPU 或编辑器硬件加速开关。
- macOS、Linux 和 Windows ARM64 包含对应 Dawn 模块，但需要普通 Node.js 18+（PATH 中的 `node`，或机器设置 `py2cpp-lexer.nodePath`）。仅 Windows x64 经过实际编辑器与硬件验证；平台驱动和动态库要求仍以 Dawn 为准。
- 后台通过一次真实、非空 `parse()` 探针确认就绪，拒绝软件/fallback adapter。初始化失败、设备丢失、子进程退出或单次请求超时会显示原因；可运行 **Restart GPU Session** 重试，不会无限自动重启或弹出预览。
- `.py2` 同时带有 TextMate 基础高亮，在后台初始化、GPU 不可用、关闭设置或文件超限时回退。GPU 分类作为 Semantic Tokens 覆盖基础规则，模型标记 plain 的位置仍由基础规则显示；预览开关不再切换高亮来源。基础规则不提供编译器语法验证。
- gpu-lexer 是实验性的模型分类器，可能把标识符或新语法分错。它不提供 AST、类型检查、补全或诊断，也不表示本项目编译器已经支持设计文档中的新语法。
- 文件大小上限按 UTF-16 单元计算，默认 200,000；超限文件保留基础高亮，不发送 GPU 请求。中文、emoji 和 CRLF 均按 VS Code 的 UTF-16 位置转换；GPU 多行区间会拆分为单行语义 token。
- 源文件只通过本地扩展宿主、后台子进程及可选预览通信，不执行用户源码，不写回源文件，不加载远程模型或上传代码。子进程通过 IPC 收取源码字符串，Webview 渲染使用文本节点。原生崩溃与扩展宿主隔离，Windows 后台进程不弹出控制台。

## 命令与设置

所有命令均以 **Py2Cpp Lexer:** 开头：

| 命令 | 用途 |
|---|---|
| Open GPU Highlight Preview | 显示当前文件的 GPU 结果；关闭不影响 Py2Cpp 高亮 |
| Enable GPU Highlighting for Current File | 当前文件切换到 Py2Cpp 模式并开启后台 GPU，不弹预览 |
| Restore Previous Language Mode | 恢复本次会话记录的原语言模式 |
| Refresh Highlighting | 重新计算当前文件 |
| Restart GPU Session | 释放旧会话并重新初始化 GPU |

| 设置 | 默认值 | 含义 |
|---|---|---|
| `py2cpp-lexer.enabled` | `true` | 是否自动启用后台 GPU 高亮 |
| `py2cpp-lexer.nodePath` | 空 | 可选普通 Node 可执行路径；机器级设置，不能由项目覆写 |
| `py2cpp-lexer.debounceMs` | `250` | 编辑防抖，50–3000 ms |
| `py2cpp-lexer.maxDocumentCharacters` | `200000` | 单文件 UTF-16 长度上限，1000–1000000 |
| `py2cpp-lexer.requestTimeoutMs` | `15000` | 请求超时，1000–60000 ms；初始化上限为 30 秒 |

**Output → Py2Cpp Lexer** 显示 GPU/文件高亮错误。已取消或旧版本的结果会被丢弃；取消不会中断已经提交到 GPU 的工作。

## 打包和验证

与其他 Py2Cpp 插件一致，源代码是直接维护的 JavaScript，不要求 TypeScript 或 npm 编译。Python 3.10+ 仅用于离线打包：

```bat
pkg-lexer.bat
```

或在插件目录执行 `package.bat` / `python package.py`；支持 `--out-dir`。输出 `py2cpp-lexer-0.2.0.vsix`，包含完整 `out/`、`media/`、`syntaxes/`、`vendor/` 及许可证。内置 Node 和原生 GPU 模块后包体积明显增加；打包过程离线，不运行第三方安装脚本。维护脚本的依赖下载须手动调用，并验证官方固定哈希。

Node 单元测试：

```bat
node --test plugins/py2cpp-lexer/tests/*.test.js
```

单元测试覆盖自动启动/多文档/预览独立生命周期、区间转换、换行/Unicode、IPC 路由、取消/超时、原生崩溃/设备丢失与被动预览状态。调试时以本目录作为 `--extensionDevelopmentPath` 启动编辑器，验证真实 GPU 与 Semantic Tokens。

集成测试入口为 `tests/extensionHost.js`，可用编辑器 CLI 的 `--extensionTestsPath` 指定；另设临时 `--user-data-dir` 和 `--extensions-dir`，并以项目目录作为位置参数启动普通工作区窗口。测试报告写入仓库 `.cache/py2cpp-lexer/extension-host-results.json`，测试文件位于同一缓存目录，另使用未保存文档验证语言切换。

0.2.0 已通过 54 项单元测试，并在 Windows x64、Cursor（VS Code API 1.105.1）、NVIDIA RTX 5060 / Vulkan 上通过六项集成检查：不开预览自动高亮、多文档高亮、开关预览保持同一 GPU 会话与完全相同的 tokens、关闭预览后编辑更新、Python 语言启用/恢复、重启刷新所有文档。纯随包运行时处理完整 `lexer_preview.py2` 约 4 ms，已验证取消、重启及退出时释放进程；时间随文件、显卡与驱动变化。基础 grammar 的 TextMate/Oniguruma 验证不代替 GPU 验证。

## 实现与第三方代码

`out/extension.js` 管理文档、版本、防抖和消费者生命周期；`out/gpuRuntime.js` 管理独立进程，`out/gpuWorker.mjs` 加载 Dawn 和原库 `parse()`。`out/gpuPanel.js` 与 `media/main.mjs` 仅显示由 controller 提供的快照，前端不再加载模型。`out/semanticTokens.js` 转为 VS Code Semantic Tokens；`constant` 对应 `variable.readonly`。预览的 CSS 颜色仍由预览主题映射决定，编辑器颜色由 Semantic Tokens 主题决定。

`vendor/gpu-lexer/provenance.json` 固定发布包 SHA-512 与文件 SHA-256。上游 `dist/index.js` 仅改扩展名为 `index.mjs`，内容不变；所有模型数据内嵌其中。上游许可证声明及作者归属见 [第三方说明](./vendor/gpu-lexer/NOTICE.md)。插件自身采用 MIT。

新增原生依赖的官方来源、版本、逐文件哈希及许可证分别位于 `vendor/webgpu/`、`vendor/node/`、`vendor/vulkan/`。Windows 使用随包的公开发行组件，不复制编辑器私有 DLL；系统仍须安装匹配的显卡驱动。
