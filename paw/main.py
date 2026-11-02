#!/usr/bin/env python3
"""薄入口：转发到 ``python -m cmd.paw``（亦可直接调用本文件）。"""
from __future__ import annotations

import sys

from cmd.paw.__main__ import main

if __name__ == "__main__":
  sys.exit(main())
