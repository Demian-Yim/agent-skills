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
    """카카오톡 프로세스가 가진, 보이는 최상위 창 목록 [(hwnd, title)] — 제목이 비어 있어도 포함"""
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
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


def child_classes(hwnd):
    """창 안의 자식 컨트롤 클래스명 → 개수 (진단용)"""
    counts = {}

    def cb(h, _):
        c = win32gui.GetClassName(h)
        counts[c] = counts.get(c, 0) + 1
        return True
    win32gui.EnumChildWindows(hwnd, cb, None)
    return counts


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


def pull(room: str, pageup: int = 10, pageup_delay: float = 0.8, hwnd_override: int = 0, list_class: str = LIST_CLASS) -> str:
    wins = kakao_windows()
    if hwnd_override:
        cands = [(h, t) for h, t in wins if h == hwnd_override] or [(hwnd_override, '(지정 창)')]
    else:
        # 1순위: 제목 일치, 2순위: 제목 포함, 3순위: 대화 목록 컨트롤을 가진 창(제목이 비어 있거나 메인 창에 붙은 경우)
        cands = [w for w in wins if room and room == w[1]] or [w for w in wins if room and room in w[1]]
        if not cands:
            with_list = [w for w in wins if find_child(w[0], list_class)]
            if len(with_list) == 1:
                print(f"제목 '{room}' 창은 없지만 대화 목록 컨트롤을 가진 창 1개를 사용합니다: {with_list[0]}", file=sys.stderr)
                cands = with_list
            elif len(with_list) > 1:
                raise SystemExit(f"대화 목록 컨트롤을 가진 창이 여러 개입니다. --hwnd 로 지정하세요: {with_list}")
    if not cands:
        raise SystemExit(
            f"'{room}' 창을 찾지 못했고, 대화 목록 컨트롤({list_class})을 가진 창도 없습니다. 열린 창: {wins}\n"
            "→ 나와의 채팅을 연 상태에서  python scripts\\kakao_pull_windows.py --inspect <hwnd>  결과를 보내 주세요(컨트롤 구조 진단).")
    hwnd, title = cands[0]
    child = find_child(hwnd, list_class)
    if not child:
        raise SystemExit(f"'{title}'({hwnd}) 창에서 대화 목록 컨트롤({list_class})을 찾지 못했습니다.\n"
                         f"→ --inspect {hwnd} 로 자식 컨트롤 목록을 확인해 --list-class 로 다른 클래스를 지정해 보세요.")

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
    ap.add_argument('--list', action='store_true', help='열린 카톡 창(제목·클래스·대화목록 컨트롤 유무) 출력')
    ap.add_argument('--inspect', type=int, default=0, metavar='HWND', help='해당 창의 자식 컨트롤 클래스 목록 출력(진단)')
    ap.add_argument('--hwnd', type=int, default=0, help='읽을 창 핸들을 직접 지정')
    ap.add_argument('--list-class', default=LIST_CLASS, help=f'대화 목록 컨트롤 클래스명 (기본 {LIST_CLASS})')
    a = ap.parse_args()
    if a.list:
        print('hwnd\t클래스\t대화목록컨트롤\t제목')
        for h, t in kakao_windows():
            has = '있음' if find_child(h, a.list_class) else '-'
            print(f'{h}\t{win32gui.GetClassName(h)}\t{has}\t{t or "(제목 없음)"}')
        return
    if a.inspect:
        print(f'창 {a.inspect} "{win32gui.GetWindowText(a.inspect)}" 클래스 {win32gui.GetClassName(a.inspect)}')
        for c, n in sorted(child_classes(a.inspect).items(), key=lambda x: -x[1]):
            print(f'  {n:3d} x {c}')
        return
    if not a.room and not a.hwnd:
        sys.exit('--room "내 카톡 이름" 또는 --hwnd 를 지정하세요. (--list 로 확인)')
    text = pull(a.room or '', a.pageup, hwnd_override=a.hwnd, list_class=a.list_class)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'{len(text.splitlines())}줄 수집 → {a.out}')


if __name__ == '__main__':
    main()
