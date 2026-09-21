"""Stamp the part of the tree an end-to-end run actually exercises.

`make score` treats a result whose stamp differs from the tree on disk as missing, so a
fifteen-minute run is never claimed for code that has changed since. The question this
file answers is which files "changed since" should mean.

It used to mean everything except a hand-kept list of prose, which was wrong in both
directions. A new teaching page had to be remembered or it silently invalidated every
recorded run, and adding an unrelated `book` target to the Makefile cost a full Docker
run to re-certify a change that cannot reach the stack. So the question is now asked
directly: what does `make e2e` load?

Two lists, each entry carrying the reason it is on that side, and a test fails when a
tracked path matches neither. Nothing lands on a side by default, so a new service
directory cannot quietly end up uncovered.

`--all` covers every tracked file, which is what the `make check` stamp uses: those
results come from a suite that reads the whole repository.
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What an end-to-end run loads. A change to any of it can change what the run proves.
STAMPED: tuple[tuple[str, str], ...] = (
    ("docker-compose.all-in-one.yml", "the compose file every target passes to docker"),
    ("sre-control/", "the control plane under test: detector, policy, tools, approvals"),
    ("subscription-app/", "the app under test, in both releases"),
    ("docs-loader/", "the service the second chaos scenario hangs"),
    ("traffic/", "the baseline every signal is measured against"),
    ("otel-collector/", "container metrics the self-observability spec asserts on"),
    ("mcp-clickhouse/", "the second MCP server the agent calls"),
    ("librechat/", "the workspace the agent runs in, and its MCP registration"),
    ("postgresql-db/", "the schema a signup writes to"),
    ("config/", "the collector and source configuration the stack boots with"),
    ("workshop/", "the SQL the agent's tools load, so a query here changes a tool"),
    ("e2e/", "the specs themselves, and the helpers they assert through"),
    ("scripts/chaos.py", "run by the e2e target to inject and reset the failure"),
    ("scripts/bootstrap_users.py", "run by `make up` to create the logins the specs sign in with"),
    ("scripts/generate_env.py", "run by `make env` to produce the secrets the stack boots with"),
    ("pyproject.toml", "the dependencies those scripts run under"),
    ("uv.lock", "the exact versions of them"),
    (".python-version", "the interpreter they run under"),
)

# What it does not. A change here cannot alter what a recorded run proved.
NOT_STAMPED: tuple[tuple[str, str], ...] = (
    ("guide.html", "prose: the facilitator guide"),
    ("workbook.html", "prose: the attendee workbook"),
    (
        "design/",
        "how both look in print: the brand tokens, the stylesheet, the fonts, the diagram descriptions",
    ),
    ("sources.json", "prose: the citations those pages carry"),
    ("tests/", "the unit and structural suite, which `make check` runs and no spec loads"),
    ("scripts/rubric.py", "the scorecard, which reads results rather than producing them"),
    ("scripts/score.py", "the scorer, same"),
    ("scripts/tree_hash.py", "this file: stamping the stamper invalidates every stamp on every edit"),
    ("scripts/check_prose.py", "a `make check` step"),
    ("scripts/prose-rules.json", "the word lists that step reads"),
    ("scripts/check_links.py", "a scheduled CI job"),
    ("scripts/contents.py", "generates the contents of a teaching page"),
    ("scripts/diagram.mjs", "draws the figures on the teaching pages"),
    ("scripts/highlight.mjs", "colours the code blocks on the teaching pages"),
    ("scripts/tokens.py", "writes design/tokens.css"),
    ("scripts/build_book.mjs", "renders the PDFs"),
    ("scripts/pdf_freshness.json", "what the PDFs were built from"),
    ("evidence/", "written by the run itself, so it cannot be an input to it"),
    ("artifacts/", "written by the run itself"),
    ("k8s/", "a deployment target no spec drives"),
    ("caddy/", "only the VPS override mounts it, and no spec runs that override"),
    ("docker-compose.vps.yml", "the VPS override, which no spec runs"),
    ("docker-compose.yml", "the modular compose file, which no target passes to docker"),
    ("load-generator/", "an optional profile the e2e target never starts"),
    (".github/", "CI configuration"),
    ("architecture.png", "an illustration"),
    ("LICENSE", "not code"),
    (".gitignore", "not code"),
    (".env.example", "a template; the real .env is untracked and generated"),
)

# The Makefile is the one file with mixed concerns: the same file carries the command
# that brings the stack up and the command that prints a PDF. Hashing all of it made an
# unrelated target cost a rerun, so only the recipes an end-to-end run executes are
# stamped.
E2E_RECIPES = ("env", "build", "up", "e2e")


def tracked(include_prose: bool) -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    files = [name for name in listed if name and (ROOT / name).is_file()]
    if include_prose:
        return sorted(name for name in files if not name.startswith("artifacts/"))
    return sorted(name for name in files if is_stamped(name))


def is_stamped(name: str) -> bool:
    """Whether an end-to-end run loads this file. The Makefile is handled separately."""
    if name == "Makefile":
        return False
    return any(name == prefix or name.startswith(prefix) for prefix, _ in STAMPED)


def unclassified(names: list[str]) -> list[str]:
    """Tracked files that neither list claims. A test fails on anything in here."""
    known = tuple(prefix for prefix, _ in STAMPED) + tuple(prefix for prefix, _ in NOT_STAMPED)
    return [
        name
        for name in names
        if name != "Makefile"
        and not any(name == prefix or name.startswith(prefix) for prefix in known)
        and not name.endswith((".md", ".pdf"))
    ]


def makefile_slice() -> str:
    """The recipes `make e2e` runs, plus the variables above them, and nothing else."""
    text = (ROOT / "Makefile").read_text()
    head = re.split(r"^[a-z][a-z0-9-]*:", text, maxsplit=1, flags=re.M)[0]
    blocks = [head]
    for target in E2E_RECIPES:
        found = re.search(rf"^{target}:.*?(?=^[a-zA-Z0-9_.-]+:|\Z)", text, re.M | re.S)
        if found is None:
            raise SystemExit(
                f"Makefile has no {target} target, so the stamp would silently cover less than it claims"
            )
        blocks.append(found.group(0))
    return "".join(blocks)


def tree_hash(include_prose: bool) -> str:
    digest = hashlib.sha256()
    for name in tracked(include_prose):
        digest.update(name.encode())
        digest.update((ROOT / name).read_bytes())
    # Included whole for the check stamp, by recipe for the e2e stamp.
    digest.update(b"Makefile")
    digest.update((ROOT / "Makefile").read_bytes() if include_prose else makefile_slice().encode())
    return digest.hexdigest()


if __name__ == "__main__":
    print(tree_hash(include_prose="--all" in sys.argv))
