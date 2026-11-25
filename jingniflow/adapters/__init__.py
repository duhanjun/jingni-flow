# -*- coding: utf-8 -*-
"""适配器注册表。"""

from ..core.errors import ValidationError
from ..core.runtime import resolve_context
from .goldminer import GoldminerAdapter
from .ptrade import PtradeAdapter
from .qmt import QmtAdapter

ADAPTERS = {
    "goldminer": GoldminerAdapter,
    "qmt": QmtAdapter,
    "ptrade": PtradeAdapter,
}


def get_adapter(trade_mode, context_data, config=None):
    context = resolve_context(trade_mode, context_data, config=config)
    cls = ADAPTERS.get(context.platform)
    if cls is None:
        raise ValidationError("unsupported platform: {0}".format(context.platform))
    return cls(context)
