# jp-corporate (法人照会) for Hermes Agent

Look up Japanese corporations from [Hermes Agent](https://hermes-agent.nousresearch.com): check that a business partner is a registered corporation and whether its registration has been closed, find a company's corporate number (法人番号), check the number on an invoice against the company name and address, and see its record of government subsidies, contracts, awards, certifications, financials, patents and workplace data.

Data comes from [gBizINFO](https://info.gbiz.go.jp/) (Gビズインフォ), the free corporate-information service of Japan's Ministry of Economy, Trade and Industry. You need your own free gBizINFO API token (see [Get a token](#get-a-gbizinfo-token)).

> 日本語の説明は [下にあります](#日本語)。

## Install

1. Install and enable. Hermes asks for `GBIZINFO_API_TOKEN` and saves it to `~/.hermes/.env`:

   ```bash
   hermes plugins install TakeshiTGAL/hermes-plugin-jp-corporate --enable
   ```

   Once the plugin is listed in the Hermes plugin catalog, `hermes plugins install jp-corporate --enable` works too. To try a local copy instead, run `hermes plugins install "file://$PWD" --enable` inside a clone of this repository.

2. Paste your gBizINFO token at the prompt (or add `GBIZINFO_API_TOKEN=...` to `~/.hermes/.env` later), then restart Hermes.

3. Ask:

   ```text
   法人番号 1180301018771 の会社を調べて。名前と所在地、登記が閉鎖されていないかも
   ```

## What to ask

- "What is the corporate number of (株)トヨタ自動車 in Aichi, and is its registration still open?"
- "請求書にある登録番号 T1180301018771 と社名「トヨタ自動車(株)」、住所「愛知県豊田市トヨタ町1番地」は一致している？"
- "「〇〇商事」という会社は何社ある？ 大阪府にあるものだけ所在地つきで並べて"
- "トヨタ自動車の官公庁からの受注実績と認定を見せて"
- "Show the government contracts and certifications of corporate number 1180301018771."

## Tools

| Tool | Use it for | API requests |
|---|---|---|
| `jp_corp_search` | Find a corporation by **name** (+ optional **address**), or look one up by **corporate_number** and check a name/address against the official record | at most 1 |
| `jp_corp_profile` | Details for one corporate number. Choose **sections**: `basic`, `subsidy`, `procurement`, `commendation`, `certification`, `finance`, `patent`, `workplace`, `offices` | 1 per section |

Both tools are read-only. A typical question takes one or two calls: search, then profile. Every result reports `api_requests`, the number of requests actually sent (repeats within 10 minutes are answered from memory and count 0).

### `jp_corp_search`

| Argument | Example | Notes |
|---|---|---|
| `name` | `ﾄﾖﾀ自動車`, `(株)トヨタ自動車` | Partial match. `株式会社` / `(株)` / `㈱` / `有限会社` and similar words, half-width kana, full-width letters and spaces are all handled. |
| `address` | `愛知県`, `豊田市`, `愛知県豊田市`, `Tokyo` | Separates companies with the same name. The prefecture goes to gBizINFO as a filter; the rest is matched against the head-office address. |
| `corporate_number` | `1180301018771`, `T1180301018771`, `1180-3010-18771` | 13 digits. The check digit is verified **before** any request, so a mistyped number is reported as an input error without using the API. |
| `limit` | `10` | 1–50 results. |

Results come back ranked: exact name match first, then names that start with the query, then names that contain it; registered corporations before closed ones.

```json
{"query": {"name": "ﾄﾖﾀ自動車", "searched_as": "トヨタ自動車"}, "found": 81, "shown": 3,
 "results": [{"corporate_number": "1180301018771", "name": "トヨタ自動車株式会社",
   "location": "愛知県豊田市トヨタ町１番地", "postal_code": "471-0826", "status": "registered",
   "match": "exact", "gbizinfo_url": "https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771"}, "..."],
 "note": "78 more not shown. Add address (prefecture or city) to narrow, or raise limit.",
 "attribution": {"ja": "出典：「Gビズインフォ」（経済産業省）（https://info.gbiz.go.jp/）を加工して作成（2026年10月2日に利用）", "en": "..."},
 "api_requests": 1}
```

`status` is `registered` (the registration is not closed) or `closed` (closed by liquidation, merger and so on; `jp_corp_profile` gives the date and reason). `registered` does not prove that the business is operating.

**Invoice check.** Pass `corporate_number` together with the `name` and/or `address` printed on the invoice. The result includes `checks`:

```json
"checks": {"name": "match", "address": "match"}
```

- `name`: `match` (same after ignoring width, spaces and `(株)` vs `株式会社`), `match_except_legal_form` (same name, but the legal form or its position differs, e.g. `(株)X` vs `X株式会社`) or `mismatch`.
- `address`: `match` (same address; a building name after the lot number is ignored), `partial` (the given address stops early, e.g. city only), `more_detailed` (the given address adds a sub-number, e.g. `1-1` where the registry has `1番地`), `same_municipality_different_street` or `mismatch`. Lot numbers are compared whole, so `トヨタ町1番地` does not match `トヨタ町10番地`; `1丁目3番1号`, `一丁目3-1` and `1-3-1` are treated alike, as are `霞ヶ関` and `霞が関`. A leading postal code (`〒471-0826`) is ignored.
- A closed corporation gets a `warning`.

This confirms the corporation behind the number. Whether it is a registered qualified invoice issuer (適格請求書発行事業者) is a separate register: check <https://www.invoice-kohyo.nta.go.jp/>.

### `jp_corp_profile`

| Section | Contents |
|---|---|
| `basic` (default) | Official name, kana, English name, legal form, registered/closed (with date and reason), address, representative, capital, employees, date of establishment, industry, website |
| `subsidy` | Government subsidies received: date, title, amount, ministry |
| `procurement` | Government contracts won: date, title, amount, ordering body |
| `commendation` | Government awards |
| `certification` | Government registrations and certifications (e.g. ＤＸ認定制度, national procurement qualification) |
| `finance` | Net sales, ordinary profit, net income, assets and major shareholders from securities reports (mostly listed companies). Figures are for the filing company alone (提出会社単体, non-consolidated), not the group |
| `patent` | Patents, designs and trademarks (one row per registration) |
| `workplace` | Average age, years of service, overtime, women in management, childcare leave |
| `offices` | Business sites enrolled in employees' pension and health insurance (厚生年金・健康保険の適用事業所), with the number of insured people |

Lists are newest first and capped by `max_items` (default 10, up to 50); each list also reports its `total`.

## Get a gBizINFO token

The token is free. It is issued to you, for the purpose you state.

1. Open the application form: <https://info.gbiz.go.jp/hojin/various_registration/form>
2. 利用者区分 (user type): **法人担当者の方** if you use the data for your company's work (then enter your company's corporate number, department and address), otherwise **個人利用者の方**.
3. 申請区分: **トークン利用(WebAPI・データダウンロード)**.
4. 利用目的 (purpose), pick what matches how you will use this plugin:
   - Checking your own business partners or invoices: **社内業務改善（自社分析、自社システムへの組み込み）**
   - Personal use: **個人利用（趣味・教育）**
   - Offering it to other people, for example through a Hermes gateway bot that others can talk to: **サービス利用（サービス開発・プロダクトへの組み込み）**
5. 利用予定 (planned use): say how you will call it, for example "Hermes Agent から取引先の確認のため手動で照会。1日数十件程度。"
6. Agree to the API terms and the privacy policy, submit, and open the link in the 「Web API 利用申請完了」 email. The token is shown on that page.

**Apply once and keep using that token.** The gBizINFO API terms forbid obtaining or using several tokens to get around usage limits, and allow use only for the purpose you declared. If a token stops working, contact gBizINFO (<https://help.info.gbiz.go.jp/hc/ja/requests/new>) instead of applying again.

## Credit the source

gBizINFO's terms of use require a source credit, plus a note when the data has been edited. Every successful result carries an `attribution` field in that form, with the gBizINFO page of the corporation and the date:

```text
出典：「Gビズインフォ」（経済産業省）（https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771）を加工して作成（2026年10月2日に利用）
```

The tool descriptions ask the agent to include this line whenever it shows results. Keep it when you paste results into documents.

## Fair use, built in

gBizINFO is a public service; its terms let it suspend tokens that send excessive requests. The plugin keeps usage low:

- At most one request per search and one per profile section. It never pages through results on its own and never retries in a loop.
- Requests are spaced at least 0.5 s apart, and identical requests within 10 minutes are answered from memory.
- Malformed corporate numbers are rejected before any request.

For bulk data, use gBizINFO's [download files](https://info.gbiz.go.jp/hojin/DownloadTop) instead of this plugin.

## When something goes wrong

| What you see | What to do |
|---|---|
| `token_missing` | Apply for a token (above), add `GBIZINFO_API_TOKEN=...` to `~/.hermes/.env`, restart Hermes. |
| `401` | The token is wrong. Copy it again from the page linked in the 「Web API 利用申請完了」 email, without quotes or spaces. |
| `found: 0` | The message suggests what to try: a shorter or differently written name, or no address filter. A well-formed number that is not found may be a sole proprietor's invoice number; check <https://www.invoice-kohyo.nta.go.jp/>. |
| `403` / `429` | gBizINFO is limiting requests. Wait several minutes; do not loop. |
| `input` | The argument is wrong (e.g. 12 digits, failed check digit, unknown section). The message says what to fix. No request was sent. |
| `3xx` (redirect) | The API address may have changed. The redirect was not followed, so the token went nowhere else. Update the plugin. |
| network error / `500` | Check the connection and try again later; maintenance is announced at <https://info.gbiz.go.jp/>. |

## Limits of the data

- Name, address and closure status come from the National Tax Agency's corporate-number data, which gBizINFO imports daily ([gBizINFO: data sources](https://help.info.gbiz.go.jp/hc/ja/articles/4795050523806)). Representative, capital and employee counts can be years old; `gbizinfo_last_updated` shows the date and a `freshness_note` appears when it is over a year old.
- Sole proprietors are not covered: only entities with a corporate number. Zero results is not proof that a company does not exist.
- For credit decisions, confirm with the commercial registry (登記事項証明書).

## Security and privacy

- Network: HTTPS requests to `api.info.gbiz.go.jp` only. The names, corporate numbers and prefectures you search for are sent there, with your token in the `X-hojinInfo-api-token` header. Redirects are refused, so the token cannot be forwarded to another host. The token never appears in tool output or error messages.
- Reads only the `GBIZINFO_API_TOKEN` environment variable. Writes no files; the cache lives in memory and is gone when Hermes exits.
- Never prompts, so it does not block cron jobs or the messaging gateway: a missing token is returned as an error message.
- Python standard library only, no dependencies. No shell commands, no background processes, no telemetry, no self-update.

## Development

```bash
pip install pytest pyyaml
pytest -q
hermes plugins validate .
```

The tests replay gBizINFO responses recorded on 2026-10-02 and trimmed to the fields the tests use (`tests/fixtures/`, source credits in `tests/fixtures/README.md`). They need no token and block all network access.

## License

MIT. This plugin is not affiliated with or endorsed by the Ministry of Economy, Trade and Industry or gBizINFO.

---

## 日本語

### できること

取引先が登記された法人か、登記が閉鎖されていないかを確かめる。会社名から法人番号を調べる。請求書の登録番号と社名・住所が合っているかを照合する。補助金・官公庁の受注・表彰・認定・財務・特許・職場情報から相手を知る。これを Hermes Agent に頼めるようにするプラグインです。データは経済産業省の [Gビズインフォ](https://info.gbiz.go.jp/) から取ります。

### 導入（3手）

1. `hermes plugins install TakeshiTGAL/hermes-plugin-jp-corporate --enable` を実行する（手元のコピーで試すときは、clone したフォルダで `hermes plugins install "file://$PWD" --enable`）
2. 聞かれたら Gビズインフォの API トークンを貼る（あとで `~/.hermes/.env` に `GBIZINFO_API_TOKEN=...` と書いてもよい）。Hermes を再起動する
3. 「法人番号 1180301018771 の会社を調べて」と頼む

### トークンの申請

無料です。[利用申請フォーム](https://info.gbiz.go.jp/hojin/various_registration/form)で、申請区分は「トークン利用(WebAPI・データダウンロード)」を選びます。

- 利用目的の選び方: 自社の取引先確認・請求書の照合なら「社内業務改善（自社分析、自社システムへの組み込み）」、個人で使うなら「個人利用（趣味・教育）」、ほかの人も使える形（Hermes のゲートウェイで他人と共有するボットなど）で提供するなら「サービス利用（サービス開発・プロダクトへの組み込み）」。
- 利用予定の欄には使い方と頻度を書きます（例:「Hermes Agent から取引先確認のため手動で照会。1日数十件程度」）。
- 申請後に届く「Web API 利用申請完了」メールのリンク先にトークンが表示されます。
- **トークンは1人1つ。** 一度申請したら、そのトークンを使い続けてください。利用制限を避けるために複数のトークンを取ったり使ったりすることは、API 利用規約で禁止されています。使えるのは申請した目的の範囲だけです。トークンが使えなくなったら、申請し直さずに[問い合わせ窓口](https://help.info.gbiz.go.jp/hc/ja/requests/new)へ。

### 表記の揺れと照合

「(株)トヨタ自動車」「ﾄﾖﾀ自動車」「トヨタ自動車株式会社」はどれも同じ検索になり、トヨタ自動車株式会社（1180301018771）が先頭に来ます。同じ名前の会社は `address`（「愛知県」「豊田市」など）で絞れます。法人番号は桁数とチェックディジットを手元で確かめ、誤りなら API を呼ばずに入力誤りと返します。請求書の照合では、社名は「(株)」と「株式会社」の違いや全角半角を無視して比べ、住所は番地を数字のまとまりごとに比べます（「1番地」と「10番地」は別、「一丁目3番1号」と「1-3-1」は同じ、「霞ヶ関」と「霞が関」も同じ）。先頭の郵便番号（〒471-0826）は無視します。請求書のほうが詳しい（登記は「1番地」、請求書は「1-1」）ときは `more_detailed` と返します。

### 注意

- `status` が `registered` なのは「登記が閉鎖されていない」という意味で、営業していることの証明ではありません。
- 適格請求書発行事業者として登録されているかは別の台帳です。[国税庁 インボイス制度 適格請求書発行事業者公表サイト](https://www.invoice-kohyo.nta.go.jp/)で確かめてください。
- 個人事業主は対象外です。0件でも「存在しない」証明にはなりません。
- 代表者・資本金・従業員数は古いことがあります。結果の `gbizinfo_last_updated` で日付を確かめてください。与信の判断には登記事項証明書で確かめてください。

### 困ったとき

| 表示 | すること |
|---|---|
| `token_missing` | トークンを申請し、`~/.hermes/.env` に `GBIZINFO_API_TOKEN=...` を書いて Hermes を再起動する |
| `401` | トークンの写し間違い。完了メールのリンク先から、引用符や空白を付けずに貼り直す |
| `found: 0` | 名前を短くする・表記を変える（カタカナ／漢字／英字）・住所の絞り込みを外す |
| `403` / `429` | 混雑か使いすぎ。数分待つ。繰り返し呼ばない |
| `input` | 入力の誤り（12桁、チェックディジット不一致など）。API は呼んでいない |
| `3xx`（redirect） | API の住所が変わった可能性。リダイレクトは追わない（トークンを他へ送らない）。プラグインの更新を待つ |
| 通信エラー・`500` | 接続を確かめ、少し待ってからやり直す。メンテナンス情報は https://info.gbiz.go.jp/ |

### 出典の表記

結果には、Gビズインフォの利用規約が求める形の出典（加工した旨と利用日つき）が `attribution` として付きます。資料に転記するときも、この1行を残してください。

### 使いすぎない作り

検索は1回の呼び出しで多くても1リクエスト、詳細は区分ごとに1リクエストです。自動でページをめくったり、失敗を繰り返し再送したりはしません。同じ問い合わせは10分間メモリから返します。大量に取得したいときは Gビズインフォの[データダウンロード](https://info.gbiz.go.jp/hojin/DownloadTop)を使ってください。
