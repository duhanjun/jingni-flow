# -*- coding: utf-8 -*-
"""JingniFlow 包入口。"""

from .compat import legacy as _legacy
from .version import __version__, __version_info__

__all__ = list(_legacy.__all__) + ["__version__", "__version_info__"]

# 旧版 ``from jingniflow import *`` 的导出面保持在 compat/legacy.py 的
# __all__ 中；这里用显式映射避免包入口再出现 star import。
for _name in _legacy.__all__:
    globals()[_name] = getattr(_legacy, _name)
del _name
