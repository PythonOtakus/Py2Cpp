# Py2Cpp `spatial` 扩展设计（Rect / Color / Image / Random·Noise / Animate）

> 状态：**部分已落地**。`spatial.color`（`Color` / `ColorMatrix`）与 `spatial.rect`（`Rect`）已实现并有 `test/spatial/test_color.py`、`test_rect.py`；其余（`image` / `random` / `noise` / `animate`）仍为计划草案，实现前仍须短确认。

与现有 `py2cpp.spatial`（`Vector*` / `Matrix*` / `Rotator` / `Quaternion` / `Transform2D`·`Transform3D`）配套，补齐游戏/UI 常用的矩形、颜色、**CPU 像素图**、空间随机与噪声、以及基于注解的异步属性动画。风格参考仓库外 `tggame`（`rect` / `color` / `texture.Texture` / `random`·`Noise` / `action.LerpAssign`），写法遵守 [编码规范.md](./编码规范.md) 与 Py2Cpp 语法能力。

相关文档：[zeus设计方案.md](./zeus设计方案.md)（引擎将复用本扩展，不在 `zeus` 内重写；**GPU 纹理 / OpenGL upload** 仍属 Zeus/`render`，本模块只管 CPU 侧 `Image`）。

### 落地对照（Zeus 前置子集）

| 模块 | 源码 | 测试 | 说明 |
|------|------|------|------|
| `spatial.color` | `py2cpp/spatial/color.py` | `test/spatial/test_color.py` | `[0,1]` 钳制；`lerp`/`with_alpha`/`to_argb`/`from_argb`；矩阵用 `ColorMatrix.apply(color)`（**无** `Color.apply_matrix`，避免同类前向声明） |
| `spatial.rect` | `py2cpp/spatial/rect.py` | `test/spatial/test_rect.py` | 轴对齐；尺寸属性 **`size`**（``Vector2``；S02 对 ``Rect`` 豁免）；谓词 `contains`/`overlaps`/`embraces`；`&`/`|`；`in`；`apply_matrix(Matrix3)`；**无** `Rect @ Rect` |
| 其余 | — | — | 未实现 |

---

## 1. 目标与边界

### 1.1 目标模块

| 模块路径 | 主要类型 | 职责 |
|----------|----------|------|
| `py2cpp.spatial.rect` | `Rect`（可选 `RectAnchor`） | 2D 轴对齐矩形：位置/尺寸、锚点对齐、相交并集、点包含 |
| `py2cpp.spatial.color` | `Color`、`ColorMatrix` | 浮点 RGBA 颜色；5×5（或约定维）颜色变换矩阵 |
| `py2cpp.spatial.image` | `Image`、可选 `ImageFilter` / 区域类型 | CPU 像素缓冲：创建/填充/读写像素、子矩形、滤镜、与 `Color`/`Rect` 协作 |
| `py2cpp.spatial.random` | `Random2D`、`Random3D` | **空间采样**随机（圆/环/球/盒等），非 CPython `random` 替代 |
| `py2cpp.spatial.noise` | `Noise` | Perlin/类 Perlin 噪声（1D/2D/3D 采样） |
| `py2cpp.spatial.animate` | `AnimateMeta`、动画驱动 API | 用注解标记可动画字段/属性；异步插值驱动 |

### 1.2 与已有模块的关系

| 已有 | 关系 |
|------|------|
| `py2cpp.spatial.vector` / `matrix` | `Rect` 用 `Vector2`；`ColorMatrix` 可与矩阵语义对齐但**独立类型**（颜色空间，非几何 `Matrix4`） |
| `py2cpp.spatial.transform` | `Rect` 可提供 `apply_matrix(Matrix3)`；**不**在本扩展重做场景图 |
| `py2cpp.spatial.color` | `Image` 像素用 `Color` 读写；`ColorMatrix` 可作为 `PixelFilter` 作用于整图 |
| `py2cpp.spatial.rect` | 子图/裁剪/区域填充以 `Rect` 为界 |
| `py2cpp.math.random.Random` | **标量 PRNG**（MT19937）；`Random2D`/`Random3D` **内部组合**它做 `float`/`int`，对外只暴露空间采样 API |
| `py2cpp.concur.task` | `animate` 的「异步」优先 `async`/`await` + `Task.sleep` / 帧推进，勿另造调度器 |
| `py2cpp` `@annotation` | `AnimateMeta` 必须是 `*Meta` 后缀的 `@annotation`（见编码规范 §4.1.2） |
| `py2cpp.io` | 可选二期：从文件解码/编码（PNG 等）——第一期可不做 IO，只做内存图 |
| Zeus `render` / GL | `Image` → GPU 纹理上传在引擎层；**禁止** `spatial.image` 直接调 OpenGL |

