# Vulkan loader for Windows x64

The unmodified Vulkan loader in `../webgpu/dist/win32-x64/vulkan-1.dll` comes
from LunarG's official Windows runtime components ZIP, version `1.4.357.0`.
It is placed next to Dawn's native module so its explicit library search can
find the loader. It uses the user's installed GPU driver for Vulkan compute.

- Upstream: https://github.com/KhronosGroup/Vulkan-Loader
- Publisher/download page: https://vulkan.lunarg.com/sdk/home
- Official file metadata (including archive SHA-256): https://vulkan.lunarg.com/sdk/files.json
- Archive: https://sdk.lunarg.com/sdk/download/1.4.357.0/windows/VulkanRT-X64-1.4.357.0-Components.zip
- Archive bytes: 18134567
- Archive SHA-256: `a14672efed15aafc7f5a16572d35cd3a3416eadf670aeee3cdf50ee32d5fbf83`
- Original member: `VulkanRT-X64-1.4.357.0-Components/x64/vulkan-1.dll`
- Loader SHA-256: `cd862090370454630b31b174e3d4eb474fda38ea034998d1fe1767b0c99a8696`
- Binary format: PE32+ / AMD64 (`0x8664`).

`licenses/VulkanRT-License.txt` is the entire license file supplied in the
runtime ZIP, copied byte-for-byte. It includes the upstream copyright notices,
MIT license texts, and an Apache 2.0 reference. `licenses/Apache-2.0.txt` contains
the complete Apache 2.0 license, copied unchanged from https://www.apache.org/licenses/LICENSE-2.0.txt.
These files cover the loader's upstream MIT and Apache-2.0 components.

Only the x64 loader and licenses are shipped: x86 DLLs, debug symbols, diagnostic
executables, and installers are omitted. No system DLLs or editor-private files
supply this published dependency. The loader is not an installer and is never
copied into Windows system directories. Other platforms use their native
system backends. GPU hardware and a compatible installed driver are required.

`provenance.json` records archive members, source URLs, byte lengths, and SHA-256
digests. Its file paths are relative to the extension root. This notice and the
provenance manifest are generated locally; upstream DLL and license bytes are
unchanged.

Maintenance:
- `python scripts/vendor-vulkan.py --archive PATH --apache-license PATH`
  reproduces the vendored files from verified local inputs.
- `python scripts/vendor-vulkan.py --download` explicitly downloads the pinned
  runtime ZIP and the Apache license before verification.
- `python scripts/vendor-vulkan.py --verify` checks the installed file hashes
  and PE machine offline without writing.

Normal extension packaging and runtime inference perform no downloads.
