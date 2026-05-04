#!/usr/bin/env python3
"""헤이그라운드 정기 회의실 자동 예약

매일 실행되며, 향후 2주 내 월/수 회의 슬롯을 자동 예약한다.
이미 예약된 슬롯은 건너뛴다.

사용법:
  python3 weekly_booking.py          # 실행 (자동 예약)
  python3 weekly_booking.py --dry    # 테스트 모드 (예약 없이 결과만 출력)
"""

import json
import sys
import os
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    pass

# 네트워크 연결 대기 설정
NETWORK_CHECK_HOST = "api.heyground.com"
NETWORK_MAX_RETRIES = 5
NETWORK_RETRY_INTERVAL = 30  # 초

# 같은 디렉토리의 heyground.py에서 함수 임포트
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heyground import (
    load_token,
    get_my_reservations,
    find_available_rooms,
    build_booking_data,
    check_credit,
    create_reservation,
    ROOMS,
)

# === 정기 회의 설정 ===
# 요일: 0=월, 1=화, 2=수, 3=목, 4=금
# reminder_webhook_key: token.json에 저장된 webhook URL 키 이름
WEEKLY_SCHEDULE = [
    {
        "weekday": 0, "start": "0930", "end": "1030",
        "dtl": "정기 회의",
        "preferred_rooms": ["M7-6C", "M7-6B", "M7-6A"],
        "reminder_webhook_key": "slack_webhook_url",  # #사업팀-셀리더-2025
    },
    {
        "weekday": 2, "start": "1100", "end": "1200",
        "dtl": "정기 회의",
        "preferred_rooms": ["M7-6C", "M7-6B", "M7-6A"],
        "reminder_webhook_key": "slack_webhook_url",
    },
    # ax daily camp — 화/수/목/금 10:00~10:30, 7B 선호
    *[
        {
            "weekday": wd, "start": "1000", "end": "1030",
            "dtl": "ax daily camp",
            "preferred_rooms": ["M7-6B", "M7-6C", "M7-6A"],
            "reminder_webhook_key": "slack_webhook_url_ax_hero_camp",  # #ax-hero-camp
        }
        for wd in (1, 2, 3, 4)
    ],
]

PREFERRED_CAPACITY = 6       # 6인실
PREFERRED_FLOOR = "07"       # 7층
LOOKAHEAD_DAYS = 14          # 2주 뒤까지

# 휴일·휴가 블랙리스트 (dtl별 YYYY-MM-DD 제외 날짜)
# 취소만 하면 재예약되니, 제외하려면 반드시 여기에 등록
EXCLUDED_DATES = {
    "ax daily camp": {
        "2026-05-01",  # 근로자의 날
        "2026-05-05",  # 어린이날
        "2026-05-06",  # Rich 휴가
        "2026-05-07",  # Rich 휴가
    },
}
LOG_PATH = Path(__file__).parent / "weekly_booking.log"
RUN_MARKER = Path(__file__).parent / ".last_run_date"


def already_ran_today():
    """오늘 이미 실행됐는지 확인 (RunAtLoad + StartCalendarInterval 중복 방지)"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    if RUN_MARKER.exists() and RUN_MARKER.read_text().strip() == today_str:
        return True
    return False


def mark_today_run():
    """오늘 실행 완료 마킹"""
    RUN_MARKER.write_text(datetime.now().strftime("%Y-%m-%d"))


def log(msg):
    """로그 출력 + 파일 기록"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def wait_for_network():
    """네트워크 연결될 때까지 대기 (Mac 잠자기 복귀 대응)

    Returns:
        True: 연결 성공, False: 최대 재시도 초과
    """
    for attempt in range(1, NETWORK_MAX_RETRIES + 1):
        try:
            socket.getaddrinfo(NETWORK_CHECK_HOST, 443)
            return True
        except socket.gaierror:
            log(f"  네트워크 대기 중... ({attempt}/{NETWORK_MAX_RETRIES})")
            if attempt < NETWORK_MAX_RETRIES:
                time.sleep(NETWORK_RETRY_INTERVAL)
    return False


