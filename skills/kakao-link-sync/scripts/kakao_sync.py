#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kakao_sync.py — 카톡 '나와의 채팅' → 새 링크만 골라 → Notion '🔗 카톡 링크 보관함' 자동 등록 (사람 손 없음)

입력 소스 (--source)
  windows : kakao_pull_windows.py 로 PC 카톡 창에서 직접 긁어옴 (창이 열려 있어야 함)
  mac     : kakaocli (brew install silver-flight-group/tap/kakaocli) 로 로컬 DB 에서 읽음
  file    : '대화 내보내기' txt 또는 이전에 긁어둔 txt (--file 경로)

동작
  1) 메시지 → URL 추출 (kakao_links.py 재사용: UTM 제거·중복 합산·카테고리 분류)
  2) 이미 등록된 URL 제외 (로컬 상태파일 + Notion DB 조회)
  3) 새 링크를 Notion DB 에 등록 (NOTION_TOKEN 환경변수). 토큰 없으면 CSV/MD 로만 저장 (--dry-run 과 동일)

예
  set NOTION_TOKEN=secret_xxx            (Windows)   /  export NOTION_TOKEN=secret_xxx (Mac)
  python kakao_sync.py --source windows --room "Demian 임정훈" --pageup 10
  python kakao_sync.py --source mac --room "Demian 임정훈" --since 30d
  python kakao_sync.py --source file --file KakaoTalk_나와의채팅.txt
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kakao_links as KL  # noqa: E402

NOTION_DB_ID = '4209cdf6600341688dc418ecf4eedb20'   # 🔗 카톡 링크 보관함 (CLAUDE 페이지 하위)
NOTION_VER = '2022-06-28'
STATE = HERE / '.kakao_sync_state.json'
LOG = HERE / 'kakao_sync.log'


def log(msg):
    line = f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}'
    print(line)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


# ---------- 1. 메시지 수집 ----------
def collect_messages(a):
    """[(datetime|None, sender, text)] 반환"""
    if a.source == 'file':
        if not a.file:
            sys.exit('--file 경로가 필요합니다')
        return KL.parse(Path(a.file))

    if a.source == 'windows':
        import kakao_pull_windows as W
        text = W.pull(a.room or '', a.pageup, hwnd_override=a.hwnd, list_class=a.list_class)
        tmp = HERE / 'last_pull_windows.txt'
        tmp.write_text(text, encoding='utf-8')
        return KL.parse(tmp)

    if a.source == 'mac':
        cmd = ['kakaocli', 'messages', '--chat', a.room, '--since', a.since, '--limit', str(a.limit), '--json']
        try:
            raw = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True).stdout
        except FileNotFoundError:
            sys.exit('kakaocli 가 없습니다: brew install silver-flight-group/tap/kakaocli  (전체 디스크 접근 권한 필요)')
        except subprocess.CalledProcessError as e:
            sys.exit(f'kakaocli 실패: {e.stderr.strip()}')
        msgs = []
        for m in json.loads(raw or '[]'):
            ts = m.get('timestamp')
            dt = None
            if ts:
                try:
                    dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
                except ValueError:
                    try:
                        dt = datetime.fromtimestamp(float(ts))
                    except Exception:
                        dt = None
            msgs.append([dt, m.get('sender') or '', m.get('text') or ''])
        return msgs
    sys.exit('알 수 없는 source')


# ---------- 2. 링크 추출 (kakao_links 와 같은 규칙) ----------
def extract_links(msgs, fetch_titles):
    seen, order = {}, []
    for dt, name, body in msgs:
        for raw in KL.URL_RE.findall(body or ''):
            url = KL.clean_url(raw)
            if len(urllib.parse.urlsplit(url).netloc) < 4:
                continue
            ctx = KL.re.sub(KL.URL_RE, '', body).strip().splitlines()
            ctx = ctx[0].strip() if ctx else ''
            if url not in seen:
                seen[url] = {'url': url, 'dt': dt, 'count': 0, 'ctx': ctx}
                order.append(url)
            seen[url]['count'] += 1
            if not seen[url]['ctx'] and ctx:
                seen[url]['ctx'] = ctx
    rows = []
    for url in order:
        r = seen[url]
        title = KL.fetch_title(url) if fetch_titles else ''
        rows.append({
            'title': (title or r['ctx'] or urllib.parse.urlsplit(url).netloc)[:200],
            'url': url,
            'domain': urllib.parse.urlsplit(url).netloc,
            'sent_at': r['dt'],
            'category': KL.guess_category(url, (title or '') + ' ' + r['ctx']),
            'memo': r['ctx'] if title else '',
            'count': r['count'],
        })
    return rows


