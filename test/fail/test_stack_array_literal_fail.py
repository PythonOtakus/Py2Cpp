"""负向：``T[:N]`` 列表字面量长度与 ``N`` 不一致时翻译失败（``build_fail.bat``）。"""
from py2cpp import *


def main():
  buf: int[:4] = [1, 2, 3]
