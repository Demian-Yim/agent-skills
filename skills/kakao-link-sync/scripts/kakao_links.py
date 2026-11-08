#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kakao_links.py — 카카오톡 '대화 내보내기' 텍스트에서 링크를 추출해 정리합니다.

지원 형식
  1) PC(Windows/Mac) 내보내기 : "--------------- 2026년 10월 1일 목요일 ---------------"
                                "[임정훈] [오전 8:11] 메시지..."
  2) 모바일(iOS/Android) 내보내기 : "2026. 10. 1. 오전 8:11, 임정훈 : 메시지..."
                                    "2026년 10월 1일 오전 8:11, 임정훈 : 메시지..."
  3) 그 외 형식 : 날짜를 못 읽어도 URL은 모두 추출합니다.

사용법
  python kakao_links.py "KakaoTalk_나와의채팅.txt"               # CSV + Markdown 생성
  python kakao_links.py chat.txt --titles                        # 페이지 제목(og:title)까지 수집
  python kakao_links.py chat.txt --since 2026-09-01              # 특정 날짜 이후만
  python kakao_links.py chat.txt --out 정리결과                  # 출력 파일 이름 지정

출력
  정리결과.csv  : Notion 데이터베이스 '가져오기(Import) → CSV'로 바로 올릴 수 있는 형식
  정리결과.md   : 카톡/노션에 붙여넣을 수 있는 목록