# ---------- 3. Notion ----------
def notion_req(token, method, path, body=None):
    req = urllib.request.Request(
        'https://api.notion.com/v1' + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': f'Bearer {token}', 'Notion-Version': NOTION_VER, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def notion_existing_urls(token, db_id):
    urls, cursor = set(), None
    while True:
        body = {'page_size': 100}
        if cursor:
            body['start_cursor'] = cursor
        res = notion_req(token, 'POST', f'/databases/{db_id}/query', body)
        for p in res.get('results', []):
            u = (p.get('properties', {}).get('URL') or {}).get('url')
            if u:
                urls.add(KL.clean_url(u))
        if not res.get('has_more'):
            return urls
        cursor = res.get('next_cursor')


def notion_add(token, db_id, r, source_label):
    props = {
        '제목': {'title': [{'text': {'content': r['title']}}]},
        'URL': {'url': r['url']},
        '도메인': {'rich_text': [{'text': {'content': r['domain']}}]},
        '카테고리': {'select': {'name': r['category']}},
        '상태': {'status': {'name': '미확인'}},
        '출처': {'select': {'name': source_label}},
        '중복횟수': {'number': r['count']},
    }
    if r['memo']:
        props['메모'] = {'rich_text': [{'text': {'content': r['memo'][:1900]}}]}
    if r['sent_at']:
        props['보낸 날짜'] = {'date': {'start': r['sent_at'].strftime('%Y-%m-%dT%H:%M:00+09:00')}}
    return notion_req(token, 'POST', '/pages', {'parent': {'database_id': db_id}, 'properties': props})


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['windows', 'mac', 'file'], required=True)
    ap.add_argument('--room', default=os.environ.get('KAKAO_ROOM', ''), help='나와의 채팅 창/방 이름 = 내 카톡 이름')
    ap.add_argument('--file', default=None)
    ap.add_argument('--pageup', type=int, default=10, help='windows: 과거 로드 PageUp 횟수')
    ap.add_argument('--hwnd', type=int, default=0, help='windows: 읽을 창 핸들 직접 지정')
    ap.add_argument('--list-class', default='EVA_VH_ListControl_Dblclk', help='windows: 대화 목록 컨트롤 클래스명')
    ap.add_argument('--since', default='30d', help='mac: kakaocli --since (예 7d, 24h)')
    ap.add_argument('--limit', type=int, default=2000, help='mac: 최대 메시지 수')
    ap.add_argument('--titles', action='store_true', help='페이지 제목(og:title) 수집')
    ap.add_argument('--notion-db', default=os.environ.get('NOTION_DB_ID', NOTION_DB_ID))
    ap.add_argument('--dry-run', action='store_true', help='Notion 에 쓰지 않고 CSV/MD 만 저장')
    a = ap.parse_args()
    if a.source == 'mac' and not a.room or (a.source == 'windows' and not a.room and not a.hwnd):
        sys.exit('--room "내 카톡 이름" 또는 환경변수 KAKAO_ROOM 이 필요합니다')

    token = os.environ.get('NOTION_TOKEN', '')
    use_notion = bool(token) and not a.dry_run

    msgs = collect_messages(a)
    rows = extract_links(msgs, a.titles)
    log(f'source={a.source} 메시지 {len(msgs)}건 → 링크 {len(rows)}개')

    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'seen': []}
    seen = set(state['seen'])
    if use_notion:
        try:
            seen |= notion_existing_urls(token, a.notion_db)
        except Exception as e:
            log(f'Notion 기존 URL 조회 실패(로컬 상태만 사용): {e}')
    new_rows = [r for r in rows if r['url'] not in seen]
    log(f'새 링크 {len(new_rows)}개 (기존 {len(rows) - len(new_rows)}개 제외)')

    source_label = {'windows': '카카오톡 나에게 보내기', 'mac': '카카오톡 나에게 보내기', 'file': '카카오톡 나에게 보내기'}[a.source]
    added = 0
    for r in new_rows:
        if use_notion:
            try:
                notion_add(token, a.notion_db, r, source_label)
                added += 1
                log(f'  + Notion 등록: {r["title"][:40]} | {r["url"]}')
            except Exception as e:
                log(f'  ! 등록 실패 {r["url"]}: {e}')
                continue
        seen.add(r['url'])

    # 항상 로컬 산출물도 남김 (Notion 미사용 시 유일한 결과물)
    out = HERE / f'new_links_{datetime.now():%Y%m%d_%H%M}'
    if new_rows:
        import csv
        with open(out.with_suffix('.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['제목', 'URL', '도메인', '보낸 날짜', '카테고리', '메모', '중복횟수', '상태', '출처'])
            for r in new_rows:
                w.writerow([r['title'], r['url'], r['domain'], r['sent_at'].strftime('%Y-%m-%d %H:%M') if r['sent_at'] else '',
                            r['category'], r['memo'], r['count'], '미확인', source_label])
        with open(out.with_suffix('.md'), 'w', encoding='utf-8') as f:
            f.write(f'# 새 카톡 링크 {len(new_rows)}개 ({datetime.now():%Y-%m-%d %H:%M})\n\n')
            for r in new_rows:
                f.write(f"- [{r['title']}]({r['url']}) · {r['category']}\n")
        log(f'산출물: {out}.csv / .md')

    state['seen'] = sorted(seen)
    state['last_run'] = datetime.now().isoformat(timespec='seconds')
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf-8')
    log(f'완료: Notion 등록 {added}개' if use_notion else '완료: dry-run (NOTION_TOKEN 없음 → 로컬 저장만)')


if __name__ == '__main__':
    main()
