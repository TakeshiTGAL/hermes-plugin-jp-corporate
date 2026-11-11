"""A final reply stays as written when the token is unset.

A 13-digit number or 株式会社 in an unrelated conversation used to match the
company classifier. Nothing here rewrites that reply. llm_execution is not
registered.
"""


def test_unrelated_reply_is_unchanged_when_the_token_is_unset(plugin, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    middleware = []

    class Ctx:
        def register_tool(self, *args, **kwargs):
            return None

        def register_hook(self, *args, **kwargs):
            return None

        def register_middleware(self, name, callback):
            middleware.append(name)

        def register_skill(self, *args, **kwargs):
            return None

    plugin.register(Ctx())
    assert middleware == []
    assert "llm_execution" not in middleware
    assert not hasattr(plugin, "_fill_token_help")
    assert not hasattr(plugin, "_token_screen")

    cases = (
        (
            "処理が終わった時刻は 1731283200123 です。この数字は何ですか。",
            "1731283200123 はミリ秒の時刻です。会社の照会結果ではありません。",
        ),
        (
            "メールの末尾に株式会社とだけ書いてあります。返事の書き出しを提案して。",
            "お世話になっております。署名の株式会社はメールの定型です。",
        ),
    )
    for user, reply in cases:
        history = [
            {"role": "user", "content": user},
            {"role": "assistant", "content": reply},
        ]
        plugin._nudge_company(
            user_message=user,
            conversation_history=history,
            session_id="s-unrelated",
        )
        assert history[1]["content"] == reply
        assert len(history[1]["content"]) == len(reply)
