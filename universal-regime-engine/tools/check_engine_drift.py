#!/usr/bin/env python3
"""Fail if the shared engine block has drifted between the indicator and the strategy.

TradingView has no way to share code between two unpublished scripts — a Pine
`library()` has to be published before it can be imported — so the engine is
physically duplicated in both .pine files. That is a deliberate trade-off, and this
check is what keeps it honest: edit the engine in the indicator, regenerate or copy
it into the strategy, and run this before committing.

    python3 tools/check_engine_drift.py

Exit status 0 = identical, 1 = drift (a unified diff is printed).
"""
import difflib
import pathlib
import sys

START = ">>>>> ENGINE BLOCK START"
END = "<<<<< ENGINE BLOCK END"
ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = {
    "indicator": ROOT / "indicators" / "Universal_Regime_Engine.pine",
    "strategy": ROOT / "strategies" / "Universal_Regime_Strategy.pine",
}


def extract(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    starts = [i for i, l in enumerate(lines) if START in l]
    ends = [i for i, l in enumerate(lines) if END in l]
    if len(starts) != 1 or len(ends) != 1:
        sys.exit(f"{path}: expected exactly one engine marker pair, "
                 f"found {len(starts)} start / {len(ends)} end")
    if ends[0] <= starts[0]:
        sys.exit(f"{path}: engine end marker precedes the start marker")
    return lines[starts[0] + 1:ends[0]]


def main():
    blocks = {name: extract(path) for name, path in FILES.items()}
    if blocks["indicator"] == blocks["strategy"]:
        print(f"engine block identical in both scripts ({len(blocks['indicator'])} lines)")
        return 0
    diff = difflib.unified_diff(
        blocks["indicator"], blocks["strategy"],
        fromfile="indicator engine", tofile="strategy engine", lineterm="",
    )
    print("ENGINE DRIFT — the two scripts no longer measure the same thing:\n")
    print("\n".join(diff))
    return 1


if __name__ == "__main__":
    sys.exit(main())