def get_target_dates():
    """오늘부터 2주 내 예약 대상 날짜 목록 반환

    Returns:
        list of (date, schedule_entry)
    """
    today = datetime.now().date()
    targets = []

    for day_offset in range(0, LOOKAHEAD_DAYS + 1):
        d = today + timedelta(days=day_offset)
        weekday = d.weekday()  # 0=월 ~ 6=일
        date_iso = d.strftime("%Y-%m-%d")

        for entry in WEEKLY_SCHEDULE:
            if weekday != entry["weekday"]:
                continue
            # 블랙리스트 (휴일·휴가) 체크
            excluded = EXCLUDED_DATES.get(entry["dtl"], set())
            if date_iso in excluded:
                continue
            targets.append((d, entry))

    return targets


def is_already_booked(my_reservations, date, start, end):
    """내 예약 목록에서 해당 날짜·시간 슬롯이 이미 잡혀있는지 확인"""
    date_str = date.strftime("%Y%m%d")

    for r in my_reservations:
        if r["de_use"] == date_str:
            r_start = int(r["time_use_start"])
            r_end = int(r["time_use_end"])
            # 시간이 겹치면 이미 예약된 것으로 간주
            if r_start < int(end) and r_end > int(start):
                return True
    return False


def send_error_alert(config, message):
    """Slack으로 에러 알림 발송"""
    webhook_url = config.get("slack_webhook_url")
    if not webhook_url:
        return
    payload = {"text": f":rotating_light: *회의실 자동예약 오류*\n{message}"}
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception:
        pass


def main():
    dry_run = "--dry" in sys.argv

    # 당일 중복 실행 방지 (RunAtLoad + StartCalendarInterval 동시 트리거 대응)
    if not dry_run and already_ran_today():
        log("오늘 이미 실행됨 — 중복 실행 방지로 스킵")
        return

    if dry_run:
        log("=== 테스트 모드 (예약 없이 결과만 출력) ===")
    else:
        log("=== 정기 회의실 자동 예약 시작 ===")

    # 네트워크 연결 확인 (Mac 잠자기 복귀 시 DNS 실패 방지)
    if not wait_for_network():
        msg = f"네트워크 연결 실패 — {NETWORK_MAX_RETRIES}회 재시도 후 포기"
        log(f"ERROR: {msg}")
        return

    config = load_token()
    token = config["access_token"]
    location = config.get("location", "seoulsoop")

    # 내 기존 예약 조회 (401 시 토큰 갱신 후 재시도)
    try:
        my_reservations = get_my_reservations(location, token)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            log("토큰 만료 감지 — 자동 갱신 시도")
            try:
                from heyground import _refresh_tokens
                config = _refresh_tokens(config)
                token = config["access_token"]
                my_reservations = get_my_reservations(location, token)
                log("토큰 갱신 성공 — 예약 조회 재시도 완료")
            except Exception as refresh_err:
                msg = f"토큰 자동 갱신 실패: {refresh_err}"
                log(f"ERROR: {msg}")
                send_error_alert(config, msg)
                return
        else:
            raise
    log(f"기존 예약 {len(my_reservations)}건 확인")

    # 예약 대상 날짜 계산
    targets = get_target_dates()
    log(f"예약 대상 슬롯: {len(targets)}건")

    booked = 0
    skipped = 0
    failed = 0

    for date, entry in targets:
        start = entry["start"]
        end = entry["end"]
        dtl = entry["dtl"]
        preferred_rooms = entry["preferred_rooms"]
        date_label = f"{date.strftime('%Y-%m-%d')} ({['월','화','수','목','금','토','일'][date.weekday()]}) {start[:2]}:{start[2:]}~{end[:2]}:{end[2:]} [{dtl}]"

        # 중복 체크
        if is_already_booked(my_reservations, date, start, end):
            log(f"  SKIP  {date_label} — 이미 예약 있음")
            skipped += 1
            continue

        # 빈 방 찾기
        date_dash = date.strftime("%Y-%m-%d")
        date_ymd = date.strftime("%Y%m%d")

        try:
            available = find_available_rooms(
                date_dash, start, end,
                PREFERRED_CAPACITY, location, token, PREFERRED_FLOOR
            )
        except Exception as e:
            log(f"  FAIL  {date_label} — 조회 오류: {e}")
            failed += 1
            continue

        if not available:
            log(f"  FAIL  {date_label} — 빈 방 없음")
            failed += 1
            continue

        # 선호 방 우선 선택 (스케줄별 preferred_rooms 사용)
        room = None
        available_names = {r["name"]: r for r in available}
        for pref in preferred_rooms:
            if pref in available_names:
                room = available_names[pref]
                break
        if room is None:
            room = available[0]  # 선호 방이 모두 찬 경우 기존 로직 (용량·층 순)

        if dry_run:
            log(f"  PLAN  {date_label} → {room['name']} ({room['capacity']}인실)")
            booked += 1
            continue

        # 예약 실행
        try:
            booking = build_booking_data(
                room["code"], date_ymd, start, end,
                dtl=dtl, location=location
            )
            credit_info = check_credit(booking, token)
            result = create_reservation(booking, token)
            log(f"  DONE  {date_label} → {room['name']} (코드: {result['cd']}, 크레딧: {credit_info['credit']})")
            booked += 1
        except Exception as e:
            log(f"  FAIL  {date_label} → {room['name']} — 예약 오류: {e}")
            failed += 1

    log(f"=== 완료: 예약 {booked}건 / 스킵 {skipped}건 / 실패 {failed}건 ===\n")

    # 당일 회의실 예약 Slack 리마인드
    if not dry_run:
        send_today_reminder(my_reservations, config)
        mark_today_run()


