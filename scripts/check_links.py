"""Resolve every URL sources.json declares, and fail on the ones that do not answer.

    python scripts/check_links.py

This is deliberately not part of `make check`. A gate that needs the network fails for
reasons that have nothing to do with the change in front of it, and a gate that cries
wolf is a gate people learn to skip. It runs as its own scheduled CI job instead, where
a rotted citation is news rather than noise.

A citation nobody can open is not a citation, which is the whole reason this exists.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = "learnwithparam-link-check/1.0 (+https://learnwithparam.com)"


def resolve(url: str) -> str | None:
    """None when the URL answers, otherwise why it did not."""
    # Only http and https. urlopen will happily read file: and a source list is
    # editable text, so the scheme is checked here rather than assumed.
    if not url.startswith(("http://", "https://")):
        return "not an http URL"
    request = urllib.request.Request(url, headers={"User-Agent": AGENT}, method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
            if response.status >= 400:
                return f"HTTP {response.status}"
            return None
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    except Exception as error:  # noqa: BLE001 - any failure to open it is the finding
        return f"{type(error).__name__}: {error}"


def main() -> int:
    sources = json.loads((ROOT / "sources.json").read_text())["sources"]
    problems = []
    for source in sources:
        why = resolve(source["url"])
        print(f"{'ok  ' if why is None else 'FAIL'}  {source['url']}" + (f"  {why}" if why else ""))
        if why is not None:
            problems.append(f"{source['url']} ({source['title']}): {why}")
    if problems:
        print(f"\ncheck_links FAILED: {len(problems)} source(s) did not answer", file=sys.stderr)
        for line in problems:
            print(f"  ✗ {line}", file=sys.stderr)
        return 1
    print(f"\ncheck_links ok: {len(sources)} sources resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