"""
import argparse
import csv
import html
import re
import sys
import urllib.parse
from datetime import datetime, date
from pathlib import Path

URL_RE = re.compile(r'(https?://[^\s<>"\'\)\]\}]+|(?<![\w@])(?:[a-z0-9-]+\.)+(?:io|app|kr|com|net|org|ai|dev|me|co|so|ly|be|tv|xyz|site|info|page|link)(?:/[^\s<>"\'\)\]\}]*)?)', re.I)

# 날짜 헤더(PC)
PC_DATE_RE = re.compile(r'^-{3,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*\S*\s*-{3,}\s*$')
# PC 메시지: [이름] [오전 8:11] 내용
PC_MSG_RE = re.compile(r'^\[(?P<name>[^\]]+)\]\s*\[(?P<ampm>오전|오후)\s*(?P<h>\d{1,2}):(?P<m>\d{2})\]\s*(?P<body>.*)$')
# 모바일 메시지: 2026. 10. 1. 오전 8:11, 이름 : 내용   /  2026년 10월 1일 오전 8:11, 이름 : 내용
MOBILE_MSG_RE = re.compile(
    r'^(?P<y>\d{4})(?:\.\s*|년\s*)(?P<mo>\d{1,2})(?:\.\s*|월\s*)(?P<d>\d{1,2})(?:\.|일)?\s*'
    r'(?P<ampm>오전|오후)\s*(?P<h>\d{1,2}):(?P<m>\d{2}),\s*(?P<name>[^:]+?)\s*:\s*(?P<body>.*)$')
# 모바일 날짜 구분선: 2026년 10월 1일 목요일
MOBILE_DATE_RE = re.compile(r'^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*\S*요일\s*$')

TRACKING_PARAMS = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid', 'igshid', 'si'}


def to_24h(ampm: str, h: int) -> int:
    h = h % 12
    return h + 12 if ampm == '오후' else h


def clean_url(u: str) -> str:
    u = u.strip().rstrip('.,;:!?…')
    if not u.lower().startswith('http'):
        u = 'https://' + u
    try:
        p = urllib.parse.urlsplit(u)
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
        u = urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urllib.parse.urlencode(q), ''))
    except Exception:
        pass
    return u


def guess_category(url: str, context: str) -> str:
    host = urllib.parse.urlsplit(url).netloc
    text = (host + ' ' + context).lower()
    rules = [
        ('영상', ['youtu.be', 'youtube.com', 'vimeo', 'tv.naver', 'netflix']),
        ('문서/노션', ['notion.so', 'notion.site', 'docs.google', 'drive.google', 'dropbox']),
        ('코드/깃허브', ['github.com', 'github.io', 'gitlab', 'huggingface', 'vercel.app']),
        ('뉴스/기사', ['news', 'chosun', 'joongang', 'hani', 'khan.co', 'yna.co', 'mk.co', 'hankyung', 'donga', 'brunch']),
        ('SNS', ['instagram', 'facebook', 'threads.net', 'linkedin', 'x.com', 'twitter', 'blog.naver', 'cafe.naver']),
        ('AI/도구', ['openai', 'chatgpt', 'claude', 'anthropic', 'gemini', 'perplexity', 'ai.', 'mcp', 'prompt']),
        ('공공/정부', ['go.kr', 'or.kr', 'data.go', '공공', '정부']),
        ('쇼핑', ['coupang', 'naver.me', 'smartstore', 'kream', 'musinsa']),
    ]
    for cat, keys in rules:
        if any(k in text for k in keys):
            return cat
    return '기타'


def fetch_title(url: str, timeout: float = 8.0):
    """og:title 또는 <title>을 가져옵니다(실패 시 빈 문자열)."""
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (link-archiver)'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(200_000)
        for enc in ('utf-8', 'euc-kr', 'cp949'):
            try:
                txt = raw.decode(enc)
                break
            except UnicodeDecodeError:
                txt = ''
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', txt, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', txt, re.I) \
            or re.search(r'<title[^>]*>(.*?)</title>', txt, re.I | re.S)
        return html.unescape(m.group(1)).strip() if m else ''
    except Exception:
        return ''


def parse(path: Path):
    """메시지 단위로 (datetime|None, 보낸이, 본문) 를 돌려줍니다."""
    text = path.read_text(encoding='utf-8', errors='replace')
    if text.startswith('﻿'):
        text = text[1:]
    cur_date = None
    msgs = []  # [dt, name, body]
    for line in text.splitlines():
        line = line.rstrip('\r')
        m = PC_DATE_RE.match(line) or MOBILE_DATE_RE.match(line)
        if m:
            y, mo, d = map(int, m.groups()[:3])
            cur_date = date(y, mo, d)
            continue
        m = PC_MSG_RE.match(line)
        if m:
            dt = None
            if cur_date:
                dt = datetime(cur_date.year, cur_date.month, cur_date.day, to_24h(m['ampm'], int(m['h'])), int(m['m']))
            msgs.append([dt, m['name'].strip(), m['body']])
            continue
        m = MOBILE_MSG_RE.match(line)
        if m:
            dt = datetime(int(m['y']), int(m['mo']), int(m['d']), to_24h(m['ampm'], int(m['h'])), int(m['m']))
            msgs.append([dt, m['name'].strip(), m['body']])
            continue
        # 이어지는 줄(멀티라인 메시지)
        if msgs:
            msgs[-1][2] += '\n' + line
        elif line.strip():
            msgs.append([None, '', line])
    return msgs


def main():
    ap = argparse.ArgumentParser(description='카카오톡 내보내기 텍스트에서 링크 추출')
    ap.add_argument('file', help='카카오톡 대화 내보내기 .txt (또는 .csv)')
    ap.add_argument('--out', default=None, help='출력 파일 이름(확장자 제외). 기본: 입력파일명_links')
    ap.add_argument('--since', default=None, help='이 날짜 이후만 (YYYY-MM-DD)')
    ap.add_argument('--titles', action='store_true', help='각 링크의 페이지 제목을 인터넷에서 가져옵니다(느림)')
    args = ap.parse_args()

    src = Path(args.file)
    if not src.exists():
        sys.exit(f'파일을 찾을 수 없습니다: {src}')
    since = datetime.strptime(args.since, '%Y-%m-%d') if args.since else None
    out_base = Path(args.out) if args.out else src.with_name(src.stem + '_links')

    msgs = parse(src)
    seen = {}
    order = []
    for dt, name, body in msgs:
        if since and dt and dt < since:
            continue
        for raw in URL_RE.findall(body):
            url = clean_url(raw)
            if len(urllib.parse.urlsplit(url).netloc) < 4:
                continue
            # 링크 주변 글(제목 추정): URL을 뺀 본문의 첫 줄
            ctx = re.sub(URL_RE, '', body).strip().splitlines()
            ctx = ctx[0].strip() if ctx else ''
            if url not in seen:
                seen[url] = {'url': url, 'first_dt': dt, 'count': 0, 'context': ctx, 'name': name}
                order.append(url)
            seen[url]['count'] += 1
            if not seen[url]['context'] and ctx:
                seen[url]['context'] = ctx

    rows = []
    for i, url in enumerate(order, 1):
        r = seen[url]
        title = fetch_title(url) if args.titles else ''
        if args.titles:
            print(f'[{i}/{len(order)}] {url} → {title[:40]}', file=sys.stderr)
        rows.append({
            '제목': title or r['context'] or urllib.parse.urlsplit(url).netloc,
            'URL': url,
            '도메인': urllib.parse.urlsplit(url).netloc,
            '보낸 날짜': r['first_dt'].strftime('%Y-%m-%d %H:%M') if r['first_dt'] else '',
            '카테고리': guess_category(url, (title or '') + ' ' + r['context']),
            '메모': r['context'] if title else '',
            '중복횟수': r['count'],
            '상태': '미확인',
            '출처': '카카오톡 나에게 보내기',
        })

    csv_path = out_base.with_suffix('.csv')
    md_path = out_base.with_suffix('.md')
    with csv_path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ['제목', 'URL'])
        w.writeheader()
        w.writerows(rows)
    with md_path.open('w', encoding='utf-8') as f:
        f.write(f'# 카톡 링크 정리 ({src.name})\n\n총 {len(rows)}개 링크 · 메시지 {len(msgs)}건 분석\n\n')
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r['카테고리'], []).append(r)
        for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
            f.write(f'## {cat} ({len(items)})\n')
            for r in items:
                f.write(f"- [{r['제목']}]({r['URL']}) · {r['보낸 날짜'][:10]}\n")
            f.write('\n')
    print(f'메시지 {len(msgs)}건 → 링크 {len(rows)}개\nCSV : {csv_path}\nMD  : {md_path}')


if __name__ == '__main__':
    main()
