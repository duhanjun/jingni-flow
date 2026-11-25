# -*- coding: utf-8 -*-
"""运行上下文与平台 API 解析。

三家平台的 API 都不是可以稳定 import 的普通包：
- 掘金通过 ``gm.api`` 注入；
- QMT 在策略模块的全局命名空间中注入；
- PTrade 在策略模块的全局命名空间中注入。

因此这里用一个很小的 ``platform_call`` 解析器：优先当前模块全局，
其次 ``__main__`` 全局，再次显式注册表（测试/嵌入场景），最后尝试
``gm.api``。单文件发行物被复制到策略尾部时，前两种方式即可工作。
"""

import datetime

from .config import RuntimeConfig
from .contract import normalize_platform
from .errors import PlatformApiMissing


DEFAULT_MODE = "软件名称"
_PLATFORM_APIS = {}
_CONTEXT_CACHE = {}


def python_version_text():
    """返回 Python 版本文本；PTrade 禁用系统模块，失败时降级为 unknown。"""
    try:
        return __import__("platform").python_version()
    except Exception:
        return "unknown"


def _main_namespace():
    """返回策略主模块命名空间；单文件模式下就是当前 globals。"""
    if "__name__" in globals() and globals().get("__name__") == "__main__":
        return globals()
    try:
        main = __import__("__main__")
    except Exception:
        return globals()
    return getattr(main, "__dict__", None) or globals()


def set_default_mode(mode):
    global DEFAULT_MODE
    DEFAULT_MODE = normalize_platform(mode) or mode
    return DEFAULT_MODE


def get_default_mode():
    """读取策略模块的 trade_mode；兼容旧全局变量。"""
    current = globals().get("trade_mode")
    if current and current != "软件名称":
        return normalize_platform(current)
    main = _main_namespace()
    value = main.get("trade_mode")
    if value and value != "软件名称":
        return normalize_platform(value)
    return normalize_platform(DEFAULT_MODE) or DEFAULT_MODE


def register_api(mapping):
    """注册平台函数表，主要用于测试或嵌入式运行。"""
    if mapping:
        _PLATFORM_APIS.update(mapping)
    return _PLATFORM_APIS


def clear_api_registry():
    _PLATFORM_APIS.clear()
    _CONTEXT_CACHE.clear()


def get_platform_global(name, default=None):
    """从当前模块或 __main__ 读取平台注入的全局变量。"""
    if name in globals():
        return globals()[name]
    main = _main_namespace()
    if name in main:
        return main[name]
    return default


def get_platform_constant(name, default=None):
    """读取平台常量（如 OrderSide_Buy / ADJUST_PREV）。"""
    value = get_platform_global(name)
    if value is not None:
        return value
    if name in _PLATFORM_APIS:
        return _PLATFORM_APIS[name]
    try:
        import gm.api as gm_api

        return getattr(gm_api, name, default)
    except Exception:
        return default


def platform_call(name, *args, **kwargs):
    """按优先级解析并调用平台函数。"""
    fn = globals().get(name)
    if fn is None:
        main = _main_namespace()
        fn = main.get(name)
    if fn is None:
        fn = _PLATFORM_APIS.get(name)
    if fn is None:
        try:
            import gm.api as gm_api

            fn = getattr(gm_api, name, None)
        except Exception:
            fn = None
    if fn is None:
        raise PlatformApiMissing("platform api not found: {0}".format(name))
    return fn(*args, **kwargs)


def _detect_mode(platform, raw):
    if raw is None:
        return "unknown"
    if platform == "goldminer":
        mode = getattr(raw, "mode", None)
        if mode == 1:
            return "live"
        if mode == 2:
            return "backtest"
        return "unknown"
    if platform == "qmt":
        return "backtest" if bool(getattr(raw, "do_back_test", False)) else "live"
    if platform == "ptrade":
        try:
            return "live" if bool(platform_call("is_trade")) else "backtest"
        except Exception:
            return "unknown"
    return "unknown"


class RuntimeContext(object):
    """平台无关的运行上下文。"""

    def __init__(self, platform, raw=None, config=None):
        self.platform = normalize_platform(platform) or platform
        self.raw = raw
        self.config = config or RuntimeConfig()
        self.mode = _detect_mode(self.platform, raw)

    @property
    def is_backtest(self):
        return self.mode == "backtest"

    @property
    def is_live(self):
        return self.mode == "live"

    def now(self):
        """返回策略时钟；QMT/PTrade 优先使用回测时钟。"""
        try:
            if self.platform == "goldminer" and self.raw is not None:
                value = getattr(self.raw, "now", None)
                if callable(value):
                    value = value()
                if value is not None:
                    return value
            if self.platform == "qmt" and self.raw is not None:
                barpos = getattr(self.raw, "barpos", None)
                if barpos is not None:
                    timetag = self.raw.get_bar_timetag(barpos)
                    value = platform_call(
                        "timetag_to_datetime", timetag, "%Y-%m-%d %H:%M:%S"
                    )
                    if isinstance(value, str):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
                            try:
                                return datetime.datetime.strptime(value, fmt)
                            except ValueError:
                                continue
                    return value
            if self.platform == "ptrade" and self.raw is not None:
                blotter = getattr(self.raw, "blotter", None)
                current_dt = getattr(blotter, "current_dt", None)
                if current_dt is not None:
                    return current_dt
        except Exception:
            pass
        return datetime.datetime.now()

    def trade_date(self, fmt="%Y%m%d"):
        return self.now().strftime(fmt)

    def account_id(self):
        if self.config.account_id:
            return self.config.account_id
        return get_platform_global("account")


def resolve_context(trade_mode, context_data, config=None):
    """把旧式 (trade_mode, context_data) 解析为 RuntimeContext。"""
    if isinstance(trade_mode, RuntimeContext):
        if config is not None:
            trade_mode.config = config
        return trade_mode
    platform = normalize_platform(trade_mode) or get_default_mode()
    raw = context_data
    key = (platform, id(raw) if raw is not None else None)
    context = _CONTEXT_CACHE.get(key)
    if context is None:
        context = RuntimeContext(platform, raw=raw, config=config)
        _CONTEXT_CACHE[key] = context
    elif config is not None:
        context.config = config
    return context
