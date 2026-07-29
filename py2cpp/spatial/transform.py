"""场景图变换 ``Transform2D`` / ``Transform3D``（对齐 tggame ``space.Transform*`` 子集）。"""
from __future__ import annotations

from ..builtins import *
from ..core.exceptions import ValueError
from ..weak.ref import WeakRef
from .matrix import Matrix3, Matrix4
from .rotator import Quaternion, Rotator
from .vector import Vector2, Vector3


@dataclass(eq=False, repr=False)
@mixin
class TransformMixin[Vec, Rot, Mat]:
  """``Transform2D`` / ``Transform3D`` 公共场景图 + 世界空间 TRS（维相关类型由 ``Vec``/``Rot``/``Mat`` 形参绑定）。"""

  name: str = "Anonymous"
  _parent: WeakRef[Self] | None = None
  _children: list[Self] @optional = []
  _local_position: Vec = new.zero
  _local_rotation: Rot = new.identity
  _local_scale: Vec = new.one

  @staticmethod
  @immutable
  def _is_descendant_of(node: Self, ancestor: Self) -> bool:
    cur: Self = node
    while True:
      if cur is ancestor:
        return True
      if cur.parent is None:
        return False
      cur = cur.parent

  @property
  @immutable
  def parent(self) -> Self | None:
    if self._parent is None:
      return None
    wr: WeakRef[Self] = self._parent.value
    if not wr.alive:
      return None
    return wr.value

  @property.setter
  def parent(self, value: Self | None) -> None:
    old: Self | None = self.parent
    if old is not None:
      old.detach(self)
    if value is not None:
      if value is self or Self._is_descendant_of(value, self):
        raise ValueError("transform parent would create a cycle")
      value.attach(self)

  @property
  @immutable
  def root(self) -> Self:
    node: Self = self
    while True:
      p: Self | None = node.parent
      if p is None:
        return node
      node = p

  @property
  @immutable
  def child_count(self) -> int:
    return len(self._children)

  @property
  @immutable
  def children(self) -> list[Self]:
    return self._children.copy()

  def attach(self, child: Self) -> None:
    self._children.append(child)
    child.bind_parent(self)

  def detach(self, child: Self) -> None:
    for i in range(len(self._children)):
      if self._children[i] is child:
        self._children.pop(i)
        child.unbind_parent()
        return

  def detach_all(self) -> None:
    for i in range(len(self._children)):
      self._children[i].unbind_parent()
    self._children.clear()

  def bind_parent(self, par: Self) -> None:
    wr: WeakRef[Self] = new(par)
    self._parent = wr

  def unbind_parent(self) -> None:
    self._parent = None

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
      subs: list[Self] = node.children
      for j in range(len(subs)):
        stack.append(subs[j])
    return None

  @property
  @immutable
  def local_matrix(self) -> Mat:
    return new.transform(self._local_position, self._local_rotation, self._local_scale)

  @property
  @immutable
  def local_inv_matrix(self) -> Mat:
    return self.local_matrix.inv

  @property
  @immutable
  def local_to_world_matrix(self) -> Mat:
    m: Mat = self.local_matrix
    par: Self | None = self.parent
    while par is not None:
      m = par.local_matrix @ m
      par = par.parent
    return m

  @property
  @immutable
  def world_to_local_matrix(self) -> Mat:
    return self.local_to_world_matrix.inv

  @immutable
  def local_to_world_point(self, point: Vec) -> Vec:
    return self.local_to_world_matrix.apply_to_point(point)

  @immutable
  def local_to_world_vector(self, vector: Vec) -> Vec:
    return self.local_to_world_matrix.apply_to_vector(vector)

  @immutable
  def world_to_local_point(self, point: Vec) -> Vec:
    return self.world_to_local_matrix.apply_to_point(point)

  @immutable
  def world_to_local_vector(self, vector: Vec) -> Vec:
    return self.world_to_local_matrix.apply_to_vector(vector)

  @property
  @immutable
  def position(self) -> Vec:
    p: Vec = self.local_position
    par: Self | None = self.parent
    if par is not None:
      return par.local_to_world_point(p)
    return p

  @property.setter
  def position(self, value: Vec) -> None:
    par: Self | None = self.parent
    if par is not None:
      local: Vec = par.world_to_local_point(value)
      self.local_position = local
    else:
      self.local_position = value

  @property
  @immutable
  def rotation(self) -> Rot:
    rot: Rot = self.local_rotation
    par: Self | None = self.parent
    while par is not None:
      rot = par.local_rotation @ rot
      par = par.parent
    return rot

  @property.setter
  def rotation(self, value: Rot) -> None:
    par: Self | None = self.parent
    if par is not None:
      local: Rot = value @ ~par.rotation
      self.local_rotation = local
    else:
      self.local_rotation = value

  @property
  @immutable
  def scale(self) -> Vec:
    return self.local_to_world_matrix.scale

  def translate(self, translation: Vec) -> None:
    self.position += translation


