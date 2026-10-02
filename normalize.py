"""Input normalisation that runs before any API request.

Everything here is pure and offline: corporate-number validation (format and
check digit), company-name folding (width, legal-form words such as 株式会社 /
(株) / ㈱), address folding, and prefecture lookup. A request that fails these
checks never reaches gBizINFO.
"""

from __future__ import annotations

import re
import unicodedata

# --- Corporate number (法人番号) -------------------------------------------------

_NUMBER_JUNK = re.compile(r"[\s\-‐‑‒–—―ー－/]")


class InputError(ValueError):
    """The caller's input is wrong. The message says how to fix it."""


def check_digit(base12: str) -> int:
    """Check digit of a 12-digit corporate-number base (National Tax Agency rule).

    Digits are weighted 1, 2, 1, 2, ... from the rightmost digit; the check digit
    is 9 - (weighted sum mod 9) and is written in front of the 12 digits.
    """
    total = sum(int(d) * (1 if i % 2 == 0 else 2) for i, d in enumerate(reversed(base12)))
    return 9 - total % 9


def parse_corporate_number(raw: str) -> str:
    """Return a clean 13-digit corporate number or raise InputError.

    Accepts full-width digits, spaces and hyphens, and the "T" prefix of an
    invoice registration number (適格請求書発行事業者登録番号), which for a
    corporation is "T" + its corporate number.
    """
    text = unicodedata.normalize("NFKC", str(raw or "")).strip()
    text = _NUMBER_JUNK.sub("", text)
    if text[:1] in ("T", "t"):
        text = text[1:]
    if not text:
        raise InputError("corporate_number is empty. Give the 13-digit 法人番号, e.g. 1180301018771.")
    if not text.isdigit():
        raise InputError(
            f"corporate_number {raw!r} contains characters other than digits. "
            "Give the 13-digit 法人番号 (an invoice number like T1180301018771 is also accepted)."
        )
    if len(text) != 13:
        raise InputError(
            f"corporate_number {raw!r} has {len(text)} digits; a 法人番号 has exactly 13. "
            "Check for a missing or extra digit. To find the number from a name, call jp_corp_search with name instead."
        )
    expected = check_digit(text[1:])
    if int(text[0]) != expected:
        # The expected digit is deliberately not shown: "fixing" the first digit would turn a
        # typo anywhere in the number into a valid-looking number of some other corporation.
        raise InputError(
            f"corporate_number {raw!r} fails the 法人番号 check digit, so at least one digit is wrong. "
            "Re-check it against the source document (invoice, contract, registry) or search by name "
            "instead. No request was sent."
        )
    return text


# --- Company names --------------------------------------------------------------

# Longest first so 特定非営利活動法人 wins over shorter overlaps.
_LEGAL_FORMS = sorted(
    [
        "株式会社", "有限会社", "合同会社", "合名会社", "合資会社", "相互会社",
        "一般社団法人", "一般財団法人", "公益社団法人", "公益財団法人",
        "特定非営利活動法人", "NPO法人", "医療法人社団", "医療法人財団", "医療法人",
        "社会福祉法人", "学校法人", "宗教法人", "独立行政法人", "国立研究開発法人",
        "有限責任事業組合", "協同組合", "外国会社",
    ],
    key=len,
    reverse=True,
)
# After NFKC, ㈱ becomes "(株)" and ㍿ becomes "株式会社".
_ABBREVIATIONS = {
    "(株)": "株式会社", "(有)": "有限会社", "(同)": "合同会社", "(名)": "合名会社",
    "(資)": "合資会社", "(相)": "相互会社", "(一社)": "一般社団法人", "(一財)": "一般財団法人",
    "(公社)": "公益社団法人", "(公財)": "公益財団法人", "(特非)": "特定非営利活動法人",
    "(医)": "医療法人", "(福)": "社会福祉法人", "(学)": "学校法人", "(宗)": "宗教法人",
    "(独)": "独立行政法人",
}
_SPACE = re.compile(r"\s+")


def fold(text: str) -> str:
    """Width- and space-insensitive form: NFKC, no whitespace, upper-case ASCII."""
    return _SPACE.sub("", unicodedata.normalize("NFKC", str(text or ""))).upper()


def full_name(text: str) -> str:
    """Folded name with abbreviations such as (株) / ㈱ spelled out as 株式会社."""
    folded = fold(text)
    for short, long in _ABBREVIATIONS.items():
        folded = folded.replace(short, long)
    return folded


def core_name(text: str) -> str:
    """Folded name without its legal-form words: '(株)ﾄﾖﾀ自動車' -> 'トヨタ自動車'."""
    name = full_name(text)
    for form in _LEGAL_FORMS:
        name = name.replace(form, "")
    return name


def query_term(text: str) -> str:
    """The string to send to gBizINFO's partial-match name search.

    Width differences are left to the API (it matches ﾄﾖﾀ to トヨタ and KDDI to
    ＫＤＤＩ), but legal-form words are removed because '(株)トヨタ自動車' is not a
    substring of 'トヨタ自動車株式会社'. Official names sometimes contain spaces
    ('ＫＤＤＩ　ｘＧ　Ｎｅｔｗｏｒｋｓ') and user input sometimes adds them, so only
    the longest space-free piece is sent; the full name is matched afterwards,
    ignoring spaces.
    """
    name = unicodedata.normalize("NFKC", str(text or ""))
    for short, long in _ABBREVIATIONS.items():
        name = name.replace(short, long)
    for form in _LEGAL_FORMS:
        name = name.replace(form, " ")
    pieces = name.split()
    return max(pieces, key=len) if pieces else ""


