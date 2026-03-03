# WordPress REST API 設定ガイド

このドキュメントでは、imayoshinaoki.fun サイトの自動更新システムに必要な WordPress 設定手順を説明します。

---

## 📋 事前確認

- WordPress バージョン: 5.6 以上（Application Passwords が標準搭載）
- プラグイン: WP CORS（CORS対応）がインストール済み、または functions.php で CORS ヘッダーを設定済み

---

## 1️⃣ パーマリンク設定

GitHub Actions のスクリプトが投稿を識別するためにスラッグを使用するため、パーマリンク設定を「投稿名」に変更する必要があります。

### 手順

1. WordPress 管理画面にログイン
2. **設定 → パーマリンク**
3. **「投稿名」** を選択
4. **「変更を保存」** をクリック

**設定前**: `https://example.com/?p=123`
**設定後**: `https://example.com/my-post-title/`

---

## 2️⃣ カテゴリーの作成

自動スクリプトが投稿を分類するために、以下の 4 つのカテゴリーを作成します。

### カテゴリー一覧

| 名前（表示） | スラッグ | 説明 |
|---|---|---|
| 霧島市ニュース | `kirishima-news` | 市役所・きりなび・まいぷれから自動収集 |
| イベント | `events` | イベント情報（カレンダー表示） |
| SNS投稿 | `social-post` | Facebook/X の投稿連携 |
| コラム | `column` | 手動投稿記事 |

### 手順

1. WordPress 管理画面 → **投稿 → カテゴリー**
2. 以下の情報で 4 つのカテゴリーを作成：

#### カテゴリー 1: 霧島市ニュース
- **名前**: 霧島市ニュース
- **スラッグ**: `kirishima-news`
- **説明**: 市役所・きりなび・まいぷれから自動収集したニュース記事

#### カテゴリー 2: イベント
- **名前**: イベント
- **スラッグ**: `events`
- **説明**: 霧島市内で開催されるイベント情報

#### カテゴリー 3: SNS投稿
- **名前**: SNS投稿
- **スラッグ**: `social-post`
- **説明**: Facebook や X（Twitter）の投稿

#### カテゴリー 4: コラム
- **名前**: コラム
- **スラッグ**: `column`
- **説明**: 今吉なおきによる手動投稿記事・ブログ

---

## 3️⃣ Application Password の生成

REST API 認証に使用するアプリケーションパスワードを生成します。

### 手順

1. WordPress 管理画面 → **ユーザー → あなたのプロフィール**
2. ページ下部の **「アプリケーションパスワード」** セクションを探す
   - 見つからない場合は、プラグイン管理 → 「WP Application Passwords」をアクティベート
3. **アプリケーション名**: `GitHub Auto Poster` と入力
4. **「新しいアプリケーションパスワードを生成」** をクリック
5. **生成されたパスワード** をコピー（以下の形式）:
   ```
   例: 1234 5678 9012 3456 7890 1234 5678 9012
   ```
6. **「パスワードを確認」** をクリック

### ⚠️ 注意
- このパスワードは **一度だけ表示されます**
- 後で見直せないため、安全な場所に保存してください
- GitHub Secrets に登録する際に使用します

---

## 4️⃣ CORS (Cross-Origin Resource Sharing) 設定

フロントエンド（GitHub Pages）から WordPress REST API にアクセスするため、CORS を有効化します。

### オプション A: WP CORS プラグインを使用（推奨）

1. プラグイン管理 → **新規追加**
2. **WP CORS** を検索
3. **インストール** → **有効化**
4. **設定 → WP CORS**
5. **Enable CORS** にチェック
6. **Save Changes** をクリック

### オプション B: functions.php で手動設定

WP CORS が使用できない場合、`functions.php` に以下を追加：

```php
add_filter('rest_pre_serve_request', function($served) {
    header('Access-Control-Allow-Origin: https://imayoshinaoki.fun');
    header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
    header('Access-Control-Allow-Credentials: true');
    header('Access-Control-Allow-Headers: Content-Type, Authorization');
    return $served;
}, 10, 1);
```

---

## 5️⃣ REST API の動作確認

### 確認方法 1: ブラウザで確認

以下の URL にアクセス（`your-wp-domain.com` は自分のドメインに置き換え）:

```
https://your-wp-domain.com/wp-json/wp/v2/posts?categories=events
```

**成功時**: JSON形式で投稿データが表示される

### 確認方法 2: cURL コマンドで確認

```bash
curl -H "Authorization: Basic $(echo -n 'username:password' | base64)" \
  "https://your-wp-domain.com/wp-json/wp/v2/posts?categories=events"
```

---

## 6️⃣ GitHub Secrets の登録

Python スクリプトが WordPress に接続するための認証情報を GitHub Secrets に登録します。

### 登録内容

| Secret 名 | 値 | 例 |
|---|---|---|
| `WP_URL` | WordPress サイトの URL | `https://your-wp-domain.com` |
| `WP_USER` | WordPress ユーザー名 | `admin` |
| `WP_APP_PASS` | Application Password | `1234 5678 9012 3456 7890 1234 5678 9012` |

### 手順

1. GitHub リポジトリを開く
2. **Settings → Secrets and variables → Actions**
3. **「New repository secret」** をクリック
4. 以下の 3 つを登録：

#### Secret 1: WP_URL
- **Name**: `WP_URL`
- **Secret**: `https://your-wp-domain.com` (末尾のスラッシュなし)
- **「Add secret」** をクリック

#### Secret 2: WP_USER
- **Name**: `WP_USER`
- **Secret**: WordPress ユーザー名
- **「Add secret」** をクリック

#### Secret 3: WP_APP_PASS
- **Name**: `WP_APP_PASS`
- **Secret**: Application Password（スペース含む）
- **「Add secret」** をクリック

---

## ✅ チェックリスト

以下を確認して、設定が完了したことを確認してください：

- [ ] パーマリンク設定を「投稿名」に変更
- [ ] 4 つのカテゴリーを作成（kirishima-news, events, social-post, column）
- [ ] Application Password を生成して安全に保存
- [ ] CORS を有効化（WP CORS または functions.php）
- [ ] REST API の動作を確認
- [ ] GitHub Secrets に 3 つの情報を登録

---

## 🔗 参考リンク

- [WordPress REST API 公式ドキュメント](https://developer.wordpress.org/rest-api/)
- [Application Passwords 設定ガイド](https://wordpress.org/support/article/application-passwords/)
- [GitHub Secrets 設定ガイド](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)

---

## ❓ トラブルシューティング

### REST API が 404 エラーで返される
→ パーマリンク設定が「投稿名」になっているか確認してください

### CORS エラーが発生する
→ WP CORS プラグインが有効化されているか、または functions.php の設定が正しいか確認してください

### Authentication error が発生する
→ WP_USER と WP_APP_PASS が正しいか、GitHub Secrets に正しく登録されているか確認してください

---

**設定が完了したら、GitHub Actions で自動更新スクリプトをデプロイします。**
