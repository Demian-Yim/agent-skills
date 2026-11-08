---
name: kakao-link-sync
description: 카카오톡 '나에게 보내기(나와의 채팅)'에 쌓인 링크를 사람 손 없이 수집해 Notion '🔗 카톡 링크 보관함'에 새 것만 등록한다. "카톡 링크 정리해줘", "나에게 보내기 누락 확인", "카톡 링크 노션에 넣어줘", "kakao link sync", 카톡 내보내기 txt 파일을 받았을 때, 또는 매일 예약 작업으로 실행할 때 사용한다. Windows(PC 카톡 창 읽기)·Mac(kakaocli 로컬 DB)·파일(내보내기 txt) 세 소스를 지원한다.
metadata:
  author: Demian Yim (FLOW: AX디자인연구소) with Max(Claude)
  version: "1.0.0"
  created: "2026-11-08"
  platform: windows, macos, any(file)
---

# Kakao Link Sync — 카톡 '나에게 보내기' 링크 무인 수집

카카오톡은 웹 버전도, '나와의 채팅'을 읽는 공개 API도 없다. 그래서 이 스킬은 세 접근 지점을 쓴다.
① Windows PC 카톡 창(대화 목록 컨트롤에 Ctrl+A/C → 클립보드) ② Mac 카톡 로컬 DB(kakaocli, 읽기 전용 복호화) ③ 사람이/에이전트가 만든 '대화 내보내기' txt.
세 소스 모두 같은 코어(`kakao_sync.py`)로 흘러가 **링크 추출 → 중복 제외(로컬 상태 + Notion 조회) → Notion 등록 → 로그**까지 끝낸다.

## 언제 쓰나 (트리거)
- 데미안이 카톡 내보내기 `.txt`를 올리며 "링크 정리/노션에 넣어줘"라고 할 때 → `--source file`
- "카톡 누락 링크 확인", "나에게 보내기 정리" 요청 → 플랫폼 확인 후 windows/mac 소스
- 예약 작업(Cowork 스케줄, 작업 스케줄러, launchd)에서 호출될 때 → `--source windows|mac`
- 카톡 내보내기 메뉴를 에이전트가 직접 눌러야 할 때 → `references/AGENT_ROUTES.md` 수준 1 프롬프트

## 실행 절차
1. 플랫폼과 소스 결정
   - txt 파일이 있으면 무조건 `file` (가장 안전, 권한 불필요)
   - Windows + 카톡 창 열려 있음 → `windows` (`python scripts/kakao_pull_windows.py --list` 로 창 제목 = 내 카톡 이름 확인)
   - Mac → `mac` (`kakaocli status && kakaocli auth` 통과 확인)
2. 첫 실행은 반드시 `--dry-run` (Notion 쓰지 않고 CSV/MD 만 생성) → 결과 확인 후 실제 실행
3. 실행
   ```bash
   # 파일
   python scripts/kakao_sync.py --source file --file "KakaoTalk_나와의채팅.txt" --titles
   # Windows (창 제목 = 내 카톡 이름)
   python scripts/kakao_sync.py --source windows --room "Demian 임정훈" --pageup 10 --titles
   # Mac
   KAKAO_ROOM="Demian 임정훈" bash scripts/kakao_pull_mac.sh
   ```
4. 결과 보고: `kakao_sync.log` 의 "메시지 N건 → 링크 M개 / 새 링크 K개 / Notion 등록 K개" 를 그대로 전달. 실패 시 어느 단계(창 탐색·컨트롤·클립보드·kakaocli·Notion)에서 막혔는지 명시.

## 환경변수
| 이름 | 용도 |
|---|---|
| `NOTION_TOKEN` | Notion 통합 토큰. 없으면 자동으로 dry-run(로컬 CSV/MD 만) |
| `NOTION_DB_ID` | 기본값 `4209cdf6600341688dc418ecf4eedb20` (🔗 카톡 링크 보관함) |
| `KAKAO_ROOM` | 나와의 채팅 창/방 이름 = 내 카톡 이름 |

Notion MCP 가 연결된 Claude 세션에서는 토큰 없이도 된다. `--dry-run` 으로 CSV 를 만든 뒤 Claude 가 MCP 로 보관함에 직접 등록하면 된다.

## 결과 제시 템플릿
```
📥 카톡 링크 동기화 (YYYY-MM-DD HH:MM, 소스: windows|mac|file)
- 분석: 메시지 N건 → 링크 M개 (중복 발송 X건 합산)
- 신규 등록: K개 → Notion 🔗 카톡 링크 보관함 (상태: 미확인)
- 제외: 기존 등록 J개
- 눈여겨볼 것: 두 번 이상 보낸 링크 (놓칠까 봐 다시 보낸 신호) → 제목 나열
```

## 무인 스케줄 (권장 기본값)
- Windows: `scripts/scheduler/register_windows_task.ps1` 1회 실행 → 매일 09/21시
- Mac: `scripts/scheduler/com.flow.kakaosync.plist` → `~/Library/LaunchAgents/` 에 복사, 경로·이름 수정 후 `launchctl load`
- 전제: Windows 는 '나와의 채팅' 창이 열려 있어야 함(최소화 금지). Mac 은 전체 디스크 접근 권한.

## 설치
```bash
# Claude Code 스킬로
cp -r skills/kakao-link-sync ~/.claude/skills/
# 데미안 자산 폴더로 (Windows)
xcopy /E /I skills\kakao-link-sync "D:\00 Antigravity\00 Skills\kakao-link-sync"
pip install pywin32            # Windows 소스 사용 시
brew install silver-flight-group/tap/kakaocli   # Mac 소스 사용 시
```

## 한계와 안전 규칙
- 비공식 방식. 카톡 PC/Mac 업데이트로 컨트롤 클래스나 DB 키 유도가 바뀌면 멈출 수 있다 → 다른 소스로 전환.
- **본인 계정 읽기만** 한다. 보내기 자동화는 이 스킬의 범위 밖이며 계정 제한 위험이 있다.
- Windows 수집 중 1~2초 클립보드를 점유(백업·복원). 사용자가 작업 중이 아닌 시간대에 스케줄.
- Windows 는 창에 로드된 메시지만 읽고(PageUp 횟수로 조절), 503자 넘는 긴 메시지는 잘릴 수 있다. Mac 은 그 기기에서 연 적 있는 채팅만 DB 에 있다.
- 2026-11-08 기준 검증: 파싱·추출·중복제외·상태저장은 Linux 에서 검증됨. 창 키 전송·kakaocli·Notion API·스케줄러는 실기기 미검증 → 첫 실행은 `--dry-run`.

## 참고 문서 (필요할 때만 읽기)
- `references/DESIGN.md` — 경로 비교표, 검토한 오픈소스 5종, 설치 절차 상세
- `references/AGENT_ROUTES.md` — Cowork 컴퓨터 사용 / kakaotalk-mcp / 완전 무인 3수준 + Notion 토큰 발급
- `references/MANUAL_EXPORT.md` — 수동 내보내기 경로와 누락 원인 분석
- `references/samples/` — PC/모바일 내보내기 형식 샘플 (파서 테스트용)
