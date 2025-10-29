# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**大規模言語モデルのためのインテリジェントコードインデックス作成と解析**

高度な検索、解析、ナビゲーション機能で、AIのコードベース理解を根本的に変革します。

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## 概要

Code Index MCPは、AIモデルと複雑なコードベースの橋渡しをする[Model Context Protocol](https://modelcontextprotocol.io)サーバーです。インテリジェントなインデックス作成、高度な検索機能、詳細なコード解析を提供し、AIアシスタントがプロジェクトを効果的に理解しナビゲートできるようにします。

**最適な用途：**コードレビュー、リファクタリング、ドキュメント生成、デバッグ支援、アーキテクチャ解析。

## クイックスタート

### 🚀 **推奨セットアップ（ほとんどのユーザー）**

任意MCP対応アプリケーションで開始する最も簡単な方法：

**前提条件：** Python 3.10+ および [uv](https://github.com/astral-sh/uv)

1. **MCP設定に追加** (例：`claude_desktop_config.json` または `~/.claude.json`)：
   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uvx",
         "args": ["code-index-mcp"]
       }
     }
   }
   ```

   > 起動時にプロジェクトを自動設定したい場合は、`args` 配列の末尾に
   > `--project-path /absolute/path/to/repo` を追加してください。これで起動直後に
   > `set_project_path` を呼び出した場合と同じ状態になります。
2. **アプリケーションを再起動** – `uvx`がインストールと実行を自動処理

3. **使用開始**（AIアシスタントにこれらのプロンプトを与える）：
   ```
   プロジェクトパスを/Users/dev/my-react-appに設定
   このプロジェクトのすべてのTypeScriptファイルを検索
   「authentication」関連関数を検索
   メインのApp.tsxファイルを解析
   ```
   *起動時に `--project-path` を付けた場合は、最初のコマンドは不要です。サーバーが既にパスを認識しています。*

### Codex CLI 設定

Anthropic の Codex CLI を使用している場合は、`~/.codex/config.toml` に次のサーバー設定を追加します。
Windows では `C:\Users\<you>\.codex\config.toml` に保存されています。

```toml
[mcp_servers.code-index]
type = "stdio"
command = "uvx"
args = ["code-index-mcp"]
```
> 起動時にプロジェクトを設定したい場合は、`args` リストに `--project-path C:/absolute/path/to/repo` を追加してください。
> これは起動後に `set_project_path` ツールを呼び出すのと同じ効果です。

Windows の `uvx` は標準ユーザープロファイルディレクトリが必要です。
MCP を安定して起動するために、同じブロックに次の環境変数を残してください。

```toml
env = {
  HOME = "C:\\Users\\<you>",
  APPDATA = "C:\\Users\\<you>\\AppData\\Roaming",
  LOCALAPPDATA = "C:\\Users\\<you>\\AppData\\Local",
  SystemRoot = "C:\\Windows"
}
```

Linux と macOS では OS が `HOME` や XDG 系のパスを標準で公開しているため、通常は `env` セクションは不要です。
制限されたコンテナで実行する場合やキャッシュ／設定の保存先を手動で変更したいときだけ上書きしてください。
環境変数の一覧は [`uv` の環境変数リファレンス](https://docs.astral.sh/uv/reference/environment/)（`HOME`、`XDG_CACHE_HOME`、`XDG_CONFIG_HOME`、`APPDATA` など）を参照してください。


## 一般的な使用ケース

**コードレビュー**：「旧いAPIを使用しているすべての箇所を検索」  
**リファクタリング支援**：「この関数はどこで呼ばれている？」  
**プロジェクト学習**：「このReactプロジェクトの主要コンポーネントを表示」  
**デバッグ支援**：「エラーハンドリング関連のコードをすべて検索」

## 主な機能

### 🔍 **インテリジェント検索・解析**
- **二重戦略アーキテクチャ**：7つのコア言語に特化したTree-sitter解析、50+ファイルタイプにフォールバック戦略
- **直接Tree-sitter統合**：特化言語で正規表現フォールバックなし - 明確なエラーメッセージで高速フェイル
- **高度な検索**：最適なツール（ugrep、ripgrep、ag、grep）を自動検出・使用
- **汎用ファイルサポート**：高度なAST解析から基本ファイルインデックスまでの包括的カバレッジ
- **ファイル解析**：`build_deep_index` 実行後に構造、インポート、クラス、メソッド、複雑度メトリクスを深く把握

### 🗂️ **多言語サポート**
- **7言語でTree-sitter AST解析**：Python、JavaScript、TypeScript、Java、Go、Objective-C、Zig
- **50+ファイルタイプでフォールバック戦略**：C/C++、Rust、Ruby、PHPおよびすべての他のプログラミング言語
- **文書・設定ファイル**：Markdown、JSON、YAML、XML適切な処理
- **Webフロントエンド**：Vue、React、Svelte、HTML、CSS、SCSS
- **データベース**：SQLバリアント、NoSQL、ストアドプロシージャ、マイグレーション
- **設定ファイル**：JSON、YAML、XML、Markdown
- **[完全なリストを表示](#サポートされているファイルタイプ)**

### ⚡ **リアルタイム監視・自動更新**
- **ファイルウォッチャー**：ファイル変更時の自動インデックス更新
- **クロスプラットフォーム**：ネイティブOSファイルシステム監視
- **スマート処理**：急速な変更をバッチ処理して過度な再構築を防止
- **浅いインデックス更新**：ファイル変更を監視して最新のファイル一覧を維持し、シンボルが必要な場合は `build_deep_index` を実行

### ⚡ **パフォーマンス・効率性**
- **Tree-sitter AST解析**：正確なシンボル抽出のためのネイティブ構文解析
- **永続キャッシュ**：超高速な後続アクセスのためのインデックス保存
- **スマートフィルタリング**：ビルドディレクトリと一時ファイルのインテリジェント除外
- **メモリ効率**：大規模コードベース向けに最適化
- **直接依存関係**：フォールバック機構なし - 明確なエラーメッセージで高速フェイル

## サポートされているファイルタイプ

<details>
<summary><strong>📁 プログラミング言語（クリックで展開）</strong></summary>

**特化Tree-sitter戦略言語：**
- **Python** (`.py`, `.pyw`) - クラス/メソッド抽出と呼び出し追跡を含む完全AST解析
- **JavaScript** (`.js`, `.jsx`, `.mjs`, `.cjs`) - Tree-sitterを使用したES6+クラスと関数解析
- **TypeScript** (`.ts`, `.tsx`) - インターフェースを含む完全な型認識シンボル抽出
- **Java** (`.java`) - 完全なクラス階層、メソッドシグネチャ、呼び出し関係
- **Go** (`.go`) - 構造体メソッド、レシーバータイプ、関数解析
- **Objective-C** (`.m`, `.mm`) - +/-記法を使用したクラス/インスタンスメソッド区別
- **Zig** (`.zig`, `.zon`) - Tree-sitter ASTを使用した関数と構造体解析

**すべての他のプログラミング言語：**
すべての他のプログラミング言語は**フォールバック解析戦略**を使用し、基本ファイルインデックスとメタデータ抽出を提供します。これには以下が含まれます：
- **システム・低レベル言語：** C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)、Rust (`.rs`)
- **オブジェクト指向言語：** C# (`.cs`)、Kotlin (`.kt`)、Scala (`.scala`)、Swift (`.swift`)
- **スクリプト・動的言語：** Ruby (`.rb`)、PHP (`.php`)、Shell (`.sh`, `.bash`)
- **および40+ファイルタイプ** - すべてフォールバック戦略による基本インデックス処理

</details>

<details>
<summary><strong>🌐 Web・フロントエンド（クリックで展開）</strong></summary>

**フレームワーク・ライブラリ：**
- Vue (`.vue`)
- Svelte (`.svelte`)
- Astro (`.astro`)

**スタイリング：**
- CSS (`.css`, `.scss`, `.less`, `.sass`, `.stylus`, `.styl`)
- HTML (`.html`)

**テンプレート：**
- Handlebars (`.hbs`, `.handlebars`)
- EJS (`.ejs`)
- Pug (`.pug`)

</details>

<details>
<summary><strong>🗄️ データベース・SQL（クリックで展開）</strong></summary>

**SQL バリアント：**
- 標準SQL (`.sql`, `.ddl`, `.dml`)
- データベース固有 (`.mysql`, `.postgresql`, `.psql`, `.sqlite`, `.mssql`, `.oracle`, `.ora`, `.db2`)

**データベースオブジェクト：**
- プロシージャ・関数 (`.proc`, `.procedure`, `.func`, `.function`)
- ビュー・トリガー (`.view`, `.trigger`, `.index`)

**マイグレーション・ツール：**
- マイグレーションファイル (`.migration`, `.seed`, `.fixture`, `.schema`)
- ツール固有 (`.liquibase`, `.flyway`)

**NoSQL・モダンDB：**
- グラフ・クエリ (`.cql`, `.cypher`, `.sparql`, `.gql`)

</details>

<details>
<summary><strong>📄 ドキュメント・設定（クリックで展開）</strong></summary>

- Markdown (`.md`, `.mdx`)
- 設定 (`.json`, `.xml`, `.yml`, `.yaml`)

</details>

## クイックスタート

### 🚀 **推奨セットアップ（ほとんどのユーザー向け）**

任意のMCP対応アプリケーションで開始する最も簡単な方法：

**前提条件：** Python 3.10+ と [uv](https://github.com/astral-sh/uv)

1. **MCP設定に追加**（例：`claude_desktop_config.json` または `~/.claude.json`）：
   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uvx",
         "args": ["code-index-mcp"]
       }
     }
   }
   ```

