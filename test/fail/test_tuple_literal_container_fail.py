"""负向：元组字面量不得作 in / 下标容器（应翻译失败）。"""


from py2cpp import *
def use_in():
  x: int = 1
  if x in (1, 2, 3):
  # expect NotImplementedError at translate
    pass


def use_subscript():
  y: int = (10, 20, 30)[1]
  # expect NotImplementedError at translate
  _ = y
