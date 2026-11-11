"""jp-corporate (法人照会): look up Japanese corporations in gBizINFO from Hermes Agent.

Registers two read-only tools under the `jp_corporate` toolset:
jp_corp_search (find / verify a corporation) and jp_corp_profile (details by
corporate number). Data source: gBizINFO REST API v2, Ministry of Economy,
Trade and Industry, Japan.
"""

from . import client, schemas, tools, turn_scope

_SKILL_DESCRIPTION = (
    "Japan company registry (gBizINFO) and corporate numbers. "
    "Before web_search, use tool_search to find jp_corp_search and tool_call it. "
    "Do not call tool_describe. If error is token_missing, copy next_step and stop. "
    "Do not say jp_corp_profile confirmed a number when that tool was not called. "
    "Do not write 取得しました, 確認できます, successfully retrieved, verified, or obtained using. "
    "That ban is the same as 取得しました. "
    "Do not write a number the result does not contain."
)


def _company_turn(user_message, conversation_history=None) -> bool:
    """Corporate number, legal form, registry name, field plus name, or a previous jp_corp call."""
    return turn_scope.owns(user_message, conversation_history, "company")


_NUDGE = (
    "Company lookup: the parameters of jp_corp_search are known. Do not call tool_describe. "
    "Before web_search, use tool_search to find jp_corp_search when it is not already visible, "
    "then tool_call it. "
    "If a tool result is already in this conversation, copy its next_step and stop. "
    "Otherwise call jp_corp_search. The company name is the name in the user message. "
    "Do not pass the word COMPANY as the name. "
    "If the result error is token_missing, copy the next_step field into the reply and stop. "
    "Do not say jp_corp_profile confirmed a corporate number or an address when that tool was not called. "
    "Do not write 取得しました, 確認しました, or 確認できます. "
    "Do not write successfully retrieved, verified, or obtained using. "
    "That ban is the same as 取得しました. "
    "Do not write a corporate number, address, industry, capital, employees, or yen "
    "that the tool result does not contain."
)


def _nudge_company(user_message="", conversation_history=None, **kwargs):
    if not _company_turn(user_message, conversation_history):
        return None
    return {"context": _NUDGE}


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
    try:
        ctx.register_hook("pre_llm_call", _nudge_company)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("jp-corporate pre_llm_call hook unavailable", exc_info=True)
    try:
        from pathlib import Path
        ctx.register_skill(
            "japan-company",
            Path(__file__).resolve().parent / "skills" / "japan-company" / "SKILL.md",
            description=_SKILL_DESCRIPTION,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning("jp-corporate skill was not registered", exc_info=True)
