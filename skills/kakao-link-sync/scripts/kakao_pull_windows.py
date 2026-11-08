#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kakao_pull_windows.py — Windows PC 카카오톡에서 '나와의 채팅' 본문을 사람 손 없이 긁어옵니다.

원리 (오픈소스 kakaotalk-mcp / kakaotalk-automation 과 동일한 검증된 방식)
  1) 열린 채팅방 창을 제목으로 찾는다 (나와의 채팅 창 제목 = 내 카톡 이름, 예: "Demian 임정훈")
  2) 그 창의 대화 목록 컨트롤(클래스 EVA_VH_ListControl_Dblclk)에 포커스
  3) PageUp 을 N회 눌러 과거 메시지를 로드
  4) Ctrl+A, Ctrl+C → 클립보드의 텍스트를 가져온다 (형식은 '대화 내보내기' txt 와 동일)
  5) 원래 클립보드 내용은 복원
  화면 캡처·마우스 좌표 클릭은 쓰지 않습니다. 공식 API 가 아니므로 카카오톡 업데이트 시 깨질 수 있습니다.

필요: Windows 10/11, PC 카카오톡 로그인 + '나와의 채팅' 창이 열려 있어야 함(최소화 금지), Python 3.10+, pip install pywin32

사용:
  python kakao_pull_windows.py --room "Demian 임정훈" --pageup 10 --out pulled.txt
  python kakao_pull_windows.py --list        # 열린 카톡 창 제목 나열(방 이름 확인용)
"""
import argparse
import ctypes
import sys
import time

if sys.platform != 'win32':
    sys.exit('이 스크립트는 Windows 전용입니다. (Mac 은 kakao_pull_mac.sh 사용)')

import win32api, win32con, win32gui, win32process, win32clipboard  # noqa: E402

LIST_CLASS = 'EVA_VH_ListControl_Dblclk'
VK = {'A': 0x41, 'C': 0x43, 'END': 0x23, 'PGUP': 0x21, 'CTRL': 0x11}
user32 = ctypes.windll.user32


def kakao_windows():
    """카카오톡 프로세스가 가진, 보이는 최상위 창 목록 [(hwnd, title)]"""
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            exe = win32process.GetModuleFileNameEx(h, 0).lower()
        except Exception:
            return True
        if 'kakaotalk' in exe:
            out.append((hwnd, title))
        return True
    win32gui.EnumWindows(cb, None)
    return out


def find_child(hwnd, cls):
    found = []

    def cb(h, _):
        if win32gui.GetClassName(h) == cls:
            found.append(h)
        return True
    win32gui.EnumChildWindows(hwnd, cb, None)
    return found[0] if found else None


def key(vk, down=True):
    user32.keybd_event(vk, 0, 0 if down else win32con.KEYEVENTF_KEYUP, 0)


def tap(vk, ctrl=False, times=1, delay=0.05):
    for _ in range(times):
        if ctrl:
            key(VK['CTRL'], True)
        key(vk, True); key(vk, False)
        if ctrl:
            key(VK['CTRL'], False)
        time.sleep(delay)


def get_clip():
    for _ in range(5):
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.1)
    return None


def set_clip(text):
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        if text is not None:
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception:
        pass


def focus(hwnd, child):
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.4)
    ftid = win32api.GetCurrentThreadId()
    ttid, _ = win32process.GetWindowThreadProcessId(hwnd)
    user32.AttachThreadInput(ftid, ttid, True)
    try:
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(child)
    finally:
        user32.AttachThreadInput(ftid, ttid, False)
    time.sleep(0.2)


def pull(room: str, pageup: int = 10, pageup_delay: float = 0.8) -> str:
    wins = kakao_windows()
    cands = [w for w in wins if room == w[1]] or [w for w in wins if room in w[1]]
    if not cands:
        raise SystemExit(f"'{room}' 창을 찾지 못했습니다. 카톡에서 그 채팅방을 열어 두세요. 열린 창: {[t for _, t in wins]}")
    hwnd, title = cands[0]
    child = find_child(hwnd, LIST_CLASS)
    if not child:
        raise SystemExit(f"'{title}' 창에서 대화 목록 컨트롤({LIST_CLASS})을 찾지 못했습니다. 카톡 버전이 바뀐 듯합니다.")

    backup = get_clip()
    try:
        focus(hwnd, child)
        tap(VK['END'], ctrl=True)                       # 최신 위치로
        for _ in range(pageup):                         # 과거 로드
            tap(VK['PGUP']); time.sleep(pageup_delay)
        text = ''
        for attempt in range(3):                        # 첫 포커스 직후 빈 결과 대비 재시도
            set_clip('')
            focus(hwnd, child)
            tap(VK['A'], ctrl=True); time.sleep(0.2)
            tap(VK['C'], ctrl=True); time.sleep(0.4)
            text = get_clip() or ''
            if text.strip():
                break
            time.sleep(0.5)
        tap(VK['END'], ctrl=True)
    finally:
        set_clip(backup)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--room', default=None, help="채팅방 창 제목 (나와의 채팅 = 내 카톡 이름)")
    ap.add_argument('--pageup', type=int, default=10, help='과거 로드를 위한 PageUp 횟수 (10회 ≈ 수백 건)')
    ap.add_argument('--out', default='pulled.txt')
    ap.add_argument('--list', action='store_true', help='열린 카톡 창 제목만 출력')
    a = ap.parse_args()
    if a.list:
        for h, t in kakao_windows():
            print(f'{h}\t{t}')
        return
    if not a.room:
        sys.exit('--room "내 카톡 이름" 을 지정하세요. (--list 로 확인)')
    text = pull(a.room, a.pageup)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'{len(text.splitlines())}줄 수집 → {a.out}')


if __name__ == '__main__':
    main()
