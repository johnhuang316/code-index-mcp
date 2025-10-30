# 코드 인덱스 MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**대규모 언어 모델을 위한 지능형 코드 인덱싱과 분석**

고급 검색, 정밀 분석, 유연한 탐색 기능으로 AI가 코드베이스를 이해하고 활용하는 방식을 혁신하세요.

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## 개요

Code Index MCP는 [Model Context Protocol](https://modelcontextprotocol.io) 기반 MCP 서버로, AI 어시스턴트와 복잡한 코드베이스 사이를 연결합니다. 빠른 인덱싱, 강력한 검색, 정밀한 코드 분석을 제공하여 AI가 프로젝트 구조를 정확히 파악하고 효과적으로 지원하도록 돕습니다.

**이럴 때 안성맞춤:** 코드 리뷰, 리팩터링, 문서화, 디버깅 지원, 아키텍처 분석

## 빠른 시작

### 🚀 **권장 설정 (대부분의 사용자)**

어떤 MCP 호환 애플리케이션에서도 몇 단계만으로 시작할 수 있습니다.

**사전 준비:** Python 3.10+ 및 [uv](https://github.com/astral-sh/uv)

1. **MCP 설정에 서버 추가** (예: `claude_desktop_config.json` 또는 `~/.claude.json`)
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

   > 시작할 때 프로젝트를 자동으로 지정하려면 `args` 배열 끝에
   > `--project-path /absolute/path/to/repo` 를 추가하세요. 이렇게 하면 시작 직후 `set_project_path` 를 호출한 것과 동일한 상태가 됩니다.
2. **애플리케이션 재시작** – `uvx`가 설치와 실행을 자동으로 처리합니다.

3. **사용 시작** (AI 어시스턴트에게 아래 프롬프트를 전달)
   ```
   프로젝트 경로를 /Users/dev/my-react-app 으로 설정해줘
   이 프로젝트에서 모든 TypeScript 파일을 찾아줘
   "authentication" 관련 함수를 검색해줘
   src/App.tsx 파일을 분석해줘
   ```
   *실행 시 `--project-path` 옵션을 사용했다면 첫 번째 명령은 건너뛰어도 됩니다. 서버가 이미 경로를 알고 있습니다.*

### Codex CLI 설정

Anthropic의 Codex CLI를 사용하는 경우 `~/.codex/config.toml`에 다음 MCP 서버 설정을 추가하세요.
Windows에서는 `C:\Users\<you>\.codex\config.toml`에 위치합니다.

```toml
[mcp_servers.code-index]
type = "stdio"
command = "uvx"
args = ["code-index-mcp"]
```
> 실행 시 프로젝트를 자동으로 지정하려면 `args` 리스트에 `--project-path C:/absolute/path/to/repo` 를 추가하세요.
> 이는 이후에 `set_project_path` 도구를 호출하는 것과 같은 효과입니다.

Windows의 `uvx`는 기본 사용자 프로필 디렉터리가 필요합니다.
MCP가 안정적으로 시작되도록 같은 블록에 아래 환경 변수 덮어쓰기를 유지하세요.

```toml
env = {
  HOME = "C:\Users\<you>",
  APPDATA = "C:\Users\<you>\AppData\Roaming",
  LOCALAPPDATA = "C:\Users\<you>\AppData\Local",
  SystemRoot = "C:\Windows"
}
```

Linux와 macOS는 운영체제가 `HOME`과 XDG 경로를 기본으로 제공하므로 대부분 별도의 `env` 섹션이 필요하지 않습니다.
제한된 컨테이너에서 실행하거나 캐시/설정 위치를 수동으로 바꾸고 싶을 때만 덮어쓰면 됩니다.
환경 변수 전체 목록은 [`uv` 환경 변수 문서](https://docs.astral.sh/uv/reference/environment/) (`HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, `APPDATA` 등)를 참고하세요.


## 대표 사용 사례

**코드 리뷰:** "예전 API를 사용하는 부분을 모두 찾아줘"
**리팩터링 지원:** "이 함수는 어디에서 호출되나요?"
**프로젝트 학습:** "이 React 프로젝트의 핵심 컴포넌트를 보여줘"
**디버깅:** "에러 처리 로직이 있는 파일을 찾아줘"

## 주요 기능

### 🧠 **지능형 검색과 분석**
- **듀얼 전략 아키텍처:** 7개 핵심 언어는 전용 tree-sitter 파서를 사용하고, 그 외 50+ 파일 형식은 폴백 전략으로 처리
- **직접 Tree-sitter 통합:** 특화 언어에 정규식 폴백 없음 – 문제 시 즉시 실패하고 명확한 오류 메시지 제공
- **고급 검색:** ugrep, ripgrep, ag, grep 중 최적의 도구를 자동 선택해 활용
- **범용 파일 지원:** 정교한 AST 분석부터 기본 파일 인덱싱까지 폭넓게 커버
- **파일 분석:** `build_deep_index` 실행 후 구조, 임포트, 클래스, 메서드, 복잡도 지표를 심층적으로 파악

### 🗂️ **다중 언어 지원**
- **Tree-sitter AST 분석(7종):** Python, JavaScript, TypeScript, Java, Go, Objective-C, Zig
- **폴백 전략(50+ 형식):** C/C++, Rust, Ruby, PHP 등 대부분의 프로그래밍 언어 지원
- **문서 및 설정 파일:** Markdown, JSON, YAML, XML 등 상황에 맞는 처리
- **웹 프론트엔드:** Vue, React, Svelte, HTML, CSS, SCSS
- **데이터 계층:** SQL, NoSQL, 스토어드 프로시저, 마이그레이션 스크립트
- **구성 파일:** JSON, YAML, XML, Markdown
- **[지원 파일 전체 목록 보기](#지원-파일-형식)**

### 🔄 **실시간 모니터링 & 자동 새로고침**
- **파일 워처:** 파일 변경 시 자동으로 얕은 인덱스(파일 목록) 갱신
- **크로스 플랫폼:** 운영체제 기본 파일시스템 이벤트 활용
- **스마트 처리:** 빠른 변경을 묶어 과도한 재빌드를 방지
- **얕은 인덱스 갱신:** 파일 목록을 최신 상태로 유지하며, 심볼 데이터가 필요하면 `build_deep_index`를 실행

### ⚡ **성능 & 효율성**
- **Tree-sitter AST 파싱:** 정확한 심볼 추출을 위한 네이티브 구문 분석
- **지속 캐싱:** 인덱스를 저장해 이후 응답 속도를 극대화
- **스마트 필터링:** 빌드 디렉터리·임시 파일을 자동 제외
- **메모리 효율:** 대규모 코드베이스를 염두에 둔 설계
- **직접 의존성:** 불필요한 폴백 없이 명확한 오류 메시지 제공

## 지원 파일 형식

<details>
<summary><strong>💻 프로그래밍 언어 (클릭하여 확장)</strong></summary>

**전용 Tree-sitter 전략 언어:**
- **Python** (`.py`, `.pyw`) – 클래스/메서드 추출 및 호출 추적이 포함된 완전 AST 분석
- **JavaScript** (`.js`, `.jsx`, `.mjs`, `.cjs`) – ES6+ 클래스와 함수를 tree-sitter로 파싱
- **TypeScript** (`.ts`, `.tsx`) – 인터페이스를 포함한 타입 인지 심볼 추출
- **Java** (`.java`) – 클래스 계층, 메서드 시그니처, 호출 관계 분석
- **Go** (`.go`) – 구조체 메서드, 리시버 타입, 함수 분석
- **Objective-C** (`.m`, `.mm`) – 클래스/인스턴스 메서드를 +/- 표기로 구분
- **Zig** (`.zig`, `.zon`) – 함수와 구조체를 tree-sitter AST로 분석

**기타 모든 프로그래밍 언어:**
나머지 언어는 **폴백 파싱 전략**으로 기본 메타데이터와 파일 인덱싱을 제공합니다. 예:
- **시스템/저수준:** C/C++ (`.c`, `.cpp`, `.h`, `.hpp`), Rust (`.rs`)
- **객체지향:** C# (`.cs`), Kotlin (`.kt`), Scala (`.scala`), Swift (`.swift`)
- **스크립트:** Ruby (`.rb`), PHP (`.php`), Shell (`.sh`, `.bash`)
- **그 외 40+ 형식** – 폴백 전략으로 빠른 탐색 가능

</details>

<details>
<summary><strong>🌐 웹 프론트엔드 & UI</strong></summary>

- 프레임워크: Vue (`.vue`), Svelte (`.svelte`), Astro (`.astro`)
- 스타일링: CSS (`.css`, `.scss`, `.less`, `.sass`, `.stylus`, `.styl`), HTML (`.html`)
- 템플릿: Handlebars (`.hbs`, `.handlebars`), EJS (`.ejs`), Pug (`.pug`)

</details>

<details>
<summary><strong>🗄️ 데이터 계층 & SQL</strong></summary>

- **SQL 변형:** 표준 SQL (`.sql`, `.ddl`, `.dml`), 데이터베이스별 방언 (`.mysql`, `.postgresql`, `.psql`, `.sqlite`, `.mssql`, `.oracle`, `.ora`, `.db2`)
- **DB 객체:** 프로시저/함수 (`.proc`, `.procedure`, `.func`, `.function`), 뷰/트리거/인덱스 (`.view`, `.trigger`, `.index`)
- **마이그레이션 도구:** 마이그레이션 파일 (`.migration`, `.seed`, `.fixture`, `.schema`), 도구 구성 (`.liquibase`, `.flyway`)
- **NoSQL & 그래프:** 질의 언어 (`.cql`, `.cypher`, `.sparql`, `.gql`)

</details>

<details>
<summary><strong>📄 문서 & 설정 파일</strong></summary>

- Markdown (`.md`, `.mdx`)
- 구성 파일 (`.json`, `.xml`, `.yml`, `.yaml`)

</details>

## 사용 가능한 도구

### 🏗️ **프로젝트 관리**
| 도구 | 설명 |
|------|------|
| **`set_project_path`** | 프로젝트 디렉터리의 인덱스를 초기화 |
| **`refresh_index`** | 파일 변경 후 얕은 파일 인덱스를 재생성 |
| **`build_deep_index`** | 심층 분석에 사용하는 전체 심볼 인덱스를 생성 |
| **`get_settings_info`** | 현재 프로젝트 설정과 상태를 확인 |

*심볼 레벨 데이터가 필요하면 `build_deep_index`를 실행하세요. 기본 얕은 인덱스는 빠른 파일 탐색을 담당합니다.*

### 🔍 **검색 & 탐색**
| 도구 | 설명 |
|------|------|
| **`search_code_advanced`** | 정규식, 퍼지 매칭, 파일 필터링을 지원하는 스마트 검색 (기본적으로 페이지당 10개 결과 반환, `max_results`·`start_index`로 조정 가능) |
| **`find_files`** | 글롭 패턴으로 파일 찾기 (예: `**/*.py`) |
| **`get_file_summary`** | 파일 구조, 함수, 임포트, 복잡도를 분석 (심층 인덱스 필요) |

### 🔄 **모니터링 & 자동 새로고침**
| 도구 | 설명 |
|------|------|
| **`get_file_watcher_status`** | 파일 워처 상태와 구성을 확인 |
| **`configure_file_watcher`** | 자동 새로고침 설정 (활성/비활성, 지연 시간, 추가 제외 패턴) |

### 🛠️ **시스템 & 유지 관리**
| 도구 | 설명 |
|------|------|
| **`create_temp_directory`** | 인덱스 저장용 임시 디렉터리를 생성 |
| **`check_temp_directory`** | 인덱스 저장 위치와 권한을 확인 |
| **`clear_settings`** | 모든 설정과 캐시 데이터를 초기화 |
| **`refresh_search_tools`** | 사용 가능한 검색 도구를 재검색 (ugrep, ripgrep 등) |

## 사용 예시

### 🧭 **빠른 시작 워크플로**

**1. 프로젝트 초기화**
```
프로젝트 경로를 /Users/dev/my-react-app 으로 설정해줘
```
*프로젝트를 설정하고 얕은 인덱스를 생성합니다.*

**2. 프로젝트 구조 탐색**
```
src/components 안의 TypeScript 컴포넌트 파일을 모두 찾아줘
```
*사용 도구: `find_files` (`src/components/**/*.tsx`)*

**3. 핵심 파일 분석**
```
src/api/userService.ts 요약을 알려줘
```
*사용 도구: `get_file_summary` (함수, 임포트, 복잡도 표시)*
*팁: `needs_deep_index` 응답이 나오면 먼저 `build_deep_index`를 실행하세요.*

### 🔍 **고급 검색 예시**

<details>
<summary><strong>코드 패턴 검색</strong></summary>

```
"get.*Data"에 해당하는 함수 호출을 정규식으로 찾아줘
```
*예: `getData()`, `getUserData()`, `getFormData()`*

</details>

<details>
<summary><strong>퍼지 함수 검색</strong></summary>

```
'authUser'와 유사한 인증 관련 함수를 찾아줘
```
*예: `authenticateUser`, `authUserToken`, `userAuthCheck`*

</details>

<details>
<summary><strong>언어별 검색</strong></summary>

```
Python 파일에서만 "API_ENDPOINT" 를 찾아줘
```
*`search_code_advanced` + `file_pattern="*.py"` (기본 10개 결과, `max_results`로 확장하고 `start_index`로 페이지 이동)*

</details>

<details>
<summary><strong>자동 새로고침 설정</strong></summary>

```
파일 변경 시 자동으로 인덱스를 새로고침하도록 설정해줘
```
*`configure_file_watcher`로 활성화 및 지연 시간 설정*

</details>

<details>
<summary><strong>프로젝트 유지 관리</strong></summary>

```
새 컴포넌트를 추가했어. 프로젝트 인덱스를 다시 빌드해줘
```
*`refresh_index`로 빠르게 얕은 인덱스를 업데이트*

</details>

## 문제 해결

### 🔄 **자동 새로고침이 동작하지 않을 때**
- 환경 문제로 `watchdog`가 빠졌다면 설치: `pip install watchdog`
- 수동 새로고침: 변경 후 `refresh_index` 도구 실행
- 워처 상태 확인: `get_file_watcher_status` 도구로 활성 여부 점검

## 개발 & 기여

### 🛠️ **소스에서 실행하기**
```bash
git clone https://github.com/johnhuang316/code-index-mcp.git
cd code-index-mcp
uv sync
uv run code-index-mcp
```

### 🧪 **디버깅 도구**
```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

### 🤝 **기여 안내**
Pull Request를 언제든 환영합니다. 변경 사항과 테스트 방법을 함께 공유해주세요.

---

### 📄 **라이선스**
[MIT License](LICENSE)

### 🌍 **번역본**
- [English](README.md)
- [繁體中文](README_zh.md)
- [日本語](README_ja.md)
