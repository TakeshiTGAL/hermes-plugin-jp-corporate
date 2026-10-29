"""The company nudge still names the search call and does not claim an uncalled profile."""


def test_nudge_calls_search_and_does_not_claim_an_uncalled_profile(plugin):
    text = plugin._nudge_company(user_message="トヨタ自動車")["context"]
    assert "jp_corp_search" in text
    assert "use tool_search to find jp_corp_search" in text
    assert "Do not call tool_search" not in text
    assert "Do not call tool_describe" in text
    assert "The company name is the name in the user message." in text
    assert "Do not pass the word COMPANY as the name." in text
    assert '"name":"COMPANY"' not in text
    assert "jp_corp_profile confirmed" in text
    assert "確認できます" in text
    assert "successfully retrieved" in text
    assert "verified" in text
    assert "obtained using" in text
    assert "取得しました" in text
    assert "next_step" in text


def test_missing_token_paragraph_names_the_form_and_the_env(plugin, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    text = plugin._nudge_company(user_message="パナソニックの資本金は？", session_id="s-form")["context"]
    assert text.startswith("Company lookup:")
    assert "https://info.gbiz.go.jp/hojin/various_registration/form" in text
    assert "GBIZINFO_API_TOKEN" in text
    assert "not the user message" in text
    assert "EDINET" not in text
    monkeypatch.setenv("GBIZINFO_API_TOKEN", "present-token")
    set_text = plugin._nudge_company(user_message="パナソニックの資本金は？", session_id="s-set")["context"]
    assert "various_registration/form" not in set_text


def test_nudge_is_absent_on_a_settings_question(plugin):
    assert plugin._nudge_company(user_message="hermes の設定はどこで見る？") is None
    assert plugin._nudge_company(user_message="コーヒーの入れ方") is None
    assert plugin._nudge_company(user_message="Pythonでフィボナッチ数列を計算する関数を書いて。") is None
    assert plugin._nudge_company(user_message="グラタン皿でチーズグラタンを作る手順を教えて。") is None
    assert plugin._nudge_company(user_message="有報の連結の売上") is None
