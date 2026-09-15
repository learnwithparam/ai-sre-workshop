"""Steady background traffic: page views and signups, so every signal has a baseline to deviate from.

The browser load generator (profile browser-load) is realistic but costs 1.3 GB; this costs 20 MB.
It never calls /load-docs; that hang is injected on purpose by `make chaos SCENARIO=docs-hang`.
"""

import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

TARGET = os.environ["TARGET_URL"].rstrip("/")
RATE = float(os.environ.get("REQUESTS_PER_SECOND", "4"))
HEARTBEAT = Path("/tmp/heartbeat")  # noqa: S108  read by the container health check
SOURCES = ["webinar", "in-person-event", "ads", "web-research", "llm-suggestion", "others"]


def call(method: str, path: str, body: dict | None = None) -> int:
    data = json.dumps(body).encode() if body else None
    request = urllib.request.Request(  # noqa: S310  fixed internal URL
        f"{TARGET}{path}", data=data, method=method, headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as err:
        return err.code
    except OSError:
        return 0


def main() -> None:
    sent = 0
    while True:
        started = time.monotonic()
        if random.random() < 0.5:  # noqa: S311  traffic shape, not security
            call("GET", "/")
        else:
            n = random.randint(1, 40)  # noqa: S311
            call("POST", "/api/subscribe",
                 {"name": f"Visitor {n}", "company": "Example Co", "email": f"visitor{n}@example.com",
                  "source": random.choice(SOURCES)})  # noqa: S311  # fmt: skip
        sent += 1
        if sent % 10 == 0:
            HEARTBEAT.touch()
        time.sleep(max(0.0, 1 / RATE - (time.monotonic() - started)))


if __name__ == "__main__":
    HEARTBEAT.touch()
    main()
