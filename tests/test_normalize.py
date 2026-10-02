import pytest


@pytest.mark.parametrize("raw", ["4000012090001", "1180301018771", "T1180301018771", "t1180301018771",
                                 "１１８０３０１０１８７７１", "1180-3010-18771", " 1180301018771 "])
def test_valid_corporate_numbers_are_cleaned(plugin, raw):
    assert plugin.normalize.parse_corporate_number(raw) in {"4000012090001", "1180301018771"}


@pytest.mark.parametrize("raw, fragment", [
    ("118030101877", "has 12 digits"),
    ("11803010187711", "has 14 digits"),
    ("2180301018771", "fails the 法人番号 check digit"),
    ("1180301018772", "fails the 法人番号 check digit"),
    ("ABC", "characters other than digits"),
    ("", "empty"),
])
def test_bad_corporate_numbers_are_rejected(plugin, raw, fragment):
    with pytest.raises(plugin.normalize.InputError, match=fragment):
        plugin.normalize.parse_corporate_number(raw)


@pytest.mark.parametrize("raw", ["トヨタ自動車", "トヨタ自動車株式会社", "(株)トヨタ自動車", "（株）トヨタ自動車",
                                 "㈱トヨタ自動車", "ﾄﾖﾀ自動車", "ﾄﾖﾀ自動車(株)", "株式会社 トヨタ自動車", "トヨタ 自動車"])
def test_name_variants_share_one_core(plugin, raw):
    assert plugin.normalize.core_name(raw) == "トヨタ自動車"


@pytest.mark.parametrize("raw, term", [
    ("(株)トヨタ自動車", "トヨタ自動車"),
    ("ﾄﾖﾀ自動車", "トヨタ自動車"),
    ("ＫＤＤＩ株式会社", "KDDI"),
    ("KDDI xG Networks", "Networks"),
])
def test_query_term_drops_legal_forms_and_keeps_the_longest_piece(plugin, raw, term):
    assert plugin.normalize.query_term(raw) == term


@pytest.mark.parametrize("address, expected", [
    ("愛知県豊田市", ("23", "豊田市")),
    ("愛知", ("23", "")),
    ("Tokyo", ("13", "")),
    ("tokyo-to", ("13", "")),
    ("北海道札幌市", ("01", "札幌市")),
    ("豊田市", (None, "豊田市")),
    ("京都市南区", (None, "京都市南区")),
    ("京都府京都市", ("26", "京都市")),
    ("福島区", (None, "福島区")),
    ("〒471-0826 愛知県豊田市", ("23", "豊田市")),
])
def test_split_prefecture(plugin, address, expected):
    assert plugin.normalize.split_prefecture(address) == expected


def test_fold_address_ignores_chome_banchi_and_width(plugin):
    fold = plugin.normalize.fold_address
    assert fold("東京都千代田区霞が関１丁目３－１") == fold("東京都千代田区霞が関1-3-1")
    assert fold("愛知県豊田市トヨタ町１番地") == fold("愛知県豊田市トヨタ町1")
