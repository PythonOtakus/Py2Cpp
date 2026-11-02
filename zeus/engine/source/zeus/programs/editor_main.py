"""打开 Zeus 编辑器：加载跳一跳示例场景 ``main.zas``。"""
from paw import *
from paw.io.path import Path

from zeus.developer.command import CommandResult, ZeusCommandUnion
from zeus.editor.shell import EditorShell


def _load_jump_scene(shell: EditorShell) -> int:
  jump_scene: str = "zeus/samples/jump/content/scenes/main.zas"
  scene: Path = new(jump_scene)
  if not scene.exists():
    print("scene not found: " + jump_scene)
    return 1
  r: CommandResult = shell.session.dispatch(ZeusCommandUnion.SceneLoad(jump_scene))
  if not r.ok:
    print("SceneLoad failed: " + r.message)
    return 1
  shell.session.dispatch(ZeusCommandUnion.EditorSelect("Player"))
  print("Zeus editor: " + jump_scene + " (" + shell.session.bus.scene_name + ")")
  return 0


def main() -> int:
  shell: EditorShell = new()
  code: int = _load_jump_scene(shell)
  if code != 0:
    return code
  return shell.run()


if __name__ == "__main__":
  raise SystemExit(main())
