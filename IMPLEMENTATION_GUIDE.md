# 自動更新システム実装ガイド

このドキュメントでは、imayoshinaoki.fun の自動更新システムを完全に機能させるための実装手順を説明します。

---

## 📋 システム全体構成

```
GitHub Pages                WordPress (ユーザー側)
(フロントエンド)            (CMS バックエンド)
      ↓                            ↓
index.html ←────── REST API ───── posts
events/index.js ←─────────────── /wp-json/wp/v2/
topics/index.js      ↑
                     │
                GitHub Actions (毎日 6:00 AM JST)
                     │
          ┌──────────┴──────────┐
          ↓                     ↓
   scrape_kirishima.py  post_to_wordpress.py
          ↓                     ↓
    霧島市役所              WordPress
    きりなび               REST API
    まいぷれ
```

---

## 🚀 実装手順

### Step 1: WordPress 側の設定（ユーザー側作業）

**所要時間**: 15-20 分

ユーザーが WordPress 管理画面で以下の設定を完了してください：

**詳細は `WORDPRESS_SETUP.md` を参照**

✅ **チェックリスト:**
- [ ] パーマリンク設定 → 「投稿名」に変更
- [ ] カテゴリー作成: kirishima-news, events, social-post, column
- [ ] Application Password 生成
- [ ] CORS 設定（WP CORS または functions.php）
- [ ] REST API 動作確認
- [ ] GitHub Secrets に 3 つの情報を登録

### Step 2: GitHub リポジトリの準備

**所要時間**: 5 分

#### 2.1 GitHub Secrets を登録

1. GitHub リポジトリ → **Settings → Secrets and variables → Actions**
2. **「New repository secret」** をクリック

以下の 3 つを登録：

| Secret 名 | 値 | 例 |
|---|---|---|
| `WP_URL` | WordPress のURL | `https://your-wp-domain.com` |
| `WP_USER` | WordPress ユーザー名 | `admin` |
| `WP_APP_PASS` | Application Password | `1234 5678 9012 3456 7890 1234 5678 9012` |

#### 2.2 リポジトリにファイルをプッシュ

以下のファイルが配置されていることを確認：

```
.github/
└── workflows/
    └── daily-update.yml          ← GitHub Actions ワークフロー

scripts/
├── scrape_kirishima.py           ← スクレイピングスクリプト
├── post_to_wordpress.py          ← WordPress 投稿スクリプト
└── requirements.txt              ← Python 依存パッケージ
```

**プッシュコマンド:**

```bash
cd imayoshinaoki-website
git add .github/workflows/daily-update.yml
git add scripts/
git add WORDPRESS_SETUP.md
git add IMPLEMENTATION_GUIDE.md
git commit -m "Add automatic news update system with WordPress integration"
git push origin main
```

### Step 3: システム動作確認

**所要時間**: 10 分

#### 3.1 ローカルでテスト

```bash
# 依存パッケージをインストール
pip install -r scripts/requirements.txt

# スクレイピング実行（テスト）
python scripts/scrape_kirishima.py

# 生成されたファイルを確認
cat scripts/scraped_items.json

# WordPress 投稿テスト（WP_* 環境変数を設定）
export WP_URL="https://your-wp-domain.com"
export WP_USER="admin"
export WP_APP_PASS="your-app-password"
python scripts/post_to_wordpress.py
```

#### 3.2 GitHub Actions でテスト

1. GitHub リポジトリ → **Actions**
2. **「Daily Kirishima News Update」** を選択
3. **「Run workflow」** をクリック（manual trigger）
4. ログを確認して成功を確認

**期待される出力:**
```
✓ WordPress connection successful
Scraped 15 items from 霧島市役所
Scraped 8 items from きりなび
Scraped 6 items from まいぷれ
Total items scraped: 29
Deduplicated: 29 -> 27
✓ Created post: ... (ID: 123)
✓ Created post: ... (ID: 124)
...
Posted: 5, Skipped: 22
```

---

## 🔧 トラブルシューティング

### Problem 1: GitHub Actions が失敗する

**症状:** Workflow run が失敗、赤い ✗ マークが表示される

