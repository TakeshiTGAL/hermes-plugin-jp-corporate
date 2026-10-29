"""Tool schemas: what the model reads to decide when and how to call each tool."""

SEARCH = {
    "name": "jp_corp_search",
    "description": (
        "Japan company registry (gBizINFO): find a corporation. "
        "Use it to check a business partner, to look up a 法人番号 (corporate number) from a company "
        "name, or to check the number on an invoice. "
        "Give name to search. Add address to tell same-name companies apart. "
        "Exact matches and registered companies rank first. "
        "Give corporate_number (13 digits; an invoice number such as T1180301018771 also works) to look one "
        "corporation up; add name and/or address too. "
        "Malformed numbers are rejected without any request. "
        "Returns name, head-office address, status and the gBizINFO page URL. status 'registered' means the "
        "registration is not closed, which does not prove the business operates; 'closed' covers "
        "liquidation, merger, and so on. "
        "Corporations only, not sole proprietors, and not an invoice-issuer check. "
        "Zero results do not prove a company does not exist. "
        "gBizINFO is METI's lookup service for Japanese companies. "
        "At 1000 rows, later rows were not read. "
        "Costs at most one API request. Include the attribution line."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Company name or its distinctive part, e.g. 'トヨタ自動車' or '(株)ﾄﾖﾀ自動車'. "
                               "With corporate_number: the name to verify against the official one.",
            },
            "corporate_number": {
                "type": "string",
                "description": "13-digit 法人番号, e.g. '1180301018771'. Hyphens, spaces, full-width digits and "
                               "a leading 'T' (invoice registration number) are accepted.",
            },
            "address": {
                "type": "string",
                "description": "Prefecture and/or municipality to narrow by, e.g. '愛知県', '豊田市', "
                               "'愛知県豊田市', 'Tokyo'. With corporate_number: the address to verify.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (1-50). Default 10.",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
            },
        },
    },
}

PROFILE = {
    "name": "jp_corp_profile",
    "description": (
        "Japan gBizINFO: one company by its corporate number. "
        "The corporate number (法人番号, houjin bangou) has 13 digits; get it from jp_corp_search. "
        "Pick only the sections you need; each section is one API request: "
        "basic (official name, kana, status and close reason, address, representative, capital, employees, "
        "established date, industry, website), subsidy (government subsidies received), procurement "
        "(government contracts won), commendation (government awards), certification (government "
        "registrations/certifications such as DX認定 or 健康経営), finance (sales, profit, assets and major "
        "shareholders from securities reports; listed companies mostly), patent (patents, designs, trademarks), "
        "workplace (mean age, years of service, overtime, women in management, childcare leave), offices "
        "(business sites on employees' pension, with insured headcount). Lists come newest first, with a total. "
        "When you quote representative, capital, or employees, also give gbizinfo_last_updated. "
        "When you show the results, include the attribution line."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "corporate_number": {
                "type": "string",
                "description": "13-digit 法人番号, e.g. '4000012090001'. A leading 'T' is accepted.",
            },
            "sections": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["basic", "subsidy", "procurement", "commendation", "certification",
                             "finance", "patent", "workplace", "offices"],
                },
                "description": "Sections to fetch. Default ['basic'].",
                "default": ["basic"],
            },
            "max_items": {
                "type": "integer",
                "description": "Maximum rows per list section (1-50). Default 10.",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
            },
        },
        "required": ["corporate_number"],
    },
}

ALL_SCHEMAS = [SEARCH, PROFILE]
