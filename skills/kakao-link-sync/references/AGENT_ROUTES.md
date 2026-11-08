# AI 에이전트가 직접 수행하는 경로 (Claude Cowork / Claude Code)

데미안이 원한 "AI가 컴퓨터를 열어서 알아서 긁어오는" 방식입니다. 세 가지 수준이 있고, 아래로 갈수록 사람 개입이 줄어듭니다.

## 수준 1. Cowork 예약 작업 + 컴퓨터 사용 (가장 쉬움, 느림)
Claude Desktop → Cowork → 예약 작업(Scheduled task) 에 아래 프롬프트를 매일 1회로 등록.
컴퓨터 사용(Computer use) 베타를 설정 → 기능 에서 켜 두어야 합니다. (Pro/Max, macOS·Windows 모두 지원)

```
매일 아침 루틴: 카카오톡 '나와의 채팅' 링크 동기화.
1. 카카오톡 PC 앱을 열고 '나와의 채팅'(내 이름 Demian 임정훈) 방을 연다.
2. 방의 ≡ 메뉴 → 대화 내용 → 대화 내보내기 로 txt 를 "00 Claude/2026-11-07_카톡링크정리/inbox/" 에 저장한다.
   (메뉴 위치가 다르면 화면을 보고 찾고, 못 찾으면 Ctrl+S 를 시도한다. Esc 와 Ctrl+F 는 누르지 않는다.)
3. 터미널에서 실행: python kakao_sync.py --source file --file "<방금 저장한 txt>" --titles
4. 로그(kakao_sync.log)의 '새 링크 N개'와 등록 결과를 요약해 보고한다. 실패하면 어느 단계에서 막혔는지 스크린샷과 함께 알린다.
```

## 수준 2. Claude Code + kakaotalk-mcp (Windows, 창 조작 없이 MCP 도구로 읽기)
```
git clone https://github.com/jjround/kakaotalk-mcp
cd kakaotalk-mcp && uv sync
uv run kakaotalk-mcp-diag "Demian 임정훈" --read      # 나와의 채팅 읽기 진단
claude mcp add kakaotalk -- uv --directory C:\경로\kakaotalk-mcp run kakaotalk-mcp
```
이후 Claude Code 에서: "kakaotalk 의 read_messages(room='Demian 임정훈', last_n=300) 로 읽은 뒤 URL 만 뽑아
Notion 🔗 카톡 링크 보관함에 없는 것만 등록해 줘" — Notion MCP 가 연결돼 있으면 토큰 없이도 끝납니다.
(MIT, 2026-11-05 커밋. 창이 열려 있어야 하고, 로드된 메시지만 읽으며, 503자 넘는 긴 메시지는 잘립니다.)

## 수준 3. 완전 무인 (이 폴더의 스크립트 + OS 스케줄러) ← 권장 기본값
- Windows: `scheduler/register_windows_task.ps1` 1회 실행 → 매일 09/21시 `kakao_sync.py --source windows`
- Mac: `scheduler/com.flow.kakaosync.plist` 설치 → 매일 09/21시 `kakao_pull_mac.sh` (kakaocli 로 DB 직접 읽기, 창 조작 없음)
- 결과는 Notion 보관함에 '미확인' 상태로 쌓이고, 데미안은 주 1회 보관함만 훑으면 됩니다.
- 수준 1~2 는 수준 3 이 깨졌을 때(카톡 업데이트로 창 구조 변경 등) 복구용 백업 경로로 두세요.

## Notion 통합 토큰 만들기 (수준 3 에 필요, 2분)
1. https://www.notion.so/profile/integrations → 새 API 통합 → 이름 "KakaoLinkSync", 권한: 콘텐츠 읽기/삽입/업데이트
2. 토큰(secret_… 또는 ntn_…) 복사
3. Notion 에서 🔗 카톡 링크 보관함 페이지 → ··· → 연결 → KakaoLinkSync 추가
4. Windows: register 스크립트가 묻는 칸에 입력 / Mac: `security add-generic-password -s notion-token -a $USER -w "<토큰>"`
