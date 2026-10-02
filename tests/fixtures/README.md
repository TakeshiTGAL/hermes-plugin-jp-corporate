# Recorded gBizINFO responses (trimmed)

Responses of the gBizINFO REST API v2, all retrieved on 2026-10-02 for the offline tests, then trimmed to the fields the tests read. Personal data such as representative names was removed.

出典：「Gビズインフォ」（経済産業省）（各行のURL）を加工して作成（2026年10月2日に利用）

| File | Request | Source page (出典) | Kept (加工の内容) |
|---|---|---|---|
| `search_name_toyota.json` | `GET /v2/hojin?name=トヨタ自動車` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 を含む81法人（各行の法人番号のページ） | 法人番号・名称・所在地・郵便番号・状態のみ |
| `search_not_found.json` | `GET /v2/hojin?name=（該当なし）` | https://info.gbiz.go.jp/ | 無加工（404 応答） |
| `unauthorized.json` | `GET /v2/hojin/{番号}（無効なトークン）` | https://info.gbiz.go.jp/ | 無加工（401 応答） |
| `hojin_4000012090001.json` | `GET /v2/hojin/4000012090001` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=4000012090001 | 名称・所在地・郵便番号・状態・法人種別のみ |
| `hojin_1180301018771.json` | `GET /v2/hojin/1180301018771` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 代表者名などを削除。名称・所在地・状態・種別・資本金・業種・設立日・更新日のみ |
| `hojin_1180301018771_procurement.json` | `GET /v2/hojin/1180301018771/procurement` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 受注日と金額のみ |
| `hojin_1180301018771_certification.json` | `GET /v2/hojin/1180301018771/certification` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 認定日と名称のみ |
| `hojin_1180301018771_commendation.json` | `GET /v2/hojin/1180301018771/commendation` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 部門と表彰名のみ |
| `hojin_1180301018771_subsidy.json` | `GET /v2/hojin/1180301018771/subsidy` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 無加工（0件） |
| `hojin_1180301018771_finance.json` | `GET /v2/hojin/1180301018771/finance` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 事業年度・回次・売上高・大株主上位2社（法人）のみ |
| `hojin_1180301018771_workplace.json` | `GET /v2/hojin/1180301018771/workplace` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1180301018771 | 女性労働者の割合のみ |
| `hojin_1010801006516_subsidy.json` | `GET /v2/hojin/1010801006516/subsidy` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1010801006516 | 認定日・補助金名・金額のみ |
| `hojin_1010801006516_corporation.json` | `GET /v2/hojin/1010801006516/corporation` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=1010801006516 | 被保険者数のみ |
| `hojin_5011001043924_patent.json` | `GET /v2/hojin/5011001043924/patent` | https://info.gbiz.go.jp/hojin/ichiran?hojinBango=5011001043924 | 先頭12行、種別・登録番号・出願日・名称のみ |

Source: gBizINFO, Ministry of Economy, Trade and Industry, Japan (https://info.gbiz.go.jp/), retrieved 2026-10-02; trimmed by the jp-corporate plugin authors.
