"""Inject or undo the workshop's failures.

bad-release  deploy subscription-app v2, whose signups are slow and a third of them fail
docs-hang    send six requests to /load-docs; each one hangs inside docs-loader forever
reset        redeploy v1 and restart docs-loader
"""

import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker-compose.all-in-one.yml")]
APP = os.environ.get("APP_URL", "http://localhost:8000")


def compose(*args: str, release: str | None = None) -> None:
    env = {**os.environ, "WORKSHOP_DIR": str(ROOT)}
    if release:
        env["APP_RELEASE"] = release
    subprocess.run([*COMPOSE, *args], cwd=ROOT, env=env, check=True, capture_output=True, text=True)


def deploy(release: str) -> None:
    compose("up", "-d", "--no-deps", "--wait", "subscription-app", release=release)
    print(f"subscription-app is now running release {release}")


def hang_docs(count: int = 6) -> None:
    def call() -> None:
        try:
            urllib.request.urlopen(f"{APP}/load-docs", timeout=3)  # noqa: S310  fixed local URL
        except OSError:
            pass  # the browser gives up; the server-side request keeps hanging, which is the fault

    threads = [threading.Thread(target=call) for _ in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"sent {count} requests to /load-docs; they are now hanging inside docs-loader")


def main(scenario: str) -> None:
    if scenario == "bad-release":
        deploy("v2")
    elif scenario == "docs-hang":
        hang_docs()
    elif scenario == "reset":
        deploy("v1")
        compose("restart", "docs-loader")
        print("docs-loader restarted")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
