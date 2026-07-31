"""打开 Zeus 编辑器：加载跳一跳示例场景 ``main.zas``。"""
from py2cpp import *
from py2cpp.io.path import Path

from .command import CommandResult, ZeusCommand
from .editor.shell import EditorShell


def _load_jump_scene(shell: EditorShell) -> int:
  jump_scene: str = "zeus/examples/jump_demo/scenes/main.zas"
  scene: Path = new(jump_scene)
  if not scene.exists():
    print("scene not found: " + jump_scene)
    return 1
  r: CommandResult = shell.session.dispatch(ZeusCommand.SceneLoad(jump_scene))
  if not r.ok:
    print("SceneLoad failed: " + r.message)
    return 1
  shell.session.dispatch(ZeusCommand.EditorSelect("Player"))
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
