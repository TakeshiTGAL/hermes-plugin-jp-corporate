import json
from pathlib import Path

import pytest
import yaml

from conftest import FAKE_TOKEN, call

PLUGIN_DIR = Path(__file__).resolve().parent.parent
TOYOTA = "1180301018771"
METI = "4000012090001"


# --- Registration, manifest and catalog entry --------------------------------------

def test_register_wires_every_schema_to_its_handler(plugin):
    registered = {}

    class Ctx:
        def register_tool(self, name, toolset, schema, handler, **kwargs):
            registered[name] = (toolset, schema, handler, kwargs)

    plugin.register(Ctx())
    assert list(registered) == ["jp_corp_search", "jp_corp_profile"]
    for name, (toolset, schema, handler, kwargs) in registered.items():
        assert toolset == "jp_corporate"
        assert schema["name"] == name
        assert kwargs["requires_env"] == ["GBIZINFO_API_TOKEN"]
        assert callable(handler)


def test_manifest_matches_the_registrations(plugin):
    manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    tools = [schema["name"] for schema in plugin.schemas.ALL_SCHEMAS]
    assert manifest["provides_tools"] == tools
    assert [env["name"] for env in manifest["requires_env"]] == [plugin.client.TOKEN_ENV]
    assert manifest["version"] == plugin.client.VERSION


# --- Search by name ------------------------------------------------------------------

@pytest.mark.parametrize("name", ["トヨタ自動車", "(株)トヨタ自動車", "(株) トヨタ自動車", "ﾄﾖﾀ自動車", "トヨタ自動車株式会社", "㈱ﾄﾖﾀ自動車"])
def test_name_variants_reach_toyota_first(plugin, api, name):
    result = call(plugin, "jp_corp_search", {"name": name})
    assert api.params()["name"] == "トヨタ自動車"
    top = result["results"][0]
    assert top["corporate_number"] == TOYOTA
    assert top["name"] == "トヨタ自動車株式会社"
    assert top["match"] == "exact"
    assert top["status"] == "registered"
    assert top["gbizinfo_url"] == f"https://info.gbiz.go.jp/hojin/ichiran?hojinBango={TOYOTA}"
    assert result["found"] > 50 and result["shown"] == 10
    assert "出典：「Gビズインフォ」（経済産業省）" in result["attribution"]["ja"]


def test_search_sends_the_token_header_and_no_trailing_slash(plugin, api):
    call(plugin, "jp_corp_search", {"name": "トヨタ自動車"})
    url, headers = api.requests[0]
    assert url.startswith("https://api.info.gbiz.go.jp/hojin/v2/hojin?")
    assert headers["X-hojininfo-api-token"] == FAKE_TOKEN


def test_closed_companies_rank_after_registered_ones_with_the_same_match(plugin, api, monkeypatch):
    monkeypatch.setattr(plugin.tools, "MAX_RESULTS", 100)
    result = plugin.tools.search({"name": "トヨタ自動車", "limit": 100})
    rows = [(r["match"], r["status"]) for r in result["results"]]
    assert len(rows) == 81 and sum(status == "closed" for _, status in rows) == 9
    for tier in ("exact", "starts_with", "contains"):
        statuses = [status for match, status in rows if match == tier]
        assert statuses == sorted(statuses, key=lambda status: status == "closed"), tier
    tiers = [match for match, _ in rows]
    assert tiers == sorted(tiers, key=["exact", "starts_with", "contains"].index)


def test_address_narrows_same_name_companies(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "address": "愛知県豊田市"})
    assert api.params()["prefecture"] == "23"
    assert result["results"][0]["corporate_number"] == TOYOTA
    assert all("豊田市" in r["location"] for r in result["results"])
    assert result["found"] == 5
    assert result["query"]["prefecture"] == "愛知県"


def test_city_only_address_filters_locally(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "address": "札幌市"})
    assert "prefecture" not in api.params()
    assert {r["corporate_number"] for r in result["results"]} == {"2430001020191", "4430005002614", "5430005002522"}


def test_half_width_ascii_is_left_to_the_api(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "kddi"})
    assert api.params()["name"] == "kddi"


def test_unknown_name_says_zero_results_and_what_to_try(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "ゾゾヌヌポポ架空商事"})
    assert result["found"] == 0
    assert "0 results" in result["message"]
    assert result["next_steps"]
    assert "error" not in result


def test_address_that_matches_nothing_explains_the_filter(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "address": "那覇市"})
    assert result["found"] == 0
    assert "none at '那覇市'" in result["next_steps"][0]


def test_legal_form_only_is_an_input_error_without_a_request(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "株式会社"})
    assert result["error"] == "input" and api.requests == []


def test_nothing_given_is_an_input_error(plugin, api):
    result = call(plugin, "jp_corp_search", {})
    assert result["error"] == "input" and api.requests == []


# --- Search / verify by corporate number ------------------------------------------------

