"""Five argument shapes. No session record of argument mistakes exists for this plugin."""
import json

from conftest import call

TOYOTA = "1180301018771"


def test_hyphenated_corporate_number_is_looked_up(plugin, api):
    result = call(plugin, "jp_corp_search", {"corporate_number": "1180-3010-18771"})
    assert result.get("error") is None
    assert result["results"][0]["corporate_number"] == TOYOTA
    assert TOYOTA in api.requests[0][0]


def test_prefecture_without_suffix_is_aichi(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "address": "愛知"})
    assert result.get("error") is None
    assert api.params()["prefecture"] == "23"
    assert result["query"]["prefecture"] == "愛知県"


def test_limit_float_and_fullwidth_keep_ten(plugin, api):
    for limit in (10.0, "１０"):
        api.requests.clear()
        result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "limit": limit})
        assert result.get("error") is None
        assert result["shown"] == 10


def test_section_case_is_basic(plugin, api):
    result = call(plugin, "jp_corp_profile", {
        "corporate_number": TOYOTA,
        "sections": ["Basic"],
        "max_items": 10.0,
    })
    assert result.get("error") is None
    assert "basic" in result["sections"]
    assert api.requests


def test_extra_argument_and_out_of_range_limit_hide_the_input(plugin, api):
    extra = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "region_code": "23"})
    text = json.dumps(extra, ensure_ascii=False)
    assert extra["ok"] is False
    assert extra["error_type"] == "bad_args"
    assert "トヨタ自動車" in extra["message"]
    assert "region_code" not in text
    assert api.requests == []

    for bad in (0, 80, "１０．５"):
        refused = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "limit": bad})
        blob = json.dumps(refused, ensure_ascii=False)
        assert refused["ok"] is False
        assert refused["error_type"] == "bad_args"
        assert refused["message"] == plugin.tools._LIMIT_MSG
        assert "80" not in blob
        assert api.requests == []
