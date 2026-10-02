"""jp-corporate (法人照会): look up Japanese corporations in gBizINFO from Hermes Agent.

Registers two read-only tools under the `jp_corporate` toolset:
jp_corp_search (find / verify a corporation) and jp_corp_profile (details by
corporate number). Data source: gBizINFO REST API v2, Ministry of Economy,
Trade and Industry, Japan.
"""

from . import client, schemas, tools


def register(ctx):
    """Wire each schema to its handler."""
    for schema in schemas.ALL_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="jp_corporate",
            schema=schema,
            handler=tools.HANDLERS[schema["name"]],
            requires_env=[client.TOKEN_ENV],
            emoji="🏢",
        )
