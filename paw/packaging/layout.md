# 安装前缀布局（`$PAW_HOME`）

开发树与安装树分离。打包/本地 `tools/install_prefix`（待补）从 `out/` 收集到此前缀。

```text
$PAW_HOME/
  bin/
    paw.exe                 # CLI（开发期：python -m cmd.paw）
  lib/
    paw/                    # 标准库 + runtime 头/inl（出自 out/runtime/paw）
  include/
    paw/                    # 对外嵌入 API 子集（从 out/runtime/paw 精选）
  share/
    paw/docs/
```

| 开发树 | 安装角色 |
|--------|----------|
| `cmd/paw/` | → `bin/paw` |
| `lib/paw/` | 源；构建后产物在 `out/runtime/paw/` → `lib/paw/` |
| `host/` | 不进安装包（C0 宿主；自举后可收缩） |
| `compiler/` | 工具链私有；不进用户 `lib/paw` |
| `tools/` | 仅开发/CI |
| `extensions/` | 可选独立组件 |
| `out/` | 构建产物（gitignore） |