@refcount
class Transform2D(TransformMixin[Vector2, Rotator, Matrix3]):
  """2D 变换节点：局部 TRS + 父子层级（父引用 ``WeakRef``，子列表强引用）。"""

  def __repr__(self) -> str:
    return f"<Transform2D {self.name}>"

  @property
  @immutable
  def local_position(self) -> Vector2:
    return new(self._local_position.x, self._local_position.y)

  @property.setter
  def local_position(self, value: Vector2) -> None:
    self._local_position.x = value.x
    self._local_position.y = value.y

  @property
  @immutable
  def local_rotation(self) -> Rotator:
    return new(self._local_rotation.w, self._local_rotation.z)

  @property.setter
  def local_rotation(self, value: Rotator) -> None:
    self._local_rotation.w = value.w
    self._local_rotation.z = value.z
  @property
  @immutable
  def local_angle(self) -> float64:
    return self._local_rotation.to_angle()

  @property.setter
  def local_angle(self, value: float64) -> None:
    r: Rotator = new.from_angle(value)
    self._local_rotation.w = r.w
    self._local_rotation.z = r.z

  @property
  @immutable
  def local_scale(self) -> Vector2:
    return new(self._local_scale.x, self._local_scale.y)

  @property.setter
  def local_scale(self, value: Vector2) -> None:
    self._local_scale.x = value.x
    self._local_scale.y = value.y

  @property
  @immutable
  def angle(self) -> float64:
    rot: Rotator = self.rotation
    return rot.to_angle()

  @property.setter
  def angle(self, value: float64) -> None:
    r: Rotator = new.from_angle(value)
    self.rotation = r

  @property
  @immutable
  def right(self) -> Vector2:
    axis: Vector2 = new.right
    return self.local_to_world_vector(axis)

  @property
  @immutable
  def down(self) -> Vector2:
    axis: Vector2 = new.down
    return self.local_to_world_vector(axis)

  def rotate(self, angle: float64) -> None:
    delta: Rotator = new.from_angle(angle)
    self.rotation = delta @ self.rotation

  def rotate_around(self, center: Vector2, angle: float64) -> None:
    pos: Vector2 = self.position
    self.position = pos.rotated_around(center, angle)
    delta: Rotator = new.from_angle(angle)
    self.rotation = delta @ self.rotation

  def look_at(self, target: Vector2) -> None:
    aim: Rotator = new.look_at(target - self.position)
    self.rotation = aim


@refcount
class Transform3D(TransformMixin[Vector3, Quaternion, Matrix4]):
  """3D 变换节点：局部 TRS + 父子层级（父引用 ``WeakRef``，子列表强引用）。"""

  def __repr__(self) -> str:
    return f"<Transform3D {self.name}>"

  @property
  @immutable
  def local_position(self) -> Vector3:
    return new(self._local_position.x, self._local_position.y, self._local_position.z)

  @property.setter
  def local_position(self, value: Vector3) -> None:
    self._local_position.x = value.x
    self._local_position.y = value.y
    self._local_position.z = value.z

  @property
  @immutable
  def local_rotation(self) -> Quaternion:
    return new(
      self._local_rotation.w,
      self._local_rotation.x,
      self._local_rotation.y,
      self._local_rotation.z,
    )

  @property.setter
  def local_rotation(self, value: Quaternion) -> None:
    self._local_rotation.w = value.w
    self._local_rotation.x = value.x
    self._local_rotation.y = value.y
    self._local_rotation.z = value.z
  @property
  @immutable
  def local_euler_angles(self) -> Vector3:
    return self._local_rotation.to_euler_angles()

  @property.setter
  def local_euler_angles(self, value: Vector3) -> None:
    q: Quaternion = new.from_euler_angles(value)
    self._local_rotation.w = q.w
    self._local_rotation.x = q.x
    self._local_rotation.y = q.y
    self._local_rotation.z = q.z

  @property
  @immutable
  def local_scale(self) -> Vector3:
    return new(self._local_scale.x, self._local_scale.y, self._local_scale.z)

  @property.setter
  def local_scale(self, value: Vector3) -> None:
    self._local_scale.x = value.x
    self._local_scale.y = value.y
    self._local_scale.z = value.z

  @property
  @immutable
  def euler_angles(self) -> Vector3:
    rot: Quaternion = self.rotation
    return rot.to_euler_angles()

  @property.setter
  def euler_angles(self, value: Vector3) -> None:
    q: Quaternion = new.from_euler_angles(value)
    self.rotation = q

  @property
  @immutable
  def right(self) -> Vector3:
    axis: Vector3 = new.right
    return self.local_to_world_vector(axis)

  @property
  @immutable
  def down(self) -> Vector3:
    axis: Vector3 = new.down
    return self.local_to_world_vector(axis)

  @property
  @immutable
  def forward(self) -> Vector3:
    axis: Vector3 = new.forward
    return self.local_to_world_vector(axis)

  def rotate(self, axis: Vector3, angle: float64) -> None:
    delta: Quaternion = new.from_axis_angle(axis, angle)
    self.rotation = delta @ self.rotation

  def rotate_around(self, center: Vector3, axis: Vector3, angle: float64) -> None:
    pos: Vector3 = self.position
    self.position = pos.rotated_around(center, axis, angle)
    delta: Quaternion = new.from_axis_angle(axis, angle)
    self.rotation = delta @ self.rotation

  def look_at(self, target: Vector3) -> None:
    aim: Quaternion = new.look_at(target - self.position)
    self.rotation = aim
