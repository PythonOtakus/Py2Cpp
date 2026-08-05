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
  enc.dump_key(key)
  enc.begin_array()
  enc.dump_float(v.x)
  enc.dump_float(v.y)
  enc.dump_float(v.z)
  enc.end_array()


def _dump_quat(enc: JsonEncoder @ref, key: str, q: Quaternion) -> None:
  enc.dump_key(key)
  enc.begin_array()
  enc.dump_float(q.x)
  enc.dump_float(q.y)
  enc.dump_float(q.z)
  enc.dump_float(q.w)
  enc.end_array()


def _dump_transform(enc: JsonEncoder @ref, xf: Transform) -> None:
  enc.dump_key("root_transform")
  enc.begin_object()
  _dump_vec3(enc, "local_position", xf.local_position)
  _dump_quat(enc, "local_rotation", xf.local_rotation)
  _dump_vec3(enc, "local_scale", xf.local_scale)
  enc.end_object()


def _dump_component(enc: JsonEncoder @ref, c: Component) -> None:
  enc.begin_object()
  enc.dump_field_str("type", c.kind)
  match c.kind:
    case "MeshComponent":
      mesh_ref: str = c.asset_path
      if not mesh_ref:
        mesh_ref = "cube"
      enc.dump_field_str("mesh", mesh_ref)
      enc.dump_field_str("material", "default")
    case "CameraComponent":
      enc.dump_key("fov_deg")
      enc.dump_float(60.0)
      enc.dump_key("z_near")
      enc.dump_float(0.1)
      enc.dump_key("z_far")
      enc.dump_float(100.0)
    case "JumpMotor":
      enc.dump_key("jump_power")
      enc.dump_float(c.inspect_float("jump_power"))
      enc.dump_key("max_charge")
      enc.dump_float(c.inspect_float("max_charge"))
    case "PlatformPad":
      enc.dump_key("half_x")
      enc.dump_float(1.0)
      enc.dump_key("half_z")
      enc.dump_float(1.0)
    case _:
      pass
  enc.end_object()


def _dump_game_object(enc: JsonEncoder @ref, go: GameObject) -> None:
  enc.begin_object()
  enc.dump_field_str("type", "GameObject")
  enc.dump_field_str("name", go.name)
  enc.dump_field_bool("active", go.active)
  enc.dump_field_bool("visible", go.visible)
  _dump_transform(enc, go.root)
  enc.dump_key("components")
  enc.begin_array()
  for i in range(go.component_count()):
    c: Component = go.component_at(i)
    if c.kind == "Transform":
      continue
    _dump_component(enc, c)
  enc.end_array()
  enc.dump_key("children")
  enc.begin_array()
  for j in range(go.child_count):
    _dump_game_object(enc, go.child_at(j))
  enc.end_array()
  enc.end_object()


def scene_to_json(world: World, scene_name: str = "Scene") -> str:
  enc: JsonEncoder = new()
  enc.begin_object()
  enc.dump_key("zas")
  enc.dump_int(ZAS_VERSION)
  enc.dump_field_str("kind", "scene")
  enc.dump_field_str("name", scene_name)
  enc.dump_key("root")
  _dump_game_object(enc, world.root)
  enc.end_object()
  return enc.take()


def scene_save(world: World, path: str, scene_name: str = "Scene") -> None:
  p: str = ensure_suffix(path, ZAS_SUFFIX)
  if not is_zas(p):
    p = path
    p += ZAS_SUFFIX
  doc: Path = new(p)
  doc.write_text(scene_to_json(world, scene_name))


def _load_float_list3(dec: JsonDecoder @ref) -> Vector3:
  dec.begin_array()
  x: float64 = 0.0
  y: float64 = 0.0
  z: float64 = 0.0
  if not dec.at_array_end():
    x = dec.parse_float_at()
    dec.skip_spaces()
    if not dec.at_array_end():
      dec.expect_char(",")
      dec.skip_spaces()
      y = dec.parse_float_at()
      dec.skip_spaces()
      if not dec.at_array_end():
        dec.expect_char(",")
        dec.skip_spaces()
        z = dec.parse_float_at()
        dec.skip_spaces()
        if not dec.at_array_end():
          dec.fail("vec3 too long")
  return new(x, y, z)


