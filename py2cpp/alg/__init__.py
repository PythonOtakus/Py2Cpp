"""``alg`` 域：竞赛 / 游戏常用数据结构（纯 Python → C++ 模板）。"""
from ..builtins import *
from .agg_mode import AggMode
from .ac_auto import ACAuto
from .dsu import DSU
from .fen_tree import FenTree
from .heap import Heap, IndexedHeap
from .mono_queue import MonoQueue
from .chunk_deque import ChunkDeque
from .seg_tree import SegTree
from .sparse_table import SparseTable
from .trie import Trie
from .protocols import Navigatable
from .grid2d import Cell, Grid2D, GridConnectivity, GridNav
from .graph import AdjList, Edge, GraphNav
from .navigate import astar, dijkstra

__all__ = [
  "AggMode",
  "ACAuto",
  "DSU",
  "FenTree",
  "Heap",
  "IndexedHeap",
  "MonoQueue",
  "ChunkDeque",
  "SegTree",
  "SparseTable",
  "Trie",
  "Navigatable",
  "Cell",
  "Grid2D",
  "GridConnectivity",
  "GridNav",
  "AdjList",
  "Edge",
  "GraphNav",
  "astar",
  "dijkstra",
]