DEFAULT_WEBHOOK_KEY = "slack_webhook_url"  # 스케줄 매칭 실패 시 기본 채널


def _match_schedule_entry(weekday, start, end):
    """오늘 예약을 WEEKLY_SCHEDULE 엔트리와 매칭. 매칭 실패 시 None."""
    for entry in WEEKLY_SCHEDULE:
        if entry["weekday"] == weekday and entry["start"] == start and entry["end"] == end:
            return entry
    return None


def send_today_reminder(my_reservations, config):
    """오늘 예약된 회의실이 있으면 Slack으로 리마인드 발송 (채널별 분기)"""
    today = datetime.now().date()
    today_str = today.strftime("%Y%m%d")
    weekday = today.weekday()
    weekday_names = ['월', '화', '수', '목', '금', '토', '일']

    # 오늘 예약 → webhook_key별 그룹핑
    grouped: dict = {}
    for r in my_reservations:
        if r["de_use"] != today_str:
            continue
        s = r["time_use_start"]
        e = r["time_use_end"]
        room_name = r.get("pblspc_nm", "회의실")

        entry = _match_schedule_entry(weekday, s, e)
        webhook_key = entry["reminder_webhook_key"] if entry else DEFAULT_WEBHOOK_KEY

        grouped.setdefault(webhook_key, []).append({
            "time": f"{s[:2]}:{s[2:]}~{e[:2]}:{e[2:]}",
            "room": room_name,
            "dtl": entry["dtl"] if entry else "회의",
        })

    if not grouped:
        log("오늘 예약 없음 — 리마인드 생략")
        return

    date_label = f"{today.strftime('%m/%d')} ({weekday_names[weekday]})"

    # 그룹별 발송
    for webhook_key, bookings in grouped.items():
        webhook_url = config.get(webhook_key)
        if not webhook_url:
            log(f"Slack webhook 미설정 (키: {webhook_key}) — {len(bookings)}건 리마인드 생략")
            continue

        lines = [f":calendar: *오늘의 회의실 예약 — {date_label}*", ""]
        for b in bookings:
            lines.append(f"• *{b['time']}*  :office:  {b['room']}")
        lines.append("")
        lines.append("_자동 리마인드 by 리치 비서_")
        payload = {"text": "\n".join(lines)}

        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                log(f"Slack 리마인드 발송 완료 (키: {webhook_key}, {len(bookings)}건)")
            else:
                log(f"Slack 리마인드 실패 (키: {webhook_key}): {resp.status_code} {resp.text}")
        except Exception as e:
            log(f"Slack 리마인드 오류 (키: {webhook_key}): {e}")


if __name__ == "__main__":
    main()
