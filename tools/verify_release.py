# -*- coding: utf-8 -*-
"""发布产物契约校验。

这个脚本不做构建，只校验已经生成的 dist 产物和根目录单文件。CI 在
``build_single.py`` / ``build_smoke.py`` 之后运行它，用来兜住那些单纯
hash 校验发现不了的平台约束：

- QMT full 必须是可解码的 GBK，且可按 Python 3.6 语法编译；
- PTrade full 不得出现 ``sys`` 引用，并满足 Python 3.5 语法约束；
- 三份 full 的 ``trade_mode`` 不能被 legacy 尾部覆盖；
- 根 ``jingniflow.py`` 必须与 dist UTF-8 单文件逐字节一致；
- manifest 必须存在，并包含三类单文件产物。

脚本本身保持 Python 3.6 兼容，不依赖 pytest。
"""

import ast
import hashlib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
UTF8_PATH = os.path.join(DIST, "jingniflow_single.py")
GBK_PATH = os.path.join(DIST, "jingniflow_single_gbk.py")
ROOT_PATH = os.path.join(ROOT, "jingniflow.py")
MANIFEST_PATH = os.path.join(DIST, "build-manifest.json")

SMOKE_CASES = (
    ("goldminer_smoke_full.py", "utf-8", "goldminer"),
    ("qmt_smoke_full.py", "gbk", "qmt"),
    ("ptrade_smoke_full.py", "utf-8", "ptrade"),
)

VALIDATION_CASES = (
    ("goldminer_validation_full.py", "utf-8", "goldminer"),
    ("qmt_validation_full.py", "gbk", "qmt"),
    ("ptrade_validation_full.py", "utf-8", "ptrade"),
)

SYS_IMPORT = re.compile(r"(^|\n)\s*(import\s+sys|from\s+sys\s+import)")
SYS_USE = re.compile(r"\bsys\.")


class VerifyError(Exception):
    pass


def read_bytes(path):
    if not os.path.exists(path):
        raise VerifyError("missing artifact: {0}".format(path))
    with io.open(path, "rb") as handle:
        return handle.read()


def read_text(path, encoding):
    data = read_bytes(path)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise VerifyError(
            "{0} is not valid {1}: {2}".format(path, encoding, exc)
        )
    if text.startswith("\ufeff"):
        raise VerifyError("{0} contains a BOM".format(path))
    return text


def parse_tree(text, path, feature_version):
    try:
        return ast.parse(
            text, filename=path, mode="exec", feature_version=feature_version
        )
    except TypeError:
        # Python 3.6 的 ast.parse 没有 feature_version 参数；此时退回普通
        # parse，再由 reject_py36_only 兜住 3.6+ 语法。
        return ast.parse(text, filename=path, mode="exec")


def reject_py36_only(tree, path):
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            raise VerifyError("{0} contains an f-string (Python 3.6+)".format(path))
        if isinstance(node, ast.AnnAssign):
            raise VerifyError(
                "{0} contains a variable annotation (Python 3.6+)".format(path)
            )
        if isinstance(node, ast.comprehension) and getattr(node, "is_async", 0):
            raise VerifyError(
                "{0} contains an async comprehension (Python 3.6+)".format(path)
            )


