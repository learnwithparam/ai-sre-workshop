"""Structural: every MCP tool is classified, and its MCP annotations say the same thing."""

import asyncio

import pytest
from fastmcp import FastMCP

from sre_control.policy import TOOL_CLASSES, ToolClass
from sre_control.tools import UnclassifiedTool, build_mcp, sre_tool


def tools(remediations):
    mcp = build_mcp(telemetry=None, remediations=remediations, token=None)
    return {t.name: t for t in asyncio.run(mcp.list_tools())}


def test_every_tool_is_classified(remediations):
    registered = tools(remediations)
    assert set(registered) == set(TOOL_CLASSES)
    for name, tool in registered.items():
        cls = TOOL_CLASSES[name]
        assert tool.annotations.read_only_hint is (cls is ToolClass.READ), name
        assert tool.annotations.destructive_hint is (cls is ToolClass.ACTION), name


def test_an_unclassified_tool_cannot_register():
    with pytest.raises(UnclassifiedTool):

        @sre_tool(FastMCP("probe"))
        def delete_everything() -> str:
            return "no"


def test_only_one_tool_can_act():
    assert [n for n, c in TOOL_CLASSES.items() if c is ToolClass.ACTION] == ["execute_remediation"]


def test_every_remediation_target_names_its_service():
    from sre_control.policy import ACTIONS, TARGETS

    assert {t for targets in ACTIONS.values() for t in targets} == set(TARGETS)
