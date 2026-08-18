# 設計文件：修復 #88 — tree-sitter byte offset 被當成字元 offset 使用

- 日期：2026-07-27
- Issue：[#88](https://github.com/johnhuang316/code-index-mcp/issues/88)（含 2026-07-22 kajiyap 的補充留言）
- 範圍：修程式碼 + 回歸測試。不含 PR、issue 回覆、發版（由使用者另行決定）。

## 問題

tree-sitter 解析時吃的是 UTF-8 bytes，回報的 `node.start_byte` / `node.end_byte` 是 **byte 偏移**；但多個語言策略拿這些偏移直接切 Python `str`（**字元**索引）。檔案中每出現一個多位元組字元（中文註解、`é`、`—`、`→` 等），之後所有符號名稱的切割位置就累積偏移，導致：

- 符號名稱亂碼（`greet` → `(): s`）
- `get_symbol_body` 找不到符號
- Zig 策略連行號都算錯（它用 byte 偏移去 str 裡數換行）
- 對任何含非 ASCII 字元的 codebase，符號級索引實質不可用

## 根因與核心規則

檔案在系統中有三種形態：磁碟原始 bytes →（`errors="ignore"` decode）→ `str` →（`encode('utf8')`）→ 餵給 parser 的 bytes。tree-sitter 的座標**只對第三種形態有效**。

修復遵守一條規則，全專案無例外：

> **餵給 `parser.parse()` 的那份 bytes，就是所有切片使用的 bytes。**
> （量與切用同一把尺。）

每個策略本來就會 encode 一次供解析使用，只是用完即丟；修法是留住這份 bytes 重複使用，因此**零額外效能成本**。

## 已驗證的影響範圍（master @ 5e8d5fc）

| 檔案 | 錯誤切片處 | 備註 |
|---|---|---|
| `base_strategy.py` | `_safe_extract_text`（L88）、`_extract_line_number`（L80） | 僅 zig 呼叫 |
| `typescript_strategy.py` | 15 處（L200, 202, 240, 245, 297, 309, 346, 358, 396, 425, 436, 443, 450, 457, 462） | 比 issue 留言列的 6 處多 |
| `java_strategy.py` | 7 處（L152, 166, 172, 176, 181, 193, 196） | |
| `javascript_strategy.py` | 3 處（L227, 478, 481） | 無 context class，content 以參數傳遞 |
| `kotlin_strategy.py` | 2 處（L218, 227）；另 L189, 231 傳 str 進 union 簽名走每次重編碼的慢速分支 | 已有正確的 `_slice_bytes`（L412）與 `content_bytes` |
| `zig_strategy.py` | 經由 base helper 共 5 處（3 處文字抽取：L67, 92, 99；2 處行號：L60, 74） | issue 原始回報場景 |

**不受影響**：`csharp`、`rust`（已為 bytes-first 寫法）；`go`、`objective_c`、`python`、`fallback`（regex/逐行處理，不用 tree-sitter offset）。

## 方案決策

採 **方案 B：`_slice_bytes` 上提至 base、每檔 encode 一次**。

否決的替代方案：

- **A（issue 原提案）**：`_safe_extract_text` 每次呼叫重新 encode 整檔再切。正確但每個符號付 O(檔案大小) 編碼成本，且保留五份重複 context class 與易誤用的 str 簽名，同類 bug 容易復發。
- **C（順勢統一五套 context class）**：結構最徹底，但會觸碰三個目前正確運作的策略（csharp/rust/kotlin），bugfix 的風險半徑過大。列為後續重構候選，不在此次範圍。

## 設計細節

### `base_strategy.py`

新增（bytes-only 簽名，不收 str——union 簽名正是 kotlin 混用出 bug 的溫床）：

```python
def _slice_bytes(self, content_bytes: bytes, start: int, end: int) -> str:
    start = max(0, min(start, len(content_bytes)))
    end = max(0, min(end, len(content_bytes)))
    if start >= end:
        return ""
    return content_bytes[start:end].decode("utf8", errors="ignore")

def _line_at_byte(self, content_bytes: bytes, offset: int) -> int:
    return content_bytes[:max(0, min(offset, len(content_bytes)))].count(b"\n") + 1
```

刪除 `_safe_extract_text` 與 `_extract_line_number`：遷移後全 repo 呼叫者歸零；其「str + byte offset」簽名即混淆原型，留存會誘導新策略重蹈覆轍。此為套件內部 protected method，無對外相容性包袱。

### 各策略變更

- **typescript**：`content_bytes = content.encode('utf8')` 一次；`parser.parse(content_bytes)`；`TraversalContext`（L465）加 `content_bytes` 欄位；15 處切片改 `self._slice_bytes(context.content_bytes, ...)`；L436–462 收 `content: str` 的 helper 改收 bytes。
- **java**：同 typescript 模式（`TraversalContext` 在 L200），7 處改寫。
- **javascript**：encode 一次；bytes 以參數隨 traversal 傳遞；3 處改寫。
- **kotlin**：L218、L227 改走 `_slice_bytes(context.content_bytes, ...)`；L189、L231 改傳 bytes（脫離慢速分支）；刪除本地 `_slice_bytes`（L412），繼承 base 版。
- **zig**：encode 一次並以參數傳入 traversal；行號改 `node.start_point[0] + 1`（與既有 `end_line = node.end_point[0] + 1` 對稱，tree-sitter 原生提供）；3 處文字抽取（L67, 92, 99）改 `_slice_bytes`。
- **csharp**（條件性）：本地 `_slice_bytes`（L497）若語意與 base 版完全一致則刪除改繼承（呼叫點零修改）；有差異則保留不動。

### 錯誤處理

- 切片座標越界 → clamp；start ≥ end → 空字串；與 kotlin 現行行為一致，不拋例外。
- `decode(errors="ignore")` 為保險絲：tree-sitter 節點邊界理論上必落在完整 UTF-8 字元邊界。
- 讀檔路徑（`json_index_builder.py` 的 `errors="ignore"`）**刻意不動**：核心規則已使切片正確性與檔案編碼好壞脫鉤；改動讀檔會影響「哪些檔案可被索引」的既有行為，超出範圍。
- 不新增錯誤攔截層：策略失敗時上層既有 fallback（退回純文字模式）維持原樣。

### 測試計畫

位置與寫法沿用 `tests/strategies/test_*_discovery.py` 既有模式。

**雙胞胎檔案測試**（核心手法）：每語言一對內容相同、僅其一在註解塞入多位元組字元（`é`、`—`、中文）的測試檔，斷言兩者解析出的符號名稱與行號完全一致。

| 測試 | 涵蓋 |
|---|---|
| TypeScript 雙胞胎 | 直接採用 issue 留言的 `greet` / `Cafés — açúcar` 重現案例 |
| JavaScript、Java、Kotlin 雙胞胎 | 各自修改處 |
| Zig 雙胞胎 | 符號名稱 + **行號**（唯一行號也錯的策略） |
| `_slice_bytes` 單元測試 | 越界、start ≥ end、空輸入 |
| 既有全套測試 | 確保 csharp/rust/kotlin 等未回歸 |

## 成功標準

1. 雙胞胎測試全綠：非 ASCII 檔案的符號名稱、行號與 ASCII 對照組完全一致。
2. 既有測試套件全數通過。
3. `grep -rn "content\[.*start_byte" src/` 與 str 切片同型式的搜尋結果歸零（除 bytes 切片外無殘留）。
4. 全 repo 不再存在 `_safe_extract_text` / `_extract_line_number` 呼叫。

## 明確不做（Non-goals）

- 開 PR、回覆 issue #88、發版 PyPI（使用者另行決定）。
- 統一五套 context class（後續重構候選）。
- 更動讀檔／編碼偵測行為。
- 支援非 UTF-8 原始編碼的精確還原（`errors="ignore"` 現況維持）。
