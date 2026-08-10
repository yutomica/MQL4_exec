# Backtestレポート仕様

## 目的と適用範囲

この文書は、`Backtest/Backtest.py`と`utils/STReportReader.py`が通常バックテストのMT4 HTMLレポートから生成する成果物のデータ契約を定義します。

- 対象：通常バックテスト（Backtest）
- 対象外：Optimization、Validation、旧式の従来Excel
- 現在のschema version：`1.0.0`

Optimizationの成果物にはこの仕様を適用しません。Optimizationを改修する場合は、別の仕様書と独立したschema versionを定義します。

## 正本と優先順位

成果物は、次の順序で確認します。

1. `manifest.json`
2. `validation.json`
3. `analysis/metrics.xlsx`
4. `normalized/trades.csv.gz`
5. `normalized/order_events.csv.gz`
6. `raw/report.html`

`raw/report.html`はMT4が生成した完全な原本です。正規化データや集計結果に疑義がある場合は、必ずこのHTMLへ戻って確認します。

出力ディレクトリ直下に残る従来形式の`Backtest_*.xlsx`および固定名HTMLは後方互換用であり、この仕様の正本ではありません。

## ディレクトリ構成

通常バックテストの1条件ごとに、一意のrun IDを持つディレクトリを生成します。

```text
results/BKT_<EA>/<run_id>/
├── input/
│   └── test_params.txt
├── raw/
│   ├── report.html
│   └── report.gif              # MT4が生成した場合のみ
├── normalized/
│   ├── order_events.csv.gz
│   └── trades.csv.gz
├── analysis/
│   └── metrics.xlsx
├── validation.json
└── manifest.json
```

run IDの現在の形式は次のとおりです。

```text
YYYYMMDDTHHMMSSffffff_<symbol>_<timeframe>_<start>_<end>
```

## 共通表現

- CSV文字コード：UTF-8
- CSV圧縮：gzip
- 日時：`YYYY-MM-DDTHH:MM:SS`
- JSON文字コード：UTF-8
- JSON欠損値：`null`
- ExcelのDataFrame index：出力しない
- 時刻基準：MT4サーバー時刻
- タイムゾーン：現在は未特定であり、`timezone`は`null`

タイムゾーンが`null`の場合、東京、ロンドン、ニューヨークなどの現地時間へ推測で変換してはいけません。

## manifest.json

### トップレベル

| フィールド | 型 | 内容 |
|---|---|---|
| `schema_version` | string | このBacktest成果物のschema version |
| `run_metadata` | object | Backtest.pyから渡された実行条件 |
| `report` | object | 生HTMLのパス、サイズ、SHA-256 |
| `summary` | object | MT4サマリを型変換した値 |
| `parameters` | array | EA入力パラメータの名前と元文字列 |
| `validation_status` | string | `valid`、`warning`、`invalid`のいずれか |
| `artifacts` | array | 派生成果物の相対パス |

### run_metadata

現在の`Backtest.py`は次のフィールドを設定します。

| フィールド | 内容 |
|---|---|
| `run_id` | 一意の実行識別子 |
| `ea` | EA名 |
| `symbol` | 通貨ペア |
| `timeframe` | 時間足 |
| `test_model` | MT4テストモデル |
| `time_start` | 要求した開始日 |
| `time_end` | 要求した終了日 |
| `time_basis` | `mt4_server_time` |
| `timezone` | 現在は`null` |

Gitコミット、作業ツリー状態、EAハッシュなど、存在しないメタデータを推測で補ってはいけません。

### report

| フィールド | 内容 |
|---|---|
| `path` | 解析に使用した保存済みHTMLの絶対パス |
| `size` | バイト数 |
| `sha256` | HTML全体のSHA-256 |

### summary

`summary`にはMT4 HTMLのサマリ値を保存します。主な項目は、通貨ペア、期間、時間足、モデル、パラメータ、テストバー数、モデルティック数、モデリング品質、不整合チャートエラー、初期証拠金、スプレッド、取引数、純益、総利益、総損失、PF、期待利得、DD、方向別件数・勝率、平均・最大損益、連勝・連敗です。

MT4の表示値であり、`analysis/metrics.xlsx`の再計算値と区別します。

## validation.json

### ステータス

| ステータス | 意味 | 評価時の扱い |
|---|---|---|
| `valid` | 必須照合が一致し、警告もない | 通常どおり評価可能 |
| `warning` | 必須照合は成立するが、推定値・未解決注文・計算対象差などがある | 警告を明記した条件付き評価 |
| `invalid` | 件数、損益、状態遷移、必須フィールドなどに不一致がある | 正式評価に使用しない |

`invalid`でも診断用成果物は保存される場合があります。`warning`を自動的に失敗扱いせず、警告の内容を確認します。

