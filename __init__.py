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


def _token_is_unset() -> bool:
    """True only when the token helper answered that no token is configured."""
    try:
        return not client.token_configured()
    except Exception:
        return False


# session_id -> this turn should show the free-token steps instead of the user text.
_token_screen = {}

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
_TOKEN_LINE = (
    " If GBIZINFO_API_TOKEN is not set, the reply is how to get the free token, not the user message."
    f" Apply at {client.APPLY_URL}"
    " and put the token in the environment variable GBIZINFO_API_TOKEN."
)


def _note_screen(session_id, user_message, conversation_history) -> None:
    company = _company_turn(user_message, conversation_history)
    _token_screen[session_id or ""] = bool(company and _token_is_unset())


def _message_of(response):
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return None
    choice = choices[0]
    if isinstance(choice, dict):
        return choice.get("message")
    return getattr(choice, "message", None)


def _has_tool_calls(message) -> bool:
    if isinstance(message, dict):
        calls = message.get("tool_calls")
    else:
        calls = getattr(message, "tool_calls", None)
    return bool(calls)


def _content_of(message):
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", None)


def _write_content(message, text: str) -> bool:
    try:
        if isinstance(message, dict):
            message["content"] = text
        else:
            message.content = text
    except Exception:
        return False
    return True


def _nudge_company(user_message="", conversation_history=None, **kwargs):
    _note_screen(kwargs.get("session_id") or "", user_message, conversation_history)
    if not _company_turn(user_message, conversation_history):
        return None
    text = _NUDGE
    if _token_is_unset():
        text += _TOKEN_LINE
    return {"context": text}


def _fill_token_help(**kwargs):
    """On a company turn with no token, a final reply becomes the free-token steps.

    A reply that still has tool calls is left alone so the tool can run. The
    first transform hook that returns a string wins, and another book appends
    its line first, so this runs on the provider response before that hook.
    """
    next_call = kwargs.get("next_call")
    if not callable(next_call):
        return None
    response = next_call()
    if not _token_screen.get(kwargs.get("session_id") or ""):
        return response
    message = _message_of(response)
    if message is None or _has_tool_calls(message):
        return response
    content = _content_of(message)
    if isinstance(content, str) and client.APPLY_URL in content:
        return response
    if _write_content(message, client.TOKEN_HELP):
        return response
    return response


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
        ctx.register_middleware("llm_execution", _fill_token_help)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("jp-corporate llm_execution middleware unavailable", exc_info=True)
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
