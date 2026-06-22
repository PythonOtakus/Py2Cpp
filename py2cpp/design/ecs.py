"""ECS 通用接口：``ECSEntity``、``ECSComponentTable``、``ECSWorldMixin``。"""
from ..builtins import *
from ..core.exceptions import KeyError, ValueError
from ..util.list import list

# 稀疏表行数上限（``ECSWorldMixin`` / ``ECSComponentTable`` 共享）
ECS_MAX_ENTITIES: int = 4096

# 稀疏槽未占用
ECS_SPARSE_EMPTY: int = -1


@copyable
@dataclass(eq=True)
class ECSEntity:
  index: int = -1
  generation: int = 0


@annotation
class ComponentTableMeta:
  """World 组件列容器标记：标在 ``ECSComponentTable`` 上；``iter_fields[ComponentTableMeta]()``。"""

  pass


class ECSComponentTableIterator[T]:
  """遍历当前持有组件 ``T`` 的实体（稠密序）。"""

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, owner: ECSComponentTable[T]):
    self._owner: ECSComponentTable[T] = owner
    self._index: int = 0

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> ECSEntity:
    if self._index >= len(self._owner):
      raise StopIteration
    e: ECSEntity = self._owner.entity_at_dense(self._index)
    self._index += 1
    return e


class ECSComponentTableQuery[T, U]:
  """``for e in table_a & table_b``：遍历在 ``table_a`` 与 ``table_b`` 中均持有组件的实体。"""

  @overload
  def __init__(self):
    pass

  @overload
  def __init__(self, lead: ECSComponentTable[T], other: ECSComponentTable[U]):
    self._lead: ECSComponentTable[T] = lead
    self._other: ECSComponentTable[U] = other
    self._index: int = 0

  def __iter__(self) -> Self:
    return self

  def __next__(self) -> ECSEntity:
    end: int = len(self._lead)
    for di in range(self._index, end):
      e: ECSEntity = self._lead.entity_at_dense(di)
      if e in self._other:
        self._index = di + 1
        return e
    self._index = end
    raise StopIteration


@ComponentTableMeta
class ECSComponentTable[T]:
  """``table[e]`` / ``table[e] = v`` / ``del table[e]``；``for e in table`` / ``e in table``。"""

  def __init__(self):
    self._dense: list[T] = []
    self._entities: list[ECSEntity] = []
    self._sparse: int[:] = new(ECS_MAX_ENTITIES)
    self._init_sparse()

  def _init_sparse(self):
    for i in range(ECS_MAX_ENTITIES):
      self._sparse[i] = ECS_SPARSE_EMPTY

  @immutable
  def _ensure_active(self) -> None:
    if self.__moved__:
      raise ValueError("ECSComponentTable used after move")

  @immutable
  def _ensure_other_active(self, other_moved: bool) -> None:
    if other_moved:
      raise ValueError("move from moved ECSComponentTable")

  def __copy__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    dense: list[T] = []
    entities: list[ECSEntity] = []
    self._dense = dense
    self._entities = entities
    for i in range(len(other._dense)):
      self._dense.append(other._dense[i])
      self._entities.append(other._entities[i])
    self._sparse = new(ECS_MAX_ENTITIES)
    for i in range(ECS_MAX_ENTITIES):
      self._sparse[i] = other._sparse[i]

  def __move__(self, other: Self):
    self._ensure_active()
    self._ensure_other_active(other.__moved__)
    self._dense = other._dense
    self._entities = other._entities
    self._sparse = other._sparse
    dense: list[T] = []
    entities: list[ECSEntity] = []
    other._dense = dense
    other._entities = entities
    other._sparse = new(ECS_MAX_ENTITIES)
    other._init_sparse()

  @immutable
  def copy(self) -> Self:
    self._ensure_active()
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
    return self._dense_index(e) >= 0

  @immutable
  def entity_at_dense(self, di: int) -> ECSEntity:
    """稠密下标 ``di`` 处的实体（供迭代器 / 交集查询；勿与稀疏 ``e.index`` 混用）。"""
    return self._entities[di]

  def __iter__(self) -> ECSComponentTableIterator[T]:
    return new(self)

  def __and__[U](self, other: ECSComponentTable[U] @ref) -> ECSComponentTableQuery[T, U]:
    return new(self, other)

  def __getitem__(self, e: ECSEntity) -> T @ref:
    di: int = self._dense_index(e)
    if di < 0:
      raise KeyError("ECSComponentTable: entity has no component")
    return self._dense[di]

  def __setitem__(self, e: ECSEntity, value: T):
    if e.index < 0 or e.index >= ECS_MAX_ENTITIES:
      raise ValueError("ECSComponentTable: invalid entity index")
    di: int = self._dense_index(e)
    if di >= 0:
      self._dense[di] = value
      return
    self._dense.append(value)
    self._entities.append(e)
    self._sparse[e.index] = len(self._dense) - 1

  def __delitem__(self, e: ECSEntity):
    di: int = self._dense_index(e)
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
    self._sparse[e.index] = ECS_SPARSE_EMPTY

  @immutable
  def _dense_index(self, e: ECSEntity) -> int:
    if e.index < 0 or e.index >= ECS_MAX_ENTITIES:
      return ECS_SPARSE_EMPTY
    di: int = self._sparse[e.index]
    if di < 0:
      return ECS_SPARSE_EMPTY
    if self._entities[di] != e:
      return ECS_SPARSE_EMPTY
    return di


@mixin
class ECSWorldMixin:
  """实体索引池 + ``destroy``；子类可覆写 ``_post_init``，并实现 ``create`` 等。"""

  def __init__(self):
    self._generation: int[:] = new(ECS_MAX_ENTITIES)
    self._alive: int[:] = new(ECS_MAX_ENTITIES)
    self._free: list[int] = []
    self._next_index: int = 0
    self._post_init()

  def _post_init(self):
    """在索引池字段初始化之后调用；子类可覆写以注册表或预热资源。"""

  @immutable
  def is_alive(self, e: ECSEntity) -> bool:
    if e.index < 0 or e.index >= ECS_MAX_ENTITIES:
      return False
    if not self._alive[e.index]:
      return False
    return e.generation == self._generation[e.index]

  def _alloc_entity(self) -> ECSEntity:
    idx: int = ECS_SPARSE_EMPTY
    if self._free:
      idx = self._free.pop()
    else:
      if self._next_index >= ECS_MAX_ENTITIES:
        raise ValueError("ECS: entity limit exceeded")
      idx = self._next_index
      self._next_index += 1
    gen: int = self._generation[idx]
    self._alive[idx] = 1
    return new(idx, gen)

  def _dealloc_entity(self, e: ECSEntity) -> None:
    self._alive[e.index] = 0
    self._generation[e.index] += 1
    self._free.append(e.index)

  def destroy(self, e: ECSEntity):
    if not self.is_alive(e):
      raise ValueError("ECS: entity not alive")
    for field in Self.iter_fields[ComponentTableMeta]():
      if e in getattr(self, field):
        del getattr(self, field)[e]
    self._dealloc_entity(e)
