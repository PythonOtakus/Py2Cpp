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
  _localPosition: Vec = new.zero
  _localRotation: Rot = new.identity
  _localScale: Vec = new.one

  @staticmethod
  @immutable
  def _isDescendantOf(node: Self, ancestor: Self) -> bool:
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
      if value is self or Self._isDescendantOf(value, self):
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
  def childCount(self) -> int:
    return len(self._children)

  @property
  @immutable
  def children(self) -> list[Self]:
    return self._children.copy()

  def attach(self, child: Self) -> None:
    self._children.append(child)
    child.bindParent(self)

  def detach(self, child: Self) -> None:
    for i in range(len(self._children)):
      if self._children[i] is child:
        self._children.pop(i)
        child.unbindParent()
        return

  def detachAll(self) -> None:
    for i in range(len(self._children)):
      self._children[i].unbindParent()
    self._children.clear()

  def bindParent(self, par: Self) -> None:
    self._parent = new(par)

  def unbindParent(self) -> None:
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
  def localMatrix(self) -> Mat:
    return new.transform(self._localPosition, self._localRotation, self._localScale)

  @property
  @immutable
  def localInvMatrix(self) -> Mat:
    return self.localMatrix.inv

  @property
  @immutable
  def localToWorldMatrix(self) -> Mat:
    m: Mat = self.localMatrix
    par: Self | None = self.parent
    while par is not None:
      m = par.localMatrix @ m
      par = par.parent
    return m

  @property
  @immutable
  def worldToLocalMatrix(self) -> Mat:
    return self.localToWorldMatrix.inv

  @immutable
  def localToWorldPoint(self, point: Vec) -> Vec:
    return self.localToWorldMatrix.applyToPoint(point)

  @immutable
  def localToWorldVector(self, vector: Vec) -> Vec:
    return self.localToWorldMatrix.applyToVector(vector)

  @immutable
  def worldToLocalPoint(self, point: Vec) -> Vec:
    return self.worldToLocalMatrix.applyToPoint(point)

  @immutable
  def worldToLocalVector(self, vector: Vec) -> Vec:
    return self.worldToLocalMatrix.applyToVector(vector)

  @property
  @immutable
  def position(self) -> Vec:
    p: Vec = self.localPosition
    par: Self | None = self.parent
    if par is not None:
      return par.localToWorldPoint(p)
    return p

  @property.setter
  def position(self, value: Vec) -> None:
    par: Self | None = self.parent
    if par is not None:
      local: Vec = par.worldToLocalPoint(value)
      self.localPosition = local
    else:
      self.localPosition = value

  @property
  @immutable
  def rotation(self) -> Rot:
    rot: Rot = self.localRotation
    par: Self | None = self.parent
    while par is not None:
      rot = par.localRotation @ rot
      par = par.parent
    return rot

  @property.setter
  def rotation(self, value: Rot) -> None:
    par: Self | None = self.parent
    if par is not None:
      local: Rot = value @ ~par.rotation
      self.localRotation = local
    else:
      self.localRotation = value

  @property
  @immutable
  def scale(self) -> Vec:
    return self.localToWorldMatrix.scale

  def translate(self, translation: Vec) -> None:
    self.position += translation


