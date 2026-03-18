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
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    pass

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
WEEKLY_SCHEDULE = [
    # (요일 번호, 시작, 종료, 용도)
    # 0=월, 1=화, 2=수, 3=목, 4=금
    (0, "0930", "1030", "정기 회의"),   # 월요일 09:30~10:30
    (2, "1100", "1200", "정기 회의"),   # 수요일 11:00~12:00
]

PREFERRED_CAPACITY = 6       # 6인실
PREFERRED_FLOOR = "07"       # 7층
PREFERRED_ROOMS = ["M7-6C", "M7-6B", "M7-6A"]  # 선호 순서 (7C > 7B > 7A)
LOOKAHEAD_DAYS = 14          # 2주 뒤까지
LOG_PATH = Path(__file__).parent / "weekly_booking.log"


def log(msg):
    """로그 출력 + 파일 기록"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def get_target_dates():
    """오늘부터 2주 내 예약 대상 날짜 목록 반환

    Returns:
        list of (date, start_time, end_time, dtl)
    """
    today = datetime.now().date()
    targets = []

    for day_offset in range(0, LOOKAHEAD_DAYS + 1):
        d = today + timedelta(days=day_offset)
        weekday = d.weekday()  # 0=월 ~ 6=일

        for sched_weekday, start, end, dtl in WEEKLY_SCHEDULE:
            if weekday == sched_weekday:
                targets.append((d, start, end, dtl))

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

    if dry_run:
        log("=== 테스트 모드 (예약 없이 결과만 출력) ===")
    else:
        log("=== 정기 회의실 자동 예약 시작 ===")

    config = load_token()
    token = config["access_token"]
    location = config.get("location", "seoulsoop")

    # 내 기존 예약 조회
    try:
        my_reservations = get_my_reservations(location, token)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            msg = "access_token 만료 — 브라우저 헤이그라운드 로그인 후 Local Storage에서 토큰 재발급 필요"
            log(f"ERROR: {msg}")
            send_error_alert(config, msg)
            return
        raise
    log(f"기존 예약 {len(my_reservations)}건 확인")

    # 예약 대상 날짜 계산
    targets = get_target_dates()
    log(f"예약 대상 슬롯: {len(targets)}건")

    booked = 0
    skipped = 0
    failed = 0

    for date, start, end, dtl in targets:
        date_label = f"{date.strftime('%Y-%m-%d')} ({['월','화','수','목','금','토','일'][date.weekday()]}) {start[:2]}:{start[2:]}~{end[:2]}:{end[2:]}"

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

        # 선호 방 우선 선택
        room = None
        available_names = {r["name"]: r for r in available}
        for pref in PREFERRED_ROOMS:
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


def send_today_reminder(my_reservations, config):
    """오늘 예약된 회의실이 있으면 Slack으로 리마인드 발송"""
    webhook_url = config.get("slack_webhook_url")
    if not webhook_url:
        log("Slack webhook URL 미설정 — 리마인드 생략")
        return

    today = datetime.now().date()
    today_str = today.strftime("%Y%m%d")
    weekday_names = ['월', '화', '수', '목', '금', '토', '일']

    # 오늘 예약 필터링
    today_bookings = []
    for r in my_reservations:
        if r["de_use"] == today_str:
            s = r["time_use_start"]
            e = r["time_use_end"]
            room_name = r.get("pblspc_nm", "회의실")
            today_bookings.append({
                "time": f"{s[:2]}:{s[2:]}~{e[:2]}:{e[2:]}",
                "room": room_name,
                "code": r.get("cd", ""),
            })

    if not today_bookings:
        log("오늘 예약 없음 — 리마인드 생략")
        return

    # Slack 메시지 구성
    date_label = f"{today.strftime('%m/%d')} ({weekday_names[today.weekday()]})"
    lines = [f":calendar: *오늘의 회의실 예약 — {date_label}*", ""]
    for b in today_bookings:
        lines.append(f"• *{b['time']}*  :office:  {b['room']}")
    lines.append("")
    lines.append("_자동 리마인드 by 리치 비서_")

    payload = {"text": "\n".join(lines)}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 200:
            log(f"Slack 리마인드 발송 완료 ({len(today_bookings)}건)")
        else:
            log(f"Slack 리마인드 실패: {resp.status_code} {resp.text}")
    except Exception as e:
        log(f"Slack 리마인드 오류: {e}")


if __name__ == "__main__":
    main()
