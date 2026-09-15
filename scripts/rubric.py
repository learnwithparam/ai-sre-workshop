"""The scorecard: every point is bound to one test that already exists.

A `junit` id is a pytest node id. A `pw` id is `<spec file> > <test title>` from Playwright.
tests/test_gate.py fails if any id here names a test that does not exist.
"""

from typing import NamedTuple


class Check(NamedTuple):
    source: str  # "junit" or "pw"
    id: str
    points: int


PHASES: dict[str, list[Check]] = {
    "1 Gate": [
        Check("junit", "tests/test_gate.py::test_make_targets_exist", 3),
        Check("junit", "tests/test_gate.py::test_ci_runs_make_check", 2),
        Check("junit", "tests/test_gate.py::test_every_scored_check_exists", 3),
        Check("junit", "tests/test_gate.py::test_prose_check_is_wired", 2),
    ],
    "2 Substrate and telemetry": [
        Check("pw", "01-stack.spec.ts > every service is healthy", 2),
        Check("pw", "02-telemetry.spec.ts > traces and logs arrive for every app service", 2),
        Check("pw", "02-telemetry.spec.ts > docs-loader logs join traces by TraceId", 2),
        Check("pw", "05-workshop-sql.spec.ts > every workshop query runs as sre_agent", 3),
        Check("pw", "05-workshop-sql.spec.ts > sre_agent cannot write", 2),
        Check("pw", "03-app.spec.ts > a browser signup lands in Postgres and ClickHouse", 2),
        Check("pw", "04-hyperdx.spec.ts > HyperDX search shows subscription-backend traces", 2),
    ],
    "3 Detection": [
        Check("junit", "sre-control/tests/test_anomaly.py::test_spike_is_flagged", 1),
        Check("junit", "sre-control/tests/test_anomaly.py::test_ramp_is_not_flagged", 1),
        Check("pw", "05-workshop-sql.spec.ts > anomaly materialized view is populated", 2),
        Check("pw", "07-bad-release.spec.ts > a bad release opens an incident within 90 seconds", 3),
        Check("pw", "10-docs-hang.spec.ts > hung requests open an incident", 3),
    ],
    "4 MCP tools": [
        Check("junit", "sre-control/tests/test_tools.py::test_every_tool_is_classified", 3),
        Check("junit", "sre-control/tests/test_grounding.py::test_ungrounded_proposal_is_rejected", 2),
        Check("pw", "13-mcp.spec.ts > every SRE read tool returns data", 4),
        Check("pw", "13-mcp.spec.ts > MCP endpoints reject requests without a token", 3),
        Check("pw", "13-mcp.spec.ts > mcp-clickhouse cannot write", 3),
    ],
    "5 Agent loop and HITL": [
        Check(
            "pw",
            "08-investigate.spec.ts > the AI SRE investigates with tools and proposes a grounded rollback",
            6,
        ),
        Check("pw", "09-approve.spec.ts > nothing changes before a human approves", 4),
        Check("pw", "09-approve.spec.ts > approval rolls back, verifies recovery and resolves", 5),
        Check("pw", "10-docs-hang.spec.ts > reject, edit and approve a restart", 4),
        Check("junit", "sre-control/tests/test_approvals.py::test_execute_twice_runs_once", 2),
        Check("junit", "sre-control/tests/test_approvals.py::test_execute_without_approval_refuses", 2),
        Check("pw", "09-approve.spec.ts > audit trail records every decision with approver and time", 2),
    ],
    "6 Self-observability": [
        Check(
            "pw",
            "11-self-observability.spec.ts > agent, MCP and control-plane spans land in ClickStack",
            3,
        ),
        Check("pw", "12-report.spec.ts > report records tool calls, tokens, cost and time to root cause", 2),
    ],
    "7 VPS-ready": [
        Check("junit", "tests/test_compose.py::test_vps_override_is_valid", 1),
        Check("junit", "tests/test_compose.py::test_vps_publishes_only_web_ports", 2),
        Check("junit", "tests/test_compose.py::test_every_vps_ui_requires_login", 1),
        Check("junit", "tests/test_compose.py::test_e2e_targets_derive_from_public_domain", 1),
    ],
    "8 Teach": [
        Check("junit", "tests/test_teach.py::test_teach_exists", 1),
        Check("junit", "tests/test_teach.py::test_named_targets_and_files_exist", 4),
        Check("junit", "tests/test_teach.py::test_every_module_segment_is_complete", 4),
        Check("junit", "tests/test_teach.py::test_figures_match_e2e_report", 4),
        Check("junit", "tests/test_teach.py::test_prose_is_clean", 2),
    ],
}
