"""Score the build 0 to 100 from test results. Exits 1 below 100.

Results come from artifacts/junit.xml (make check) and artifacts/playwright.json (make e2e).
A result file produced from a different tree than the one on disk counts as missing.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rubric import PHASES  # noqa: E402
from tree_hash import tree_hash  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def fresh(stamp: str, include_prose: bool) -> bool:
    path = ARTIFACTS / stamp
    return path.exists() and path.read_text().strip() == tree_hash(include_prose)


def junit_results() -> dict[str, bool]:
    path = ARTIFACTS / "junit.xml"
    if not path.exists() or not fresh("check-tree.txt", include_prose=True):
        return {}
    results = {}
    for case in ET.parse(path).iter("testcase"):  # noqa: S314  pytest wrote this file in this run
        module = case.get("classname", "").replace(".", "/")
        passed = not any(child.tag in ("failure", "error", "skipped") for child in case)
        results[f"{module}.py::{case.get('name')}"] = passed
    return results


def playwright_results() -> dict[str, bool]:
    path = ARTIFACTS / "playwright.json"
    if not path.exists() or not fresh("e2e-tree.txt", include_prose=False):
        return {}
    results = {}

    def walk(suite: dict, file: str) -> None:
        file = suite.get("file", file)
        for spec in suite.get("specs", []):
            results[f"{Path(file).name} > {spec['title']}"] = spec.get("ok", False)
        for child in suite.get("suites", []):
            walk(child, file)

    for suite in json.loads(path.read_text()).get("suites", []):
        walk(suite, suite.get("file", ""))
    return results


def main() -> int:
    results = {"junit": junit_results(), "pw": playwright_results()}
    total = 0
    for phase, checks in PHASES.items():
        earned = sum(c.points for c in checks if results[c.source].get(c.id))
        possible = sum(c.points for c in checks)
        total += earned
        mark = "✅" if earned == possible else "❌"
        print(f"{mark} {phase:<28} {earned:>3} / {possible}")
        for c in checks:
            if not results[c.source].get(c.id):
                state = "not run" if c.id not in results[c.source] else "failed"
                print(f"     {state:<8} {c.id}")
    for source, stamp in (("junit", "check-tree.txt"), ("pw", "e2e-tree.txt")):
        if not results[source]:
            print(f"   no fresh {source} results ({stamp} missing or from other code)")
    print(f"\nScore: {total} / 100")
    return 0 if total == 100 else 1


if __name__ == "__main__":
    sys.exit(main())
