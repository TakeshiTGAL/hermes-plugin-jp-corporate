---
name: japan-company
description: "Japan company registry (gBizINFO) and corporate numbers. Before web_search, use tool_search to find jp_corp_search and tool_call it. Do not call tool_describe. If error is token_missing, copy next_step and stop. Do not say jp_corp_profile confirmed a number when that tool was not called. Do not write 取得しました, 確認できます, successfully retrieved, verified, or obtained using. That ban is the same as 取得しました. Do not write a number the result does not contain."
---

For this kind of request, use tool_search to find this plugin's tools before web_search, then call them with tool_call. Write tool_search queries in English (for example: "company registry").

Tools: `jp_corp_search`, `jp_corp_profile`. Include the attribution line.

When the user names a company or a corporate number, call `jp_corp_search` first. Call `jp_corp_profile` with sections `basic` and `finance` only after a corporate number is in a tool result. Do not say `jp_corp_profile` confirmed a corporate number or an address when that tool was not called. Do not write 確認できます. Do not write "successfully retrieved", "verified", or "obtained using". That ban is the same as 取得しました.

From `basic`, report the corporate number, `location`, `industry`, `capital_stock_jpy` with `capital_unit`, and `employees` with `employees_unit`. If `employees_note` is present, the employee count is absent. Do not write 0. Pass `location` to `address_split` and copy prefecture, city, town, `other`, and that tool's attribution. Do not invent a town.

`finance.scope` is `non_consolidated` (提出会社単体). Report `finance.headline`: the same six lines as `edinet_financials`, one block per `years_before_latest`. `found: false` means that line is not in gBizINFO. Do not copy a consolidated figure into it, and do not add the two series. The recorded Toyota note in `results_note` is an example of two different statements and two different fiscal years. Copy each line's `unit` and the gBizINFO URL.

Do not say the company is eligible for a subsidy.

If the tool says `GBIZINFO_API_TOKEN` is not set, the reply is the free-token steps in that message: the application form URL and `GBIZINFO_API_TOKEN`. Do not repeat the user message. Say the basic row and the non-consolidated lines stay empty until that token is set. Do not invent them. Consolidated EDINET rows need a different key and stay empty when that key is unset.
