# 카톡 '나에게 보내기' 무인 자동 수집 — 설계와 선택 (2026-11-07)

## 0. 결론 먼저
| | Windows | Mac |
|---|---|---|
| **채택 경로** | PC 카톡 창의 대화 목록 컨트롤에 Ctrl+A/C 를 보내 클립보드로 읽기 (`kakao_pull_windows.py`) | kakaocli 로 카톡 로컬 DB(SQLCipher)를 읽기 전용 복호화 (`kakao_pull_mac.sh`) |
| 창 조작 | 필요 (나와의 채팅 창이 열려 있어야 함, 최소화 금지) | **불필요** (DB 직접 읽기) |
| 권한 | 없음 (pywin32) | 전체 디스크 접근 |
| 과거 메시지 | PageUp 횟수만큼 로드 (10회 ≈ 수백 건) | 그 Mac 에서 한 번이라도 연 채팅은 DB 에 있음 |
| 깨질 위험 | 카톡 PC 업데이트로 컨트롤 클래스가 바뀌면 | 카톡 Mac 업데이트로 DB 키 유도가 바뀌면 (이슈 #14 유형) |
| 스케줄 | 작업 스케줄러 (`scheduler/register_windows_task.ps1`) | launchd (`scheduler/com.flow.kakaosync.plist`) |
| 공통 코어 | `kakao_sync.py` : 추출 → 중복 제외(로컬 상태 + Notion 조회) → Notion 보관함 등록 → 로그 | |

**순서**: Windows 를 먼저 시도 → `--list` 로 창 제목 확인 → 수집 실패(컨트롤 못 찾음) 시 Mac 경로로 전환. 둘 다 막히면 `AGENT_PROMPT.md` 수준 1(Cowork 컴퓨터 사용)이 최후 백업.

## 1. 왜 "AI 가 브라우저를 열어서"는 안 되는가
카카오톡은 **웹 버전이 없습니다.** 브라우저 자동화(Playwright 등)로 접근할 대상 자체가 없고, 카카오는 '나와의 채팅'을 읽는 공개 API 도 제공하지 않습니다(메시지 API 는 '보내기' 전용). 그래서 접근 지점은 세 곳뿐입니다. ① PC 앱의 창(Win32) ② Mac 앱의 로컬 DB ③ 사람이 쓰는 '대화 내보내기' 메뉴. 이번 설계는 ①②를 스크립트로, ③을 에이전트(Cowork 컴퓨터 사용)로 커버합니다.

## 2. 검토한 오픈소스 (2026-11-07 직접 README 확인)
| 프로젝트 | 플랫폼 | 읽기 방식 | 상태 | 판단 |
|---|---|---|---|---|
| jjround/kakaotalk-mcp | Windows | 윈도우 메시지로 Ctrl+A/C → 클립보드, 복원 | MIT, 2026-11-05 커밋, 스타 0 | 방식 검증됨. MCP 도구 5종(read_messages 등). 수준 2 에 채택 |
| ttl0988k-cmyk/kakaotalk-automation | Windows | 동일 + PageUp 으로 과거 로드, OCR 폴백 | MIT, 2026-11-05 | 실측치 유용(PageUp 3회=100건, 503자 절단). 본 스크립트 설계에 반영 |
| silver-flight-group/kakaocli | Mac | 로컬 SQLCipher DB 읽기 전용 복호화 | MIT, 스타 183, 마지막 커밋 2026-03-30, 열린 이슈 4 | Mac 경로에 채택. 사용자 ID 자동감지 실패 이슈 있음 → `kakaocli auth` 로 먼저 확인 |
| yoonjechoi/kakao-live | Mac | kakaocli 위에 Claude Code 플러그인 | MIT, 2026-10-18 | 실시간 봇용. 링크 수집엔 과함 |
| bssm-oss/katalk-ax | Mac | 접근성 API | 라이선스 불명 | **읽기 기능 없음** (보내기 전용) → 제외 |

## 3. 파일 구성
```
kakao_links.py            링크 추출 공통 모듈 (PC/모바일 내보내기 형식, UTM 제거, 분류)
kakao_sync.py             동기화 코어 (--source windows|mac|file) → Notion 등록
kakao_pull_windows.py     Windows 수집기 (창 → 클립보드)
kakao_pull_mac.sh         Mac 수집기 (kakaocli)
scheduler/                작업 스케줄러 등록 스크립트, launchd plist
AGENT_PROMPT.md           Cowork/Claude Code 에이전트 경로 3수준 + Notion 토큰 발급법
README.md                 1차 가이드(수동 내보내기 경로, 원인 분석)
```

## 4. 설치 (Windows, 10분)
```powershell
pip install pywin32
python kakao_pull_windows.py --list                 # 창 제목 확인 (나와의 채팅 = 내 이름)
python kakao_pull_windows.py --room "Demian 임정훈" --pageup 5 --out test.txt   # 수집 테스트
python kakao_sync.py --source file --file test.txt --dry-run                      # 추출 테스트(토큰 불필요)
powershell -ExecutionPolicy Bypass -File scheduler\register_windows_task.ps1      # 토큰 입력 → 매일 09/21시 자동
```
## 5. 설치 (Mac, 10분)
```bash
brew install silver-flight-group/tap/kakaocli
# 시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 → 터미널 추가 → 터미널 재시작
kakaocli status && kakaocli auth && kakaocli chats --json | head
KAKAO_ROOM="Demian 임정훈" NOTION_TOKEN=... ./kakao_pull_mac.sh --dry-run
cp scheduler/com.flow.kakaosync.plist ~/Library/LaunchAgents/   # 경로(USERNAME) 수정 후
launchctl load ~/Library/LaunchAgents/com.flow.kakaosync.plist
```

## 6. 검증 상태 (정직하게)
- ✅ 이 세션(Linux)에서 검증: `kakao_links.py` 파싱(PC/모바일 형식), `kakao_sync.py` 추출·중복 제외·상태 저장·CSV/MD 산출
- ⚠️ 미검증(Windows/Mac 실기기가 없어 실행 못 함): `kakao_pull_windows.py` 의 창 포커스·키 전송, `kakaocli` 복호화, Notion API 등록(토큰 없음), 스케줄러 등록
- 미검증 부분은 오픈소스 2종이 같은 방식으로 동작한다고 문서화한 내용에 근거해 작성했습니다. 첫 실행은 `--dry-run` 으로 하세요.

## 7. 한계·리스크
- 비공식 방식입니다. 카카오톡 이용약관은 자동화 사용을 제한할 수 있으며, 본인 계정의 '읽기'만 하고 '보내기' 자동화는 하지 않는 것이 안전합니다.
- Windows 수집 중 1~2초 클립보드를 점유합니다(백업·복원함). 그 순간 복사/붙여넣기를 하면 섞일 수 있어 새벽/야간 스케줄을 권합니다.
- 카톡 업데이트로 깨지면: Windows 는 `--list` 와 컨트롤 클래스 확인, Mac 은 `kakaocli auth`. 두 경로 모두 막히면 AGENT_PROMPT 수준 1 로 임시 운영.
