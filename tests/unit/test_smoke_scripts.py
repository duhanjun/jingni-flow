# -*- coding: utf-8 -*-
"""三端冒烟脚本的静态契约测试。"""

import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SMOKE_DIR = os.path.join(ROOT, "examples", "smoke")
FILES = ("goldminer_smoke.py", "qmt_smoke.py", "ptrade_smoke.py")


def test_smoke_scripts_are_safe_and_py36_compatible():
    for name in FILES:
        path = os.path.join(SMOKE_DIR, name)
        with io.open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        assert "SMOKE_REAL_ORDER = False" in text
        assert "jingni_order_amount" in text
        assert "jingni_schedule" in text
        assert "validator=lambda result: result is not None" in text
        assert "jingni_doctor" in text
        assert "_smoke_summary" in text
        assert "SMOKE VERIFICATION SUCCESS" in text
        assert "[SMOKE][SKIP]" in text
        assert "_JINGNI_RUNTIME = jingni_main" in text
        ast.parse(text, feature_version=(3, 6))

    goldminer_text = io.open(
        os.path.join(SMOKE_DIR, "goldminer_smoke.py"), "r", encoding="utf-8"
    ).read()
    assert "def on_backtest_finished(context, indicator)" in goldminer_text
    qmt_text = io.open(
        os.path.join(SMOKE_DIR, "qmt_smoke.py"), "r", encoding="utf-8"
    ).read()
    assert "def on_backtest_finished(ContextInfo)" in qmt_text
    ptrade_text = io.open(
        os.path.join(SMOKE_DIR, "ptrade_smoke.py"), "r", encoding="utf-8"
    ).read()
    assert "def after_trading_end(context, data)" in ptrade_text

    qmt_path = os.path.join(SMOKE_DIR, "qmt_smoke.py")
    with io.open(qmt_path, "rb") as handle:
        raw = handle.read()
    assert all(byte < 128 for byte in raw)
