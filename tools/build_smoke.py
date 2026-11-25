# -*- coding: utf-8 -*-
"""把三端冒烟脚本与单文件尾部拼成可直接粘贴的 full 版本。

用法：
    python tools/build_smoke.py
    python tools/build_smoke.py --check

产物：
    dist/smoke/goldminer_smoke_full.py
    dist/smoke/qmt_smoke_full.py
    dist/smoke/ptrade_smoke_full.py
"""

import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE_DIR = os.path.join(ROOT, "examples", "smoke")
DIST_DIR = os.path.join(ROOT, "dist")
OUT_DIR = os.path.join(DIST_DIR, "smoke")

PAIRS = [
    ("goldminer_smoke.py", "jingniflow_single.py", "goldminer_smoke_full.py"),
    ("qmt_smoke.py", "jingniflow_single_gbk.py", "qmt_smoke_full.py"),
    ("ptrade_smoke.py", "jingniflow_single.py", "ptrade_smoke_full.py"),
]


def read_bytes(path):
    if not os.path.exists(path):
        raise SystemExit("missing file: {0}".format(path))
    with io.open(path, "rb") as handle:
        return handle.read()


def combined(head_path, tail_path):
    head = read_bytes(head_path)
    tail = read_bytes(tail_path)
    return head.rstrip() + b"\n\n" + tail


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    if not args.check and not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    ok = True
    for head_name, tail_name, out_name in PAIRS:
        head_path = os.path.join(SMOKE_DIR, head_name)
        tail_path = os.path.join(DIST_DIR, tail_name)
        out_path = os.path.join(OUT_DIR, out_name)
        expected = combined(head_path, tail_path)
        if args.check:
            if not os.path.exists(out_path):
                print("[STALE] missing {0}".format(out_path))
                ok = False
                continue
            actual = read_bytes(out_path)
            if actual != expected:
                print("[STALE] {0}".format(out_path))
                ok = False
            else:
                print("[OK] {0}".format(out_path))
        else:
            with io.open(out_path, "wb") as handle:
                handle.write(expected)
            print("wrote {0}".format(out_path))
    print("[SMOKE-BUILD] {0}".format("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