### トップレベル

| フィールド | 内容 |
|---|---|
| `schema_version` | Backtest schema version |
| `status` | 検証状態 |
| `checks` | 期待値と実測値の照合結果 |
| `errors` | 必須解析・状態遷移エラー |
| `warnings` | 評価時に明示すべき制約 |
| `event_count` | 正規化した全イベント数 |
| `trade_count` | 決済済み取引数 |
| `unresolved_ticket_count` | 未決済または未取消ticket数 |
| `pip_size` | 使用したpip幅 |
| `pip_size_source` | pip幅の決定元 |
| `digits` | 推定または指定された価格桁数 |

### 必須照合

現在、次をMT4サマリまたはイベント系列と照合します。

- 総取引数
- 売り件数
- 買い件数
- MT4勝トレード件数
- 負トレード件数
- 純益
- 総利益
- 総損失
- 最終残高
- プロフィットファクタ
- event sequenceの一意性と連続性

MT4は損益0の取引を勝トレード側へ含めるため、`mt4_winning_trade_count`では`win + breakeven`をMT4勝トレード数と照合します。

### 警告扱いの照合

- MT4報告最大DDと決済残高から再計算した最大DDの差
- `event_seq`順と分単位の表示時刻順の差

部分決済などにより表示時刻が逆転する場合があるため、イベント順序の正本は`event_time`ではなく`event_seq`です。

### 主な警告

| 警告 | 意味 |
|---|---|
| `unresolved_tickets` | テスト終了時点の未決済または未取消注文がある |
| `inferred_from_price_digits` | pip幅を明示値ではなく表示価格の桁数から推定した |
| `reported_and_closed_balance_drawdown_differ` | MT4報告DDと決済残高DDの計算対象が異なる可能性がある |

## normalized/order_events.csv.gz

MT4 HTMLの明細を、一行一イベントとして`event_seq`順に保存します。pending注文、実約定、変更、取消、決済の全イベントを含みます。

| 列 | 型 | 内容 |
|---|---|---|
| `event_seq` | integer | HTMLのイベント番号。イベント順序の正本 |
| `event_time` | datetime | MT4表示時刻 |
| `event_type` | string | 小文字へ正規化した取引種別 |
| `ticket` | integer | MT4注文番号 |
| `lots` | number | イベント時の数量 |
| `price` | number | イベント価格 |
| `stop_loss` | number | イベント時点のSL |
| `take_profit` | number | イベント時点のTP |
| `profit` | number/null | 決済損益。非決済イベントは欠損 |
| `balance` | number/null | 決済後残高。非決済イベントは欠損 |
| `source_row` | integer | 明細テーブル上の読込み順 |
| `parse_status` | string | `valid`または`invalid` |

認識するイベント種別は次のとおりです。

- pending：`buy limit`、`sell limit`、`buy stop`、`sell stop`
- 実約定：`buy`、`sell`
- 変更：`modify`
- 取消：`delete`
- 決済：`close`、`s/l`、`t/p`、`close at stop`

未知のイベント種別は推測せず、検証エラーにします。

## normalized/trades.csv.gz

実約定イベントと後続の決済イベントが存在するticketだけを、一行一決済済み取引として保存します。pendingのみ、取消のみ、テスト終了時の未解決注文は含めません。

| 列 | 内容 |
|---|---|
| `ticket` | MT4注文番号 |
| `entry_event_seq` | 実約定イベント番号 |
| `exit_event_seq` | 決済イベント番号 |
| `direction` | `buy`または`sell` |
| `entry_time` | 実約定時刻。pending発注時刻ではない |
| `entry_price` | 実約定価格 |
| `entry_lots` | 実約定数量 |
| `initial_stop_loss` | 実約定イベントに記録されたSL |
| `initial_take_profit` | 実約定イベントに記録されたTP |
| `exit_time` | 決済時刻 |
| `exit_price` | 決済価格 |
| `exit_lots` | 決済数量 |
| `exit_reason` | 決済イベント種別 |
| `profit_amount` | MT4 HTMLの決済損益 |
| `balance_after` | 決済後残高 |
| `holding_seconds` | 保有秒数 |
| `holding_hours` | 保有時間 |
| `price_move` | 売買方向を考慮した価格差 |
| `pips` | `price_move / pip_size` |
| `initial_risk_price` | 実約定価格と初期SLの方向付き距離 |
| `initial_risk_pips` | `initial_risk_price / pip_size` |
| `r_multiple` | `price_move / initial_risk_price` |
| `result` | `win`、`loss`、`breakeven` |
| `modify_count` | 実約定後から決済までの変更回数 |
| `last_stop_loss` | 決済までに最後に記録されたSL |
| `last_take_profit` | 決済までに最後に記録されたTP |
| `remaining_lots` | `max(entry_lots - exit_lots, 0)` |
| `possible_partial_close` | entryとexitの数量が異なる場合にtrue |
| `entry_year` | エントリー年 |
| `entry_month` | エントリー年月 |
| `entry_weekday` | 月曜=1、日曜=7 |
| `entry_hour` | MT4サーバー時刻のエントリー時 |
| `exit_year` | 決済年 |
| `exit_month` | 決済年月 |
| `exit_weekday` | 月曜=1、日曜=7 |
| `exit_hour` | MT4サーバー時刻の決済時 |
| `data_quality_flags` | セミコロン区切りの品質フラグ |