@refcount
class Transform2D(TransformMixin[Vector2, Rotator, Matrix3]):
  """2D 变换节点：局部 TRS + 父子层级（父引用 ``WeakRef``，子列表强引用）。"""

  def __repr__(self) -> str:
    return f"<Transform2D {self.name}>"

  @property
  @immutable
  def localPosition(self) -> Vector2:
    return new(self._localPosition.x, self._localPosition.y)

  @property.setter
  def localPosition(self, value: Vector2) -> None:
    self._localPosition.x = value.x
    self._localPosition.y = value.y

  @property
  @immutable
  def localRotation(self) -> Rotator:
    return new(self._localRotation.w, self._localRotation.z)

  @property.setter
  def localRotation(self, value: Rotator) -> None:
    self._localRotation.w = value.w
    self._localRotation.z = value.z
  @property
  @immutable
  def localAngle(self) -> float64:
    return self._localRotation.toAngle()

  @property.setter
  def localAngle(self, value: float64) -> None:
    r: Rotator = new.fromAngle(value)
    self._localRotation.w = r.w
    self._localRotation.z = r.z

  @property
  @immutable
  def localScale(self) -> Vector2:
    return new(self._localScale.x, self._localScale.y)

  @property.setter
  def localScale(self, value: Vector2) -> None:
    self._localScale.x = value.x
    self._localScale.y = value.y

  @property
  @immutable
  def angle(self) -> float64:
    rot: Rotator = self.rotation
    return rot.toAngle()

  @property.setter
  def angle(self, value: float64) -> None:
    self.rotation = new.fromAngle(value)

  @property
  @immutable
  def right(self) -> Vector2:
    return self.localToWorldVector(Vector2.right)

  @property
  @immutable
  def down(self) -> Vector2:
    return self.localToWorldVector(Vector2.down)

  def rotate(self, angle: float64) -> None:
    delta: Rotator = new.fromAngle(angle)
    self.rotation = delta @ self.rotation

  def rotateAround(self, center: Vector2, angle: float64) -> None:
    pos: Vector2 = self.position
    self.position = pos.rotatedAround(center, angle)
    delta: Rotator = new.fromAngle(angle)
    self.rotation = delta @ self.rotation

  def lookAt(self, target: Vector2) -> None:
    self.rotation = new.lookAt(target - self.position)


@refcount
class Transform3D(TransformMixin[Vector3, Quaternion, Matrix4]):
  """3D 变换节点：局部 TRS + 父子层级（父引用 ``WeakRef``，子列表强引用）。"""

  def __repr__(self) -> str:
    return f"<Transform3D {self.name}>"

  @property
  @immutable
  def localPosition(self) -> Vector3:
    return new(self._localPosition.x, self._localPosition.y, self._localPosition.z)

  @property.setter
  def localPosition(self, value: Vector3) -> None:
    self._localPosition.x = value.x
    self._localPosition.y = value.y
    self._localPosition.z = value.z

  @property
  @immutable
  def localRotation(self) -> Quaternion:
    return new(
      self._localRotation.w,
      self._localRotation.x,
      self._localRotation.y,
      self._localRotation.z,
    )

  @property.setter
  def localRotation(self, value: Quaternion) -> None:
    self._localRotation.w = value.w
    self._localRotation.x = value.x
    self._localRotation.y = value.y
    self._localRotation.z = value.z
  @property
  @immutable
  def localEulerAngles(self) -> Vector3:
    return self._localRotation.toEulerAngles()

  @property.setter
  def localEulerAngles(self, value: Vector3) -> None:
    q: Quaternion = new.fromEulerAngles(value)
    self._localRotation.w = q.w
    self._localRotation.x = q.x
    self._localRotation.y = q.y
    self._localRotation.z = q.z

  @property
  @immutable
  def localScale(self) -> Vector3:
    return new(self._localScale.x, self._localScale.y, self._localScale.z)

  @property.setter
  def localScale(self, value: Vector3) -> None:
    self._localScale.x = value.x
    self._localScale.y = value.y
    self._localScale.z = value.z

  @property
  @immutable
  def eulerAngles(self) -> Vector3:
    rot: Quaternion = self.rotation
    return rot.toEulerAngles()

  @property.setter
  def eulerAngles(self, value: Vector3) -> None:
    self.rotation = new.fromEulerAngles(value)

  @property
  @immutable
  def right(self) -> Vector3:
    return self.localToWorldVector(Vector3.right)

  @property
  @immutable
  def down(self) -> Vector3:
    return self.localToWorldVector(Vector3.down)

  @property
  @immutable
  def forward(self) -> Vector3:
    return self.localToWorldVector(Vector3.forward)

  def rotate(self, axis: Vector3, angle: float64) -> None:
    delta: Quaternion = new.fromAxisAngle(axis, angle)
    self.rotation = delta @ self.rotation

  def rotateAround(self, center: Vector3, axis: Vector3, angle: float64) -> None:
    pos: Vector3 = self.position
    self.position = pos.rotatedAround(center, axis, angle)
    delta: Quaternion = new.fromAxisAngle(axis, angle)
    self.rotation = delta @ self.rotation

  def lookAt(self, target: Vector3) -> None:
    self.rotation = new.lookAt(target - self.position)