### 1.3 第一期不做

- GPU `Texture`、采样器状态、压缩格式（属 Zeus/`opengl`）。
- 完整编解码管线（PNG/JPEG 全格式）——可二期 + `@native` 叶子或 FFI。
- tggame 级 `ImageMask` 岛屿/海岸算法、卷积核全家桶（可二期）。
- `SystemRandom`、密码学随机。
- 完整缓动曲线编辑器、时间轴 UI。
- 骨骼/变形动画、Sprite 帧动画（属引擎/`zeus` 或 media 层）。
- 在 `zeus` 内复制本扩展类型。

### 1.4 设计原则

- **勿重复造轮子**：几何用现有 `Vector*`；颜色用 `spatial.color`；标量随机用 `math.random`；协程用 `concur.task`；像素缓冲用 `uint[:,:]` / `byte[:]` 等已有数组视图，**禁止** STL `vector`。
- **`@native` 原子化**：整图 fill/blit/滤镜热点可叶子加速；编解码必为叶子；业务组合纯 Python。
- **规范写法**：`new` / `Self` / `@dataclass` / `@copyable` / `@immutable`；切片 `[:k]`；无 STL；测试 `TestCaseMixin`。
- **命名消歧**：`spatial.color.Color` vs 其它域；`spatial.random` vs `math.random`；`Image`（CPU）vs Zeus/GPU `Texture`。

---

## 2. 模块与目录规划

```text
py2cpp/spatial/
  __init__.py          # 可再导出新符号（实现时决定是否进 __all__）
  vector.py            # 已有
  matrix.py            # 已有
  rotator.py           # 已有
  transform.py         # 已有
  rect.py              # 新增 Rect
  color.py             # 新增 Color, ColorMatrix
  image.py             # 新增 Image（及可选 Filter / Area）
  random.py            # 新增 Random2D, Random3D
  noise.py             # 新增 Noise
  animate.py           # 新增 AnimateMeta + 动画 API

test/spatial/
  test_rect.py
  test_color.py
  test_image.py
  test_spatial_random.py
  test_noise.py
  test_animate.py
```

实现时：`STDLIB_REL_PATHS` 随 `py2cpp/` 发现自动纳入；bootstrap `python main.py py2cpp\__init__.py -o generated --no-main`。
---

## 3. `spatial.rect`：`Rect`

### 3.1 语义（对齐 tggame `Rect` 子集）

轴对齐矩形，常用表示：`x, y, width, height`（或 `pos`/`size` 为 `Vector2`）。

建议能力（第一期）：

| 类别 | API 示意 |
|------|----------|
| 构造 | `new(x, y, w, h)` / `from_pos_size` / `from_min_max`（已实现） |
| 属性 | `x`/`y`/`width`/`height`，`pos`/`size`，`center`，`x_min`/`x_max`/`y_min`/`y_max` |
| 变换 | `move`/`moved`，`expand`/`expanded`，`correct`/`corrected`（已实现） |
| 集合 | `intersect`，`union`，`overlaps`，`embraces`，`contains(point)` / `in`；`&`/`|`（已实现；**无** `@` overlap） |
| 对齐 | `align_pos` / 锚点（**暂未**实现） |
| 矩阵 | `apply_matrix(m: Matrix3) -> Rect`（AABB 外包，已实现） |

### 3.2 类型形态

- 推荐 `@copyable` + `@dataclass`（或显式值语义类）。
- **暂不**第一期做完整 `RectTransform`（属 `Transform2D` + UI 布局，可另案）。

### 3.3 测试要点

- 相交/并集边界、空矩形、`contains`、负宽高 `correct`、与 `Vector2` 互操作。

---

## 4. `spatial.color`：`Color` / `ColorMatrix`

### 4.1 `Color`（已实现）

- 分量：浮点 `r, g, b, a`，**钳制到 \[0,1\]**（第一期不做 HDR）。
- 已落地：`lerp` / `with_alpha` / `scaled` / `to_argb` / `from_argb`、预设 `clear`/`black`/`white`/`red`/`green`/`blue`；运算符 `+ - * / & | ~ @ **`（色×色为 Hadamard；`@` 同色×色）。
- 颜色矩阵变换走 **`matrix.apply(color)`**，不在 `Color` 上挂 `apply_matrix`（C++ 同类前向声明）。
- **像素图**：不放在本模块；见 §5 `spatial.image`。