### 取引成立条件

次をすべて満たすticketだけを取引として扱います。

1. `buy`または`sell`の実約定イベントがある
2. その後に認識可能な決済イベントがある
3. 決済損益と残高を取得できる
4. 必須値と状態遷移が検証可能である

### result

| 値 | 条件 |
|---|---|
| `win` | `profit_amount > 0` |
| `loss` | `profit_amount < 0` |
| `breakeven` | `profit_amount == 0` |

集計の`win_count`と`win_rate`は厳密に正の損益だけを勝ちとします。

### pips

```text
buy  : (exit_price - entry_price) / pip_size
sell : (entry_price - exit_price) / pip_size
```

pip幅の優先順位は次のとおりです。

1. 呼出し側から渡されたsymbol仕様の`pip_size`
2. `BacktestReport`へ直接渡された値
3. HTML表示価格の最大小数桁数からの推定

推定規則は、3桁・5桁価格では`10 ^ -(digits - 1)`、それ以外では`10 ^ -digits`です。`pip_size_source=inferred_digits`の場合は推定値として扱います。

### R

```text
buy risk  = entry_price - initial_stop_loss
sell risk = initial_stop_loss - entry_price
R         = price_move / initial_risk_price
```

初期SLが0、欠損、方向と矛盾、またはリスクが0以下の場合、Rは欠損となり`invalid_initial_risk`を記録します。変更後SLではなく、実約定イベントに記録された初期SLを使用します。

### 部分決済

HTMLに明示的な親子関係がないため、部分決済後に生成された別ticketとの関係を推測しません。数量差は`possible_partial_close`と`remaining_lots`で示します。

### data_quality_flags

現在使用する値は次のとおりです。

- `multiple_entries`
- `multiple_exits`
- `missing_exit_value`
- `volume_mismatch`
- `invalid_initial_risk`

`multiple_entries`、`multiple_exits`、`missing_exit_value`は検証を`invalid`にします。品質フラグのある取引を、評価エージェントが根拠なく除外してはいけません。

## analysis/metrics.xlsx

### シート一覧

| シート | 内容 |
|---|---|
| `run_metadata` | Backtest.pyから渡された実行条件 |
| `data_quality` | checks、errors、warningsを表形式で結合 |
| `overall` | 全決済済み取引の共通集計 |
| `period_metrics` | 年、四半期、月ごとの共通集計 |
| `segment_metrics` | 方向、時刻、曜日、決済理由、保有時間帯別集計 |
| `distribution` | 損益、pips、R、保有時間の分布 |
| `drawdowns` | 決済残高DDエピソード |
| `streaks` | 連続する同一resultの系列 |
| `concentration` | 上位利益取引への依存度 |
| `trades` | `normalized/trades.csv.gz`と同じ取引表 |

## 共通集計列

`overall`、`period_metrics`、`segment_metrics`は次の共通指標を持ちます。

| 列 | 定義 |
|---|---|
| `trade_count` | 決済済み取引数 |
| `win_count` | 損益が正の件数 |
| `loss_count` | 損益が負の件数 |
| `breakeven_count` | 損益が0の件数 |
| `net_profit` | 損益合計 |
| `gross_profit` | 正の損益合計 |
| `gross_loss` | 負の損益合計。負値 |
| `profit_factor` | `gross_profit / abs(gross_loss)` |
| `expectancy` | 一取引あたり平均損益 |
| `win_rate` | `win_count / trade_count` |
| `average_win` | 正の損益の平均 |
| `average_loss` | 負の損益の平均。負値 |
| `payoff_ratio` | `average_win / abs(average_loss)` |
| `pips_total` | pips合計 |
| `pips_mean` | pips平均 |
| `r_total` | 有効なRの合計 |
| `r_mean` | 有効なRの平均 |
| `max_profit` | 最大損益 |
| `max_loss` | 最小損益 |
| `holding_hours_mean` | 平均保有時間 |
| `holding_hours_median` | 保有時間中央値 |
| `holding_hours_max` | 最大保有時間 |
| `max_drawdown_amount` | 対象取引系列の決済損益から再計算したDD金額 |
| `max_drawdown_percent` | 再計算したDDをその時点のピーク残高で除した値 |

