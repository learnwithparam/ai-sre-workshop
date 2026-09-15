"""The SRE MCP server. Semantic tools over workshop SQL, plus the two remediation tools.

Every tool must be classified in policy.TOOL_CLASSES before it can register, and its MCP
annotations are derived from that class, so a client sees the same boundary the server enforces.
Payloads are pruned: rows are capped and rounded, because every token returned is paid for twice.
"""

import datetime as dt
import decimal
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from mcp.types import ToolAnnotations
from pydantic import Field

from sre_control.approvals import ApprovalRequired, InvalidTransition, Remediations, Ungrounded
from sre_control.policy import ACTIONS, TARGETS, TOOL_CLASSES, PolicyError, ToolClass

INSTRUCTIONS = """You are connected to the control plane of a production web app.
Read tools query ClickStack telemetry. propose_remediation stores a proposal that a human must
approve; execute_remediation only succeeds after that approval. Always cite trace ids that a tool
returned. Never claim an action ran unless execute_remediation returned its result."""


class UnclassifiedTool(ValueError):
    pass


def sre_tool(mcp: FastMCP):
    def register(fn):
        cls = TOOL_CLASSES.get(fn.__name__)
        if cls is None:
            raise UnclassifiedTool(f"{fn.__name__} is not in policy.TOOL_CLASSES")
        annotations = ToolAnnotations(
            read_only_hint=cls is ToolClass.READ,
            destructive_hint=cls is ToolClass.ACTION,
            idempotent_hint=cls is not ToolClass.PROPOSE,
            open_world_hint=False,
        )
        return mcp.tool(name=fn.__name__, annotations=annotations)(fn)

    return register


def jsonable(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float | decimal.Decimal):
        return round(float(value), 4)
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    return value


