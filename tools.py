"""Tool handlers for jp_corp_search and jp_corp_profile.

`search` and `profile` hold the logic: they take the model's arguments, raise
InputError / ApiError on a problem, and return a JSON-ready dict. `_as_handler`
wraps them in the Hermes handler contract (always return a JSON string, never
raise).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from . import client
from .normalize import (
    InputError,
    PREFECTURES,
    core_name,
    fold,
    fold_address,
    full_name,
    parse_corporate_number,
    query_term,
    split_prefecture,
)

SEARCH_FETCH_LIMIT = 1000  # rows asked from gBizINFO per name search (one request)
DEFAULT_RESULTS = 10
MAX_RESULTS = 50
DEFAULT_ITEMS = 10
MAX_ITEMS = 50
GBIZINFO_TOP = "https://info.gbiz.go.jp/"
JST = timezone(timedelta(hours=9))

# Section name -> path suffix under /v2/hojin/{number}. "basic" is the number itself.
SECTIONS = {
    "basic": "",
    "subsidy": "subsidy",
    "procurement": "procurement",
    "commendation": "commendation",
    "certification": "certification",
    "finance": "finance",
    "patent": "patent",
    "workplace": "workplace",
    "offices": "corporation",
}

KIND_LABELS = {
    "101": "国の機関 (national government body)",
    "201": "地方公共団体 (local government)",
    "301": "株式会社 (kabushiki kaisha)",
    "302": "有限会社 (yugen kaisha)",
    "303": "合名会社 (general partnership company)",
    "304": "合資会社 (limited partnership company)",
    "305": "合同会社 (godo kaisha / LLC)",
    "399": "その他の設立登記法人 (other registered corporation)",
    "401": "外国会社等 (foreign company)",
    "499": "その他 (other)",
}
CLOSE_CAUSES = {
    "01": "清算の結了等 (liquidation completed)",
    "11": "合併による解散等 (dissolved by merger)",
    "21": "登記官による閉鎖 (closed by the registrar)",
    "31": "その他の清算の結了等 (other liquidation)",
}
INDUSTRY_LABELS = {
    "A": "農業，林業", "B": "漁業", "C": "鉱業，採石業，砂利採取業", "D": "建設業", "E": "製造業",
    "F": "電気・ガス・熱供給・水道業", "G": "情報通信業", "H": "運輸業，郵便業", "I": "卸売業，小売業",
    "J": "金融業，保険業", "K": "不動産業，物品賃貸業", "L": "学術研究，専門・技術サービス業",
    "M": "宿泊業，飲食サービス業", "N": "生活関連サービス業，娯楽業", "O": "教育，学習支援業",
    "P": "医療，福祉", "Q": "複合サービス事業", "R": "サービス業（他に分類されないもの）", "S": "公務",
    "T": "分類不能の産業",
}


# --- Shared helpers ---------------------------------------------------------------

def page_url(number: str) -> str:
    return f"https://info.gbiz.go.jp/hojin/ichiran?hojinBango={number}"


def attribution(url: str) -> dict:
    """Credit line in the form the gBizINFO terms of use ask for (出典の記載 + 加工の旨 + 利用日)."""
    today = datetime.now(JST).date()
    return {
        "ja": f"出典：「Gビズインフォ」（経済産業省）（{url}）を加工して作成（{today.year}年{today.month}月{today.day}日に利用）",
        "en": (
            f"Source: gBizINFO (Ministry of Economy, Trade and Industry, Japan), {url}, "
            f"retrieved {today.isoformat()}; reformatted by the jp-corporate plugin."
        ),
    }


def _compact(value):
    """Drop None, empty strings and empty containers, recursively."""
    if isinstance(value, dict):
        out = {k: _compact(v) for k, v in value.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [v for v in (_compact(v) for v in value) if v not in (None, "", [], {})]
    return value


def _date(value) -> str | None:
    return str(value)[:10] if value else None


def _int(value):
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").replace(",", "").strip()
    return int(text) if text.isdigit() else (text or None)


def _postal(value) -> str | None:
    text = str(value or "")
    return f"{text[:3]}-{text[3:]}" if len(text) == 7 and text.isdigit() else (text or None)


def _status(value) -> str:
    # gBizINFO only says whether the registration is closed ("閉鎖") or not ("-").
    # "registered" does not prove that the business is operating.
    return "closed" if value and value != "-" else "registered"


def _clean_text(value) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s*\n\s*", " / ", str(value)).strip() or None


def _representative(value) -> str | None:
    """'代表取締役    山  田  太  郎' -> '代表取締役 山田太郎' (the source pads characters with spaces)."""
    if not value:
        return None
    text = re.sub(r"\s{3,}", "\t", str(value).strip())
    text = re.sub(r"(?<=\S)\s{2}(?=\S)", "", text)
    return re.sub(r"\s+", " ", text.replace("\t", " ")).strip()


def _first(data: dict) -> dict:
    infos = data.get("hojin-infos") or []
    return infos[0] if infos else {}


def _clamp(value, default: int, upper: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(upper, number))


# --- jp_corp_search ----------------------------------------------------------------

def _summary(info: dict, match: str | None = None) -> dict:
    number = info.get("corporate_number")
    return _compact({
        "corporate_number": number,
        "name": info.get("name"),
        "location": info.get("location"),
        "postal_code": _postal(info.get("postal_code")),
        "status": _status(info.get("status")),
        "match": match,
        "gbizinfo_url": page_url(number) if number else None,
    })


def _name_check(given: str, official: str) -> str:
    if full_name(given) == full_name(official):
        return "match"
    if core_name(given) == core_name(official):
        return "match_except_legal_form"
    return "mismatch"


def _address_check(given: str, official: str) -> str:
    """Compare an address from a document with the registered head-office address.

    match: same address (a building or floor added after the lot number is ignored).
    partial: the given address stops early (e.g. only the prefecture and city, or no lot number).
    more_detailed: the given address continues the registered one with a sub-number (1番地 vs 1-1).
    same_municipality_different_street / mismatch: otherwise.
    Lot numbers are compared whole, so トヨタ町1番地 does not match トヨタ町10番地.
    """
    pref_given, rest_given = split_prefecture(given)
    pref_official, rest_official = split_prefecture(official)
    if pref_given and pref_official and pref_given != pref_official:
        return "mismatch"
    a, b = fold_address(rest_given), fold_address(rest_official)
    if not a:
        return "partial"  # only a prefecture and/or a postal code was given
    if a == b:
        return "match"
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    if b and longer.startswith(shorter):
        tail = longer[len(shorter):]
        if shorter[-1].isdigit() and tail[0].isdigit():
            pass  # 1 vs 10: different lot numbers
        elif shorter[-1].isdigit() and tail[0] != "-":
            return "match"  # only a building / floor name follows the lot number
        elif shorter is a:
            return "partial"
        elif tail[0] == "-":
            return "more_detailed"  # the document adds a sub-number the registry does not have
    city_a = re.match(r".+?[市区町村]", a)
    city_b = re.match(r".+?[市区町村]", b)
    if city_a and city_b and city_a.group(0) == city_b.group(0):
        return "same_municipality_different_street"
    return "mismatch"


def _lookup_number(raw_number: str, name: str, address: str) -> dict:
    number = parse_corporate_number(raw_number)
    try:
        info = _first(client.get(number))
    except client.NotFound:
        info = {}
    if not info:
        return {
            "found": 0,
            "corporate_number": number,
            "message": (
                f"{number} is a well-formed 法人番号 (check digit OK), but gBizINFO has no corporation with it. "
                "Possible reasons: the number was mistyped in a way the check digit cannot catch; the entity is "
                "newly registered and not yet in gBizINFO; or it came from an invoice (T-number) of a sole "
                "proprietor, whose registration numbers are not 法人番号. Check invoice numbers at "
                "https://www.invoice-kohyo.nta.go.jp/ ."
            ),
            "attribution": attribution(GBIZINFO_TOP),
        }
    result = {"found": 1, "results": [_summary(info, "corporate_number")]}
    checks = {}
    if name:
        checks["name"] = _name_check(name, info.get("name") or "")
    if address:
        checks["address"] = _address_check(address, info.get("location") or "")
    if checks:
        result["checks"] = checks
        result["checks_note"] = (
            "name: match = same after ignoring width, spaces and (株)/㈱ vs 株式会社; match_except_legal_form = "
            "same name but the legal form or its position differs (e.g. (株)X vs X株式会社). "
            "address: match = same address (building names after the lot number ignored); partial = the given "
            "address stops early (e.g. city only), so confirm the rest; more_detailed = the given address adds a "
            "sub-number to the registered one (1番地 vs 1-1), usually the same place; "
            "same_municipality_different_street; mismatch. "
            "This checks the corporation behind the number, not qualified-invoice-issuer registration "
            "(check that at https://www.invoice-kohyo.nta.go.jp/)."
        )
    if _status(info.get("status")) == "closed":
        result["warning"] = (
            f"This corporation's registration is closed ({info.get('close_date') or 'date unknown'}). "
            "Call jp_corp_profile for the reason."
        )
    result["attribution"] = attribution(page_url(number))
    return result


def search(args: dict) -> dict:
    name = str(args.get("name") or "").strip()
    number = str(args.get("corporate_number") or "").strip()
    address = str(args.get("address") or "").strip()
    limit = _clamp(args.get("limit"), DEFAULT_RESULTS, MAX_RESULTS)

    if number:
        return _lookup_number(number, name, address)
    if not name:
        raise InputError("Give a company name (name) or a 13-digit 法人番号 (corporate_number).")

    term = query_term(name)
    wanted = core_name(name)
    if not term or not wanted:
        raise InputError(
            f"name {name!r} has nothing left after removing the legal form (株式会社, (株), ...). "
            "Include the distinctive part of the name, e.g. トヨタ自動車."
        )
    prefecture, street = split_prefecture(address) if address else (None, "")
    params = {"name": term, "limit": SEARCH_FETCH_LIMIT}
    if prefecture:
        params["prefecture"] = prefecture
    query = _compact({
        "name": name,
        "searched_as": term,
        "address": address or None,
        "prefecture": PREFECTURES[prefecture][0] if prefecture else None,
    })

    try:
        rows = client.get("", params).get("hojin-infos") or []
    except client.NotFound:
        rows = []
    fetched = len(rows)

    wanted_full = full_name(name)
    gave_form = wanted_full != wanted
    street_key = fold_address(street)
    ranked = []
    for info in rows:
        official = info.get("name") or ""
        if wanted not in core_name(official) and wanted not in fold(official):
            continue  # multi-word input: the API matched one word, the full name is not there
        if street_key and street_key not in fold_address(info.get("location") or ""):
            continue
        official_core = core_name(official)
        rank = 0 if official_core == wanted else 1 if official_core.startswith(wanted) else 2
        form_differs = gave_form and full_name(official) != wanted_full
        closed = _status(info.get("status")) == "closed"
        ranked.append(((rank, closed, form_differs, len(official), info.get("corporate_number") or ""), info, rank))
    ranked.sort(key=lambda item: item[0])

    result = {"query": query, "found": len(ranked)}
    if not ranked:
        hints = [
            "Try a shorter distinctive part of the name (e.g. drop 本店, ホールディングス or a branch name).",
            "Try the other script: katakana vs kanji vs alphabet (e.g. ソニー / SONY).",
        ]
        if fetched:
            hints.insert(0, f"{fetched} corporations match the name, but none at '{address}'. Check the address, "
                            "or search again without it.")
        elif address:
            hints.append("Search again without the address.")
        result["message"] = f"0 results: gBizINFO has no corporation whose name contains '{term}'" + (
            f" in {query['prefecture']}" if prefecture and not fetched else "") + "."
        result["next_steps"] = hints
        result["attribution"] = attribution(GBIZINFO_TOP)
        return result

    labels = {0: "exact", 1: "starts_with", 2: "contains"}
    result["shown"] = min(limit, len(ranked))
    result["results"] = [_summary(info, labels[rank]) for _, info, rank in ranked[:limit]]
    notes = []
    if len(ranked) > limit:
        notes.append(f"{len(ranked) - limit} more not shown. Add address (prefecture or city) to narrow, or raise limit.")
    if fetched >= SEARCH_FETCH_LIMIT:
        notes.append(f"gBizINFO returned its first {SEARCH_FETCH_LIMIT} rows only; the name is very common, "
                     "so add address to be sure the right company is included.")
    if sum(1 for _, _, rank in ranked if rank == 0) > 1:
        notes.append("Several corporations share this exact name: tell them apart by location and status.")
    if notes:
        result["note"] = " ".join(notes)
    result["attribution"] = attribution(GBIZINFO_TOP)
    return result


# --- jp_corp_profile ---------------------------------------------------------------

def _by_date(items: list, key: str) -> list:
    return sorted(items, key=lambda item: item.get(key) or "", reverse=True)


def _basic(info: dict) -> dict:
    industry = [f"{code} {INDUSTRY_LABELS[code]}" if code in INDUSTRY_LABELS else code
                for code in info.get("industry") or []]
    closed = _status(info.get("status")) == "closed"
    return _compact({
        "name": info.get("name"),
        "kana": info.get("kana"),
        "name_en": info.get("name_en"),
        "kind": KIND_LABELS.get(str(info.get("kind")), info.get("kind")),
        "status": "closed" if closed else "registered",
        "closed_on": _date(info.get("close_date")),
        "close_reason": CLOSE_CAUSES.get(str(info.get("close_cause")), info.get("close_cause")),
        "location": info.get("location"),
        "postal_code": _postal(info.get("postal_code")),
        "representative": _representative(info.get("representative_name")),
        "capital_stock_jpy": info.get("capital_stock"),
        "employees": info.get("employee_number"),
        "established": _date(info.get("date_of_establishment")),
        "founding_year": info.get("founding_year"),
        "business_summary": info.get("business_summary"),
        "website": info.get("company_url"),
        "industry": industry,
        "national_procurement_grade": info.get("qualification_grade"),
        "gbizinfo_last_updated": _date(info.get("update_date")),
        "freshness_note": _freshness(info.get("update_date")),
    })


def _freshness(update_date) -> str | None:
    updated = _date(update_date)
    if not updated:
        return None
    try:
        age_days = (datetime.now(JST).date() - datetime.strptime(updated, "%Y-%m-%d").date()).days
    except ValueError:
        return None
    if age_days < 365:
        return None
    return (f"Representative, capital and employee figures are as of {updated} and may be out of date; "
            "name, address and closure status come from the National Tax Agency's corporate-number data, "
            "which gBizINFO imports daily.")


def _listed(items: list, max_items: int, shape, date_key: str | None) -> dict:
    shaped = [shape(item) for item in items]
    if date_key:
        shaped = _by_date(shaped, date_key)
    return {"total": len(shaped), "items": _compact(shaped[:max_items])}


def _subsidy(item: dict) -> dict:
    return {"date": _date(item.get("date_of_approval")), "title": _clean_text(item.get("title")),
            "amount_jpy": _int(item.get("amount")), "target": item.get("target"),
            "ministry": item.get("government_departments")}


def _procurement(item: dict) -> dict:
    return {"date": _date(item.get("date_of_order")), "title": _clean_text(item.get("title")),
            "amount_jpy": _int(item.get("amount")), "ordered_by": item.get("government_departments"),
            "note": item.get("note")}


def _commendation(item: dict) -> dict:
    return {"date": _date(item.get("date_of_commendation")), "title": _clean_text(item.get("title")),
            "category": item.get("category"), "target": item.get("target"),
            "ministry": item.get("government_departments"), "note": item.get("note")}


def _certification(item: dict) -> dict:
    return {"date": _date(item.get("date_of_approval")), "title": _clean_text(item.get("title")),
            "category": item.get("category"), "target": item.get("target"),
            "ministry": item.get("government_departments")}


_FINANCE_FIELDS = {
    "net_sales_jpy": "net_sales_summary_of_business_results",
    "operating_revenue_jpy": "operating_revenue1_summary_of_business_results",
    "operating_receipts_jpy": "operating_revenue2_summary_of_business_results",
    "gross_operating_revenue_jpy": "gross_operating_revenue_summary_of_business_results",
    "ordinary_revenue_jpy": "ordinary_income_summary_of_business_results",
    "ordinary_profit_jpy": "ordinary_income_loss_summary_of_business_results",
    "net_income_jpy": "net_income_loss_summary_of_business_results",
    "net_premiums_written_jpy": "net_premiums_written_summary_of_business_results_ins",
    "total_assets_jpy": "total_assets_summary_of_business_results",
    "net_assets_jpy": "net_assets_summary_of_business_results",
    "capital_stock_jpy": "capital_stock_summary_of_business_results",
    "employees": "number_of_employees",
}


def _finance(finance: dict, max_items: int) -> dict:
    if not finance:
        return {"total": 0, "items": []}
    years = []
    for row in finance.get("management_index") or []:
        entry = {"years_before_latest": _int(row.get("period"))}
        for out_key, key in _FINANCE_FIELDS.items():
            entry[out_key] = row.get(key)
        years.append(entry)
    years.sort(key=lambda e: e["years_before_latest"] if isinstance(e["years_before_latest"], int) else 99)
    holders = sorted(finance.get("major_shareholders") or [],
                     key=lambda h: h.get("shareholding_ratio") or 0, reverse=True)
    return _compact({
        "fiscal_year": _clean_text(finance.get("fiscal_year_cover_page")),
        "accounting_standards": finance.get("accounting_standards"),
        "results_by_year": years,
        "results_note": "Non-consolidated figures of the filing company only (提出会社単体, from 「提出会社の経営指標等"
                        "の推移」 in the securities report), not the consolidated group: e.g. Toyota's net sales here are "
                        "about 18 trillion yen, while its consolidated revenue is about 48 trillion yen. "
                        "years_before_latest 0 is the fiscal year above, 1 the year before it, and so on.",
        "major_shareholders": [
            {"name": h.get("name_major_shareholders"),
             "share_pct": round(h["shareholding_ratio"] * 100, 2) if isinstance(h.get("shareholding_ratio"), (int, float)) else None}
            for h in holders[:max_items]
        ],
    })


def _workplace(info: dict) -> dict:
    base = info.get("base_infos") or {}
    women = info.get("women_activity_infos") or {}
    childcare = info.get("compatibility_of_childcare_and_work") or {}
    return _compact({
        "average_age": base.get("average_age"),
        "average_years_of_service": base.get("average_continuous_service_years"),
        "average_years_of_service_male": base.get("average_continuous_service_years_Male"),
        "average_years_of_service_female": base.get("average_continuous_service_years_Female"),
        "years_of_service_scope": base.get("average_continuous_service_years_type"),
        "monthly_overtime_hours": base.get("month_average_predetermined_overtime_hours"),
        "female_worker_pct": women.get("female_workers_proportion"),
        "female_worker_pct_scope": women.get("female_workers_proportion_type"),
        "managers_female": women.get("female_share_of_manager"),
        "managers_total": women.get("gender_total_of_manager"),
        "officers_female": women.get("female_share_of_officers"),
        "officers_total": women.get("gender_total_of_officers"),
        "childcare_leave_eligible_male": childcare.get("number_of_paternity_leave"),
        "childcare_leave_taken_male": childcare.get("paternity_leave_acquisition_num"),
        "childcare_leave_eligible_female": childcare.get("number_of_maternity_leave"),
        "childcare_leave_taken_female": childcare.get("maternity_leave_acquisition_num"),
    })


def _patents(items: list, max_items: int) -> dict:
    # gBizINFO repeats a patent once per classification code; keep one row per registration.
    unique = {}
    for item in items:
        key = (item.get("patent_type"), item.get("registration_number"), item.get("title"))
        unique.setdefault(key, {"type": item.get("patent_type"), "registration_number": item.get("registration_number"),
                                "application_date": _date(item.get("application_date")),
                                "title": _clean_text(item.get("title")), "url": item.get("url")})
    return _listed(list(unique.values()), max_items, lambda x: x, "application_date")


def _office(item: dict) -> dict:
    return {"name": re.sub(r"\s+", " ", item.get("corporation_name") or "").strip() or None,
            "location": re.sub(r"\s+", " ", item.get("corporation_location") or "").strip() or None,
            "insured_employees": _int(item.get("insured_number")),
            "closed_on": _date(item.get("loss_date"))}


def _section(section: str, info: dict, max_items: int):
    if section == "basic":
        return _basic(info)
    if section == "subsidy":
        return _listed(info.get("subsidy") or [], max_items, _subsidy, "date")
    if section == "procurement":
        return _listed(info.get("procurement") or [], max_items, _procurement, "date")
    if section == "commendation":
        return _listed(info.get("commendation") or [], max_items, _commendation, "date")
    if section == "certification":
        return _listed(info.get("certification") or [], max_items, _certification, "date")
    if section == "finance":
        return _finance(info.get("finance") or {}, max_items)
    if section == "patent":
        return _patents(info.get("patent") or [], max_items)
    if section == "workplace":
        return _workplace(info.get("workplace_info") or {})
    if section == "offices":
        return _listed(info.get("corporation-info") or [], max_items, _office, None)
    raise InputError(f"unknown section {section!r}")


def profile(args: dict) -> dict:
    number = parse_corporate_number(args.get("corporate_number"))
    raw_sections = args.get("sections") or ["basic"]
    if isinstance(raw_sections, str):
        raw_sections = [s for s in re.split(r"[,\s]+", raw_sections) if s]
    sections = []
    for section in raw_sections:
        key = str(section).strip().lower()
        if key not in SECTIONS:
            raise InputError(f"unknown section {section!r}. Choose from: {', '.join(SECTIONS)}.")
        if key not in sections:
            sections.append(key)
    max_items = _clamp(args.get("max_items"), DEFAULT_ITEMS, MAX_ITEMS)

    header, out = {}, {}
    for section in sections:
        suffix = SECTIONS[section]
        try:
            info = _first(client.get(f"{number}/{suffix}" if suffix else number))
        except client.NotFound:
            info = {}
        if not info and section == "basic":
            return {
                "found": 0,
                "corporate_number": number,
                "message": f"gBizINFO has no corporation with 法人番号 {number} (the number itself is well-formed). "
                           "Check the number, or find the company by name with jp_corp_search.",
                "attribution": attribution(GBIZINFO_TOP),
            }
        if info and not header:
            header = {"name": info.get("name"), "location": info.get("location")}
        out[section] = _section(section, info, max_items) if info else {"total": 0, "items": []}

    result = _compact({"corporate_number": number, **header, "gbizinfo_url": page_url(number)})
    if not header:
        result["message"] = ("gBizINFO returned no data for this number in the requested sections. "
                             "Add 'basic' to sections to confirm the corporation exists.")
    result["sections"] = out
    result["attribution"] = attribution(page_url(number))
    return result


# --- Hermes handler contract ---------------------------------------------------------

def _as_handler(fn):
    def handler(args: dict, **kwargs) -> str:
        client.reset_request_count()
        try:
            result = fn(args or {})
        except InputError as error:
            result = {"error": "input", "message": str(error)}
        except client.ApiError as error:
            result = {"error": "api" if client.token_configured() else "token_missing", "message": str(error)}
            if error.status:
                result["http_status"] = error.status
        except Exception as error:  # never raise into the agent loop
            result = {"error": "internal", "message": f"{type(error).__name__}: {error}. Please report this at "
                                                       "https://github.com/TakeshiTGAL/hermes-plugin-jp-corporate/issues"}
        result["api_requests"] = client.request_count()
        return json.dumps(result, ensure_ascii=False)

    handler.__name__ = fn.__name__
    return handler


HANDLERS = {
    "jp_corp_search": _as_handler(search),
    "jp_corp_profile": _as_handler(profile),
}
