# Changelog

## 0.1.13

The plugin no longer registers `llm_execution`. A final reply stays as the model wrote it. A tool result with error `token_missing` still sets `next_step` to the same text as `message`.

## 0.1.12

What was understood: a question such as パナソニックの資本金は？, ホンダの従業員数はどれくらい？, or 日産自動車の概要を教えて had no corporate number, no legal-form word, and no recorded registry name, so `pre_llm_call` added nothing. On a small model the reply said no tool could answer, or it repeated the question after `token_missing`. Pytest before this change, on 0.1.11: 124 passed, 2 skipped.

What changed: company talk also includes a katakana or kanji name before の together with a field this plugin returns (資本金, 従業員, 設立, 本社, 代表者, 概要, 事業内容, 法人番号). フィボナッチ数列, グラタン皿, and トヨタの売上 do not match. When the token is unset, the paragraph names the free application form and `GBIZINFO_API_TOKEN`. `llm_execution` replaces a final reply that does not already contain that form URL with the `token_missing` `next_step`, and leaves a tool call in place. Pytest on this commit: 130 passed, 2 skipped.

## 0.1.11

What was understood: company talk treated two katakana characters followed by kanji as a registry name, so フィボナッチ数列 and グラタン皿 received the company paragraph. Pytest before this change, on 0.1.10: 121 passed, 2 skipped.

What changed: company talk is a 13-digit corporate number, the word 法人番号, a legal-form word, a name in the recorded registry table (トヨタ自動車, 大栄精工, グローバルプロダクトプランニング, キヤノン, 任天堂, ソニーグループ), or `jp_corp_search` or `jp_corp_profile` called in the previous turn. A katakana-kanji shape is not a name. ソニー alone is not in the table. The decision is `turn_scope.domains`, copied into this plugin and not imported from another. Pytest on this commit: 120 passed, 6 skipped.

## 0.1.10

What was understood: `pre_llm_call` added the company-search paragraph on every turn, including a settings question. Pytest before this change, on 0.1.9: 120 passed, 2 skipped.

What changed: that paragraph is added only on company talk (a 13-digit corporate number, a legal-form word, a registry-style name such as トヨタ自動車, or a tool name from the six books). Other turns get no extra context. The paragraph text is unchanged. Pytest on this commit: 121 passed, 2 skipped.

## 0.1.9

What was understood: the skill told the model not to say `jp_corp_profile` confirmed a number when that tool was not called. `pre_llm_call` forbade 確認しました. A reply that said "obtained using" and "verified" was outside that ban. Pytest before this change, on 0.1.8: 120 passed, 2 skipped.

What changed: the skill and `pre_llm_call` forbid "successfully retrieved", "verified", and "obtained using" on the same ban as 取得しました. Pytest on this commit: 120 passed, 2 skipped.

## 0.1.8

What was understood: the skill tells the model to find `jp_corp_search` with `tool_search` before web search. `pre_llm_call` said "Do not call tool_describe or tool_search." When the tools are deferred, that sentence blocks the call the skill asks for. Pytest before this change, on 0.1.7: 120 passed, 2 skipped.

What changed: `pre_llm_call` no longer forbids `tool_search`. It still forbids `tool_describe`. It still says to take the company name from the user message and not to pass the word COMPANY. Pytest on this commit: 120 passed, 2 skipped.

## 0.1.7

What was understood: `pre_llm_call` showed `{"name":"COMPANY"}` and told the model to replace COMPANY. On a small model the search argument was the literal COMPANY. Pytest on this commit: 120 passed, 2 skipped.

What changed: `pre_llm_call` no longer shows that argument. It says the company name is the name in the user message, and not to pass the word COMPANY as the name.

## 0.1.6

What was understood: `jp_corp_search` returned `token_missing`, and `next_step` was the same text as `message`. The reply said `jp_corp_profile` could confirm the corporate number and the registered address. That tool had not been called. Pytest on this commit: 116 passed, 6 skipped.

What changed: `pre_llm_call` still tells the model to call `jp_corp_search` with the company name. It also says not to say `jp_corp_profile` confirmed a corporate number or an address when that tool was not called, and not to write 確認できます. `next_step` on `token_missing` is still the same string as `message`.

