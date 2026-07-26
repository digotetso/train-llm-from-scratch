import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "audition_get_status",
    "audition_get_document",
    "audition_get_selection",
    "audition_set_playhead",
    "audition_set_selection",
    "audition_play",
    "audition_pause",
    "audition_stop",
    "audition_record",
    "audition_open",
    "audition_import",
    "audition_save",
    "audition_export",
    "audition_list_effects",
    "audition_apply_effect",
}


def test_server_exposes_exact_tool_surface(config_path: Path) -> None:
    async def scenario() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "audio_mcp.audition.server"],
            env={
                **os.environ,
                "AUDIO_MCP_AUDITION_CONFIG": str(config_path),
            },
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                local_result = await session.call_tool(
                    "audition_list_effects",
                    {},
                )
                coerced_confirmation = await session.call_tool(
                    "audition_save",
                    {"confirm": "true"},
                )

        assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS
        assert local_result.isError is False
        assert coerced_confirmation.isError is True
        confirmed = {
            tool.name: tool.inputSchema
            for tool in tools.tools
            if tool.name
            in {
                "audition_record",
                "audition_open",
                "audition_import",
                "audition_save",
                "audition_export",
                "audition_apply_effect",
            }
        }
        for schema in confirmed.values():
            assert "confirm" in schema["required"]
            assert schema["properties"]["confirm"]["type"] == "boolean"

    asyncio.run(scenario())
