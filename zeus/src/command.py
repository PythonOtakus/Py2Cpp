"""Zeus 命令 ADT + ``CommandBus``（Editor / 后续 MCP 共用）。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.vector import Vector3

from .scene import CameraComponent, Component, GameObject, MeshComponent
from .scene_io import scene_from_json, scene_load, scene_save, scene_to_json
from .world import WORLD_PLAYING, WORLD_STOPPED, World


@copyable
@dataclass
class CommandResult:
  ok: bool = True
  message: str = ""


@union
class ZeusCommandUnion:
  @variant
  class ObjectCreate:
    name: str
    parent_name: str

  @variant
  class ObjectDelete:
    name: str

  @variant
  class ObjectRename:
    name: str
    new_name: str

  @variant
  class ObjectSetPosition:
    name: str
    x: float64
    y: float64
    z: float64

  @variant
  class ObjectSetActive:
    name: str
    active: bool

  @variant
  class ObjectSetVisible:
    name: str
    visible: bool

  @variant
  class ObjectAddMesh:
    name: str
    size: float64

  @variant
  class ObjectAddCamera:
    name: str

  @variant
  class ObjectRemoveComponent:
    name: str
    kind: str

  @variant
  class ComponentSetFloat:
    name: str
    kind: str
    field: str
    value: float64

  @variant
  class PlayStart:
    pass

  @variant
  class PlayPause:
    pass

  @variant
  class PlayStop:
    pass

  @variant
  class PlayStep:
    frames: int

  @variant
  class EditorSelect:
    name: str

  @variant
  class SceneSave:
    path: str
    scene_name: str

  @variant
  class SceneLoad:
    path: str

  @variant
  class SceneFromJson:
    text: str


@refcount
class CommandBus:
  """持有 ``World`` 与编辑选中名；``dispatch`` 执行命令。"""

  world: World = new()
  selected: str = ""
  scene_name: str = "Scene"

  def __init__(self):
    self.world = new()
    self.selected = ""
    self.scene_name = "Scene"

  def _find(self, name: str) -> GameObject | None:
    if self.world.root.name == name:
      return self.world.root
    return self.world.root.find(name)

  def _fail(self, msg: str) -> CommandResult:
    r: CommandResult = new()
    r.ok = False
    r.message = msg
    return r

  def _ok(self, msg: str = "") -> CommandResult:
    r: CommandResult = new()
    r.ok = True
    r.message = msg
    return r

  def _is_play_write(self, cmd: ZeusCommandUnion) -> bool:
    """Play 态禁止改场景的写命令（play / editor.select / 存读场景除外）。"""
    match cmd:
      case new.PlayStart:
        return False
      case new.PlayPause:
        return False
      case new.PlayStop:
        return False
      case new.PlayStep:
        return False
      case new.EditorSelect:
        return False
      case new.SceneSave:
        return False
      case new.SceneLoad:
        return False
      case new.SceneFromJson:
        return False
      case _:
        return True

  def dispatch(self, cmd: ZeusCommandUnion) -> CommandResult:
    if self.world.state == WORLD_PLAYING and self._is_play_write(cmd):
      return self._fail("write blocked while playing")
    match cmd:
      case new.ObjectCreate(name, parent_name):
        if not name:
          return self._fail("empty name")
        if self._find(name) is not None:
          return self._fail("object exists")
        parent: GameObject | None = self.world.root
        if parent_name:
          parent = self._find(parent_name)
          if parent is None:
            return self._fail("parent not found")
        go: GameObject = new(name)
        go.parent = parent
        return self._ok(name)
      case new.ObjectDelete(name):
        if name == self.world.root.name:
          return self._fail("cannot delete root")
        target: GameObject | None = self._find(name)
        if target is None:
          return self._fail("not found")
        target.parent = None
        if self.selected == name:
          self.selected = ""
        return self._ok()
      case new.ObjectRename(name, new_name):
        if not new_name:
          return self._fail("empty new_name")
        if self._find(new_name) is not None:
          return self._fail("new_name exists")
        obj: GameObject | None = self._find(name)
        if obj is None:
          return self._fail("not found")
        obj.name = new_name
        if self.selected == name:
          self.selected = new_name
        return self._ok(new_name)
      case new.ObjectSetPosition(name, x, y, z):
        pos_obj: GameObject | None = self._find(name)
        if pos_obj is None:
          return self._fail("not found")
        pos_obj.root.localPosition = Vector3(x, y, z)
        return self._ok()
      case new.ObjectSetActive(name, active):
        act_obj: GameObject | None = self._find(name)
        if act_obj is None:
          return self._fail("not found")
        act_obj.active = active
        return self._ok()
      case new.ObjectSetVisible(name, visible):
        vis_obj: GameObject | None = self._find(name)
        if vis_obj is None:
          return self._fail("not found")
        vis_obj.visible = visible
        return self._ok()
      case new.ObjectAddMesh(name, size):
        mesh_obj: GameObject | None = self._find(name)
        if mesh_obj is None:
          return self._fail("not found")
        if mesh_obj.find_component("MeshComponent") is not None:
          return self._fail("MeshComponent exists")
        mc: MeshComponent = new()
        s: float64 = size
        if s <= 0.0:
          s = 1.0
        mc.set_cube(s)
        mesh_obj.add_component(mc)
        return self._ok()
      case new.ObjectAddCamera(name):
        cam_obj: GameObject | None = self._find(name)
        if cam_obj is None:
          return self._fail("not found")
        if cam_obj.find_component("CameraComponent") is not None:
          return self._fail("CameraComponent exists")
        cam_obj.add_component(CameraComponent())
        return self._ok()
      case new.ObjectRemoveComponent(name, kind):
        rem_obj: GameObject | None = self._find(name)
        if rem_obj is None:
          return self._fail("not found")
        if not rem_obj.remove_component(kind):
          return self._fail("component not found")
        return self._ok()
      case new.ComponentSetFloat(name, kind, field, value):
        float_obj: GameObject | None = self._find(name)
        if float_obj is None:
          return self._fail("not found")
        float_comp: Component | None = float_obj.find_component(kind)
        if float_comp is None:
          return self._fail("component not found")
        if not float_comp.set_inspect_float(field, value):
          return self._fail("field not found")
        return self._ok()
      case new.PlayStart:
        self.world.play()
        return self._ok()
      case new.PlayPause:
        self.world.pause()
        return self._ok()
      case new.PlayStop:
        self.world.state = WORLD_STOPPED
        return self._ok()
      case new.PlayStep(frames):
        n: int = frames
        if n < 1:
          n = 1
        if self.world.state != WORLD_PLAYING:
          self.world.play()
        for _i in range(n):
          self.world.step()
        return self._ok()
      case new.EditorSelect(name):
        if name and self._find(name) is None:
          return self._fail("not found")
        self.selected = name
        return self._ok(name)
      case new.SceneSave(path, scene_name):
        sn: str = scene_name
        if not sn:
          sn = self.scene_name
        scene_save(self.world, path, sn)
        self.scene_name = sn
        return self._ok(path)
      case new.SceneLoad(path):
        self.scene_name = scene_load(self.world, path)
        self.selected = ""
        return self._ok(self.scene_name)
      case new.SceneFromJson(text):
        self.scene_name = scene_from_json(self.world, text)
        self.selected = ""
        return self._ok(self.scene_name)
      case _:
        return self._fail("unknown command")

  def dump_json(self) -> str:
    return scene_to_json(self.world, self.scene_name)
