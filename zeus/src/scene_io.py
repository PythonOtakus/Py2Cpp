"""场景 ``.zas``（Zeus Asset）：JSON 嵌套图式往返。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.io.path import Path
from py2cpp.serde.json import JsonDecoder, JsonEncoder
from py2cpp.spatial.rotator import Quaternion
from py2cpp.spatial.vector import Vector3

from .assets import ZAS_SUFFIX, ZAS_VERSION, ensure_suffix, is_fbx, is_zas
from .jump.motor import JumpMotor
from .jump.platform import PlatformPad
from .scene import CameraComponent, Component, GameObject, MeshComponent, Transform
from .world import World


def _dump_vec3(enc: JsonEncoder @ref, key: str, v: Vector3) -> None:
  enc.dumpKey(key)
  enc.beginArray()
  enc.dumpFloat(v.x)
  enc.dumpFloat(v.y)
  enc.dumpFloat(v.z)
  enc.endArray()


def _dump_quat(enc: JsonEncoder @ref, key: str, q: Quaternion) -> None:
  enc.dumpKey(key)
  enc.beginArray()
  enc.dumpFloat(q.x)
  enc.dumpFloat(q.y)
  enc.dumpFloat(q.z)
  enc.dumpFloat(q.w)
  enc.endArray()


def _dump_transform(enc: JsonEncoder @ref, xf: Transform) -> None:
  enc.dumpKey("root_transform")
  enc.beginObject()
  _dump_vec3(enc, "local_position", xf.localPosition)
  _dump_quat(enc, "local_rotation", xf.localRotation)
  _dump_vec3(enc, "local_scale", xf.localScale)
  enc.endObject()


def _dump_component(enc: JsonEncoder @ref, c: Component) -> None:
  enc.beginObject()
  enc.dumpFieldStr("type", c.kind)
  match c.kind:
    case "MeshComponent":
      mesh_ref: str = c.asset_path
      if not mesh_ref:
        mesh_ref = "cube"
      enc.dumpFieldStr("mesh", mesh_ref)
      enc.dumpFieldStr("material", "default")
    case "CameraComponent":
      enc.dumpKey("fov_deg")
      enc.dumpFloat(60.0)
      enc.dumpKey("z_near")
      enc.dumpFloat(0.1)
      enc.dumpKey("z_far")
      enc.dumpFloat(100.0)
    case "JumpMotor":
      enc.dumpKey("jump_power")
      enc.dumpFloat(c.inspect_float("jump_power"))
      enc.dumpKey("max_charge")
      enc.dumpFloat(c.inspect_float("max_charge"))
    case "PlatformPad":
      enc.dumpKey("half_x")
      enc.dumpFloat(1.0)
      enc.dumpKey("half_z")
      enc.dumpFloat(1.0)
    case _:
      pass
  enc.endObject()


def _dump_game_object(enc: JsonEncoder @ref, go: GameObject) -> None:
  enc.beginObject()
  enc.dumpFieldStr("type", "GameObject")
  enc.dumpFieldStr("name", go.name)
  enc.dumpFieldBool("active", go.active)
  enc.dumpFieldBool("visible", go.visible)
  _dump_transform(enc, go.root)
  enc.dumpKey("components")
  enc.beginArray()
  for i in range(go.component_count()):
    c: Component = go.component_at(i)
    if c.kind == "Transform":
      continue
    _dump_component(enc, c)
  enc.endArray()
  enc.dumpKey("children")
  enc.beginArray()
  for j in range(go.child_count):
    _dump_game_object(enc, go.child_at(j))
  enc.endArray()
  enc.endObject()


def scene_to_json(world: World, scene_name: str = "Scene") -> str:
  enc: JsonEncoder = new()
  enc.beginObject()
  enc.dumpKey("zas")
  enc.dumpInt(ZAS_VERSION)
  enc.dumpFieldStr("kind", "scene")
  enc.dumpFieldStr("name", scene_name)
  enc.dumpKey("root")
  _dump_game_object(enc, world.root)
  enc.endObject()
  return enc.take()


def scene_save(world: World, path: str, scene_name: str = "Scene") -> None:
  p: str = ensure_suffix(path, ZAS_SUFFIX)
  if not is_zas(p):
    p = path
    p += ZAS_SUFFIX
  doc: Path = new(p)
  doc.writeText(scene_to_json(world, scene_name))


def _load_float_list3(dec: JsonDecoder @ref) -> Vector3:
  dec.beginArray()
  x: float64 = 0.0
  y: float64 = 0.0
  z: float64 = 0.0
  if not dec.atArrayEnd():
    x = dec.parseFloatAt()
    dec.skipSpaces()
    if not dec.atArrayEnd():
      dec.expectChar(",")
      dec.skipSpaces()
      y = dec.parseFloatAt()
      dec.skipSpaces()
      if not dec.atArrayEnd():
        dec.expectChar(",")
        dec.skipSpaces()
        z = dec.parseFloatAt()
        dec.skipSpaces()
        if not dec.atArrayEnd():
          dec.fail("vec3 too long")
  return new(x, y, z)


def _load_float_list4(dec: JsonDecoder @ref) -> Quaternion:
  dec.beginArray()
  x: float64 = 0.0
  y: float64 = 0.0
  z: float64 = 0.0
  w: float64 = 1.0
  if not dec.atArrayEnd():
    x = dec.parseFloatAt()
    dec.skipSpaces()
    if not dec.atArrayEnd():
      dec.expectChar(",")
      dec.skipSpaces()
      y = dec.parseFloatAt()
      dec.skipSpaces()
      if not dec.atArrayEnd():
        dec.expectChar(",")
        dec.skipSpaces()
        z = dec.parseFloatAt()
        dec.skipSpaces()
        if not dec.atArrayEnd():
          dec.expectChar(",")
          dec.skipSpaces()
          w = dec.parseFloatAt()
          dec.skipSpaces()
          if not dec.atArrayEnd():
            dec.fail("quat too long")
  return new(w, x, y, z)


def _apply_transform(xf: Transform, dec: JsonDecoder @ref) -> None:
  dec.skipSpaces()
  dec.expectChar("{")
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    match key:
      case "local_position":
        xf.localPosition = _load_float_list3(dec)
      case "local_rotation":
        xf.localRotation = _load_float_list4(dec)
      case "local_scale":
        xf.localScale = _load_float_list3(dec)
      case _:
        dec.skipValue()


def _load_component(go: GameObject, dec: JsonDecoder @ref) -> None:
  typ: str = "Component"
  mesh: str = ""
  fov: float64 = 60.0
  z_near: float64 = 0.1
  z_far: float64 = 100.0
  jump_power: float64 = 8.0
  max_charge: float64 = 1.2
  half_x: float64 = 1.0
  half_z: float64 = 1.0
  dec.skipSpaces()
  dec.expectChar("{")
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    match key:
      case "type":
        typ = dec.loadStr()
      case "mesh":
        mesh = dec.loadStr()
      case "material":
        dec.loadStr()
      case "fov_deg":
        fov = dec.parseFloatAt()
      case "z_near":
        z_near = dec.parseFloatAt()
      case "z_far":
        z_far = dec.parseFloatAt()
      case "jump_power":
        jump_power = dec.parseFloatAt()
      case "max_charge":
        max_charge = dec.parseFloatAt()
      case "half_x":
        half_x = dec.parseFloatAt()
      case "half_z":
        half_z = dec.parseFloatAt()
      case _:
        dec.skipValue()
  match typ:
    case "MeshComponent":
      mc: MeshComponent = new()
      if is_fbx(mesh):
        mc.load_fbx(mesh)
      else:
        mc.set_cube(1.0)
      go.add_component(mc)
    case "CameraComponent":
      cam: CameraComponent = new()
      cam.fov_deg = fov
      cam.z_near = z_near
      cam.z_far = z_far
      go.add_component(cam)
    case "JumpMotor":
      jm: JumpMotor = new()
      jm.jump_power = jump_power
      jm.max_charge = max_charge
      go.add_component(jm)
    case "PlatformPad":
      pad: PlatformPad = new()
      pad.half_x = half_x
      pad.half_z = half_z
      go.add_component(pad)
    case _:
      pass


def _load_game_object(dec: JsonDecoder @ref) -> GameObject:
  name: str = "GameObject"
  active: bool = True
  visible: bool = True
  go: GameObject = new("tmp")
  dec.skipSpaces()
  dec.expectChar("{")
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    match key:
      case "type":
        dec.loadStr()
      case "name":
        name = dec.loadStr()
      case "active":
        active = dec.parseBoolAt()
      case "visible":
        visible = dec.parseBoolAt()
      case "root_transform":
        _apply_transform(go.root, dec)
      case "components":
        dec.beginArray()
        dec.skipSpaces()
        if not dec.atArrayEnd():
          while True:
            _load_component(go, dec)
            dec.skipSpaces()
            if dec.atArrayEnd():
              break
            dec.expectChar(",")
            dec.skipSpaces()
      case "children":
        dec.beginArray()
        dec.skipSpaces()
        if not dec.atArrayEnd():
          while True:
            child: GameObject = _load_game_object(dec)
            child.parent = go
            dec.skipSpaces()
            if dec.atArrayEnd():
              break
            dec.expectChar(",")
            dec.skipSpaces()
      case _:
        dec.skipValue()
  go.name = name
  go.active = active
  go.visible = visible
  go.root.name = "root"
  return go


def scene_from_json(world: World, text: str) -> str:
  """解析 ``.zas`` / 场景 JSON，替换 ``world.root``；返回场景 ``name``。"""
  dec: JsonDecoder = new.fromText(text)
  scene_name: str = "Scene"
  dec.beginRootObject()
  while not dec.atObjectEnd():
    key: str = dec.loadKey()
    match key:
      case "name":
        scene_name = dec.loadStr()
      case "zas":
        dec.parseIntAt()
      case "kind":
        dec.loadStr()
      case "root":
        world.root = _load_game_object(dec)
      case _:
        dec.skipValue()
  return scene_name


def scene_load(world: World, path: str) -> str:
  p: str = ensure_suffix(path, ZAS_SUFFIX)
  doc: Path = new(p)
  return scene_from_json(world, doc.readText())
