# -*- coding: utf-8 -*-
"""单文件产物契约测试。"""

import ast
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_single_file_build_and_py36_grammar():
    subprocess.check_call(
        [sys.executable, os.path.join("tools", "build_single.py"), "--root"],
        cwd=ROOT,
    )
    subprocess.check_call(
        [
            sys.executable,
            os.path.join("tools", "build_single.py"),
            "--check",
            "--root",
        ],
        cwd=ROOT,
    )
    utf8_path = os.path.join(ROOT, "dist", "jingniflow_single.py")
    gbk_path = os.path.join(ROOT, "dist", "jingniflow_single_gbk.py")
    manifest_path = os.path.join(ROOT, "dist", "build-manifest.json")
    subprocess.check_call(
        [sys.executable, os.path.join("tools", "build_smoke.py")], cwd=ROOT
    )
    subprocess.check_call(
        [
            sys.executable,
            os.path.join("tools", "build_smoke.py"),
            "--check",
        ],
        cwd=ROOT,
    )
    with io.open(utf8_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    assert "from .." not in text
    assert "from ." not in text
    assert "# Source-SHA256:" in text
    assert "# Build-UTC:" in text
    assert os.path.exists(manifest_path)
    ast.parse(text, feature_version=(3, 6))
    with io.open(gbk_path, "r", encoding="gbk") as handle:
        gbk_text = handle.read()
    assert gbk_text.startswith("# coding: gbk")
    assert "# Source-SHA256:" in gbk_text
    ast.parse(gbk_text, feature_version=(3, 6))

    # 单文件尾部的 legacy trade_mode 不能覆盖冒烟脚本已设置的平台名。
    smoke_cases = (
        ("goldminer_smoke_full.py", "utf-8", "goldminer"),
        ("qmt_smoke_full.py", "gbk", "qmt"),
        ("ptrade_smoke_full.py", "utf-8", "ptrade"),
    )
    for name, encoding, expected in smoke_cases:
        path = os.path.join(ROOT, "dist", "smoke", name)
        with io.open(path, "r", encoding=encoding) as handle:
            source = handle.read()
        namespace = {"__name__": "smoke_contract"}
        exec(compile(source, path, "exec"), namespace)
        assert namespace["trade_mode"] == expected
        assert callable(namespace["jingni_set_strategy"])
        assert callable(namespace["jingni_get_strategy"])

    ptrade_path = os.path.join(ROOT, "dist", "smoke", "ptrade_smoke_full.py")
    with io.open(ptrade_path, "r", encoding="utf-8") as handle:
        ptrade_text = handle.read()
    assert "import sys" not in ptrade_text
    assert "sys." not in ptrade_text
    ptrade_tree = ast.parse(ptrade_text, feature_version=(3, 5))
    for node in ast.walk(ptrade_tree):
        assert not isinstance(node, ast.JoinedStr)
        assert not isinstance(node, ast.AnnAssign)

    subprocess.check_call(
        [sys.executable, os.path.join("tools", "verify_release.py")], cwd=ROOT
    )
