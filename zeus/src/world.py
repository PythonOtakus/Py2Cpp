"""``World``：场景根与 Task 主循环。"""
from __future__ import annotations

from py2cpp import *
from py2cpp.spatial.color import Color

from .scene import GameObject
from .task import Task

WORLD_STOPPED: int = 0
WORLD_PLAYING: int = 1
WORLD_PAUSED: int = 2


@refcount
class World:
  """引擎世界：对象树根 + detect→update→draw→refresh。"""

  state: int = 0
  dt: float64 = 0.016
  clear_color: Color = new(0.1, 0.1, 0.15, 1.0)
  root: GameObject = new("world_root")
  _tasks: list[Task] = []
  _quit: bool = False

  def __init__(self):
    self.state = WORLD_STOPPED
    self.dt = 0.016
    self.clear_color = new(0.1, 0.1, 0.15, 1.0)
    self.root = new("world_root")
    self._tasks = []
    self._quit = False
    self._tasks.append(Task("detect"))
    self._tasks.append(Task("update"))
    self._tasks.append(Task("draw"))
    self._tasks.append(Task("refresh"))

  def clear(self) -> None:
    self.root = new("world_root")
    self._quit = False

  def quit(self) -> None:
    self._quit = True
    self.state = WORLD_STOPPED

  def play(self) -> None:
    self.state = WORLD_PLAYING
    self._quit = False

  def pause(self) -> None:
    self.state = WORLD_PAUSED

  def detect(self) -> None:
    pass

  def update(self) -> None:
    if self.state != WORLD_PLAYING:
      return
    self.root.update(self.dt)

  def draw(self) -> None:
    if self.state == WORLD_STOPPED:
      return
    self.root.draw()

  def refresh(self) -> None:
    pass

  def step(self) -> None:
    if self._quit:
      return
    for i in range(len(self._tasks)):
      t: Task = self._tasks[i]
      if not t.enabled:
        continue
      match t.name:
        case "detect":
          self.detect()
        case "update":
          self.update()
        case "draw":
          self.draw()
        case "refresh":
          self.refresh()
        case _:
          pass

  def run_frames(self, frames: int) -> int:
    self.play()
    n: int = 0
    while n < frames and not self._quit:
      self.step()
      n += 1
    return n