def check_manifest():
    if not os.path.exists(MANIFEST_PATH):
        raise VerifyError("missing manifest: {0}".format(MANIFEST_PATH))
    with io.open(MANIFEST_PATH, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not manifest.get("version"):
        raise VerifyError("manifest has no version")
    if not manifest.get("source_sha256"):
        raise VerifyError("manifest has no source_sha256")
    artifacts = manifest.get("artifacts") or {}
    required = (
        "dist/jingniflow_single.py",
        "dist/jingniflow_single_gbk.py",
        "jingniflow.py",
    )
    for relative in required:
        if relative not in artifacts:
            raise VerifyError("manifest missing artifact: {0}".format(relative))
    return manifest


def check_artifact_bytes(manifest):
    for relative, entry in (manifest.get("artifacts") or {}).items():
        path = os.path.join(ROOT, relative.replace("/", os.sep))
        data = read_bytes(path)
        checksum = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") != checksum:
            raise VerifyError("artifact hash mismatch: {0}".format(relative))
        if entry.get("bytes") != len(data):
            raise VerifyError("artifact size mismatch: {0}".format(relative))


def check_utf8_single():
    text = read_text(UTF8_PATH, "utf-8")
    parse_tree(text, UTF8_PATH, (3, 6))
    if "from .." in text or "from ." in text:
        raise VerifyError("UTF-8 single file still contains relative imports")


def check_gbk_single():
    text = read_text(GBK_PATH, "gbk")
    if not text.startswith("# coding: gbk"):
        raise VerifyError("GBK single file must start with '# coding: gbk'")
    parse_tree(text, GBK_PATH, (3, 6))
    try:
        read_bytes(GBK_PATH).decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        raise VerifyError("GBK single file is also valid UTF-8; check encoding")


def check_root_equals_dist():
    if read_bytes(ROOT_PATH) != read_bytes(UTF8_PATH):
        raise VerifyError("root jingniflow.py differs from dist/jingniflow_single.py")


def exec_trade_mode(text, path):
    namespace = {"__name__": "verify_release"}
    try:
        exec(compile(text, path, "exec"), namespace)
    except Exception as exc:
        raise VerifyError("cannot execute {0}: {1}".format(path, exc))
    return namespace.get("trade_mode")


def check_smoke_files():
    for name, encoding, expected in SMOKE_CASES:
        path = os.path.join(DIST, "smoke", name)
        text = read_text(path, encoding)
        parse_tree(text, path, (3, 6))
        if "SMOKE_REAL_ORDER = False" not in text:
            raise VerifyError("{0} does not default to SMOKE_REAL_ORDER=False".format(name))
        observed = exec_trade_mode(text, path)
        if observed != expected:
            raise VerifyError(
                "{0} trade_mode is {1!r}, expected {2!r}".format(
                    name, observed, expected
                )
            )
    ptrade_path = os.path.join(DIST, "smoke", "ptrade_smoke_full.py")
    ptrade_text = read_text(ptrade_path, "utf-8")
    if SYS_IMPORT.search(ptrade_text) or SYS_USE.search(ptrade_text):
        raise VerifyError("PTrade full contains forbidden sys references")
    ptrade_tree = parse_tree(ptrade_text, ptrade_path, (3, 5))
    reject_py36_only(ptrade_tree, ptrade_path)
    if "def _smoke_scheduled(*args, **kwargs)" not in ptrade_text:
        raise VerifyError("PTrade schedule callback must accept extra arguments")


def check_validation_files():
    for name, encoding, expected in VALIDATION_CASES:
        path = os.path.join(DIST, "validation", name)
        text = read_text(path, encoding)
        if encoding == "gbk" and not text.startswith("# encoding: gbk"):
            raise VerifyError("{0} must start with '# encoding: gbk'".format(name))
        parse_tree(text, path, (3, 6))
        if 'VALIDATION_STAGE = "dry_run"' not in text:
            raise VerifyError("{0} must default to VALIDATION_STAGE='dry_run'".format(name))
        observed = exec_trade_mode(text, path)
        if observed != expected:
            raise VerifyError(
                "{0} trade_mode is {1!r}, expected {2!r}".format(
                    name, observed, expected
                )
            )
    ptrade_path = os.path.join(DIST, "validation", "ptrade_validation_full.py")
    ptrade_text = read_text(ptrade_path, "utf-8")
    if SYS_IMPORT.search(ptrade_text) or SYS_USE.search(ptrade_text):
        raise VerifyError("PTrade validation contains forbidden sys references")
    ptrade_tree = parse_tree(ptrade_text, ptrade_path, (3, 5))
    reject_py36_only(ptrade_tree, ptrade_path)


def main():
    try:
        manifest = check_manifest()
        check_artifact_bytes(manifest)
        check_utf8_single()
        check_gbk_single()
        check_root_equals_dist()
        check_smoke_files()
        check_validation_files()
    except VerifyError as exc:
        print("[VERIFY] FAILED: {0}".format(exc))
        return 1
    print("[VERIFY] OK version={0}".format(manifest.get("version")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
