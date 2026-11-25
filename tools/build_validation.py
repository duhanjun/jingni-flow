# -*- coding: utf-8 -*-
"""Build the three copy-paste simulation validation strategies.

Usage:
    python tools/build_validation.py
    python tools/build_validation.py --check

Output:
    dist/validation/goldminer_validation_full.py
    dist/validation/qmt_validation_full.py
    dist/validation/ptrade_validation_full.py
"""

import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(ROOT, "examples", "validation")
DIST_DIR = os.path.join(ROOT, "dist")
OUT_DIR = os.path.join(DIST_DIR, "validation")
README_SOURCE = os.path.join(SOURCE_DIR, "README.md")
README_OUT = os.path.join(OUT_DIR, "README.md")

PAIRS = [
    (
        "goldminer_validation.py",
        "validation_core.py",
        "jingniflow_single.py",
        "goldminer_validation_full.py",
        "utf-8",
    ),
    (
        "qmt_validation.py",
        "validation_core.py",
        "jingniflow_single_gbk.py",
        "qmt_validation_full.py",
        "gbk",
    ),
    (
        "ptrade_validation.py",
        "validation_core.py",
        "jingniflow_single.py",
        "ptrade_validation_full.py",
        "utf-8",
    ),
]


def read_bytes(path):
    if not os.path.exists(path):
        raise SystemExit("missing file: {0}".format(path))
    with io.open(path, "rb") as handle:
        return handle.read()


def read_text(path, encoding):
    with io.open(path, "r", encoding=encoding) as handle:
        return handle.read()


def combined(head_path, core_path, tail_path, encoding):
    head = read_text(head_path, encoding).rstrip()
    core = read_text(core_path, "utf-8").rstrip()
    tail = read_text(tail_path, encoding)
    return head + u"\n\n" + core + u"\n\n" + tail


def order_cancel_name(out_name):
    return out_name.replace("_validation_full.py", "_validation_order_cancel.py")


def order_cancel_text(text):
    marker = '\nVALIDATION_STAGE = "dry_run"\n'
    if marker not in text:
        raise SystemExit("validation stage assignment not found")
    text = text.replace(marker, '\nVALIDATION_STAGE = "order_cancel"\n', 1)
    doc_old = (
        'STEP 1: keep VALIDATION_STAGE = "dry_run" and run once. It places no order.\n'
        'STEP 2: after confirming this is a simulation account, change it to\n'
        '        "order_cancel".'
    )
    doc_new = (
        'This file is preset to VALIDATION_STAGE = "order_cancel": it places one\n'
        '100-share limit buy below the market, waits, cancels it, and reconciles\n'
        'orders/positions.'
    )
    return text.replace(doc_old, doc_new, 1)


def check_or_write(path, expected, encoding, check):
    if check:
        if not os.path.exists(path):
            print("[STALE] missing {0}".format(path))
            return False
        try:
            actual = read_text(path, encoding)
        except UnicodeError as exc:
            print("[STALE] {0} is not valid {1}: {2}".format(path, encoding, exc))
            return False
        if actual != expected:
            print("[STALE] {0}".format(path))
            return False
        print("[OK] {0}".format(path))
        return True
    with io.open(path, "w", encoding=encoding, newline="\n") as handle:
        handle.write(expected)
    print("wrote {0} ({1})".format(path, encoding))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    if not args.check and not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    ok = True
    for head_name, core_name, tail_name, out_name, encoding in PAIRS:
        head_path = os.path.join(SOURCE_DIR, head_name)
        core_path = os.path.join(SOURCE_DIR, core_name)
        tail_path = os.path.join(DIST_DIR, tail_name)
        out_path = os.path.join(OUT_DIR, out_name)
        expected = combined(head_path, core_path, tail_path, encoding)
        ok = check_or_write(out_path, expected, encoding, args.check) and ok
        cancel_path = os.path.join(OUT_DIR, order_cancel_name(out_name))
        cancel_expected = order_cancel_text(expected)
        ok = check_or_write(cancel_path, cancel_expected, encoding, args.check) and ok
    readme = read_bytes(README_SOURCE)
    if args.check:
        if not os.path.exists(README_OUT):
            print("[STALE] missing {0}".format(README_OUT))
            ok = False
        elif read_bytes(README_OUT) != readme:
            print("[STALE] {0}".format(README_OUT))
            ok = False
        else:
            print("[OK] {0}".format(README_OUT))
    else:
        with io.open(README_OUT, "wb") as handle:
            handle.write(readme)
        print("wrote {0}".format(README_OUT))
    print("[VALIDATION-BUILD] {0}".format("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
