"""Turns an approved action into one fixed docker compose command. No shell, no free text."""

import subprocess
from pathlib import Path
from typing import Any

from sre_control.policy import validate_action

COMPOSE_FILE = "docker-compose.all-in-one.yml"


def build_command(action: str, target: str, params: dict[str, str], project_dir: str) -> tuple[list, dict]:
    validate_action(action, target, params)
    base = ["docker", "compose", "--project-directory", project_dir, "-f", f"{project_dir}/{COMPOSE_FILE}"]
    if action == "rollback_release":
        # Redeploying the previous release is `up` on the previous image tag, as a deploy system would.
        return [*base, "up", "-d", "--no-deps", "--wait", target], {"APP_RELEASE": params["release"]}
    return [*base, "restart", target], {}


class ComposeRunner:
    def __init__(self, project_dir: Path, timeout_s: int = 180):
        self.project_dir, self.timeout_s = str(project_dir), timeout_s

    def run(self, action: str, target: str, params: dict[str, str]) -> dict[str, Any]:
        cmd, extra_env = build_command(action, target, params, self.project_dir)
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "WORKSHOP_DIR": self.project_dir, **extra_env}
        try:
            done = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "command": " ".join(cmd), "output": f"timed out after {self.timeout_s}s"}
        output = (done.stdout + done.stderr)[-2000:]
        return {"exit_code": done.returncode, "command": " ".join(cmd), "output": output}
