"""场景对象模型：``Component`` / ``Transform`` / ``GameObject``（同模块避免循环依赖）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color
from py2cpp.spatial.matrix import Matrix4
from py2cpp.spatial.rotator import Quaternion
from py2cpp.spatial.transform import Transform3D
from py2cpp.spatial.vector import Vector3

from .assets.fbx_ascii import read_fbx
from .render.mesh import Mesh


@mixin
class GameNodeMixin:
  """对象树节点公共开关。"""

  active: bool = True
  visible: bool = True

  def enable(self) -> None:
    self.active = True

  def disable(self) -> None:
    self.active = False

  def show(self) -> None:
    self.visible = True

  def hide(self) -> None:
    self.visible = False


@refcount
class Component:
  """挂在 ``GameObject`` 上的逻辑组件。"""

  kind: str = "Component"
  enabled: bool = True
  asset_path: str = ""
  _owner: GameObject | None = None

  @property
  @immutable
  def owner(self) -> GameObject | None:
    return self._owner

  def bind_owner(self, go: GameObject) -> None:
    self._owner = go

  def unbind_owner(self) -> None:
    self._owner = None

  @virtual
  def on_create(self) -> None:
    pass

  @virtual
  def on_update(self, dt: float64) -> None:
    pass

  @virtual
  def on_draw(self) -> None:
    pass

  @virtual
  def on_destroy(self) -> None:
    pass


@refcount
class Transform(Component):
  """场景组件；数学委托 ``Transform3D``。"""

  space: Transform3D = new("transform")

  def __init__(self):
    self.kind = "Transform"
    self.enabled = True
    self._owner = None
    self.space = new("transform")

  @property
  @immutable
  def name(self) -> str:
    return self.space.name

  @property.setter
  def name(self, value: str) -> None:
    self.space.name = value

  @property
  @immutable
  def local_position(self) -> Vector3:
    return self.space.local_position

  @property.setter
  def local_position(self, value: Vector3) -> None:
    self.space.local_position = value

  @property
  @immutable
  def local_rotation(self) -> Quaternion:
    return self.space.local_rotation

  @property.setter
  def local_rotation(self, value: Quaternion) -> None:
    self.space.local_rotation = value

  @property
  @immutable
  def local_scale(self) -> Vector3:
    return self.space.local_scale

  @property.setter
  def local_scale(self, value: Vector3) -> None:
    self.space.local_scale = value

  @property
  @immutable
  def position(self) -> Vector3:
    return self.space.position

  @property.setter
  def position(self, value: Vector3) -> None:
    self.space.position = value

  @property
  @immutable
  def rotation(self) -> Quaternion:
    return self.space.rotation

  @property.setter
  def rotation(self, value: Quaternion) -> None:
    self.space.rotation = value

  @property
  @immutable
  def scale(self) -> Vector3:
    return self.space.scale

  @property
  @immutable
  def local_to_world_matrix(self) -> Matrix4:
    return self.space.local_to_world_matrix

  def attach(self, child: Self) -> None:
    self.space.attach(child.space)

  def detach(self, child: Self) -> None:
    self.space.detach(child.space)

  def translate(self, delta: Vector3) -> None:
    self.space.translate(delta)


@refcount
class MeshComponent(Transform):
  """``Transform`` + ``Mesh``；模型资产路径为 ``.fbx``。"""

  has_mesh: bool = False
  mesh: Mesh = new()
  color: Color = new(0.2, 0.6, 0.9, 1.0)

  def __init__(self):
    self.kind = "MeshComponent"
    self.enabled = True
    self.asset_path = ""
    self._owner = None
    self.space = new("transform")
    self.has_mesh = False
    self.mesh = new()
    self.color = new(0.2, 0.6, 0.9, 1.0)

  def set_cube(self, size: float64) -> None:
    self.kind = "MeshComponent"
    self.mesh = new.colored_cube(size, self.color)
    self.has_mesh = True
    self.asset_path = ""

  def load_fbx(self, path: str) -> None:
    self.kind = "MeshComponent"
    self.asset_path = path
    self.mesh = read_fbx(path, self.color)
    self.has_mesh = True


@refcount
class CameraComponent(Transform):
  """投影参数 + 位姿。"""

  fov_deg: float64 = 60.0
  z_near: float64 = 0.1
  z_far: float64 = 100.0
  look_at_target: Vector3 = new(0.0, 0.0, 0.0)

  def __init__(self):
    self.kind = "CameraComponent"
    self.enabled = True
    self._owner = None
    self.space = new("transform")
    self.fov_deg = 60.0
    self.z_near = 0.1
    self.z_far = 100.0
    self.look_at_target = new(0.0, 0.0, 0.0)


@refcount
class GameObject(GameNodeMixin):
  """可放置对象：对象树 + 组件 + root ``Transform``。"""

  name: str = "GameObject"
  _parent: Self | None = None
  _children: list[Self] = []
  _components: list[Component] = []
  root: Transform = new()

  def __init__(self, name: str = "GameObject"):
    self.name = name
    self.active = True
    self.visible = True
    self._parent = None
    self._children = []
    self._components = []
    self.root = new()
    self.root.kind = "Transform"
    self.root.name = "root"
    self._components.append(self.root)
    self.root.on_create()

  @property
  @immutable
  def parent(self) -> Self | None:
    return self._parent

  @property.setter
  def parent(self, value: Self | None) -> None:
    old: Self | None = self.parent
    if old is not None:
      old.detach(self)
    if value is not None:
      value.attach(self)

  @property
  @immutable
  def child_count(self) -> int:
    return len(self._children)

  def append_hierarchy_names(
    self, names: list[str] @ref, depths: list[int] @ref, depth: int,
  ) -> None:
    """深度优先写出对象树（供编辑器 Hierarchy；避免对外暴露 ``_children``）。"""
    names.append(self.name)
    depths.append(depth)
    for i in range(len(self._children)):
      self._children[i].append_hierarchy_names(names, depths, depth + 1)

  def child_at(self, index: int) -> Self:
    return self._children[index]

  def attach(self, child: Self) -> None:
    self._children.append(child)
    child._parent = self

  def detach(self, child: Self) -> None:
    for i in range(len(self._children)):
      if self._children[i] is child:
        self._children.pop(i)
        child._parent = None
        return

  def find(self, name: str) -> Self | None:
    stack: list[Self] = []
    for i in range(len(self._children)):
      stack.append(self._children[i])
    head: int = 0
    while head < len(stack):
      node: Self = stack[head]
      head += 1
      if node.name == name:
        return node
      for j in range(len(node._children)):
        stack.append(node._children[j])
    return None

  def add_component(self, comp: Component) -> Component:
    comp.bind_owner(self)
    self._components.append(comp)
    comp.on_create()
    return comp

  def find_component(self, kind: str) -> Component | None:
    for i in range(len(self._components)):
      c: Component = self._components[i]
      if c.kind == kind:
        return c
    return None

  def remove_component(self, kind: str) -> bool:
    if kind == "Transform":
      return False
    for i in range(len(self._components)):
      c: Component = self._components[i]
      if c.kind == kind:
        c.on_destroy()
        c.unbind_owner()
        self._components.pop(i)
        return True
    return False

  def component_count(self) -> int:
    return len(self._components)

  def component_at(self, index: int) -> Component:
    return self._components[index]

  def _update(self, dt: float64) -> None:
    pass

  def _draw(self) -> None:
    pass

  def update(self, dt: float64) -> None:
    if not self.active:
      return
    self._update(dt)
    for i in range(len(self._components)):
      c: Component = self._components[i]
      if c.enabled:
        c.on_update(dt)
    for j in range(len(self._children)):
      self._children[j].update(dt)

  def draw(self) -> None:
    if not self.active or not self.visible:
      return
    self._draw()
    for i in range(len(self._components)):
      c: Component = self._components[i]
      if c.enabled:
        c.on_draw()
    for j in range(len(self._children)):
      self._children[j].draw()