### 4.2 `ColorMatrix`（已实现）

- 齐次 RGBA **5×5** 仿射（4 色 + 平移列）；存储 `float64[:5,:5]`。
- 已落地：`identity`/`zero`、`apply`、`__matmul__`/`__imatmul__`、`grayscale()`；加减乘除、`~`/`abs`(det)、`**`（对齐 `MatrixMixin` 路径）；饱和度/亮度预设可后置。

### 4.3 测试要点

- lerp 端点、alpha、矩阵恒等、灰度矩阵烟雾、与序列化（若 `@serializable`）往返。

---

## 5. `spatial.image`：`Image`（及滤镜子集）

### 5.1 定位

对标 tggame `Texture` / `ImageSource` 的 **CPU 侧子集**：可变尺寸的 2D 像素缓冲，供 UI 合成、软件绘制、噪声可视化、以及日后上传到 Zeus GPU 纹理。

```text
spatial.color.Color     → 单个像素 / 材质色
spatial.image.Image     → width×height 像素缓冲（CPU）
zeus render Texture     → GPU 资源（本模块不实现）
```

### 5.2 主类型 `Image`

| 类别 | API 示意 |
|------|----------|
| 构造 | `new(width, height)`；`new.filled(w, h, color)`；可选从 `span`/打包缓冲包装（实现时定） |
| 属性 | `width` / `height`；只读尺寸 |
| 像素 | `get(x, y) -> Color` / `set(x, y, color)`；越界策略：钳制或报错（实现前确认） |
| 区域 | `fill(color)`；`fill_rect(rect, color)`；`blit(src, dst_pos)` / `blit_rect(...)` |
| 拷贝 | `copy()`；`view`/`sub_image` 若做共享视图须明确所有权（第一期可只做拷贝子矩形） |
| 变换 | `apply_matrix(ColorMatrix)` 整图或 ROI；可选水平/垂直翻转（二期） |
| 采样 | 可选 `at(u, v)` 双线性（二期；软件绘制有用） |

存储建议：

- 打包像素：`uint[:,:]`（ARGB/RGBA 约定写死一种并测）或 `byte[:]` 行主序 + `stride`。
- 对外读写统一走 `Color`，避免业务直接啃 bit 布局（布局细节可藏在 `_pack` / `_unpack`）。

### 5.3 可选类型（第一期可砍到只留 `Image`）

| 类型 | 说明 | 阶段 |
|------|------|------|
| `ImageFilter` / `PixelFilter` | 对单像素或邻域的滤镜协议；`ColorMatrix` 作 `PixelFilter` 适配 | L1 适配即可 |
| `RectArea` | 矩形绘制/裁剪区域（可用 `Rect` 代替，不必新类） | 优先复用 `Rect` |
| `ImageKernel` | 卷积核 | 二期 |
| `ImageMask` | 二值掩码、岛屿分析 | 二期 |

### 5.4 与 IO / 引擎

- **第一期**：无文件编解码；测试用程序化 `fill` / 渐变生成。
- **二期**：`Image.load(path)` / `save` 经 `py2cpp.io` + 最小 `@native` 或 FFI（格式范围另定）。
- **Zeus**：`MeshComponent` / UI 可将 `Image` 上传为 GL 纹理；上传 API 不进 `spatial.image`。

### 5.5 `@native` 边界

适合叶子加速的操作：整图 `fill`、`blit`、逐像素 `ColorMatrix`、未来编解码。  
组合逻辑（「先 fill 再画几个 rect」）保持纯 Python。

### 5.6 测试要点

- 构造尺寸；`set`/`get` 往返；`fill` / `fill_rect`；`blit` 不越界与裁剪；`ColorMatrix` 整图烟雾；大图拷贝不泄漏（若 `@boxing`/`@refcount` 策略需明确）。

---

## 6. `spatial.random`：`Random2D` / `Random3D`

### 6.1 定位

**空间分布采样器**，不是 `math.random.Random` 的重命名。

```text
math.random.Random  →  next float/int/choice
spatial.Random2D    →  在圆/环/矩形等上采样 Vector2
spatial.Random3D    →  在球/壳/盒等上采样 Vector3
```

