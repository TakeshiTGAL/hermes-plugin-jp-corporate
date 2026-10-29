"""Name search at the 1000-row cap must not claim the corporation is absent."""

from conftest import call

NAME = "架空特別名称"


def _rows(count, name="別件商事", location="大阪府大阪市北区１"):
    return [
        {
            "corporate_number": f"{index:013d}",
            "name": f"{name}{index}",
            "location": location,
            "status": "-",
        }
        for index in range(count)
    ]


def _stub(plugin, monkeypatch, rows):
    seen = {}

    def fake_get(path="", params=None):
        seen["params"] = dict(params or {})
        return {"hojin-infos": rows}

    monkeypatch.setattr(plugin.client, "get", fake_get)
    return seen


def test_cap_with_no_local_name_does_not_claim_absence(plugin, monkeypatch):
    _stub(plugin, monkeypatch, _rows(1000))
    result = call(plugin, "jp_corp_search", {"name": NAME})
    message = result["message"]
    assert "has no corporation" not in message
    assert "0 results" not in message
    assert "この1000件には無かった。続きは分からない。" in message
    assert "gBizINFO" in message
    assert "https://info.gbiz.go.jp/" in message
    assert result["attribution"]["en"].startswith("Source: gBizINFO")
    assert result["complete"] is False
    assert result["found"] == 0


def test_under_the_cap_still_says_there_is_no_corporation(plugin, monkeypatch):
    _stub(plugin, monkeypatch, _rows(999))
    result = call(plugin, "jp_corp_search", {"name": NAME})
    assert "has no corporation" in result["message"]
    assert "続きは分からない" not in result["message"]
    assert result.get("complete") is not False


def test_not_found_still_says_there_is_no_corporation(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "ゾゾヌヌポポ架空商事"})
    assert "has no corporation" in result["message"]
    assert "続きは分からない" not in result["message"]
    assert result.get("complete") is not False


def test_empty_list_under_the_cap_still_says_there_is_no_corporation(plugin, monkeypatch):
    _stub(plugin, monkeypatch, [])
    result = call(plugin, "jp_corp_search", {"name": NAME})
    assert "has no corporation" in result["message"]
    assert "続きは分からない" not in result["message"]


def test_one_row_past_the_cap_does_not_pretend_only_1000_were_read(plugin, monkeypatch):
    _stub(plugin, monkeypatch, _rows(1001))
    result = call(plugin, "jp_corp_search", {"name": NAME})
    assert "has no corporation" not in result["message"]
    assert "この1001件には無かった。続きは分からない。" in result["message"]
    assert "この1000件には無かった" not in result["message"]
    assert result["complete"] is False


def test_a_match_inside_the_cap_is_returned(plugin, monkeypatch):
    rows = _rows(999)
    rows.append({
        "corporate_number": "1180301018771",
        "name": f"{NAME}株式会社",
        "location": "東京都千代田区１",
        "status": "-",
    })
    seen = _stub(plugin, monkeypatch, rows)
    result = call(plugin, "jp_corp_search", {"name": NAME})
    assert seen["params"]["limit"] == "1000" or seen["params"]["limit"] == 1000
    assert result["found"] >= 1
    assert result["results"][0]["corporate_number"] == "1180301018771"
    assert "has no corporation" not in result.get("message", "")
    assert "続きは分からない" not in result.get("message", "")
    assert "1000" in result["note"]
    assert result.get("complete") is not False


def test_cap_and_address_filter_does_not_deny_the_name(plugin, monkeypatch):
    rows = _rows(1000, name=f"{NAME}株式会社", location="東京都千代田区１")
    _stub(plugin, monkeypatch, rows)
    result = call(plugin, "jp_corp_search", {"name": NAME, "address": "那覇市"})
    message = result["message"]
    assert "has no corporation" not in message
    assert "whose name contains" not in message
    assert "続きは分からない" in message
    assert "那覇市" in message
    assert result["complete"] is False


def test_cap_inside_one_prefecture_names_that_prefecture(plugin, monkeypatch):
    seen = _stub(plugin, monkeypatch, _rows(1000))
    result = call(plugin, "jp_corp_search", {"name": NAME, "address": "東京都"})
    assert seen["params"]["prefecture"] == "13"
    assert "東京都" in result["message"]
    assert "has no corporation" not in result["message"]
    assert "続きは分からない" in result["message"]
    assert result["attribution"]["ja"].startswith("出典：")