# --- Addresses ------------------------------------------------------------------

PREFECTURES = {
    "01": ("北海道", "hokkaido"), "02": ("青森県", "aomori"), "03": ("岩手県", "iwate"),
    "04": ("宮城県", "miyagi"), "05": ("秋田県", "akita"), "06": ("山形県", "yamagata"),
    "07": ("福島県", "fukushima"), "08": ("茨城県", "ibaraki"), "09": ("栃木県", "tochigi"),
    "10": ("群馬県", "gunma"), "11": ("埼玉県", "saitama"), "12": ("千葉県", "chiba"),
    "13": ("東京都", "tokyo"), "14": ("神奈川県", "kanagawa"), "15": ("新潟県", "niigata"),
    "16": ("富山県", "toyama"), "17": ("石川県", "ishikawa"), "18": ("福井県", "fukui"),
    "19": ("山梨県", "yamanashi"), "20": ("長野県", "nagano"), "21": ("岐阜県", "gifu"),
    "22": ("静岡県", "shizuoka"), "23": ("愛知県", "aichi"), "24": ("三重県", "mie"),
    "25": ("滋賀県", "shiga"), "26": ("京都府", "kyoto"), "27": ("大阪府", "osaka"),
    "28": ("兵庫県", "hyogo"), "29": ("奈良県", "nara"), "30": ("和歌山県", "wakayama"),
    "31": ("鳥取県", "tottori"), "32": ("島根県", "shimane"), "33": ("岡山県", "okayama"),
    "34": ("広島県", "hiroshima"), "35": ("山口県", "yamaguchi"), "36": ("徳島県", "tokushima"),
    "37": ("香川県", "kagawa"), "38": ("愛媛県", "ehime"), "39": ("高知県", "kochi"),
    "40": ("福岡県", "fukuoka"), "41": ("佐賀県", "saga"), "42": ("長崎県", "nagasaki"),
    "43": ("熊本県", "kumamoto"), "44": ("大分県", "oita"), "45": ("宮崎県", "miyazaki"),
    "46": ("鹿児島県", "kagoshima"), "47": ("沖縄県", "okinawa"),
}
_ROMAJI_SUFFIX = re.compile(r"[-\s]?(ken|to|fu|prefecture|pref\.?)$")


def split_prefecture(address: str) -> tuple[str | None, str]:
    """Split a free-text address into (prefecture code, rest of the address).

    '愛知県豊田市' -> ('23', '豊田市'); '愛知' -> ('23', ''); 'Tokyo' -> ('13', '');
    '豊田市' -> (None, '豊田市'). A leading postal code ('〒471-0826') is ignored.
    """
    text = strip_postal_code(fold(address))
    if not text:
        return None, ""
    lowered = _ROMAJI_SUFFIX.sub("", text.lower())
    for code, (ja, romaji) in PREFECTURES.items():
        if lowered == romaji:
            return code, ""
    for code, (ja, _) in PREFECTURES.items():
        if text.startswith(ja):
            return code, text[len(ja):]
    for code, (ja, _) in PREFECTURES.items():
        bare = ja[:-1]
        if code == "01" or not text.startswith(bare):
            continue
        rest = text[len(bare):]
        # '愛知豊田市' is Aichi, but '京都市' / '福島区' / '千葉市' are cities, not prefectures.
        if not rest.startswith(("市", "区", "町", "村", "郡")):
            return code, rest
    return None, text


_ADDRESS_MARKS = re.compile(r"(丁目|番地の|番地|番|号)")
_HYPHENS = re.compile(r"[-‐‑‒–—―ー－]")
_KANJI_NUMBER = re.compile(r"([一二三四五六七八九十]+)(?=丁目|番|号)")
_KANJI_DIGITS = {c: i for i, c in enumerate("〇一二三四五六七八九")}


def _kanji_to_int(text: str) -> str:
    """'三' -> '3', '十二' -> '12', '二十' -> '20' (enough for 丁目 / 番 / 号)."""
    if "十" not in text:
        return "".join(str(_KANJI_DIGITS[c]) for c in text)
    tens, _, ones = text.partition("十")
    return str((_KANJI_DIGITS.get(tens, 1) if tens else 1) * 10 + (_KANJI_DIGITS.get(ones, 0) if ones else 0))


_POSTAL_CODE = re.compile(r"^(〒|郵便番号:?)?\d{3}[-‐‑‒–—―ー－]?\d{4}")
_SMALL_KE = re.compile(r"[ヶケがガ]")


def strip_postal_code(folded: str) -> str:
    """'〒471-0826愛知県...' -> '愛知県...' (input already folded: NFKC, no spaces)."""
    return _POSTAL_CODE.sub("", folded)


def fold_address(text: str) -> str:
    """Address form that ignores width, spaces, a leading postal code, kanji numerals, ヶ/ケ/が
    ('霞ヶ関' = '霞が関') and 丁目/番地/号 vs hyphen differences."""
    folded = strip_postal_code(fold(text))
    folded = _SMALL_KE.sub("ケ", folded)
    folded = _KANJI_NUMBER.sub(lambda m: _kanji_to_int(m.group(1)), folded)
    folded = _HYPHENS.sub("-", folded)
    folded = _ADDRESS_MARKS.sub("-", folded)
    # Keep a hyphen only between numbers: '1番地トヨタ会館' -> '1トヨタ会館', '1丁目3番1号' -> '1-3-1'.
    return re.sub(r"-+(?!\d)", "", re.sub(r"-+", "-", folded)).strip("-")