def _load_float_list4(dec: JsonDecoder @ref) -> Quaternion:
  dec.begin_array()
  x: float64 = 0.0
  y: float64 = 0.0
  z: float64 = 0.0
  w: float64 = 1.0
  if not dec.at_array_end():
    x = dec.parse_float_at()
    dec.skip_spaces()
    if not dec.at_array_end():
      dec.expect_char(",")
      dec.skip_spaces()
      y = dec.parse_float_at()
      dec.skip_spaces()
      if not dec.at_array_end():
        dec.expect_char(",")
        dec.skip_spaces()
        z = dec.parse_float_at()
        dec.skip_spaces()
        if not dec.at_array_end():
          dec.expect_char(",")
          dec.skip_spaces()
          w = dec.parse_float_at()
          dec.skip_spaces()
          if not dec.at_array_end():
            dec.fail("quat too long")
  return new(w, x, y, z)


def _apply_transform(xf: Transform, dec: JsonDecoder @ref) -> None:
  dec.skip_spaces()
  dec.expect_char("{")
  while not dec.at_object_end():
    key: str = dec.load_key()
    match key:
      case "local_position":
        xf.local_position = _load_float_list3(dec)
      case "local_rotation":
        xf.local_rotation = _load_float_list4(dec)
      case "local_scale":
        xf.local_scale = _load_float_list3(dec)
      case _:
        dec.skip_value()


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
  dec.skip_spaces()
  dec.expect_char("{")
  while not dec.at_object_end():
    key: str = dec.load_key()
    match key:
      case "type":
        typ = dec.load_str()
      case "mesh":
        mesh = dec.load_str()
      case "material":
        dec.load_str()
      case "fov_deg":
        fov = dec.parse_float_at()
      case "z_near":
        z_near = dec.parse_float_at()
      case "z_far":
        z_far = dec.parse_float_at()
      case "jump_power":
        jump_power = dec.parse_float_at()
      case "max_charge":
        max_charge = dec.parse_float_at()
      case "half_x":
        half_x = dec.parse_float_at()
      case "half_z":
        half_z = dec.parse_float_at()
      case _:
        dec.skip_value()
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
  dec.skip_spaces()
  dec.expect_char("{")
  while not dec.at_object_end():
    key: str = dec.load_key()
    match key:
      case "type":
        dec.load_str()
      case "name":
        name = dec.load_str()
      case "active":
        active = dec.parse_bool_at()
      case "visible":
        visible = dec.parse_bool_at()
      case "root_transform":
        _apply_transform(go.root, dec)
      case "components":
        dec.begin_array()
        dec.skip_spaces()
        if not dec.at_array_end():
          while True:
            _load_component(go, dec)
            dec.skip_spaces()
            if dec.at_array_end():
              break
            dec.expect_char(",")
            dec.skip_spaces()
      case "children":
        dec.begin_array()
        dec.skip_spaces()
        if not dec.at_array_end():
          while True:
            child: GameObject = _load_game_object(dec)
            child.parent = go
            dec.skip_spaces()
            if dec.at_array_end():
              break
            dec.expect_char(",")
            dec.skip_spaces()
      case _:
        dec.skip_value()
  go.name = name
  go.active = active
  go.visible = visible
  go.root.name = "root"
  return go


def scene_from_json(world: World, text: str) -> str:
  """解析 ``.zas`` / 场景 JSON，替换 ``world.root``；返回场景 ``name``。"""
  dec: JsonDecoder = new.from_text(text)
  scene_name: str = "Scene"
  dec.begin_root_object()
  while not dec.at_object_end():
    key: str = dec.load_key()
    match key:
      case "name":
        scene_name = dec.load_str()
      case "zas":
        dec.parse_int_at()
      case "kind":
        dec.load_str()
      case "root":
        world.root = _load_game_object(dec)
      case _:
        dec.skip_value()
  return scene_name


def scene_load(world: World, path: str) -> str:
  p: str = ensure_suffix(path, ZAS_SUFFIX)
  doc: Path = new(p)
  return scene_from_json(world, doc.read_text())