def test_number_lookup_returns_meti(plugin, api):
    result = call(plugin, "jp_corp_search", {"corporate_number": METI})
    assert result["found"] == 1
    assert result["results"][0]["name"] == "経済産業省"
    assert api.requests[0][0] == f"https://api.info.gbiz.go.jp/hojin/v2/hojin/{METI}"


def test_invoice_number_with_t_prefix_is_accepted(plugin, api):
    result = call(plugin, "jp_corp_search", {"corporate_number": f"T{TOYOTA}"})
    assert result["results"][0]["corporate_number"] == TOYOTA


@pytest.mark.parametrize("number", ["118030101877", "2180301018771", "1180301018772", "abc"])
def test_bad_numbers_never_reach_the_api(plugin, api, number):
    result = call(plugin, "jp_corp_search", {"corporate_number": number})
    assert result["error"] == "input"
    assert api.requests == []


@pytest.mark.parametrize("given, verdict", [
    ("トヨタ自動車株式会社", "match"),
    ("ﾄﾖﾀ自動車(株)", "match"),
    ("(株)トヨタ自動車", "match_except_legal_form"),
    ("トヨタ自動車販売株式会社", "mismatch"),
])
def test_invoice_name_check(plugin, api, given, verdict):
    result = call(plugin, "jp_corp_search", {"corporate_number": TOYOTA, "name": given})
    assert result["checks"]["name"] == verdict


@pytest.mark.parametrize("given, verdict", [
    ("愛知県豊田市トヨタ町1番地", "match"),
    ("愛知県豊田市トヨタ町１", "match"),
    ("豊田市トヨタ町一番地", "match"),
    ("愛知県豊田市トヨタ町1番地 トヨタ会館", "match"),
    ("愛知県豊田市トヨタ町10番地", "same_municipality_different_street"),
    ("愛知県豊田市", "partial"),
    ("愛知県", "partial"),
    ("愛知県豊田市元町1", "same_municipality_different_street"),
    ("東京都文京区後楽1-4-18", "mismatch"),
    ("岐阜県豊田市トヨタ町1", "mismatch"),
    ("〒471-0826 愛知県豊田市トヨタ町1番地", "match"),
    ("４７１－０８２６　愛知県豊田市トヨタ町１番地", "match"),
    ("愛知県豊田市トヨタ町1-1", "more_detailed"),
    ("〒471‐0826 愛知県豊田市トヨタ町1", "match"),
    ("〒471-0826", "partial"),
])
def test_invoice_address_check(plugin, api, given, verdict):
    result = call(plugin, "jp_corp_search", {"corporate_number": TOYOTA, "address": given})
    assert result["checks"]["address"] == verdict


def test_well_formed_number_unknown_to_gbizinfo(plugin, api):
    result = call(plugin, "jp_corp_search", {"corporate_number": "7123456789012"})  # check digit OK, no such corporation in the fixtures
    assert result["found"] == 0
    assert "invoice-kohyo.nta.go.jp" in result["message"]


# --- Errors that need the user to act ----------------------------------------------------

def test_missing_token_points_to_the_application_form(plugin, api, monkeypatch):
    monkeypatch.delenv("GBIZINFO_API_TOKEN")
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車"})
    assert result["error"] == "token_missing"
    assert "https://info.gbiz.go.jp/hojin/various_registration/form" in result["message"]
    assert "~/.hermes/.env" in result["message"]
    assert api.requests == []


def test_rejected_token_says_what_to_check(plugin, api):
    api.status_override = 401
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車"})
    assert result["error"] == "api" and result["http_status"] == 401
    assert "Web API 利用申請完了" in result["message"]
    assert FAKE_TOKEN not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("status", [403, 429])
def test_rate_limit_says_to_wait(plugin, api, status):
    api.status_override = status
    result = call(plugin, "jp_corp_profile", {"corporate_number": METI})
    assert result["http_status"] == status
    assert "wait several minutes" in result["message"]


def test_server_error_suggests_retry_later(plugin, api):
    api.status_override = 500
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車"})
    assert "try again later" in result["message"]


def test_repeated_lookup_is_served_from_memory(plugin, api):
    call(plugin, "jp_corp_search", {"name": "トヨタ自動車"})
    call(plugin, "jp_corp_search", {"name": "(株)トヨタ自動車"})
    assert len(api.requests) == 1


# --- Profile ----------------------------------------------------------------------------

def test_profile_basic_for_toyota(plugin, api):
    result = call(plugin, "jp_corp_profile", {"corporate_number": TOYOTA})
    basic = result["sections"]["basic"]
    assert result["name"] == "トヨタ自動車株式会社"
    assert result["api_requests"] == 1
    assert basic["kind"].startswith("株式会社")
    assert basic["status"] == "registered"
    assert "freshness_note" in basic and "2019-04-23" in basic["freshness_note"]
    assert basic["capital_stock_jpy"] == 635402000000
    assert basic["industry"] == ["E 製造業"]
    assert basic["established"] == "1937-08-27"
    assert result["attribution"]["ja"].startswith(
        f"出典：「Gビズインフォ」（経済産業省）（https://info.gbiz.go.jp/hojin/ichiran?hojinBango={TOYOTA}）を加工して作成")