2. **アプリケーションを再起動** – `uvx` が自動的にインストールと実行を処理

### 🛠️ **開発セットアップ**

貢献やローカル開発用：

1. **クローンとインストール：**
   ```bash
   git clone https://github.com/johnhuang316/code-index-mcp.git
   cd code-index-mcp
   uv sync
   ```

2. **ローカル開発用設定：**
   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uv",
         "args": ["run", "code-index-mcp"]
       }
     }
   }
   ```

3. **MCP Inspectorでデバッグ：**
   ```bash
   npx @modelcontextprotocol/inspector uv run code-index-mcp
   ```

<details>
<summary><strong>代替案：手動pipインストール</strong></summary>

従来のpip管理を好む場合：

```bash
pip install code-index-mcp
```

そして設定：
```json
{
  "mcpServers": {
    "code-index": {
      "command": "code-index-mcp",
      "args": []
    }
  }
}
```

</details>


## 利用可能なツール

### 🏗️ **プロジェクト管理**
| ツール | 説明 |
|--------|------|
| **`set_project_path`** | プロジェクトディレクトリのインデックス作成を初期化 |
| **`refresh_index`** | ファイル変更後に浅いファイルインデックスを再構築 |
| **`build_deep_index`** | 深い解析で使う完全なシンボルインデックスを生成 |
| **`get_settings_info`** | 現在のプロジェクト設定と状態を表示 |

*シンボルレベルのデータが必要な場合は `build_deep_index` を実行してください。デフォルトの浅いインデックスは高速なファイル探索を担います。*

### 🔍 **検索・発見**
| ツール | 説明 |
|--------|------|
| **`search_code_advanced`** | 正規表現、ファジーマッチング、ファイルフィルタリング対応のスマート検索 |
| **`find_files`** | globパターンを使用したファイル検索（例：`**/*.py`） |
| **`get_file_summary`** | ファイル構造、関数、インポート、複雑度の解析（深いインデックスが必要） |

### 🔄 **監視・自動更新**
| ツール | 説明 |
|--------|------|
| **`get_file_watcher_status`** | ファイルウォッチャーの状態と設定を確認 |
| **`configure_file_watcher`** | 自動更新の有効化/無効化と設定の構成 |

### 🛠️ **システム・メンテナンス**
| ツール | 説明 |
|--------|------|
| **`create_temp_directory`** | インデックスデータの保存ディレクトリをセットアップ |
| **`check_temp_directory`** | インデックス保存場所と権限を確認 |
| **`clear_settings`** | すべてのキャッシュデータと設定をリセット |
| **`refresh_search_tools`** | 利用可能な検索ツール（ugrep、ripgrep等）を再検出 |

## 使用例

### 🎯 **クイックスタートワークフロー**

**1. プロジェクトの初期化**
```
プロジェクトパスを /Users/dev/my-react-app に設定してください
```
*コードベースを自動インデックス作成し、検索可能なキャッシュを構築*

**2. プロジェクト構造の探索**
```
src/components で全てのTypeScriptコンポーネントファイルを見つけてください
```
*使用ツール：`find_files`、パターン `src/components/**/*.tsx`*

**3. キーファイルの解析**
```
src/api/userService.ts の要約を教えてください
```
*使用ツール：`get_file_summary` で関数、インポート、複雑度を表示*
*ヒント：`needs_deep_index` が返った場合は `build_deep_index` を先に実行してください。*

### 🔍 **高度な検索例**

<details>
<summary><strong>コードパターン検索</strong></summary>

```
正規表現を使って "get.*Data" にマッチする全ての関数呼び出しを検索してください
```
*発見：`getData()`、`getUserData()`、`getFormData()` など*

</details>

<details>
<summary><strong>ファジー関数検索</strong></summary>

```
'authUser' でファジー検索して認証関連の関数を見つけてください
```
*マッチ：`authenticateUser`、`authUserToken`、`userAuthCheck` など*

</details>

<details>
<summary><strong>言語固有検索</strong></summary>

```
Pythonファイルのみで "API_ENDPOINT" を検索してください
```
*使用ツール：`search_code_advanced`、`file_pattern: "*.py"`*

</details>

<details>
<summary><strong>自動更新設定</strong></summary>

```
ファイル変更時の自動インデックス更新を設定してください
```
*使用ツール：`configure_file_watcher` で監視の有効化/無効化とデバウンス時間を設定*

</details>

<details>
<summary><strong>プロジェクトメンテナンス</strong></summary>

```
新しいコンポーネントを追加したので、プロジェクトインデックスを更新してください
```
*使用ツール：`refresh_index` で検索可能なキャッシュを更新*

</details>

## トラブルシューティング

### 🔄 **自動リフレッシュが動作しない**

ファイル変更時に自動インデックス更新が動作しない場合、以下を試してください：
- `pip install watchdog`（環境分離の問題を解決する可能性があります）
- 手動リフレッシュを使用：ファイル変更後に `refresh_index` ツールを呼び出す
- ファイルウォッチャーステータスを確認：`get_file_watcher_status` を使用して監視がアクティブかどうかを確認

## 開発・貢献

### 🔧 **ソースからのビルド**
```bash
git clone https://github.com/johnhuang316/code-index-mcp.git
cd code-index-mcp
uv sync
uv run code-index-mcp
```

### 🐛 **デバッグ**
```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

### 🤝 **貢献**
貢献を歓迎します！お気軽にプルリクエストを提出してください。

---

### 📜 **ライセンス**
[MIT License](LICENSE)

### 🌐 **翻訳**
- [English](README.md)
- [繁體中文](README_zh.md)