def build_mcp(*, telemetry, remediations: Remediations, token: str | None, public_url: str = "") -> FastMCP:
    auth = StaticTokenVerifier(tokens={token: {"client_id": "ai-sre", "scopes": []}}) if token else None
    mcp = FastMCP("sre", instructions=INSTRUCTIONS, auth=auth)
    store = remediations.store
    tool = sre_tool(mcp)

    def rows(name: str, limit: int = 20, **params) -> list[dict]:
        return jsonable(telemetry.rows(name, **params)[:limit])

    @tool
    def list_sources(minutes: int = 60) -> dict:
        """List the services reporting telemetry, their releases, span and error counts."""
        return {"services": rows("list_services", minutes=minutes), "tables": rows("list_tables")}

    @tool
    def service_timeseries(service: str, minutes: int = 15, bucket_s: int = 30) -> dict:
        """Requests, errors, error rate and p95 latency per time bucket for one service."""
        return {"service": service, "buckets": rows("service_timeseries", 60, service=service,
                                                    minutes=minutes, bucket_s=bucket_s)}  # fmt: skip

    @tool
    def analyze_service_anomalies(baseline_minutes: int = 10) -> dict:
        """Compare each service's last minute with a 3 sigma bound over its trailing baseline."""
        return {
            "services": rows("analyze_service_anomalies", baseline_minutes=baseline_minutes, min_delta=0.05)
        }

    @tool
    def get_event_deltas(service: str, incident_minutes: int = 5) -> dict:
        """What changed: new or growing log patterns, failing endpoints by release, and failing traces."""
        window = {"service": service, "incident_minutes": incident_minutes}
        return {
            "log_patterns": rows("get_event_deltas", 10, **window),
            "span_changes": rows("error_span_deltas", 10, **window),
            "releases": rows("errors_by_release", service=service, minutes=incident_minutes * 3),
            "failing_traces": rows("sample_error_traces", 5, service=service, minutes=incident_minutes),
        }

    @tool
    def event_patterns(service: str, minutes: int = 10) -> dict:
        """Cluster recent logs for one service into patterns with counts and an example each."""
        return {"service": service, "patterns": rows("event_patterns", 15, service=service, minutes=minutes)}

    @tool
    def get_trace_waterfall(trace_id: str) -> dict:
        """One trace: every span in start order (service, duration, status, SQL) and its correlated logs."""
        spans = rows("get_trace_waterfall", 50, trace_id=trace_id)
        logs = rows("trace_logs", 50, trace_id=trace_id)
        if not spans and not logs:
            raise ToolError(f"no spans or logs found for trace {trace_id}")
        result = {"trace_id": trace_id, "spans": spans, "logs": logs}
        if not spans:
            result["note"] = (
                "No spans: a span is exported when its request finishes, so a request that is still "
                "hanging has only its logs. That absence is itself evidence of a hang."
            )
        return result

    @tool
    def search_logs(service: str, text: str, minutes: int = 60) -> dict:
        """Find log lines for one service containing a word or phrase (case-insensitive), newest first."""
        return {"logs": rows("search_logs", 25, service=service, text=text, minutes=minutes)}

    @tool
    def list_incidents(state: str = "open") -> dict:
        """List incidents opened by the detector. state is open, resolved or all."""
        found = [i for i in store.incidents() if state == "all" or i.state == state][:20]
        return {"incidents": [jsonable(vars(i)) for i in found]}

    @tool
    def get_incident(incident_id: str) -> dict:
        """One incident with its summary, detector evidence and every remediation proposed for it."""
        try:
            incident = store.incident(incident_id)
        except KeyError as err:
            raise ToolError(f"no incident {incident_id}") from err
        actions = [
            {"action_id": a.action_id, "state": a.state, "action": a.action, "target": a.target}
            for a in remediations.actions_for(incident_id)
        ]
        allowed = {action: sorted(targets) for action, targets in ACTIONS.items()}
        return {
            "incident": jsonable(vars(incident)),
            "remediations": actions,
            "allowed_actions": allowed,
            "targets": TARGETS,
        }

    @tool
    def get_remediation_status(action_id: str) -> dict:
        """The approval state of a proposed remediation, its result, and whether recovery was verified."""
        try:
            s = remediations.status(action_id)
        except KeyError as err:
            raise ToolError(f"no remediation {action_id}") from err
        return jsonable(
            {"action_id": s.action_id, "state": s.state, "action": s.action, "target": s.target,
             "params": s.params, "result": s.result, "verification": s.verification,
             "approval_url": f"{public_url}/actions/{s.action_id}"}
        )  # fmt: skip

    # Every argument is described. The first version had a bare `release: str`, and the model
    # filled it with the release to roll back TO, which is exactly the ambiguity Module 4 teaches.
    @tool
    def propose_remediation(
        incident_id: Annotated[str, Field(description="The incident id, for example inc-1a2b3c4d5e6f.")],
        action: Annotated[str, Field(description="One of get_incident's allowed_actions keys.")],
        target: Annotated[str, Field(description="A target listed for that action in allowed_actions.")],
        root_cause: Annotated[str, Field(description="Two or three sentences: what fails, where, and why.")],
        faulty_service: Annotated[str, Field(description="The service whose telemetry shows the fault.")],
        faulty_release: Annotated[
            str,
            Field(
                description="The service.version that introduced the fault (NOT the release to roll back to)."
            ),
        ],
        trace_ids: Annotated[
            list[str], Field(description="Failing trace ids exactly as a tool returned them.")
        ],
        params: Annotated[
            dict[str, str] | None,
            Field(
                description='Action parameters. rollback_release needs {"release": "<release to deploy>"}.'
            ),
        ] = None,
    ) -> dict:
        """Store a remediation for a human to approve. It does not run anything.

        Unknown trace ids, services or releases are refused, and so is any action outside policy.
        """
        try:
            s = remediations.propose(
                incident_id=incident_id, action=action, target=target, params=params or {},
                root_cause=root_cause, service=faulty_service, release=faulty_release, trace_ids=trace_ids,
                proposed_by="ai-sre",
            )  # fmt: skip
        except (Ungrounded, PolicyError) as err:
            raise ToolError(f"proposal refused: {err}") from err
        return {
            "action_id": s.action_id,
            "state": s.state,
            "approval_url": f"{public_url}/actions/{s.action_id}",
            "next": "Share the approval_url. Wait for the human to confirm approval before executing.",
        }

    @tool
    def execute_remediation(action_id: str) -> dict:
        """Run a remediation a human has approved. Refused, and recorded, if it is not approved."""
        try:
            result = remediations.execute(action_id, executed_by="ai-sre")
        except (ApprovalRequired, InvalidTransition) as err:
            raise ToolError(str(err)) from err
        except KeyError as err:
            raise ToolError(f"no remediation {action_id}") from err
        return {
            "action_id": action_id,
            "result": result,
            "next": "Recovery is verified automatically over the next minute; check get_remediation_status.",
        }

    return mcp
