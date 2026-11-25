# -*- coding: utf-8 -*-
"""策略注册入口契约测试。"""

import pytest


from jingniflow.api.lifecycle import (
    jingni_get_strategy,
    jingni_handle_data,
    jingni_main,
    jingni_set_strategy,
)


class Recorder(object):
    def __init__(self):
        self.calls = []

    def __call__(self, trade_mode, context_data):
        self.calls.append((trade_mode, context_data))
        return "called"


def _raw():
    # 每个测试用独立对象，避免 resolve_context 的 id 缓存串场。
    return object()


def test_main_registers_strategy_and_handle_data_uses_it():
    raw = _raw()
    recorder = Recorder()
    try:
        jingni_main("qmt", raw, strategy=recorder)
        assert jingni_get_strategy("qmt", raw) is recorder
        result = jingni_handle_data("qmt", raw)
        assert result == "called"
        assert len(recorder.calls) == 1
        assert recorder.calls[0][0] == "qmt"
    finally:
        jingni_set_strategy(None)


def test_set_strategy_before_main_is_used():
    raw = _raw()
    recorder = Recorder()
    try:
        jingni_set_strategy(recorder)
        jingni_main("qmt", raw)
        jingni_handle_data("qmt", raw)
        assert recorder.calls == [("qmt", raw)]
    finally:
        jingni_set_strategy(None)


def test_explicit_handle_strategy_overrides_registered():
    raw = _raw()
    registered = Recorder()
    explicit = Recorder()
    try:
        jingni_main("qmt", raw, strategy=registered)
        jingni_handle_data("qmt", raw, strategy=explicit)
        assert registered.calls == []
        assert explicit.calls == [("qmt", raw)]
    finally:
        jingni_set_strategy(None)


def test_clear_strategy_restores_placeholder():
    raw = _raw()
    recorder = Recorder()
    try:
        jingni_set_strategy(recorder)
        jingni_set_strategy(None)
        assert jingni_get_strategy() is None
        jingni_handle_data("qmt", raw)
        assert recorder.calls == []
    finally:
        jingni_set_strategy(None)


def test_non_callable_strategy_is_rejected():
    with pytest.raises(TypeError):
        jingni_set_strategy("not-a-function")
    with pytest.raises(TypeError):
        jingni_handle_data("qmt", _raw(), strategy="not-a-function")
    jingni_set_strategy(None)