内部持有或接受 `math.random.Random`（可注入种子，便于测试可复现）。

### 6.2 API 草案

`Random2D`：

- `unit()` / `in_circle(radius)` / `in_annulus(r0, r1)` / `in_rect(Rect)` / `on_circle(radius)`
- `direction()`（单位向量）
- 可选：`lerp` 区间采样（两向量之间）

`Random3D`：

- `unit()` / `in_sphere` / `in_shell` / `in_box` / `on_sphere`
- `direction()`

命名用 `snake_case`；类名 `Random2D`/`Random3D` 保留维度后缀（与 `Vector2` 一致）。

### 6.3 与 tggame 的差异

- tggame 的 `RandVec2`/`ConstVec2`/`LerpVec2` 曲线族可作 **二期**；第一期先稳定均匀采样。
- 不移植 `nogil` Cython 细节；热点再考虑 `@native` 叶子。

### 6.4 测试要点

- 固定种子可复现；采样落在几何约束内；与 `math.random` 种子联动。

---

## 7. `spatial.noise`：`Noise`

### 7.1 语义

对标 tggame `Noise`：可重置置换表、`frequency`/`phase`，采样：

- `get(x)` / `get(x, y)` / `get(x, y, z)`（重载或分名 `sample1`/`sample2`/`sample3`，实现时择一对齐编码规范）
- 可选导数值（`get_dx` 等）作二期

返回 `float`（典型约 \[-1,1\] 或 \[0,1\]，**实现时写死一种并测**）。

可选：用 `Noise` 填充 `Image` 灰度（示范组合，测例可放 `test_image` 或独立烟雾）。

### 7.2 实现策略

- 置换表：`int[:512]` 或定长栈数组；`reset(seed)` 打乱。
- 纯 Python 可先全绿；若剖面显示热，再对插值内核 `@native`。

### 7.3 测试要点

- 同输入同输出；`reset` 改变序列；频率缩放烟雾；2D/3D 连续性抽检（邻域差分不过大）。

---

## 8. `spatial.animate`：异步属性动画 + `AnimateMeta`

### 8.1 动机

为 UI / 场景对象提供声明式「哪些字段可插值」，以及异步播放（不阻塞主逻辑线程语义上的一帧循环，而是 `await` 可组合）。

对标直觉：tggame `LerpAssign` + 协程；Py2Cpp 侧用 **`@annotation` + `iter_fields`**，而不是元类钩子。

### 8.2 `AnimateMeta`

```python
@annotation
class AnimateMeta:
  """标记字段/属性支持属性动画（插值）。"""
  # 可选字段：ease 名、默认 duration 等 —— 实现时再定是否需要载荷
  pass
```

用法示意：

```python
@dataclass
class Widget:
  x: float @AnimateMeta = 0.0
  y: float @AnimateMeta = 0.0
  color: Color @AnimateMeta = new(1.0, 1.0, 1.0, 1.0)
  name: str = "w"   # 未标记：不可 animate
```

约定：

- 仅被 `AnimateMeta` 标记的成员可进入动画 API；未标记则译期或运行时报错（**优先运行时明确错误**，若译期可检查再加强）。
- 支持类型第一期：`float` / `Vector2` / `Vector3` / `Color`（及已实现的 `@copyable` 标量聚合）；`str` 等不可插值。
- 与 `@property` 叠用：若属性可写，动画写回 setter；只读则拒绝。

### 8.3 动画驱动 API（草案）

```python
# 异步：在 Task 循环中可 await
await animate(target, "x", to=100.0, duration=0.5, ease="linear")
await animate_many(target, x=100.0, y=20.0, duration=0.3)

# 或返回可 await 的句柄，支持 cancel
handle: AnimateHandle = animate_start(target, "color", to=new(...), duration=1.0)
await handle
handle.cancel()
```

能力分级：

| 级别 | 内容 | 阶段 |
|------|------|------|
| L1 | 单字段线性插值 + `duration` + `await` | 第一期 |
| L2 | 多字段并行、`ease` 枚举（linear/quad/cubic）、cancel | 第一期或紧随 |
| L3 | 序列/并行编排（chain/group）、重复、yoyo | 二期 |
| L4 | 基于曲线表、与 Zeus `World` 时钟绑定的专用封装 | 随引擎 |

时钟：默认用 `Task.duration` / 调用方传入 `delta_time` 累加；**不**依赖全局隐藏单例（若需 `Clock`，显式注入）。

