"""Run an exercise file and the solution block it was cut from against ClickHouse, and diff the rows.

    make exercise N=2

Both queries run as the read-only sre_agent user, inside the clickstack container. The password
travels in the process environment, never in an argument. Rows are compared by column names, row
count and the first column, because time-based windows move between two runs.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "sre-control"))
import generate_env as secrets_file  # noqa: E402

from sre_control.queries import load_queries  # noqa: E402

WORKSHOP = ROOT / "workshop"


def exercise_file(n: int) -> Path:
    found = sorted((WORKSHOP / "exercises").glob(f"{n:02d}-*.sql"))
    if not found:
        raise SystemExit(f"no exercise {n}; there are 1 to 5")
    return found[0]


def run(sql: str, params: dict[str, str]) -> list[dict]:
    args = ["docker", "exec", "-i", "-e", "CLICKHOUSE_PASSWORD", "clickstack", "clickhouse-client",
            "--user", "sre_agent", "--format", "JSONEachRow"]  # fmt: skip
    args += [f"--param_{k}={v}" for k, v in params.items()]
    password = secrets_file.read(secrets_file.ENV)["CLICKHOUSE_READER_PASSWORD"]
    done = subprocess.run(args, input=sql, capture_output=True, text=True,
                          env={**os.environ, "CLICKHOUSE_PASSWORD": password})  # fmt: skip
    if done.returncode:
        raise SystemExit(done.stderr.strip() or "clickhouse-client failed")
    return [json.loads(line) for line in done.stdout.splitlines() if line]


def shape(rows: list[dict]) -> tuple:
    if not rows:
        return ([], 0, [])
    first = next(iter(rows[0]))
    return (sorted(rows[0]), len(rows), sorted(str(r[first]) for r in rows))


def load_one(path: Path):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / path.name).write_text(path.read_text())
        ((name, query),) = load_queries(Path(tmp)).items()
        return name, query


def main(n: int) -> int:
    path = exercise_file(n)
    name, query = load_one(path)
    if re.search(r"\bTODO\b", query.sql):
        print(f"{path.name}: the TODO in {name} is still there")
        return 1
    solution = load_queries(WORKSHOP)[name]
    want = shape(run(solution.sql, solution.example))
    got = shape(run(query.sql, solution.example))
    if got == want:
        print(f"match: {name} returns the same {want[1]} row(s) as the solution")
        return 0
    print(f"differ: {name}\n  yours:    {got}\n  solution: {want}")
    return 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))
