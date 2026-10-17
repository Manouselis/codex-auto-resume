#!/usr/bin/env python3
"""Run the suite and write a compact, credential-free verification record."""
import argparse
import json
import os
import platform
import sys
import unittest
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true", help="Run the Tk tests in the current graphical session")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.gui:
        os.environ["AUTO_RESUME_GUI_TEST"] = "1"
        os.environ["AUTO_RESUME_SCREENSHOTS"] = str(root / "docs/evidence")
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
              "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "skip_reasons": [{"test": str(test), "reason": reason} for test, reason in result.skipped],
              "python": platform.python_version(), "platform": platform.system(), "gui_requested": args.gui,
              "live_model_requests": 0, "live_continuation": "BLOCKED", "windows_host_test": "NOT TESTED"}
    (root / "docs/evidence/test-results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