### 8.4 插值实现

- `float`：`a + (b - a) * t`
- `Vector*`：分量 lerp（复用已有向量 API，若有 `lerp` 则调用）
- `Color`：`Color.lerp`
- `t` 经 ease 映射到 \[0,1\]

### 8.5 与 Zeus / UI 的关系

- Zeus `GameObject` / `Transform` / `Color` 材质字段可标 `@AnimateMeta`，由 gameplay `await animate(...)`。
- `py2cpp.ui` 控件位置/颜色同理。
- **不**在 animate 模块内依赖 `zeus`。

### 8.6 测试要点

- 未标记字段拒绝动画；标记字段到达 `to`；cancel 中途停止；固定 dt 步进可复现；多字段并行结束同步。

---

## 9. 阶段计划

### Phase A：文档与类型清单确认

- 本文定稿；确认 `Color` 分量范围、`Noise` 输出范围、`Image` 像素打包序、`AnimateMeta` 是否需要载荷字段。

### Phase B：`rect` + `color`

- 实现与 `test/spatial/test_rect.py`、`test_color.py`；bootstrap + MSVC。

### Phase C：`image`

- `Image` 构造 / 像素 / `fill` / `fill_rect` / `blit`；`ColorMatrix` 整图；`test_image.py`。

### Phase D：`random` + `noise`

- `Random2D`/`Random3D` + `Noise`；可复现种子测试；可选噪声写入 `Image` 烟雾。

### Phase E：`animate` L1/L2

- `AnimateMeta` + `animate`/`animate_many` + cancel；`test_animate.py`。

### Phase F：文档同步

- 更新 [参考手册.md](./参考手册.md) / [编码规范.md](./编码规范.md) §8.1 模块对照；`spatial/__init__.py` 导出策略。

### Phase G（可选）：接入 Zeus / UI 示例

- UI/`Image` 软件预览或跳一跳中一处属性动画；Zeus 侧 `Image`→GL 纹理示范（引擎层）。

---

## 10. 风险与开放点

| 项 | 说明 |
|----|------|
| `Color` vs `Image` 边界 | 数值色在 `color`；缓冲在 `image`；避免 `Color` 再长出整图 API |
| `Image` 像素序 | ARGB vs RGBA 必须文档+测试写死 |
| `ColorMatrix` 维数 | 锁定 5×5 仿射需在实现前写死测试向量 |
| `Image` 所有权 | 值语义拷贝 vs `@boxing` 共享缓冲——影响 blit/子图 |
| `Random2D` 名 vs `math.random` | 包路径分离；文档强调 |
| `AnimateMeta` 译期 vs 运行时 | 第一期运行时检查足够；译期检查属增强 |
| 异步与帧循环 | 必须与现有 `Task` 模型一致，禁止第二套 `await` 运行时 |
| 性能 | `Noise`/`animate`/整图滤镜再剖面，勿预优化 `@native` |
| GPU 越界 | `spatial.image` 禁止依赖 OpenGL |

**实现前建议再确认**：

1. `Color` 是否允许 >1 的 HDR 分量。  
2. `Noise.get` 输出区间。  
3. `animate` 第一期是否必须支持 `Color`/`Vector3`，还是仅 `float`+`Vector2`。  
4. `spatial/__init__.py` 是否星式再导出新类型（倾向显式子模块 import，避免万能头膨胀）。  
5. `Image` 像素打包序（ARGB/RGBA）与越界策略（报错 vs 钳制）。  
6. `Image` 第一期是否包含双线性 `at`，还是仅整数像素。

---

## 11. 验收清单（实现完成后）

- [ ] `Rect` 几何测例全绿  
- [ ] `Color` / `ColorMatrix` 测例全绿  
- [ ] `Image` 构造/像素/fill/blit/矩阵整图测例全绿  
- [ ] `Random2D`/`Random3D` 约束与种子测例全绿  
- [ ] `Noise` 可复现与维度采样全绿  
- [ ] `@AnimateMeta` 标记字段可 `await animate`；未标记失败明确  
- [ ] 无手改 `generated/`；bootstrap + 触达测试 MSVC 通过  
- [ ] 对照编码规范自检；手册/规范模块表已更新  

---

## 12. 下一步

1. 确认 §10 开放点（含 `Image` 打包序与所有权）。  
2. 按 Phase B→E 落地源码与测试。  
3. Zeus 设计可交叉引用「CPU `Image` → GPU 纹理在引擎层完成」。
