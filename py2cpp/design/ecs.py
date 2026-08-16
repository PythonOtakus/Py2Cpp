"""ECS 通用接口：``ECSEntity``、``ECSComponentTable``、``ECSWorldMixin``。"""
from ..builtins import *
from ..core.exceptions import KeyError, ValueError
from ..util.list import list

# 稀疏表行数上限（``ECSWorldMixin`` / ``ECSComponentTable`` 共享）
EcsMaxEntities: int = 4096

# 稀疏槽未占用
EcsSparseEmpty: int = -1


@copyable
@dataclass(eq=True)
class ECSEntity:
  index: int = -1
  generation: int = 0


@annotation
class ComponentTableMeta:
  """World 组件列容器标记：标在 ``ECSComponentTable`` 上；``iterFields[ComponentTableMeta]()``。"""

  pass


class ECSComponentTableIterator[Component]:
  """遍历当前持有组件 ``T`` 的实体（稠密序）。"""

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, owner: ECSComponentTable[Component]):
    self._owner: ECSComponentTable[Component] = owner
    self._index: int = 0

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> ECSEntity:
    if self._index >= len(self._owner):
      raise StopIteration
    e: ECSEntity = self._owner.entityAtDense(self._index)
    self._index += 1
    return e


class ECSComponentTableQuery[Lead, Other]:
  """``for e in table_a & table_b``：遍历在 ``table_a`` 与 ``table_b`` 中均持有组件的实体。"""

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, lead: ECSComponentTable[Lead], other: ECSComponentTable[Other]):
    self._lead: ECSComponentTable[Lead] = lead
    self._other: ECSComponentTable[Other] = other
    self._index: int = 0

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> ECSEntity:
    end: int = len(self._lead)
    for di in range(self._index, end):
      e: ECSEntity = self._lead.entityAtDense(di)
      if e in self._other:
        self._index = di + 1
        return e
    self._index = end
    raise StopIteration


@ComponentTableMeta
class ECSComponentTable[Component]:
  """``table[e]`` / ``table[e] = v`` / ``del table[e]``；``for e in table`` / ``e in table``。"""

  def __init__(self):
    self._dense: list[Component] = []
    self._entities: list[ECSEntity] = []
    self._sparse: int[:] = new(EcsMaxEntities)
    self._initSparse()

  def _initSparse(self):
    for i in range(EcsMaxEntities):
      self._sparse[i] = EcsSparseEmpty

  @immutable
  def _ensureActive(self) -> None:
    if self.__moved__:
      raise ValueError("ECSComponentTable used after move")

  @immutable
  def _ensureOtherActive(self, otherMoved: bool) -> None:
    if otherMoved:
      raise ValueError("move from moved ECSComponentTable")

  def __copy__(self, other: Self):
    self._ensureActive()
    self._ensureOtherActive(other.__moved__)
    dense: list[Component] = []
    entities: list[ECSEntity] = []
    self._dense = dense
    self._entities = entities
    for i in range(len(other._dense)):
      self._dense.append(other._dense[i])
      self._entities.append(other._entities[i])
    self._sparse = new(EcsMaxEntities)
    for i in range(EcsMaxEntities):
      self._sparse[i] = other._sparse[i]

  def __move__(self, other: Self):
    self._ensureActive()
    self._ensureOtherActive(other.__moved__)
    self._dense = other._dense
    self._entities = other._entities
    self._sparse = other._sparse
    dense: list[Component] = []
    entities: list[ECSEntity] = []
    other._dense = dense
    other._entities = entities
    other._sparse = new(EcsMaxEntities)
    other._initSparse()

  @immutable
  def copy(self) -> Self:
    self._ensureActive()
    out: Self = new()
    out.__copy__(self)
    return out

  @immutable
  def __len__(self) -> int:
    return len(self._dense)

  @immutable
  def __bool__(self) -> bool:
    return bool(self._dense)

  @immutable
  def __contains__(self, e: ECSEntity) -> bool:
    return self._denseIndex(e) >= 0

  @immutable
  def entityAtDense(self, di: int) -> ECSEntity:
    """稠密下标 ``di`` 处的实体（供迭代器 / 交集查询；勿与稀疏 ``e.index`` 混用）。"""
    return self._entities[di]

  def __iter__(self) -> ECSComponentTableIterator[Component]:
    return new(self)

  def __and__[U](self, other: ECSComponentTable[U] @ref) -> ECSComponentTableQuery[Component, U]:
    return new(self, other)

  def __getitem__(self, e: ECSEntity) -> Component @ref:
    di: int = self._denseIndex(e)
    if di < 0:
      raise KeyError("ECSComponentTable: entity has no component")
    return self._dense[di]

  def __setitem__(self, e: ECSEntity, value: Component):
    if e.index < 0 or e.index >= EcsMaxEntities:
      raise ValueError("ECSComponentTable: invalid entity index")
    di: int = self._denseIndex(e)
    if di >= 0:
      self._dense[di] = value
      return
    self._dense.append(value)
    self._entities.append(e)
    self._sparse[e.index] = len(self._dense) - 1

  def __delitem__(self, e: ECSEntity):
    di: int = self._denseIndex(e)
    if di < 0:
      raise KeyError("ECSComponentTable: entity has no component")
    last: int = len(self._dense) - 1
    if di != last:
      self._dense[di] = self._dense[last]
      moved: ECSEntity = self._entities[last]
      self._entities[di] = moved
      self._sparse[moved.index] = di
    self._dense.pop()
    self._entities.pop()
    self._sparse[e.index] = EcsSparseEmpty

  @immutable
  def _denseIndex(self, e: ECSEntity) -> int:
    if e.index < 0 or e.index >= EcsMaxEntities:
      return EcsSparseEmpty
    di: int = self._sparse[e.index]
    if di < 0:
      return EcsSparseEmpty
    if self._entities[di] != e:
      return EcsSparseEmpty
    return di


@mixin
class ECSWorldMixin:
  """实体索引池 + ``destroy``；子类可覆写 ``_postInit``，并实现 ``create`` 等。"""

  def __init__(self):
    self._generation: int[:] = new(EcsMaxEntities)
    self._alive: int[:] = new(EcsMaxEntities)
    self._free: list[int] = []
    self._nextIndex: int = 0
    self._postInit()

  def _postInit(self):
    """在索引池字段初始化之后调用；子类可覆写以注册表或预热资源。"""

  @immutable
  def isAlive(self, e: ECSEntity) -> bool:
    if e.index < 0 or e.index >= EcsMaxEntities:
      return False
    if not self._alive[e.index]:
      return False
    return e.generation == self._generation[e.index]

  def _allocEntity(self) -> ECSEntity:
    idx: int = EcsSparseEmpty
    if self._free:
      idx = self._free.pop()
    else:
      if self._nextIndex >= EcsMaxEntities:
        raise ValueError("ECS: entity limit exceeded")
      idx = self._nextIndex
      self._nextIndex += 1
    gen: int = self._generation[idx]
    self._alive[idx] = 1
    return new(idx, gen)

  def _deallocEntity(self, e: ECSEntity) -> None:
    self._alive[e.index] = 0
    self._generation[e.index] += 1
    self._free.append(e.index)

  def destroy(self, e: ECSEntity):
    if not self.isAlive(e):
      raise ValueError("ECS: entity not alive")
    for field in Self.iterFields[ComponentTableMeta]():
      if e in getattr(self, field):
        del getattr(self, field)[e]
    self._deallocEntity(e)
