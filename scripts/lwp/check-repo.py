#!/usr/bin/env python3
"""Validate repo.json against repo.schema.json; check-affected.py --audit loads it for that and for
the steps a gate command runs.

Usage:  check-repo.py [REPO_JSON]   defaults to the repo's repo.json; exits 1 on a schema miss
Why: docs/decisions/scripts.md#check-affectedpy
"""

import json
import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("repo.schema.json")
# .agents/ is the agent-neutral home; .claude/ is where every repo kept it before 24 Oct 2026.
CONFIG_PATHS = (".agents/repo.json", ".claude/repo.json")


def repo_json(root: Path) -> Path | None:
    """The one place every hook and script finds a repo's config."""
    return next((root / c for c in CONFIG_PATHS if (root / c).is_file()), None)


def load_schema() -> dict | None:
    try:
        return json.loads(SCHEMA_PATH.read_text())
    except (OSError, ValueError):
        return None


# The schema is the one list of stages, in order; this copy is only for a checkout synced before it existed.
STAGES = ((load_schema() or {}).get("$defs", {}).get("stage", {}).get("enum")) or ["stop", "push", "nightly"]
TYPES = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}


def schema_errors(value, schema: dict, root: dict, at: str = "repo.json") -> list[str]:
    """The subset of JSON Schema repo.schema.json uses: $ref, type, enum, pattern, required, properties,
    additionalProperties, propertyNames, items. Enough to catch a misspelt key or an unknown stage."""
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[-1]]
    want = TYPES.get(schema.get("type", ""))
    if want and (not isinstance(value, want) or (want is int and isinstance(value, bool))):
        return [f"{at}: expected {schema['type']}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{at}: {value!r} is not one of {schema['enum']}"]
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        return [f"{at}: {value!r} does not match {schema['pattern']}"]
    errs = []
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errs += [f"{at}: missing {k}" for k in schema.get("required", []) if k not in value]
        for k, v in value.items():
            if "propertyNames" in schema:
                errs += schema_errors(k, schema["propertyNames"], root, f"{at} key")
            if k in props:
                errs += schema_errors(v, props[k], root, f"{at}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{at}: unknown key {k!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += schema_errors(v, schema["additionalProperties"], root, f"{at}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            errs += schema_errors(v, schema["items"], root, f"{at}[{i}]")
    return errs


NPM_STEP = re.compile(r"^npm (?:run )?(?:(?:-s|--silent) )*([\w:.-]+)(?: .*)?$")
MAKE_STEP = re.compile(r"^(?:make|\$\(MAKE\)) (?:-\S+ )*([\w.-]+)$")
BOOKKEEPING = re.compile(r"check-affected\.py --audit|gate-stamp|^echo |^true$|^:$")


def make_rule(root: Path, target: str) -> tuple[list[str], list[str]]:
    """A Makefile target's prerequisites and recipe lines (`@`/`-` and continuations folded)."""
    try:
        lines = (root / "Makefile").read_text().replace("\\\n", " ").splitlines()
    except OSError:
        return [], []
    for i, line in enumerate(lines):
        head = re.match(rf"^{re.escape(target)}\s*:(?!=)(.*)$", line)
        if not head:
            continue
        recipe = []
        for r in lines[i + 1 :]:
            if not r.startswith("\t"):
                if r.strip():
                    break
                continue
            s = r.strip().lstrip("@-").strip()
            if s and not s.startswith("#"):
                recipe.append(s)
        return head.group(1).split("#")[0].split(), recipe
    return [], []


def gate_steps(root: Path, cmd: str, depth: int = 0) -> list[str]:
    """The steps a gate command runs, one level into npm scripts and make targets, bookkeeping dropped."""
    if BOOKKEEPING.search(cmd) or depth > 3:
        return []
    npm, mk = NPM_STEP.match(cmd), MAKE_STEP.match(cmd)
    if npm and depth == 0:
        try:
            body = json.loads((root / "package.json").read_text()).get("scripts", {}).get(npm.group(1), "")
        except (OSError, ValueError):
            body = ""
        return [s for part in body.split("&&") for s in gate_steps(root, part.strip(), depth + 1)] or [cmd]
    if npm:
        return [npm.group(1)]
    if mk and depth == 0:
        pre, recipe = make_rule(root, mk.group(1))
        steps = [p for p in pre if any(not BOOKKEEPING.search(r) for r in make_rule(root, p)[1])]
        work = [r for r in recipe if not BOOKKEEPING.search(r)]
        if not steps and len(work) == 1 and NPM_STEP.match(work[0]):
            return gate_steps(root, work[0])
        return steps + [s for r in recipe for s in gate_steps(root, r, depth + 1)]
    if mk:
        return [mk.group(1)]
    return [cmd]


def uncovered_steps(root: Path, cfg: dict) -> tuple[list[str], list[str]]:
    """Gate steps no check runs, `covers` or `fullOnly` names; and `fullOnly` entries the gate no longer runs."""
    impact = cfg["impact"]
    steps = gate_steps(root, cfg.get("gate", "make check"))
    said = " ".join(f"{c['run']} {c.get('scoped', '')}" for c in impact["checks"])
    named = {n for c in impact["checks"] for n in c.get("covers", [])} | set(impact.get("fullOnly", []))
    token = lambda s: re.search(rf"(?<![\w:.-]){re.escape(s)}(?![\w:.-])", said)
    missing = [s for s in steps if s not in named and not token(s)]
    return missing, [s for s in impact.get("fullOnly", []) if s not in steps]


def context_errors(root: Path) -> list[str]:
    """AGENTS.md is the one brief every agent reads; CLAUDE.md only imports it, so the two cannot drift."""
    errs = [] if (root / "AGENTS.md").is_file() else ["no AGENTS.md at the root; every agent but one starts blind"]
    claude = root / "CLAUDE.md"
    if claude.is_file() and "@AGENTS.md" not in claude.read_text().split():
        errs.append("CLAUDE.md does not import @AGENTS.md, so it is a second brief")
    if all((root / c).is_file() for c in CONFIG_PATHS):
        errs.append(f"both {' and '.join(CONFIG_PATHS)} exist; keep {CONFIG_PATHS[0]}")
    return errs


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_json(Path.cwd()) or Path(CONFIG_PATHS[0])
    schema = load_schema()
    if schema is None:
        print(f"check-repo  FAIL  no readable {SCHEMA_PATH.name} beside this script; re-sync the kit")
        return 1
    try:
        cfg = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        print(f"check-repo  FAIL  {path}: {e}")
        return 1
    if errs := schema_errors(cfg, schema, schema):
        print(f"check-repo  FAIL  {path} breaks {SCHEMA_PATH.name}:")
        print("\n".join(f"  {e}" for e in errs[:30]))
        return 1
    print(f"check-repo  ok  {path} fits {SCHEMA_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
