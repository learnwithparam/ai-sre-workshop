"""What the AI SRE may do. Reads are free; one tool can act, and only after a human approves."""

import re
from enum import StrEnum


class ToolClass(StrEnum):
    READ = "read"
    PROPOSE = "propose"
    ACTION = "action"


TOOL_CLASSES: dict[str, ToolClass] = {
    "list_sources": ToolClass.READ,
    "service_timeseries": ToolClass.READ,
    "analyze_service_anomalies": ToolClass.READ,
    "get_event_deltas": ToolClass.READ,
    "event_patterns": ToolClass.READ,
    "get_trace_waterfall": ToolClass.READ,
    "search_logs": ToolClass.READ,
    "list_incidents": ToolClass.READ,
    "get_incident": ToolClass.READ,
    "get_remediation_status": ToolClass.READ,
    "propose_remediation": ToolClass.PROPOSE,
    "execute_remediation": ToolClass.ACTION,
}

# action -> target -> allowed values for each parameter. Nothing outside this map can run.
ACTIONS: dict[str, dict[str, dict[str, set[str]]]] = {
    "rollback_release": {"subscription-app": {"release": {"v1"}}},
    "restart_service": {"docs-loader": {}, "subscription-app": {}},
}

# A remediation targets a container; telemetry names a service. The agent needs both names.
TARGETS: dict[str, str] = {
    "subscription-app": "container running service subscription-backend (Flask), which calls docs-loader",
    "docs-loader": "container running service docs-loader (Go), called by subscription-backend /load-docs",
}

# Shown on the approval page, so the approver sees the cost of saying yes.
BLAST_RADIUS = {
    "rollback_release": (
        "Redeploys subscription-app on the previous image. The signup page returns errors for the few "
        "seconds the container takes to pass its health check. Anything shipped in the newer release is "
        "withdrawn until it is fixed and deployed again."
    ),
    "restart_service": (
        "Restarts one container. Requests in flight to it fail, and callers see errors until its health "
        "check passes. Nothing about the code changes, so a defect that caused the incident can recur."
    ),
}

SAFE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


class PolicyError(ValueError):
    pass


def validate_action(action: str, target: str, params: dict[str, str]) -> None:
    targets = ACTIONS.get(action)
    if targets is None:
        raise PolicyError(f"action {action!r} is not allowed; allowed: {sorted(ACTIONS)}")
    allowed = targets.get(target)
    if allowed is None:
        raise PolicyError(f"{action} cannot target {target!r}; allowed: {sorted(targets)}")
    if set(params) != set(allowed):
        raise PolicyError(f"{action} takes exactly {sorted(allowed)}, got {sorted(params)}")
    for key, value in params.items():
        if not SAFE.match(str(value)) or value not in allowed[key]:
            raise PolicyError(f"{action} {key}={value!r} is not allowed; allowed: {sorted(allowed[key])}")