def test_profile_sections_cost_one_request_each(plugin, api):
    sections = ["basic", "procurement", "certification", "commendation", "finance", "workplace", "subsidy"]
    result = call(plugin, "jp_corp_profile", {"corporate_number": TOYOTA, "sections": sections, "max_items": 3})
    assert result["api_requests"] == len(api.requests) == 7
    again = call(plugin, "jp_corp_profile", {"corporate_number": TOYOTA, "sections": ["basic"]})
    assert again["api_requests"] == 0  # served from the in-memory cache
    out = result["sections"]
    assert out["procurement"]["total"] == 39 and len(out["procurement"]["items"]) == 3
    dates = [item["date"] for item in out["procurement"]["items"]]
    assert dates == sorted(dates, reverse=True)
    assert out["certification"]["items"][0]["title"] == "ＤＸ認定制度"
    assert out["subsidy"] == {"total": 0, "items": []}
    finance = out["finance"]
    assert finance["results_by_year"][0]["years_before_latest"] == 0
    assert finance["major_shareholders"][0] == {"name": "日本マスタートラスト信託銀行㈱", "share_pct": 12.8}
    assert out["workplace"]["female_worker_pct"] == 40.6


def test_profile_subsidy_and_offices(plugin, api):
    result = call(plugin, "jp_corp_profile", {"corporate_number": "1010801006516", "sections": ["subsidy", "offices"]})
    subsidy = result["sections"]["subsidy"]["items"][0]
    assert subsidy["amount_jpy"] == 10000000
    assert "ものづくり" in subsidy["title"]
    office = result["sections"]["offices"]["items"][0]
    assert office["insured_employees"] == 21
    assert result["name"] == "大栄精工株式会社"


def test_profile_patents_are_deduplicated(plugin, api):
    result = call(plugin, "jp_corp_profile", {"corporate_number": "5011001043924", "sections": "patent"})
    patents = result["sections"]["patent"]
    raw = json.loads((PLUGIN_DIR / "tests/fixtures/hojin_5011001043924_patent.json").read_text())
    raw_rows = raw["hojin-infos"][0]["patent"]
    assert patents["total"] < len(raw_rows)
    numbers = [p["registration_number"] for p in patents["items"]]
    assert len(numbers) == len(set(numbers))


def test_profile_unknown_section_is_an_input_error(plugin, api):
    result = call(plugin, "jp_corp_profile", {"corporate_number": TOYOTA, "sections": ["basic", "news"]})
    assert result["error"] == "input" and "subsidy" in result["message"]
    assert api.requests == []


def test_profile_bad_number_is_an_input_error(plugin, api):
    result = call(plugin, "jp_corp_profile", {"corporate_number": "1234567890123"})
    assert result["error"] == "input" and api.requests == []


def test_handlers_return_json_even_on_unexpected_errors(plugin, api, monkeypatch):
    monkeypatch.setattr(plugin.client, "get", lambda *a, **k: 1 / 0)
    result = call(plugin, "jp_corp_search", {"corporate_number": METI})
    assert result["error"] == "internal"


def test_meti_address_with_chome_is_checked_by_whole_numbers(plugin, api):
    def check(address):
        return call(plugin, "jp_corp_search", {"corporate_number": METI, "address": address})["checks"]["address"]
    assert check("東京都千代田区霞が関1-3-1") == "match"
    assert check("東京都千代田区霞が関一丁目3番1号") == "match"
    assert check("東京都千代田区霞が関1-3") == "partial"
    assert check("東京都千代田区霞が関1-31-1") == "same_municipality_different_street"
    assert check("東京都千代田区霞ヶ関1-3-1") == "match"


def test_errors_and_input_errors_report_zero_requests(plugin, api):
    assert call(plugin, "jp_corp_search", {"corporate_number": "1"})["api_requests"] == 0


def test_redirects_are_not_followed(plugin):
    import urllib.request
    handler = plugin.client._NoRedirect()
    request = urllib.request.Request("https://api.info.gbiz.go.jp/hojin/v2/hojin/x",
                                     headers={"X-hojinInfo-api-token": FAKE_TOKEN})
    assert handler.redirect_request(request, None, 302, "Found", {}, "https://elsewhere.example/") is None
    message = str(plugin.client._http_error(302))
    assert "not followed" in message and FAKE_TOKEN not in message


def test_postal_code_in_search_address_is_ignored(plugin, api):
    result = call(plugin, "jp_corp_search", {"name": "トヨタ自動車", "address": "〒471-0826 愛知県豊田市"})
    assert api.params()["prefecture"] == "23"
    assert result["results"][0]["corporate_number"] == TOYOTA


def test_representative_padding_is_removed(plugin):
    # gBizINFO pads the title and each character of the name with NBSP + space (synthetic example).
    assert plugin.tools._representative("代表取締役\xa0\xa0\xa0 山\xa0 田\xa0 太\xa0 郎") == "代表取締役 山田太郎"
    assert plugin.tools._representative("代表取締役 山田 太郎") == "代表取締役 山田 太郎"
