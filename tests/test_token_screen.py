"""A company turn with no token shows the free-token steps, not the user text."""

from types import SimpleNamespace


def _response(content, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_echo_becomes_the_free_token_steps(plugin, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    plugin._nudge_company(user_message="パナソニックの資本金は？", session_id="s-echo")
    response = _response("パナソニックの資本金は？")

    def next_call():
        return response

    out = plugin._fill_token_help(next_call=next_call, session_id="s-echo")
    text = out.choices[0].message.content
    assert text == plugin.client.TOKEN_HELP
    assert "パナソニックの資本金は？" not in text
    assert "https://info.gbiz.go.jp/hojin/various_registration/form" in text
    assert "GBIZINFO_API_TOKEN" in text


def test_tool_call_is_left_alone(plugin, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    plugin._nudge_company(user_message="ホンダの従業員数はどれくらい？", session_id="s-call")
    response = _response("", tool_calls=[SimpleNamespace(name="jp_corp_profile")])

    def next_call():
        return response

    out = plugin._fill_token_help(next_call=next_call, session_id="s-call")
    assert out.choices[0].message.tool_calls[0].name == "jp_corp_profile"
    assert out.choices[0].message.content == ""


def test_plain_turn_keeps_the_model_text(plugin, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    plugin._nudge_company(user_message="グラタン皿でチーズグラタンを作る手順を教えて。", session_id="s-off")
    response = _response("オーブンで焼きます。")

    def next_call():
        return response

    out = plugin._fill_token_help(next_call=next_call, session_id="s-off")
    assert out.choices[0].message.content == "オーブンで焼きます。"


def test_reply_that_already_has_the_form_stays(plugin, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    plugin._nudge_company(user_message="日産自動車の概要を教えて", session_id="s-keep")
    kept = "Apply at https://info.gbiz.go.jp/hojin/various_registration/form and set GBIZINFO_API_TOKEN."
    response = _response(kept)

    def next_call():
        return response

    out = plugin._fill_token_help(next_call=next_call, session_id="s-keep")
    assert out.choices[0].message.content == kept