**原因と対策:**
1. **Secrets の設定不足** → GitHub Secrets に WP_URL, WP_USER, WP_APP_PASS が登録されているか確認
2. **WordPress 接続失敗** → WP_URL が正しいか、https:// を含んでいるか確認
3. **Authentication エラー** → WP_USER と WP_APP_PASS が正しいか確認

### Problem 2: REST API 404 エラー

**症状:** "REST API endpoint not found" エラー

**原因:** パーマリンク設定が「投稿名」になっていない

**対策:**
```
WordPress 管理画面 → 設定 → パーマリンク → 「投稿名」を選択 → 保存
```

### Problem 3: CORS エラー

**症状:** "Access-Control-Allow-Origin" エラー

**原因:** CORS が有効化されていない

**対策:**
- WP CORS プラグインをインストール・有効化
- または functions.php に CORS ヘッダーを追加

### Problem 4: 投稿が重複する

**症状:** 同じニュースが複数回投稿される

**原因:** URL ベースの重複チェックが機能していない

**対策:**
1. WordPress の既存投稿を確認
2. Metadata に `source_url` が正しく設定されているか確認
3. スクリプトのログを確認

---

## 📊 スケジュール設定

### 毎日 6:00 AM に実行

**現在の設定:**
```yaml
schedule:
  - cron: '0 21 * * *'  # 毎日 21:00 UTC = 6:00 AM JST
```

**変更方法:**

時刻を変更したい場合、`.github/workflows/daily-update.yml` を編集：

```yaml
schedule:
  - cron: '30 18 * * *'  # 毎日 18:30 UTC = 3:30 AM JST
```

**Cron 式の参考:**
- `0 21 * * *` = 毎日 21:00 UTC （6:00 AM JST）
- `0 12 * * *` = 毎日 12:00 UTC （9:00 PM JST）
- `0 0 * * *` = 毎日 00:00 UTC （9:00 AM JST）
- `0 */4 * * *` = 4 時間ごと

---

## 📈 監視・ログ確認

### GitHub Actions ログの確認

1. GitHub リポジトリ → **Actions**
2. **「Daily Kirishima News Update」** をクリック
3. 実行履歴から最新のワークフロー実行をクリック
4. 各ステップのログを確認

**主なログポイント:**
- ✓ Python セットアップ完了
- ✓ 依存パッケージインストール完了
- ✓ スクレイピング完了
- ✓ WordPress 投稿完了

### WordPress での確認

1. WordPress 管理画面 → **投稿**
2. 最近の投稿を確認
3. メタデータ（ソースURL等）を確認（Advanced Custom Fields 等で表示可能）

---

## 🔒 セキュリティ に関する注意

### Secrets の管理

- Application Password は **絶対に公開しないこと**
- GitHub Secrets にのみ保存
- ローカルでテストする場合も、コミットしないこと

### パーソナルアクセストークン

- 定期的にパスワードを変更する（WordPress の Application Password）
- 不要になったら削除する

---

## 🎯 次のステップ

### Phase 4: フロントエンドの API 連携

GitHub Actions で投稿が WordPress に保存されたら、フロントエンドから REST API を通じて取得：

**events/index.html** の FullCalendar.js：
```javascript
const WP_API = 'https://your-wp-domain.com/wp-json/wp/v2';

async function loadEvents() {
  const res = await fetch(`${WP_API}/posts?categories=events-id&per_page=50`);
  const posts = await res.json();
  return posts.map(p => ({
    title: p.title.rendered,
    start: p.date,
    url: p.link,
  }));
}
```

**topics/index.html** の記事リスト：
```javascript
async function loadTopics() {
  const res = await fetch(`${WP_API}/posts?per_page=10`);
  const posts = await res.json();
  // レンダリング処理
}
```

---

## 📞 サポート

トラブルがあれば以下を確認：

1. **WORDPRESS_SETUP.md** - WordPress 設定ガイド
2. **GitHub Actions ログ** - 実行ログ確認
3. **スクリプト実行ログ** - ローカルテスト時のログ
4. **WordPress の REST API 確認** - ブラウザで `/wp-json/wp/v2/posts` にアクセス

---

**実装完了後は、毎日 6:00 AM に自動的にニュースが収集・投稿されます！**
