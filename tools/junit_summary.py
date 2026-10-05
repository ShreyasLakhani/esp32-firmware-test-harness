"""Reads JUnit XML files and prints a markdown table per test ID.

Also lists IDs from docs/test-plan.md that no test covered.
usage: python tools/junit_summary.py reports/*.xml >> $GITHUB_STEP_SUMMARY
"""
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "test-plan.md"
ORDER = {"failed": 0, "error": 0, "skipped": 1, "passed": 2}


def plan_ids():
    text = PLAN.read_text() if PLAN.exists() else ""
    return re.findall(r"^\| ((?:UART|I2C|SPI|ALM|FLT|TIM|HOST)-\d\d) \|", text, re.M)


def case_status(tc):
    if tc.find("failure") is not None:
        return "failed"
    if tc.find("error") is not None:
        return "error"
    if tc.find("skipped") is not None:
        return "skipped"
    return "passed"


def collect(paths):
    by_id = defaultdict(list)
    for p in paths:
        for tc in ET.parse(p).getroot().iter("testcase"):
            tid = None
            for prop in tc.iter("property"):
                if prop.get("name") == "test_id":
                    tid = prop.get("value")
            if tid:
                by_id[tid].append((tc.get("name"), case_status(tc)))
    return by_id


def main(argv):
    by_id = collect(argv[1:])
    ids = plan_ids() or sorted(by_id)
    print("| Test ID | Result | Tests |")
    print("|---|---|---|")
    bad = 0
    for tid in ids:
        cases = by_id.get(tid, [])
        if not cases:
            result = "missing"
            bad += 1
        else:
            result = min((s for _, s in cases), key=lambda s: ORDER[s])
            if result in ("failed", "error"):
                bad += 1
        names = ", ".join(n for n, _ in cases) or "-"
        print(f"| {tid} | {result} | {names} |")
    print()
    print(f"{len(ids) - bad} of {len(ids)} test IDs ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