## 0.1.5

What was understood: on the recorded Toyota finance file `tests/fixtures/hojin_1180301018771_finance.json` (retrieved 2026-10-02, page https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771), the management-index rows carry net sales and a unit reference. Operating income, net income, total assets, net assets, and operating cash flow are absent, so all five are `found: false`. A written note that named only operating income and operating cash flow was narrower than the record. The missing-token reply put the free-token steps in `message` and did not set `next_step`. On a small model the skill body was not opened, `jp_corp_search` was not called, and the reply said the corporate number and address had been confirmed.

What changed: a `token_missing` result sets `next_step` to the same string as `message`. `pre_llm_call` tells the model to call `jp_corp_search` with the company name and, when `token_missing` comes back, to copy `next_step` and stop. The first section names all five `found: false` lines on that Toyota record, plus the sales line 18,259,979,000,000 JPY.

## 0.1.4

What was understood: `jp_corp_profile` section `finance` already returned several years of gBizINFO management-index fields and a note that they are the filing company's non-consolidated figures. The six lines used for a securities-report headline were not labeled, so a missing operating-income or cash-flow line disappeared instead of being reported as absent. Capital and employees on `basic` had no unit. The missing-token reply did not say which rows stay empty.

What changed: `finance.headline` lists revenue, operating income, net income, total assets, net assets, and operating cash flow for each `years_before_latest`, with `found`, `value`, and `unit`. A gBizINFO `unit_ref` of `JPY` is reported as unit `円` and `unit_ref` `JPY`. The numeric value is not rescaled. Lines the record does not contain are `found: false` and are not filled with 0. `basic` adds `capital_unit` (円) and, when the employee count is absent, `employees_note`. The missing-token reply says the basic row and the non-consolidated lines stay empty until the free token is set. The Toyota note now uses the recorded fixtures: non-consolidated net sales 18,259,979,000,000 JPY at years_before_latest 0 (cover page 2026年3月期, retrieved 2026-10-02) and EDINET S100TR7I consolidated operating revenues 45,095,325,000,000 円 (year ended 2024-03-31). The skill tells the model to pass `location` to `address_split` and not to mix the two series.

## 0.1.3

A name search asks gBizINFO for 1000 rows and does not read another page. When that response is full and the local filter matches nothing, the reply names gBizINFO and says that these rows did not contain the match and that later rows are unknown. It says there is no such corporation only when fewer than 1000 rows come back, or when gBizINFO answers 404.

## 0.1.2

The first sentence Tool Search shows now uses the words a person would ask with. A sentence that starts by describing the mechanism is not found, and the model falls through to the built-in web_search.

Adds the `japan-company` skill. It tells the model to find the gBizINFO tools with tool_search before web_search. It does not set requires_toolsets, so it stays in the model's skill list when Tool Search is left at its default, which hides this plugin's tools.

limit and max_items written as 10.0 or fullwidth digits are accepted. A hyphen in a corporate number, a prefecture written without 県, and sections in any letter case were already accepted, and tests now check them. Extra arguments, and a limit or max_items outside 1 to 50, are refused with a fix and an example; a number outside the range used to be clamped. Error text no longer copies the caller's value. Input errors add `ok: false` and `error_type`.

## 0.1.1

`GBIZINFO_API_TOKEN` was read from `os.environ` on each request and when checking whether a token is configured. One Hermes process can serve more than one profile, so that read can use another profile's token. Each call now reads it with `agent.secret_scope.get_secret`. An HTTP proxy set in the environment is not used for gBizINFO requests, so a machine that can reach the network only through that proxy can no longer reach the API. Each profile needs its own `GBIZINFO_API_TOKEN` in that profile's `.env` (`~/.hermes/.env` for the default profile, `~/.hermes/profiles/<name>/.env` for a named profile). Tool results and error text do not include the token value. `plugin.yaml` now declares `requires_hermes: >=0.21.4`, the floor the catalog entry already had. Installing this repository on Hermes older than 0.21.4 now fails that check; catalog installs were already held to the same floor. This version is tested on Hermes 0.21.4 and later.
