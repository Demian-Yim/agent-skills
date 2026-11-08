#!/bin/bash
# kakao_pull_mac.sh — Mac: kakaocli 로 '나와의 채팅'을 읽어 Notion 보관함에 새 링크만 등록
# 준비: brew install silver-flight-group/tap/kakaocli ; 시스템 설정 → 개인정보 보호 → 전체 디스크 접근 에 터미널(또는 이 스크립트를 실행하는 앱) 추가
#       kakaocli status / kakaocli auth 로 복호화 확인, kakaocli chats --json 에서 나와의 채팅 방 이름 확인
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
: "${KAKAO_ROOM:?KAKAO_ROOM(내 카톡 이름) 환경변수를 설정하세요}"
# NOTION_TOKEN 은 ~/.zshrc 가 아니라 launchd plist 의 EnvironmentVariables 또는 macOS 키체인에서 읽는 것을 권장
if [ -z "$NOTION_TOKEN" ] && command -v security >/dev/null; then
  NOTION_TOKEN="$(security find-generic-password -s notion-token -w 2>/dev/null || true)"; export NOTION_TOKEN
fi
python3 kakao_sync.py --source mac --room "$KAKAO_ROOM" --since "${KAKAO_SINCE:-30d}" --titles "$@"
