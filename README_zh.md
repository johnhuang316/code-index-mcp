# 程式碼索引 MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**為大型語言模型提供智慧程式碼索引與分析**

以先進的搜尋、分析和導航功能，徹底改變 AI 對程式碼庫的理解方式。

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## 概述

程式碼索引 MCP 是一個 [模型上下文協定](https://modelcontextprotocol.io) 伺服器，架起 AI 模型與複雜程式碼庫之間的橋樑。它提供智慧索引、先進搜尋功能和詳細程式碼分析，幫助 AI 助理有效地理解和導航您的專案。

**適用於：**程式碼審查、重構、文件生成、除錯協助和架構分析。

## 快速開始

### 🚀 **推薦設定（大多數使用者）**

與任何 MCP 相容應用程式開始的最簡單方式：

**前置需求：** Python 3.10+ 和 [uv](https://github.com/astral-sh/uv)

1. **新增到您的 MCP 設定** (例如 `claude_desktop_config.json` 或 `~/.claude.json`)：
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
   > 若想在啟動時自動設定專案路徑，可在 `args` 陣列末尾加入
   > `--project-path /絕對/路徑`，效果等同於啟動後呼叫 `set_project_path`。

2. **重新啟動應用程式** – `uvx` 會自動處理安裝和執行

3. **開始使用**（向您的 AI 助理提供這些提示）：
   ```
   設定專案路徑為 /Users/dev/my-react-app
   在這個專案中找到所有 TypeScript 檔案
   搜尋「authentication」相關函數
   分析主要的 App.tsx 檔案
   ```
   *如果啟動時已提供 `--project-path`，可以略過第一個指令，伺服器會自動記住路徑。*

### Codex CLI 設定

如果你使用 Anthropic 的 Codex CLI，請在 `~/.codex/config.toml` 中加入下列伺服器設定。
Windows 的設定檔位於 `C:\Users\<you>\.codex\config.toml`：

```toml
[mcp_servers.code-index]
type = "stdio"
command = "uvx"
args = ["code-index-mcp"]
```
> 如需要啟動時自動設定專案，請把 `--project-path C:/絕對/路徑` 加到 `args`
> 清單中，與手動呼叫 `set_project_path` 的結果相同。

在 Windows 中，`uvx` 需要找到標準的使用者目錄。保留下列環境變數覆寫設定，才能讓 MCP 穩定啟動：

```toml
env = {
  HOME = "C:\\Users\\<you>",
  APPDATA = "C:\\Users\\<you>\\AppData\\Roaming",
  LOCALAPPDATA = "C:\\Users\\<you>\\AppData\\Local",
  SystemRoot = "C:\\Windows"
}
```

Linux 與 macOS 預設會提供 `HOME` 與 XDG 路徑，因此通常不需要額外的 `env` 區塊；只有在受限的容器環境或想手動調整快取／設定位置時才需要覆寫。
完整的環境變數清單請參考 [`uv` 環境變數說明](https://docs.astral.sh/uv/reference/environment/)（包含 `HOME`、`XDG_CACHE_HOME`、`XDG_CONFIG_HOME`、`APPDATA` 等）。


## 典型使用場景

**程式碼審查**：「找出所有使用舊 API 的地方」  
**重構協助**：「這個函數在哪裡被呼叫？」  
**學習專案**：「顯示這個 React 專案的主要元件」  
**除錯協助**：「搜尋所有錯誤處理相關的程式碼」

## 主要特性

### 🔍 **智慧搜尋與分析**
- **雙策略架構**：7 種核心語言使用專業化 Tree-sitter 解析，50+ 種檔案類型使用備用策略
- **直接 Tree-sitter 整合**：專業化語言無正則表達式備用 - 快速失敗並提供清晰錯誤訊息
- **進階搜尋**：自動偵測並使用最佳工具（ugrep、ripgrep、ag 或 grep）
- **通用檔案支援**：從進階 AST 解析到基本檔案索引的全面覆蓋
- **檔案分析**：執行 `build_deep_index` 後深入了解結構、匯入、類別、方法和複雜度指標

### 🗂️ **多語言支援**
- **7 種語言使用 Tree-sitter AST 解析**：Python、JavaScript、TypeScript、Java、Go、Objective-C、Zig
- **50+ 種檔案類型使用備用策略**：C/C++、Rust、Ruby、PHP 和所有其他程式語言
- **文件與配置檔案**：Markdown、JSON、YAML、XML 適當處理
- **網頁前端**：Vue、React、Svelte、HTML、CSS、SCSS
- **資料庫**：SQL 變體、NoSQL、存儲過程、遷移腳本
- **配置檔案**：JSON、YAML、XML、Markdown
- **[查看完整列表](#支援的檔案類型)**

### ⚡ **即時監控與自動刷新**
- **檔案監控器**：檔案變更時自動更新索引
- **跨平台**：原生作業系統檔案系統監控
- **智慧處理**：批次處理快速變更以防止過度重建
- **淺層索引更新**：監控檔案變更並維持檔案清單最新；需要符號資料時請執行 `build_deep_index`

### ⚡ **效能與效率**
- **Tree-sitter AST 解析**：原生語法解析以實現準確的符號提取
- **持久快取**：儲存索引以實現超快速的後續存取
- **智慧篩選**：智能排除建構目錄和暫存檔案
- **記憶體高效**：針對大型程式碼庫優化
- **直接依賴**：無備用機制 - 快速失敗並提供清晰錯誤訊息

## 支援的檔案類型

<details>
<summary><strong>📁 程式語言（點擊展開）</strong></summary>

**專業化 Tree-sitter 策略語言：**
- **Python** (`.py`, `.pyw`) - 完整 AST 分析，包含類別/方法提取和呼叫追蹤
- **JavaScript** (`.js`, `.jsx`, `.mjs`, `.cjs`) - ES6+ 類別和函數解析使用 Tree-sitter
- **TypeScript** (`.ts`, `.tsx`) - 完整類型感知符號提取，包含介面
- **Java** (`.java`) - 完整類別階層、方法簽名和呼叫關係
- **Go** (`.go`) - 結構方法、接收者類型和函數分析
- **Objective-C** (`.m`, `.mm`) - 類別/實例方法區分，使用 +/- 標記法
- **Zig** (`.zig`, `.zon`) - 函數和結構解析使用 Tree-sitter AST

**所有其他程式語言：**
所有其他程式語言使用 **備用解析策略**，提供基本檔案索引和元資料提取。包括：
- **系統與低階語言：** C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)、Rust (`.rs`)
- **物件導向語言：** C# (`.cs`)、Kotlin (`.kt`)、Scala (`.scala`)、Swift (`.swift`)
- **腳本與動態語言：** Ruby (`.rb`)、PHP (`.php`)、Shell (`.sh`, `.bash`)
- **以及 40+ 種檔案類型** - 全部通過備用策略處理進行基本索引

</details>

<details>
<summary><strong>🌐 網頁與前端（點擊展開）</strong></summary>

**框架與函式庫：**
- Vue (`.vue`)
- Svelte (`.svelte`)
- Astro (`.astro`)

**樣式：**
- CSS (`.css`, `.scss`, `.less`, `.sass`, `.stylus`, `.styl`)
- HTML (`.html`)

**模板：**
- Handlebars (`.hbs`, `.handlebars`)
- EJS (`.ejs`)
- Pug (`.pug`)

</details>

<details>
<summary><strong>🗄️ 資料庫與 SQL（點擊展開）</strong></summary>

**SQL 變體：**
- 標準 SQL (`.sql`, `.ddl`, `.dml`)
- 資料庫特定 (`.mysql`, `.postgresql`, `.psql`, `.sqlite`, `.mssql`, `.oracle`, `.ora`, `.db2`)

**資料庫物件：**
- 程序與函式 (`.proc`, `.procedure`, `.func`, `.function`)
- 檢視與觸發器 (`.view`, `.trigger`, `.index`)

**遷移與工具：**
- 遷移檔案 (`.migration`, `.seed`, `.fixture`, `.schema`)
- 工具特定 (`.liquibase`, `.flyway`)

**NoSQL 與現代資料庫：**
- 圖形與查詢 (`.cql`, `.cypher`, `.sparql`, `.gql`)

</details>

<details>
<summary><strong>📄 文件與配置（點擊展開）</strong></summary>

- Markdown (`.md`, `.mdx`)
- 配置 (`.json`, `.xml`, `.yml`, `.yaml`)

</details>

## 快速開始

### 🚀 **建議設定（適用於大多數使用者）**

在任何相容 MCP 的應用程式中開始使用的最簡單方法：

**先決條件：** Python 3.10+ 和 [uv](https://github.com/astral-sh/uv)

1. **新增到您的 MCP 配置**（例如 `claude_desktop_config.json` 或 `~/.claude.json`）：
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

2. **重新啟動您的應用程式** – `uvx` 會自動處理安裝和執行

### 🛠️ **開發設定**

適用於貢獻或本地開發：

1. **克隆並安裝：**
   ```bash
   git clone https://github.com/johnhuang316/code-index-mcp.git
   cd code-index-mcp
   uv sync
   ```

2. **配置本地開發：**
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

3. **使用 MCP Inspector 除錯：**
   ```bash
   npx @modelcontextprotocol/inspector uv run code-index-mcp
   ```

<details>
<summary><strong>替代方案：手動 pip 安裝</strong></summary>

如果您偏好傳統的 pip 管理：

```bash
pip install code-index-mcp
```

然後配置：
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


## 可用工具

### 🏗️ **專案管理**
| 工具 | 描述 |
|------|------|
| **`set_project_path`** | 為專案目錄初始化索引 |
| **`refresh_index`** | 在檔案變更後重建淺層檔案索引 |
| **`build_deep_index`** | 產生供深度分析使用的完整符號索引 |
| **`get_settings_info`** | 檢視目前專案配置和狀態 |

*需要符號層級資料時，請執行 `build_deep_index`；預設的淺層索引提供快速檔案探索。*

### 🔍 **搜尋與探索**
| 工具 | 描述 |
|------|------|
| **`search_code_advanced`** | 智慧搜尋，支援正規表達式、模糊匹配和檔案篩選，預設每頁回傳 10 筆結果，可透過 `max_results` 與 `start_index` 調整 |
| **`find_files`** | 使用萬用字元模式尋找檔案（例如 `**/*.py`） |
| **`get_file_summary`** | 分析檔案結構、函式、匯入和複雜度（需要深度索引） |

### 🔄 **監控與自動刷新**
| 工具 | 描述 |
|------|------|
| **`get_file_watcher_status`** | 檢查檔案監控器狀態和配置 |
| **`configure_file_watcher`** | 啟用/停用自動刷新並配置設定 |

### 🛠️ **系統與維護**
| 工具 | 描述 |
|------|------|
| **`create_temp_directory`** | 設定索引資料的儲存目錄 |
| **`check_temp_directory`** | 驗證索引儲存位置和權限 |
| **`clear_settings`** | 重設所有快取資料和配置 |
| **`refresh_search_tools`** | 重新偵測可用的搜尋工具（ugrep、ripgrep 等） |

## 使用範例

### 🎯 **快速開始工作流程**

**1. 初始化您的專案**
```
將專案路徑設定為 /Users/dev/my-react-app
```
*自動索引您的程式碼庫並建立可搜尋的快取*

**2. 探索專案結構**
```
在 src/components 中尋找所有 TypeScript 元件檔案
```
*使用：`find_files`，模式為 `src/components/**/*.tsx`*

**3. 分析關鍵檔案**
```
給我 src/api/userService.ts 的摘要
```
*使用：`get_file_summary` 顯示函式、匯入和複雜度*
*提示：若收到 `needs_deep_index` 回應，請先執行 `build_deep_index`。*

### 🔍 **進階搜尋範例**

<details>
<summary><strong>程式碼模式搜尋</strong></summary>

```
使用正規表達式搜尋所有符合 "get.*Data" 的函式呼叫
```
*找到：`getData()`、`getUserData()`、`getFormData()` 等*

</details>

<details>
<summary><strong>模糊函式搜尋</strong></summary>

```
使用 'authUser' 的模糊搜尋尋找驗證相關函式
```
*匹配：`authenticateUser`、`authUserToken`、`userAuthCheck` 等*

</details>

<details>
<summary><strong>特定語言搜尋</strong></summary>

```
只在 Python 檔案中搜尋 "API_ENDPOINT"
```
*使用：`search_code_advanced`，`file_pattern: "*.py"`（預設回傳 10 筆；使用 `max_results` 擴充或 `start_index` 換頁）*

</details>

<details>
<summary><strong>自動刷新配置</strong></summary>

```
配置檔案變更時的自動索引更新
```
*使用：`configure_file_watcher` 啟用/停用監控並設定防抖時間*

</details>

<details>
<summary><strong>專案維護</strong></summary>

```
我新增了新元件，請重新整理專案索引
```
*使用：`refresh_index` 更新可搜尋的快取*

</details>

## 故障排除

### 🔄 **自動刷新無法運作**

如果檔案變更時自動索引更新無法運作，請嘗試：
- `pip install watchdog`（可能解決環境隔離問題）
- 使用手動刷新：在檔案變更後呼叫 `refresh_index` 工具
- 檢查檔案監視器狀態：使用 `get_file_watcher_status` 驗證監控是否處於活動狀態

## 開發與貢獻

### 🔧 **從原始碼建構**
```bash
git clone https://github.com/johnhuang316/code-index-mcp.git
cd code-index-mcp
uv sync
uv run code-index-mcp
```

### 🐛 **除錯**
```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

### 🤝 **貢獻**
歡迎貢獻！請隨時提交拉取請求。

---

### 📜 **授權條款**
[MIT 授權條款](LICENSE)

### 🌐 **翻譯**
- [English](README.md)
- [日本語](README_ja.md)
