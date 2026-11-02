# Dawn WebGPU runtime

This directory vendors the runtime files from `webgpu` 0.6.0, published by the Dawn project. The npm archive SHA-512 was verified against the registry metadata; archive and file digests are recorded in `provenance.json`.

- Upstream: https://github.com/dawn-gpu/node-webgpu
- Native implementation: https://dawn.googlesource.com/dawn
- License: see the unmodified `LICENSE.md` and upstream licensing information.
- Bundled platforms: Windows x64/arm64, Linux x64/arm64, macOS universal. Windows runtime DLLs remain beside their matching `dawn.node`.
- `index.js`, `package.json`, `README.md`, `LICENSE.md`, and all `dist` files are unchanged. Build scripts and type declarations were omitted; no npm install or postinstall scripts were run.

The extension loads this runtime in an isolated child process for local compute inference. It does not download code or models at runtime. GPU driver and operating system support are still required; software/fallback adapters are rejected.
