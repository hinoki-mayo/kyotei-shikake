# 競艇 仕掛け予想サイト

全24場の番組表・競走成績を自動で集め、1マーク仕掛け予想（スリット隊形＋1マーク隊形の2枚の図）を毎日公開するサイトです。

## 自動で動くもの

| 時間(日本時間) | 内容 |
|---|---|
| 7:00 / 21:00 | 番組表を取得 → 出走表ページを更新 |
| 8:00〜21:59 に5分おき | 締切30分前のレースの展示進入を1レース1回だけ確認 → スリット・1マークの展開予想を公開 |
| 0:30 | 成績を取得（今期勝率・節間成績に反映） |

締切を過ぎたレースの予想は書き換えません。予想データ（data/predictions）の更新履歴が「締切前に出した」証明になります。

## はじめの設定

**くわしい手順は「公開手順.md」を見てください。**

### 1. GitHub
1. 新しいリポジトリを作り、このフォルダの中身をアップロード（パソコン推奨）
2. Settings → Actions → General → Workflow permissions を「Read and write permissions」に
3. Actions →「過去データ一括取得」を1年ずつ6回実行（2020-10-01〜2021-09-30 … 2025-10-01〜今日）

### 2. Cloudflare Pages（公開先）
1. Cloudflare → Workers & Pages → 作成 → Pages →「直接アップロード」でプロジェクトを作る（名前は例: kyotei-shikake）
2. マイプロフィール → APIトークン →「Cloudflare Pages 編集」権限のトークンを作る
3. GitHubのリポジトリ Settings → Secrets and variables → Actions で登録
   - Secrets: `CLOUDFLARE_API_TOKEN`（トークン）、`CLOUDFLARE_ACCOUNT_ID`（アカウントID）
   - Variables: `CF_PROJECT`（プロジェクト名）
4. 独自ドメインは Pages プロジェクトの「カスタムドメイン」から設定

### 3. サイト設定
- `site_config.json`：サイト名・URL・運営者情報・連絡先
- `ads/` フォルダ：広告タグやads.txtを貼るだけ

## 中身
| ファイル | 役割 |
|---|---|
| scripts/backfill.py, daily.py | データ取得（公式配信ファイル） |
| scripts/model.py | 予想モデル（選手×コースの勝ち方・ST・実力・潰れ合い・攻め手なし） |
| scripts/scene.py | 展開の組み立て（主役・頭注目・連絡み注目・展開不向き・一言） |
| scripts/draw.py | 図の生成（ターンマーク・ボート・ラベルの重なりチェック付き） |
| scripts/predict.py | 予想の作成と封印保存 |
| scripts/entry.py | 展示進入の反映（1レース1回だけアクセス） |
| scripts/build_site.py | サイト生成（レース・場・日付・的中実績・必須ページ・sitemap） |

## 注意
- 公式サーバーに負担をかけないよう、アクセスの間隔を空けています。短くしないでください
- 予想はデータから見た展開の傾向で、着順を保証するものではありません。舟券の購入は20歳から