損失取引がない場合など、分母が0になる比率は欠損とします。

期間・セグメント集計のDDは、そのグループに属する取引だけを時系列順に抽出した仮想系列のDDです。口座全体のDDではありません。

## period_metrics

追加列は次のとおりです。

- `period_type`：`year`、`quarter`、`month`
- `period_key`：対象期間キー
- `period_start`：グループ内の最初の決済時刻
- `period_end`：グループ内の最後の決済時刻

ローリング3・6・12か月集計は現在未実装です。

## segment_metrics

追加列は次のとおりです。

- `segment_type`
- `segment_value`

現在のsegment typeは次のとおりです。

- `direction`
- `entry_hour`
- `entry_weekday`
- `exit_reason`
- `holding_bucket`

`holding_bucket`の区切りは`0-1h`、`1-6h`、`6-24h`、`24-72h`、`72h+`です。各区間は右端を含み、例えば1時間は`0-1h`、6時間は`1-6h`に含まれます。

## distribution

対象指標は次のとおりです。

- `profit_amount`
- `pips`
- `r_multiple`
- `holding_hours`

各指標について`count`、`mean`、標本標準偏差`std`、`min`、1%、5%、25%、50%、75%、95%、99%分位点、`max`を出力します。

## drawdowns

`balance_after`と初期証拠金を使用して、決済残高DDの開始、底、回復を記録します。

| 列 | 内容 |
|---|---|
| `episode` | DDエピソード番号 |
| `start_time` | 直前ピーク時刻。初回ピーク未記録時は最初のentry時刻 |
| `trough_time` | 最大DD到達時刻 |
| `recovery_time` | ピーク回復時刻。未回復は欠損 |
| `drawdown_amount` | ピーク残高と底の差 |
| `drawdown_percent` | DD金額をピーク残高で除した値 |
| `recovered` | 回復済みか |

MT4報告DDが含み損益を含む場合、決済残高DDとは一致しません。両者を同一指標として扱ってはいけません。

## streaks

`win`、`loss`、`breakeven`が連続する系列ごとに、開始・終了時刻、件数、損益合計を出力します。`breakeven`は連勝・連敗を分断する独立resultです。

## concentration

| 列 | 定義 |
|---|---|
| `top_1_profit_share` | 最大利益1件 / 総利益 |
| `top_5_profit_share` | 上位利益5件 / 総利益 |
| `top_10_profit_share` | 上位利益10件 / 総利益 |
| `net_profit_without_top_1` | 最大利益1件を除く純益 |
| `net_profit_without_top_5` | 上位利益5件を除く純益 |
| `net_profit_without_top_10` | 上位利益10件を除く純益 |

## 評価エージェントの読取り規則

1. 対象run IDを明示する。
2. 最初に`manifest.json`と`schema_version`を確認する。
3. 次に`validation.json`を確認する。
4. `invalid`は正式評価に使用しない。
5. `warning`は内容と影響を報告へ明記する。
6. 定型集計は`metrics.xlsx`を優先する。
7. 取引単位の確認は`trades.csv.gz`を使用する。
8. 注文状態、pending、modifyの確認は`order_events.csv.gz`を使用する。
9. 疑義がある場合は`raw/report.html`へ戻る。
10. 追加計算を行う場合は入力列、式、欠損処理を明示する。
11. `data_quality_flags`のある行を根拠なく除外しない。
12. 結論にrun ID、schema version、参照成果物を付記する。

## 既知の制約

- タイムゾーンは未特定。
- pip幅は現在のBacktest.pyから明示指定されず、通常は価格桁数から推定される。
- MT4 HTMLだけでは含み損益系列を完全再現できない。
- 手数料、スワップ、スリッページを独立列へ分離していない。
- 部分決済後の親子ticketを推定していない。
- MFE、MAE、相場局面は生成していない。
- ローリング期間、ブートストラップ、コスト悪化シナリオは未実装。
- manifestに存在しないGit情報やEAハッシュを推測してはいけない。

## schema version運用

- major：既存列の意味変更、削除、非互換な構造変更
- minor：後方互換な列・シート・検証項目の追加
- patch：列と意味を変えない不具合修正または文書修正

`Backtest.py`または`STReportReader.py`で成果物の列、意味、式、欠損処理、検証条件を変更する場合は、同じタスクでこの文書とschema versionの要否を確認します。

Optimizationはこのschema versionを共有しません。

## 変更履歴

### 1.0.0

- Backtest通常実行のrun単位成果物を定義。
- 全注文イベント、決済済み取引、検証JSON、manifest、定型集計Excelを定義。
- MT4報告値と再計算値の区別を定義。
