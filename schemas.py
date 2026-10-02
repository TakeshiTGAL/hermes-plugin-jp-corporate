"""Tool schemas: what the model reads to decide when and how to call each tool."""

SEARCH = {
    "name": "jp_corp_search",
    "description": (
        "Find a Japanese corporation in gBizINFO (Ministry of Economy, Trade and Industry) and confirm it is "
        "registered. Use it to check a business partner, to look up a 法人番号 (corporate number) from a company "
        "name, or to check the number on an invoice. "
        "Give name to search (partial match; 株式会社/(株)/㈱, half-width kana and full-width letters are "
        "handled, e.g. '(株)ﾄﾖﾀ自動車' finds トヨタ自動車株式会社); add address (prefecture and/or city, e.g. "
        "'愛知県豊田市') to tell same-name companies apart. Results are ranked exact match first, registered "
        "before closed. "
        "Give corporate_number (13 digits; an invoice number such as T1180301018771 also works) to look one "
        "corporation up; add name and/or address too and the result says whether they match the official "
        "record. Malformed numbers are rejected without any request. "
        "Returns name, head-office address, status and the gBizINFO page URL. status 'registered' means the "
        "registration is not closed; it does not prove the business is operating. 'closed' means the "
        "registration was closed (liquidation, merger, ...). "
        "Limits: covers corporations only (not sole proprietors); 0 results is not proof that a company does "
        "not exist; it does not check qualified-invoice-issuer (適格請求書発行事業者) registration. "
        "Costs at most one API request. When you show the results, include the attribution line."
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
        "Get gBizINFO details for one Japanese corporation by its 13-digit 法人番号 (find the number with "
        "jp_corp_search first). Pick only the sections you need; each section is one API request: "
        "basic (official name, kana, status and close reason, address, representative, capital, employees, "
        "established date, industry, website), subsidy (government subsidies received), procurement "
        "(government contracts won), commendation (government awards), certification (government "
        "registrations/certifications such as DX認定 or 健康経営), finance (sales, profit, assets and major "
        "shareholders from securities reports; listed companies mostly), patent (patents, designs, trademarks), "
        "workplace (average age, years of service, overtime, women in management, childcare leave), offices "
        "(business sites enrolled in employees' pension and health insurance, with insured headcount). Lists are newest first with a total count. "
        "Representative, capital and employee counts can be years old: when you quote them, also give "
        "gbizinfo_last_updated (a freshness_note appears when the record is over a year old). "
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
